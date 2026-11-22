"""Independent recompute (own code; reads only the app data files). Round 2, audit A."""
import json, math
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
DATA = HERE.parents[2] / "app" / "data"
TR = json.load(open(DATA / "tax_rules.json", encoding="utf-8"))
STJ = json.load(open(DATA / "state_tax.json", encoding="utf-8"))
ST = STJ["states"]; SS_STATES = set(STJ["taxes_social_security"]["states"])
SSD = json.load(open(DATA / "social_security.json", encoding="utf-8"))
CTC = TR["child_tax_credit"]


def fed(ordinary, filing, n65=0, gains=0.0):
    ded = TR["standard_deduction"][filing] + n65 * (1700 if filing == "married_joint" else 2100)
    ti = max(0, ordinary - ded); br = TR["ordinary_brackets"][filing]; tax = 0.0
    for i, b in enumerate(br):
        hi = br[i + 1]["threshold"] if i + 1 < len(br) else 1e18
        if ti > b["threshold"]:
            tax += (min(ti, hi) - b["threshold"]) * b["rate"]
    if gains:
        lt = TR["long_term_capital_gains"][filing]
        g0 = min(gains, max(0, lt["zero_rate_max"] - ti))
        g15 = min(gains - g0, max(0, lt["fifteen_rate_max"] - max(ti, lt["zero_rate_max"])))
        tax += .15 * g15 + .20 * (gains - g0 - g15)
    return tax


def strate(state, gross, filing):
    s = ST.get((state or "").upper())
    if not s or gross <= 0:
        return 0.0
    grid = s["effective_rate_by_gross"].get(filing) or s["effective_rate_by_gross"]["single"]
    pts = sorted((float(k), v) for k, v in grid.items()); xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    if gross <= xs[0]:
        return ys[0] * gross / xs[0]
    return float(np.interp(gross, xs, ys))


def ctc(kids, tax_before, agi, earned, filing):
    if kids <= 0:
        return 0.0
    start = CTC["phaseout_start"]["married_joint" if filing == "married_joint" else "other"]
    full = kids * CTC["per_child_under_17"]
    over = max(0, agi - start)
    full = max(0, full - CTC["phaseout_per_1000"] * math.ceil(over / 1000))
    used = min(full, tax_before)
    refund = min(full - used, min(kids * CTC["refundable_max_per_child"], CTC["refundable_rate"] * max(0, earned - CTC["refundable_earned_income_floor"])))
    return used + refund


def work_tax(pay, ppay, state, married, kids, pretax, addl_medicare=False):
    filing = "married_joint" if married else ("head_of_household" if kids > 0 else "single")
    g = pay + ppay; ti = g - min(pretax, g)
    f0 = fed(ti, filing); f = f0 - ctc(kids, f0, ti, g, filing)
    fica = min(pay, 192300) * .062 + min(ppay, 192300) * .062 + g * .0145
    if addl_medicare:
        thr = 250000 if married else 200000
        fica += 0.009 * max(0, g - thr)
    st = strate(state, ti, "married_joint" if married else "single") * ti
    return dict(fed=f, state=st, fica=fica, filing=filing)


def pia_year(pay, years):
    a = min(pay, SSD["wage_base"]) / 12 * max(0, min(35, years)) / 35
    b1, b2 = SSD["bend_points_monthly"]
    return 12 * (.9 * min(a, b1) + .32 * max(0, min(a, b2) - b1) + .15 * max(0, a - b2))


def cf(c):
    c = max(62, min(70, c))
    if c < 67:
        m = (67 - c) * 12
        return 1 - (min(36, m) * 5 / 900 + max(0, m - 36) * 5 / 1200)
    return 1 + .08 * (c - 67)


def sf(c):
    c = max(62, min(70, c))
    if c >= 67:
        return 1.0
    m = (67 - c) * 12
    return 1 - (min(36, m) * 25 / 3600 + max(0, m - 36) * 5 / 1200)


def default_claim(retire):
    return 67 if retire < 67 else min(70, retire)


def ss_people(p):
    """p: completed profile dict (model_dump). People list from my own reading of the rules (estimated SS only)."""
    age = p["age"]; couple = bool(p.get("has_partner") and p.get("partner_age"))
    pay = p.get("pay_per_year") or 0
    ppay = p.get("partner_pay_per_year") or 0
    ret = p["retire_age"]; pret = p.get("partner_retire_age") or ret
    if not pay:
        pay = 0 if (couple and ppay > 0) else 50980.0
    pia_you = pia_year(pay, ret - 22) if pay else 0.0
    claim_you = max(62, min(70, p["claim_age"])) if p.get("claim_age") is not None else default_claim(ret)
    ppl = [dict(who="you", age=age, pia=pia_you, sp=0.0, claim=claim_you, fixed=age >= claim_you, chosen=p.get("claim_age") is not None)]
    if couple:
        pia_p = pia_year(ppay, pret - 22) if ppay else 0.0
        if p.get("partner_claim_age") is not None:
            cp = max(62, min(70, p["partner_claim_age"]))
        elif p.get("claim_age") is not None:
            cp = max(62, min(70, p["claim_age"]))
        else:
            cp = default_claim(pret)
        ppl[0]["sp"] = .5 * pia_p
        ppl.append(dict(who="partner", age=p["partner_age"], pia=pia_p, sp=.5 * pia_you, claim=cp, fixed=p["partner_age"] >= cp,
                        chosen=p.get("partner_claim_age") is not None or p.get("claim_age") is not None))
    return ppl


def amounts(x, c):
    if x.get("amount") is not None and x["fixed"]:
        return x["amount"], 0.0
    return x["pia"] * cf(c), max(0, x["sp"] - x["pia"]) * sf(c)


def schedule(ppl, n, strat_claim=None, death=None):
    claims = []
    for x in ppl:
        if x["fixed"] or x["chosen"] or strat_claim is None:
            claims.append(x["claim"])
        else:
            claims.append(max(62, min(70, max(strat_claim, x["age"]))))
    starts = [0 if x["fixed"] else max(0, c - x["age"]) for x, c in zip(ppl, claims)]
    am = [amounts(x, c) for x, c in zip(ppl, claims)]
    each = []
    for i, x in enumerate(ppl):
        o = starts[1 - i] if len(ppl) == 2 else 0
        own, top = am[i]
        each.append([(own if t >= starts[i] else 0) + (top if (top and t >= max(starts[i], o)) else 0) for t in range(n)])
    tot = [sum(e[t] for e in each) for t in range(n)]
    if death is not None and len(ppl) == 2:
        for t in range(max(0, death), n):
            tot[t] = max(each[0][t], each[1][t])
    return np.array(tot), claims


def ret_rate(spending, ss, savings, state, married, n65, other_income=0.0):
    """My own gross-up: share of a gross withdrawal that goes to tax, by fixed point. Also SS tax rate."""
    filing = "married_joint" if married else "single"
    need = max(0, spending - ss - other_income)
    tot = sum(savings.get(k, 0) for k in ("pretax", "roth", "taxable", "cash")) or 1.0
    tshare = (savings.get("taxable", 0) + savings.get("cash", 0)) / tot; pshare = savings.get("pretax", 0) / tot
    base = .85 * ss; ssst = base if (state or "").upper() in SS_STATES else 0.0

    def T(ordi, gains=0.0):
        sti = ordi - base + ssst + gains
        return fed(ordi, filing, n65, gains) + strate(state, sti, filing) * sti
    below = base + other_income
    ref = max(need, .25 * spending, 1000.0)
    W = ref
    for _ in range(200):
        tw = max(0.0, T(below + W * pshare, W * tshare * .5) - T(below))
        Wn = ref + tw
        if abs(Wn - W) < .01:
            W = Wn
            break
        W = Wn
    rate = min(.5, (W - ref) / W)
    return rate, (T(base) / ss if ss > 0 else 0.0)


def sim(inp, ss_gross_by_year, stock_path=None, paths=20000, seed=7, ss_tax_rate=0.0, survivor_spend=None, death=None, target=.9):
    """Own simulation. survivor_spend: share of spending after the first death (None = unchanged)."""
    age, ra, hor = inp["age"], inp["retire_age"], inp["horizon_age"]; n = hor - age

    def pad(xs):
        a = np.zeros(n); k = min(n, len(xs)); a[:k] = xs[:k]; return a
    extra, save, inc = pad(inp["extra_by_year"]), pad(inp["save_by_year"]), pad(inp["income_by_year"])
    lump = pad(inp["lump_by_year"])
    txa = np.full(n, inp["tax_rate"]); k = min(n, len(inp["tax_rate_by_year"])); txa[:k] = inp["tax_rate_by_year"][:k]
    ssn = np.zeros(n); k = min(n, len(ss_gross_by_year)); ssn[:k] = np.array(ss_gross_by_year[:k]) * (1 - ss_tax_rate)
    if 0 < k < n:
        ssn[k:] = ss_gross_by_year[k - 1] * (1 - ss_tax_rate)
    cap = {"careful": .5, "balanced": .75, "growth": 1.0}[inp["risk"]]
    rng = np.random.default_rng(seed)
    z1 = rng.standard_normal((paths, n)); z2 = rng.standard_normal((paths, n))
    rs = .05 + .17 * z1; rb = .018 + .06 * (.1 * z1 + math.sqrt(.99) * z2)
    ws = np.array(stock_path[:n]) if stock_path else np.array([min(max((110 - (age + t)) / 100, .2), cap) for t in range(n)])
    r = np.maximum(-.95, ws * rs + (1 - ws) * rb)

    def ok(sp):
        w = np.full(paths, float(inp["savings"])); alive = np.ones(paths, bool)
        for t in range(n):
            a = age + t
            if lump[t]:
                w = w + lump[t]
            if a < ra:
                w = np.maximum(w - extra[t] + inc[t], 0) * (1 + r[:, t]) + save[t]
            else:
                s = sp * (survivor_spend if (survivor_spend and death is not None and t >= death) else 1.0)
                need = s + extra[t] - inc[t] - ssn[t]
                w = w - max(0, need) / max(.05, 1 - txa[t]) + max(0, -need)
                alive &= w >= 0; w = np.where(alive, np.maximum(w, 0) * (1 + r[:, t]), 0)
        if inp.get("legacy"):
            alive &= w >= inp["legacy"]
        return alive.mean()
    lo, hi = 0.0, 2e6
    for _ in range(26):
        mid = (lo + hi) / 2
        if ok(mid) >= target:
            lo = mid
        else:
            hi = mid
    return lo, ok
