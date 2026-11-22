"""Patch: starting points that help on the person's numbers, each with a What If text; headline and action 1 wording."""
from pathlib import Path

L = Path(__file__).resolve().parents[3]
F = L / "app/agents/adviser.py"
s = F.read_text(encoding="utf-8")
a = s.index("MATCH_MIN_YEARS = config.MATCH_MIN_YEARS_LEFT")
b = s.index("def allowed_for_adviser")
NEW = (Path(__file__).parent / "sp_new.txt").read_text(encoding="utf-8")
NEW = NEW.replace('''    # one "retire later" is enough: the better of the two
    seen_retire, kept = False, []
    for x in out:
        if x["keys"] == ["retire"]:
            if seen_retire:
                continue
            seen_retire = True
        kept.append(x)''', '''    # one "retire later" is enough: the nearer age when both make the basics safe, else the one that helps more
    rets = [x for x in out if x["keys"] == ["retire"]]
    safe_rets = [x for x in rets if x["makes_basics_safe"]]
    keep_ret = min(safe_rets, key=lambda x: x["title"]) if safe_rets else (rets[0] if rets else None)
    kept = [x for x in out if x["keys"] != ["retire"] or x is keep_ret]''')
s = s[:a] + NEW + s[b:]

old = '''        more = " The starting points below show what would change that." if m.get("starting_points") else ""'''
new = '''        pts = m.get("starting_points") or []
        more = (" The starting points below show what would make the basics safe." if any(x.get("makes_basics_safe") for x in pts) else
                " The starting points below each help, but none we tried makes the basics safe." if pts else "")'''
assert s.count(old) == 1
s = s.replace(old, new)
old = '''        if pts:
            why += " Starting points: " + "; ".join(f"{x['title'].lower()} ({x['result']})" for x in pts) + "."
        else:'''
new = '''        if pts:
            why += " The starting points show what helps on your numbers."
        else:'''
assert s.count(old) == 1
s = s.replace(old, new)
F.write_text(s, encoding="utf-8")
print("ok")
