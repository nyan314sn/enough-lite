from pathlib import Path
root = Path(__file__).resolve().parents[3]


def patch(rel, rep):
    f = root / rel
    s = f.read_text(encoding="utf-8")
    for a, b in rep:
        assert s.count(a) == 1, (rel, a[:60])
        s = s.replace(a, b)
    f.write_text(s, encoding="utf-8")


patch("app/tools/simulate.py", [
    ("legacy: float = 0.0, ss_tax_rate: float = 0.0, want_short: bool = False, ss_arr: np.ndarray | None = None):",
     "legacy: float = 0.0, ss_tax_rate: float = 0.0, want_short: bool = False, ss_arr: np.ndarray | None = None,\n"
     "         tax_arr: np.ndarray | None = None):"),
    ("            w = w - np.maximum(0.0, need) * gross_up + np.maximum(0.0, -need)",
     "            gu = 1.0 / max(0.05, 1.0 - tax_arr[t]) if tax_arr is not None else gross_up\n"
     "            w = w - np.maximum(0.0, need) * gu + np.maximum(0.0, -need)"),
    ("             shock: dict | None = None, ss_by_year: list[float] | None = None) -> dict:",
     "             shock: dict | None = None, ss_by_year: list[float] | None = None,\n"
     "             tax_rate_by_year: list[float] | None = None) -> dict:"),
    ("    ssa = None\n",
     "    ssa = None\n    txa = None\n    if tax_rate_by_year:\n        txa = np.full(n, float(tax_rate))\n"
     "        k = min(n, len(tax_rate_by_year))\n        txa[:k] = tax_rate_by_year[:k]\n"),
    ("                    sby, inc, lmp, legacy, ss_tax_rate, want_short, ssa)",
     "                    sby, inc, lmp, legacy, ss_tax_rate, want_short, ssa, txa)"),
])
patch("app/agents/tax.py", [
    ("        ret[\"pension_per_year\"], ret[\"part_time_per_year\"] = round(pension), round(part_time)",
     "        ret[\"pension_per_year\"], ret[\"part_time_per_year\"] = round(pension), round(part_time)\n"
     "        # the rate on withdrawals in years with no pension or part-time pay yet (they stack on top of it otherwise)\n"
     "        ret[\"rate_without_other_income\"] = (tax.retirement_years(p.spending_per_year or 0, p.social_security_per_year or 0,\n"
     "                                          p.savings.model_dump(), p.state, p.has_partner, over65)[\"effective_rate_on_withdrawals\"]\n"
     "                                          if pension + part_time > 0 else ret[\"effective_rate_on_withdrawals\"])"),
])
patch("app/agents/markets.py", [
    ('"extra_by_year": extra, "tax_rate": tx["effective_rate_on_withdrawals"],',
     '"extra_by_year": extra, "tax_rate": tx["effective_rate_on_withdrawals"],\n'
     '        "tax_rate_by_year": [tx["effective_rate_on_withdrawals"] if x > 0 else tx.get("rate_without_other_income", tx["effective_rate_on_withdrawals"])\n'
     '                             for x in ms["income_by_year"]],'),
    ('ARRAYS = ("extra_by_year", "save_by_year", "income_by_year", "lump_by_year", "ss_by_year", "ss_people")',
     'ARRAYS = ("extra_by_year", "save_by_year", "income_by_year", "lump_by_year", "ss_by_year", "ss_people", "tax_rate_by_year")'),
])
print("ok")
