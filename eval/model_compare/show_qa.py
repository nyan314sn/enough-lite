import json
from mc_common import *
A={a:json.load(open(HERE/"raw"/f"qa_{a}.json")) for a in ("anthropic","openai")}
J={a:json.load(open(HERE/"raw"/f"qa_judged_{a}.json")) for a in ("anthropic","openai")}
for k in A["anthropic"]:
    a,o=A["anthropic"][k],A["openai"][k]
    ja,jo=J["anthropic"][k]["verdict"],J["openai"][k]["verdict"]
    if ja!=jo or ja!="correct":
        print(f'{k} [{a["cat"]}] {a["msg"][:70]}\n   H: {a["kind"]}/{a["status"]} {ja} err={a["err"]} | {(a["text"] or "")[:90]!r}\n   G: {o["kind"]}/{o["status"]} {jo} err={o["err"]} | {(o["text"] or "")[:90]!r}')
