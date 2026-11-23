r"""Before shots + fixtures: build three sample plans live on :8020 (admin, test header), save the /api/plan stream and one What If reply.
Run: python docs/loop/feedback_round/plan/capture.py e09 e24 e27"""
import json
import os
import sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
URL = "http://localhost:8020/admin"
SAMPLES = {s["id"]: s for s in json.load(open(os.path.join(FIX, "samples.json")))}


def run(p, sid, whatif=False):
    name = SAMPLES[sid]["name"]
    b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, extra_http_headers={"X-Enough-Test": "1"})
    pg = ctx.new_page()
    bodies = {}

    def on_resp(r):
        if "/api/plan" in r.url or "/api/ask" in r.url:
            try:
                bodies.setdefault(r.url.split("/api/")[1], []).append(r.text())
            except Exception as e:
                print("body err", e)
    pg.on("response", on_resp)
    pg.goto(URL)
    pg.locator("tr", has_text=name).first.get_by_role("button", name="Build plan").click()
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=os.path.join(HERE, f"before_{sid}_1440.png"), full_page=True)
    print(sid, "headline:", pg.locator("[data-testid=plan-headline]").inner_text())
    if whatif:
        btn = pg.locator(".starting-points button, [data-testid=an-levers] button")
        if btn.count() == 0:
            pg.locator("#ask-input").fill("What if I retire 2 years later?")
            pg.keyboard.press("Enter")
        else:
            pg.locator("[data-testid=plan-analysis] summary").first.click()
            btn.first.click()
        pg.wait_for_selector("#tab-1", timeout=120000)
        pg.wait_for_timeout(1500)
        pg.screenshot(path=os.path.join(HERE, f"before_{sid}_whatif_1440.png"), full_page=True)
    for k, v in bodies.items():
        for i, t in enumerate(v):
            with open(os.path.join(FIX, f"{sid}_{k.split('?')[0]}_{i}.txt"), "w", encoding="utf-8") as f:
                f.write(t)
    b.close()


if __name__ == "__main__":
    with sync_playwright() as p:
        for a in sys.argv[1:]:
            sid, _, w = a.partition(":")
            run(p, sid, whatif=bool(w))
