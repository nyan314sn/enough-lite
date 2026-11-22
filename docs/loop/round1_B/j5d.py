from lib import *
with sync_playwright() as p:
    b, pg = new(p, 390, 844)
    say(pg, "I'm 30, a software engineer in Austin Texas, I rent. I make $95,000 and my employer matches 4% of my 401k. I have $45,000 in student loans at 6.5% and $8,000 saved. I spend $4,500 a month. Retire at 65.")
    say(pg,"No children")
    for _ in range(3):
        if can_build(pg): break
        say(pg,"That's about right")
    print(pg.locator("aside.side").inner_text().count("6.5"), [l for l in pg.locator("aside.side").inner_text().split("\n") if "oan" in l])
    build(pg)
    shot(pg,"j5d_plan_top",full=False)
    pg.evaluate("window.scrollTo(0,700)"); pg.wait_for_timeout(300); shot(pg,"j5d_plan_mid",full=False)
    r = ask(pg,"Retire at 60"); pg.wait_for_timeout(800)
    shot(pg,"j5d_wi_top",full=False)
    pg.evaluate("window.scrollTo(0,900)"); pg.wait_for_timeout(300); shot(pg,"j5d_wi_mid",full=False)
    pg.evaluate("window.scrollTo(0,document.body.scrollHeight)"); pg.wait_for_timeout(300)
    # open team panel
    t = pg.locator(".team-panel button").first
    print("team toggle:", t.inner_text().replace("\n"," | "), t.get_attribute("aria-expanded"))
    t.click(); pg.wait_for_timeout(600)
    pg.locator(".team-panel").scroll_into_view_if_needed()
    shot(pg,"j5d_team_open",full=False)
    pg.locator(".team-panel button.node").nth(1).evaluate("e=>e.click()"); pg.wait_for_timeout(600)
    shot(pg,"j5d_team_adviser",full=False)
    print(pg.locator(".team-panel").inner_text()[:1800].replace("\n"," | "))
    # keyboard focus visible?
    print(pg.errors)
    b.close()
