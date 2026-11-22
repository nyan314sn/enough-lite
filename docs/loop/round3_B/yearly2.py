from lib import *
log = lambda *a: print(*a, flush=True)
def panel(pg): return pg.locator("aside").first.inner_text().replace("\n"," | ")
def row(pg, label):
    t = panel(pg); i = t.find(label); return t[i:i+330]
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 40, a teacher in Ohio, married, wife is 38. We make $120,000 together, have $200,000 saved and spend $6,000 a month. Retire at 65.")
    for a in ["That's about right","Not working","I rent","No other debts","No children and no pets","That's about right"]:
        if can_build(pg): break
        say(pg,a)
    log("CHIPS", pg.locator(".quick .chip").all_inner_texts(), "| last:", transcript(pg)[-1][-160:])
    log("BEFORE savings:", row(pg,"Savings")); log("BEFORE yearly:", row(pg,"Yearly saving"))
    hb = pg.locator("aside").get_by_text("Saving", exact=True)
    log("hdrs", hb.count())
    if pg.get_by_role("button", name=re.compile("Change Yearly saving")).count()==0: hb.first.click(); pg.wait_for_timeout(400)
    log("BEFORE savings:", row(pg,"Savings")); log("BEFORE yearly:", row(pg,"Yearly saving"))
    pg.get_by_role("button", name=re.compile("Change Yearly saving")).first.click(); pg.wait_for_timeout(4000)
    shot(pg,"yearly_editor2",full=False)
    log("last:", transcript(pg)[-2:], pg.locator(".quick .chip").all_inner_texts())
    say(pg, "$30,000 a year")
    log("AFTER bot:", transcript(pg)[-1][-400:], pg.locator(".quick .chip").all_inner_texts())
    log("AFTER savings:", row(pg,"Savings")); log("AFTER yearly:", row(pg,"Yearly saving"))
    shot(pg,"yearly_after2",full=False)
    b.close()
