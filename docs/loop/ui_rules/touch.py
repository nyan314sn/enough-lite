import sys, os, re
sys.stdout.reconfigure(encoding="utf-8")
sys.argv = ["x"]
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots.py"), encoding="utf-8").read().split("def run(")[0]
exec(src)
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    c = b.new_context(viewport={"width": 390, "height": 844}, extra_http_headers={"X-Enough-Test": "1"})
    pg = c.new_page(); pg.goto(URL); pg.wait_for_timeout(800)
    pg.locator(".quick .chip", has_text="Use an example").click()
    pg.wait_for_selector(".typing", state="detached", timeout=60000); pg.wait_for_timeout(500)
    for _ in range(14):
        if can_build(pg): break
        chips = pg.locator(".quick .chip").all_inner_texts()
        pick = [x for x in chips if re.search(r"about|typical|skip|none|no\b|same", x, re.I)]
        say(pg, pick[0] if pick else chips[0])
    pg.locator(".sheet-open").click(); pg.wait_for_timeout(300)
    print("reset", pg.evaluate("[...document.querySelectorAll('.sheet .reset')].map(e=>Math.round(e.getBoundingClientRect().height))"))
    pg.screenshot(path=os.path.join(HERE, "sheet_390.png"))
    print("overflow", pg.evaluate("[document.documentElement.scrollWidth, innerWidth]"), axe(pg))
    pg.keyboard.press("Escape")
    pg.get_by_role("button", name="Build my plan", exact=True).first.click()
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000); pg.wait_for_timeout(1000)
    pg.get_by_role("button", name="← Change my answers").click(); pg.wait_for_timeout(500)
    pg.locator(".sheet-open").click(); pg.wait_for_timeout(300)
    pg.locator(".sheet button.pen[aria-label^='Change']").first.click(); pg.wait_for_timeout(300)
    pg.locator(".sheet .editor input").first.fill("46"); pg.locator(".sheet .editor button", has_text="Save").click(); pg.wait_for_timeout(2500)
    pg.get_by_role("button", name=re.compile("Your plan")).click(); pg.wait_for_timeout(800)
    print("stale", pg.evaluate("[...document.querySelectorAll('.stale .btn-small')].map(e=>Math.round(e.getBoundingClientRect().height))"), pg.locator(".stale").count())
    pg.screenshot(path=os.path.join(HERE, "stale_390.png"))
    print("overflow", pg.evaluate("[document.documentElement.scrollWidth, innerWidth]"), axe(pg))
    b.close()
