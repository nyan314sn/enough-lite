from lib import *
with sync_playwright() as p:
    b, pg = new(p, 1440, 900)
    say(pg, "I'm 30, a software engineer in Austin Texas, I rent. I make $95,000 and my employer matches 4% of my 401k. I have $45,000 in student loans at 6.5% and $8,000 saved. Retire at 65.")
    print("\n".join(transcript(pg)[-2:]))
    for a in ["That's about right"]:
        say(pg,a); print(transcript(pg)[-1])
    print(pg.locator("aside.side").inner_text()[:900].replace("\n"," | "))
    b.close()
