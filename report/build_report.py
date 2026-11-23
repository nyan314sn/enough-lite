"""Build report.html (one self-contained file) from report/report.md (or report_source.txt).

  python report\\build_report.py [--usage PATH]

- Images are embedded as base64 (resized JPEG), so the file opens by double-click.
- Colours are the app's own (web/src/styles.css :root).
- Token tables and charts are built from runs/usage.jsonl when the report is built:
    plan statistics use the eval harness sessions ("eval-*") with all six specialists present;
    the cost of a What If, a question and an intake message comes from every other metered run.
- Every placeholder is written [[TODO: ...]]; the build prints the full list.
Needs: markdown, Pillow (both in miniconda).
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import json
import re
from collections import defaultdict
from pathlib import Path

import markdown
from PIL import Image

HERE = Path(__file__).resolve().parent
LITE = HERE.parent
DOCS = LITE / "docs"
OUT = LITE / "report.html"

# the app's palette: Royal Indigo, light theme (web/src/styles.css, docs/THEME_ROYAL_INDIGO.css)
BG, PANEL, SURFACE2, LINE, TEXT, TEXT2, MUTED = "#F7F7FC", "#FFFFFF", "#F1F1F9", "#E2E2F0", "#0F172A", "#334155", "#586579"
ACCENT, ACCENT2, SOFT = "#4F46E5", "#4338CA", "#EEF2FF"
BRAND, SOFT2 = "#1E1B4B", "#E0E7FF"   # Midnight Indigo for headlines; a deeper indigo tint
GOOD, GOOD_SOFT, WARN, WARN_SOFT, DANGER = "#15803D", "#DCFCE7", "#B45309", "#FEF3C7", "#BE123C"
FONT = '"Inter","Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",sans-serif'

PRICE = {"input": 0.10, "cached": 0.01, "cache_write": 0.125, "output": 0.50}  # USD per million tokens, Haiku 5.5 (app/llm.py)
PLANS_PER_USER_MONTH = 4       # assumption, flagged in the report
WHATIFS_PER_PLAN = 3           # assumption, flagged in the report
INTAKE_CALLS_PER_PLAN = 10     # assumption, flagged in the report
TODO_RE = re.compile(r"\[\[TODO:.*?\]\]", re.S)
SIX = {"longevity", "family", "tax", "research", "markets", "adviser"}


# ---------------------------------------------------------------- helpers shared with build_slides.py
def img_data_uri(path: Path, max_w: int = 1000, quality: int = 80) -> str:
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def todo(text: str) -> str:
    return f"[[TODO: {text}]]"


def load_usage(path: Path | None = None) -> list[dict]:
    p = path or (LITE / "runs" / "usage.jsonl")
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return [r for r in rows if r.get("ok", True)]


def usd(r: dict) -> float:
    return (r["input"] * PRICE["input"] + r["cached"] * PRICE["cached"] + r["cache_write"] * PRICE["cache_write"]
            + r["output"] * PRICE["output"]) / 1e6


def usage_stats(rows: list[dict]) -> dict | None:
    """Plan statistics from eval sessions with all six specialists; costs of other run kinds from every row."""
    if not rows:
        return None
    all_runs: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        all_runs[r["run_id"]].append(r)
    plan_runs = {k: v for k, v in all_runs.items()
                 if SIX <= {x["agent"] for x in v} and all(x["session"].startswith("eval-") for x in v)}
    if not plan_runs:
        return None
    n = len(plan_runs)
    agents: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for run in plan_runs.values():
        for x in run:
            a = agents[x["agent"]]
            a["input"] += x.get("input_tokens", 0) / n
            a["cached"] += x.get("cached_tokens", 0) / n
            a["cache_write"] += x.get("cache_write_tokens", 0) / n
            a["output"] += x.get("output_tokens", 0) / n
            a["cost"] += x.get("cost_usd", 0.0) / n
            a["seconds"] += x.get("seconds", 0.0) / n
    costs = sorted(sum(x.get("cost_usd", 0.0) for x in run) for run in plan_runs.values())
    tot = {k: sum(v[k] for v in agents.values()) for k in ("input", "cached", "cache_write", "output", "cost", "seconds")}
    # cost of the other kinds of metered run
    kinds: dict[str, list[float]] = defaultdict(list)
    for k, v in all_runs.items():
        if k in plan_runs:
            continue
        ag = {x["agent"] for x in v}
        c = sum(x.get("cost_usd", 0.0) for x in v)
        if ag & {"ask", "ask_intent", "ask_turn_read"}:
            kinds["ask"].append(c)
        elif ag & {"intake", "turn_read"}:
            kinds["intake"].append(c)
        elif "markets" in ag:
            kinds["whatif"].append(c)
    mean = lambda xs: sum(xs) / len(xs) if xs else 0.0  # noqa: E731
    in_all = tot["input"] + tot["cached"] + tot["cache_write"]
    return {"n": n, "agents": dict(agents), "mean": tot, "p90": costs[int(0.9 * (len(costs) - 1))], "max": costs[-1],
            "median": costs[len(costs) // 2],
            "input_all": in_all, "cached_share": tot["cached"] / in_all, "write_share": tot["cache_write"] / in_all,
            "uncached_cost": (in_all * PRICE["input"] + tot["output"] * PRICE["output"]) / 1e6,
            "whatif": mean(kinds["whatif"]), "whatif_n": len(kinds["whatif"]), "ask": mean(kinds["ask"]), "ask_n": len(kinds["ask"]),
            "intake": mean(kinds["intake"]), "intake_n": len(kinds["intake"])}


def session_cost(st: dict) -> float:
    """One planning session: one plan, a few What Ifs and questions, and the intake messages."""
    return st["mean"]["cost"] + WHATIFS_PER_PLAN * st["whatif"] + INTAKE_CALLS_PER_PLAN * st["intake"]


def money(x: float) -> str:
    return f"${x:,.4f}" if x < 1 else f"${x:,.2f}"


# ---------------------------------------------------------------- SVG
def agents_svg(legend: bool = True) -> str:
    """Seven agents, and the MCP server outside the app. Inline SVG in the app's palette. legend=False drops the two note lines (slides)."""
    f = f"font-family:{FONT}"
    W, H = 980, (506 if legend else 462)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Diagram. The person talks to Intake. Intake sends a profile to the lead adviser. The lead adviser starts Longevity, Family, Tax, Research and Markets. Longevity, Family and Tax also hand their findings to Markets. Every specialist returns a finding to the lead adviser, who writes the plan. A number check sits between the lead adviser and the plan. Outside the app, any AI assistant reaches the Enough tools through the MCP server, which has no AI model inside." xmlns="http://www.w3.org/2000/svg" style="{f}">',
         f'<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{ACCENT}"/></marker>'
         f'<marker id="ahg" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="{MUTED}"/></marker></defs>',
         f'<rect width="{W}" height="{H}" rx="14" fill="{PANEL}" stroke="{LINE}"/>']
    box = lambda x, y, w, h, fill, stroke, dash="": (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")  # noqa: E731
    txt = lambda x, y, t, size=13, fill=TEXT, weight=400, anchor="middle", fam="": f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"' + (f' font-family="{fam}"' if fam else "") + f">{t}</text>"  # noqa: E731
    arrow = lambda x1, y1, x2, y2, color=ACCENT, w=2, dash="", mk="ah": f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{w}"' + (f' stroke-dasharray="{dash}"' if dash else "") + f' marker-end="url(#{mk})"/>'  # noqa: E731
    # top row
    s += [box(20, 26, 110, 48, SURFACE2, MUTED), txt(75, 55, "The person", 14),
          arrow(130, 50, 158, 50),
          box(162, 16, 190, 68, SOFT, ACCENT), txt(257, 42, "Intake", 16, TEXT, 700), txt(257, 60, "text to profile, estimates,", 12, MUTED), txt(257, 74, "person approves each field", 12, MUTED),
          arrow(352, 50, 384, 50), txt(368, 40, "profile", 11, MUTED),
          box(388, 10, 250, 80, ACCENT, ACCENT2), txt(513, 40, "Lead adviser", 18, "#fff", 700), txt(513, 60, "reads findings, writes needs, wants,", 12, "#fff"), txt(513, 76, "wishes and three actions", 12, "#fff"),
          arrow(638, 50, 672, 50),
          box(676, 22, 130, 56, GOOD_SOFT, GOOD), txt(741, 46, "Number check", 14, TEXT, 700), txt(741, 64, "every figure from a tool", 11, MUTED),
          arrow(806, 50, 838, 50, GOOD),
          box(842, 22, 120, 56, PANEL, ACCENT, "5 4"), txt(902, 46, "The plan", 14, TEXT, 700), txt(902, 64, "needs, wants, wishes", 11, MUTED)]
    # specialists
    specs = [("Longevity", ["life_table"]), ("Family", ["family_costs"]), ("Tax", ["tax_estimate"]),
             ("Research", ["search_sources"]), ("Markets", ["simulate_plan", "test_similar_households"])]
    bw, gap = 170, 15
    x0 = (W - (5 * bw + 4 * gap)) / 2
    cxs = []
    for i, (name, tools) in enumerate(specs):
        x = x0 + i * (bw + gap)
        cx = x + bw / 2
        cxs.append(cx)
        top = 5 + i * 0  # placeholder to keep lines simple
        sx = 428 + i * 40
        s.append(arrow(sx, 90, int(cx - 12), 158, ACCENT, 1.8))
        s.append(arrow(int(cx + 12), 158, sx + 24, 92, MUTED, 1.2, "4 3", "ahg"))
        s.append(box(int(x), 160, bw, 62, SOFT if name != "Markets" else SOFT2, ACCENT))
        s.append(txt(int(cx), 187, name, 16, TEXT, 700))
        s.append(txt(int(cx), 207, "one job", 12, MUTED))
        s.append(arrow(int(cx), 222, int(cx), 246, MUTED, 1.4, "", "ahg"))
        h = 26 + 16 * (len(tools) - 1)
        s.append(box(int(x), 248, bw, h, SURFACE2, LINE))
        for j, t in enumerate(tools):
            s.append(txt(int(cx), 266 + 16 * j, f"{t}()", 12, TEXT, 400, "middle", "Consolas,monospace"))
    # hand-offs to Markets
    mx = cxs[4]
    bus = 336
    for cx in cxs[:3]:
        s.append(f'<line x1="{int(cx)}" y1="276" x2="{int(cx)}" y2="{bus}" stroke="{ACCENT}" stroke-width="1.6"/>')
    s.append(f'<polyline points="{int(cxs[0])},{bus} {int(mx)},{bus} {int(mx)},296" fill="none" stroke="{ACCENT}" stroke-width="1.6" marker-end="url(#ah)"/>')
    s.append(txt(int((cxs[0] + mx) / 2), bus + 18, "hand-offs: Longevity, Family and Tax pass their findings to Markets before it runs", 12, ACCENT2, 600))
    # the MCP server: outside the app
    s.append(f'<rect x="10" y="364" width="960" height="76" rx="12" fill="none" stroke="{ACCENT}" stroke-width="1.4" stroke-dasharray="6 4"/>')
    s += [box(24, 376, 190, 52, SURFACE2, MUTED), txt(119, 398, "Any AI assistant", 14, TEXT, 700), txt(119, 416, "e.g. Claude Desktop", 11, MUTED),
          arrow(214, 402, 262, 402), txt(238, 394, "MCP", 11, ACCENT2, 700),
          box(266, 376, 210, 52, ACCENT, ACCENT2), txt(371, 398, "MCP server", 15, "#fff", 700), txt(371, 416, "mcp_server.py, no AI inside", 11, "#fff"),
          arrow(476, 402, 524, 402),
          box(528, 376, 430, 52, PANEL, ACCENT),
          txt(743, 396, "plan_check()  social_security_estimate()  tax_estimate()", 11, TEXT, 400, "middle", "Consolas,monospace"),
          txt(743, 414, "life_expectancy()  family_costs()  search_rules()", 11, TEXT, 400, "middle", "Consolas,monospace")]
    s.append(txt(24, 458, "MCP server, optional and outside the web app: any assistant gets Enough&#8217;s checked numbers and sources, with the same engine and refusals.", 12, ACCENT2, 600, "start"))
    if legend:
        s.append(txt(24, 482, "Solid indigo: work handed down. Dashed grey: findings handed back. Every hand-off shows on screen as &#8220;Team talk&#8221;. Tools are plain Python, no model.", 12, MUTED, 400, "start"))
        s.append(txt(24, 500, "Markets also tests the plans of the five most similar households (section 4). All seven agents run on Claude Haiku 5.5. A dollar cap checks each agent before it starts.", 12, MUTED, 400, "start"))
    s.append("</svg>")
    return "".join(s)


def cost_chart_svg(stats: dict | None) -> str:
    W, H, L = 760, 250, 150
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Bar chart: mean cost per plan for each agent" xmlns="http://www.w3.org/2000/svg" style="font-family:{FONT}"><rect width="{W}" height="{H}" rx="14" fill="{PANEL}" stroke="{LINE}"/>']
    s.append(f'<text x="20" y="28" fill="{TEXT}" font-size="15" font-weight="700">Cost of one plan, by agent (USD)</text>')
    if not stats:
        s.append(f'<text x="20" y="80" fill="{WARN}" font-size="13">[[TODO: chart fills from runs/usage.jsonl]]</text>')
    else:
        items = sorted(stats["agents"].items(), key=lambda kv: -kv[1]["cost"])
        mx = max(v["cost"] for _, v in items) or 1e-9
        rowh = min(32, (H - 80) / max(1, len(items)))
        for i, (n, v) in enumerate(items):
            y = 46 + i * rowh
            w = (W - L - 130) * v["cost"] / mx
            s.append(f'<text x="{L - 10}" y="{y + 16}" fill="{TEXT}" font-size="13" text-anchor="end">{html.escape(n)}</text>'
                     f'<rect x="{L}" y="{y}" width="{max(w, 2):.0f}" height="22" rx="4" fill="{ACCENT}"/>'
                     f'<text x="{L + max(w, 2) + 8:.0f}" y="{y + 16}" fill="{TEXT}" font-size="12">{money(v["cost"])} ({100 * v["cost"] / stats["mean"]["cost"]:.0f}%)</text>')
        s.append(f'<text x="{W - 20}" y="{H - 12}" fill="{MUTED}" font-size="12" text-anchor="end">Mean of {stats["n"]} plans, measured by the app&#8217;s meter (runs/usage.jsonl)</text>')
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- data-wired tables (HTML)
def table_html(head: list[str], rows: list[list[str]], cls: str = "") -> str:
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def token_tables(stats: dict | None) -> str:
    T = todo
    if not stats:
        return f"<p>{T('no usage data: run the eval harness, then rebuild')}</p>"
    out = ["<h3>Tokens and cost of one plan, by agent</h3>"]
    head = ["Agent", "Input (uncached)", "Cached input (read)", "Cache write", "Output", "Cost", "Share"]
    m = stats["mean"]
    rows = []
    for n, v in sorted(stats["agents"].items(), key=lambda kv: -kv[1]["cost"]):
        rows.append([html.escape(n), f"{v['input']:,.0f}", f"{v['cached']:,.0f}", f"{v['cache_write']:,.0f}", f"{v['output']:,.0f}", money(v["cost"]), f"{100 * v['cost'] / m['cost']:.0f}%"])
    rows.append(["<b>One plan, all six agents</b>", f"<b>{m['input']:,.0f}</b>", f"<b>{m['cached']:,.0f}</b>", f"<b>{m['cache_write']:,.0f}</b>", f"<b>{m['output']:,.0f}</b>", f"<b>{money(m['cost'])}</b>", "<b>100%</b>"])
    out.append(table_html(head, rows))
    tot_tokens = m["input"] + m["cached"] + m["cache_write"] + m["output"]
    out.append(f"<p class='note'>Means over {stats['n']} plans from the 300-household eval (sessions <code>eval-*</code> in <code>runs/usage.jsonl</code>), measured by the app's meter. About {tot_tokens:,.0f} tokens a plan. Cost per plan: median {money(stats['median'])}, 90th percentile {money(stats['p90'])}, highest {money(stats['max'])}. Intake runs on rules and calls the model only when the rules fail; it is costed separately below.</p>")
    out.append("<h3>The other things a user does</h3>")
    out.append(table_html(["Action", "Mean cost", "Metered runs", "Note"], [
        ["A What If (adviser, markets, tax re-run)", money(stats["whatif"]), f"{stats['whatif_n']:,}", "Re-uses the profile; three of six agents run"],
        ["A question about the plan or the rules", money(stats["ask"]), f"{stats['ask_n']:,}", "One small classification call and a cited answer"],
        ["One intake message that needs the model", money(stats["intake"]), f"{stats['intake_n']:,}", "Most messages are read by rules and cost nothing"]]))
    out.append("<h3>Cost per user and at scale</h3>")
    sc = session_cost(stats)
    pm = sc * PLANS_PER_USER_MONTH
    rows = [["One plan", money(m["cost"]), f"Mean over {stats['n']} measured plans"],
            ["One planning session", money(sc), f"One plan, plus {WHATIFS_PER_PLAN} What Ifs and {INTAKE_CALLS_PER_PLAN} intake model calls. These two counts are my assumption; the real user test will show the true figure"],
            ["Cost per user per month", money(pm), f"{PLANS_PER_USER_MONTH} planning sessions a month (my assumption; the user test will show the real figure)"],
            ["100 users, a month", money(pm * 100), "Cost per user times 100"],
            ["10,000 users, a month", money(pm * 10_000), "Cost per user times 10,000. Assumes the price per token does not change and the rate limits hold. Hosting is not included"],
            ["Worst case, one plan", "$0.05", "The per-run dollar cap. No run can cost more"]]
    out.append(table_html(["", "Value", "How it is worked out"], rows))
    out.append("<h3>Caching: before and after</h3>")
    full = stats["input_all"]
    saved = 100 * (1 - m["cost"] / stats["uncached_cost"]) if stats["uncached_cost"] else 0
    rows = [["Without caching (computed: same tokens, all at the full input price)", f"{full:,.0f}", "0", money(stats["uncached_cost"])],
            ["With caching (measured, the shipped app)", f"{m['input']:,.0f}", f"{m['cached']:,.0f} read, {m['cache_write']:,.0f} written", money(m["cost"])],
            ["Saving", "", "", f"<b>{saved:.0f}%</b> a plan"]]
    out.append(table_html(["", "Input tokens at full price", "Cached input tokens", "Cost per plan"], rows))
    out.append(f"<p class='note'>{100 * stats['cached_share']:.0f}% of input tokens are cache reads, {100 * stats['write_share']:.0f}% are cache writes (priced at 1.25 times input), under 1% are uncached. I did not run the 300 households with caching switched off, so the no-cache row is arithmetic, not a measurement.</p>")
    return "\n".join(out)


def md_section(md: str, title_part: str) -> str:
    m = re.search(r"^## [^\n]*" + re.escape(title_part) + r"[^\n]*\n(.*?)(?=^## |\Z)", md, re.S | re.M)
    return m.group(0) if m else ""


def tuning_table() -> str:
    b, a = LITE / "runs" / "tuning_before.json", LITE / "runs" / "tuning_after.json"
    if not (b.exists() and a.exists()):
        return f"<p>{todo('runs/tuning_before.json and tuning_after.json missing')}</p>"
    jb, ja = json.loads(b.read_text(encoding="utf-8")), json.loads(a.read_text(encoding="utf-8"))
    names = {"longevity": "Longevity", "family": "Family", "tax": "Tax", "research": "Research", "markets": "Markets", "adviser": "Lead adviser"}
    rows = []
    for k, nm in names.items():
        pb, pa = jb["per_agent"][k], ja["per_agent"][k]
        rows.append([nm, f"{pb['first_try_pass']} of {pb['runs']} ({100 * pb['first_try_pass'] // pb['runs']}%)", f"{pb['fallbacks']}", f"{pa['first_try_pass']} of {pa['runs']} ({100 * pa['first_try_pass'] // pa['runs']}%)", f"{pa['fallbacks']}"])
    cb = sum(r["cost"] for r in jb["runs"]) / len(jb["runs"])
    ca = sum(r["cost"] for r in ja["runs"]) / len(ja["runs"])
    rows.append(["<b>Cost of one plan (mean of 10)</b>", money(cb), "", money(ca), ""])
    kinds = jb["failure_kinds"]
    k_txt = "; ".join(f"{len(v)} {html.escape(k)}" for k, v in kinds.items())
    return (table_html(["Agent", "Before: text passed the number check first try", "Before: fell back to the template", "After: first try", "After: fell back"], rows)
            + f"<p class='note'>Ten households (<code>runs/tuning_before.json</code>, <code>tuning_after.json</code>). The {sum(len(v) for v in kinds.values())} rejected figures before the tuning: {k_txt}.</p>")


DIRECTIVES = {"agents_svg": lambda ctx: f'<figure class="svgfig">{agents_svg()}<figcaption>Figure 1. Seven agents. The lead adviser starts the specialists; three of them also hand findings to Markets; a number check stands between the lead adviser and the person. Below, outside the app: the optional MCP server.</figcaption></figure>',
              "token_tables": lambda ctx: token_tables(ctx["stats"]),
              "cost_chart": lambda ctx: f'<figure class="svgfig">{cost_chart_svg(ctx["stats"])}</figure>',
              "tuning_table": lambda ctx: tuning_table()}


# ---------------------------------------------------------------- markdown to html
def resolve_img(src: str) -> Path:
    for base in (DOCS, HERE):
        p = (base / src)
        if p.exists():
            return p
    return DOCS / src


def render_chunk(md: str) -> str:
    h = markdown.markdown(md, extensions=["tables", "sane_lists"])

    def fig(m):
        alt, src = html.unescape(m.group(1)), m.group(2)
        p = resolve_img(src)
        if not p.exists():
            return f'<p class="todo-box">[[TODO: image missing: {html.escape(src)}]]</p>'
        small = "narrow" in src
        return (f'<figure class="shot{" narrow" if small else ""}"><img alt="{html.escape(alt)}" src="{img_data_uri(p)}">'
                f'<figcaption>{html.escape(alt)}</figcaption></figure>')
    h = re.sub(r'<p><img alt="([^"]*)" src="([^"]+)"\s*/?></p>', fig, h)
    h = TODO_RE.sub(lambda m: f'<mark class="todo">{m.group(0)}</mark>', h)
    return h


CSS = f"""
:root{{--brand:{BRAND};--bg:{BG};--panel:{PANEL};--accent:{ACCENT};--text:{TEXT};--muted:{MUTED};--line:{LINE};--soft:{SOFT}}}
*{{box-sizing:border-box}}
html{{background:var(--bg)}}
body{{margin:0 auto;max-width:900px;padding:40px 30px 80px;background:var(--panel);color:var(--text);font:16px/1.6 {FONT}}}
h1{{font-size:44px;line-height:1.1;margin:.2em 0 .3em;letter-spacing:-.02em;color:var(--brand)}} h1::after{{content:".";color:var(--accent)}}
h2{{font-size:25px;margin:2.1em 0 .5em;padding-top:.6em;border-top:2px solid var(--accent);color:var(--brand)}}
h3{{font-size:17px;margin:1.5em 0 .4em;color:var(--brand)}}
h4{{font-size:15px;margin:1.2em 0 .3em;color:var(--brand)}}
p,li{{margin:.5em 0}} a{{color:var(--accent)}} strong{{color:var(--text)}}
code{{font-family:Consolas,monospace;background:{SOFT};padding:1px 5px;border-radius:4px;font-size:.9em}}
pre{{background:{SOFT};border:1px solid var(--line);border-radius:8px;padding:8px 10px;font:12px/1.4 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;margin:.8em 0;break-inside:avoid}}
pre code{{background:none;padding:0;font-size:inherit}}
table{{border-collapse:collapse;width:100%;margin:1em 0;font-size:13.5px}}
th,td{{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}}
th{{background:{SOFT};color:{ACCENT2}}}
tr{{break-inside:avoid}}
figure{{margin:1.2em 0;break-inside:avoid}}
figure.shot img{{display:block;margin:0 auto;max-width:100%;max-height:6in;width:auto;border:1px solid var(--line);border-radius:10px;box-shadow:0 1px 3px rgba(30,27,75,.08)}}
figure.narrow img{{max-height:5in}}
figcaption{{color:var(--muted);font-size:13px;text-align:center;margin-top:6px}}
.svgfig svg{{width:100%;height:auto;display:block}}
.note{{color:var(--muted);font-size:13px}}
.good{{color:{GOOD};font-weight:600}} .bad{{color:{DANGER};font-weight:600}}
mark.todo{{background:#ffd23f;color:#111;padding:1px 4px;border-radius:3px;font-weight:600}}
.todo-box{{border:2px dashed #ffd23f;padding:8px}}
.banner{{background:{WARN_SOFT};border-left:4px solid #ffd23f;padding:10px 14px;border-radius:6px;font-size:14px;margin-bottom:24px}}
@media print{{
 @page{{size:Letter;margin:0.5in}}
 html,body{{background:#fff}} body{{max-width:none;padding:0;font-size:9.5pt;line-height:1.3}}
 h1{{font-size:30pt}} h2{{font-size:15pt;break-after:avoid}} h3,h4{{break-after:avoid}}
 pre{{font-size:7.2pt;padding:5px 7px;margin:.5em 0}} table{{font-size:7.3pt}} th,td{{padding:3px 5px}} p,li{{margin:.3em 0}} h2{{margin:1.1em 0 .3em}} h3{{margin:.8em 0 .25em}}
 figure.shot img{{max-height:2.2in;box-shadow:none}} figure.narrow img{{max-height:2.0in}}
 .banner{{display:none}}
 mark.todo{{background:#fff3b0;border:1px solid #d9b800}}
 .svgfig svg,img{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
}}
"""


def build(usage_path: Path | None = None) -> list[str]:
    src = HERE / "report.md"
    if not src.exists():
        src = HERE / "report_source.txt"
    md = src.read_text(encoding="utf-8")
    ctx = {"stats": usage_stats(load_usage(usage_path))}
    chunks = re.split(r"^@@(\w+)\s*$", md, flags=re.M)
    body = []
    for i, c in enumerate(chunks):
        if i % 2 == 0:
            body.append(render_chunk(c))
        else:
            out = DIRECTIVES[c](ctx)
            parts = re.split(r"(<svg.*?</svg>)", out, flags=re.S)
            body.append("".join(x if x.startswith("<svg") else TODO_RE.sub(lambda m: f'<mark class="todo">{m.group(0)}</mark>', x) for x in parts))
    page = "\n".join(body)
    banner = '<div class="banner"><b>Draft.</b> Yellow marks that start with <b>TODO</b> show where evidence is still to come. Remove every one before submitting. This banner does not print.</div>'
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           f'<title>Enough Lite: report</title><style>{CSS}</style></head><body>{banner}{page}</body></html>')
    OUT.write_text(doc, encoding="utf-8")
    return sorted(set(m.group(0) for m in TODO_RE.finditer(doc)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--usage", help="path to a usage.jsonl (default runs/usage.jsonl)")
    a = ap.parse_args()
    todos = build(Path(a.usage) if a.usage else None)
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB). {len(todos)} distinct TODO markers:")
    for t in todos:
        print(" -", re.sub(r"\s+", " ", t)[:150])
