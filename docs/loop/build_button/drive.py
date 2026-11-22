import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "round3_B"))
import lib
lib.URL = "http://localhost:8096/"
lib.OUT = HERE
from playwright.sync_api import sync_playwright

def count_btn(pg):
    return pg.get_by_role("button", name="Build my plan", exact=True).count()

with sync_playwright() as p:
    for w, h, tag in ((1440, 900, "desktop"), (390, 844, "phone")):
        b, pg = lib.new(p, w, h)
        pg.set_viewport_size({"width": w, "height": h})
        lib.say(pg, "I'm 44 and live in Connecticut")
        btn = pg.get_by_role("button", name="Build my plan", exact=True)
        print(tag, "buttons:", count_btn(pg), "aria-disabled:", btn.first.get_attribute("aria-disabled"))
        print(tag, "why:", pg.locator(".build-why").first.inner_text())
        if tag == "phone":
            print("chat input visible:", pg.locator("#chat-input").is_visible(), pg.locator("#chat-input").bounding_box(), "bar:", pg.locator(".phone-bar").bounding_box())
        lib.shot(pg, f"{tag}_1_disabled", full=False)
        if tag == "phone":
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); pg.wait_for_timeout(300)
            print("scrolled: input", pg.locator("#chat-input").bounding_box(), "bar", pg.locator(".phone-bar").bounding_box())
            lib.shot(pg, "phone_1b_disabled_scrolled", full=False)
            pg.evaluate("window.scrollTo(0, 0)")
        print(tag, "axe disabled:", lib.axe(pg, "d"))
        if tag == "phone":
            pg.get_by_role("button", name="Your numbers").first.click(); pg.wait_for_timeout(500)
            print("sheet buttons:", count_btn(pg))
            lib.shot(pg, "phone_sheet_disabled", full=False)
            print("axe sheet:", lib.axe(pg, "s"))
            pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        ok = lib.auto(pg)
        print(tag, "ready:", ok, "buttons:", count_btn(pg), "aria-disabled:", btn.first.get_attribute("aria-disabled"))
        print(tag, "why:", pg.locator(".build-why").first.inner_text(), "| live:", pg.locator(".build [role=status]").first.inner_text())
        print(tag, "size:", btn.first.bounding_box())
        lib.shot(pg, f"{tag}_2_enabled", full=False)
        print(tag, "axe ready:", lib.axe(pg, "r"))
        if tag == "phone":
            pg.get_by_role("button", name="Your numbers").first.click(); pg.wait_for_timeout(500)
            print("sheet buttons:", count_btn(pg))
            lib.shot(pg, "phone_sheet_enabled", full=False)
            print("axe sheet:", lib.axe(pg, "s"))
        if tag == "phone":
            pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        btn.first.click(); pg.wait_for_timeout(600)
        print(tag, "check shown:", pg.locator(".check").count(), "| focus:", pg.evaluate("document.activeElement.textContent"), "| buttons:", count_btn(pg))
        print(tag, "note:", pg.locator(".check-h").first.inner_text(), "| highlighted rows:", pg.locator(".field.is-check").count(), "visible:", pg.locator(".field.is-check:visible").count())
        print(tag, "check btn sizes:", [pg.get_by_role("button", name=n).first.bounding_box()["height"] for n in ("Looks right, build my plan", "Let me change something")])
        lib.shot(pg, f"{tag}_3_check", full=False)
        print(tag, "axe check:", lib.axe(pg, "c"))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        print(tag, "after Esc check:", pg.locator(".check").count(), "highlight:", pg.locator(".field.is-check").count())
        print(tag, "errors:", pg.errors, "overflow:", lib.overflow(pg))
        b.close()
