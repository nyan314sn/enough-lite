from tour import *

def pay_line(pg):
    t = panel(pg)
    m = re.search(r"Your pay[^|]*\|[^|]*\|?\s*\$[\d,]+", t)
    return t[t.find("MONEY IN"):t.find("MONEY IN")+220] if "MONEY IN" in t else t[:200]

with sync_playwright() as p:
    b, pg = newctx(p)
    example(pg)
    walk(pg, "ed")
    P("READY. money:", pay_line(pg))
    # editor on pay
    pg.locator("button.pen[aria-label='Change Your pay']").click(); pg.wait_for_timeout(500)
    P("EDITOR buttons:", pg.locator("button:visible").all_inner_texts()[:40])
    P("inputs:", pg.evaluate("[...document.querySelectorAll('input,textarea')].filter(e=>e.offsetParent!==null).map(e=>[e.id,e.value,e.getAttribute('aria-label')])"))
    shot(pg, "ed_pay_open", full=False)
    inp = pg.locator("#lp-ed-pay_per_year"); inp.fill("400000"); inp.press("Enter"); pg.wait_for_timeout(1500); wait_idle(pg)
    P("after save pay=400000:", pay_line(pg), "| bot:", last_bot(pg)[-250:])
    shot(pg, "ed_pay_saved", full=False)
    # invalid values
    for label, sel, val in (("Your age", "#lp-ed-age", "150"), ("Your age", "#lp-ed-age", "abc"), ("Retirement age", "#lp-ed-retire_age", "80"), ("Retirement age", "#lp-ed-retire_age", "40"), ("Your pay", "#lp-ed-pay_per_year", "-5")):
        pg.locator(f"button.pen[aria-label='Change {label}']").click(); pg.wait_for_timeout(400)
        i = pg.locator(sel); i.fill(val); i.press("Enter"); pg.wait_for_timeout(1200); wait_idle(pg)
        P(f"EDIT {label}={val}: money={pay_line(pg)}; panel row: {[l for l in panel(pg).split(' | ') if l.strip()][ :0]} err={pg.locator('[role=alert], .err, .error').all_inner_texts()} bot={last_bot(pg)[-200:]!r}")
        P("   panel:", panel(pg)[panel(pg).find('WHAT WE HAVE'):][:420])
        cb = pg.get_by_role("button", name="Cancel")
        if cb.count() and cb.first.is_visible(): cb.first.click(); pg.wait_for_timeout(300)
    shot(pg, "ed_invalid", full=False)
    # chat change needing confirmation
    for msg in ("change my pay to 90000", "actually I retire at 66"):
        say(pg, msg)
        P(f"CHAT CHANGE {msg!r}: bot={last_bot(pg)[-300:]!r} chips={chips(pg)}")
        P("   panel unchanged yet? money:", pay_line(pg))
        shot(pg, "ed_chat_change", full=False)
        yes = [c for c in chips(pg) if re.search(r"^yes|confirm|apply", c, re.I)]
        P("   yes chips:", yes)
        if yes:
            click_chip(pg, yes[0]); P("   after yes: money:", pay_line(pg), "bot:", last_bot(pg)[-200:])
    b.close()
