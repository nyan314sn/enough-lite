import json, collections
r = json.load(open("raw/judge_pairs.json"))
crit = ["plain_words","numbers_right","actionable","honest_shortfall","no_bad_advice","overall"]
def tally(sub):
    out = {}
    for c in crit:
        cnt = collections.Counter()
        for x in sub:
            v = x.get(c)
            if v in ("A","B"): cnt[x["A_is"] if v=="A" else ("openai" if x["A_is"]=="anthropic" else "anthropic")] += 1
            else: cnt["tie"] += 1
        out[c] = dict(cnt)
    return out
allp = list(r.values())
res = {"n": len(allp), "identical_text": sum(x["identical"] for x in allp), "all": tally(allp), "non_identical": tally([x for x in allp if not x["identical"]])}
print(json.dumps(res, indent=1)); json.dump(res, open("results_pairs.json","w"), indent=1)
