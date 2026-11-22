from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    c = b.new_context(viewport={"width":1440,"height":900}, extra_http_headers={"X-Enough-Test":"1"})
    pg = c.new_page()
    pg.goto("http://localhost:5182/")
    pg.wait_for_timeout(1500)
    pg.screenshot(path="docs/loop/round1_B/s0.png")
    print(pg.inner_text("body")[:1500])
    b.close()
