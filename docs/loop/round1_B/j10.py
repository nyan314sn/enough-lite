from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 47, a teacher in Ohio, married, my husband is 49 and works as an electrician. I make $68,000, he makes $82,000. We have $210,000 saved, spend $6,500 a month. I have a state teacher pension of about $3,000 a month starting at 60. Retire at 60. Two kids, 15 and 12.")
    print("canbuild", auto(pg, log=True), flush=True)
    print(pg.locator("aside.side").inner_text().replace("\n"," | ")[:2200])
    build(pg)
    print(pg.locator("[data-testid=plan-headline]").inner_text())
    ask(pg,"Retire at 62"); ask(pg,"Another child")
    shot(pg,"j10_two_wi_vp",full=False)
    print("show buttons before:", pg.get_by_role("button", name=re.compile("Show this What If")).count())
    # change while a What If is open
    print(ask(pg,"actually I have 3 kids, not 2")[:200])
    print("WI open while confirm pending:", pg.locator("[data-testid=whatif]").count())
    print(ask(pg,"no")[:250])
    print(ask(pg,"actually I have 3 kids, not 2")[:100]); print(ask(pg,"yes")[:200])
    print("after: whatif view", pg.locator("[data-testid=whatif]").count(), "plan card", pg.locator(".plan").count(), "history", pg.locator(".history").count(), "bar", pg.locator(".summary-bar").count())
    btns = pg.get_by_role("button", name=re.compile("Show this What If"))
    print("stale show buttons:", btns.count())
    if btns.count():
        btns.first.click(); pg.wait_for_timeout(500)
        print("after click stale show: whatif", pg.locator("[data-testid=whatif]").count(), "plan", pg.locator(".plan").count(), "bar", pg.locator(".summary-bar").count())
        shot(pg,"j10_stale_show_vp",full=False)
    # pension in panel?
    pg.get_by_role("button", name="← Change my answers").click(); pg.wait_for_timeout(500)
    print([l for l in pg.locator("aside.side").inner_text().split("\n") if re.search("ension|Partner|Children",l)])
    shot(pg,"j10_intake_back",full=False)
    print(pg.errors); b.close()
