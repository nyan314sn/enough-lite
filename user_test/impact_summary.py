"""Print the real-user results as a compact Markdown block for the report's Impact section.

Reads SESSION_LOG.md (note-taker fields) and the JSON files in responses/ (saved by
FEEDBACK_FORM.html, form_version 2; version-1 files still work). Fake data (a heading
marked EXAMPLE, or "fake": true in a file) is skipped unless --include-fake is given.

Run:  python user_test/impact_summary.py [--include-fake] [--responses DIR] [--log FILE]
"""
import argparse
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
COST_PER_PLAN = 0.002  # dollars, from the app's own cost figure
GRADES = ("right", "partly", "wrong")
CHECKS = [("retire-age", "Can you retire at the age you wanted?", "retire_age"),
          ("yearly gap", "How much short or ahead each year?", "gap_per_year"),
          ("first-step", "First thing you would do?", "first_step")]


def num(text):
    m = re.search(r"\d+(?:\.\d+)?", str(text if text is not None else "").replace(",", ""))
    return float(m.group()) if m else None


def parse_log(path, include_fake):
    sessions, cur = [], None
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        h = re.match(r"###\s+Session\s+(\S+)", line)
        if h:
            cur = {"id": h.group(1), "fake": "EXAMPLE" in line.upper()}
            sessions.append(cur)
            continue
        f = re.match(r"-\s+([^:]+):\s*(.*)", line)
        if cur and f:
            cur[f.group(1).strip().lower()] = f.group(2).strip()
    sessions = [s for s in sessions if not s["id"].endswith("_")]  # the blank template
    return [s for s in sessions if include_fake or not s["fake"]]


def load_feedback(folder, include_fake):
    out = []
    for p in sorted(folder.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            print(f"(skipped {p.name}: not valid JSON)")
            continue
        if not isinstance(d, dict) or (d.get("fake") and not include_fake):
            continue
        d["_file"] = p.name
        out.append(d)
    return out


def get(s, prefix):
    for k, v in s.items():
        if k.startswith(prefix):
            return v
    return ""


def sub(d, *keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def rating(d, *names):
    """Read a 1-5 rating under the new name or the version-1 name."""
    for n in names:
        v = sub(d, "ratings", n)
        if isinstance(v, (int, float)):
            return v
    return None


def mean(xs):
    return f"{statistics.mean(xs):.1f}" if xs else "no data"


def med(xs):
    return f"{statistics.median(xs):g}" if xs else "no data"


def scores(xs):
    return ", ".join(f"{x:g}" for x in xs) if xs else "-"


def rating_line(label, xs):
    return f"- {label}: mean {mean(xs)} of 5 (scores: {scores(xs)})"


def count(xs):
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return ", ".join(f"{k} {v}" for k, v in out.items()) or "no data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-fake", action="store_true")
    ap.add_argument("--responses", default=str(HERE / "responses"))
    ap.add_argument("--log", default=str(HERE / "SESSION_LOG.md"))
    a = ap.parse_args()

    sessions = parse_log(Path(a.log), a.include_fake)
    rdir = Path(a.responses)
    fb = load_feedback(rdir, a.include_fake) if rdir.exists() else []
    log = {s["id"]: s for s in sessions}
    fbs = {str(d.get("session_id") or d["_file"]): d for d in fb}
    ids = list(dict.fromkeys(list(log) + list(fbs)))
    n = len(ids)
    if a.include_fake:
        print("*** FAKE DATA INCLUDED: do not paste into the report ***\n")
    print(f"### Real-user test: {n} tester{'s' if n != 1 else ''} "
          f"({len(sessions)} log blocks, {len(fb)} form files)\n")
    if not n:
        print("No data yet.")
        return

    # Time and cost against the tester's own method today
    print("**Time and cost against today's method**\n")
    print("| Tester | Minutes to first plan | Minutes to one What If | Method today | Their time today (min) | Their cost today ($) |")
    print("|---|---|---|---|---|---|")
    tp, tb, cb, pairs = [], [], [], []
    for i in ids:
        s, d = log.get(i, {}), fbs.get(i, {})
        t = num(get(s, "minutes to first"))
        w = num(get(s, "minutes to one"))
        method = get(s, "baseline method") or sub(d, "baseline", "method") or "-"
        b = num(get(s, "baseline minutes"))
        if b is None:
            b = sub(d, "baseline", "time_minutes")
        c = num(get(s, "baseline cost"))
        if c is None:
            c = sub(d, "baseline", "cost_usd")
        if t is not None:
            tp.append(t)
        if b is not None:
            tb.append(b)
        if c is not None:
            cb.append(c)
        if t is not None and b is not None:
            pairs.append(b - t)
        f = lambda x: "-" if x is None else f"{x:g}"
        print(f"| {i} | {f(t)} | {f(w)} | {method} | {f(b)} | {f(c)} |")
    print(f"| **Median** | **{med(tp)}** | | | **{med(tb)}** | **{med(cb)}** |\n")
    if pairs:
        print(f"- Time saved: median {statistics.median(pairs):g} minutes per tester "
              f"(their own estimate for today's method, minus the measured time to a first plan).")
    else:
        print("- Time saved: not yet, because no tester has both a measured time and an estimate.")
    print(f"- Cost: testers put today's method at a median of ${med(cb)}; a plan here costs about ${COST_PER_PLAN:.3f}.\n")

    # Comprehension
    print("**Did they understand the answer** (log check against the screen where present; else self-report)\n")
    print("| Question | right | partly | wrong | not checked |")
    print("|---|---|---|---|---|")
    selfreport = []
    for key, label, fkey in CHECKS:
        g = {k: 0 for k in GRADES}
        unchecked = 0
        for i in ids:
            v = get(log.get(i, {}), key).lower()
            hit = next((k for k in GRADES if v.startswith(k)), None)
            if hit:
                g[hit] += 1
            else:
                unchecked += 1
                txt = sub(fbs.get(i, {}), "comprehension", fkey)
                if txt:
                    selfreport.append(f"{i}, {label} {txt}")
        print(f"| {label} | {g['right']} | {g['partly']} | {g['wrong']} | {unchecked} |")
    if selfreport:
        print("\nSelf-reported answers not yet checked against the screen:")
        for line in selfreport:
            print(f"- {line}")
    print()

    # Ratings and usability
    print("**Ease, look, and the new ideas**\n")
    rows = [("Ease", ("ease", "clarity")), ("Look", ("look",)),
            ("Needs, wants, wishes made sense", ("needs_wants_wishes",)),
            ("Readiness score helpful", ("readiness_helpful",)),
            ("Trust in the answer", ("trust",)), ("Would use it again", ("reuse",))]
    for label, names in rows:
        print(rating_line(label, [v for v in (rating(d, *names) for d in fb) if v is not None]))
    helped = [sub(d, "usability", "needed_help") for d in fb if sub(d, "usability", "needed_help")]
    early = [sub(d, "usability", "noticed_early_build") for d in fb if sub(d, "usability", "noticed_early_build")]
    print(f"- Needed help (form): {count(helped)}")
    logged = [get(log[i], "needed help").split(" ")[0].strip("(:,.").lower() for i in log if get(log[i], "needed help")]
    if logged:
        print(f"- Needed help (note-taker saw): {count(logged)}")
    print(f"- Noticed they could build the plan early: {count(early)}\n")

    # Reach
    print("**Reach**\n")
    rec = [d["recommend_0_10"] for d in fb if isinstance(d.get("recommend_0_10"), (int, float))]
    if rec:
        pro = sum(1 for x in rec if x >= 9)
        det = sum(1 for x in rec if x <= 6)
        print(f"- Recommend (0 to 10): {scores(rec)}. Net promoter score {round(100 * (pro - det) / len(rec))} "
              f"({pro} promoters, {det} detractors; very rough at this n).")
    else:
        print("- Recommend (0 to 10): no data")
    pay = [d for d in fb if sub(d, "would_pay", "answer")]
    yes = [d for d in pay if sub(d, "would_pay", "answer") == "yes"]
    amts = [sub(d, "would_pay", "per_year_usd") for d in yes if isinstance(sub(d, "would_pay", "per_year_usd"), (int, float))]
    print(f"- Would pay: {len(yes)} of {len(pay)} who answered" + (f"; about ${med(amts)} a year (median)" if amts else "") + ".")
    cmp_ = [(i, sub(fbs[i], "compare", "choice"), sub(fbs[i], "compare", "note")) for i in ids
            if i in fbs and sub(fbs[i], "compare", "choice")]
    print(f"- Compared with today: {count([c for _, c, _ in cmp_])}")
    for i, c, note in cmp_:
        if note:
            print(f"  - {i}: {note}")
    print()

    # Quotes (only with consent)
    print("**Quotes (consent given)**\n")
    q = 0
    for i in ids:
        d = fbs.get(i, {})
        text = (d.get("quote") or "").strip()
        if text and sub(d, "consent", "quote") is True and q < 3:
            print(f'- "{text}" ({d.get("tester") or "tester"}, {i})')
            q += 1
    if not q:
        print("- None with consent yet.")
    print()
    print("*Caveat: " + f"{n} tester{'s' if n != 1 else ''}, not a sample; times are their own estimates.*")


if __name__ == "__main__":
    main()
