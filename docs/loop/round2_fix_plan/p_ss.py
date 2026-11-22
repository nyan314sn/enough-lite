"""Patch: Social Security of someone already claiming counts in working years; spending steps down after the first death."""
from pathlib import Path
L = Path(__file__).resolve().parents[3]
def sub(rel, old, new, count=1):
    f = L / rel
    s = f.read_text(encoding="utf-8")
    assert s.count(old) == count, (rel, old[:60], s.count(old))
    f.write_text(s.replace(old, new), encoding="utf-8")

sub("app/tools/socialsec.py", """    per = {x["who"]: round(sum(a), -2) for x, a in zip(people, amts)}""",
"""    # benefits already being paid (someone already claiming): they also come in while the household still works
    working = [min(by_year[t], sum(r[t] for x, r in zip(people, each) if x.get("fixed"))) for t in range(n)]
    per = {x["who"]: round(sum(a), -2) for x, a in zip(people, amts)}""")
sub("app/tools/socialsec.py", """    out = {"by_year": [round(v) for v in by_year], "claims\"""",
"""    out = {"by_year": [round(v) for v in by_year], "working_by_year": [round(v) for v in working], "claims\"""")

sub("app/tools/neighbors.py", """    args = {k: v for k, v in sim.items() if k not in ("ss_per_year", "ss_age", "ss_by_year", "ss_people", "ss_first_death_t")}""",
"""    args = {k: v for k, v in sim.items() if k not in ("ss_per_year", "ss_age", "ss_by_year", "ss_people", "ss_first_death_t", "ss_work_by_year")}""")
sub("app/tools/neighbors.py", """    r = simulate.simulate(**args, ss_per_year=ss["total_per_year"], ss_age=you, ss_by_year=ss["by_year"],""",
"""    r = simulate.simulate(**args, ss_per_year=ss["total_per_year"], ss_age=you, ss_by_year=ss["by_year"], ss_work_by_year=ss.get("working_by_year"),""")

sub("app/agents/markets.py", """        "ss_by_year": ss["by_year"], "ss_people": ss["people"], "ss_first_death_t": ss["first_death_t"],""",
"""        "ss_by_year": ss["by_year"], "ss_people": ss["people"], "ss_first_death_t": ss["first_death_t"],
        "ss_work_by_year": ss["working_by_year"], "spend_drop_t": ss["first_death_t"],""")
sub("app/agents/markets.py", """ARRAYS = ("extra_by_year", "save_by_year", "income_by_year", "lump_by_year", "ss_by_year", "ss_people", "tax_rate_by_year")""",
"""ARRAYS = ("extra_by_year", "save_by_year", "income_by_year", "lump_by_year", "ss_by_year", "ss_people", "tax_rate_by_year", "ss_work_by_year")""")

S = "app/tools/simulate.py"
sub(S, """LAST_GOOD = 0.90
""", """LAST_GOOD = 0.90
from ..config import SURVIVOR_SPEND_SHARE  # noqa: E402  (spending after the first death of a couple, a share)
""")
sub(S, """         legacy: float = 0.0, ss_tax_rate: float = 0.0, want_short: bool = False, ss_arr: np.ndarray | None = None,
         tax_arr: np.ndarray | None = None):""", """         legacy: float = 0.0, ss_tax_rate: float = 0.0, want_short: bool = False, ss_arr: np.ndarray | None = None,
         tax_arr: np.ndarray | None = None, ss_work: np.ndarray | None = None, spend_drop_t: int | None = None):""")
sub(S, """            w = w - extra[t] + inc
            short |= w < 0""", """            w = w - extra[t] + inc
            if ss_work is not None:
                w = w + ss_work[t] * (1 - ss_tax_rate)     # a benefit someone already draws comes in while you work too
            short |= w < 0""")
sub(S, """            need = spend + extra[t] - inc - ss_t - ann""", """            sp = spend * SURVIVOR_SPEND_SHARE if (spend_drop_t is not None and t >= spend_drop_t) else spend
            need = sp + extra[t] - inc - ss_t - ann""")
sub(S, """             shock: dict | None = None, ss_by_year: list[float] | None = None,
             tax_rate_by_year: list[float] | None = None) -> dict:""", """             shock: dict | None = None, ss_by_year: list[float] | None = None,
             tax_rate_by_year: list[float] | None = None, ss_work_by_year: list[float] | None = None,
             spend_drop_t: int | None = None) -> dict:""")
sub(S, """    from `age` (each person's own start, the survivor step-down); when given it replaces ss_per_year and ss_age.\"\"\"""",
"""    from `age` (each person's own start, the survivor step-down); when given it replaces ss_per_year and ss_age.
    ss_work_by_year: benefits already being paid, which also come in before retirement. spend_drop_t: the year of the
    first death of a couple; from then on spending (and the basics) are SURVIVOR_SPEND_SHARE of the couple's.\"\"\"""")
sub(S, """        if 0 < k < n:
            ssa[k:] = ss_by_year[k - 1]
""", """        if 0 < k < n:
            ssa[k:] = ss_by_year[k - 1]
    ssw = arr(ss_work_by_year)
""")
sub(S, """                    sby, inc, lmp, legacy, ss_tax_rate, want_short, ssa, txa)""", """                    sby, inc, lmp, legacy, ss_tax_rate, want_short, ssa, txa, ssw, spend_drop_t)""")

sub("app/config.py", """MATCH_MIN_YEARS_LEFT = 2       # no employer-match advice with fewer than this many working years left
""", """MATCH_MIN_YEARS_LEFT = 2       # no employer-match advice with fewer than this many working years left
SURVIVOR_SPEND_SHARE = 0.75    # after the first death of a couple, the survivor spends this share (a common rule of thumb)
""")
print("ok")
