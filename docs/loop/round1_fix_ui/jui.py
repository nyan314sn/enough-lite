from lib import *

def run(w, h, tag):
    with sync_playwright() as p:
        b, pg = new(p, w, h)
        say(pg, "I'm 47, a teacher in Ohio, married, my husband is 49 and works as an electrician. I make $68,000, he makes $82,000. We have $210,000 saved, spend $6,500 a month. Retire at 60. Two kids, 15 and 12.")
        print(tag, "canbuild", auto(pg, log=False), flush=True)
        print(tag, "note on intake:", pg.locator(".note").count())
        build(pg)
        print(tag, "note on plan:", pg.locator(".note").count(), "header h:", pg.evaluate("document.querySelector('header.top').getBoundingClientRect().height"))
        print(tag, "ask bar h:", pg.evaluate("document.querySelector('.ask').getBoundingClientRect().height"), "of", h)
        print(tag, "chips:", pg.locator(".ask .chip").all_inner_texts())
        shot(pg, f"ui_{tag}_plan", full=False); pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(200); shot(pg, f"ui_{tag}_top", full=False)
        if w < 600 and pg.locator(".ideas-toggle").count():
            pg.locator(".ideas-toggle").click(); pg.wait_for_timeout(200)
            shot(pg, f"ui_{tag}_chips_open", full=False)
        ask(pg, "Retire at 62")
        print(tag, "history:", pg.locator(".history").inner_text().replace("\n", " | "))
        print(tag, "tried chips:", pg.locator(".chip.tried").count())
        print(tag, "new tags:", pg.locator(".new-tag").count(), "family heading:", pg.get_by_role("heading", name="Family moments").count())
        shot(pg, f"ui_{tag}_wi", full=False)
        # change flow
        print(ask(pg, "actually my pay is 150000")[:200])
        print(ask(pg, "yes")[:200])
        print(tag, "stale show buttons:", pg.get_by_role("button", name=re.compile("Show this What If")).count(), "gone lines:", pg.locator("[data-testid=whatif-gone]").count())
        print(tag, "cites after change:", pg.locator(".turn .cites").count())
        shot(pg, f"ui_{tag}_changed", full=False)
        # stale: go back, edit, return
        pg.get_by_role("button", name="← Change my answers").click(); pg.wait_for_timeout(500)
        print(tag, "chips after back:", pg.locator(".chat .quick .chip").count(), "link h:", pg.evaluate("document.querySelector('.step-link')?.getBoundingClientRect().height"))
        shot(pg, f"ui_{tag}_back", full=False)
        print(tag, "axe:", axe(pg, "intake"))
        pg.get_by_role("button", name="2 · Your plan →").click(); pg.wait_for_timeout(400)
        print(tag, "axe plan:", axe(pg, "plan"), "overflow", overflow(pg))
        # failed question
        pg.route("**/api/ask", lambda r: r.fulfill(status=500, body='{"detail":"Traceback boom"}', content_type="application/json"))
        inp = pg.locator("#ask-input"); inp.fill("how much in an IRA"); inp.press("Enter"); pg.wait_for_timeout(800)
        print(tag, "error:", pg.locator(".turn .alert").inner_text().replace("\n", " "), "| box:", inp.input_value())
        shot(pg, f"ui_{tag}_error", full=False)
        print(pg.errors)
        b.close()

run(1440, 900, "desk")
run(390, 844, "phone")
