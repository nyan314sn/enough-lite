from hdr import *
FIRSTS = {"old_chipper": "I am 40, a plumber in Ohio. My wife is 38 and we have a mortgage.",
          "new_nurse": "I'm 33, a nurse in Texas, married to Sam who is 35 and an accountant. We rent and have a baby on the way."}
def groups(pg):
    out = {}
    for s in ("Saving", "Home & debts", "Pensions & income", "Insurance", "Goals", "Health", "Costs", "Work & pay", "Household"):
        el = pg.locator(f'[data-section="{s}"]').first
        if el.count(): out[s] = el.inner_text().replace("\n", " | ")[:330]
    return out
with sync_playwright() as p:
    for name, first in FIRSTS.items():
        b, pg = newctx(p, W, H)
        P(f"===== {name}")
        say(pg, first); P("FIRST:", last_bot(pg)[:600])
        clicked = set()
        for i in range(30):
            if can_build(pg): break
            cs = chips(pg)
            P(f"[{i}] Q: {last_bot(pg)[-170:]!r} CHIPS={cs}")
            new = [c for c in cs if c not in clicked and not re.search(r"^Build my plan", c)]
            # prefer estimate-type chips
            est = [c for c in new if re.search(r"estimate|typical|not sure|don't know", c, re.I)]
            if est: c = est[0]
            elif new: c = new[0]
            else:
                c = "I don't know"
            P("   ->", c)
            if c in cs: clicked.add(c); click_chip(pg, c)
            else: say(pg, c)
            P("   BOT:", last_bot(pg)[:420])
        P("READY", can_build(pg))
        for k, v in groups(pg).items(): P("GROUP", k, "::", v)
        # R1 approve: pencil on an estimate -> approve becomes you said?
        shot(pg, f"r1_{name}_{W}", full=False)
        P("errors", pg.errors)
        b.close()
