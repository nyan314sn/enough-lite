from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 45, an accountant in Illinois, married, my wife is 43. We own our home with a mortgage. Retire at 62.")
    for a in ["About $50k","That's about right","Not working","Not sure, estimate it"]:
        pg.locator(".quick .chip", has_text=a).first.click(); pg.wait_for_selector(".typing", state="detached", timeout=60000); pg.wait_for_timeout(400)
    log("REPLY:", transcript(pg)[-1])
    pg.locator("aside").get_by_text("Home & debts", exact=False).first.click(); pg.wait_for_timeout(500)
    t = pg.locator("aside").first.inner_text().replace("\n"," | "); i=t.find("Home & debts"); log("HOME:", t[i:i+500])
    shot(pg,"mortchip",full=False)
    # then build and see plan note
    for _ in range(8):
        if can_build(pg): break
        chips = pg.locator(".quick .chip").all_inner_texts(); say(pg, chips[0] if chips else "skip")
    build(pg); a = pg.locator("details", has=pg.locator("summary", has_text=re.compile("^Assumptions"))).first
    a.locator("summary").first.click(); log("ASSUMP:", a.inner_text()[:1800])
    b.close()
