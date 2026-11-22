from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/tools/simulate.py"
s = f.read_text(encoding="utf-8")
rep = [
("legacy: float = 0.0, ss_tax_rate: float = 0.0, want_short: bool = False):\n    paths, n = rs.shape",
 "legacy: float = 0.0, ss_tax_rate: float = 0.0, want_short: bool = False, ss_arr: np.ndarray | None = None):\n    paths, n = rs.shape"),
("            need = spend + extra[t] - inc - (ss_net if a >= ss_age else 0.0) - ann",
 "            ss_t = ss_arr[t] * (1 - ss_tax_rate) if ss_arr is not None else (ss_net if a >= ss_age else 0.0)\n            need = spend + extra[t] - inc - ss_t - ann"),
("             shock: dict | None = None) -> dict:",
 "             shock: dict | None = None, ss_by_year: list[float] | None = None) -> dict:"),
("    buy_age, start_age}]: bought with that share of savings at buy_age.\"\"\"",
 "    buy_age, start_age}]: bought with that share of savings at buy_age. ss_by_year: gross Social Security for each year\n    from `age` (each person's own start, the survivor step-down); when given it replaces ss_per_year and ss_age.\"\"\""),
("    sby, inc, lmp = arr(save_by_year), arr(income_by_year), arr(lump_by_year)",
 "    sby, inc, lmp = arr(save_by_year), arr(income_by_year), arr(lump_by_year)\n    ssa = None\n    if ss_by_year is not None:\n        ssa = np.zeros(n)\n        k = min(n, len(ss_by_year))\n        ssa[:k] = ss_by_year[:k]\n        if 0 < k < n:\n            ssa[k:] = ss_by_year[k - 1]"),
("                    sby, inc, lmp, legacy, ss_tax_rate, want_short)",
 "                    sby, inc, lmp, legacy, ss_tax_rate, want_short, ssa)"),
("savings / 5 + ss_per_year)", "savings / 5 + (max(ss_by_year) if ss_by_year else ss_per_year))"),
]
for a, b in rep:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
