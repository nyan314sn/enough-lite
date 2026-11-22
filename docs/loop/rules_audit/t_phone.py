from tour import *

with sync_playwright() as p:
    b, pg = newctx(p, 390, 844)
    example(pg)
    walk(pg, "ph")
    P("buttons visible:", pg.locator("button:visible").all_inner_texts()[:15])
    sheet = pg.get_by_role("button", name=re.compile("Your numbers")).first
    P("sheet btn:", sheet.inner_text(), sheet.bounding_box())
    sheet.click(); pg.wait_for_timeout(700)
    shot(pg, "ph_sheet", full=False)
    P("small targets in sheet:", small_targets(pg))
    P("axe sheet:", axe(pg, "s"), "overflow", overflow(pg))
    # pencil + editor on phone
    pen = pg.locator("button.pen[aria-label='Change Your pay']:visible")
    pen.scroll_into_view_if_needed(); pen.click(); pg.wait_for_timeout(600)
    shot(pg, "ph_editor", full=False)
    P("editor inputs visible:", pg.evaluate("[...document.querySelectorAll('input,textarea,select')].filter(e=>e.offsetParent!==null).map(e=>[e.id,Math.round(e.getBoundingClientRect().height)])"))
    P("small targets with editor open:", small_targets(pg))
    cb = pg.get_by_role("button", name="Cancel")
    if cb.count(): cb.first.click()
    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
    P("sheet closed?", pg.get_by_role("button", name="Reset").count())
    # Build on phone
    P("build visible:", can_build(pg))
    note = build2(pg)
    shot(pg, "ph_plan", full=True)
    P("plan buttons:", pg.locator("button:visible").all_inner_texts()[:25])
    P("small targets plan:", small_targets(pg), "overflow", overflow(pg))
    # What if collapse bar on phone
    pg.get_by_role("button", name="Retire at 60").first.click(); pg.wait_for_timeout(800); wait_idle(pg, 120000)
    shot(pg, "ph_whatif", full=False)
    P("whatif body head:", body(pg)[:900].replace("\n", " | "))
    P("small targets whatif:", small_targets(pg), "overflow", overflow(pg))
    bk = pg.get_by_role("button", name=re.compile("Back to my plan"))
    P("back btn:", bk.count(), bk.first.bounding_box() if bk.count() else None)
    if bk.count(): bk.first.click(); pg.wait_for_timeout(500)
    # error state: ask empty / very long
    ans = ask(pg, "x" * 3000)
    P("long input reply:", ans[:300].replace("\n", " | "))
    shot(pg, "ph_after", full=False)
    # team panel on phone
    P("team panel visible:", pg.locator("[data-testid=team-panel]").is_visible(), pg.locator("[data-testid=team-panel]").bounding_box())
    P("errors", pg.errors)
    b.close()
