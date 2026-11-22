from pathlib import Path
root = Path(__file__).resolve().parents[3]
f = root / "app/agents/longevity.py"
s = f.read_text(encoding="utf-8")
rep = [
('        r["years_in_retirement"] = max(0, r["horizon_age"] - max(ra, age))\n',
 '        r["years_in_retirement"] = max(0, r["horizon_age"] - max(ra, age))\n'
 '        from .adviser import horizon_text\n'
 '        r["horizon_text"] = horizon_text(p, r)\n'),
('        return f"Planning horizon: age {r[\'horizon_age\']}."',
 '        return f"Planning horizon: {r.get(\'horizon_text\') or \'age \' + str(r[\'horizon_age\'])}."'),
('        return (f"Plan for your money to last to age {r[\'horizon_age\']}.",',
 '        reach = "one of you reaches" if who == "one of you" else "you reach"\n'
 '        return (f"Plan for your money to last {r.get(\'horizon_text\') or \'to age \' + str(r[\'horizon_age\'])}.",'),
('                 f"The chance that {who} reaches 90 is about',
 '                 f"The chance that {reach} 90 is about'),
('"that anyone in the household is still alive.")',
 '"that anyone in the household is still alive. When your partner is much younger and the horizon would pass 100 for you, "\n'
 '                    "say it as your partner\'s age (partner_age_at_horizon), never as your own age past 100.")'),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
g = root / "app/pipeline.py"
s = g.read_text(encoding="utf-8")
rep = [
('        out.append(("family", f"{len(moments)} family moments to show, such as: {moments[0]}"))',
 '        out.append(("family", f"{len(moments)} family moment{\'s\' if len(moments) != 1 else \'\'} to show, such as: {moments[0]}"))'),
('    out = [("longevity", f"Plan to age {lon[\'horizon_age\']}.")]',
 '    out = [("longevity", f"Plan {lon.get(\'horizon_text\') or \'to age \' + str(lon[\'horizon_age\'])}.")]'),
]
for a, b in rep:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
g.write_text(s, encoding="utf-8")
print("ok")
