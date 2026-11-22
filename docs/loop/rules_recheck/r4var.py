from hdr import *
with sync_playwright() as p:
    b, pg = newctx(p, W, H)
    say(pg, "I'm 41, divorced, a paralegal in Seattle, Washington making $67,000. I have two kids: Ava is 9 and Ben is 4. Ava will go to a private college and I will pay half; Ben will go to community college. I have a beagle. I owe $22,000 on student loans at 5% and $6,000 on a credit card at 22%. I rent for $1,900 a month and have $60,000 saved. I want to retire at 64. I need to keep health insurance before Medicare. My dad lives with me and I give him $500 a month.")
    P("BOT:", last_bot(pg)[:900])
    pn = panel(pg)
    for key in ("Children", "College: child", "Pets", "Other debts", "Home", "Helping parents", "Health", "Your pay", "Retirement age", "Partner"):
        for m in re.finditer(re.escape(key), pn):
            P("PANEL", key, "::", pn[m.start():m.start()+200]); break
        else: P("PANEL", key, ":: (none)")
    P("pencils", [l for l in pg.locator("button.pen").evaluate_all("els=>els.map(e=>e.getAttribute('aria-label'))")])
    b.close()
