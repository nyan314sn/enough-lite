from lib import *
log = lambda *a: print(*a, flush=True)
BUS = "I'm 52, a bus driver in Detroit Michigan, divorced, two kids 16 and 14. I make $52,000 and spend $4,200 a month. I have $30,000 saved. I want to retire at 58."
with sync_playwright() as p:
    for w, h in ((1440, 900), (820, 1000), (390, 800)):
        b, pg = new(p, w, h)
        say(pg, BUS)
        intake_ok = True
        for _ in range(14):
            if can_build(pg): break
            chips = pg.locator(".quick .chip").all_inner_texts()
            skip = [c for c in chips if re.search(r"skip|typical|same|none|no\b|not sure", c, re.I)]
            say(pg, skip[0] if skip else (chips[0] if chips else "skip"))
        if w == 390:
            pg.get_by_role("button", name="Build my plan", exact=True).last.click()
            pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000)
        else:
            build(pg)
        pg.wait_for_timeout(1500)
        log(w, "STEPS", pg.locator(".steps").inner_text().replace("\n", " | "), [pg.evaluate("e=>e.getBoundingClientRect().height", pg.locator(".steps li").nth(i).element_handle()) for i in range(3)])
        log(w, "points buttons", pg.locator(".starting-points button").count(), "action1:", pg.locator(".actions li").first.inner_text()[:300].replace("\n"," "))
        shot(pg, f"plan_{w}", full=False)
        log(w, "chip rows:", pg.evaluate("(()=>{const c=document.querySelector('.chip-scroll');if(!c)return null;const r=c.getBoundingClientRect();return [Math.round(r.height), c.scrollHeight, [...c.querySelectorAll('.chip')].map(x=>{const q=x.getBoundingClientRect();return q.left<r.left-1||q.right>r.right+1})]})()"))
        log(w, "ask bar h", pg.evaluate("Math.round(document.querySelector('.ask').getBoundingClientRect().height)"))
        sm = pg.locator("[data-testid=plan-assumptions] > summary")
        if sm.count():
            log(w, "assump summary h", sm.evaluate("e=>e.getBoundingClientRect().height"), "li", pg.locator("[data-testid=plan-assumptions] > ul > li").count(), "more", pg.locator(".more-assumptions").count())
        if w < 861:
            pg.get_by_role("button", name=re.compile("Your advisory team")).click(); pg.wait_for_timeout(500)
            pg.get_by_role("button", name=re.compile("^Ideas")).click(); pg.wait_for_timeout(300)
            log(w, "chip rows:", pg.evaluate("(()=>{const c=document.querySelector('.chip-scroll');if(!c)return null;const r=c.getBoundingClientRect();return [Math.round(r.height), c.scrollHeight, [...c.querySelectorAll('.chip')].map(x=>{const q=x.getBoundingClientRect();return q.left<r.left-1||q.right>r.right+1})]})()"), "ask h", pg.evaluate("Math.round(document.querySelector('.ask').getBoundingClientRect().height)"))
            shot(pg, f"chips_{w}", full=False)
        if True:
            tl = pg.locator(".talk-log")
            if tl.count():
                tl.scroll_into_view_if_needed()
                log(w, "talk rows whole?", pg.evaluate("(()=>{const l=document.querySelector('.talk-log');const r=l.getBoundingClientRect();return [...l.querySelectorAll('.talk-row')].map(x=>{const q=x.getBoundingClientRect();return [Math.round(q.top-r.top),Math.round(q.bottom-r.bottom)]})})()"))
                pg.locator(".team-panel").screenshot(path=os.path.join(OUT, f"team_{w}.png"))
            pg.locator("[data-agent=markets]").click(); pg.wait_for_timeout(300)
            shot(pg, f"detail_{w}", full=False)
            log(w, "DETAIL:", pg.locator(".detail-box").inner_text().replace("\n"," | ")[:400])
        # starting point button
        if pg.locator(".starting-points button").count():
            pg.locator(".starting-points button").first.click()
            try: pg.locator(".turn .spinner").first.wait_for(state="detached", timeout=90000)
            except Exception: pass
            pg.wait_for_selector("[data-testid=whatif]", timeout=90000); pg.wait_for_timeout(500)
            log(w, "SP result:", pg.locator(".turn").last.inner_text()[:200].replace("\n"," "), "| whatif shown:", pg.locator("[data-testid=whatif]").count())
        log(w, "axe", axe(pg, "p"), overflow(pg))
        pg.get_by_role("button", name=re.compile("Change my answers")).click(); pg.wait_for_timeout(500)
        log(w, "visible quick chips in intake:", [c for c in pg.locator(".intake .quick .chip").all_inner_texts()], "| visible plan chips:", pg.locator(".ask .chip:visible").count())
        pg.get_by_role("button", name="Start over").click(); pg.get_by_role("button", name="Yes, clear").click(); pg.wait_for_timeout(800)
        log(w, "AFTER START OVER:", len(transcript(pg)), transcript(pg)[-1][:80])
        log(pg.errors); b.close()
