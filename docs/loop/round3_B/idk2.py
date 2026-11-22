from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    b, pg = new(p, 820, 1000)
    say(pg, "hi, I think I want to retire someday but I don't know much")
    for a in ["I don't know","skip","I don't know","not sure","dunno","idk"]+["I don't know"]*20:
        if can_build(pg): break
        say(pg, a)
        log(f"U: {a}\n  BOT:", transcript(pg)[-1][-330:].replace("\n"," "), "\n  CHIPS:", pg.locator(".quick .chip").all_inner_texts())
    log("CANBUILD", can_build(pg))
    shot(pg, "idk2_end", full=False)
    log("PANEL:", pg.locator("aside").first.inner_text().replace("\n"," | ")[:3000])
    if can_build(pg):
        log("build", build(pg))
        log("PLAN:", pg.locator(".plan").inner_text()[:2500])
        shot(pg,"idk_plan",full=False); shot(pg,"idk_plan_full")
        log("axe", axe(pg,"p"), overflow(pg))
    log(pg.errors)
    b.close()
