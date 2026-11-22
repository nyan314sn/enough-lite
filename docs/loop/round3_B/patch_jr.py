import re
s=open("jr3.py",encoding="utf-8").read()
s=s.replace('''    ad = pg.locator("[data-testid=plan-assumptions]")
    log("ASSUMP:", ad.inner_text() if ad.count() else None)''','''    ad = pg.locator("[data-testid=plan-assumptions]")
    if ad.count():
        ad.locator("summary").first.click(); pg.wait_for_timeout(400)
        log("ASSUMP4:", ad.inner_text())
        shot(pg, f"{key}_assump", full=False)
        mb = ad.get_by_role("button", name=re.compile("More assumptions"))
        if mb.count():
            mb.first.click(); pg.wait_for_timeout(400); log("ASSUMP_ALL:", ad.inner_text())
    for d in pg.locator(".plan details:not([data-testid=plan-assumptions]) > summary").all():
        try:
            nm = d.inner_text().strip()
            d.click(); pg.wait_for_timeout(200)
            log("OPENED:", nm, "->", d.locator("xpath=..").inner_text()[:700].replace("\n"," | "))
        except Exception as e: log("openfail", e)''')
open("jr3.py","w",encoding="utf-8").write(s)
