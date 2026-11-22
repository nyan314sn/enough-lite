from pathlib import Path
F = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = F.read_text(encoding="utf-8")
def sub(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)
sub('''    if not why:
        return ""
    lst = why[0]''', '''    if m.get("extra_costs_in_retirement"):
        why.append("costs the plan pays on top of your spending goal")
    if not why:
        why.append("the margin the plan keeps for bad markets")
    lst = why[0]''')
sub('''    return _headline(m, basics) + ("" if safe < 0.95 * basics else below_ss_note(m))''',
    '''    return _headline(m, basics) + below_ss_note(m)''')
sub('''        if x["key"] in ("match", "disability") and (not working or years_left < MATCH_MIN_YEARS):
            continue''', '''        if x["key"] in ("match", "disability") and (not working or years_left < MATCH_MIN_YEARS):
            continue
        if x["key"] == "match" and lever_impact(x) < MATCH_MIN_DOLLARS:
            continue        # a few dollars of match a year is not worth an action''')
sub('''MATCH_MIN_YEARS = config.MATCH_MIN_YEARS_LEFT
''', '''MATCH_MIN_YEARS = config.MATCH_MIN_YEARS_LEFT
MATCH_MIN_DOLLARS = 500    # a missed match below this a year is not worth an action
CATCH_UP_SHARE = 0.8       # the catch-up action only for someone already saving near the yearly limit
''')
sub('''    if working and years_left >= MATCH_MIN_YEARS and (p.age or 45) >= 50 and lim:''',
    '''    near_limit = bool(lim) and costs.contributions(p)["you"] >= CATCH_UP_SHARE * lim["401k_limit"]
    if working and years_left >= MATCH_MIN_YEARS and (p.age or 45) >= 50 and lim and near_limit:''')
F.write_text(s, encoding="utf-8")
print("ok")
