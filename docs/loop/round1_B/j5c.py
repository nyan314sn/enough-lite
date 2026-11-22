from lib import *
with sync_playwright() as p:
    b, pg = new(p, 390, 844)
    say(pg, "I'm 30, a software engineer in Austin Texas, I rent. I make $95,000 and my employer matches 4% of my 401k. I have $45,000 in student loans at 6.5% and $8,000 saved. I spend $4,500 a month. Retire at 65.")
    print(transcript(pg)[-1][:900])
    for _ in range(8):
        if can_build(pg): break
        chips = pg.locator(".quick .chip").all_inner_texts(); 
        skip=[c for c in chips if re.search(r"skip|typical|same|about right|none|no\b",c,re.I)]
        a = skip[0] if skip else (chips[0] if chips else "skip")
        if "children" in transcript(pg)[-1]: a = "No children"
        say(pg, a); print("Q:", transcript(pg)[-1][:300])
    build(pg)
    print(pg.locator(".plan").inner_text()[:2200])
    shot(pg,"j5c_plan_phone_full")
    wc=pg.locator(".worth-checking"); print("worth", wc.count())
    # adviser click
    pg.locator(".team-panel button.node").nth(1).evaluate("e=>e.click()"); pg.wait_for_timeout(600)
    shot(pg,"j5c_adviser_phone",full=False)
    print(pg.locator(".team-panel").inner_text()[:1800].replace("\n"," | "))
    pg.keyboard.press("Tab"); 
    print(pg.errors)
    b.close()
