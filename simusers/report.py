"""Write SIM_REPORT.md from runs/ and judged/. Usage: python report.py"""
import json
import statistics
from collections import Counter, defaultdict

import httpx

from common import APP, HERE, JUDGED, RUNS, load_personas, usage_cost

SEV = {"P0": 0, "P1": 1, "P2": 2}
TYPE_FIX = {
    "dead_end": "Never end a reply without a specific next question or option; add a fallback question with chips.",
    "ignored_correction": "Apply a stated correction on the spot (and echo the new value); never ask the old question again.",
    "unstated_assumption": "Say every assumed or estimated figure in the reply, in plain words, when it is first used.",
    "repeated_question": "Track answered questions; do not re-ask what the person gave, even in different words.",
    "misunderstanding": "Check parsed figures against the message (totals, who earns what, what is spending vs pay) before echoing them.",
    "confusing": "Replace jargon and bare statistics (such as '0 of 100 scenarios') with one plain sentence.",
    "contradiction": "Do not store or show a figure that differs from what the person said.",
}


def main():
    ps = {p["id"]: p for p in load_personas()}
    runs = {}
    for f in RUNS.glob("*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        runs[r["persona_id"]] = r
    judged = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in JUDGED.glob("*.json")}
    n = len(runs)
    L = ["# Enough Lite: simulated-user test report", "",
         f"Claude Haiku played {n} people (personas.json); a second Haiku judged each exchange. Runs: `simusers/runs/`, verdicts: `simusers/judged/`.", ""]
    reached = [r for r in runs.values() if r.get("plan_ok")]
    stuck = [r for r in runs.values() if not r.get("plan_ok")]
    turns = [r["turns_to_plan"] for r in reached if r.get("turns_to_plan")]
    L += ["## Completion", "",
          f"- Reached a plan: **{len(reached)} of {n}** ({100 * len(reached) // max(n, 1)}%).",
          f"- Average intake turns to a plan: **{statistics.mean(turns):.1f}** (median {statistics.median(turns)}, max {max(turns)})." if turns else "- No plans reached.",
          f"- Did not reach a plan: {', '.join(f'{r['persona_id']} ({r['status']}, {len(r['intake_turns'])} turns)' for r in stuck) or 'none'}.", ""]
    acc = [j["accuracy"]["share"] for j in judged.values() if j["accuracy"]["share"] is not None]
    L += ["## Profile accuracy (final profile against the hidden truth)", ""]
    if acc:
        L.append(f"- Share of checked fields correct: **{100 * statistics.mean(acc):.0f}%** (over {len(acc)} personas).")
    byf = defaultdict(lambda: [0, 0])
    causes = Counter()
    for j in judged.values():
        for f in j["accuracy"]["fields"]:
            byf[f["field"]][1] += 1
            byf[f["field"]][0] += f["ok"]
        for w in j["accuracy"].get("why") or []:
            if isinstance(w, dict):
                causes[w.get("cause")] += 1
    L += ["", "| Field | Correct | Share |", "|---|---|---|"]
    for k, (a, b) in sorted(byf.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        L.append(f"| {k} | {a}/{b} | {100 * a // b}% |")
    L += ["", "Why fields were wrong (judge's cause): " + (", ".join(f"{c} {k}" for k, c in causes.most_common()) or "n/a"), ""]

    issues = []
    for pid, j in judged.items():
        for i in j["issues"]:
            issues.append(dict(i, pid=pid))
    cnt = Counter(i["type"] for i in issues)
    L += ["## Issues by type", "", "| Type | Total | P0 | P1 | P2 | Personas hit |", "|---|---|---|---|---|---|"]
    for t, c in cnt.most_common():
        s = Counter(i["severity"] for i in issues if i["type"] == t)
        L.append(f"| {t} | {c} | {s['P0']} | {s['P1']} | {s['P2']} | {len({i['pid'] for i in issues if i['type'] == t})} |")
    L.append("")
    for t, _ in cnt.most_common():
        L += [f"### {t}", ""]
        ex = sorted([i for i in issues if i["type"] == t], key=lambda i: SEV.get(i["severity"], 3))[:5]
        for i in ex:
            L.append(f"- {i['severity']} {i['pid']} {i['ref']}: \"{(i.get('quote') or '').strip()}\" ({i.get('note')})")
        L.append("")
    L += ["## Five worst examples", ""]
    for i in sorted(issues, key=lambda i: (SEV.get(i["severity"], 3), i["type"]))[:5]:
        L.append(f"- {i['severity']} {i['type']} ({i['pid']} {i['ref']}): \"{(i.get('quote') or '').strip()}\" {i.get('note')}")

    # plan-page behaviour
    kinds = Counter(t.get("kind") for r in runs.values() for t in r["plan_turns"])
    L += ["", "## Plan page", "", "Reply kinds: " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()) + ".", ""]

    # fixes ranked by severity-weighted count, with personas hit
    score = Counter()
    for i in issues:
        score[i["type"]] += {"P0": 5, "P1": 2, "P2": 1}.get(i["severity"], 1)
    for f, (a, b) in byf.items():
        score["field:" + f] += (b - a) * 2
    L += ["## Top 10 fixes, ranked", ""]
    fixes = []
    for k, sc in score.most_common():
        if k.startswith("field:"):
            fixes.append((sc, f"Get '{k[6:]}' right: {byf[k[6:]][1] - byf[k[6:]][0]} of {byf[k[6:]][1]} personas ended with a wrong or missing value (ask for it, or parse the message correctly)."))
        else:
            fixes.append((sc, f"{TYPE_FIX[k]} ({cnt[k]} issues)"))
    for n_, (sc, txt) in enumerate(fixes[:10], 1):
        L.append(f"{n_}. {txt}")

    # cost
    app_cost = sum(r.get("app_cost_usd") or 0 for r in runs.values())
    uc = usage_cost()
    tot = app_cost + sum(v["usd"] for v in uc.values())
    L += ["", "## Tokens and cost", "", f"- App (sum of each persona's /api/costs): ${app_cost:.4f}, {sum(r.get('app_tokens') or 0 for r in runs.values()):,} tokens."]
    for k, v in uc.items():
        L.append(f"- {k.capitalize()}: {v['calls']} calls, {v['input']:,} in / {v['output']:,} out, ${v['usd']:.4f} (at the app's Haiku prices of $0.10 in and $0.50 out per million).")
    L.append(f"- **Total: ${tot:.4f}** (budget $1.50, stop at $2).")
    (HERE / "SIM_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
