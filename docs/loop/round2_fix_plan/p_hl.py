from pathlib import Path
F = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = F.read_text(encoding="utf-8")
def sub(old, new):
    global s
    assert s.count(old) == 1, old[:50]
    s = s.replace(old, new)
sub('''    return f" That is less than your Social Security of {money(ss)} a year because of {lst}."''',
    '''    # when the plan starts it at another age than your answers, say so, so the figure matches the one in your answers' basis
    return f" That is less than your Social Security of {money(ss)} a year{m.get('ss_when') or ''} because of {lst}."''')
sub('''        m0["starting_points"] = await starting_points(ctx)
''', '''        m0["starting_points"] = await starting_points(ctx)
    b = ss_basis(ctx.profile, m0)
    m0["ss_when"] = "" if b["same"] or b["claim_age"] is None else " " + _when(b["claim_age"], b["partner_claim_age"]) + " in this plan"
''')
F.write_text(s, encoding="utf-8")
print("ok")
