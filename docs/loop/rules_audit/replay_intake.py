"""Replay of the intake failures from the rules audit against a live instance (default port 8112). Intake only: no plan is built.
Run: python replay_intake.py [idk|long|parent|edit|misc ...]"""
import sys
import lib
lib.URL = "http://localhost:8112/"
from tour import *
from journeys import J

PANEL_SECTIONS = ("Saving", "Home & debts", "Pensions & income", "Insurance", "Goals", "Health", "Costs")


def groups(pg):
    out = {}
    for s in PANEL_SECTIONS:
        el = pg.locator(f'[data-section="{s}"]').first
        if el.count():
            out[s] = el.inner_text().replace("\n", " | ")[:260]
    return out


def idk(p):
    b, pg = newctx(p)
    say(pg, "I'm 50, I live in Georgia")
    P("FIRST:", last_bot(pg))
    for i in range(14):
        if can_build(pg): break
        cs = chips(pg)
        pick = [c for c in cs if re.search(r"estimate it for me", c, re.I)]
        a = pick[0] if pick else ("I don't know" if i % 2 == 0 else "skip")
        P("ANSWER", repr(a))
        if a in cs: click_chip(pg, a)
        else: say(pg, a)
        P("  BOT:", last_bot(pg)[:300])
    for k, v in groups(pg).items(): P("GROUP", k, "::", v)
    b.close()


def longmsg(p):
    b, pg = newctx(p)
    say(pg, J["long"]["first"])
    P("BOT:", last_bot(pg))
    pn = panel(pg)
    for key in ("Savings", "Other debts", "Spending split", "Money to leave behind", "Home", "Children", "College"):
        i = pn.find(key)
        P("PANEL", key, "::", pn[i:i + 170] if i >= 0 else "(none)")
    b.close()


def parent(p):
    b, pg = newctx(p)
    say(pg, J["parent"]["first"])
    P("BOT:", last_bot(pg))
    pn = panel(pg)
    for m in re.finditer(r"College: child \d[^|]*\|[^|]*\|", pn): P("PANEL", m.group(0))
    P("CHIPS", chips(pg))
    say(pg, "I don't know")
    b.close()


def edit(p):
    b, pg = newctx(p)
    say(pg, "I'm 45, a lawyer in Ohio making $400,000, single, no kids, $900k saved, own with no mortgage, spend $5,000 a month, retire at 60")
    for i in range(10):
        if can_build(pg): break
        cs = chips(pg)
        say(pg, cs[0] if cs else "skip")
    P("READY", can_build(pg))
    # R7 on page 1
    say(pg, "change my pay to 90000")
    P("CHAT CHANGE bot:", last_bot(pg)[:300], "CHIPS", chips(pg))
    P("  panel pay:", re.findall(r"Your pay \| [^|]*\| [^|]*", panel(pg))[:1])
    click_chip(pg, "No")
    P("  after No:", last_bot(pg)[:200], "| pay", re.findall(r"Your pay \| [^|]*\| [^|]*", panel(pg))[:1])
    say(pg, "change my pay to 90000")
    click_chip(pg, "Yes")
    P("  after Yes:", last_bot(pg)[:260], "| pay", re.findall(r"Your pay \| [^|]*\| [^|]*", panel(pg))[:1])
    # editor: retirement age 40
    for label, val in (("Retirement age", "40"), ("Your age", "abc"), ("Retirement age", "62")):
        pg.locator(f".side button[aria-label='Change {label}']").first.click(); pg.wait_for_timeout(300)
        inp = pg.locator(".side .editor input").first
        inp.fill(val); inp.press("Enter"); pg.wait_for_timeout(500)
        err = pg.locator(".side .editor .editor-error, .side .editor [role=alert], .side .editor .error").all_inner_texts()
        P(f"EDITOR {label}={val}: error={err} bot={last_bot(pg)[:120]!r} editor_open={pg.locator('.side .editor').count()}")
        if pg.locator(".side .editor").count():
            pg.locator(".side .editor button", has_text="Cancel").first.click(); pg.wait_for_timeout(200)
    # pay edit via the editor, then the chat's words
    pg.locator(".side button[aria-label='Change Your pay']").first.click(); pg.wait_for_timeout(300)
    inp = pg.locator(".side .editor input").first; inp.fill("310000"); inp.press("Enter")
    pg.wait_for_timeout(1500)
    P("PAY EDIT SAVED bot:", last_bot(pg)[:300])
    b.close()


def misc(p):
    b, pg = newctx(p)
    say(pg, "I'm 45, a nurse in Ohio, single, no kids, 300k saved, I rent")
    say(pg, "I may inherit $300,000")
    P("INHERIT bot:", last_bot(pg)[:300])
    pn = panel(pg)
    i = pn.find("Possible inheritance")
    P("PANEL", pn[i:i + 140] if i >= 0 else "(no inheritance row)")
    say(pg, "my health is fair")
    P("HEALTH bot:", last_bot(pg)[:300])
    b.close()


if __name__ == "__main__":
    fns = dict(idk=idk, long=longmsg, parent=parent, edit=edit, misc=misc)
    with sync_playwright() as p:
        for n in (sys.argv[1:] or fns):
            P(f"===== {n} =====")
            safe(n, fns[n], p)
