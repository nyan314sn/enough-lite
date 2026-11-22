from walk import *
with sync_playwright() as p:
    b, pg = start(p)
    pg.get_by_role("button", name=re.compile(EX)).click()
    pg.wait_for_timeout(1500)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass
    walk(pg, "ex"); build2(pg)
    P("DETAILS:", pg.evaluate("[...document.querySelectorAll('details')].map(d=>[d.open,(d.querySelector('summary')||{}).textContent])"))
    P("EXPANDED:", pg.evaluate("[...document.querySelectorAll('[aria-expanded]')].map(d=>[d.tagName,d.getAttribute('aria-expanded'),d.textContent.slice(0,40)])"))
    P("SVG:", pg.evaluate("[...document.querySelectorAll('svg')].map(d=>[d.getAttribute('role'),d.getAttribute('tabindex'),d.getAttribute('aria-label'),d.parentElement.className, JSON.stringify(d.getBoundingClientRect())])"))
    P("TABINDEX:", pg.evaluate("[...document.querySelectorAll('[tabindex]')].map(d=>[d.tagName,d.className,d.getAttribute('tabindex'),(d.getAttribute('aria-label')||'').slice(0,50)])"))
    P("LEFT PANEL:", pg.locator("aside").count(), pg.locator("main").count())
    P("ASK area:", pg.locator("#ask-input").evaluate("e=>e.closest('section,div').outerHTML.slice(0,800)"))
    b.close()
