from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    pg.get_by_role("button", name=re.compile("Use an example")).click(); pg.wait_for_timeout(500)
    pg.wait_for_selector(".typing", state="detached", timeout=60000)
    print("\n".join(transcript(pg)[-2:]))
    # finish intake with defaults
    for _ in range(12):
        if can_build(pg): break
        chips = pg.locator(".quick .chip").all_inner_texts(); print("chips:", chips)
        skip=[c for c in chips if re.search(r"skip|typical|same|about right|none|no\b",c,re.I)]
        say(pg, skip[0] if skip else (chips[0] if chips else "skip"))
        print(transcript(pg)[-1][:300])
    shot(pg,"j2_intake_end")
    print(pg.locator("aside").inner_text()[:3000])
    t=build(pg); print("build", t)
    shot(pg,"j2_plan_vp",full=False); shot(pg,"j2_plan_full")
    print(pg.locator(".plan").inner_text()[:3500])
    print(pg.errors)
    # save state for reuse
    pg.context.storage_state(path="state_j2.json")
    b.close()
