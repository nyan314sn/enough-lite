from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    # P1-9 and P2-6 and P1-6 at 390
    b, pg = new(p, 390, 844)
    say(pg, "I'm 30, a software engineer in Austin Texas, I make $95,000. I have $8,000 saved and student loans. Retire at 65.")
    for i in range(14):
        if can_build(pg): break
        last = transcript(pg)[-1]
        a = "skip" if re.search(r"spend|loan|debt|owe", last, re.I) else None
        if a is None:
            chips = pg.locator(".quick .chip").all_inner_texts()
            a = next((c for c in chips if re.search(r"about right|rent|no children|none", c, re.I)), chips[0] if chips else "I rent")
        log("Q:", last[-150:].replace("\n"," "), "->", a); say(pg, a)
    shot(pg,"v9_intake390",full=False)
    pg.get_by_role("button", name=re.compile("Your numbers")).first.click(); pg.wait_for_timeout(500)
    t = pg.locator("#numbers-sheet").inner_text().replace("\n"," | "); i=t.find("Other debts"); log("DEBTS:", t[i:i+300])
    shot(pg,"v9_sheet390",full=False)
    pg.keyboard.press("Escape")
    small = pg.evaluate("[...document.querySelectorAll('summary,button')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.height<32}).map(e=>(e.innerText||e.getAttribute('aria-label')).slice(0,25)+' '+Math.round(e.getBoundingClientRect().height))")
    log("small targets intake:", small)
    b.close()
    # P1-6 bare 62 on mortgage payment
    b, pg = new(p)
    say(pg, "I'm 55, a nurse in Ohio, married, wife 53. We have a mortgage of $150,000. Pay $90,000. Saved $300,000. Spend $5,000 a month. Retire at 65.")
    for i in range(6):
        last = transcript(pg)[-1]
        if re.search(r"mortgage payment", last, re.I): break
        chips = pg.locator(".quick .chip").all_inner_texts(); say(pg, next((c for c in chips if re.search(r"about right|not working",c,re.I)), chips[0] if chips else "skip"))
    log("MORT Q:", transcript(pg)[-1][-120:])
    say(pg, "62"); log("after 62:", transcript(pg)[-1][-300:])
    log("age row:", pg.locator("aside").first.inner_text().replace("\n"," | ")[:400])
    # start over
    pg.get_by_role("button", name="Start over").click(); pg.wait_for_timeout(800)
    log("START OVER:", pg.inner_text("body")[:500].replace("\n"," | "))
    shot(pg,"v7_startover",full=False)
    b.close()
    # layout at 820 and 390 plan page
    for w,h in [(820,1000),(390,844)]:
        pass
    for w,h in [(820,1000),(390,844)]:
        b, pg = new(p, w, h)
        say(pg, "I'm 47, a teacher in Ohio, married, my husband is 49 and works as an electrician. I make $68,000, he makes $82,000. We have $210,000 saved, spend $6,500 a month. Retire at 60. Two kids, 15 and 12.")
        auto(pg, [(r"mortgage payment","$1,500 a month")])
        shot(pg, f"lay{w}_intake", full=False)
        stp = pg.evaluate("[...document.querySelectorAll('.steps button, header button')].map(e=>e.innerText.trim()+' vis='+(e.getBoundingClientRect().width>0))"); log(w,"steps", stp)
        build(pg)
        shot(pg, f"lay{w}_plan", full=False); shot(pg, f"lay{w}_plan_full")
        log(w,"axe", axe(pg,"p"), overflow(pg))
        sm = pg.evaluate("[...document.querySelectorAll('summary,button,a,input')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.height<32}).map(e=>(e.innerText||e.getAttribute('aria-label')||'').slice(0,25).replace(/\n/g,' ')+' '+Math.round(e.getBoundingClientRect().height))"); log(w,"small", sm)
        if w==1440: pass
        # chips overflow and team talk, adviser
        log(w,"chips", pg.locator(".composer-chips .chip").all_inner_texts())
        pg.locator(".team-panel button").nth(2).click(); pg.wait_for_timeout(500)
        shot(pg, f"lay{w}_adviser", full=False)
        log(w,"ADVISER:", pg.locator(".team-panel").inner_text().replace("\n"," | ")[:900])
        # whatif then back
        ask(pg,"Retire at 62"); shot(pg, f"lay{w}_wi", full=False); shot(pg, f"lay{w}_wi_full")
        log(w,"axe wi", axe(pg,"w"), overflow(pg))
        b.close()
    # 1440 chips + talk
    b, pg = new(p)
    say(pg, "I'm 47, a teacher in Ohio, married, my husband is 49 and works as an electrician. I make $68,000, he makes $82,000. We have $210,000 saved, spend $6,500 a month. Retire at 60. Two kids, 15 and 12.")
    auto(pg, [(r"mortgage payment","$1,500 a month")]); build(pg)
    r = pg.evaluate("""()=>{const out=[];document.querySelectorAll('.composer-chips .chip').forEach(c=>{const b=c.getBoundingClientRect(),p=c.parentElement.getBoundingClientRect();out.push([c.innerText,Math.round(b.right),Math.round(p.right),c.scrollWidth>c.clientWidth])});const l=document.querySelector('.talk-log');return {chips:out,talk:l?{sh:l.scrollHeight,ch:l.clientHeight,st:l.scrollTop}:null}}""")
    log("1440 chips/talk:", r)
    shot(pg,"v_chips1440",full=False)
    b.close()
