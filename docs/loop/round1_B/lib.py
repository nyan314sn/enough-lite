import json, re, time, os
from playwright.sync_api import sync_playwright
OUT = os.path.dirname(os.path.abspath(__file__))
AXE = open(os.path.join(OUT, "..", "..", "..", "web", "node_modules", "axe-core", "axe.min.js"), encoding="utf-8").read()
URL = "http://localhost:5182/"

def new(p, w=1440, h=900):
    b = p.chromium.launch(channel="msedge")
    c = b.new_context(viewport={"width": w, "height": h}, extra_http_headers={"X-Enough-Test": "1"})
    pg = c.new_page()
    pg.errors = []
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.errors.append("PAGEERR " + str(e)))
    pg.goto(URL); pg.wait_for_timeout(800)
    return b, pg

def shot(pg, name, full=True):
    path = os.path.join(OUT, name + ".png")
    pg.screenshot(path=path, full_page=full)
    return path

def say(pg, text):
    ta = pg.locator("#chat-input")
    ta.fill(text); ta.press("Enter")
    pg.wait_for_timeout(300)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass
    pg.wait_for_timeout(300)

def transcript(pg):
    return pg.locator(".log .bubble").all_inner_texts()

def can_build(pg):
    return pg.get_by_role("button", name="Build my plan", exact=True).first.is_visible() if pg.get_by_role("button", name="Build my plan", exact=True).count() else False

def intake(pg, first, answers=(), maxturns=14):
    say(pg, first)
    i = 0
    for _ in range(maxturns):
        if can_build(pg): break
        if i < len(answers):
            a = answers[i]; i += 1
        else:
            a = None
        if a is None:
            chips = pg.locator(".quick .chip").all_inner_texts()
            skip = [c for c in chips if re.search(r"skip|typical|same|none|no\b|not sure", c, re.I)]
            a = skip[0] if skip else (chips[0] if chips else "skip")
        say(pg, a)
    return transcript(pg)

def build(pg, timeout=240000):
    t0 = time.time()
    pg.get_by_role("button", name="Build my plan", exact=True).first.click()
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=timeout)
    pg.wait_for_timeout(500)
    return time.time() - t0

def axe(pg, label):
    pg.evaluate(AXE)
    r = pg.evaluate("axe.run(document, {resultTypes:['violations']}).then(r=>r.violations.map(v=>({id:v.id,impact:v.impact,n:v.nodes.length,t:v.nodes.slice(0,2).map(n=>n.target.join(' '))})))")
    return r

def overflow(pg):
    return pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")

def ask(pg, q, wait=90000):
    inp = pg.locator("#ask-input")
    inp.fill(q); inp.press("Enter")
    pg.wait_for_timeout(500)
    try: pg.wait_for_function("!document.querySelector('.turn .spinner')", timeout=wait)
    except Exception: pass
    pg.wait_for_timeout(500)
    return pg.locator(".turn").last.inner_text() if pg.locator(".turn").count() else ""

DEFAULT_RULES = [
 (r"saved in all", "$400k"),
 (r"own your home or rent", "I own it outright"),
 (r"owe anything", "No other debts"),
 (r"children, or pets", "No children and no pets"),
 (r"spend in a year|spend a year now|household spend", "$5,000 a month"),
 (r"how old|your age", "I'm 44"),
 (r"where do you live|which state", "Connecticut"),
 (r"retire", "62"),
 (r"pay|earn|income|make", "$150,000"),
]
def auto(pg, rules=None, maxturns=14, log=False):
    rules = (rules or []) + DEFAULT_RULES
    for _ in range(maxturns):
        if can_build(pg): return True
        last = transcript(pg)[-1]
        a = None
        for rx, ans in rules:
            if re.search(rx, last, re.I):
                a = ans; break
        if a is None or re.search(r"is that about right|right\?$", last, re.I) and not any(re.search(rx,last,re.I) for rx,_ in (rules or [])[:0]):
            chips = pg.locator(".quick .chip").all_inner_texts()
            pick = [c for c in chips if re.search(r"about right|same as now|skip|typical", c, re.I)]
            if re.search(r"is that about right", last, re.I) and pick: a = pick[0]
            elif a is None: a = pick[0] if pick else (chips[0] if chips else "skip")
        if log: print("  Q:", last[-120:].replace("\n"," "), "->", a)
        say(pg, a)
    return can_build(pg)
