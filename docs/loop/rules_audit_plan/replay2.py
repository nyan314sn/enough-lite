"""Replay, part 2: the Social Security start-age change from the Assumptions, with its confirm, on :8114."""
from tour import *
from pathlib import Path
OUT = Path(__file__).parent

def run(p):
    b, pg = newctx(p)
    example(pg); walk(pg, "ex"); build2(pg)
    P("HEADLINE:", pg.locator("[data-testid=plan-headline]").inner_text())
    d = pg.locator("[data-testid=plan-assumptions]")
    d.locator("summary").first.click(); pg.wait_for_timeout(300)
    d.locator(".assumption-changes button", has_text="Social Security").first.click()
    pg.wait_for_timeout(1500)
    P("CLAIM BTN ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400])
    click_chip(pg, "start age to 70")
    P("CLAIM 70 ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400])
    click_chip(pg, "Yes, rebuild")
    try: pg.locator(".turn .spinner").first.wait_for(state="detached", timeout=90000)
    except Exception: pass
    pg.wait_for_timeout(2000)
    P("CLAIM YES ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400])
    P("HEADLINE after:", pg.locator("[data-testid=plan-headline]").inner_text())
    d = pg.locator("[data-testid=plan-assumptions]")
    if d.count():
        P("CHANGE BUTTONS after:", d.locator(".assumption-changes button").all_inner_texts())
    pg.screenshot(path=str(OUT / "ex_after_claim.png"), full_page=False)
    d.locator(".assumption-changes button", has_text="retirement age").first.click(); pg.wait_for_timeout(1500)
    P("RETIRE BTN ->", pg.locator(".turn").last.inner_text().replace("\n", " | ")[:400])
    P("errors", pg.errors); b.close()

with sync_playwright() as p:
    safe("claim", run, p)
