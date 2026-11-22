import glob, json, os, collections
D = os.path.dirname(os.path.abspath(__file__))
c = collections.Counter(); wi = collections.Counter(); src = []; bad = []
for f in sorted(glob.glob(D + "/runs/*.json")):
    r = json.load(open(f, encoding="utf-8"))
    for t in r.get("plan_turns", []):
        c[(t.get("kind"), t.get("status"))] += 1
        if t.get("intent") == "whatif":
            wi[t.get("kind")] += 1
        if "From the source" in (t.get("text") or ""):
            src.append((r["persona_id"], t["n"], t["intent"], t["user"][:90], t["text"][:90].replace("\n", " ")))
        if t.get("status") == "applied":
            bad.append((r["persona_id"], t["n"], t.get("had_pending"), t["user"][:80], t["text"][:80]))
print(c); print("whatif intents by kind", wi, sum(wi.values()))
print("source quotes", len(src))
for s in src: print(s)
print("applied", len(bad))
for b in bad: print(b)
print("total plan turns", sum(c.values()))
