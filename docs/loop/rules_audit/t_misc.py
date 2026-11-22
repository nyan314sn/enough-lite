from tour import *

with sync_playwright() as p:
    b, pg = newctx(p)
    # R21: XSS in first message
    say(pg, "I'm 40 and a <img src=x onerror=\"window.__pwn=1\"> plumber in Ohio <script>window.__pwn2=1</script>")
    P("XSS flags:", pg.evaluate("[window.__pwn, window.__pwn2]"), "| bot:", last_bot(pg)[-250:])
    pg.get_by_role("button", name="Start over").first.click(); pg.wait_for_timeout(400)
    pg.get_by_role("button", name=re.compile("Yes, clear")).click(); pg.wait_for_timeout(800)
    example(pg); walk(pg, "ms")
    # editor pending state
    pg.locator("button.pen[aria-label='Add health']").click(); pg.wait_for_timeout(700)
    bb = pg.get_by_role("button", name="Build my plan", exact=True).first
    P("after 'Add health' pen: build aria-disabled:", bb.get_attribute("aria-disabled"), "| why:", pg.locator("#lp-build-why").inner_text(), "| bot:", last_bot(pg)[-160:], chips(pg))
    shot(pg, "ms_pending", full=False)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
    P("after Escape: build aria-disabled:", bb.get_attribute("aria-disabled"), "| why:", pg.locator("#lp-build-why").inner_text())
    click_chip(pg, "Fair"); P("after chip Fair: build disabled?", bb.get_attribute("aria-disabled"), "| bot:", last_bot(pg)[-200:])
    # R9: inheritance counted?
    say(pg, "I may inherit $300,000 from my aunt someday")
    P("INHERIT bot:", last_bot(pg)[-400:], chips(pg))
    t = panel(pg); i = t.find("Goals"); P("Goals panel:", t[i:i+500])
    build2(pg)
    P("headline:", headline_figures(pg))
    # timing of AI-answered questions
    for q in ("tell me exactly what to do", "what rules apply to my 401(k) at 60?", "explain my plan"):
        t0 = time.time(); r = ask(pg, q); P(f"ASK {q!r} took {time.time()-t0-1:.1f}s ->", r.replace("\n", " | ")[:400])
    # R9 plan chat
    r = ask(pg, "what if I inherit 300000 next year"); P("WHATIF inherit ->", r.replace("\n", " | ")[:500])
    r = ask(pg, "what does the plan assume"); P("assume ->", r.replace("\n", " | ")[:700])
    P("errors", pg.errors)
    b.close()
