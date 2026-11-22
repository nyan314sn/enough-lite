import glob, json, os, re
D = os.path.dirname(os.path.abspath(__file__))
pat = re.compile(r"not sure|estimate|don'?t know|dont know|skip|no idea|guess|unsure|not certain|you pick|you choose|whatever", re.I)
n = 0
for f in sorted(glob.glob(D + "/runs/*.json")):
    r = json.load(open(f, encoding="utf-8"))
    ts = r.get("intake_turns", [])
    for i, t in enumerate(ts):
        u = (t.get("user") or "") + " " + str(t.get("clicked") or "")
        if pat.search(u) and i > 0:
            n += 1
            pq = (ts[i-1].get("question") or {}).get("text", "")
            print(f"== {r['persona_id']} t{t['n']} prevQ: {pq[:90]}\n U: {u[:110]}\n new_assumed: {t.get('new_assumed')}\n A: {(t.get('reply') or '')[:260]}\n")
print("skip turns", n)
