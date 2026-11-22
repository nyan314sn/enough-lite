from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/tools/neighbors.py"
s = f.read_text(encoding="utf-8")
rep = [
('''GRID_STOCK_SHIFTS = (-0.15, 0.15)    # ... and the rule's stock path 15 points lower and higher (at the default claim)''',
 '''GRID_STOCK_SHIFTS = (-0.30, -0.15, 0.15)   # ... and the rule's stock path shifted, at the default claim and at 70'''),
('''    for d in GRID_STOCK_SHIFTS:
        path = [float(min(cap, max(0.10, x + d))) for x in rule["stock_path"]]
        if path == rule["stock_path"]:
            continue
        word = "more" if d > 0 else "less"
        out.append({**rule, "stock_path": path, "name": f"Rule of thumb, {round(abs(d) * 100)} points {word} in stocks",
                    "source": f"rule-stocks{'+' if d > 0 else '-'}{round(abs(d) * 100)}",
                    "description": f"Stocks at 110 minus your age, {round(abs(d) * 100)} points {word}, no products"})
    return out''',
 '''    seen = set()
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
                        "name": f"Rule of thumb, {pts} points {word} in stocks" + ("" if c is None else f", claiming at {c}"),
                        "source": f"rule-stocks{'+' if d > 0 else '-'}{pts}{tag}",
                        "description": f"Stocks at 110 minus your age, {pts} points {word}" + ("" if c is None else f", claim at {c}") + ", no products"})
    return out'''),
('''TIE_SHARE, TIE_MIN = 0.03, 500.0    # safe spending within this of the best counts as a tie (simulation noise)''',
 '''TIE_SHARE, TIE_MIN = 0.01, 300.0    # safe spending within this of the best counts as a tie (simulation noise)'''),
('''    best = max(c["basics_paid_of_100"] or 0 for c in scored)
    pool = [c for c in scored if (c["basics_paid_of_100"] or 0) >= best - BASICS_GUARD]''',
 '''    best = max(c["basics_paid_of_100"] or 0 for c in scored)
    # a fixed bar, not "near the best", so more pay or savings can only add candidates to the pool and what you can
    # count on never falls: when some candidate pays the basics in 95 of 100, keep those (less the guard); otherwise
    # all, where the most to spend is also the one nearest to paying the basics
    pool = [c for c in scored if (c["basics_paid_of_100"] or 0) >= SAFE_BASICS - BASICS_GUARD] if best >= SAFE_BASICS else list(scored)'''),
('''    """Basics first: keep candidates within BASICS_GUARD points of the best basics paid, then the most to spend.''',
 '''    """Basics first: keep candidates that pay the basics safely, then the most to spend.'''),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
