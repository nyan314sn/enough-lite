import sys, os, re, json
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
AXE = open(os.path.join(HERE, "..", "..", "..", "web", "node_modules", "axe-core", "axe.min.js"), encoding="utf-8").read()
URL = "http://localhost:8092/"
log = lambda *a: print(*a, flush=True)


def axe(pg):
    pg.evaluate(AXE)
    return pg.evaluate("axe.run(document, {resultTypes:['violations']}).then(r=>r.violations.map(v=>({id:v.id,n:v.nodes.length,t:v.nodes.slice(0,2).map(n=>n.target.join(' '))})))")


def say(pg, text):
    ta = pg.locator("#chat-input")
    ta.fill(text); ta.press("Enter")
    pg.wait_for_timeout(300)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass
    pg.wait_for_timeout(300)


def can_build(pg):
    b = pg.get_by_role("button", name="Build my plan", exact=True)
    return b.count() > 0 and b.first.is_visible()


def run(p, w):
    h = 900 if w > 600 else 844
    b = p.chromium.launch(channel="msedge")
    c = b.new_context(viewport={"width": w, "height": h}, extra_http_headers={"X-Enough-Test": "1"})
    pg = c.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.goto(URL); pg.wait_for_timeout(800)
    res = {"w": w}
    res["header"] = pg.locator("header .note").inner_text()
    pg.locator(".quick .chip", has_text="Use an example").click()
    pg.wait_for_selector(".typing", state="detached", timeout=60000); pg.wait_for_timeout(500)
    for _ in range(14):
        if can_build(pg): break
        chips = pg.locator(".quick .chip").all_inner_texts()
        pick = [x for x in chips if re.search(r"about|typical|skip|none|no\b|same", x, re.I)]
        say(pg, pick[0] if pick else (chips[0] if chips else "skip"))
    log(w, "can build", can_build(pg))

    # page 1: editor open
    if w <= 600:
        pg.locator(".sheet-open").click(); pg.wait_for_timeout(300)
        scope = pg.locator(".sheet")
    else:
        scope = pg.locator(".side")
    pen = scope.locator("button.pen[aria-label^='Change']").first
    pen.click(); pg.wait_for_timeout(400)
    res["editor_open"] = scope.locator(".editor").count()
    res["typing_visible"] = pg.evaluate("[...document.querySelectorAll('textarea, input:not([type=hidden]):not([type=checkbox]):not([type=radio])')].filter(e=>e.offsetParent!==null).length")
    res["note"] = pg.locator(".composer-note").count() and pg.locator(".composer-note").inner_text()
    res["focus_in_editor"] = pg.evaluate("!!document.activeElement.closest('.editor')")
    pg.screenshot(path=os.path.join(HERE, f"editor_open_{w}.png"))
    res["axe_editor"] = axe(pg)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    res["focus_after_cancel"] = pg.evaluate("document.activeElement.getAttribute('aria-label') || document.activeElement.tagName")
    res["composer_back"] = pg.locator("#chat-input").count()
    if w <= 600:
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    # reset size check
    sizes = pg.evaluate("[...document.querySelectorAll('.reset')].filter(e=>e.offsetParent!==null).map(e=>Math.round(e.getBoundingClientRect().height))")
    res["reset_heights"] = sizes
    res["overflow1"] = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    res["axe_page1"] = axe(pg)

    # build, mid-run
    pg.get_by_role("button", name="Build my plan", exact=True).first.click()
    pg.wait_for_selector(".team-panel", timeout=60000)
    mid = None
    for i in range(12):
        pg.wait_for_timeout(500)
        working = pg.locator(".node.working").count(); done = pg.locator(".node.done").count()
        if working and done >= 2 and mid is None:
            pg.locator(".team-panel").screenshot(path=os.path.join(HERE, f"team_mid_{w}.png")); mid = (working, done)
            break
    res["mid"] = mid
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000); pg.wait_for_timeout(1500)
    pg.locator(".team-panel").screenshot(path=os.path.join(HERE, f"team_done_{w}.png"))
    res["done_nodes"] = pg.locator(".node.done").count()
    res["stale_btn"] = pg.evaluate("[...document.querySelectorAll('.stale .btn-small')].map(e=>Math.round(e.getBoundingClientRect().height))")

    # savings chart keyboard
    svg = pg.locator("figure.chart:not(.costs) svg").first
    svg.scroll_into_view_if_needed(); pg.wait_for_timeout(300)
    svg.focus(); pg.keyboard.press("Home"); pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowRight")
    res["savings_live"] = pg.locator("[data-testid=savings-live]").inner_text()
    res["savings_label"] = svg.get_attribute("aria-label")[-60:]
    pg.wait_for_timeout(200)
    pg.locator("figure.chart:not(.costs)").first.screenshot(path=os.path.join(HERE, f"savings_key_{w}.png"))
    pg.keyboard.press("End"); res["savings_end"] = pg.locator("[data-testid=savings-live]").inner_text()
    pg.keyboard.press("Escape"); res["savings_esc"] = pg.locator("[data-testid=savings-live]").inner_text()
    res["axe_plan"] = axe(pg)
    res["overflow2"] = pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    pg.screenshot(path=os.path.join(HERE, f"plan_{w}.png"), full_page=True)
    res["errors"] = errs
    b.close()
    log(json.dumps(res, indent=1))


with sync_playwright() as p:
    run(p, 1440); run(p, 390)
