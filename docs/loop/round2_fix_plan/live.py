"""Live check on this fix's own server (:8054, test mode, no AI): the B journeys' households through /api/intake, then
/api/plan, then each starting point's What If through /api/ask. Prints the panel's figures beside the plan's.
Usage: live.py [name ...]"""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diag import J, answer  # noqa: E402  (the same households and answers as diag.py)

URL = "http://127.0.0.1:8054"
H = {"Content-Type": "application/json", "X-Enough-Test": "1"}


class Q:
    def __init__(self, d):
        self.text = (d or {}).get("text", "")
        self.quick_answers = (d or {}).get("quick_answers", [])


def post(path, body, sse=False):
    req = urllib.request.Request(URL + path, data=json.dumps(body).encode(), headers=H, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        if not sse:
            return json.loads(r.read())
        ev = []
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("data:"):
                ev.append(json.loads(line[5:]))
        return ev


def run(name):
    r = post("/api/intake", {"text": J[name], "profile_so_far": {}})
    for _ in range(14):
        if r["ready"] and not r["missing"] and (r["question"] is None or "more" in (r["profile"].get("asking") or "")):
            break
        r = post("/api/intake", {"text": answer(Q(r["question"])), "profile_so_far": r["profile"]})
    f = {x["key"]: x for x in r["fields"]}
    prof = r["profile"]
    ev = post("/api/plan", {"profile": prof}, sse=True)
    plan = next(e["plan"] for e in ev if e.get("type") == "plan")
    print("=" * 20, name, plan["verdict"], "|", plan["headline"])
    print("  panel Yearly saving:", f["save_rate"]["display"] if "save_rate" in f else None, "| plan saving", plan["saving"]["per_year"])
    print("  panel Costs now:", prof.get("spending_now_per_year"), "| plan now_per_year", plan["costs_by_age"]["now_per_year"])
    print("  panel SS:", f.get("social_security_per_year", {}).get("display"), "| plan SS", plan["social_security_per_year"], "claim", plan["claim_age"])
    print("  consistency:", plan.get("consistency"))
    print("  levers:", [x["whatif_text"] for x in plan["levers"]])
    adv = next(e for e in ev if e.get("type") == "agent_done" and e["agent"] == "adviser")["finding"]
    print("  adviser finding:", adv["headline"], "|", adv["details"])
    for a in plan["assumptions"]:
        print("   -", a)
    for x in plan["starting_points"]:
        w = post("/api/ask", {"question": x["whatif_text"], "profile": prof, "plan": plan})
        got = w.get("plan", {}).get("count_on_per_year")
        paid = (w.get("plan", {}).get("needs") or {}).get("paid_of_100")
        print(f"  point {x['whatif_text']!r}: {x['result']} | What If -> {w['kind']} count-on {got} paid {paid}",
              "MATCH" if (got == x["count_on_per_year"] and paid == x["paid_of_100"]) else "DIFF")


for n in sys.argv[1:] or ["bus", "retired", "parent2", "parent_skip", "teacher", "swe"]:
    try:
        run(n)
    except Exception as e:      # keep going: one household's error is a finding, not a stop
        print("ERROR", n, repr(e)[:300])
