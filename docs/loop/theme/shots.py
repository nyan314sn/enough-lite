"""Royal Indigo screenshots of the live app (http://localhost:8020), light and dark at 1440 px, light at 390 px.
Each live plan is built once; the header toggle switches the theme between shots. Needs the conda python and msedge."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

OUT = os.path.dirname(os.path.abspath(__file__))
URL = "http://localhost:8020/"


def ctx(p, w, h, scheme="light"):
    b = p.chromium.launch(channel="msedge")
    c = b.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, extra_http_headers={"X-Enough-Test": "1"})
    pg = c.new_page()
    pg.errors = []
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.errors.append("PAGEERR " + str(e)))
    return b, pg


def theme(pg, want):
    if pg.evaluate("document.documentElement.dataset.theme") != want:
        pg.locator("button.theme-toggle").click(); pg.wait_for_timeout(350)
    assert pg.evaluate("document.documentElement.dataset.theme") == want


def shot(pg, name, themes=("light", "dark"), w=1440, full=False, el=None):
    for t in themes:
        theme(pg, t)
        path = os.path.join(OUT, f"{name}_{t}_{w}.png")
        if el is not None:
            e = pg.locator(el); e.scroll_into_view_if_needed(); e.screenshot(path=path)
        else:
            pg.screenshot(path=path, full_page=full)
        print("saved", path)


def to_admin(pg):
    pg.goto(URL + "?admin"); pg.wait_for_timeout(1500)


def row(pg, tier):
    return pg.locator(".adm-tier").filter(has_text=tier).locator("tbody tr").first


def build(pg, tier):
    to_admin(pg)
    row(pg, tier).get_by_role("button", name="Build plan").click()
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000)
    pg.wait_for_selector("[data-testid=cost-session]", state="attached", timeout=30000)
    pg.wait_for_timeout(1500)


with sync_playwright() as p:
    # 1440: page 1 with the panel filled (a sample opened, no AI call)
    b, pg = ctx(p, 1440, 900)
    to_admin(pg)
    row(pg, "Comfortable").get_by_role("button", name="Open in app").click(); pg.wait_for_timeout(2500)
    shot(pg, "01_page1_panel")
    print("page1 errors", pg.errors); b.close()

    # 1440: a short plan (struggling), its What If and the token costs
    b, pg = ctx(p, 1440, 900)
    build(pg, "Struggling")
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "02_short_plan")
    shot(pg, "02_short_plan_full", full=True)
    pg.locator("details.cost-detail summary").click(); pg.wait_for_timeout(200)
    shot(pg, "05_token_costs", el="[data-testid=cost-block]")
    pg.locator("#ask-input").fill("What if I retire at 60"); pg.locator("#ask-input").press("Enter")
    pg.wait_for_selector("[data-testid=whatif]", timeout=120000); pg.wait_for_timeout(800)
    shot(pg, "04_what_if")
    shot(pg, "04_what_if_full", full=True)
    print("short errors", pg.errors); b.close()

    # 1440: a working plan with the charts and the analysis open
    b, pg = ctx(p, 1440, 900)
    build(pg, "Comfortable")
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "03_working_plan")
    d = pg.locator("[data-testid=plan-analysis]")
    if d.count() and d.get_attribute("open") is None:
        d.locator("summary").click(); pg.wait_for_timeout(600)
    shot(pg, "03_working_plan_full", full=True)
    pg.evaluate("document.querySelector('.ask').style.display='none'")
    shot(pg, "03_working_plan_analysis", el="[data-testid=plan-analysis]")
    print("working errors", pg.errors); b.close()

    # 390: light, page 1 and the plan
    b, pg = ctx(p, 390, 844)
    to_admin(pg)
    row(pg, "Struggling").get_by_role("button", name="Open in app").click(); pg.wait_for_timeout(2000)
    shot(pg, "06_page1", themes=("light",), w=390)
    build(pg, "Struggling")
    pg.evaluate("window.scrollTo(0,0)")
    shot(pg, "07_plan", themes=("light",), w=390)
    shot(pg, "07_plan_full", themes=("light",), w=390, full=True)
    print("phone errors", pg.errors); b.close()
