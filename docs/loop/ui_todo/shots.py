import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
URL = "http://localhost:8020/"


def ctx(p, w, h):
    b = p.chromium.launch(channel="msedge")
    c = b.new_context(viewport={"width": w, "height": h}, extra_http_headers={"X-Enough-Test": "1"})
    pg = c.new_page()
    pg.errors = []
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.errors.append("PAGEERR " + str(e)))
    return b, pg


def shot(pg, name, full=True, el=None):
    path = os.path.join(OUT, name + ".png")
    if el is not None:
        el.scroll_into_view_if_needed()
        el.screenshot(path=path)
    else:
        pg.screenshot(path=path, full_page=full)
    print("saved", path)


def build_sample(pg, tier_idx_word):
    pg.goto(URL + "?admin"); pg.wait_for_timeout(1500)
    rows = pg.locator(".adm-tier").filter(has_text=tier_idx_word).locator("tbody tr")
    rows.first.get_by_role("button", name="Build plan").click()
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000)
    pg.wait_for_selector("[data-testid=cost-session]", state="attached", timeout=30000)
    pg.wait_for_timeout(1500)


with sync_playwright() as p:
    for w, h in ((1440, 900), (390, 844)):
        tag = str(w)
        # 1. first visit, page 1: How it works opens by itself
        b, pg = ctx(p, w, h)
        pg.goto(URL); pg.wait_for_timeout(1200)
        shot(pg, f"01_how_it_works_first_visit_{tag}", full=False)
        b.close()

        # 2. a short plan (struggling), the cost block, and a What If
        b, pg = ctx(p, w, h)
        build_sample(pg, "Struggling")
        pg.evaluate("window.scrollTo(0,0)")
        shot(pg, f"02_short_plan_{tag}", full=False)
        shot(pg, f"02_short_plan_full_{tag}")
        cost = pg.locator("[data-testid=cost-block]")
        if w < 860:
            tog = pg.locator("#team-h button")
            if tog.count() and tog.get_attribute("aria-expanded") == "false":
                tog.click(); pg.wait_for_timeout(300)
        pg.locator("details.cost-detail summary").click(); pg.wait_for_timeout(200)
        shot(pg, f"05_cost_block_{tag}", el=cost)
        # What If on a short plan
        pg.locator("#ask-input").fill("What if I retire at 60"); pg.locator("#ask-input").press("Enter")
        pg.wait_for_selector("[data-testid=whatif]", timeout=120000)
        pg.wait_for_timeout(800)
        shot(pg, f"04_what_if_{tag}")
        shot(pg, f"05_cost_block_after_whatif_{tag}", el=pg.locator("[data-testid=cost-block]"))
        # How it works from page 2
        pg.evaluate("window.scrollTo(0,0)")
        pg.locator("button.how-link").click(); pg.wait_for_timeout(400)
        shot(pg, f"01_how_it_works_page2_{tag}", full=False)
        print(tag, "short errors:", pg.errors)
        b.close()

        # 3. a working plan (comfortable)
        b, pg = ctx(p, w, h)
        build_sample(pg, "Comfortable")
        pg.evaluate("window.scrollTo(0,0)")
        shot(pg, f"03_working_plan_{tag}", full=False)
        print(tag, "working errors:", pg.errors)
        b.close()
