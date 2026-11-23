import json,sys
r=json.load(open(f"runs/{sys.argv[1]}.json",encoding="utf-8"))
a,b=int(sys.argv[2]),int(sys.argv[3])
for t in r["intake_turns"][a-1:b]:
    q=(t.get("question") or {}).get("text")
    print(f"[i{t['n']}] YOU: {t['user']}\n   APP: {t['reply'][:400]}\n   Q: {q}")
