"""Build slides.html: reveal.js (CDN), one file, 10 slides, images embedded, the app's light palette.

  python report\\build_slides.py [--usage PATH]

Cost numbers come from runs/usage.jsonl (see build_report.usage_stats). Open the file in a browser:
arrow keys to move, F for full screen, S for notes, ? for help.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_report as br  # noqa: E402

OUT = br.LITE / "slides.html"
REVEAL = "https://cdn.jsdelivr.net/npm/reveal.js@5.1.0"


def shot(name: str, width: int = 1000) -> str:
    p = br.resolve_img(name)
    if name in ("img/intake.png", "img/team.png", "img/plan.png"):   # trim the empty side margins of the 1440 px captures
        import io
        from PIL import Image
        im = Image.open(p).convert("RGB").crop((100, 0, 1340, 900))
        buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
        tmp = p.with_name("_slide_" + p.name); tmp.write_bytes(buf.getvalue())
        try:
            return br.img_data_uri(tmp, max_w=width)
        finally:
            tmp.unlink()
    return br.img_data_uri(p, max_w=width)


def build(usage_path: Path | None = None) -> list[str]:
    st = br.usage_stats(br.load_usage(usage_path))
    T = br.todo
    if st:
        run_cost = br.money(st["mean"]["cost"])
        sc = br.session_cost(st)
        per_month = br.money(sc * br.PLANS_PER_USER_MONTH)
        c100 = br.money(sc * br.PLANS_PER_USER_MONTH * 100)
        c10k = br.money(sc * br.PLANS_PER_USER_MONTH * 10_000)
        tokens = f"{st['mean']['input'] + st['mean']['cached'] + st['mean']['cache_write'] + st['mean']['output']:,.0f}"
        cache_share = f"{100 * st['cached_share']:.0f}%"
        saved = f"{100 * (1 - st['mean']['cost'] / st['uncached_cost']):.0f}%"
        nplans = f"{st['n']:,}"
    else:
        run_cost = per_month = c100 = c10k = tokens = cache_share = saved = nplans = T("from runs")
    S = []
    S.append(f"""<section class="title"><h1>Enough<span>.</span></h1>
<p class="big">Can you retire when you want, and what should you do first?</p>
<p>Seven AI advisers answer in minutes, in plain words.</p>
<p class="small">MGT 409 final project &middot; Nyan Tin<br>Repo: github.com/nyan314sn/enough-lite</p></section>""")
    S.append("""<section><h2>The problem</h2>
<div class="cols"><div><p class="big">A couple, 45 and 43. Three kids, two dogs. <b>Can we stop work at 62?</b></p>
<p>An adviser costs <b>$2,926</b> for a plan. A planner asks for 100 inputs. A chatbot may invent numbers.</p></div>
<div class="stats"><div><b>35%</b><span>of non-retirees say saving is on track (Fed, SHED)</span></div>
<div><b>$955</b><span>median retirement savings, workers 21 to 64 (NIRS)</span></div>
<div><b>32%</b><span>of guidance-seekers used an adviser (Gallup)</span></div></div></div></section>""")
    S.append("""<section><h2>What is new</h2>
<table class="cmp"><tr><th></th><th>Boldin</th><th>Origin</th><th>Human adviser</th><th class="us">Enough</th></tr>
<tr><td>AI team of agents</td><td>One assistant</td><td>Yes</td><td>No</td><td class="us">Yes, seven, you watch them</td></tr>
<tr><td>Needs / wants / wishes</td><td>No</td><td>Not found</td><td>Sometimes</td><td class="us">Yes</td></tr>
<tr><td>Kids and pets in plain words</td><td>No</td><td>Not found</td><td>Yes</td><td class="us">Yes</td></tr>
<tr><td>Numbers only from tools</td><td>Rules engine</td><td>Unknown</td><td>Yes</td><td class="us">Checked</td></tr>
<tr><td>Plans of similar households</td><td>No</td><td>Not found</td><td>Experience</td><td class="us">467 tested cases</td></tr>
<tr><td>Checked numbers for any AI assistant (MCP)</td><td>Not found</td><td>Not found</td><td>No</td><td class="us">Yes, 6 tools</td></tr>
<tr><td>Cost</td><td>$168/yr</td><td>$99/yr</td><td>$2,926+</td><td class="us">cents a plan</td></tr></table>
<p class="small">Honest: Origin already uses multi-agent AI and is regulated. We have no linked accounts and no human. "Not found" means I looked and did not find it.</p></section>""")
    S.append(f"""<section><h2>How the agents work</h2><div class="svgwrap agents-sm">{br.agents_svg(legend=False)}</div>
<div class="three">
<div><b>AI does the words</b>Reads what you type (after the rules), writes the plan and Team talk, answers rule questions from 37 cited passages.</div>
<div><b>Code does the money: it simulates</b>2,000 market paths, plus a bad first decade and high inflation; life tables, plus living to 100 and an early death. About 20 strategies tested: 5 from <b>467 plans a full optimizer solved ahead of time</b>, plus a rule of thumb and its variants. Not training.</div>
<div><b>The harness</b>Own tools only; at most 4 requests per agent; time limits; caps of $0.05 a plan and $0.50 a session; a number check, one retry, then a template. Every call logged.</div>
</div>
<p class="small"><b>MCP server (optional):</b> any AI assistant calls Enough's six tools and gets checked numbers and sources instead of guesses. No AI inside, same engine and refusals, 33 tests. Example: a 58-year-old in Ohio can count on $45,900, $9,100 short of the goal; Medicare cited; Medicaid hiding refused.</p></section>""")
    S.append(f"""<section><h2>One run</h2><div class="shots">
<figure><img src="{shot('img/intake.png', 760)}" alt="Intake"><figcaption>1. Type a few lines; every field is marked</figcaption></figure>
<figure><img src="{shot('img/team.png', 760)}" alt="Team working"><figcaption>2. Watch the team and its hand-offs</figcaption></figure>
<figure><img src="{shot('img/plan.png', 760)}" alt="Plan"><figcaption>3. Plan left, team right</figcaption></figure></div>
<p class="small">A couple, 45 and 43, $310,000 pay, $920,000 saved, three children, two dogs: they can count on $114,800 a year ($44,500 for basics), and the goal lasts in 90 of 100 scenarios. 4. What If tabs on the baseline: retire at 65 gives $140,900; savings $500 more a month, $118,400; markets fall 30%, $108,700 and $6,100 short. Compare puts them side by side.</p></section>""")
    S.append(f"""<section><h2>Cost to run</h2><div class="stats row">
<div><b>{run_cost}</b><span>one plan ({tokens} tokens)</span></div><div><b>{per_month}</b><span>per user per month</span></div>
<div><b>{c100}</b><span>100 users a month</span></div><div><b>{c10k}</b><span>10,000 users a month</span></div></div>
<ul><li>{nplans} real plans metered. Caching: {cache_share} of input is cache reads; plan cost {saved} lower than uncached.</li>
<li>Number-check tuning: first-try passes 40% to 100%; plan cost $0.0027 to $0.0016. The app shows its own token costs under Team talk.</li>
<li>Model choice, 80 plans: Haiku vs gpt-6-luna give identical numbers; template fallbacks 20% vs 51%; median 11 s vs 22 s; blind judge a tie; safety 74 of 74 both. Per user per month, plans and What Ifs only: $0.014 vs $0.010.</li>
<li>Hard caps: $0.05 a run, $0.50 a session, $5 in total.</li></ul>
<p class="small">Assumes {br.PLANS_PER_USER_MONTH} sessions a month: one plan, {br.WHATIFS_PER_PLAN} What Ifs and {br.INTAKE_CALLS_PER_PLAN} intake model calls each. Measured from the app's own log.</p></section>""")
    S.append(f"""<section><h2>Safety: before and after</h2><div class="cols"><div>
<table class="cmp"><tr><th>Test</th><th>Before</th><th class="us">After</th></tr>
<tr><td>50 attacks, then 74</td><td>45 of 50</td><td class="us">74 of 74</td></tr>
<tr><td>Forged change</td><td>10 million objects, 7 GB</td><td class="us">refused (16 payloads)</td></tr>
<tr><td>Slow regex (4,000 digits)</td><td>12.6 s</td><td class="us">36 ms</td></tr>
<tr><td>Body size, headers</td><td>none</td><td class="us">413 over 1 MB; CSP</td></tr>
<tr><td>XSS, path traversal</td><td colspan="2" class="us">pass</td></tr></table>
<p class="small">Hidden text is stripped, asset hiding is refused, tools cannot act, dollar caps stop a run: the cap stopped a plan at $0.001 and the numbers still showed.</p></div>
<div class="shots one"><figure><img src="{shot('img/s1.png', 640)}" alt="Hidden instruction ignored"><figcaption>A hidden "$9,900,000" in a statement is ignored</figcaption></figure></div></div></section>""")
    S.append(f"""<section><h2>How we tested and improved it</h2>
<p>Independent AI auditors try to break the app. We fix. We measure again.</p>
<div class="cols2"><table class="cmp"><tr><th>Three rounds</th><th>R1</th><th>R2</th><th class="us">R3</th></tr>
<tr><td>A, logic: P0 / P1</td><td>1 / 9</td><td>0 / 3</td><td class="us">0 / 0</td></tr>
<tr><td>B, UI: P0 / P1</td><td>4 / 11</td><td>1 / 9</td><td class="us">1 / 6</td></tr>
<tr><td>Simulated users: accuracy</td><td>96%</td><td>93.8%</td><td class="us">95.1%</td></tr>
<tr><td>Reached a plan</td><td>40/40</td><td>45/48</td><td class="us">48/48</td></tr>
<tr><td>Attacks, round 2 kit (107)</td><td>-</td><td>91</td><td class="us">101</td></tr>
<tr><td>Eval: gap to optimizer</td><td>-1.7%</td><td>-6.8%</td><td class="us">-0.8%</td></tr></table>
<table class="cmp"><tr><th>Added checks</th><th>Before</th><th class="us">After</th></tr>
<tr><td>What If read right, held-out 89</td><td>44%</td><td class="us">58% rules, 91% with AI</td></tr>
<tr><td>Wrong What If readings, of 413</td><td>27</td><td class="us">2</td></tr>
<tr><td>Reasonableness: 6,117 variations, negative money</td><td>671 plans</td><td class="us">0</td></tr>
<tr><td>Crashes</td><td>5</td><td class="us">0</td></tr>
<tr><td>Pay off debt: effect on count-on</td><td>-$350</td><td class="us">+$95</td></tr>
<tr><td>Model compare: template fallbacks</td><td>51% gpt-6-luna</td><td class="us">20% Haiku</td></tr></table></div>
<p class="small"><b>What the audits missed:</b> the user found by hand that "Not sure, estimate it" left the mortgage blank. So: 25 product rules, a test for each, and a live rules audit as the last gate (first run 14 pass, 10 partial, 1 fail; re-check 2 / 9 / 0). Not met: two audits in a row with no P0. The "after" columns are simulated testers and tools-only runs, not people.</p></section>""")
    S.append(f"""<section><h2>Impact</h2><div class="stats row">
<div><b>9 s</b><span>median compute per plan</span></div><div><b>{run_cost}</b><span>per plan, against $2,926 for an adviser plan</span></div>
<div><b>{T('minutes')}</b><span>real user: start to plan</span></div><div><b>{T('quote')}</b><span>real user quote</span></div></div>
<p>Not a like-for-like swap: an adviser covers tax, estate and judgment. This is access, a first answer for people who would not pay for any plan.</p>
<p class="small">Limits: not financial advice, no linked accounts, simple models, one or two testers at most.</p></section>""")
    S.append("""<section><h2>What is next</h2><ul>
<li>Five real users, then fix what confuses them.</li><li>Fix the last P0s and pass the live rules audit.</li>
<li>Compare Haiku with a larger Claude model.</li><li>Upload a statement (the injection defense is ready).</li>
<li>Roth conversion, long-term care, annuity choice; fix the ten known engine gaps (R1 to R10).</li><li>A planner reviews 30 plans. Host the app and the MCP server, with a monthly budget.</li></ul></section>""")
    body = "\n".join(S)
    body = br.TODO_RE.sub(lambda m: f'<mark class="todo">{m.group(0)}</mark>', body)
    css = f"""
:root{{--r-background-color:{br.BG};--r-main-font:{br.FONT};--r-heading-font:{br.FONT};--r-main-color:{br.TEXT};--r-heading-color:{br.BRAND};--r-link-color:{br.ACCENT};--r-main-font-size:30px}}
.reveal{{font-weight:400}} .reveal h1{{font-size:3.4em;letter-spacing:-.02em}} .reveal h1 span{{color:{br.ACCENT}}}
.reveal h2{{font-size:1.5em;text-transform:none;margin-bottom:.5em;border-bottom:3px solid {br.ACCENT};display:inline-block;padding-bottom:.1em}}
.reveal section{{text-align:left}} .reveal .title{{text-align:center}}
.reveal p.big{{font-size:1.15em;line-height:1.3}} .reveal .small{{font-size:.5em;color:{br.MUTED}}}
.reveal b{{color:{br.TEXT}}} .reveal ul{{display:block;font-size:.85em}} .reveal li{{margin:.35em 0}}
.cols{{display:grid;grid-template-columns:1.2fr 1fr;gap:1.2em;align-items:center}}
.cols2{{display:grid;grid-template-columns:1fr 1fr;gap:.8em;align-items:start}}
.stats{{display:flex;flex-direction:column;gap:.5em}} .stats.row{{flex-direction:row;gap:.8em;margin:.4em 0}}
.stats>div{{background:{br.PANEL};border:1px solid {br.LINE};border-left:4px solid {br.ACCENT};border-radius:10px;padding:.35em .6em;flex:1;box-shadow:0 1px 3px rgba(30,27,75,.06)}}
.stats b{{display:block;font-size:1.5em;color:{br.ACCENT}}} .stats span{{font-size:.55em;color:{br.MUTED};line-height:1.2;display:block}}
table.cmp{{width:100%;border-collapse:collapse;font-size:.6em;background:{br.PANEL}}} .cmp th,.cmp td{{border:1px solid {br.LINE};padding:.3em .5em}} .cmp th{{background:{br.SOFT};color:{br.ACCENT2}}} .cmp .us{{background:{br.SOFT};color:{br.TEXT};font-weight:700}}
.svgwrap svg{{width:100%;height:auto;max-height:520px}} .agents-sm svg{{max-height:355px}}
.three{{display:grid;grid-template-columns:repeat(3,1fr);gap:.8em;margin-top:.4em;font-size:.48em;text-align:left;line-height:1.35}} .three div{{border-top:4px solid {br.ACCENT};padding-top:.4em}} .three b:first-child{{display:block;font-size:1.15em;margin-bottom:.2em}}
.shots{{display:flex;gap:.6em;align-items:flex-start;justify-content:center}} .shots figure{{margin:0;flex:1;text-align:center}}
.shots img{{max-height:430px;max-width:100%;width:auto;border:1px solid {br.LINE};border-radius:8px;margin:0;box-shadow:0 1px 4px rgba(30,27,75,.10)}} .shots figcaption{{font-size:.5em;color:{br.MUTED}}}
.shots.one img{{max-height:400px}}
mark.todo{{background:#ffd23f;color:#111;padding:0 .2em;border-radius:3px;font-size:.6em;font-weight:600}}
"""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enough Lite: slides</title>
<link rel="stylesheet" href="{REVEAL}/dist/reveal.css"><link rel="stylesheet" href="{REVEAL}/dist/theme/white.css"><style>{css}</style></head>
<body><div class="reveal"><div class="slides">
{body}
</div></div>
<script src="{REVEAL}/dist/reveal.js"></script>
<script>Reveal.initialize({{hash:true,width:1280,height:720,margin:0.04,transition:'fade',controls:true,progress:true,slideNumber:'c/t'}});</script>
</body></html>"""
    OUT.write_text(doc, encoding="utf-8")
    return sorted(set(m.group(0) for m in br.TODO_RE.finditer(doc)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--usage")
    a = ap.parse_args()
    todos = build(Path(a.usage) if a.usage else None)
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB). {len(todos)} distinct TODO markers:")
    for t in todos:
        print(" -", re.sub(r"\s+", " ", t)[:120])
