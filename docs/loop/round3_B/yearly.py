from lib import *
log = lambda *a: print(*a, flush=True)
def panel(pg):
    return pg.locator("aside").first.inner_text().replace("\n"," | ")
def row(pg, label):
    t = panel(pg); i = t.find(label); return t[i:i+420]
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 40, a teacher in Ohio, married, wife is 38. We make $120,000 together, have $200,000 saved and spend $6,000 a month. Retire at 65.")
    for a in ["That's about right","Not working","I rent","No other debts","No children and no pets","That's about right"]:
        if can_build(pg): break
        say(pg,a)
    say(pg, "That's about right")
    log("LAST:", transcript(pg)[-1][-200:], pg.locator(".quick .chip").all_inner_texts())
    log("BEFORE savings:", row(pg,"Savings"))
    log("BEFORE yearly:", row(pg,"Yearly saving"))
    shot(pg,"yearly_before",full=False)
    pg.get_by_role("button", name=re.compile("Change Yearly saving")).first.click(); pg.wait_for_timeout(600)
    shot(pg,"yearly_editor",full=False)
    log("inputs:", pg.evaluate("[...document.querySelectorAll('input,textarea,select')].map(e=>e.tagName+'#'+e.id+' '+e.type+' vis='+(e.offsetParent!==null)+' ph='+(e.placeholder||''))"))
    log("buttons:", pg.locator("button:visible").all_inner_texts()[:40])
    b.close()
