import json
from mc_common import *
for a in ("anthropic","openai"):
    f=HERE/"raw"/f"qa_{a}.json"; r=json.load(open(f)); j=HERE/"raw"/f"qa_judged_{a}.json"; jd=json.load(open(j))
    bad=[k for k,v in r.items() if v["err"]]
    print(a,"redo",bad)
    for k in bad: r[k]["first_try_err"]=r[k]["err"]; del jd[k]
    for k in bad: pass
    json.dump({k:v for k,v in r.items() if k not in bad}, open(f,"w")); json.dump(jd, open(j,"w"))
