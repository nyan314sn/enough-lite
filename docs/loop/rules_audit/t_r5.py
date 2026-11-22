import lib
lib.URL = "http://localhost:8116/"
from tour import *
W = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
with sync_playwright() as p:
    b, pg = newctx(p, W, 844 if W < 600 else 900)
    example(pg); walk(pg, "r5")
    P("page1 small:", small_targets(pg)); P("page1 axe:", axe(pg, "p1"))
    build2(pg)
    pg.locator("details.analysis > summary").click(); pg.wait_for_timeout(500)
    P("plan small:", small_targets(pg)); P("plan axe:", axe(pg, "plan"))
    bx = pg.locator("[data-testid=sources-chart]").locator("xpath=..")
    bx.evaluate("e=>e.scrollIntoView({block:'center'})"); pg.wait_for_timeout(500)
    r = bx.bounding_box(); out = []
    for i in range(1, 20):
        f = i / 20; x = r["x"] + r["width"] * f; y = r["y"] + r["height"] * 0.5
        if W < 600: pg.touchscreen.tap(x, y)
        else: pg.mouse.move(x, y, steps=4)
        pg.wait_for_timeout(200)
        m = re.search(r"Age (\d+)", pg.locator("[data-testid=sources-live]").inner_text())
        out.append((round(f, 2), m.group(1) if m else None))
    P("sources age by x:", out); P("errors", pg.errors)
    b.close()
