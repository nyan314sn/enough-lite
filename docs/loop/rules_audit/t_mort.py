from tour import *

def full_bot(pg):
    return transcript(pg)[-1]

def home_rows(pg):
    g = pg.locator("button", has_text=re.compile("^Home & debts"))
    if g.count() and g.first.get_attribute("aria-expanded") == "false":
        g.first.click(); pg.wait_for_timeout(500)
    t = panel(pg)
    i = t.find("Home & debts")
    return t[i:i+700]

with sync_playwright() as p:
    b, pg = newctx(p)
    say(pg, "I am 40, a plumber in Ohio. My wife is 38 and we have a mortgage.")
    for _ in range(8):
        last = last_bot(pg)
        if re.search(r"left on the mortgage", last): break
        cs = chips(pg)
        pick = [c for c in cs if re.search(r"about \$50k|about right|not working|\$4,000", c, re.I)]
        if pick: click_chip(pg, pick[0])
        else: say(pg, "skip")
    P("MORTGAGE Q:", full_bot(pg), chips(pg))
    click_chip(pg, "Not sure, estimate it")
    P("FULL REPLY after 'Not sure, estimate it':\n", full_bot(pg))
    P("HOME ROWS:", home_rows(pg))
    shot(pg, "mort_chip", full=False)
    # also Estimate it for me, Retired, Student loans, Car loan, Credit card chips
    for _ in range(6):
        cs = chips(pg); P("chips now:", cs, "|", last_bot(pg)[-160:])
        pick = [c for c in cs if re.search(r"Student loans|Car loan|Credit card|Retired|Estimate it for me|Type an amount|Use typical|typical for", c, re.I) and not re.search(r"Build my plan", c)]
        if not pick:
            nxt = [c for c in cs if not re.search(r"Build my plan", c)]
            if not nxt: break
            pick = [nxt[0]]
        click_chip(pg, pick[0]); P("CLICKED", pick[0], "->", full_bot(pg)[-420:])
        if can_build(pg): break
    P("PANEL:", panel(pg)[:3000])
    b.close()
