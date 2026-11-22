from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/tools/neighbors.py"
s = f.read_text(encoding="utf-8")
a0 = s.index("def _ss_for(")
a1 = s.index("TIE_SHARE, TIE_MIN")
new_score = '''def _people(person: dict, sim: dict) -> list[dict]:
    """Each person's Social Security (household.ss_people), or one person standing for the household figure."""
    if sim.get("ss_people") is not None:
        return sim["ss_people"]
    return socialsec.from_household(float(sim.get("ss_per_year") or 0), int(sim.get("ss_age") or 67), int(person["age"]))


def ss_for(person: dict, sim: dict, claim_age: int | None) -> dict:
    """Household Social Security by year under a strategy's claiming age: each person claims at that age of their own
    (never before their age now); a claiming age the person chose, or one already started, is kept."""
    n = max(1, int(sim["horizon_age"]) - int(sim["age"]))
    return socialsec.schedule(_people(person, sim), n, claim_age, sim.get("ss_first_death_t"))


def score(person: dict, sim: dict, strat: dict, chart: bool = False) -> dict:
    ss = ss_for(person, sim, strat["claim_age"])
    args = {k: v for k, v in sim.items() if k not in ("ss_per_year", "ss_age", "ss_by_year", "ss_people", "ss_first_death_t")}
    you = ss["claims"].get("you", int(sim.get("ss_age") or 67))
    r = simulate.simulate(**args, ss_per_year=ss["total_per_year"], ss_age=you, ss_by_year=ss["by_year"],
                          stock_path=strat["stock_path"], annuities=strat["annuities"], chart=chart)
    r["claim_age"] = you
    r["partner_claim_age"] = ss["claims"].get("partner")
    r["social_security_per_year"] = ss["total_per_year"]
    r["social_security_by_person"] = ss["per_year"]
    if "survivor_per_year" in ss:
        r["social_security_survivor_per_year"] = ss["survivor_per_year"]
    # wants: what you can count on a year, basics included (the plan's headline figure); and the part above the basics
    r["wants_per_year"] = r["safe_spending_per_year"]
    r["above_basics_per_year"] = max(0.0, round(r["safe_spending_per_year"] - (sim.get("basics_per_year") or 0), -2))
    return r


GRID_CLAIMS = range(62, 71)          # the fixed grid: the rule of thumb claiming at each age from 62 to 70 ...
GRID_STOCK_SHIFTS = (-0.15, 0.15)    # ... and the rule's stock path 15 points lower and higher (at the default claim)


def grid(person: dict, sim: dict, rule: dict, cap: float) -> list[dict]:
    """The same candidates for every household, scored alongside the similar households so that what you can count on
    never depends on which households happen to be nearest: the rule of thumb with each claiming age from 62 to 70
    (when someone can still choose), and with its stock path shifted down and up."""
    out = []
    people = _people(person, sim)
    free = [x for x in people if not (x.get("fixed") or x.get("chosen"))]
    if free:
        lo = max(62, min(int(x["age"]) for x in free))
        for c in GRID_CLAIMS:
            if c < lo:
                continue
            out.append({**rule, "name": f"Rule of thumb, claiming at {c}", "source": f"rule-claim-{c}", "claim_age": c,
                        "description": f"Stocks at 110 minus your age, claim Social Security at {c}, no products"})
    for d in GRID_STOCK_SHIFTS:
        path = [float(min(cap, max(0.10, x + d))) for x in rule["stock_path"]]
        if path == rule["stock_path"]:
            continue
        word = "more" if d > 0 else "less"
        out.append({**rule, "stock_path": path, "name": f"Rule of thumb, {round(abs(d) * 100)} points {word} in stocks",
                    "source": f"rule-stocks{'+' if d > 0 else '-'}{round(abs(d) * 100)}",
                    "description": f"Stocks at 110 minus your age, {round(abs(d) * 100)} points {word}, no products"})
    return out


'''
s = s[:a0] + new_score + s[a1:]
rep = [
("from . import estimates, simulate", "from . import estimates, simulate, socialsec"),
("""    early = early_claim(person, sim, strategies[-1])
    if early:
        strategies.append(early)
""", """    strategies += grid(person, sim, strategies[-1], cap)
"""),
("""                       "claim_age": r["claim_age"], "stock_share_now": r["stock_share_now"],""",
 """                       "claim_age": r["claim_age"], "partner_claim_age": r.get("partner_claim_age"), "stock_share_now": r["stock_share_now"],"""),
("""    elif chosen["source"] == "rule-claim":""", """    elif chosen["source"].startswith("rule-claim"):"""),
("""    else:
        note = tested + "The rule of thumb kept your basics safest and left the most to spend.\"""",
 """    elif chosen["source"].startswith("rule-stocks"):
        note = tested + (f"The rule of thumb with {chosen['description'].split(', ')[1]} kept your basics safest "
                         "and left the most to spend.")
    else:
        note = tested + "The rule of thumb kept your basics safest and left the most to spend.\""""),
]
for a, b in rep:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
