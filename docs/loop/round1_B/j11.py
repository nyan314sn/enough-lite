from lib import *
with sync_playwright() as p:
    b, pg = new(p, 390, 844)
    say(pg, "I'm 61, a retired-soon accountant in Arizona, single. I make $90,000 and spend $5,000 a month. I have $700,000 saved. Retire at 65.")
    print("canbuild", auto(pg, log=False), flush=True)
    pg.get_by_role("button", name="Build my plan", exact=True).first.click()
    pg.wait_for_timeout(1500); shot(pg,"j11_building_phone",full=False)
    print("axe building", axe(pg,"b"))
    pg.wait_for_selector("[data-testid=plan-headline]", timeout=120000); pg.wait_for_timeout(500)
    print("focus after build:", pg.evaluate("document.activeElement.id||document.activeElement.tagName"), "scrollY", pg.evaluate("scrollY"))
    pg.set_viewport_size({"width":1440,"height":900}); pg.wait_for_timeout(500)
    pg.evaluate("window.scrollTo(0,0)")
    for i in [0,3,4]:
        pg.locator(".team-panel button.node").nth(i).evaluate("e=>e.click()"); pg.wait_for_timeout(400)
        print(i, pg.locator(".team-panel").inner_text()[:700].replace("\n"," | ")[130:560])
    shot(pg,"j11_adviser_desktop",full=False)
    print(pg.errors); b.close()
