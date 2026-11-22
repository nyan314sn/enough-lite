from pathlib import Path
L = Path(__file__).resolve().parents[3]
def sub(rel, old, new):
    f = L / rel
    s = f.read_text(encoding="utf-8")
    assert s.count(old) == 1, (rel, old[:50])
    f.write_text(s.replace(old, new), encoding="utf-8")
sub("app/agents/adviser.py", '''    if (LITTLE_ROOM.search(wants) and not wants_thin(m, basics)) or (FALLS_SHORT.search(wants) and v != "falls_short"):
        wants = t.wants_line
    wishes = out.wishes_line
    if FALLS_SHORT.search(wishes) and v in ("works", "close"):
        wishes = t.wishes_line''', '''    if ((LITTLE_ROOM.search(wants) or ABOUT_BASICS.search(wants)) and not wants_thin(m, basics)) or \
            (FALLS_SHORT.search(wants) and v != "falls_short"):
        wants = t.wants_line
    wishes = out.wishes_line
    # the wishes line says what the verdict says, without contradicting itself: code-built unless the plan works and
    # the model's line names neither a shortfall nor a goal above what lasts
    if v != "works" or FALLS_SHORT.search(wishes) or re.search(r"\babove what|\bbelow what|\bnot safe|\bshort\b", wishes, re.I):
        wishes = t.wishes_line''')
sub("app/agents/adviser.py", '''FALLS_SHORT = re.compile(r"falls? short|fell short|does not work|doesn't work", re.I)''',
    '''FALLS_SHORT = re.compile(r"falls? short|fell short|does not work|doesn't work", re.I)
ABOUT_BASICS = re.compile(r"\babout (?:the|your) basics\b", re.I)''')
sub("app/agents/family.py", '''    d = c["debts"]
    if d["total_balance"] and d["free_index"] is not None:
        out.append(f"You owe ${d['total_balance']:,.0f}; your payments of ${d['payment_per_year']:,.0f} a year end in {costs.this_year() + d['free_index'] + 1}.")
''', '''    # debts are not family moments: they show in the costs timeline ("Debts paid off ...") and the actions
''')
print("ok")
