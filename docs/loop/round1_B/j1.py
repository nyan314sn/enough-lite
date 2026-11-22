from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    tr = intake(pg, "I'm a single nurse, 58, in Ohio. I make about $78,000. I have a pension from the county hospital and want to retire at 62.")
    print("\n".join(tr)); shot(pg, "j1_intake")
    print("canbuild", can_build(pg))
    if can_build(pg):
        print("build s", build(pg)); shot(pg, "j1_plan")
        print(pg.locator(".plan").inner_text())
    print(pg.errors)
    b.close()
