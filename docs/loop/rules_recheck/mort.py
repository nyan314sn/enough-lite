from hdr import *
def to_mort(pg):
    example(pg)
    click_chip(pg, "That's about right")
    P("  at:", last_bot(pg)[-160:], chips(pg))
with sync_playwright() as p:
    for mode in ("chip", "typed_yes", "typed_yes_plain", "number", "skip"):
        b, pg = newctx(p, W, H); to_mort(pg)
        P("== mode", mode)
        if mode == "chip": click_chip(pg, "Yes, that's about right")
        elif mode == "typed_yes": say(pg, "Yes, that's about right")
        elif mode == "typed_yes_plain": say(pg, "yes")
        elif mode == "number": say(pg, "$2,900")
        else: say(pg, "skip")
        P("  after:", last_bot(pg)[-300:], chips(pg), "ready", can_build(pg))
        b.close()
