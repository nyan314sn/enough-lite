from lib import *
ANS=["About $400k","That's about right","I own it outright","No other debts","No children","$5,000 a month","That's about right"]
with sync_playwright() as p:
    b, pg = new(p)
    intake(pg, "I'm 44, a dentist in Connecticut, single, retire at 60. I make $210,000.", ANS)
    print(can_build(pg)); build(pg)
    h0 = pg.locator("[data-testid=plan-headline]").inner_text(); print("H0", h0)
    # worth checking
    wc = pg.locator(".worth-checking")
    print("worth checking count", wc.count())
    if wc.count(): wc.locator("summary").click(); print(wc.inner_text()); shot(pg,"j3_worth_vp",full=False)
    # chat correction of pay via chat
    print("ASK1:", ask(pg, "my pay is wrong, it's $150,000"))
    shot(pg,"j3_chatfix1_vp",full=False)
    print("ASK2:", ask(pg, "yes"))
    shot(pg,"j3_chatfix2_vp",full=False)
    print("HEAD now", pg.locator("[data-testid=plan-headline]").inner_text() if pg.locator("[data-testid=plan-headline]").count() else None)
    print("ASK3:", ask(pg, "actually I want to retire at 58"))
    print("ASK4:", ask(pg, "yes"))
    print("HEAD now", pg.locator("[data-testid=plan-headline]").inner_text())
    print("stale?", pg.locator(".stale").count())
    # go to answers
    pg.get_by_role("button", name="← Change my answers").click(); pg.wait_for_timeout(600)
    shot(pg,"j3_back_to_intake",full=False)
    side = pg.locator("aside.side").inner_text()
    print("PANEL pay/retire:", [l for l in side.split("\n") if re.search(r"\$|retire|Retire",l)][:12])
    # editor
    pg.get_by_role("button", name=re.compile("Change Your pay")).first.click(); pg.wait_for_timeout(500)
    shot(pg,"j3_editor_vp",full=False)
    print("editor:", pg.locator("aside.side form").first.inner_text() if pg.locator("aside.side form").count() else "no editor class")
    b.close()
