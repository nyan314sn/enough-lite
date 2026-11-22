from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    intake(pg, "I'm a single nurse, 58, in Ohio. I make about $78,000. I have a pension from the county hospital, about $1,500 a month at 62, and want to retire at 62.",
      ["About $50k","That's about right","I own it outright","No other debts","No children","$4,000 a month","That's about right"])
    print("pension panel:", pg.locator("aside").inner_text()[:2500])
    build(pg); pg.wait_for_timeout(500)
    shot(pg, "j1b_plan_vp", full=False)
    print("HEAD", pg.locator("[data-testid=plan-headline]").inner_text())
    qs = ["Retire at 60","Another child","Get a dog","Markets fall 30%","Retire at 65"]
    for i,q in enumerate(qs):
        pg.get_by_role("button", name=q, exact=True).first.click() if pg.get_by_role("button", name=q, exact=True).count() else ask(pg,q)
        pg.wait_for_function("!document.querySelector('.turn .spinner')", timeout=90000)
        pg.wait_for_timeout(800)
        print(f"--- WI {i} {q}: whatif view:", pg.locator("[data-testid=whatif]").count(), "| bar:", pg.locator(".summary-bar").count())
        print(pg.locator(".turn").last.inner_text()[:500])
        shot(pg, f"j1b_wi{i}_vp", full=False)
        if i==0:
            print(pg.locator("[data-testid=whatif]").inner_text()[:1500])
            shot(pg, "j1b_wi0_full")
    print("history:", pg.locator(".history").inner_text() if pg.locator(".history").count() else None)
    # back
    pg.get_by_role("button", name="← Back to my plan").click(); pg.wait_for_timeout(500)
    print("after back plan card:", pg.locator(".plan").count(), "bar", pg.locator(".summary-bar").count(), "history", pg.locator(".history").count())
    shot(pg, "j1b_back_vp", full=False)
    print("chip labels:", pg.locator(".ask .chip").all_inner_texts())
    print(pg.errors)
    b.close()
