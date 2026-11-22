from pathlib import Path
root = Path(__file__).resolve().parents[3]
f = root / "app/agents/adviser.py"
s = f.read_text(encoding="utf-8")
rep = [
('''    return _headline(m, basics) + below_ss_note(m)''',
 '''    safe = m.get("safe_spending_per_year") or 0
    return _headline(m, basics) + ("" if safe < 0.95 * basics else below_ss_note(m))'''),
('''        if sv["unspent_pay_per_year"] > 0:
            parts.append(f"{money(sv['unspent_pay_per_year'])} of take-home pay left after your spending, which we assume you save")
        if parts:
            out.append(f"Until you retire you save about {money(sv['per_year'])} a year: " + ", ".join(parts) +
                       ". If that is wrong, change 'Yearly saving' in your answers.")''',
 '''        if sv["unspent_pay_per_year"] > 0:
            parts.append(f"{money(sv['unspent_pay_per_year'])} of take-home pay left after your spending, which we assume you save")
        if sv["unspent_pay_per_year"] < 0:
            out.append(f"Until you retire you save about {money(sv['per_year'])} a year: what your take-home pay leaves after your "
                       "spending now, which is less than the saving assumed. If that is wrong, change 'Yearly saving' or your "
                       "spending now in your answers.")
        elif parts:
            out.append(f"Until you retire you save about {money(sv['per_year'])} a year: " + ", ".join(parts) +
                       ". If that is wrong, change 'Yearly saving' in your answers.")'''),
('''    if working:
        extra = max(1000, round(SAVE_MORE_SHARE * p.household_pay(), -3))
        tries.append(({"saving_other_per_month": round((p.saving.other_per_month or 0) + extra / 12, 2), "_extra_per_year": extra},
                      f"Save ${extra:,.0f} more a year", f"What if I save ${extra:,.0f} more a year"))''',
 '''    if working and (p.spending_now_per_year or 0) > 0:
        # pay you do not spend is saved, so saving more means spending less now
        extra = max(1000, round(SAVE_MORE_SHARE * p.household_pay(), -3))
        extra = min(extra, round(0.5 * p.spending_now_per_year, -3))
        tries.append(({"_spend_now_less": extra}, f"Spend ${extra:,.0f} a year less now and save it", ""))'''),
('''        try:
            newp, notes = pipeline.apply_whatif(p, ch)
            if notes.get("_say"):
                continue''',
 '''        try:
            if "_spend_now_less" in ch:
                newp, notes = p.model_copy(deep=True), {}
                newp.spending_now_per_year = max(0.0, (p.spending_now_per_year or 0) - ch["_spend_now_less"])
                newp.sources["spending_now_per_year"] = "you said"
            else:
                newp, notes = pipeline.apply_whatif(p, ch)
            if notes.get("_say"):
                continue'''),
('''        out.append({"key": GOAL_KEY, "title": "Make your basics safe first", "whatif_text": pts[0]["whatif_text"] if pts else "",''',
 '''        out.append({"key": GOAL_KEY, "title": "Make your basics safe first",
                    "whatif_text": next((x["whatif_text"] for x in pts if x["whatif_text"]), ""),'''),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
g = root / "app/agents/markets.py"
s = g.read_text(encoding="utf-8")
a = ('''"goal lasts, the most the household can spend and still be safe in 90 of 100 scenarios, and which strategy "
                    "was kept. Report the kept strategy's figures only. Say plainly that markets are uncertain.")''')
b = ('''"goal lasts, the most the household can spend and still be safe in 90 of 100 scenarios, and which plan "
                    "was kept, in plain words (a simple plan, or the plan of a similar household). Report the kept plan's figures "
                    "only. Say plainly that markets are uncertain.")''')
assert s.count(a) == 1
g.write_text(s.replace(a, b), encoding="utf-8")
print("ok")
