from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/agents/markets.py"
s = f.read_text(encoding="utf-8")
rep = [
("""        chosen.update(derived_markets(chosen, base["inputs"]))
""", """        chosen.update(derived_markets(chosen, base["inputs"]))
        # why what you can count on may sit below Social Security (for the headline's note)
        age, ra = sim["age"], sim["retire_age"]
        chosen["ss_tax_rate"] = sim.get("ss_tax_rate", 0.0)
        chosen["health_extra_in_retirement"] = any(x > 0 for i, x in enumerate(sim["extra_by_year"][:max(1, sim["horizon_age"] - age)]) if age + i >= ra)
        chosen["ss_starts_later"] = (chosen.get("claim_age") or 0) > max(age, ra)
        chosen["social_security_by_year"] = neighbors.ss_for(person, sim, res["chosen_strategy"]["claim_age"])["by_year"]
"""),
("""f"The plan keeps {r.get('strategy', 'the rule of thumb').lower()}, with about {round(r['stock_share_now'] * 100)}% in stocks now.",""",
 """f"The plan keeps about {round(r['stock_share_now'] * 100)}% of savings in stocks now.","""),
("""                "short_before_retirement_of_100")""", """                "short_before_retirement_of_100", "partner_claim_age", "social_security_survivor_per_year")"""),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
