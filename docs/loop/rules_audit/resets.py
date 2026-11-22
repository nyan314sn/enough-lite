from tour import *

def groups_state(pg):
    return pg.evaluate("""()=>[...document.querySelectorAll('[id^=lp-grp-]')].map(g=>{const sec=g.closest('section,div');return g.id.replace('lp-grp-','')+': '+(sec? sec.innerText.replace(/\\n+/g,' | ').slice(0,260):'')})""")

with sync_playwright() as p:
    b, pg = newctx(p)
    example(pg)
    walk(pg, "rs")
    P("RESET BUTTON LABELS:", pg.evaluate("[...document.querySelectorAll('button')].filter(b=>/reset/i.test(b.textContent+(b.getAttribute('aria-label')||''))).map(b=>[b.textContent.trim(),b.getAttribute('aria-label'),Math.round(b.getBoundingClientRect().height)])"))
    n = pg.locator("button", has_text="Reset").count()
    names = pg.evaluate("[...document.querySelectorAll('button')].filter(b=>b.textContent.trim()==='Reset').map(b=>b.getAttribute('aria-label')||b.title)")
    P("sections with reset:", names)
    for i, nm in enumerate(names):
        btn = pg.locator("button", has_text=re.compile("^Reset$")).first
        before = panel(pg)
        btn.click(); pg.wait_for_timeout(1000); wait_idle(pg)
        shot(pg, f"rs_{i}_click", full=False)
        after = panel(pg)
        P(f"--- RESET {nm}: confirm UI: {pg.locator('text=Clear').count()} ; bot={last_bot(pg)[-300:]!r}; chips={chips(pg)}")
        yes = pg.get_by_role("button", name=re.compile("^Yes"))
        if yes.count():
            P("   confirm buttons:", pg.locator('button:visible').all_inner_texts()[:8]); yes.first.click(); pg.wait_for_timeout(1200); wait_idle(pg)
            after = panel(pg)
        P("   PANEL BEFORE:", before[:1500]); P("   PANEL AFTER:", after[:1500])
        P("   bot now:", last_bot(pg)[-300:], chips(pg))
        shot(pg, f"rs_{i}_after", full=False)
        if i >= 1: break
    # Start over: keep
    pg.get_by_role("button", name="Start over").first.click(); pg.wait_for_timeout(700)
    P("START OVER dialog:", pg.locator("body").inner_text()[:500].replace("\n"," | "))
    shot(pg, "rs_startover_dialog", full=False)
    pg.get_by_role("button", name="Keep my answers").click(); pg.wait_for_timeout(500)
    P("after keep: transcript len", len(transcript(pg)))
    pg.get_by_role("button", name="Start over").first.click(); pg.wait_for_timeout(700)
    pg.get_by_role("button", name=re.compile("Yes, clear")).click(); pg.wait_for_timeout(1500)
    P("after clear: transcript", transcript(pg), "panel", panel(pg)[:300])
    shot(pg, "rs_startover_done", full=False)
    P("after clear: chips", chips(pg), "build enabled?", can_build(pg))
    b.close()
