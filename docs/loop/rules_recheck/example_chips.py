from hdr import *
# the built-in example, answered only by clicking the first offered chip at each question
with sync_playwright() as p:
    b, pg = newctx(p, W, H)
    example(pg)
    for i in range(10):
        if can_build(pg): break
        cs = chips(pg)
        P("step", i, "|", last_bot(pg)[-150:].replace("\n", " "), cs)
        if not cs: break
        click_chip(pg, cs[0])
    P("READY", can_build(pg), "| last:", last_bot(pg)[-200:].replace("\n", " "))
    P("errors", pg.errors)
    b.close()
