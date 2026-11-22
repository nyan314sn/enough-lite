"""Replay of the rules-audit findings on :8114 (build2 from walk.py): the example doctor and the retired couple."""
from tour import *
import lib
from pathlib import Path
OUT = Path(__file__).parent

def details_text(pg, name):
    d = pg.locator("details", has_text=name).first
    d.locator("summary").first.click(); pg.wait_for_timeout(300)
    return d.inner_text().replace("\n", " | ")

def ex_run(p):
    b, pg = newctx(p)
    example(pg); walk(pg, "ex"); build2(pg)
    P("HEADLINE:", pg.locator("[data-testid=plan-headline]").inner_text())
    P("ASSUMPTIONS:", details_text(pg, "Assumptions")[:1600])
    P("CHANGE BUTTONS:", pg.locator(".assumption-changes button").all_inner_texts())
    P("ANALYSIS:", details_text(pg, "The analysis")[:1400])
    bx = pg.locator(".chart-box").first; bx.scroll_into_view_if_needed(); r = bx.bounding_box()
    for f in (0.17, 0.3, 0.55):
        pg.mouse.move(r["x"] + r["width"] * f, r["y"] + r["height"] * 0.5); pg.wait_for_timeout(250)
        P("CHART0 tip:", " | ".join(t for t in pg.locator("[role=tooltip], .tip").all_inner_texts() if t)[:300])
    pg.screenshot(path=str(OUT / "ex_chart0_after.png"), full_page=False)
    for q in ["what if I retire at 63", "what if I retire at 64", "what if I retire at 65", "waht if I save 500 more a month",
              "Save 15% of my pay", "what if my wife stops working", "what does the plan assume"]:
        P(f"ASK {q!r} ->", ask(pg, q).replace("\n", " | ")[:600])
    pg.locator(".assumption-changes button", has_text="Social Security").first.click(); pg.wait_for_timeout(2500)
    P("CLAIM BTN ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400])
    click_chip(pg, "start age to 70"); pg.wait_for_timeout(1500)
    P("CLAIM 70 ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400])
    click_chip(pg, "Yes, rebuild"); pg.wait_for_timeout(4000)
    try: pg.locator(".turn .spinner").first.wait_for(state="detached", timeout=90000)
    except Exception: pass
    P("CLAIM YES ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400])
    P("HEADLINE after:", pg.locator("[data-testid=plan-headline]").inner_text())
    pg.screenshot(path=str(OUT / "ex_after_claim.png"), full_page=False)
    P("errors", pg.errors); b.close()

def retired_run(p):
    b, pg = newctx(p)
    lib.DEFAULT_RULES.insert(0, (r"children", "No children"))
    say(pg, "We're Frank, 68, and Linda, 66, both retired and already claiming Social Security. We live in Sarasota, Florida. We own our house outright. Frank gets $2,400 a month and Linda $1,500. We have $640,000 saved, mostly in IRAs, and spend about $5,500 a month.")
    walk(pg, "retired"); build2(pg)
    P("R HEADLINE:", pg.locator("[data-testid=plan-headline]").inner_text())
    P("R IDEAS:", [t for t in pg.locator("button").all_inner_texts() if re.search(r"save|spend|retire|market", t, re.I)][:12])
    for q in ["retire at 65", "waht if I save 500 more a month", "what if I retire at 70"]:
        P(f"R ASK {q!r} ->", ask(pg, q).replace("\n", " | ")[:500])
    P("errors", pg.errors); b.close()

with sync_playwright() as p:
    safe("ex", ex_run, p)
    safe("retired", retired_run, p)
