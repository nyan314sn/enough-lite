from pathlib import Path
L = Path(__file__).resolve().parents[3]
def sub(rel, old, new):
    f = L / rel
    s = f.read_text(encoding="utf-8")
    assert s.count(old) == 1, (rel, old[:50])
    f.write_text(s.replace(old, new), encoding="utf-8")
M = "app/agents/markets.py"
sub(M, '''        out.update({"retire_age": inp.get("retire_age"), "savings_now": inp.get("savings"), "saving_per_year": inp.get("save_per_year"),
                    "horizon_age": inp.get("horizon_age")})''', '''        out.update({"retire_age": inp.get("retire_age"), "savings_now": inp.get("savings"), "saving_per_year": inp.get("save_per_year"),
                    "horizon_age": inp.get("horizon_age")})
        if r.get("saving_assumed"):
            # an assumed saving is named as one, so the text says "assumed" (simulated users read it as a fact)
            for k in ("saving_per_year", "contributions_per_year"):
                if k in out:
                    out[k + "_assumed"] = out.pop(k)''')
sub(M, '''        r["strategy"] = "Simple plan"
        return r''', '''        r["strategy"] = "Simple plan"
        p = ctx.profile
        r["saving_assumed"] = (p.retire_age or 65) > (p.age or 45) and p.sources.get("save_rate") != "you said" and not p.saving.given()
        return r''')
sub(M, '''        chosen["extras"], chosen["levers"] = base["extras"], base["levers"]''', '''        chosen["extras"], chosen["levers"] = base["extras"], base["levers"]
        chosen["saving_assumed"] = base.get("saving_assumed", False)''')
sub(M, '''"only. Say plainly that markets are uncertain.")''', '''"only. Say plainly that markets are uncertain. A figure whose name ends in 'assumed' is an assumption, "
                    "not the person's own figure: if you use it, say it is assumed.")''')
sub("app/agents/adviser.py", '''"listed figures. No product sales talk. " + STYLE)''', '''"listed figures. A figure whose name ends in 'assumed' is an assumption: if you use it, say it is assumed. "
    "No product sales talk. " + STYLE)''')
print("ok")
