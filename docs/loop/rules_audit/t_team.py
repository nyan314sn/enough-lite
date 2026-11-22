from tour import *
import threading

with sync_playwright() as p:
    b, pg = newctx(p)
    example(pg)
    walk(pg, "tm")
    # Build button: first press note, "Let me change something"
    pg.get_by_role("button", name="Build my plan", exact=True).first.click(); pg.wait_for_timeout(600)
    shot(pg, "tm_check", full=False)
    pg.get_by_role("button", name="Let me change something").click(); pg.wait_for_timeout(600)
    P("after 'Let me change something': check shown", pg.locator(".check").count(), "focus:", pg.evaluate("document.activeElement.outerHTML.slice(0,120)"))
    pg.get_by_role("button", name="Build my plan", exact=True).first.click(); pg.wait_for_timeout(600)
    pg.get_by_role("button", name="Looks right, build my plan").click()
    t0 = time.time(); k = 0
    seen = set()
    while time.time() - t0 < 60 and not pg.locator("[data-testid=plan-headline]").count():
        pg.wait_for_timeout(700)
        tp = pg.locator("[data-testid=team-panel]")
        if tp.count():
            txt = tp.inner_text().replace("\n", " | ")[:700]
            lines = pg.evaluate("[...document.querySelectorAll('[data-testid=team-panel] svg.roster-lines *')].map(e=>e.tagName+':'+(e.getAttribute('class')||'')+':'+(e.getAttribute('d')||'').slice(0,40)+':'+(e.textContent||'').slice(0,40))")
            key = txt[:300]
            if key not in seen:
                seen.add(key); k += 1
                P(f"[t={time.time()-t0:.1f}s] TEAM during build: {txt}\n   LINES: {lines[:14]}")
                shot(pg, f"tm_build_{k}", full=False)
    P("plan up:", pg.locator("[data-testid=plan-headline]").count())
    pg.wait_for_timeout(1000)
    # chart 1 pointer sweep
    bx = pg.locator(".chart-box").nth(1); bx.scroll_into_view_if_needed(); r = bx.bounding_box()
    P("chart1 box", r)
    for f in (0.1, 0.3, 0.5, 0.7, 0.9):
        pg.mouse.move(r["x"] + r["width"] * f, r["y"] + r["height"] * 0.5); pg.wait_for_timeout(400)
        P(f"  f={f}:", [l for l in pg.locator("[data-testid=savings-live]").all_inner_texts()], "| tip:", bx.inner_text().replace("\n", " | ")[-110:])
    shot(pg, "tm_chart1_hover", full=False)
    # sources chart (chart 0) at pre-retirement ages, vs headline
    bx = pg.locator(".chart-box").nth(0); bx.scroll_into_view_if_needed(); r = bx.bounding_box()
    for f in (0.05, 0.15, 0.25, 0.35, 0.45):
        pg.mouse.move(r["x"] + r["width"] * f, r["y"] + r["height"] * 0.5); pg.wait_for_timeout(400)
        P(f"  src f={f}:", pg.locator("[data-testid=sources-live]").all_inner_texts())
    # Try this buttons
    tt = pg.get_by_role("button", name="Try this")
    P("Try this count:", tt.count())
    for i in range(tt.count()):
        tt.nth(i).scroll_into_view_if_needed(); tt.nth(i).click(); pg.wait_for_timeout(800); wait_idle(pg, 120000)
        P(f"TRY THIS {i}: ", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400] if pg.locator(".turn").count() else "(no turn)", "| bar:", pg.locator("button:has-text('show')").first.inner_text().replace("\n"," ")[:120] if pg.locator("button:has-text('show')").count() else "")
        shot(pg, f"tm_try_{i}", full=False)
        bk = pg.get_by_role("button", name=re.compile("Back to my plan"))
        if bk.count() and bk.first.is_visible(): bk.first.click(); pg.wait_for_timeout(600)
        shot(pg, f"tm_try_{i}_back", full=False)
    # collapse bar
    P("buttons:", pg.locator("button:visible").all_inner_texts()[:20])
    b.close()
