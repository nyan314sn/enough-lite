from walk import *
with sync_playwright() as p:
    b, pg = start(p)
    pg.get_by_role("button", name=re.compile(EX)).click()
    pg.wait_for_timeout(1500)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass
    walk(pg, "ex")
    pens = pg.locator("button[aria-label*='dit'], button:has-text('✎')")
    P("pens", pens.count(), [pens.nth(i).get_attribute("aria-label") for i in range(min(40,pens.count()))])
    pens.nth(3).click(); pg.wait_for_timeout(600)
    shot(pg,"ex_edit",full=False)
    P("INPUTS visible:", pg.evaluate("[...document.querySelectorAll('input,textarea,select')].filter(e=>e.offsetParent!==null).map(e=>[e.tagName,e.id,e.type,e.getAttribute('aria-label')])"))
    P("BUTTONS:", pg.locator("button:visible").all_inner_texts()[:60])
    P("ACTIVE:", pg.evaluate("document.activeElement.outerHTML.slice(0,200)"))
    P(pg.locator("[data-testid=live-panel]").inner_text()[:600])
    b.close()
