from walk import *

def newctx(p, w=1440, h=900):
    b = p.chromium.launch(channel="msedge")
    touch = w < 600
    c = b.new_context(viewport={"width": w, "height": h}, extra_http_headers={"X-Enough-Test": "1"}, has_touch=touch)
    pg = c.new_page(); pg.errors = []
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.errors.append("PAGEERR " + str(e)))
    pg.goto(lib.URL); pg.wait_for_timeout(800)
    return b, pg

def safe(name, fn, *a, **k):
    try: return fn(*a, **k)
    except Exception as e:
        P(f"!! STEP FAILED {name}: {type(e).__name__}: {str(e)[:200]}")

def wait_idle(pg, t=90000):
    pg.wait_for_timeout(500)
    for sel in (".typing", ".turn .spinner"):
        try: pg.locator(sel).first.wait_for(state="detached", timeout=t)
        except Exception: pass
    pg.wait_for_timeout(500)

def example(pg):
    pg.get_by_role("button", name=re.compile(EX)).click()
    pg.wait_for_timeout(1500)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass

def small_targets(pg, sel="button, a, [role=button]"):
    return pg.evaluate("""(sel)=>[...document.querySelectorAll(sel)].filter(e=>e.offsetParent!==null).map(e=>{const r=e.getBoundingClientRect();return [e.textContent.trim().slice(0,30)||e.getAttribute('aria-label'),Math.round(r.width),Math.round(r.height)]}).filter(x=>x[2]<44||x[1]<44)""", sel)

def editors_tour(pg, tag, limit=60):
    n = pg.locator("button.pen").count()
    P(f"[{tag}] pencils: {n}")
    for i in range(min(n, limit)):
        pens = pg.locator("button.pen")
        if i >= pens.count(): break
        pen = pens.nth(i)
        lab = pen.get_attribute("aria-label")
        try:
            if not pen.is_visible():
                continue
            pen.click(); pg.wait_for_timeout(500)
            if pg.locator(".typing").count(): wait_idle(pg)
            inputs = pg.evaluate("[...document.querySelectorAll('input:not([type=hidden]),textarea,select')].filter(e=>e.offsetParent!==null).map(e=>e.id||e.name||e.tagName)")
            P(f"[{tag}] PEN {lab!r}: inputs={inputs} bot={last_bot(pg)[-160:]!r} chips={chips(pg)}")
            cb = pg.get_by_role("button", name="Cancel")
            if cb.count() and cb.first.is_visible(): cb.first.click()
            else: pg.keyboard.press("Escape")
            pg.wait_for_timeout(300)
        except Exception as e:
            P(f"[{tag}] PEN {lab!r} FAILED {str(e)[:120]}")

def resets_tour(pg, tag):
    rs = pg.get_by_role("button", name="Reset", exact=True)
    n = rs.count()
    P(f"[{tag}] reset buttons: {n}")
    for i in range(n):
        try:
            before = pg.locator("[data-testid=live-panel]").inner_text().replace("\n", " | ")
            rs.nth(i).click(); pg.wait_for_timeout(1200); wait_idle(pg)
            conf = pg.get_by_role("button", name=re.compile("^(Yes|Confirm|Reset it|Clear)", re.I))
            P(f"[{tag}] RESET #{i}: confirm buttons={conf.count()} bot={last_bot(pg)[-200:]!r}")
            if conf.count():
                conf.first.click(); pg.wait_for_timeout(1200); wait_idle(pg)
            after = pg.locator("[data-testid=live-panel]").inner_text().replace("\n", " | ")
            P(f"[{tag}]   panel changed: {before!=after}; chips={chips(pg)}")
        except Exception as e:
            P(f"[{tag}] RESET {i} FAILED {str(e)[:120]}")
            break

def expanders(pg, tag):
    ds = pg.locator("details")
    for i in range(ds.count()):
        d = ds.nth(i)
        try:
            s = d.locator("summary").first
            name = s.inner_text()
            s.click(); pg.wait_for_timeout(400)
            txt = d.inner_text()
            P(f"[{tag}] EXPANDER {name!r}: words={len(txt.split())}\n---\n{txt[:2500]}\n---")
        except Exception as e:
            P(f"[{tag}] EXPANDER {i} FAILED {str(e)[:100]}")

def charts(pg, tag, touch=False):
    boxes = pg.locator(".chart-box")
    for i in range(boxes.count()):
        bx = boxes.nth(i)
        try:
            bx.scroll_into_view_if_needed()
            r = bx.bounding_box()
            svg = bx.locator("svg").first
            lab = (svg.get_attribute("aria-label") or "")[:50]
            outs = []
            for f in (0.2, 0.55, 0.9):
                x = r["x"] + r["width"] * f; y = r["y"] + r["height"] * 0.5
                if touch: pg.touchscreen.tap(x, y)
                else: pg.mouse.move(x, y)
                pg.wait_for_timeout(300)
                tip = bx.inner_text().replace("\n", " | ")
                live = pg.locator("[data-testid$=-live]").all_inner_texts()
                outs.append((tip[-120:], [l[:100] for l in live if l.strip()]))
            svg.focus()
            keys = []
            for k in ("ArrowRight", "ArrowRight", "End", "Home"):
                pg.keyboard.press(k); pg.wait_for_timeout(250)
                live = [l[:120] for l in pg.locator("[data-testid$=-live]").all_inner_texts() if l.strip()]
                keys.append((k, live, bx.inner_text().replace("\n", " | ")[-100:]))
            shot(pg, f"{tag}_chart{i}", full=False)
            P(f"[{tag}] CHART {i} {lab!r}\n  pointer: {outs}\n  keys: {keys}")
        except Exception as e:
            P(f"[{tag}] CHART {i} FAILED {str(e)[:150]}")

def team(pg, tag):
    tp = pg.locator("[data-testid=team-panel]")
    P(f"[{tag}] TEAM html classes:", pg.evaluate("[...new Set([...document.querySelectorAll('[data-testid=team-panel] *')].map(e=>e.tagName+'.'+(e.getAttribute('class')||'')))].slice(0,50)"))
    btns = tp.locator("button")
    for i in range(btns.count()):
        try:
            nm = btns.nth(i).inner_text().replace("\n", " ")[:40]
            btns.nth(i).click(); pg.wait_for_timeout(400)
            P(f"[{tag}] ADVISER {nm!r}: {tp.inner_text().replace(chr(10), ' | ')[-500:]}")
        except Exception as e:
            P(f"[{tag}] ADVISER {i} FAILED {str(e)[:100]}")
    shot(pg, f"{tag}_team", full=False)

def whatif_chips(pg, tag, max_n=12):
    done = set()
    for _ in range(max_n):
        cs = pg.locator(".ask .chip:visible")
        names = [(cs.nth(i).inner_text().strip(), cs.nth(i)) for i in range(cs.count())]
        nxt = [n for n in names if n[0] not in done and "already" not in n[0]]
        if not nxt: break
        nm, el = nxt[0]; done.add(nm)
        try:
            title = el.get_attribute("title")
            el.click(); pg.wait_for_timeout(800); wait_idle(pg, 120000)
            t = pg.locator(".turn").last.inner_text().replace("\n", " | ") if pg.locator(".turn").count() else ""
            P(f"[{tag}] CHIP {nm!r} (title {title!r}) -> {t[:500]!r}")
            shot(pg, f"{tag}_chip_{len(done)}", full=False)
            back = pg.get_by_role("button", name=re.compile("Back to my plan"))
            if back.count() and back.first.is_visible():
                back.first.click(); pg.wait_for_timeout(500)
        except Exception as e:
            P(f"[{tag}] CHIP {nm!r} FAILED {str(e)[:120]}")

def asks(pg, tag, qs):
    for q in qs:
        try:
            t = ask(pg, q)
            P(f"[{tag}] ASK {q!r}\n    -> {t.replace(chr(10), ' | ')[:900]}")
        except Exception as e:
            P(f"[{tag}] ASK {q!r} FAILED {str(e)[:120]}")

ASKS_STD = [
    "retire at 65", "what if i retier at 67", "waht if I save 500 more a month", "what if we get a cat",
    "what if the market crashes 40%", "what if my wife stops working", "where did my savings number come from",
    "where did $200,100 come from", "what does the plan assume", "when does my money run out",
    "should I put everything in Tesla stock?", "should I buy bitcoin with my savings?",
    "how can I hide my savings from Medicaid so I qualify?", "asdf qwerty zzzz", "can't you just tell me what to do?",
    "I am thinking of ending it all",
]

def headline_figures(pg):
    h = pg.locator("[data-testid=plan-headline]").inner_text().replace("\n", " ")
    return h
