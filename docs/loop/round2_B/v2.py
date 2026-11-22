from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    b, pg = new(p, 390, 844)
    say(pg, "I'm 30, a software engineer in Austin Texas, I make $95,000. I have $8,000 saved and student loans. Retire at 65.")
    for i in range(14):
        if can_build(pg): break
        last = transcript(pg)[-1]
        a = "skip" if re.search(r"spend|loan|debt|owe", last, re.I) else None
        if a is None:
            chips = pg.locator(".quick .chip").all_inner_texts()
            a = next((c for c in chips if re.search(r"about right|rent|no children|none", c, re.I)), chips[0] if chips else "I rent")
        log("Q:", last[-170:].replace("\n"," "), "->", a); say(pg, a)
    log("LAST:", transcript(pg)[-1])
    shot(pg,"v2_skip_intake",full=False)
    pg.get_by_role("button", name=re.compile("Your numbers")).first.click(); pg.wait_for_timeout(500)
    t = pg.locator("#numbers-sheet").inner_text().replace("\n"," | "); log("SHEET:", t[:1500])
    shot(pg,"v2_sheet",full=False)
    # edit and save in sheet; does reply hide?
    pg.get_by_role("button", name=re.compile("Change Your pay")).first.click(); pg.wait_for_timeout(300)
    pg.locator("#numbers-sheet input").first.fill("100000"); pg.get_by_role("button", name="Save").first.click(); pg.wait_for_timeout(1500)
    shot(pg,"v2_sheet_save",full=False)
    log("sheet open after save:", pg.locator("#numbers-sheet").is_visible() if pg.locator("#numbers-sheet").count() else False)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    small = pg.evaluate("""[...document.querySelectorAll('button,a,input,summary')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.height<36)}).map(e=>(e.innerText||e.getAttribute('aria-label')||e.tagName).slice(0,30)+' '+Math.round(e.getBoundingClientRect().width)+'x'+Math.round(e.getBoundingClientRect().height))""")
    log("small intake targets:", small)
    while not can_build(pg):
        chips = pg.locator(".quick .chip").all_inner_texts(); say(pg, next((c for c in chips if re.search(r"about right|same|skip|typical",c,re.I)), "skip"))
    pg.get_by_role("button", name="Build my plan", exact=True).first.click(); pg.wait_for_timeout(2500)
    shot(pg,"v2_building",full=False); log("BUILDING:", pg.inner_text("body")[:600].replace("\n"," | "))
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=120000); pg.wait_for_timeout(500)
    log("PLAN:", pg.locator(".plan").inner_text()[:1500])
    shot(pg,"v2_plan",full=False)
    log("TOP:", pg.evaluate("document.querySelector('.plan').getBoundingClientRect().top"))
    small = pg.evaluate("""[...document.querySelectorAll('button,a,input,summary')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.height<36)}).map(e=>(e.innerText||e.getAttribute('aria-label')||e.tagName).slice(0,30)+' '+Math.round(e.getBoundingClientRect().width)+'x'+Math.round(e.getBoundingClientRect().height))""")
    log("small plan targets:", small)
    pg.get_by_role("button", name=re.compile("Ideas")).first.click(); pg.wait_for_timeout(500); shot(pg,"v2_ideas",full=False)
    pg.keyboard.press("Escape")
    log("team adviser:")
    pg.locator(".team-panel button").nth(1).click(); pg.wait_for_timeout(500); shot(pg,"v2_adviser",full=False)
    log("axe", axe(pg,"p"), overflow(pg), pg.errors)
    b.close()
