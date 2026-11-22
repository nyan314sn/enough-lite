"""Independent recompute of key figures for the audit households. Own code; only reads the app's DATA FILES (rates, brackets)."""
import json, glob, os, math
import numpy as np
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parents[2] / "app" / "data"
TR = json.load(open(DATA / "tax_rules.json", encoding="utf-8"))
ST = json.load(open(DATA / "state_tax.json", encoding="utf-8"))["states"]

def fed(ordinary, filing, n65=0, gains=0.0):
    ded = TR["standard_deduction"][filing] + n65 * (1700 if filing == "married_joint" else 2100)
    ti = max(0, ordinary - ded)
    br = TR["ordinary_brackets"][filing]
    tax = 0.0
    for i, b in enumerate(br):
        hi = br[i + 1]["threshold"] if i + 1 < len(br) else 1e18
        if ti > b["threshold"]:
            tax += (min(ti, hi) - b["threshold"]) * b["rate"]
    if gains:
        lt = TR["long_term_capital_gains"][filing]
        room0 = max(0, lt["zero_rate_max"] - ti)
        g0 = min(gains, room0)
        room15 = max(0, lt["fifteen_rate_max"] - max(ti, lt["zero_rate_max"]))
        g15 = min(gains - g0, room15)
        tax += 0.15 * g15 + 0.20 * (gains - g0 - g15)
    return tax

def strate(state, gross, filing):
    s = ST.get((state or "").upper())
    if not s or gross <= 0:
        return 0.0
    grid = s["effective_rate_by_gross"].get(filing) or s["effective_rate_by_gross"]["single"]
    pts = sorted((float(k), v) for k, v in grid.items())
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    if gross <= xs[0]:
        return ys[0] * gross / xs[0]
    return float(np.interp(gross, xs, ys))

def working_tax(pay, ppay, state, married):
    filing = "married_joint" if married else "single"
    g = pay + ppay
    f = fed(g, filing)
    s = strate(state, g, filing) * g
    fica = min(pay, 192300) * .062 + min(ppay, 192300) * .062 + g * .0145
    return f, s, fica

def pia_monthly(pay):
    aime = min(pay, 192300) / 12
    return .9 * min(aime, 1340) + .32 * max(0, min(aime, 8077) - 1340) + .15 * max(0, aime - 8077)

def ss_factor(age):
    age = max(62, min(70, age))
    if age < 67:
        m = (67 - age) * 12
        return 1 - (min(36, m) * 5 / 900 + max(0, m - 36) * 5 / 1200)
    return 1 + .08 * (age - 67)

def ss_est(pay, ppay, married, claim):
    own = pia_monthly(pay) * 12
    tot = own * ss_factor(claim)
    if married:
        if ppay:
            tot += pia_monthly(ppay) * 12 * ss_factor(claim)
        else:
            tot += own * 0.5 * ss_factor(claim) if False else own * 0.5
    return tot

def load(f):
    d = json.load(open(f, encoding="utf-8"))
    ev = d["events"]
    plan = [e for e in ev if e.get("type") == "plan"][0]["plan"]
    fin = {e["agent"]: e["finding"] for e in ev if e.get("type") == "agent_done"}
    return d["profile"], plan, fin

# ---- independent simulation (own code, 20000 paths, own seed)
def my_sim(age, ret, hor, w0, save, ss_net, ss_age, spend_path_extra, inc, tax_rate, risk, legacy=0.0, paths=20000, seed=7):
    cap = {"careful": .5, "balanced": .75, "growth": 1.0}[risk]
    n = hor - age
    rng = np.random.default_rng(seed)
    z1 = rng.standard_normal((paths, n)); z2 = rng.standard_normal((paths, n))
    rs = .05 + .17 * z1
    rb = .018 + .06 * (.1 * z1 + math.sqrt(1 - .01) * z2)
    ws = np.array([min(max((110 - (age + t)) / 100, .2), cap) for t in range(n)])
    r = np.maximum(-.95, ws * rs + (1 - ws) * rb)
    def ok(spend):
        w = np.full(paths, float(w0)); alive = np.ones(paths, bool)
        for t in range(n):
            a = age + t
            if a < ret:
                w = np.maximum(w - spend_path_extra[t] + inc[t], 0) * (1 + r[:, t]) + save[t]
            else:
                need = spend + spend_path_extra[t] - inc[t] - (ss_net if a >= ss_age else 0)
                w = w - max(0, need) / (1 - tax_rate) + max(0, -need)
                alive &= w >= 0
                w = np.where(alive, np.maximum(w, 0) * (1 + r[:, t]), 0)
        if legacy: alive &= w >= legacy
        return alive.mean()
    lo, hi = 0.0, 1e6
    for _ in range(25):
        mid = (lo + hi) / 2
        if ok(mid) >= .9: lo = mid
        else: hi = mid
    return lo, ok

def pension_inc(profile, plan, life_exp_default=85):
    return None

if __name__ == "__main__":
    rows = []
    for f in sorted(glob.glob(str(HERE / "plans" / "*.json"))):
        name = os.path.basename(f)[:-5]
        prof, plan, fin = load(f)
        t = fin["tax"]["numbers"]; m = fin["markets"]["numbers"]
        married = bool(prof.get("has_partner"))
        pay = prof.get("pay_per_year", 0) or 0; ppay = prof.get("partner_pay_per_year", 0) or 0
        out = [name]
        if pay + ppay > 0 and prof["retire_age"] > prof["age"]:
            fe, se, fi = working_tax(pay, ppay, prof["state"], married)
            for lab, mine, theirs in (("fed", fe, t["federal_tax"]), ("state", se, t["state_tax"]), ("fica", fi, t["payroll_tax"])):
                flag = " **" if theirs and abs(mine - theirs) / max(theirs, 1) > .05 else ""
                out.append(f"{lab} mine {mine:,.0f} app {theirs:,.0f}{flag}")
        print(" | ".join(out))
