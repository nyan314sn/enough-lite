from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 47, a teacher in Ohio, married, my husband is 49 and works as an electrician. I make $68,000, he makes $82,000. We have $210,000 saved, spend $6,500 a month. I have a state teacher pension of about $3,000 a month starting at 60. Retire at 60. Two kids, 15 and 12.")
    auto(pg, [(r"mortgage payment","$1,500 a month")], log=True)
    build(pg)
    open("teacher_dom.html","w",encoding="utf-8").write(pg.content())
    pg.locator("summary", has_text="Assumptions").click(); pg.wait_for_timeout(400)
    print("ASSUMP:", pg.locator("details", has_text="Assumptions").inner_text())
    pg.locator("details", has_text="Assumptions").scroll_into_view_if_needed()
    shot(pg,"teacher_assump",full=False)
    print(pg.locator(".plan").inner_text())
    shot(pg,"teacher_plan",full=True)
    b.close()
