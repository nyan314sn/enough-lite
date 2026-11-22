import lib
lib.URL = "http://localhost:8116/"
from tour import *
W = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
OUTD = os.path.join(OUT, "..", "team_lines2")
def sh(pg, name):
    pg.screenshot(path=os.path.join(OUTD, f"{name}_{W}.png"), full_page=False)
with sync_playwright() as p:
    b, pg = newctx(p, W, 844 if W < 600 else 900)
    example(pg)
    walk(pg, "r4")
    P("page1 small targets:", small_targets(pg))
    P("page1 axe:", axe(pg, "p1"))
    pg.get_by_role("button", name="Build my plan", exact=True).first.click(); pg.wait_for_timeout(700)
    if pg.locator(".check").count(): pg.get_by_role("button", name="Looks right, build my plan").click()
    t0 = time.time(); got = 0
    tp = pg.locator("[data-testid=team-panel]")
    while time.time() - t0 < 120 and not pg.locator("[data-testid=plan-headline]").count():
        pg.wait_for_timeout(300)
        if W < 600 and tp.count() and not pg.locator("#team-body").is_visible():
            pg.locator("[data-testid=team-panel] .h-toggle button").click(); pg.wait_for_timeout(300)
        if pg.locator("[data-testid=roster-label]").count() and got < 2:
            got += 1
            P("LABEL:", pg.locator("[data-testid=roster-label]").inner_text())
            tp.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
            tp.screenshot(path=os.path.join(OUTD, f"build_{got}_{W}.png"))
            sh(pg, f"build_{got}_page")
            pg.wait_for_timeout(1500)
    pg.wait_for_selector("[data-testid=plan-headline]", timeout=120000); pg.wait_for_timeout(1500)
    if W < 600 and not pg.locator("#team-body").is_visible():
        pg.locator("[data-testid=team-panel] .h-toggle button").click(); pg.wait_for_timeout(400)
    tp.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    tp.screenshot(path=os.path.join(OUTD, f"done_{W}.png")); sh(pg, "done_page")
    P("lines:", pg.evaluate("[...document.querySelectorAll('svg.roster-lines path')].map(e=>e.dataset.line+' '+e.getAttribute('d'))"))
    P("plan small targets:", small_targets(pg))
    P("plan axe:", axe(pg, "plan"))
    P("overflow:", overflow(pg))
    # chart 1 (savings)
    bx = pg.locator(".chart-box").nth(1); bx.evaluate("e=>e.scrollIntoView({block:\"center\"})"); pg.wait_for_timeout(600)
    r = bx.bounding_box(); out = []
    for i in range(1, 20):
        f = i / 20; x = r["x"] + r["width"] * f; y = r["y"] + r["height"] * 0.5
        if W < 600: pg.touchscreen.tap(x, y)
        else: pg.mouse.move(x, y, steps=4)
        pg.wait_for_timeout(250)
        m = re.search(r"Age (\d+)", pg.locator("[data-testid=savings-live]").inner_text())
        out.append((round(f, 2), m.group(1) if m else None))
    P("savings age by x:", out)
    sh(pg, "savings_readout")
    P("errors", pg.errors)
    b.close()
