from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 52, a bus driver in Detroit Michigan, divorced, two kids 16 and 14. I make $52,000 and spend $4,200 a month. I have $30,000 saved. I want to retire at 58.")
    print(transcript(pg)[-1])
    print(auto(pg, [], log=True))
    print(pg.locator("aside").first.inner_text())
    shot(pg,"e1_intake",full=False)
    t=build(pg); print("build",t)
    print(pg.inner_text("body"))
    shot(pg,"e1_plan",full=False); shot(pg,"e1_plan_full")
    b.close()
