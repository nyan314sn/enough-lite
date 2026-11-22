from lib import *
with sync_playwright() as p:
    b, pg = new(p, 390, 844)
    tr = intake(pg, "I'm 30, a software engineer in Austin Texas, I rent. I make $95,000 and my employer matches 4% of my 401k. I have $45,000 in student loans at 6.5% and $8,000 saved. Retire at 65.",
        ["That's about right","I rent","Student loans, $45,000 at 6.5%"])
    print("\n".join(tr[-8:]))
    shot(pg,"j5_intake_phone",full=False)
    print("overflow intake", overflow(pg))
    # open sheet
    pg.get_by_role("button", name=re.compile("Your numbers")).first.click(); pg.wait_for_timeout(600)
    shot(pg,"j5_sheet_phone",full=False)
    print("sheet text:", pg.locator("#numbers-sheet").inner_text()[:1800].replace("\n"," | "))
    print("axe sheet", axe(pg,"sheet"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    print("canbuild", can_build(pg))
    for _ in range(6):
        if can_build(pg): break
        chips = pg.locator(".quick .chip").all_inner_texts(); 
        skip=[c for c in chips if re.search(r"skip|typical|same|about right|none|no\b",c,re.I)]
        say(pg, skip[0] if skip else (chips[0] if chips else "skip"))
    print("canbuild", can_build(pg))
    t = build(pg); print("build", t)
    shot(pg,"j5_plan_phone",full=False); shot(pg,"j5_plan_phone_full")
    print(pg.locator(".plan").inner_text()[:2500])
    print("overflow plan", overflow(pg))
    print("axe plan", axe(pg,"plan"))
    # small tap targets
    small = pg.evaluate("""[...document.querySelectorAll('button,a,input,[role=button],summary')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.height<40||r.width<40)}).map(e=>(e.innerText||e.getAttribute('aria-label')||e.tagName).slice(0,30)+' '+Math.round(e.getBoundingClientRect().width)+'x'+Math.round(e.getBoundingClientRect().height))""")
    print("small targets:", small)
    # what if on phone
    print(ask(pg,"Retire at 60")[:300]); pg.wait_for_timeout(600)
    shot(pg,"j5_wi_phone",full=False)
    print("overflow wi", overflow(pg))
    print("axe wi", axe(pg,"wi"))
    # adviser tap
    pg.evaluate("window.scrollTo(0,0)")
    btns = pg.locator(".team-panel button")
    print("adviser buttons", btns.count())
    pg.locator(".team-panel button").first.scroll_into_view_if_needed(); pg.locator(".team-panel button").nth(1).click(); pg.wait_for_timeout(500)
    shot(pg,"j5_adviser_phone",full=False)
    print(pg.locator(".team-panel").inner_text()[:1500].replace("\n"," | "))
    print(pg.errors)
    b.close()
