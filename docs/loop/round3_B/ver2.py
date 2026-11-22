from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    # layout at 820 and 390 plan page
    for w,h in []:
        pass
    for w,h in [(390,844)]:
        b, pg = new(p, w, h)
        say(pg, "I'm 47, a teacher in Ohio, married, my husband is 49 and works as an electrician. I make $68,000, he makes $82,000. We have $210,000 saved, spend $6,500 a month. Retire at 60. Two kids, 15 and 12.")
        auto(pg, [(r"mortgage payment","$1,500 a month")])
        shot(pg, f"lay{w}_intake", full=False)
        stp = pg.evaluate("[...document.querySelectorAll('.steps button, header button')].map(e=>e.innerText.trim()+' vis='+(e.getBoundingClientRect().width>0))"); log(w,"steps", stp)
        build(pg)
        shot(pg, f"lay{w}_plan", full=False); shot(pg, f"lay{w}_plan_full")
        log(w,"axe", axe(pg,"p"), overflow(pg))
        sm = pg.evaluate("[...document.querySelectorAll('summary,button,a,input')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.height<32}).map(e=>(e.innerText||e.getAttribute('aria-label')||'').slice(0,25)+' '+Math.round(e.getBoundingClientRect().height))"); log(w,"small", sm)
        if w==1440: pass
        # chips overflow and team talk, adviser
        log(w,"chips", pg.locator(".composer-chips .chip").all_inner_texts())
        pass
        shot(pg, f"lay{w}_adviser", full=False)
        pass
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
