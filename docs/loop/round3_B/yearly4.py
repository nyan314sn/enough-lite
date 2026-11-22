from lib import *
log = lambda *a: print(*a, flush=True)
def panel(pg): return pg.locator("aside").first.inner_text().replace("\n"," | ")
def row(pg, label):
    t = panel(pg); i = t.find(label); return t[i:i+330]
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 40, a teacher in Ohio, married, wife is 38. We make $120,000 together, have $200,000 saved and spend $6,000 a month. Retire at 65.")
    for a in ["That's about right","Not working","I rent","No other debts","No children and no pets"]+["CHIP"]*7:
        if "Add saving" in pg.locator(".quick .chip").all_inner_texts(): break
        if a=="CHIP": a = pg.locator(".quick .chip").first.inner_text()
        say(pg,a)
    log("CHIPS", pg.locator(".quick .chip").all_inner_texts(), "| last:", transcript(pg)[-1][-160:])
    pg.locator("aside").get_by_text("Saving", exact=True).first.click(); pg.wait_for_timeout(400)
    log("BEFORE savings:", row(pg,"Savings"))
    pg.get_by_role("button", name=re.compile("Change Yearly saving")).first.click(); pg.wait_for_timeout(2500)
    shot(pg,"yearly_editor4",full=False)
    log("last:", transcript(pg)[-2:], pg.locator(".quick .chip").all_inner_texts())
    for a in ["CLICKCHIP","12000"]:
        if a=="CLICKCHIP": pg.locator(".quick .chip", has_text="$10,000 a year").click(); pg.wait_for_timeout(500); pg.wait_for_selector(".typing", state="detached", timeout=60000); pg.wait_for_timeout(500)
        else: say(pg, a)
        log("USER:", a, "\nBOT:", transcript(pg)[-1][-420:], pg.locator(".quick .chip").all_inner_texts())
        log("AFTER:", row(pg,"Savings"))
    shot(pg,"yearly_after4",full=False)
    b.close()
