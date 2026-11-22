"""Build eval/cases.jsonl (v2): ~300 stratified households in the full lite profile shape, plus 30 x 6 perturbed variants.

Source: output/synth/personas.jsonl.gz (made by scripts/synth_users.py generate()).
Each case: {id, bench_id, kind, base_id, group, label, stratum, bench, profile, additions, synthetic}
  kind: base
        savings_up    +20% savings                                  (wants must not fall)
        retire_later  retire 2 years later, capped at 70            (wants must not fall)
        debt_add      add a $30k 7% debt                            (wants should fall)
        pension_add   add a $24k a year pension from 65             (wants should rise)
        match_full    contribute up to the full employer match      (wants should rise)
        legacy_add    add a $200k legacy goal                       (wants should fall)

Every persona field the new schema holds is mapped: sex, health, partner retire age, debts (with rates and payments), pensions
(Pension events, owned income annuities), saving now (contributions, match, other), life cover owned, legacy, college type per
child, spending now with a split, emergency fund. The persona set has no big costs, parents' help, part-time work or inheritance,
so a seeded share of cases gets them; each is named in "additions" and "synthetic" (the benchmark reports those cases apart,
since the optimizer never saw those inputs). The 2025-shape cases are kept in cases_v1.jsonl.

Run:  python eval\\make_cases.py [--n 300] [--direction 30] [--seed 409]
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import random
import re
import sys
from collections import defaultdict
from itertools import zip_longest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BENCH_FULL, BENCH_TREE, CASES_PATH, PERSONAS, ROOT  # noqa: E402

RISK = {"conservative": "careful", "moderate": "balanced", "aggressive": "growth"}
KIND_MAP = {"traditional_401k": "pretax", "traditional_ira": "pretax", "hsa": "pretax",
            "roth_ira": "roth", "taxable": "taxable", "checking_savings": "cash"}
HEALTH_MAP = {"preferred": "excellent", "standard": "good", "smoker": "fair", "poor": "poor"}
DEBT_KIND = {"auto": "car", "credit_card": "credit_card", "student": "student", "personal": "other", "heloc": "other"}
BUDGET_CAT = {"housing": "housing", "utilities": "housing", "food": "food", "transport": "transport", "health": "health",
              "children": "childcare"}
RETIREMENT_ACCTS = ("traditional_401k", "traditional_ira", "roth_ira", "hsa")
DIRECTION_KINDS = ["savings_up", "retire_later", "debt_add", "pension_add", "match_full", "legacy_add"]


def load_personas() -> list[dict]:
    if PERSONAS.exists():
        with gzip.open(PERSONAS, "rt", encoding="utf-8") as f:
            return [json.loads(x) for x in f if x.strip()]
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT))
    import synth_users  # type: ignore
    return synth_users.generate()


def _r(x, step=10.0):
    return round(float(x) / step) * step


def _five(x):
    return round(float(x) / 5) * 5


def health_from_habits(h: dict | None) -> str | None:
    if not h or h.get("smoking") == "prefer_not_to_say":
        return None
    if h.get("smoking") == "current" or h.get("conditions"):
        return "fair"
    if h.get("bmi_class") == "obese" and h.get("activity") == "low":
        return "fair"
    if h.get("activity") == "high" and h.get("bmi_class") == "normal":
        return "excellent"
    return "good"


def convert(p: dict, rng: random.Random, seed: int = 409) -> tuple[dict, list[str], list[str]]:
    pr = p["profile"]
    partner = pr.get("partner")
    adds: list[str] = []
    synth: list[str] = []
    prng = random.Random(f"{seed}-{p['id']}")     # per-persona stream for the synthetic additions
    sav = {"pretax": 0.0, "roth": 0.0, "taxable": 0.0, "cash": 0.0}
    accts = list(pr.get("account_list") or []) + list((partner or {}).get("account_list") or [])
    if accts:
        for a in accts:
            k = KIND_MAP.get(a.get("type"))
            if k:
                sav[k] += float(a.get("balance") or 0)
    else:
        for src in (pr.get("accounts") or {}, (partner or {}).get("accounts") or {}):
            sav["taxable"] += float(src.get("taxable") or 0)
            sav["pretax"] += float(src.get("traditional") or 0)
            sav["roth"] += float(src.get("roth") or 0)
    sav = {k: _r(v, 100) for k, v in sav.items()}

    mort = [d for d in (pr.get("debt_list") or []) if d.get("kind") == "mortgage"]
    owns = pr.get("housing_tenure") == "own"
    rent = 0.0
    if not owns:
        for e in pr.get("expenses") or []:
            if e.get("key") in ("housing", "rent") or (e.get("category") == "housing" and not str(e.get("key", "")).startswith("gen:")):
                rent += float(e.get("monthly_amount") or 0)
    home = {"owns": owns, "value": _r(pr.get("home_value") or 0, 1000) if owns else 0,
            "mortgage_balance": _r(sum(d["balance"] for d in mort), 100),
            "mortgage_payment": _r(sum(d["min_payment"] for d in mort), 5),
            "rent": _r(rent, 5)}
    if mort and mort[0].get("annual_rate"):
        home["mortgage_rate"] = round(float(mort[0]["annual_rate"]), 4)

    kids: dict[int, dict] = {}
    pets: dict[str, int] = defaultdict(int)
    for e in pr.get("events") or []:
        m = re.match(r"Child (\d+) \(age (\d+)\)(: college(?: \(([^)]*)\))?)?", e.get("label", ""))
        if m:
            k = kids.setdefault(int(m.group(1)), {"age": int(m.group(2)), "college": False, "college_type": "none"})
            if m.group(3):
                k["college"] = True
                k["college_type"] = "private" if "private" in (m.group(4) or "").lower() else "public"
        m = re.match(r"(Dog|Cat) \(age \d+\): yearly care", e.get("label", ""))
        if m:
            pets[m.group(1).lower()] += 1
    children = [kids[k] for k in sorted(kids)]
    pet_list = [{"kind": k, "count": c} for k, c in pets.items() if c]

    if (pr.get("dependents") or 0) > 0 and not children and pr["age"] < 62:
        cl = rng.random() < 0.6
        children = [{"age": rng.randint(3, 15), "college": cl, "college_type": "public" if cl else "none"}]
        adds.append("child added: dependants but no child cost lines")
    if children and not pet_list and rng.random() < 0.35:
        pet_list = [{"kind": rng.choice(["dog", "cat"]), "count": 1}]
        adds.append("pet added to a household with children")

    ss = float(pr.get("social_security_benefit") or 0) + float((partner or {}).get("social_security_benefit") or 0)
    age = int(pr["age"])
    pay = _r(pr.get("annual_income") or 0, 100)
    ppay = _r(partner.get("annual_income") or 0, 100) if partner else None
    retire_age = max(int(pr.get("retire_age") or age), age)
    profile = {
        "age": age,
        "partner_age": int(partner["age"]) if partner else None,
        "has_partner": bool(partner),
        "state": pr.get("state") or "TX",
        "retire_age": retire_age,
        "pay_per_year": pay,
        "partner_pay_per_year": ppay,
        "savings": sav,
        "savings_known": True,
        "home": home,
        "children": children,
        "pets": pet_list,
        "spending_per_year": _r(pr.get("desired_spending") or 0, 100) or None,
        "social_security_per_year": _r(ss, 100) if ss else None,
        "risk": RISK.get(pr.get("risk_profile"), "balanced"),
        "sex": pr.get("sex") if pr.get("sex") in ("male", "female") else None,
    }
    # ---- people: health, partner sex, health and retire age
    hl = HEALTH_MAP.get(pr.get("health")) or health_from_habits(pr.get("health_habits"))
    if hl:
        profile["health"] = hl
    if partner:
        if partner.get("sex") in ("male", "female"):
            profile["partner_sex"] = partner["sex"]
        ph = health_from_habits(partner.get("health") if isinstance(partner.get("health"), dict) else None)
        if ph:
            profile["partner_health"] = ph
        if partner.get("retire_age"):
            profile["partner_retire_age"] = max(int(partner["retire_age"]), int(partner["age"]))

    # ---- debts (the mortgage is in home)
    debts = []
    for d in pr.get("debt_list") or []:
        if d.get("kind") == "mortgage" or not d.get("balance"):
            continue
        debts.append({"kind": DEBT_KIND.get(d.get("kind"), "other"), "balance": _r(d["balance"], 100),
                      "rate": round(float(d["annual_rate"]), 4) if d.get("annual_rate") else None,
                      "monthly_payment": _five(d["min_payment"]) if d.get("min_payment") else None})
    debts = [d for d in debts if d["balance"] > 0]
    if debts:
        profile["debts"] = debts

    # ---- pensions: Pension events (yours), partner pensions, owned income annuities
    pens = []
    for e in pr.get("events") or []:
        if e.get("label") == "Pension" and e.get("amount_per_year", 0) > 0:
            pens.append({"who": "you", "per_year": _r(e["amount_per_year"], 100), "start_age": int(e["start_age"]),
                         "inflation_adjusted": False, "survivor_share": 0.5})
    for e in (partner or {}).get("pensions") or []:
        pens.append({"who": "partner", "per_year": _r(e.get("amount_per_year") or e.get("per_year") or 0, 100),
                     "start_age": int(e.get("start_age") or 65), "inflation_adjusted": False, "survivor_share": 0.5})
    for a in pr.get("owned_products") or []:
        if a.get("kind") in ("spia", "dia") and a.get("guaranteed_income"):
            pens.append({"who": "you", "per_year": _r(a["guaranteed_income"], 100), "start_age": int(a.get("start_age") or 65),
                         "inflation_adjusted": False, "survivor_share": 0.5})
            adds.append("owned income annuity entered as a pension")
    pens = [x for x in pens if x["per_year"] > 0]
    if pens:
        profile["pensions"] = pens

    # ---- saving now: contributions, match, other
    sv: dict = {}
    c_you = c_pt = other = 0.0
    match_rate = match_cap = None
    for a in pr.get("account_list") or []:
        amt = float(a.get("annual_contribution") or 0)
        if a.get("type") in RETIREMENT_ACCTS:
            c_you += amt
            if a.get("employer_match_rate") and pay:
                match_rate, match_cap = float(a["employer_match_rate"]), float(a.get("match_limit_pct") or 0.06)
        else:
            other += amt
    for a in (partner or {}).get("account_list") or []:
        amt = float(a.get("annual_contribution") or 0)
        if a.get("type") in RETIREMENT_ACCTS:
            c_pt += amt
            if a.get("employer_match_rate") and match_rate is None and not pay and ppay:
                match_rate, match_cap = float(a["employer_match_rate"]), float(a.get("match_limit_pct") or 0.06)
        else:
            other += amt
    if pay or ppay:
        sv["contrib_you"] = _r(c_you, 50)
        if partner and ppay:
            sv["contrib_partner"] = _r(c_pt, 50)
        if match_rate is not None:
            sv["match_rate"], sv["match_cap"] = match_rate, match_cap
    if other:
        sv["other_per_month"] = _r(other / 12, 10)
    if sv:
        profile["saving"] = sv

    # ---- insurance owned
    ins: dict = {}
    life = float(pr.get("existing_life_coverage") or 0)
    whole = [a for a in pr.get("owned_products") or [] if a.get("kind") == "whole_life"]
    if whole:
        ins["life_kind"], ins["life_face"] = "whole", _r(sum(a.get("face_amount") or 0 for a in whole) + life, 5000)
    elif life > 0:
        ins["life_kind"], ins["life_face"] = "term", _r(life, 5000)
    else:
        ins["life_kind"] = "none"
    profile["insurance"] = ins

    # ---- goals: legacy from the persona; big costs and parents' help added (the persona set has none)
    goals: dict = {}
    if pr.get("legacy_target"):
        goals["legacy"] = _r(pr["legacy_target"], 10000)
    if age < 70 and prng.random() < 0.18:
        label, amt = prng.choice([("New roof", 20000), ("Car replacement", 35000), ("Wedding", 30000),
                                  ("Kitchen remodel", 45000), ("Family trip", 15000)])
        goals["big_costs"] = [{"label": label, "amount": amt, "year": 2026 + prng.randint(2, 12)}]
        synth.append("big cost")
    if 45 <= age <= 64 and prng.random() < 0.10:
        goals["parents_per_year"] = prng.choice([6000, 12000, 18000])
        goals["parents_years"] = prng.choice([3, 5, 8])
        synth.append("parents' help")
    if goals:
        profile["goals"] = goals

    # ---- part-time work and inheritance (not in the persona set): a seeded share
    if pay and age < retire_age <= 67 and prng.random() < 0.10:
        profile["part_time"] = {"per_year": prng.choice([12000, 20000, 30000]), "until_age": min(75, retire_age + prng.randint(3, 8))}
        synth.append("part-time work")
    if age <= 70 and prng.random() < 0.06:
        profile["inheritance"] = {"amount": prng.choice([50000, 100000, 250000]), "year": 2026 + prng.randint(2, 15),
                                  "count": prng.random() < 0.5}
        synth.append("inheritance")

    # ---- spending now (a split in half the cases) and the emergency fund
    cats: dict[str, float] = defaultdict(float)
    for e in pr.get("expenses") or []:
        cats[BUDGET_CAT.get(e.get("category"), "other")] += float(e.get("monthly_amount") or 0)
    nonmort = sum(float(d.get("min_payment") or 0) for d in pr.get("debt_list") or [] if d.get("kind") != "mortgage")
    if nonmort:
        cats["debt"] += nonmort
    total_m = sum(cats.values())
    if total_m > 0:
        x = prng.random()
        if x < 0.5:
            profile["budget"] = {k: _five(v) for k, v in cats.items() if v > 0}
            profile["spending_now_per_year"] = round(sum(profile["budget"].values()) * 12, -2)
        elif x < 0.85:
            profile["spending_now_per_year"] = _r(total_m * 12, 100)
    if profile.get("spending_now_per_year") and sav["cash"] > 0 and prng.random() < 0.25:
        profile["emergency_months"] = round(min(24, sav["cash"] / (profile["spending_now_per_year"] / 12)) * 2) / 2
    if synth:
        adds.append("synthetic inputs: " + ", ".join(synth))
    return profile, adds, synth


def stratum_of(p: dict, prof: dict, hi_cut: float) -> dict:
    total = sum(prof["savings"].values())
    return {"age_band": p["age_band"], "couple": prof["has_partner"],
            "working": prof["pay_per_year"] > 0 and prof["age"] < prof["retire_age"],
            "savings": "high" if total >= hi_cut else "low"}


def round_robin(items: list[dict], key, n: int, rng: random.Random) -> list[dict]:
    """Take n items, cycling through strata so small strata are all represented."""
    groups: dict = defaultdict(list)
    for it in items:
        groups[key(it)].append(it)
    for g in groups.values():
        rng.shuffle(g)
    order = sorted(groups, key=lambda k: (len(groups[k]), str(k)))
    out = []
    for row in zip_longest(*[groups[k] for k in order]):
        for it in row:
            if it is not None and len(out) < n:
                out.append(it)
        if len(out) >= n:
            break
    return out


# ---------- perturbations: (candidate test, builder)
def match_gap(prof: dict) -> tuple[float, float] | None:
    """(pay, contribution) the app compares for the match, or None when there is no match gap to close."""
    s = prof.get("saving") or {}
    if s.get("match_rate") is None:
        return None
    you_pays = (prof.get("pay_per_year") or 0) > 0
    pay = (prof.get("pay_per_year") or 0) if you_pays else (prof.get("partner_pay_per_year") or 0)
    if pay <= 0 or (you_pays and prof["age"] >= prof["retire_age"]):
        return None
    contrib = s.get("contrib_you" if you_pays else "contrib_partner") or 0
    full = (s.get("match_cap") if s.get("match_cap") is not None else 0.06) * pay
    return (pay, contrib) if contrib < full - 1 else None


def variant(base: dict, kind: str) -> dict | None:
    prof = copy.deepcopy(base)
    if kind == "savings_up":
        prof["savings"] = {k: _r(v * 1.2, 100) for k, v in prof["savings"].items()}
    elif kind == "retire_later":
        if not (prof["pay_per_year"] and prof["age"] < prof["retire_age"] <= 68):
            return None
        prof["retire_age"] = min(70, prof["retire_age"] + 2)
    elif kind == "debt_add":
        prof.setdefault("debts", []).append({"kind": "other", "balance": 30000, "rate": 0.07, "monthly_payment": None})
    elif kind == "pension_add":
        if any(x["who"] == "you" for x in prof.get("pensions") or []):
            return None
        prof.setdefault("pensions", []).append({"who": "you", "per_year": 24000, "start_age": max(65, prof["age"]),
                                                "inflation_adjusted": False, "survivor_share": 0.5})
    elif kind == "match_full":
        g = match_gap(prof)
        if not g:
            return None
        s = prof["saving"]
        key = "contrib_you" if (prof.get("pay_per_year") or 0) > 0 else "contrib_partner"
        s[key] = _r(g[0] * (s.get("match_cap") if s.get("match_cap") is not None else 0.06), 50)
        if s[key] < g[0] * (s.get("match_cap") or 0.06):
            s[key] += 50
    elif kind == "legacy_add":
        if (prof.get("goals") or {}).get("legacy"):
            return None
        prof.setdefault("goals", {})["legacy"] = 200000
    return prof


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--direction", type=int, default=30)
    ap.add_argument("--seed", type=int, default=409)
    ap.add_argument("--out", default=str(CASES_PATH))
    a = ap.parse_args()
    rng = random.Random(a.seed)

    personas = load_personas()
    pool = []
    for p in personas:
        bench = {"full": (BENCH_FULL / f"{p['id']}.json").exists(), "tree": (BENCH_TREE / f"{p['id']}.json").exists()}
        if not (bench["full"] or bench["tree"]):
            continue
        prof, adds, synth = convert(p, rng, a.seed)
        pool.append({"p": p, "profile": prof, "adds": adds, "synth": synth, "bench": bench})
    totals = sorted(sum(c["profile"]["savings"].values()) for c in pool)
    hi_cut = totals[len(totals) // 2] if totals else 0
    for c in pool:
        c["stratum"] = stratum_of(c["p"], c["profile"], hi_cut)
    key = lambda c: tuple(c["stratum"].values())  # noqa: E731
    chosen = round_robin(pool, key, a.n, rng)
    chosen.sort(key=lambda c: c["p"]["id"])

    cases = []
    for c in chosen:
        cases.append({"id": c["p"]["id"], "bench_id": c["p"]["id"], "kind": "base", "base_id": c["p"]["id"],
                      "group": c["p"]["group"], "label": c["p"]["label"], "stratum": c["stratum"],
                      "bench": c["bench"], "additions": c["adds"], "synthetic": c["synth"], "profile": c["profile"]})
    by_id = {c["id"]: c for c in cases}
    for kind in DIRECTION_KINDS:
        cand = []
        for c in chosen:
            if kind == "retire_later" and not c["stratum"]["working"]:
                continue
            if variant(c["profile"], kind) is not None:
                cand.append(c)
        if kind == "retire_later":
            cand = [c for c in cand if c["profile"]["retire_age"] <= 68]
        dsub = round_robin(cand, key, a.direction, rng)
        for c in sorted(dsub, key=lambda c: c["p"]["id"]):
            base = by_id[c["p"]["id"]]
            cases.append({"id": f"{base['id']}__{kind}", "bench_id": base["bench_id"], "kind": kind, "base_id": base["id"],
                          "group": base["group"], "label": base["label"], "stratum": base["stratum"],
                          "bench": base["bench"], "additions": base["additions"], "synthetic": base["synthetic"],
                          "profile": variant(base["profile"], kind)})
    Path(a.out).write_text("\n".join(json.dumps(c) for c in cases) + "\n", encoding="utf-8")
    nb = sum(1 for c in cases if c["kind"] == "base")
    print(f"wrote {len(cases)} cases ({nb} base, {len(cases) - nb} perturbed) to {a.out}")
    print(f"pool with benchmark: {len(pool)} of {len(personas)} personas")
    for k in DIRECTION_KINDS:
        print(f"  {k}: {sum(1 for c in cases if c['kind'] == k)}")
    base = [c for c in cases if c["kind"] == "base"]
    for name, f in (("age band", lambda c: c["stratum"]["age_band"]), ("couple", lambda c: c["stratum"]["couple"]),
                    ("working", lambda c: c["stratum"]["working"]), ("savings", lambda c: c["stratum"]["savings"])):
        cnt: dict = defaultdict(int)
        for c in base:
            cnt[f(c)] += 1
        print(f"  {name}: {dict(sorted(cnt.items(), key=lambda kv: str(kv[0])))}")
    feats = {
        "children": lambda p: bool(p["children"]), "college": lambda p: any(c.get("college") for c in p["children"]),
        "pets": lambda p: bool(p["pets"]), "debts": lambda p: bool(p.get("debts")),
        "debt rate >= 8%": lambda p: any((d.get("rate") or 0) >= 0.08 for d in p.get("debts") or []),
        "mortgage": lambda p: p["home"]["mortgage_balance"] > 0, "pension": lambda p: bool(p.get("pensions")),
        "match given": lambda p: (p.get("saving") or {}).get("match_rate") is not None,
        "match gap": lambda p: match_gap(p) is not None,
        "legacy": lambda p: bool((p.get("goals") or {}).get("legacy")), "big cost": lambda p: bool((p.get("goals") or {}).get("big_costs")),
        "parents' help": lambda p: bool((p.get("goals") or {}).get("parents_per_year")),
        "life cover": lambda p: (p.get("insurance") or {}).get("life_kind") not in (None, "none"),
        "part-time": lambda p: bool(p.get("part_time")), "inheritance": lambda p: bool(p.get("inheritance")),
        "budget split": lambda p: bool(p.get("budget")), "spending now": lambda p: bool(p.get("spending_now_per_year")),
        "emergency months": lambda p: p.get("emergency_months") is not None, "health": lambda p: bool(p.get("health")),
        "partner retire age": lambda p: bool(p.get("partner_retire_age")),
    }
    print("  base cases with each new input:")
    for name, f in feats.items():
        print(f"    {name}: {sum(1 for c in base if f(c['profile']))}")


if __name__ == "__main__":
    main()
