import sys
from tour import *

J = {}
# name: dict(first, rules, policy, width, full)
J["ex"] = dict(first=None, rules=[], policy="rules", w=1440, full=True)
J["renter"] = dict(
    first="I'm 29, single, a software tester in Austin, Texas. I rent for $1,700 a month. I make $78,000, have $22,000 saved and $41,000 in student loans at 6.5%. I'd like to retire at 62.",
    rules=[(r"rent", "$1,700 a month")], policy="rules", w=1440, full=True)
J["retired"] = dict(
    first="We're Frank, 68, and Linda, 66, both retired and already claiming Social Security. We live in Sarasota, Florida. We own our house outright. Frank gets $2,400 a month and Linda $1,500. We have $640,000 saved, mostly in IRAs, and spend about $5,500 a month.",
    rules=[], policy="rules", w=1440, full=True)
J["widow"] = dict(
    first="I'm Dolores, 62, a widow in Cleveland, Ohio. My husband died two years ago. I work part time as a school secretary and make $34,000. I have $210,000 saved, I own my home with no mortgage, and I spend about $3,300 a month. I get a survivor benefit and I want to stop working at 65.",
    rules=[], policy="rules", w=1440, full=True)
J["parent"] = dict(
    first="I'm a single mom, 38, a nurse in Denver, Colorado earning $92,000. I have two kids, a girl of 8 and a boy of 5. I rent for $2,300 a month and have $48,000 saved. I want the girl to go to a state college and the boy to a private one. I'd like to retire at 63.",
    rules=[(r"rent", "$2,300 a month")], policy="rules", w=1440, full=True)
J["gap"] = dict(
    first="I'm 58, married to Maria who is 48. I'm an electrician in Ohio making $96,000 and she is a teacher making $58,000. We have $510,000 saved and a mortgage of $140,000. We want to retire when I'm 63.",
    rules=[], policy="rules", w=1440, full=True)
J["idk"] = dict(
    first="I'm 50, I live in Georgia.",
    rules=[(r"how old|your age", "I'm 50")], policy="skipall", w=1440, full=True)
J["long"] = dict(
    first=("My name is not important but I am 47, my husband is 49. We live in Portland, Oregon with our daughter who is 12 and our cat. I'm a dental hygienist making $88,000, he is a carpenter making $71,000. "
           "We have $330,000 in 401(k)s, $45,000 in a savings account and about $20,000 in an IRA. Our house is worth $620,000 and we owe $310,000 at 3.1% with payments of $2,150 a month. "
           "We have a car loan of $14,000 at 5%. We spend about $7,000 a month. I want to retire at 62, he wants to retire at 65. He will get a union pension of about $1,800 a month at 65. "
           "We want our daughter to go to a state university. My mother lives with us part of the year and we help her with about $400 a month. We also want to leave something to our daughter."),
    rules=[], policy="rules", w=1440, full=True)
J["bus"] = dict(
    first="I'm 52, a bus driver in Detroit, Michigan, divorced, with two kids 16 and 14. I make $52,000 and spend $4,200 a month. I have $30,000 saved. I want to retire at 58.",
    rules=[(r"rent|own your home", "I rent for $1,100 a month")], policy="rules", w=1440, full=True)
J["high"] = dict(
    first="I'm 41, a hedge fund analyst in New York City making $620,000 a year. I'm single, no kids. I have $1.9 million saved in a mix of accounts and I own a $1.6 million condo with a $900,000 mortgage. I spend $18,000 a month. I want to retire at 55.",
    rules=[], policy="rules", w=1440, full=True)
J["chipper"] = dict(first="I am 40, a plumber in Ohio. My wife is 38 and we have a mortgage.", rules=[], policy="chips", w=1440, full=True)
J["phone"] = dict(
    first="I'm 44, a high school teacher in Connecticut making $85,000. My husband is 46 and makes $70,000. We have two kids, 10 and 7. We've saved $260,000, own our home with a $200,000 mortgage and spend $6,500 a month. We want to retire at 62.",
    rules=[], policy="rules", w=390, full=True)

def run(name):
    cfg = J[name]
    with sync_playwright() as p:
        b, pg = newctx(p, cfg["w"], 844 if cfg["w"] < 600 else 900)
        touch = cfg["w"] < 600
        P(f"===== JOURNEY {name} width {cfg['w']} =====")
        if cfg["first"] is None:
            example(pg)
        else:
            say(pg, cfg["first"])
        P("FIRST BOT:", last_bot(pg))
        P("PANEL after first message:", panel(pg)[:2500])
        shot(pg, f"{name}_01_first", full=True)
        P("AXE intake:", axe(pg, "i"), "overflow", overflow(pg))
        P("small targets intake:", small_targets(pg))
        walk(pg, name, cfg["rules"], policy="chips" if cfg["policy"] == "chips" else "rules", maxturns=40) if cfg["policy"] != "skipall" else skipall(pg, name)
        P("PANEL before build:", panel(pg)[:3500])
        shot(pg, f"{name}_02_ready", full=True)
        if name in ("ex", "bus", "renter"):
            safe("editors", editors_tour, pg, name)
        if name in ("ex", "parent"):
            pass
        if not can_build(pg):
            P("!! cannot build; stuck. last bot:", last_bot(pg));
            safe("buildwith", lambda: pg.get_by_role("button", name=re.compile("Build with typical")).click())
            pg.wait_for_timeout(1500)
        note = safe("build", build2, pg)
        shot(pg, f"{name}_03_plan", full=True)
        P("PLAN BODY:\n", body(pg)[:7000])
        P("AXE plan:", axe(pg, "p"), "overflow", overflow(pg), "errors", pg.errors)
        P("small targets plan:", small_targets(pg))
        safe("expanders", expanders, pg, name)
        safe("charts", charts, pg, name, touch)
        safe("team", team, pg, name)
        safe("chips", whatif_chips, pg, name)
        safe("asks", asks, pg, name, ASKS_STD)
        shot(pg, f"{name}_04_after_asks", full=False)
        P("BODY after asks (head):", body(pg)[:1500])
        safe("back", lambda: pg.get_by_role("button", name=re.compile("Change my answers")).first.click())
        pg.wait_for_timeout(1000)
        P("after Change my answers panel:", panel(pg)[:600])
        if name in ("ex", "idk", "retired"):
            safe("resets", resets_tour, pg, name)
            shot(pg, f"{name}_05_after_resets", full=True)
        safe("startover", lambda: pg.get_by_role("button", name="Start over").first.click())
        pg.wait_for_timeout(1500)
        P("after Start over:", body(pg)[:800])
        shot(pg, f"{name}_06_startover", full=False)
        P("ERRORS:", pg.errors)
        b.close()

def skipall(pg, name, maxturns=40):
    for i in range(maxturns):
        if can_build(pg): P(f"[{name}] ready after {i}"); return
        last = last_bot(pg); cs = chips(pg)
        P(f"[{name}] BOT: {last[-220:]!r} CHIPS={cs}")
        if re.search(r"how old|your age", last[-250:], re.I) and i < 2:
            a = "I'm 50"
        else:
            pick = [c for c in cs if re.search(r"not sure|estimate|don't know|skip|typical", c, re.I)]
            a = pick[0] if pick else ("I don't know" if i % 2 == 0 else "skip")
        P(f"[{name}] ANSWER {a!r}")
        if a in cs: click_chip(pg, a)
        else: say(pg, a)
        pg.wait_for_timeout(200)
        if pg.locator("button", has_text="Build with typical").count() and i > 8:
            pass

if __name__ == "__main__":
    run(sys.argv[1])
