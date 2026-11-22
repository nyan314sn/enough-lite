from walk import *
with sync_playwright() as p:
    b, pg = start(p)
    pg.get_by_role("button", name=re.compile(EX)).click()
    pg.wait_for_timeout(1500)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass
    walk(pg, "j1")
    build2(pg)
    shot(pg,"j1_plan",full=True)
    P(body(pg))
    P("BUTTONS:", pg.locator("button:visible").all_inner_texts())
    P(axe(pg,"p"), overflow(pg), pg.errors)
    P(pg.evaluate("[...document.querySelectorAll('[id]')].map(e=>e.id).join(',')"))
    P(pg.evaluate("[...document.querySelectorAll('[data-testid]')].map(e=>e.dataset.testid).join(',')"))
    b.close()
