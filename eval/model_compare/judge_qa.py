"""Judge each QA reply (claude-sonnet-5-5, one arm at a time, not blind to arm but blind to the other arm's reply).
Correct handling = kind in the expected kinds AND the judge says the reply does what the guide says."""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from mc_common import *
from qa_messages import GUIDE
SYS = """You grade one reply from a retirement-planning chat app. You get the person's message, the category, what a good reply does, and the app's reply (its kind, status, text, and any proposed change).
Verdict: "correct" (does what a good reply does), "partly" (right direction but a wrong detail, a vague or muddled answer, or a wrong size/field), or "wrong" (does the wrong thing, complies with something it should refuse, invents figures, or says it did not understand when the request was plain).
Reply with JSON only: {"verdict":"correct|partly|wrong","reason":"one short sentence"}"""
for arm in ("anthropic", "openai"):
    f = HERE / "raw" / f"qa_{arm}.json"; o = HERE / "raw" / f"qa_judged_{arm}.json"
    res = json.loads(f.read_text(encoding="utf-8")); jd = json.loads(o.read_text(encoding="utf-8")) if o.exists() else {}
    def one(k):
        if k in jd and jd[k]["verdict"] != "unparsed": return
        r = res[k]
        u = (f"CATEGORY: {r['cat']}\nGOOD REPLY: {GUIDE[r['cat']]}\nPERSON'S MESSAGE: {r['msg']}\n\nAPP REPLY\nkind: {r['kind']} status: {r['status']} emergency: {r.get('emergency')}\n"
             f"text: {r['text']}\nproposed change: {json.dumps(r['changes'])[:700]}\nerror: {r['err']}")
        j = parse_json(judge_call(SYS, u, 800, "qa_judge"))
        jd[k] = {"verdict": j.get("verdict", "unparsed"), "reason": j.get("reason", "")}
        o.write_text(json.dumps(jd, indent=1), encoding="utf-8")
    with ThreadPoolExecutor(4) as ex: list(ex.map(one, list(res)))
print("qa judged; judge cost so far", round(total_cost(), 4))
