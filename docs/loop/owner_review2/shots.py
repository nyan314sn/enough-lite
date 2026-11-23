"""Owner review 2 screenshots (app on 8020, admin mode)."""
import os
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    for w, h in ((1440, 900), (390, 844)):
        ctx = b.new_context(viewport={"width": w, "height": h}, extra_http_headers={"X-Enough-Test": "1"})
        pg = ctx.new_page()
        pg.goto("http://localhost:8020/")
        pg.wait_for_selector(".bubble-us", timeout=20000)
        pg.wait_for_timeout(600)
        pg.screenshot(path=os.path.join(OUT, f"{w}_page1_greeting.png"))
        pg.goto("http://localhost:8020/admin")
        pg.wait_for_selector("text=Build plan", timeout=20000)
        pg.locator("section.adm-tier:has(#adm-struggling) button:has-text('Build plan')").first.click()
        pg.wait_for_selector(".plan", timeout=120000)
        pg.wait_for_timeout(1500)
        pg.screenshot(path=os.path.join(OUT, f"{w}_plan.png"), full_page=True)
        pg.locator("#scen-add").click()
        pg.wait_for_timeout(700)
        pg.screenshot(path=os.path.join(OUT, f"{w}_compose.png"))
        ctx.close()
    b.close()
