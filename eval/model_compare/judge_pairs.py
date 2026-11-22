"""Blind pairwise judge of plan text. Judge: claude-sonnet-5-5 (a third model). Seed 409 sets which arm is A."""
import json, random, sys
from concurrent.futures import ThreadPoolExecutor
from mc_common import *
import common as ec
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40
SYS = """You compare two versions (A and B) of the written part of a retirement plan that an AI adviser produced for the same household. The numbers behind both come from the same calculator; only the wording differs.
You get the household profile, the calculator's figures (the same for both), and each version's text (the three headline lines, three actions with reasons, family notes).
Judge each criterion as A, B or tie:
- plain_words: ordinary words an ordinary person understands; no jargon, hype, or filler.
- numbers_right: every figure quoted matches the calculator's figures or the profile; no invented or wrongly used numbers.
- actionable: the three actions are specific, fit THIS household, and the person could do them.
- honest_shortfall: if the plan falls short, says so plainly and does not soften or hide it; if it is fine, does not invent worry.
- no_bad_advice: stays out of advice it should not give (named stocks or funds, hiding assets, retiring past 70 to fix things, guarantees).
- overall: which version you would rather hand to the person.
Reply with JSON only: {"plain_words":"A|B|tie","numbers_right":"A|B|tie","actionable":"A|B|tie","honest_shortfall":"A|B|tie","no_bad_advice":"A|B|tie","overall":"A|B|tie","reason":"one short sentence"}"""
P = {a: load_plans(a) for a in ("anthropic", "openai")}
ids = [i for i in P["anthropic"] if i in P["openai"] and P["anthropic"][i]["plan"] and P["openai"][i]["plan"]]
rng = random.Random(409); rng.shuffle(ids)
# stratify by plan verdict so every tier appears
by = {}
for i in ids: by.setdefault((P["anthropic"][i]["plan"].get("wants") or {}).get("verdict"), []).append(i)
pick = []
while len(pick) < N and any(by.values()):
    for v in by.values():
        if v and len(pick) < N: pick.append(v.pop())
out_f = HERE / "raw" / "judge_pairs.json"
res = json.loads(out_f.read_text(encoding="utf-8")) if out_f.exists() else {}
def one(i):
    if i in res: return
    ta, to = ec.plan_text(P["anthropic"][i]["plan"]), ec.plan_text(P["openai"][i]["plan"])
    flip = random.Random(f"409-{i}").random() < 0.5      # True: A = openai
    A, B = (to, ta) if flip else (ta, to)
    rec = {"id": i, "A_is": "openai" if flip else "anthropic", "identical": ta.strip() == to.strip()}
    if rec["identical"]:
        rec.update({k: "tie" for k in ("plain_words", "numbers_right", "actionable", "honest_shortfall", "no_bad_advice", "overall")})
    else:
        prof = P["anthropic"][i]["profile"]
        u = ("PROFILE\n" + json.dumps(prof) + "\n\nCALCULATOR FIGURES (same for both)\n" + json.dumps(strip_text(P["anthropic"][i]["plan"]))[:4500]
             + "\n\nVERSION A\n" + A + "\n\nVERSION B\n" + B)
        raw = judge_call(SYS, u, 1000, "pair_judge"); j = parse_json(raw)
        if not j.get("overall"): j = {"raw": raw[:600]}
        rec.update(j)
    res[i] = rec
    out_f.write_text(json.dumps(res, indent=1), encoding="utf-8")
with ThreadPoolExecutor(3) as ex: list(ex.map(one, pick))
print(len(res), "pairs judged; judge cost so far", round(total_cost(), 4))
