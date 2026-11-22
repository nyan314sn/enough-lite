import sys, os, re, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "round3_B"))
import lib
lib.URL = "http://localhost:8082/"
lib.OUT = HERE
from playwright.sync_api import sync_playwright

def run(p, w, h):
    b, pg = lib.new(p, w, h)
    lib.say(pg, "I am a nurse, single, 58, in Ohio, pay $78,000, want to retire at 62")
    lib.auto(pg)
    pg.get_by_role("button", name="Build my plan", exact=True).first.click()
    shots = 0
    for i in range(120):
        pg.wait_for_timeout(250)
        if pg.locator(".rline.working").count() and shots < 2 and pg.locator(".node.working").count():
            if pg.locator("#team-body").is_visible():
                lib.shot(pg, f"mid_{w}_{shots}", full=False); shots += 1
                print(w, "classes", pg.evaluate("[...document.querySelectorAll('.rline')].map(l=>l.dataset.line+':'+l.getAttribute('class').split(' ').slice(1).join('+'))"))
        if pg.locator("[data-testid=plan-headline], .alert").count(): break
    pg.wait_for_timeout(1500)
    if w <= 860:
        btn = pg.locator(".h-toggle button")
        if btn.count() and btn.get_attribute("aria-expanded") == "false": btn.click(); pg.wait_for_timeout(600)
    pg.locator(".team-panel").scroll_into_view_if_needed()
    pg.locator(".team-panel").screenshot(path=os.path.join(HERE, f"after_{w}.png"))
    lib.shot(pg, f"after_{w}_full")
    print(w, "paths", pg.evaluate("[...document.querySelectorAll('.rline')].map(l=>l.getAttribute('d'))"))
    print(w, "axe", lib.axe(pg, "x"), "errors", pg.errors, "overflow", lib.overflow(pg))
    b.close()

with sync_playwright() as p:
    for w, h in ((1440, 900), (820, 1000), (390, 844)):
        run(p, w, h)
