"""Scenario tabs: live check on the running app (port 8020, admin mode). One struggling household, three What Ifs, tabs, Compare.
Run: python docs/loop/scenario_tabs/shots.py"""
import os
import sys
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "round2")
URL = "http://localhost:8020/admin"
TIER = sys.argv[1] if len(sys.argv) > 1 else "struggling"
log = lambda *a: print(*a, flush=True)


def shot(pg, name, full=True):
    pg.screenshot(path=os.path.join(OUT, name + ".png"), full_page=full)
    log("saved", name)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, extra_http_headers={"X-Enough-Test": "1"})
    pg = ctx.new_page()
    pg.goto(URL)
    pg.wait_for_selector("text=Build plan", timeout=20000)
    sec = pg.locator(f"section.adm-tier:has(#adm-{TIER})")
    sec.locator("button:has-text('Build plan')").first.click()
    pg.wait_for_selector(".plan", timeout=120000)
    pg.wait_for_timeout(1500)
    log("baseline:", pg.locator("#plan-h").inner_text())
    shot(pg, "1440_light_baseline")
    # three What Ifs, from the chips
    chips = pg.locator(".ask .quick button")
    labels = [chips.nth(i).inner_text() for i in range(chips.count())]
    log("chips:", labels)
    made = 0
    for lab in labels:
        if made == 3:
            break
        if pg.locator(".scen-tab").count() > 3:
            break
        pg.locator(".ask .quick button", has_text=lab).first.click()
        for _ in range(240):
            if pg.locator("[role=tab]").count() == made + 2:
                break
            pg.wait_for_timeout(500)
        made += 1
        pg.wait_for_timeout(800)
        log("tab added:", pg.locator("[role=tab]").all_inner_texts())
        pg.locator(".ask .quick button").first.wait_for(timeout=60000)
    pg.wait_for_timeout(1000)
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "1440_light_whatif_tab")
    pg.locator("[role=tab]").nth(1).click()
    pg.wait_for_timeout(500)
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "1440_light_whatif_tab1")
    # team panel follows the tab: open an adviser
    pg.locator("[data-agent=markets]").click()
    pg.evaluate("window.scrollTo(0,0)")
    pg.screenshot(path=os.path.join(OUT, "1440_light_team_panel.png"))
    pg.get_by_role("button", name="Compare").click()
    pg.wait_for_timeout(500)
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "1440_light_compare", full=False)
    # dark
    pg.locator("[role=tab]").nth(2).click()
    pg.get_by_role("button", name="Dark").click() if pg.get_by_role("button", name="Dark").count() else pg.locator(".theme-toggle, button[aria-label*='theme' i]").first.click()
    pg.wait_for_timeout(500)
    log("theme:", pg.evaluate("document.documentElement.dataset.theme"))
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "1440_dark_whatif_tab")
    pg.get_by_role("button", name="Compare").click()
    pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "1440_dark_compare", full=False)
    # light again, mobile
    pg.locator(".theme-toggle, button[aria-label*='theme' i]").first.click()
    pg.set_viewport_size({"width": 390, "height": 844})
    pg.wait_for_timeout(600)
    pg.locator("[role=tab]").nth(1).click()
    pg.wait_for_timeout(500)
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "390_light_whatif_tab")
    pg.get_by_role("button", name="Compare").click()
    pg.wait_for_timeout(400)
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "390_light_compare", full=False)
    ov = pg.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    log("horizontal overflow at 390:", ov)
    wide = pg.evaluate("""() => { const W = window.innerWidth; const out = []; for (const e of document.querySelectorAll("body *")) { const r = e.getBoundingClientRect(); if (r.right > W + 1 && r.width > 0) { let p = e.parentElement, clipped = false; while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === "auto" || o === "scroll" || o === "hidden") { clipped = true; break; } p = p.parentElement; } if (!clipped) out.push(e.tagName + "." + e.className + " " + Math.round(r.right)); } } return out.slice(0, 15); }""")
    log("elements past the right edge:", wide)
    log("admin link present:", pg.locator("button:has-text(\"Admin\")").count())
    b.close()
