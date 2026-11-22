from walk import *
with sync_playwright() as p:
    b, pg = start(p)
    pg.get_by_role("button", name=re.compile(EX)).click()
    pg.wait_for_timeout(1500)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass
    walk(pg, "ex"); build2(pg)
    pg.get_by_role("button", name="Retire at 60").click()
    pg.wait_for_timeout(1500)
    try: pg.locator(".turn .spinner").first.wait_for(state="detached", timeout=90000)
    except Exception: pass
    pg.wait_for_timeout(1000)
    shot(pg,"ex_whatif",full=False)
    P(body(pg)[:3500])
    P("BUTTONS:", pg.locator("button:visible").all_inner_texts())
    r = ask(pg, "what does the plan assume")
    P("ASSUME:", r)
    # hover chart
    b.close()
