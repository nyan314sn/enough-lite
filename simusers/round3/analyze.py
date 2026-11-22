import glob
import json
import os
import statistics

D = os.path.dirname(os.path.abspath(__file__))
runs = {os.path.basename(f)[:-5]: json.load(open(f, encoding="utf-8")) for f in glob.glob(D + "/runs/*.json")}
judged = {os.path.basename(f)[:-5]: json.load(open(f, encoding="utf-8")) for f in glob.glob(D + "/judged/*.json")}
for name, flt in (("original40", lambda k: k.startswith("p")), ("hard8", lambda k: k.startswith("h")), ("all", lambda k: True)):
    ks = [k for k in runs if flt(k)]
    reached = [k for k in ks if runs[k].get("plan_ok")]
    acc = [judged[k]["accuracy"]["share"] for k in ks if k in judged and judged[k]["accuracy"]["share"] is not None]
    iss = [dict(i, pid=k) for k in ks if k in judged for i in judged[k]["issues"]]
    de = [i for i in iss if i["type"] == "dead_end"]
    pt = [len(runs[k]["plan_turns"]) for k in reached]
    print(name, "n", len(ks), "reached", len(reached), "acc %.1f" % (100 * statistics.mean(acc)),
          "issues", len(iss), "P0", sum(i["severity"] == "P0" for i in iss), "P1", sum(i["severity"] == "P1" for i in iss),
          "dead_end", len(de), "P0dead", sum(i["severity"] == "P0" for i in de), "ignored_corr", sum(i["type"] == "ignored_correction" for i in iss),
          "planturns min/avg/max", min(pt), round(statistics.mean(pt), 1), max(pt))
print("\nNOT REACHED")
for k in sorted(runs):
    r = runs[k]
    if not r.get("plan_ok"):
        print(k, r["name"], r["status"], r.get("plan_error"), len(r["intake_turns"]))
        for t in r["intake_turns"][-6:]:
            print("  U:", t["user"][:140], "\n  A:", t["reply"][:220].replace("\n", " "), "| Q:", (t.get("question") or {}).get("text"), "| missing", t.get("missing"))
print("\nPLAN-CHAT ISSUES AND ALL P0/P1")
for k in sorted(judged):
    for i in judged[k]["issues"]:
        if i["severity"] in ("P0", "P1") and (i["ref"].startswith("a") or i["severity"] == "P0"):
            print(k, i["ref"], i["severity"], i["type"], "|", i["quote"], "|", i["note"])
print("\nAPPLIED/CHANGE turns")
for k in sorted(runs):
    for t in runs[k]["plan_turns"]:
        if t.get("kind") == "change" or t.get("status") == "applied" or t.get("had_pending"):
            print(k, t["n"], t["kind"], t.get("status"), "pending" if t.get("had_pending") else "", "U:", t["user"][:90], "| A:", t["text"][:110].replace("\n", " "))
print("\nUnanswered what-ifs (intent whatif but kind != whatif)")
c = 0
for k in sorted(runs):
    for t in runs[k]["plan_turns"]:
        if t.get("intent") == "whatif":
            c += 1
            if t.get("kind") != "whatif":
                print(k, t["n"], t.get("kind"), "U:", t["user"][:90], "| A:", t["text"][:110].replace("\n", " "))
print("whatif intents", c)
