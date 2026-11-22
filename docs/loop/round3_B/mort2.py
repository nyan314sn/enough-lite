from lib import *
log = lambda *a: print(*a, flush=True)
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, "I'm 45, an accountant in Illinois, married, my wife is 43. We make $160,000, have $300,000 saved, spend $8,000 a month. We own our home with a $300,000 mortgage at 4%. Retire at 62.")
    for a in ["That's about right", "$150,000", "$12,500 a month", "$12,500 a month", "yes", "yes it is right", "Yes"]:
        say(pg, a); log("U:", a, "\nBOT:", transcript(pg)[-1][-400:], "\nCHIPS:", pg.locator(".quick .chip").all_inner_texts())
    shot(pg, "mort_loop", full=False)
    b.close()
