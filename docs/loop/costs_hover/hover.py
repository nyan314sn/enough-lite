import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "round3_B"))
import lib
from lib import *
lib.URL = "http://localhost:8088/"
OUT2 = os.path.dirname(os.path.abspath(__file__))
lib.OUT = OUT2
log = lambda *a: print(*a, flush=True)
def run(p, w):
    b, pg = lib.new(p, w, 900 if w > 600 else 844)
    say(pg, "I'm 40, a teacher in Ohio, married, wife is 38. We make $120,000 together, have $200,000 saved and spend $6,000 a month. Retire at 65.")
    for a in ["That's about right","Not working","I rent","No other debts","No children and no pets"]+["CHIP"]*8:
        if can_build(pg): break
        if a=="CHIP": a = pg.locator(".quick .chip").first.inner_text()
        say(pg,a)
    build(pg)
    svg = pg.locator("figure.costs svg").first
    svg.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    bb = svg.bounding_box(); log("svg", bb)
    for i, f in enumerate([0.15, 0.5, 0.85]):
        if w > 600:
            pg.mouse.move(bb["x"] + bb["width"]*f, bb["y"] + bb["height"]/2)
        else:
            pg.mouse.click(bb["x"] + bb["width"]*f, bb["y"] + bb["height"]/2)
        pg.wait_for_timeout(300)
        log(w, f, pg.locator("[data-testid=costs-tip]").inner_text().replace("\n"," | "))
        pg.locator("figure.costs").screenshot(path=os.path.join(OUT2, f"costs_{w}_{i}.png"))
    svg.focus(); pg.keyboard.press("Home"); pg.keyboard.press("ArrowRight")
    log("key:", pg.locator("[data-testid=costs-live]").inner_text())
    pg.keyboard.press("Escape"); log("after esc tip count", pg.locator("[data-testid=costs-tip]").count())
    pg.keyboard.press("End"); pg.wait_for_timeout(200)
    pg.locator("figure.costs").screenshot(path=os.path.join(OUT2, f"costs_{w}_end.png"))
    log("overflow", overflow(pg), "axe", axe(pg, "x"), "errors", pg.errors)
    b.close()
with sync_playwright() as p:
    run(p, 1440); run(p, 390)
