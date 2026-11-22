"""Live check of "The analysis" on a local instance (port 8090, ENOUGH_TEST_MODE=1): five households, 1440 and 390 px.
Run: python docs/loop/analysis/live.py [names...]"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "round3_B"))
import lib  # noqa: E402
from lib import auto, axe, build, can_build, overflow, say, sync_playwright  # noqa: E402

lib.URL = "http://localhost:8090/"
OUT = os.path.dirname(os.path.abspath(__file__))
log = lambda *a: print(*a, flush=True)

H = {
    "bus": ("I'm 52, a bus driver in Detroit Michigan, divorced, two kids 16 and 14. I make $52,000 and spend $4,200 a month. "
            "I have $30,000 saved. I rent. I want to retire at 58.", [(r"own your home or rent", "I rent for $1,300 a month")]),
    "retired_couple": ("We're 71 and 68, both retired, in North Carolina. We have $1.1 million saved and our home is paid off. "
                       "Social Security is $56,000 a year together and I get a $24,000 a year pension. We spend about $85,000 a year.",
                       [(r"own your home or rent", "We own it outright"), (r"retire", "We are both retired")]),
    "single_parent": ("I'm 34, a single mom in Georgia with two kids, 3 and 7. I earn $52,000, rent for $1,040 a month, have $10,500 saved "
                      "and spend about $3,800 a month. I'd like to retire at 66.", []),
    "gap10": ("I'm 58 and my wife is 48, in Ohio. I make $95,000 and she makes $60,000. We have $590,000 saved, owe $120,000 on the "
              "mortgage at $1,400 a month, no kids, no pets. We spend $7,500 a month. I want to retire at 65.", []),
    "high_earner": ("I'm 41, single, in California, earning $310,000. I have $1.2 million saved, a $620,000 mortgage at $3,020 a month, "
                    "no kids, and spend about $11,800 a month. I want to retire at 60.", []),
}


def shot_el(pg, sel, name):
    pg.locator(sel).first.screenshot(path=os.path.join(OUT, name + ".png"))


def run(p, name, w):
    text, rules = H[name]
    b, pg = lib.new(p, w, 900 if w > 600 else 844)
    say(pg, text)
    ok = auto(pg, rules, maxturns=16)
    log(f"[{name} {w}] ready to build: {ok}")
    t = build(pg)
    log(f"[{name} {w}] plan built in {t:.1f}s; headline:", pg.locator("[data-testid=plan-headline]").inner_text())
    d = pg.locator("[data-testid=plan-analysis]")
    log(f"[{name} {w}] analysis present: {d.count()}, open: {d.evaluate('e => e.open') if d.count() else None}")
    if not d.count():
        b.close(); return
    d.locator("summary").first.click(); pg.wait_for_timeout(400)
    txt = d.inner_text().replace("\n", " | ")
    log(f"[{name} {w}] TEXT:", txt[:2500])
    for cid, tip in (("sure-chart", "sure-tip"), ("sources-chart", "sources-tip")):
        svg = pg.locator(f"[data-testid={cid}]")
        if not svg.count():
            continue
        svg.scroll_into_view_if_needed(); pg.wait_for_timeout(200)
        bb = svg.bounding_box()
        if w > 600:
            pg.mouse.move(bb["x"] + bb["width"] * 0.55, bb["y"] + bb["height"] / 2)
        else:
            pg.mouse.click(bb["x"] + bb["width"] * 0.55, bb["y"] + bb["height"] / 2)
        pg.wait_for_timeout(250)
        log(f"[{name} {w}] {cid} hover:", pg.locator(f"[data-testid={tip}]").inner_text().replace("\n", " | ") if pg.locator(f"[data-testid={tip}]").count() else "NO TIP")
        pg.locator(f"[data-testid={cid}]").locator("xpath=ancestor::figure").screenshot(path=os.path.join(OUT, f"{name}_{w}_{cid}.png"))
        svg.focus(); pg.keyboard.press("Home"); pg.keyboard.press("ArrowRight")
        live = cid.split("-")[0] + "-live"
        log(f"[{name} {w}] {cid} key:", pg.locator(f"[data-testid={live}]").inner_text())
        pg.keyboard.press("Escape")
    # the costs chart's readout lists the parts
    c = pg.locator("figure.costs svg").first
    if c.count():
        c.scroll_into_view_if_needed(); bb = c.bounding_box()
        pg.mouse.move(bb["x"] + bb["width"] * 0.4, bb["y"] + bb["height"] / 2); pg.wait_for_timeout(250)
        if pg.locator("[data-testid=costs-tip]").count():
            log(f"[{name} {w}] costs tip:", pg.locator("[data-testid=costs-tip]").inner_text().replace("\n", " | "))
            pg.locator("figure.costs").screenshot(path=os.path.join(OUT, f"{name}_{w}_costs.png"))
    pg.mouse.move(1, 1)
    d.scroll_into_view_if_needed()
    shot_el(pg, "[data-testid=plan-analysis]", f"{name}_{w}_analysis")
    log(f"[{name} {w}] overflow {overflow(pg)} axe {axe(pg, name)} errors {pg.errors}")
    b.close()


if __name__ == "__main__":
    names = sys.argv[1:] or list(H)
    with sync_playwright() as p:
        for n, w in [(n, 1440) for n in names] + [(x, 390) for x in ("bus", "retired_couple") if x in names]:
            try:
                run(p, n, w)
            except Exception as e:      # one household that fails never stops the others
                log(f"[{n} {w}] FAILED: {str(e)[:300]}")
