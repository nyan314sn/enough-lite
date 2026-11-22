from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 52, a bus driver in Detroit Michigan, divorced, two kids 16 and 14. I make $52,000 and spend $4,200 a month. I have $30,000 saved. I want to retire at 58.")
    auto(pg, [], log=False); build(pg)
    pg.get_by_role("button", name="Try this").first.click(); pg.wait_for_timeout(500)
    try: pg.locator(".turn .spinner").first.wait_for(state="detached", timeout=90000)
    except Exception: pass
    pg.wait_for_timeout(1000)
    shot(pg,"bus_try1",full=False); shot(pg,"bus_try1_full")
    log("AFTER TRY:", pg.inner_text("body")[:3500])
    log("BUTTONS:", pg.locator("button:visible").all_inner_texts()[:14])
    # back and click chip Make basics safe
    bk = pg.get_by_role("button", name=re.compile("Back to my plan"))
    if bk.count(): bk.first.click(); pg.wait_for_timeout(600)
    pg.get_by_role("button", name="Make your basics safe first").first.click()
    pg.wait_for_timeout(1500)
    try: pg.locator(".turn .spinner").first.wait_for(state="detached", timeout=90000)
    except Exception: pass
    pg.wait_for_timeout(800)
    shot(pg,"bus_chip_basics",full=False)
    log("AFTER BASICS CHIP:", pg.locator(".turn").last.inner_text()[:800])
    log("BUTTONS:", pg.locator("button:visible").all_inner_texts()[:14])
    log("axe", axe(pg,"x"), pg.errors)
    # typed whatifs
    for q in ["Spend $5,000 a year less now and save it","Claim Social Security at 70","save 20% of my pay"]:
        r = ask(pg,q); log("\n##",q,"\n",r[:700])
    shot(pg,"bus_typed",full=False)
    b.close()
