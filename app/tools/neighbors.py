"""Neighbours tool: test the whole strategies of the 5 most similar households, and the rule of thumb, on the person's
own numbers, and keep the one that pays the basics most often, then leaves the most to spend.

Library: app/data/households.json, 467 optimized plans of synthetic households from the full app's saved runs
(see its meta.note). Matching follows the neighbour check (hw-Final-2/docs/LITE_NEIGHBOR_CHECK.md): 19 standardized,
weighted features plus census region, Euclidean distance, k = 5. Each neighbour's decisions are applied whole (never
averaged): its stock share by stage of life, its claiming age relative to full retirement age, and its income annuity
if it holds one (bought with 30% of savings at retirement). The person's own retirement age is kept.

Lite has no optimizer to fall back on, so the result carries a low-confidence flag when the chosen strategy pays the
basics in fewer than 95 of 100 scenarios, when the person is unlike anyone in the library (mean distance above the
library's 95th percentile), or when products matter and no neighbour holds that kind.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

import numpy as np

from ..config import DATA_DIR
from . import estimates, simulate, socialsec

K = 5
FRA = 67
ANNUITY_SHARE = 0.30
INCOME_KINDS = {"spia", "dia"}
DEFAULT_PAYOUT = {"spia": 0.07, "dia": 0.25}
DEFAULT_START = {"dia": 80}
BASICS_GUARD = 1          # keep candidates within 1 point of the best basics paid, then pick the most to spend
SAFE_BASICS = 95
RISK_TO_CAP = {"careful": "conservative", "balanced": "moderate", "growth": "aggressive"}
REGION = {}
for _r, _ss in {"NE": "CT ME MA NH RI VT NJ NY PA", "MW": "IL IN MI OH WI IA KS MN MO NE ND SD",
                "S": "DE FL GA MD NC SC VA DC WV AL KY MS TN AR LA OK TX",
                "W": "AZ CO ID MT NV NM UT WY AK CA HI OR WA"}.items():
    for _s in _ss.split():
        REGION[_s] = _r
LOW_NOTE = "Few example households are like yours, so treat this as a rough guide."


@lru_cache(maxsize=1)
def library() -> dict:
    d = json.load(open(DATA_DIR / "households.json", encoding="utf-8"))
    m = d["meta"]
    keys = m["scale"]["keys"]
    w = np.array([m["weights"][k] for k in keys])
    mu, sd = np.array(m["scale"]["mu"]), np.array(m["scale"]["sd"])
    rows = d["households"]
    Z = np.array([[r["features"][k] for k in keys] for r in rows], float)
    Z = (Z - mu) / sd * w
    R = np.array([[m["region_weight"] * 2 * (r["features"]["region"] == g) for g in m["regions"]] for r in rows], float)
    return {"meta": m, "rows": rows, "Z": np.hstack([Z, R]), "keys": keys, "w": w, "mu": mu, "sd": sd}


def features_of(p: dict) -> dict:
    """The library's features for a lite profile (a dict from Profile.model_dump(), already completed)."""
    age = int(p["age"])
    couple = bool(p.get("has_partner") or p.get("partner_age"))
    page = int(p.get("partner_age") or age) if couple else age
    ra = int(p.get("retire_age") or 65)
    inc = float(p.get("pay_per_year") or 0) + float(p.get("partner_pay_per_year") or 0)
    sv = p.get("savings") or {}
    pre, roth, tx, cash = (float(sv.get(k) or 0) for k in ("pretax", "roth", "taxable", "cash"))
    home = p.get("home") or {}
    mort = float(home.get("mortgage_balance") or 0)
    ss = float(p.get("social_security_per_year") or 0)
    spend = float(p.get("spending_per_year") or 0)
    resources = max(inc, ss + 0.04 * (pre + roth + tx + cash), 1000.0)
    caps = library()["meta"]["equity_caps"]
    return {"age": age, "page": page, "gap": abs(page - age), "couple": 1.0 if couple else 0.0,
            "working": 1.0 if (inc > 0 and ra > age) else 0.0, "ytr": max(ra - age, 0), "l_inc": math.log10(1 + inc),
            "l_pretax": math.log10(1 + pre), "l_roth": math.log10(1 + roth), "l_taxable": math.log10(1 + tx), "l_cash": math.log10(1 + cash),
            "home": 1.0 if home.get("owns") else 0.0, "l_mort": math.log10(1 + mort), "l_debt": math.log10(1 + sum(float(d.get("balance") or 0) for d in (p.get("debts") or []))), "l_ss": math.log10(1 + ss),
            "l_pen": math.log10(1 + sum(float(x.get("per_year") or 0) for x in (p.get("pensions") or []))), "deps": float(len(p.get("children") or [])), "spend_ratio": min(spend / resources, 3.0),
            "cap": float(caps.get(RISK_TO_CAP.get(p.get("risk") or "balanced", "moderate"), 0.75)),
            "region": REGION.get((p.get("state") or "").upper(), "S")}


def nearest(feat: dict, k: int = K) -> list[tuple[dict, float]]:
    lib = library()
    x = (np.array([feat[key] for key in lib["keys"]], float) - lib["mu"]) / lib["sd"] * lib["w"]
    r = np.array([lib["meta"]["region_weight"] * 2 * (feat["region"] == g) for g in lib["meta"]["regions"]])
    d = np.sqrt(((lib["Z"] - np.hstack([x, r])) ** 2).sum(1))
    order = np.argsort(d)[:k]
    return [(lib["rows"][i], float(d[i])) for i in order]


def _eq_at(nb: dict, age: int) -> float | None:
    path = nb["decisions"]["stock_share_by_age"]
    if not path:
        return None
    e = path[0][1]
    for a0, x in path:
        if a0 <= age:
            e = x
    return e


def _nb_age(nb: dict, h_age: int, h_retire: int) -> int:
    """The neighbour's age matching the person's: years to retirement while working, own age after."""
    d = nb["decisions"]
    a = d["retire_age"] - (h_retire - h_age) if h_age < h_retire else max(h_age, d["retire_age"])
    return max(a, d["age"])


def describe(nb: dict) -> str:
    f, raw = nb["features"], nb["raw"]
    who = f"a couple aged {int(f['age'])} and {int(f['page'])}" if f["couple"] else f"a single person aged {int(f['age'])}"
    work = "still working" if f["working"] else "retired"
    return f"{who}, {work}, with about ${round(raw['savings'], -3):,.0f} saved"


def strategy_from(nb: dict | None, person: dict, horizon_age: int, cap: float) -> dict:
    """A whole strategy for the person: stock path by year, claiming age, annuities."""
    age, ra = int(person["age"]), int(person["retire_age"])
    years = range(age, max(age + 1, horizon_age))
    if nb is None:
        return {"name": "Simple plan", "source": "rule", "stock_path": [simulate.stock_share(person.get("risk"), a) for a in years],
                "claim_age": None, "annuities": [], "products": [], "description": "Stocks at 110 minus your age, claim at 67, no products"}
    d = nb["decisions"]
    path = []
    for a in years:
        e = _eq_at(nb, _nb_age(nb, a, ra))
        path.append(min(cap, e) if e is not None else simulate.stock_share(person.get("risk"), a))
    off = d.get("claim_offset_self")
    claim = None if off is None else int(min(max(round(FRA + off), 62, age), 70))
    ann, kinds = [], []
    for pr in d["products"]:
        k = pr["kind"]
        kinds.append(k)
        if k in INCOME_KINDS and not any(x["kind"] == k for x in ann):
            start = int(pr.get("start_age") or DEFAULT_START.get(k, ra))
            ann.append({"kind": k, "share": ANNUITY_SHARE, "payout_rate": float(pr.get("payout_rate") or DEFAULT_PAYOUT[k]),
                        "buy_age": max(ra, age), "start_age": max(start, ra, age)})
    return {"name": f"Similar household {nb['id']}", "source": f"{nb['id']}-{nb['mode']}", "stock_path": path, "claim_age": claim,
            "annuities": ann, "products": sorted(set(kinds)), "description": describe(nb)}


def early_claim(person: dict, sim: dict, rule: dict) -> dict | None:
    """The rule of thumb, claiming Social Security when you retire (62 at the earliest) instead of at 67. Tested when
    you retire before 67 and have not chosen a claiming age: savings then need not bridge the years until 67."""
    age, ra = int(person["age"]), int(person["retire_age"])
    claim = max(62, ra, age)
    if person.get("claim_age") or float(sim.get("ss_per_year") or 0) <= 0 or claim >= int(sim["ss_age"]):
        return None
    return {**rule, "name": f"Simple plan, claiming at {claim}", "source": "rule-claim", "claim_age": claim,
            "description": f"Stocks at 110 minus your age, claim Social Security at {claim}, no products"}


def _people(person: dict, sim: dict) -> list[dict]:
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
    args = {k: v for k, v in sim.items() if k not in ("ss_per_year", "ss_age", "ss_by_year", "ss_people", "ss_first_death_t", "ss_work_by_year")}
    you = ss["claims"].get("you", int(sim.get("ss_age") or 67))
    r = simulate.simulate(**args, ss_per_year=ss["total_per_year"], ss_age=you, ss_by_year=ss["by_year"], ss_work_by_year=ss.get("working_by_year"),
                          stock_path=strat["stock_path"], annuities=strat["annuities"], chart=chart)
    r["claim_age"] = you
    r["partner_claim_age"] = ss["claims"].get("partner")
    r["already_claiming"] = bool(ss["already"].get("you"))
    r["partner_already_claiming"] = bool(ss["already"].get("partner"))
    r["social_security_per_year"] = ss["total_per_year"]
    r["social_security_by_person"] = ss["per_year"]
    if "survivor_per_year" in ss:
        r["social_security_survivor_per_year"] = ss["survivor_per_year"]
    # wants: what you can count on a year, basics included (the plan's headline figure); and the part above the basics
    r["wants_per_year"] = r["safe_spending_per_year"]
    r["above_basics_per_year"] = max(0.0, round(r["safe_spending_per_year"] - (sim.get("basics_per_year") or 0), -2))
    return r


def adapt(strat: dict, age: int, retire_age: int, claim: int | None = None) -> dict:
    """The plan's kept strategy for a changed profile (a What If, a lever, a starting point): the same stock path and
    claiming age, an annuity bought when you now retire. Every one-change test uses this, so the "What each choice is
    worth" table and the What If give the same figure for the same change."""
    s = dict(strat)
    if s.get("annuities"):
        s["annuities"] = [{**a, "buy_age": max(retire_age, age), "start_age": max(a["start_age"], retire_age, age)} for a in s["annuities"]]
    if claim is not None:
        s["claim_age"] = claim
    return s


def one_change(person: dict, sim: dict, kept: dict, repick: bool) -> tuple[dict, dict | None]:
    """The strategy for a plan with one change (a What If, a lever in the analysis, a starting point), and the strategy
    test result when a fresh pick was made. The same rule everywhere, so the table and the What If agree:
    - the plan's basics are safe (repick False): the plan's own strategy, so only the change moves the figures and
      retiring a year later never gives less (a fresh pick could, audit R12);
    - the basics are not safe (repick True), or the change leaves them unsafe on the plan's own strategy (paid in
      fewer than REPICK_BELOW of 100): the better of the plan's own strategy and a fresh pick (by pick()), since a
      change may need another strategy to make the basics safe."""
    s0 = adapt(kept, int(sim["age"]), int(sim["retire_age"]))
    r0 = None
    if not repick:
        # a change that leaves the basics unsafe on the plan's own strategy is tested against a fresh pick too, the same
        # rule as a plan that falls short: keeping a strategy the change has broken understated what you can count on
        # (reasonableness audit: a child added to a safe plan kept Social Security at 70, $6,300 against $26,100 fresh)
        r0 = score(person, sim, s0)
        if (r0["basics_paid_of_100"] or 0) >= REPICK_BELOW:
            return s0, None
    res = test_strategies(person, sim)
    r0 = r0 or score(person, sim, s0)
    row = {"name": s0["name"], "source": "kept:" + s0["source"], "description": s0["description"],
           "basics_paid_of_100": r0["basics_paid_of_100"], "safe_spending_per_year": r0["safe_spending_per_year"],
           "wants_per_year": r0["wants_per_year"], "goal_lasts_of_100": r0["goal_lasts_of_100"], "claim_age": r0["claim_age"],
           "partner_claim_age": r0.get("partner_claim_age"), "stock_share_now": r0["stock_share_now"],
           "stock_share_at_retirement": r0["stock_share_at_retirement"], "products": s0["products"], "annuity": bool(s0["annuities"])}
    if pick([res["chosen"], row]) is row:
        return s0, {**res, "chosen": {**row, "source": s0["source"]}, "chosen_strategy": s0,
                    "note": "We tried other plans on the new numbers. Your own mix and claiming age still did best."}
    return res["chosen_strategy"], res


REPICK_BELOW = 90          # the adviser's "falls short" line (adviser.BASICS_SAFE): a changed plan below it gets a fresh pick too


GRID_CLAIMS = range(62, 71)       # the fixed grid: the rule of thumb claiming at each age from 62 to 70 ...
GRID_STOCK_SHIFTS = (-0.30, -0.15, 0.15)   # ... and the rule's stock path shifted, at the default claim and at 70


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
            out.append({**rule, "name": f"Simple plan, claiming at {c}", "source": f"rule-claim-{c}", "claim_age": c,
                        "description": f"Stocks at 110 minus your age, claim Social Security at {c}, no products"})
    seen = set()
    for d in GRID_STOCK_SHIFTS:
        path = [float(min(cap, max(0.10, x + d))) for x in rule["stock_path"]]
        if path == rule["stock_path"] or tuple(path) in seen:
            continue
        seen.add(tuple(path))
        word = "more" if d > 0 else "less"
        pts = round(abs(d) * 100)
        for c in ([None, 70] if free else [None]):
            tag = "" if c is None else f"-claim-{c}"
            out.append({**rule, "stock_path": path, "claim_age": c,
                        "name": f"Simple plan, {pts} points {word} in stocks" + ("" if c is None else f", claiming at {c}"),
                        "source": f"rule-stocks{'+' if d > 0 else '-'}{pts}{tag}",
                        "description": f"Stocks at 110 minus your age, {pts} points {word}" + ("" if c is None else f", claim at {c}") + ", no products"})
    return out


TIE_SHARE, TIE_MIN = 0.01, 300.0    # safe spending within this of the best counts as a tie (simulation noise)


def _order(c: dict) -> tuple:
    """A fixed order for ties: the rule of thumb, then its early-claiming variant, then similar households by id."""
    s = c["source"]
    return (0 if s == "rule" else 1 if s.startswith("rule") else 2, s)


def pick(scored: list[dict]) -> dict:
    """Basics first: keep candidates that pay the basics safely, then the most to spend.
    Candidates within noise of the most to spend tie, and a tie goes to the first in a fixed order, so near-identical
    inputs keep the same strategy."""
    best = max(c["basics_paid_of_100"] or 0 for c in scored)
    # a fixed bar, not "near the best", so more pay or savings can only add candidates to the pool and what you can
    # count on never falls: when some candidate pays the basics in 95 of 100, keep those (less the guard). When none
    # does, keep all: the most you can count on is then also the plan that comes nearest to the basics (a "near the
    # best basics paid" pool let count-on fall by up to a quarter when pay rose, audit round 1 F5)
    pool = [c for c in scored if (c["basics_paid_of_100"] or 0) >= SAFE_BASICS - BASICS_GUARD] if best >= SAFE_BASICS else list(scored)
    top = max(c["safe_spending_per_year"] for c in pool)
    near = [c for c in pool if c["safe_spending_per_year"] >= top - max(TIE_MIN, TIE_SHARE * top)]
    if top <= 0 and max(c["basics_paid_of_100"] or 0 for c in near) <= 0:
        # nothing lasts on any strategy (often years with no income and no savings before Social Security): every
        # candidate ties at zero, and the fixed order kept claiming at 67 for someone retired at 61 with $2,200 saved.
        # Then the earliest claim, so income starts as soon as it can (reasonableness audit)
        return min(near, key=lambda c: (c.get("claim_age") or 99, _order(c)))
    return min(near, key=_order)


def test_strategies(person: dict, sim: dict, products_matter: bool = False, wanted_kind: str | None = None) -> dict:
    """person: completed profile dict; sim: the keyword arguments of simulate() for the person's own numbers."""
    feat = features_of(person)
    nbs = nearest(feat)
    mean_d = float(np.mean([d for _, d in nbs]))
    cap = simulate.STOCK_CAP.get(person.get("risk") or "balanced", 0.75)
    strategies = [strategy_from(nb, person, sim["horizon_age"], cap) for nb, _ in nbs] + [strategy_from(None, person, sim["horizon_age"], cap)]
    strategies += grid(person, sim, strategies[-1], cap)
    scored = []
    for s in strategies:
        r = score(person, sim, s)
        scored.append({"name": s["name"], "source": s["source"], "description": s["description"],
                       "basics_paid_of_100": r["basics_paid_of_100"], "safe_spending_per_year": r["safe_spending_per_year"],
                       "wants_per_year": r["wants_per_year"], "goal_lasts_of_100": r["goal_lasts_of_100"],
                       "claim_age": r["claim_age"], "partner_claim_age": r.get("partner_claim_age"), "stock_share_now": r["stock_share_now"],
                       "stock_share_at_retirement": r["stock_share_at_retirement"], "products": s["products"],
                       "annuity": bool(s["annuities"])})
    chosen = pick(scored)
    strat = strategies[[c["source"] for c in scored].index(chosen["source"])]
    p95 = library()["meta"]["mean_distance_p95"]
    reasons = []
    if (chosen["basics_paid_of_100"] or 0) < SAFE_BASICS:
        reasons.append("needs are not safe on any strategy we tested")
    if mean_d > p95:
        reasons.append("no household in the library is close to yours")
    kinds = {pr["kind"] for nb, _ in nbs for pr in nb["decisions"]["products"]}
    if products_matter and (wanted_kind or "spia") not in kinds:
        reasons.append("no similar household holds that product")
    low = bool(reasons)
    used = not chosen["source"].startswith("rule")
    n_similar = sum(1 for c in scored if not c["source"].startswith("rule"))
    n_rule = len(scored) - n_similar
    tested = "We tried plans from similar households and some simple plans. "
    best = "keeps your needs safest and leaves the most to spend"
    if used:
        note = tested + f"The plan of {chosen['description']} did best. It {best}."
    elif chosen["source"].startswith("rule-claim"):
        who = "each of you claiming Social Security" if chosen.get("partner_claim_age") else "Social Security"
        note = tested + f"A simple plan did best: stocks at 110 minus your age, with {who} from {chosen['claim_age']}. It {best}."
    elif chosen["source"].startswith("rule-stocks"):
        note = tested + f"A simple plan did best: stocks at 110 minus your age, {chosen['name'].split(', ', 1)[1]}. It {best}."
    else:
        note = tested + f"A simple plan did best: stocks at 110 minus your age. It {best}."
    if low:
        note += " " + LOW_NOTE
    return {"used": used, "note": note, "candidates_tested": scored, "chosen": chosen, "chosen_strategy": strat,
            "low_confidence": low, "low_confidence_reasons": reasons, "mean_distance": round(mean_d, 2),
            "distance_p95": p95, "neighbors": [nb["id"] for nb, _ in nbs]}


def check(profile: dict) -> dict:
    """Kept for callers that only need the note (no simulation inputs)."""
    return {"used": False, "note": "Similar households were not tested for this request.", "candidates_tested": [], "chosen": None}
