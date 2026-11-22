from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/tools/costs.py"
s = f.read_text(encoding="utf-8")
rep = [
("""        total.append(round(max(0.0, x)))
        basics.append(round(max(0.0, basics0 - (drop[t] if mort_in_basics else 0.0) + health[t]), -2))""",
"""        b_t = round(max(0.0, basics0 - (drop[t] if mort_in_basics else 0.0) + health[t]), -2)
        if not retired and t > 0:
            x = max(x, b_t)      # spending while at work never shows below the basics (children leaving frees money, not the basics)
        total.append(round(max(0.0, x)))
        basics.append(b_t)"""),
("""        short = round(EMERGENCY_MIN_MONTHS * monthly - held_months * monthly)""",
"""        held = cash if (cash and abs(cash / monthly - held_months) < 0.06) else held_months * monthly   # exact, not from rounded months
        short = round(max(0.0, EMERGENCY_MIN_MONTHS * monthly - held))"""),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
