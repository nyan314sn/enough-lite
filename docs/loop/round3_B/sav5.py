from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 40, a teacher in Ohio, married, wife is 38. We make $120,000 together, have $200,000 saved and spend $6,000 a month. Retire at 65.")
    for a in ["That's about right","Not working","I rent","No other debts","No children and no pets"]+["CHIP"]*7:
        if "Add saving" in pg.locator(".quick .chip").all_inner_texts(): break
        if a=="CHIP": a = pg.locator(".quick .chip").first.inner_text()
        say(pg,a)
    say(pg, "Add saving"); log("Q:", transcript(pg)[-1][-250:])
    for a in ["$10,000 a year", "10% of pay"]:
        say(pg, a); log("U:", a, "\nBOT:", transcript(pg)[-1][-300:], pg.locator(".quick .chip").all_inner_texts())
    t = pg.locator("aside").first.inner_text().replace("\n"," | "); i=t.find("Savings"); log(t[i:i+500])
    b.close()
