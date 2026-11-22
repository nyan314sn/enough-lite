from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    print(pg.inner_text("body"))
    print("BUTTONS:", pg.locator("button:visible").all_inner_texts())
    print("CHIPS:", pg.locator(".chip:visible").all_inner_texts())
    shot(pg,"j0_start",full=False)
    b.close()
