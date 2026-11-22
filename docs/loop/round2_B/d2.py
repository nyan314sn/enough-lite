from lib import *
with sync_playwright() as p:
    b, pg = new(p)
    pg.on("response", lambda r: print("RESP", r.status, r.url[-30:], flush=True) if "/api/plan" in r.url else None)
    say(pg, "I'm 45, married to my wife who is 55. We live in Colorado. I'm an engineer making $140,000 and she is a nurse making $85,000. We have $420,000 saved and spend $9,000 a month. We own our home with a mortgage of $200k at 4%. No kids. I want to retire at 62.")
    auto(pg, [(r"mortgage payment","$2,000 a month")], log=True)
    print(pg.locator("aside").first.inner_text().replace("\n"," | ")[:3000])
    build(pg, timeout=60000)
    print(pg.locator(".alert").all_inner_texts() if pg.locator(".alert").count() else "no alert")
    shot(pg,"gap_err",full=False)
    print(pg.inner_text("body")[:1500])
    b.close()
