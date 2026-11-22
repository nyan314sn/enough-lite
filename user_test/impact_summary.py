"""Print the real-user results for the report's Impact section.

Reads SESSION_LOG.md and the JSON files in responses/ (saved by FEEDBACK_FORM.html).
Fake data (a heading marked EXAMPLE, or "fake": true in a file) is skipped unless
--include-fake is given.

Run:  python user_test/impact_summary.py [--include-fake] [--responses DIR] [--log FILE]
"""
import argparse
import json
import re
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATINGS = [("clarity", "Clarity"), ("trust", "Trust"), ("usefulness", "Usefulness"),
           ("look", "Look"), ("reuse", "Would use again")]


def num(text):
    m = re.search(r"\d+(?:\.\d+)?", (text or "").replace(",", ""))
    return float(m.group()) if m else None


def parse_log(path, include_fake):
    sessions, cur = [], None
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
        if d.get("fake") and not include_fake:
            continue
        d["_file"] = p.name
        out.append(d)
    return out


def get(s, prefix):
    for k, v in s.items():
        if k.startswith(prefix):
            return v
    return ""


def mean(xs):
    return f"{statistics.mean(xs):.1f}" if xs else "no data"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-fake", action="store_true")
    ap.add_argument("--responses", default=str(HERE / "responses"))
    ap.add_argument("--log", default=str(HERE / "SESSION_LOG.md"))
    a = ap.parse_args()

    sessions = parse_log(Path(a.log), a.include_fake)
    rdir = Path(a.responses)
    fb = load_feedback(rdir, a.include_fake) if rdir.exists() else []
    tag = "  *** FAKE DATA INCLUDED: do not paste into the report ***" if a.include_fake else ""
    print(f"Sessions: {len(sessions)}. Feedback files: {len(fb)}.{tag}\n")

    print("TIME AGAINST THE TESTER'S OWN BASELINE (their guesses)")
    print("| Session | Tester | Minutes to plan | Minutes to one What If | Today they would use | Their time (min) | Their cost ($) |")
    print("|---|---|---|---|---|---|---|")
    for s in sessions:
        print(f"| {s['id']} | {s.get('tester') or '-'} | {get(s, 'minutes to first') or '-'} "
              f"| {get(s, 'minutes to one') or '-'} | {get(s, 'baseline method') or '-'} "
              f"| {get(s, 'baseline minutes') or '-'} | {get(s, 'baseline cost') or '-'} |")
    print()
    for s in sessions:
        t, b = num(get(s, "minutes to first")), num(get(s, "baseline minutes"))
        if t and b:
            print(f"Line: {s['id']} took {t:g} minutes to a first plan. The tester said the usual way takes about "
                  f"{b:g} minutes (their own estimate; {b / t:.0f} times as long).")
        else:
            print(f"Line: {s['id']} is missing a time or a baseline.")
    print()

    print("RATINGS (1 to 5)")
    print("| Question | Mean | Scores |")
    print("|---|---|---|")
    for key, label in RATINGS:
        vals = [d["ratings"][key] for d in fb
                if isinstance(d.get("ratings", {}).get(key), (int, float))]
        print(f"| {label} | {mean(vals)} | {', '.join(str(int(v)) for v in vals) or '-'} |")
    print(f"\n(n = {len(fb)}. With so few people, give the scores, not just the mean.)\n")

    print("COMPARED WITH TODAY")
    for d in fb:
        c = d.get("compare", {})
        print(f"- {d.get('session_id') or d['_file']}: {c.get('choice') or '-'}. {c.get('note') or ''}".rstrip())
    print()

    print("QUOTES")
    for d in fb:
        q = (d.get("quote") or "").strip()
        if q:
            print(f'- "{q}" ({d.get("tester") or "tester"}, {d.get("session_id") or d["_file"]})')
    for s in sessions:
        q = get(s, "said aloud")
        if q:
            print(f"- Aloud: {q} ({s['id']})")
    print()

    print("WHAT CONFUSED THEM, AND WHAT CHANGED")
    for s in sessions:
        for k in ("hesitated at", "confused by", "changed afterwards"):
            v = get(s, k)
            if v:
                print(f"- {s['id']}, {k}: {v}")
    for d in fb:
        o = d.get("open", {})
        for k in ("confusing", "change"):
            if o.get(k):
                print(f"- {d.get('session_id') or d['_file']}, form ({k}): {o[k]}")


if __name__ == "__main__":
    main()
