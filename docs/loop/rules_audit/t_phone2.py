from tour import *

with sync_playwright() as p:
    b, pg = newctx(p, 390, 844)
    example(pg); walk(pg, "p2"); build2(pg)
    for idx, live in ((0, "sources-live"), (1, "savings-live"), (2, "costs-live")):
        bx = pg.locator(".chart-box").nth(idx); bx.evaluate("e=>e.scrollIntoView({block:\"center\"})"); pg.wait_for_timeout(600)
        r = bx.bounding_box()
        P(f"--- chart {idx} box {r}")
        out = []
        for f in (0.15, 0.4, 0.65, 0.9):
            x = r["x"] + r["width"] * f; y = r["y"] + r["height"] * 0.5
            pg.touchscreen.tap(x, y); pg.wait_for_timeout(400)
            t = pg.locator(f"[data-testid={live}]").inner_text()
            m = re.search(r"Age (\d+)", t)
            out.append((f, m.group(1) if m else None, bx.inner_text().replace("\n", " | ")[-70:]))
        P("taps:", out)
        shot(pg, f"p2_chart{idx}", full=False)
    # Ideas chips
    pg.get_by_role("button", name=re.compile("Ideas")).click(); pg.wait_for_timeout(500)
    shot(pg, "p2_ideas", full=False)
    P("chips after Ideas:", pg.locator(".ask .chip:visible").all_inner_texts(), "sizes", [pg.locator(".ask .chip:visible").nth(i).bounding_box()["height"] for i in range(pg.locator(".ask .chip:visible").count())])
    for nm in ("Retire at 60", "Another child"):
        c = pg.locator(".ask .chip:visible", has_text=nm).first
        c.click(); pg.wait_for_timeout(800); wait_idle(pg, 120000)
        shot(pg, f"p2_{nm[:6]}", full=False)
        P(nm, "->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:300])
        P("buttons:", pg.locator("button:visible").all_inner_texts()[:12])
        bk = pg.get_by_role("button", name=re.compile("Back to my plan"))
        if bk.count() and bk.first.is_visible(): bk.first.click(); pg.wait_for_timeout(500)
        if not pg.locator(".ask .chip:visible").count():
            pg.get_by_role("button", name=re.compile("Ideas")).click(); pg.wait_for_timeout(400)
    P("small targets:", small_targets(pg), "overflow", overflow(pg))
    # team panel toggle
    tb = pg.get_by_role("button", name=re.compile("advisory team", re.I)).first
    tb.click(); pg.wait_for_timeout(600); shot(pg, "p2_team", full=False)
    P("team open:", pg.locator("[data-testid=team-panel]").bounding_box(), small_targets(pg))
    # Start over on phone
    pg.get_by_role("button", name="Start over").first.click(); pg.wait_for_timeout(500)
    shot(pg, "p2_startover", full=False)
    P("errors", pg.errors)
    b.close()
