from journeys import *

with sync_playwright() as p:
    b, pg = newctx(p)
    cfg = J["renter"]
    say(pg, cfg["first"]); walk(pg, "tr", cfg["rules"]); build2(pg)
    P("HEAD:", headline_figures(pg)[:400])
    n = pg.get_by_role("button", name="Try this").count()
    P("Try this buttons:", n)
    for i in range(n):
        btn = pg.get_by_role("button", name="Try this")
        if i >= btn.count(): break
        row = btn.nth(i).locator("xpath=..").inner_text().replace("\n", " ")[:160]
        btn.nth(i).click(); pg.wait_for_timeout(800); wait_idle(pg, 120000)
        P(f"TRY {i} ({row!r}) ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:420])
        shot(pg, f"tr_{i}", full=False)
        bk = pg.get_by_role("button", name=re.compile("Back to my plan"))
        if bk.count() and bk.first.is_visible(): bk.first.click(); pg.wait_for_timeout(600)
    P("after: headline", headline_figures(pg)[:200])
    # Start over keep/clear from plan page
    pg.get_by_role("button", name="Start over").first.click(); pg.wait_for_timeout(500)
    P("start over dialog:", pg.locator("text=Clear everything").count())
    pg.get_by_role("button", name=re.compile("Yes, clear")).click(); pg.wait_for_timeout(1200)
    P("after clear: on intake?", pg.locator("#chat-input").count(), transcript(pg)[:1])
    b.close()
