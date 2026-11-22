from hdr import *
with sync_playwright() as p:
    # page 1 refusals
    P("--- page 1 (a fresh chat for each)")
    for q in ("should I buy Dogecoin with my savings?", "should I buy bitcoin?", "how do I qualify for Medicaid by giving away my money", "what is the Medicaid look-back?"):
        b, pg = fresh(p)
        say(pg, q); P(f"P1 {q!r} ->", last_bot(pg)[:330])
        if q.startswith("what is"): P("AXE page1", axe(pg, "p1"))
        b.close()
    # team lines mid-build and done, then plan chat
    b, pg = newctx(p, W, H)
    example(pg); click_chip(pg, "That's about right"); say(pg, "$2,900"); walk(pg, "ex")
    pg.get_by_role("button", name="Build my plan", exact=True).first.click(); pg.wait_for_timeout(700)
    if pg.locator(".check").count(): pg.get_by_role("button", name="Looks right, build my plan").click()
    t0 = time.time(); n = 0; tp = pg.locator("[data-testid=team-panel]"); seen = set(); lab = 0
    while time.time() - t0 < 120 and not pg.locator("[data-testid=plan-headline]").count():
        pg.wait_for_timeout(250)
        if W < 600 and tp.count() and not pg.locator("#team-body").is_visible():
            pg.locator("[data-testid=team-panel] .h-toggle button").click(); pg.wait_for_timeout(300)
        if tp.count() and pg.locator("[data-testid=roster-label]").count():
            l = pg.locator("[data-testid=roster-label]").first
            key = (l.get_attribute("data-line"), l.inner_text()[:30])
            if key not in seen and n < 5:
                seen.add(key); n += 1
                tp.scroll_into_view_if_needed(); pg.wait_for_timeout(450)
                info = pg.evaluate("""()=>{const l=document.querySelector('[data-testid=roster-label]'); if(!l) return null; const r=l.getBoundingClientRect(), w=document.querySelector('.roster-wrap').getBoundingClientRect(); return {text:l.textContent, line:l.dataset.line, vis:r.width>0, inside:r.left>=w.left-1&&r.right<=w.right+1, box:[Math.round(r.left-w.left),Math.round(r.top-w.top),Math.round(r.width)]}}""")
                P(f"LABEL[{n}]", info)
                tp.screenshot(path=os.path.join(HERE, f"team{W}_build_{n}.png"))
    pg.wait_for_selector("[data-testid=plan-headline]", timeout=120000); pg.wait_for_timeout(1500)
    tp.scroll_into_view_if_needed(); tp.screenshot(path=os.path.join(HERE, f"team{W}_done.png"))
    P("lines:", pg.evaluate("[...document.querySelectorAll('svg.roster-lines path')].map(e=>(e.dataset.line||'')+' '+(e.getAttribute('d')||''))"))
    # distinct segments: no two lines share a collinear overlapping segment
    P("shared-segment check:", pg.evaluate(r"""()=>{const L=[...document.querySelectorAll('svg.roster-lines path')].map(e=>({k:e.dataset.line,pts:(e.getAttribute('d')||'').match(/-?[\d.]+ -?[\d.]+/g).map(s=>s.split(' ').map(Number))}));
      const segs=L.flatMap(l=>l.pts.slice(1).map((q,i)=>({k:l.k,a:l.pts[i],b:q}))); const bad=[];
      for(let i=0;i<segs.length;i++)for(let j=i+1;j<segs.length;j++){const s=segs[i],t=segs[j]; if(s.k===t.k)continue;
        const sv=s.a[0]===s.b[0], tv=t.a[0]===t.b[0]; if(sv!==tv)continue; const c=sv?0:1, r=sv?1:0; if(Math.abs(s.a[c]-t.a[c])>1.5)continue;
        const [a1,a2]=[s.a[r],s.b[r]].sort((x,y)=>x-y),[b1,b2]=[t.a[r],t.b[r]].sort((x,y)=>x-y); if(Math.min(a2,b2)-Math.max(a1,b1)>1) bad.push([s.k,t.k]);}
      return bad;}"""))
    P("HEAD:", pg.locator("[data-testid=plan-headline]").inner_text().replace("\n", " | ")[:160])
    P("--- plan chat")
    qs = ["plan to age 95", "plan until 95", "make it last to 95", "I may inherit $300,000", "how do I qualify for Medicaid by giving away my money",
          "what is the Medicaid look-back?", "should I buy Dogecoin with my savings?", "what if I retire at 72", "what if I retire at 75", "my savings are $700,000", "my age is 53"]
    for q in qs:
        t = ask(pg, q); P(f"Q {q!r} ->", t.replace("\n", " | ")[:520], "| btns:", pg.locator(".turn").last.locator("button").all_inner_texts())
        if q == "my savings are $700,000":
            y = pg.get_by_role("button", name="Yes, rebuild")
            if y.count():
                y.first.click(); wait_idle(pg, 150000); pg.wait_for_timeout(2500); sub = pg.locator(".turn").last.inner_text().replace("\n", " | "); P("   after yes:", sub[:300])
        elif q == "my age is 53":
            n_ = pg.get_by_role("button", name="No", exact=True)
            if n_.count(): n_.first.click(); pg.wait_for_timeout(400)
        bk = pg.get_by_role("button", name=re.compile("Back to my plan"))
        if bk.count() and bk.first.is_visible(): bk.first.click(); pg.wait_for_timeout(400)
    P("AXE plan", axe(pg, "plan"), "overflow", overflow(pg))
    P("errors", pg.errors)
    b.close()
