from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/agents/markets.py"
s = f.read_text(encoding="utf-8")
rep = [
("""    ss_age = household.claim_age(p)
    if age >= ss_age:
        ss_age = age
    working = ra > age
""", """    n = max(1, lon["horizon_age"] - age)
    ss = household.ss_household(p, n, lon.get("life_expectancy_you"), lon.get("life_expectancy_partner"))
    working = ra > age
"""),
(""""ss_per_year": household.stated_ss_at_claim(p, ss_age), "ss_age": ss_age,""",
 """"ss_per_year": ss["total_per_year"], "ss_age": ss["claims"]["you"],
        "ss_by_year": ss["by_year"], "ss_people": ss["people"], "ss_first_death_t": ss["first_death_t"],"""),
('ARRAYS = ("extra_by_year", "save_by_year", "income_by_year", "lump_by_year")',
 'ARRAYS = ("extra_by_year", "save_by_year", "income_by_year", "lump_by_year", "ss_by_year", "ss_people")\nNOT_SIM = ("ss_people", "ss_first_death_t")     # inputs for the strategy test, not for simulate()\n\n\ndef sim_args(sim: dict) -> dict:\n    return {k: v for k, v in sim.items() if k not in NOT_SIM}'),
("        r = simulate.simulate(**sim)\n", "        r = simulate.simulate(**sim_args(sim))\n"),
]
for a, b in rep:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
