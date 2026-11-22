"""Markets tool: a simple, seeded Monte Carlo of savings in today's dollars.

Each year, stocks and bonds earn a random real return (normal, correlated). The stock share follows the rule of thumb
(110 minus age, at least 20%, at most the cap for the risk choice) unless a strategy gives its own path. Before
retirement the household adds its yearly saving; after it, the household withdraws its spending (grossed up for tax)
less Social Security (after its own income tax) and any annuity income. Extra yearly costs (college, children at home, pets) are withdrawn as given.
An income annuity is bought with a share of savings at retirement and pays a fixed dollar amount, which loses value
to inflation (2.5% a year) in today's dollars.

Return assumptions (real, a year): stocks 5.0% mean, 17% spread; bonds 1.8% mean, 6% spread; correlation 0.1.
These are round, long-run planning figures, not a forecast.
"""
from __future__ import annotations

import numpy as np

STOCK_MU, STOCK_SD = 0.050, 0.17
BOND_MU, BOND_SD = 0.018, 0.06
RHO = 0.1
INFLATION = 0.025
# stock caps by risk choice: the full app's data/assumptions/risk_profiles.json (conservative, moderate, aggressive)
STOCK_CAP = {"careful": 0.50, "balanced": 0.75, "growth": 1.00}
PATHS = 2000
SEED = 409
LAST_GOOD = 0.90
from ..config import SURVIVOR_SPEND_SHARE  # noqa: E402  (spending after the first death of a couple, a share)


def stock_share(risk: str | None, age: int) -> float:
    """Rule of thumb: 110 minus age, between 20% and the cap for the risk choice."""
    return float(min(max((110 - age) / 100.0, 0.20), STOCK_CAP.get(risk or "balanced", 0.75)))


def _draws(n_years: int, paths: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    z1 = rng.standard_normal((paths, n_years))
    z2 = rng.standard_normal((paths, n_years))
    rs = STOCK_MU + STOCK_SD * z1
    rb = BOND_MU + BOND_SD * (RHO * z1 + np.sqrt(1 - RHO ** 2) * z2)
    return rs, rb


INFLATION_EXTRA = 0.03      # "high inflation": 3 points a year above the usual 2.5%, which cuts real returns about as much
BAD_DECADE_CUT = 0.05       # "a bad first decade": stocks earn 5 points a year less than usual (about nothing after inflation)
SHOCK_YEARS = 10


def apply_shock(rs: np.ndarray, rb: np.ndarray, shock: dict, age: int, retire_age: int) -> tuple[np.ndarray, np.ndarray]:
    """A market What If, applied to every scenario. shock: {kind: "fall", size, when: "now"|"retirement"},
    {kind: "inflation"} (a decade from now) or {kind: "bad_decade"} (the first decade of retirement)."""
    rs, rb = rs.copy(), rb.copy()
    n = rs.shape[1]
    t_ret = min(n - 1, max(0, retire_age - age))
    kind = shock.get("kind")
    if kind == "fall":
        t = 0 if shock.get("when", "now") == "now" else t_ret
        rs[:, t] = -abs(float(shock.get("size", 0.30)))
    elif kind == "inflation":
        extra = float(shock.get("size", INFLATION_EXTRA))     # the analysis tests 1.5 points; the What If uses 3
        rs[:, :SHOCK_YEARS] -= extra
        rb[:, :SHOCK_YEARS] -= extra
    elif kind == "bad_decade":
        rs[:, t_ret:t_ret + SHOCK_YEARS] -= BAD_DECADE_CUT
    return rs, rb


def _run(rs, rb, w_stock: np.ndarray, ages: np.ndarray, w0: float, retire_age: int, save_per_year: float, spend: float,
         ss_per_year: float, ss_age: int, extra: np.ndarray, tax_rate: float, annuities: list[dict], keep_path: bool,
         save_by_year: np.ndarray | None = None, other_income: np.ndarray | None = None, lump: np.ndarray | None = None,
         legacy: float = 0.0, ss_tax_rate: float = 0.0, want_short: bool = False, ss_arr: np.ndarray | None = None,
         tax_arr: np.ndarray | None = None, ss_work: np.ndarray | None = None, spend_drop_t: int | None = None,
         fixed_real: np.ndarray | None = None, growth: np.ndarray | None = None, trace: dict | None = None):
    """spend may be one figure or one figure per scenario (the analysis finds each scenario's most it can spend).
    trace: a dict the run fills in (fail_t, need, ss, inc, ann), for the analysis's what-if-it-goes-wrong sentences.
    fixed_real: the buying power of a fixed payment by year (1.0 now) when prices rise faster than assumed.
    growth: 1 + the portfolio return, one row per year (worked out once per simulate() call; same figures)."""
    paths, n = rs.shape
    short = np.zeros(paths, dtype=bool)
    ss_net = ss_per_year * (1 - ss_tax_rate)       # Social Security after its own income tax
    if growth is None:
        growth = _growth(rs, rb, w_stock)
    # year-by-year figures as plain floats: the same values, read faster in the loop
    ages = [int(x) for x in ages]
    extra = [float(x) for x in extra]
    other_income = None if other_income is None else [float(x) for x in other_income]
    save_by_year = None if save_by_year is None else [float(x) for x in save_by_year]
    lump = None if lump is None else [float(x) for x in lump]
    ss_arr = None if ss_arr is None else [float(x) for x in ss_arr]
    tax_arr = None if tax_arr is None else [float(x) for x in tax_arr]
    ss_work = None if ss_work is None else [float(x) for x in ss_work]
    w = np.full(paths, float(w0))
    alive = np.ones(paths, dtype=bool)
    hist = np.empty((n + 1, paths)) if keep_path else None     # one row per year; returned as (paths, years)
    if keep_path:
        hist[0] = w
    gross_up = 1.0 / max(0.05, 1.0 - tax_rate)
    income = [np.zeros(paths) for _ in annuities]
    for t in range(n):
        a = ages[t]
        for i, an in enumerate(annuities):
            if a == an["buy_age"]:
                prem = np.maximum(w, 0.0) * an["share"]
                w = w - prem
                income[i] = prem * an["payout_rate"]
        ann = sum((income[i] * (1 - INFLATION) ** max(0, a - an["buy_age"]) if a >= an["start_age"] else 0.0)
                  for i, an in enumerate(annuities)) if annuities else 0.0
        if fixed_real is not None and annuities:
            t_buy = max(0, min(n - 1, int(annuities[0]["buy_age"]) - int(ages[0])))
            ann = ann * (fixed_real[t] / fixed_real[t_buy] if t >= t_buy else 1.0)
        if lump is not None and lump[t]:
            w = w + lump[t]
        inc = other_income[t] if other_income is not None else 0.0
        if a < retire_age:
            # while working: costs on top of spending now (college, big costs) come out of savings. Costs beyond the
            # savings are counted as short before retirement, not as a failure of the retirement spending.
            sv = save_by_year[t] if save_by_year is not None else save_per_year
            w = w - extra[t] + inc
            if ss_work is not None:
                w = w + ss_work[t] * (1 - ss_tax_rate)     # a benefit someone already draws comes in while you work too
            short |= w < 0
            w = np.maximum(w, 0.0) * growth[t] + sv
        else:
            # retired: income above the spending is saved; spending fails in a year the savings cannot cover it
            ss_t = ss_arr[t] * (1 - ss_tax_rate) if ss_arr is not None else (ss_net if a >= ss_age else 0.0)
            sp = spend * SURVIVOR_SPEND_SHARE if (spend_drop_t is not None and t >= spend_drop_t) else spend
            need = sp + extra[t] - inc - ss_t - ann
            gu = 1.0 / max(0.05, 1.0 - tax_arr[t]) if tax_arr is not None else gross_up
            w = w - np.maximum(0.0, need) * gu + np.maximum(0.0, -need)
            if trace is not None:      # the analysis only: the first year each scenario cannot pay, and that year's figures
                trace["fail_t"][alive & (w < 0)] = t
                trace["need"][t] = need
                trace["ss"][t] = ss_t
                trace["inc"][t] = inc
                trace["ann"][t] = ann
            alive &= w >= 0
            w = np.where(alive, np.maximum(w, 0.0) * growth[t], 0.0)
        if keep_path:
            # savings never show below zero: a year's saving below zero (spending above take-home pay) with nothing
            # left to draw on is counted as short (above), not as a negative balance on the chart (reasonableness audit)
            hist[t + 1] = np.maximum(w, 0.0)
    if legacy > 0:
        alive &= w >= legacy      # the money that must remain at the end
    if keep_path:
        hist = hist.T
    if want_short:
        return alive, hist, short
    return alive, hist


def _growth(rs: np.ndarray, rb: np.ndarray, w_stock: np.ndarray) -> np.ndarray:
    """1 + the portfolio's return, as (years, scenarios), contiguous by year."""
    r = np.maximum(-0.95, w_stock * rs + (1 - w_stock) * rb)
    return np.ascontiguousarray((1 + r).T)


def max_spend_by_path(run, paths: int, hi0: float, steps: int = 24) -> np.ndarray:
    """The most each scenario can spend a year and still last, found for all scenarios at once (one bisection with a
    figure per scenario). A scenario lasts at any lower figure too, so the share of scenarios at or above a figure is
    the chance that figure lasts: the same answer as simulate()'s own search, which looks for the 90 in 100 point."""
    ok0 = run(np.zeros(paths))[0]
    lo, hi = np.zeros(paths), np.full(paths, float(hi0))
    for _ in range(12):
        ok = run(hi)[0]
        if not ok.any() or hi.min() >= 5e6:
            break
        lo, hi = np.where(ok, hi, lo), np.where(ok, hi * 2, hi)
    for _ in range(steps):
        mid = (lo + hi) / 2
        ok = run(mid)[0]
        lo, hi = np.where(ok, mid, lo), np.where(ok, hi, mid)
    return np.where(ok0, lo, -1.0)      # -1: the scenario fails even with no spending of your own


def simulate(age: int, retire_age: int, horizon_age: int, savings: float, save_per_year: float, spend_per_year: float,
             ss_per_year: float, ss_age: int, extra_by_year: list[float] | None = None, tax_rate: float = 0.12,
             risk: str = "balanced", basics_per_year: float | None = None, stock_path: list[float] | None = None,
             annuities: list[dict] | None = None, paths: int = PATHS, seed: int = SEED, chart: bool = True,
             save_by_year: list[float] | None = None, income_by_year: list[float] | None = None,
             lump_by_year: list[float] | None = None, legacy: float = 0.0, ss_tax_rate: float = 0.0,
             shock: dict | None = None, ss_by_year: list[float] | None = None,
             tax_rate_by_year: list[float] | None = None, ss_work_by_year: list[float] | None = None,
             spend_drop_t: int | None = None, fixed_real_by_year: list[float] | None = None, detail: bool = False,
             trace_at: float | None = None) -> dict:
    """stock_path: stock share for each year from `age` (overrides the rule). annuities: [{share (of savings), payout_rate,
    buy_age, start_age}]: bought with that share of savings at buy_age. ss_by_year: gross Social Security for each year
    from `age` (each person's own start, the survivor step-down); when given it replaces ss_per_year and ss_age.
    ss_work_by_year: benefits already being paid, which also come in before retirement. spend_drop_t: the year of the
    first death of a couple; from then on spending (and the basics) are SURVIVOR_SPEND_SHARE of the couple's.
    fixed_real_by_year: buying power of fixed payments (annuities) by year, for the analysis's inflation test.
    detail: also return `_detail` (numpy arrays, for the analysis only): each scenario's most it can spend a year and
    the middle savings path by year."""
    n = max(1, horizon_age - age)
    ages = np.arange(age, age + n)
    extra = np.zeros(n)
    if extra_by_year:
        k = min(n, len(extra_by_year))
        extra[:k] = extra_by_year[:k]
    if stock_path:
        sp = list(stock_path) + [stock_path[-1]] * max(0, n - len(stock_path))
        w_stock = np.array(sp[:n], float)
    else:
        w_stock = np.array([stock_share(risk, int(a)) for a in ages])
    annuities = annuities or []
    rs, rb = _draws(n, paths, seed)
    if shock:
        rs, rb = apply_shock(rs, rb, shock, age, retire_age)

    def arr(xs):
        if not xs:
            return None
        a = np.zeros(n)
        k = min(n, len(xs))
        a[:k] = xs[:k]
        return a
    sby, inc, lmp = arr(save_by_year), arr(income_by_year), arr(lump_by_year)
    ssa = None
    txa = None
    if tax_rate_by_year:
        txa = np.full(n, float(tax_rate))
        k = min(n, len(tax_rate_by_year))
        txa[:k] = tax_rate_by_year[:k]
    if ss_by_year is not None:
        ssa = np.zeros(n)
        k = min(n, len(ss_by_year))
        ssa[:k] = ss_by_year[:k]
        if 0 < k < n:
            ssa[k:] = ss_by_year[k - 1]
    ssw = arr(ss_work_by_year)
    growth = _growth(rs, rb, w_stock)
    fr = None
    if fixed_real_by_year:
        fr = np.ones(n)
        k = min(n, len(fixed_real_by_year))
        fr[:k] = fixed_real_by_year[:k]
        if 0 < k < n:
            fr[k:] = fixed_real_by_year[k - 1]

    def run(spend: float, keep: bool = False, want_short: bool = False, trace: dict | None = None):
        return _run(rs, rb, w_stock, ages, savings, retire_age, save_per_year, spend, ss_per_year, ss_age, extra, tax_rate, annuities, keep,
                    sby, inc, lmp, legacy, ss_tax_rate, want_short, ssa, txa, ssw, spend_drop_t, fr, growth, trace)

    def success(spend: float) -> float:
        return float(run(spend)[0].mean())

    alive, hist, short = run(spend_per_year, True, True)
    p_goal = float(alive.mean())

    lo, hi = 0.0, max(20000.0, spend_per_year * 2, savings / 5 + (max(ss_by_year) if ss_by_year else ss_per_year))
    while success(hi) >= LAST_GOOD and hi < 5e6:
        lo, hi = hi, hi * 2
    if success(lo) < LAST_GOOD:
        safe = 0.0
    else:
        for _ in range(20):
            mid = (lo + hi) / 2
            if success(mid) >= LAST_GOOD:
                lo = mid
            else:
                hi = mid
        safe = lo
    p_basics = success(basics_per_year) if basics_per_year is not None else None
    at_retire = max(0, min(n, retire_age - age))
    out = {
        "paths": paths, "seed": seed,
        "chance_goal_lasts": round(p_goal, 2),
        "goal_lasts_of_100": int(round(p_goal * 100)),
        "spending_goal_per_year": round(spend_per_year),
        "safe_spending_per_year": round(safe, -2),
        "basics_paid_of_100": int(round(p_basics * 100)) if p_basics is not None else None,
        "median_at_retirement": round(float(np.median(hist[:, at_retire])), -3),
        "stock_share_now": round(float(w_stock[0]), 2),
        "stock_share_at_retirement": round(float(w_stock[min(at_retire, n - 1)]), 2),
        # costs before retirement (college, big costs) that run past the savings, in this many of 100 scenarios
        "short_before_retirement_of_100": int(round(float(short.mean()) * 100)),
    }
    if detail:
        hi0 = max(20000.0, spend_per_year * 2, savings / 5 + (max(ss_by_year) if ss_by_year else ss_per_year))
        out["_detail"] = {"max_spend": max_spend_by_path(run, paths, hi0), "median_by_year": np.median(hist, axis=0)}
    if trace_at is not None:
        tr = {"fail_t": np.full(paths, -1), "need": np.zeros((n, paths)), "ss": np.zeros((n, paths)),
              "inc": np.zeros((n, paths)), "ann": np.zeros((n, paths))}
        run(float(trace_at), False, False, tr)
        out["_trace"] = tr
    if chart:
        step = 1 if n <= 45 else 2
        idx = list(range(0, n + 1, step))
        if idx[-1] != n:
            idx.append(n)
        pct = np.percentile(hist[:, idx], [10, 50, 90], axis=0)
        out["median_at_horizon"] = round(float(pct[1][-1]), -3)
        out["low_at_horizon"] = round(float(pct[0][-1]), -3)
        out["chart"] = {"ages": [int(age + i) for i in idx], "median": [round(float(x), -3) for x in pct[1]],
                        "low": [round(float(x), -3) for x in pct[0]], "high": [round(float(x), -3) for x in pct[2]]}
    return out
