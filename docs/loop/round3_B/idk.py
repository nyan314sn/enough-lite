from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    b, pg = new(p, 820, 1000)
    say(pg, "hi, I think I want to retire someday but I don't know much")
    log("BOT1:", transcript(pg)[-1]); log("CHIPS:", pg.locator(".quick .chip").all_inner_texts())
    for i in range(24):
        if can_build(pg): break
        say(pg, "I don't know")
        log(f"\n[{i}] BOT:", transcript(pg)[-1][-420:], "\n   CHIPS:", pg.locator(".quick .chip").all_inner_texts())
    log("CANBUILD", can_build(pg))
    shot(pg, "idk_end", full=False)
    side = pg.locator("aside").first
    log("PANEL:", side.inner_text().replace("\n"," | ")[:2500] if side.count() else None)
    log("buttons:", pg.locator("button:visible").all_inner_texts())
    if can_build(pg):
        log("build", build(pg))
        log("PLAN:", pg.locator(".plan").inner_text()[:1800])
        shot(pg,"idk_plan",full=False); shot(pg,"idk_plan_full")
        log("axe", axe(pg,"p"), overflow(pg))
    log(pg.errors)
    b.close()
