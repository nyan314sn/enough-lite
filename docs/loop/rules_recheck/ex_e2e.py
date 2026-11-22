from hdr import *
with sync_playwright() as p:
    b, pg = newctx(p, W, H)
    example(pg)
    P("FIRST:", last_bot(pg)[:400]); shot(pg, f"ex{W}_1_first")
    P("PAGE1 axe", axe(pg,"i"), "small", small_targets(pg)[:8])
    click_chip(pg, "That's about right"); say(pg, "$2,900"); walk(pg, "ex")
    P("PANEL:", panel(pg)[:3000])
    P("pencil count", pg.locator("button.pen").count())
    note = build2(pg)
    shot(pg, f"ex{W}_2_plan")
    P("HEADLINE:", pg.locator("[data-testid=plan-headline]").inner_text().replace("\n"," | "))
    P("PLAN axe", axe(pg,"p"), "overflow", overflow(pg), "small", small_targets(pg)[:8])
    pg.locator("details.analysis > summary").first.click(); pg.wait_for_timeout(500)
    P("ANALYSIS:", pg.locator("details.analysis").first.inner_text()[:2500].replace("\n"," | "))
    shot(pg, f"ex{W}_3_analysis", full=False)
    # What If
    t = ask(pg, "retire at 65")
    P("WHATIF retire at 65 ->", t.replace("\n"," | ")[:600])
    shot(pg, f"ex{W}_4_whatif", full=False)
    P("collapsed bar:", pg.locator(".plan-bar, .summary-bar, [data-testid=plan-bar]").all_inner_texts())
    back = pg.get_by_role("button", name=re.compile("Back to my plan"))
    P("back visible", back.count() and back.first.is_visible())
    if back.count(): back.first.click(); pg.wait_for_timeout(600)
    # Assumptions
    s = pg.locator("[data-testid=plan-assumptions] > summary"); s.scroll_into_view_if_needed(); s.click(); pg.wait_for_timeout(400)
    P("ASSUMPTIONS:", pg.locator("[data-testid=plan-assumptions]").inner_text().replace("\n"," | ")[:2500])
    bt = pg.locator("[data-testid=plan-assumptions] .assumption-changes button")
    P("assumption buttons:", bt.all_inner_texts())
    shot(pg, f"ex{W}_5_assump", full=False)
    for i in range(bt.count()):
        if re.search(r"claim|social|benefit|start", bt.nth(i).inner_text(), re.I):
            bt.nth(i).click(); pg.wait_for_timeout(800); wait_idle(pg, 120000)
            sub(pg, "CLAIM BTN " + bt.nth(i).inner_text())
            shot(pg, f"ex{W}_6_claim", full=False)
            break
    else:
        P("NO claim-age button")
    P("errors", pg.errors)
    b.close()
