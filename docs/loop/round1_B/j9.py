from lib import *
with sync_playwright() as p:
    b, pg = new(p, 390, 844)
    pg.get_by_role("button", name=re.compile("Use an example")).click(); pg.wait_for_timeout(500)
    pg.wait_for_selector(".typing", state="detached", timeout=60000)
    print("canbuild", auto(pg, log=False), flush=True)
    shot(pg,"j9_intake_phone",full=False)
    # sheet: edit pay
    pg.get_by_role("button", name=re.compile("Your numbers")).first.click(); pg.wait_for_timeout(500)
    pg.locator("#numbers-sheet").get_by_role("button", name=re.compile("Change Your pay")).first.click(); pg.wait_for_timeout(400)
    shot(pg,"j9_sheet_editor",full=False)
    inp = pg.locator("#numbers-sheet input").first; inp.fill("300000")
    pg.locator("#numbers-sheet").get_by_role("button", name="Save").first.click(); pg.wait_for_timeout(3000)
    print("sheet open after save:", pg.locator("#numbers-sheet").count(), "| pay shown:", "300,000" in pg.locator("#numbers-sheet").inner_text() if pg.locator("#numbers-sheet").count() else "n/a")
    shot(pg,"j9_sheet_after_save",full=False)
    # reset a section in the sheet
    if pg.locator("#numbers-sheet").count():
        pg.locator("#numbers-sheet").get_by_role("button", name="Reset Home & debts").first.click(); pg.wait_for_timeout(2500)
        print("sheet after reset open:", pg.locator("#numbers-sheet").count())
        shot(pg,"j9_sheet_after_reset",full=False)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    print("last bubble:", transcript(pg)[-1][:300])
    shot(pg,"j9_after_sheet",full=False)
    print("canbuild", auto(pg, log=True), flush=True)
    build(pg); shot(pg,"j9_plan_phone",full=False)
    print(pg.locator("[data-testid=plan-headline]").inner_text())
    wc = pg.locator(".worth-checking")
    print("worth:", wc.count())
    if wc.count():
        wc.locator("summary").click(); print(wc.inner_text()); pg.wait_for_timeout(200)
        wc.scroll_into_view_if_needed(); shot(pg,"j9_worth_phone",full=False)
    # start over on phone
    pg.evaluate("window.scrollTo(0,0)")
    pg.get_by_role("button", name="Start over").click(); pg.wait_for_timeout(300); shot(pg,"j9_startover_phone",full=False)
    pg.get_by_role("button", name="Yes, clear").click(); pg.wait_for_timeout(600)
    print("after start over:", transcript(pg)[-1][:80], "| ask box:", pg.locator(".ask").count(), "| steps:", pg.locator(".steps").inner_text().replace("\n"," "))
    print(pg.errors)
    b.close()
