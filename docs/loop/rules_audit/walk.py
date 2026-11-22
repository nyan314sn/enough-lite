"""Rules-audit walker. Journeys call: start(), intake(), plan_tour(), chat_tour()."""
from lib import *
import lib, builtins
lib.DEFAULT_RULES.insert(0, (r"mortgage payment|monthly payment|payment", "$2,900"))
def P(*a):
    builtins.print(*a, flush=True)
EX = "Use an example"

def last_bot(pg):
    t = transcript(pg)
    return t[-1] if t else ""

def chips(pg):
    return [c.strip() for c in pg.locator(".quick .chip").all_inner_texts()]

def panel(pg):
    return pg.locator("aside, main").first.inner_text().replace("\n", " | ") if pg.locator("aside").count()==0 else pg.locator("aside").first.inner_text().replace("\n"," | ")

def click_chip(pg, text):
    c = pg.locator(".quick .chip", has_text=text).first
    c.click()
    pg.wait_for_timeout(300)
    try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
    except Exception: pass
    pg.wait_for_timeout(300)

def walk(pg, name, rules=None, policy="rules", maxturns=24, clicked=None):
    """policy: rules (use rules, else skip-like chip), chips (click each unseen chip first)."""
    clicked = clicked if clicked is not None else set()
    rules = (rules or []) + DEFAULT_RULES
    for i in range(maxturns):
        if can_build(pg): P(f"[{name}] ready after {i} turns"); return True
        last = last_bot(pg)
        cs = chips(pg)
        P(f"[{name}] BOT: {last[-200:]!r} CHIPS={cs}")
        if policy == "chips":
            new = [c for c in cs if c not in clicked]
            if new:
                clicked.add(new[0]); P(f"[{name}] CLICK CHIP {new[0]!r}")
                click_chip(pg, new[0])
                P(f"[{name}]   -> BOT: {last_bot(pg)[-300:]!r}")
                continue
        a = None
        for rx, ans in rules:
            if re.search(rx, last[-250:], re.I): a = ans; break
        if a is None or (cs and re.search(r"about right", last[-250:], re.I)):
            pick = [c for c in cs if re.search(r"about right|same as now|skip|typical|estimate|not sure|don't know", c, re.I)]
            a = pick[0] if pick else (cs[0] if cs else "skip")
        P(f"[{name}] ANSWER {a!r}")
        say(pg, a)
    return can_build(pg)

def start(p, w=1440, h=900):
    return new(p, w, h)

def build2(pg, timeout=240000):
    t0 = time.time()
    pg.get_by_role("button", name="Build my plan", exact=True).first.click()
    pg.wait_for_timeout(700)
    note = ""
    if pg.locator(".check").count():
        note = pg.locator(".check").first.inner_text().replace("\n"," | ")
        P("CHECK NOTE:", note)
        pg.get_by_role("button", name="Looks right, build my plan").click()
    pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=timeout)
    pg.wait_for_timeout(800)
    P("built in", round(time.time()-t0,1), "s")
    return note

def body(pg): return pg.inner_text("body")
