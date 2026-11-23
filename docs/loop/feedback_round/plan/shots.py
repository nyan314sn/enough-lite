r"""After shots, no live AI: the saved /api/plan streams (fixtures/) are replayed through Playwright routes on :8020/admin.
Run: python docs/loop/feedback_round/plan/shots.py [tag]
Households: e11 falls short (struggling), s011 close (average), e27 works (comfortable), e24 below goal + a What If."""
import json
import os
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
TAG = sys.argv[1] if len(sys.argv) > 1 else "after"
SAMPLES = {s["id"]: s for s in json.load(open(os.path.join(FIX, "samples.json")))}
AXE = open(os.path.join(HERE, "..", "..", "..", "..", "web", "node_modules", "axe-core", "axe.min.js"), encoding="utf-8").read()
ASK = open(os.path.join(FIX, "e24_ask_0.txt"), encoding="utf-8").read()


def page(p, sid, w, dark=False):
    b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": w, "height": 900 if w > 600 else 844}, extra_http_headers={"X-Enough-Test": "1"},
                        reduced_motion="no-preference")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    body = open(os.path.join(FIX, f"{sid}_plan_0.txt"), encoding="utf-8").read()
    pg.route("**/api/plan", lambda r: r.fulfill(status=200, headers={"Content-Type": "text/event-stream"}, body=body))
    pg.route("**/api/ask", lambda r: r.fulfill(status=200, headers={"Content-Type": "application/json"}, body=ASK))
    pg.goto("http://localhost:8020/admin")
    pg.evaluate("localStorage.removeItem('enough.moves.v1')")
    if dark:
        pg.get_by_role("button", name="Dark").first.click()
    pg.locator("tr", has_text=SAMPLES[sid]["name"]).first.get_by_role("button", name="Build plan").click()
    pg.wait_for_selector("[data-testid=plan-hero]", timeout=30000)
    pg.wait_for_timeout(1600)
    return b, pg


def shoot(pg, name):
    pg.evaluate("window.scrollTo(0, 0)")
    pg.screenshot(path=os.path.join(HERE, f"{TAG}_{name}_top.png"))
    pg.evaluate("document.querySelectorAll('.ask').forEach(e => { e.style.visibility = 'hidden'; })")
    pg.screenshot(path=os.path.join(HERE, f"{TAG}_{name}_full.png"), full_page=True)
    pg.evaluate("document.querySelectorAll('.ask').forEach(e => { e.style.visibility = ''; })")


def words(pg):
    return pg.evaluate(r"""() => { const el = document.querySelector('article.plan'); const out = [];
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let n = w.nextNode(); n; n = w.nextNode()) { const p = n.parentElement;
        if (!p || p.closest('.sr-only') || p.closest('details:not([open]) > :not(summary)') || !p.getClientRects().length) continue;
        out.push(n.textContent.trim()); }
      return out.join(' ').split(/\s+/).filter(Boolean).length; }""")


def axe(pg):
    pg.evaluate(AXE)
    return pg.evaluate("axe.run(document, {resultTypes:['violations']}).then(r=>r.violations.map(v=>v.id+':'+v.nodes.length+' '+v.nodes.slice(0,2).map(n=>n.target.join(' ')).join(' | ')))")


def small_targets(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('article.plan button, article.plan summary')].filter(e => e.getClientRects().length && !e.closest('details:not([open]) > :not(summary)'))
      .map(e => [e.className || e.tagName, Math.round(e.getBoundingClientRect().height)]).filter(([, h]) => h < 44)""")


def run(p, sid, w, dark=False, whatif=False):
    b, pg = page(p, sid, w, dark)
    name = f"{sid}_{w}{'_dark' if dark else ''}"
    print(name, "verdict:", pg.locator(".verdict").inner_text(), "| ring:", pg.locator("[data-testid=ring]").get_attribute("aria-label"),
          "| words shown:", words(pg), "| overflow:", pg.evaluate("document.documentElement.scrollWidth > window.innerWidth"), "| errors:", pg.errors)
    print("   axe:", axe(pg), "| targets < 44px:", small_targets(pg) if w < 600 else "-")
    shoot(pg, name)
    if sid == "s011" and w == 1440:
        ticks = pg.locator(".move-tick")
        for i in range(ticks.count()):
            ticks.nth(i).click(); pg.wait_for_timeout(250)
        pg.evaluate("document.querySelectorAll('.ask').forEach(e => { e.style.visibility = 'hidden'; })")
        pg.locator("[data-testid=plan-hero]").scroll_into_view_if_needed()
        pg.locator("article.plan").screenshot(path=os.path.join(HERE, f"{TAG}_{name}_ticked.png"))
        print("   ticked:", pg.locator("[data-testid=moves-count]").inner_text(), "| stored:", pg.evaluate("localStorage.getItem('enough.moves.v1')"))
    if whatif:
        tries = pg.locator("[data-testid=moves-extra] button")
        tries.first.click()
        pg.wait_for_selector("#tab-1", timeout=30000)
        pg.wait_for_timeout(1800)
        print(name, "what if:", pg.locator("#plan-h").inner_text(), "| ready:", pg.locator("[data-testid=vs-ready]").inner_text() if pg.locator("[data-testid=vs-ready]").count() else "-")
        shoot(pg, name + "_whatif")
        pg.get_by_role("button", name="Compare").click(); pg.wait_for_timeout(500)
        pg.screenshot(path=os.path.join(HERE, f"{TAG}_{name}_compare.png"))
    b.close()


if __name__ == "__main__":
    with sync_playwright() as p:
        for sid in ("e11", "s011", "e27"):
            run(p, sid, 1440)
            run(p, sid, 1440, dark=True)
            run(p, sid, 390)
        run(p, "e24", 1440, whatif=True)
        run(p, "e24", 390, whatif=True)
