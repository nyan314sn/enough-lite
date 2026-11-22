from lib import *
import sys
log = lambda *a: print(*a, flush=True)
FIRST = {"A":"I'm 45, an accountant in Illinois, married, my wife is 43. We own our home with a mortgage. Retire at 62.",
         "B":"I'm 58, a nurse in Ohio, single. I rent. I have a pension and student loans."}
k = sys.argv[1]
seen=set()
with sync_playwright() as p:
    b, pg = new(p)
    say(pg, FIRST[k]); log("BOT1:", transcript(pg)[-1][-300:])
    for i in range(22):
        chips = pg.locator(".quick .chip").all_inner_texts()
        if not chips: say(pg, "skip"); continue
        pick = next((c for c in chips if re.search(r"estimate|skip|use this|typical|not sure|not working|about right|no other|none|no pension|nothing", c, re.I) and c not in seen), None)
        if pick is None:
            pick = next((c for c in chips if c not in seen and not re.match(r"build my plan", c, re.I)), None)
        if pick is None: break
        seen.add(pick)
        last = transcript(pg)[-1][-140:].replace("\n"," ")
        pg.locator(".quick .chip", has_text=pick).first.click()
        try: pg.wait_for_selector(".typing", state="detached", timeout=60000)
        except Exception: pass
        pg.wait_for_timeout(500)
        t = pg.locator("aside").first.inner_text().replace("\n"," | ")
        blanks = re.findall(r"([A-Za-z0-9'() ]{3,40}) \| (Not given|None given|amount not given|value not given|Not sure)[^|]*", t)
        home = t[t.find("Home"):t.find("Home")+260] if "Home" in t else ""
        log(f"\n[{i}] Q: {last}\n  CHIP: {pick}\n  REPLY: {transcript(pg)[-1][-260:]}".replace("\n"," ")[:900])
        log("  HOME/DEBTS:", re.sub(r"\s+"," ",t[t.find("Home & debts"):t.find("Home & debts")+420]))
        if can_build(pg) and i>14: break
    shot(pg, f"chips_{k}", full=False)
    t = pg.locator("aside").first.inner_text().replace("\n"," | ")
    log("FINAL PANEL:", t[:3500])
    b.close()
