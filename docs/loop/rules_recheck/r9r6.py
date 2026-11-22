from hdr import *
with sync_playwright() as p:
    b, pg = newctx(p, W, H)
    example(pg); click_chip(pg, "That's about right"); say(pg, "$2,900"); walk(pg, "ex"); build2(pg)
    P("--- R9 yes path")
    t = ask(pg, "I may inherit $300,000"); P("ask:", t.replace("\n"," | ")[:300])
    y = pg.get_by_role("button", name="Yes, rebuild")
    if y.count():
        y.first.click(); wait_idle(pg, 150000); pg.wait_for_timeout(2500)
        sub(pg, "after yes")
    body_t = pg.locator("body").inner_text()
    P("HEAD:", pg.locator("[data-testid=plan-headline]").inner_text().replace("\n"," | "))
    P("inherit mentions:", [m.group(0) for m in re.finditer(r".{80}inherit.{100}", body_t.replace("\n"," "), re.I)][:4])
    shot(pg, f"r9_{W}", full=True)
    P("--- R6 variations")
    for q in ("what if my pay grows 3% a year", "what if stocks return 3% a year", "plan to age 95", "what if inflation is higher", "change when Social Security starts", "what is my yearly saving assumption and can I change it"):
        t = ask(pg, q); P(f"R6 {q!r} ->", t.replace("\n"," | ")[:420], "| btns:", pg.locator(".turn").last.locator("button").all_inner_texts())
        bk = pg.get_by_role("button", name=re.compile("Back to my plan"))
        if bk.count() and bk.first.is_visible(): bk.first.click(); pg.wait_for_timeout(400)
    P("--- R18 jargon scan of plan page")
    txt = pg.locator("body").inner_text()
    for d in pg.locator("details").all(): 
        try: d.locator("summary").first.click()
        except Exception: pass
    pg.wait_for_timeout(500)
    txt = pg.locator("body").inner_text()
    open(os.path.join(HERE, "plan_text.txt"), "w", encoding="utf-8").write(txt)
    for rx in (r"\btoken", r"Monte Carlo", r"\blibrary\b", r"\bthe tool\b", r"\bnoted that your\b.*\bis noted", r"tax-advantaged", r"\bthe model\b", r"percentile", r"\bscenarios?\b", r"market paths", r"\bis noted\b", r"stochastic", r"\bAI cost"):
        ms = re.findall(rx, txt, re.I); P("  ", rx, len(ms))
    longs = [s for s in re.split(r"(?<=[.!?])\s+", txt.replace("\n"," ")) if len(s.split()) > 40]
    P("sentences over 40 words:", [(len(s.split()), s[:160]) for s in longs])
    P("errors", pg.errors)
    b.close()
