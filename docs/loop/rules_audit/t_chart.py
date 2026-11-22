from tour import *
import sys
W = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
with sync_playwright() as p:
    b, pg = newctx(p, W, 844 if W < 600 else 900)
    example(pg)
    walk(pg, "ch"); build2(pg)
    for idx, live in ((0, "sources-live"), (1, "savings-live"), (2, "costs-live")):
        bx = pg.locator(".chart-box").nth(idx); bx.evaluate("e=>e.scrollIntoView({block:\"center\"})"); pg.wait_for_timeout(600)
        r = bx.bounding_box()
        P(f"--- chart {idx} box {r}")
        out = []
        for i in range(1, 20):
            f = i / 20
            x = r["x"] + r["width"] * f; y = r["y"] + r["height"] * 0.5
            if W < 600:
                pg.touchscreen.tap(x, y)
            else:
                pg.mouse.move(x, y, steps=4)
            pg.wait_for_timeout(250)
            t = pg.locator(f"[data-testid={live}]").inner_text()
            m = re.search(r"Age (\d+)", t)
            out.append((round(f, 2), m.group(1) if m else None))
        P("age by x fraction:", out)
        shot(pg, f"ch_{W}_{idx}", full=False)
    P("errors", pg.errors)
    b.close()
