"""Print the plan text of saved plans. Usage: show.py name [name ...]"""
import json, sys
from pathlib import Path
HERE = Path(__file__).parent
for n in sys.argv[1:]:
    d = json.load(open(HERE / "plans" / f"{n}.json", encoding="utf-8"))
    plan = [e for e in d["events"] if e.get("type") == "plan"][0]["plan"]
    print("==", n, plan["verdict"], plan["text_source"])
    print("HEAD:", plan["headline"])
    print("NEEDS:", plan["needs"]["line"])
    print("WANTS:", plan["wants"]["line"])
    print("WISH:", plan["wishes"]["line"])
    for a in plan["actions"]:
        print("  -", a["title"], "|", a["why"])
    print("POINTS:", plan.get("starting_points"))
    print("CLAIM:", plan["claim_age"], plan["partner_claim_age"], plan["already_claiming"], plan["horizon_text"])
    for a in plan.get("assumptions") or []:
        print("  *", a)
    for e in d["events"]:
        if e.get("type") == "agent_done" and e["agent"] in ("longevity", "markets"):
            print("  [", e["agent"], "]", e["finding"]["headline"], " / ".join(e["finding"]["details"]))
