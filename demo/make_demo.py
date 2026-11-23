"""Make the Enough Lite demo video (voice-over + screen recording) with no new installs.

  python make_demo.py            all stages: tts, record, assemble
  python make_demo.py tts        only the narration MP3s (OpenAI text-to-speech; a segment is made again only when its text changes)
  python make_demo.py record     only the browser recording (needs the app on http://localhost:8020/)
  python make_demo.py assemble   only the ffmpeg step (uses the work folder)

Needs: OPENAI_TTS_API_KEY in the .env the app reads (never printed), Playwright for Python with Microsoft Edge, ffmpeg.
The page is recorded with the DevTools screencast (JPEG frames with times) because Playwright's own video ffmpeg is not installed.
Each recording builds one real plan, one What If and two questions (about half a cent of AI use).
Use the conda Python: python demo\\make_demo.py
"""
import base64, hashlib, json, os, subprocess, sys, time
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
# Work files (frames, MP3s, segments) go to the local temp folder, not into OneDrive.
WORK = os.path.join(os.environ.get("TEMP", HERE), "enough_demo_work")
RAW = os.path.join(WORK, "raw")
TTS_DIR = os.path.join(WORK, "tts")
OUT = os.path.join(os.path.dirname(HERE), "enough_demo.mp4")   # the project root, next to report.html
NARRATION = "narration.txt"
URL = os.environ.get("ENOUGH_URL", "http://localhost:8020/")
FFMPEG = os.environ.get("FFMPEG", r"C:\ProgramData\chocolatey\bin\ffmpeg.exe")
FFPROBE = os.environ.get("FFPROBE", r"C:\ProgramData\chocolatey\bin\ffprobe.exe")
W, H, FPS = 1440, 900, 25
PAD_HEAD, PAD_TAIL = 0.30, 0.40          # silence before and after each narration segment
TTS_MODEL, TTS_VOICE = "gpt-4o-mini-tts", "nova"
TTS_STYLE = ("Warm, calm and confident, like a friendly product narrator. Natural pace, clear diction, "
             "slight smile in the voice. Not salesy.")

EXAMPLE = ("I'm 54 and my wife is 52, in Ohio. I make about $95,000 and she makes $60,000. We have about $520,000 saved, "
           "mostly in our 401(k)s. We owe $140,000 on our house. Our son is 16 and starts college in two years. "
           "We'd like to retire at 60 and spend about $70,000 a year.")
WHATIF = "What if we retire at 64"
RULE_Q = "When can I sign up for Medicare?"
STOCK_Q = "Which stock should I buy?"

# (id, mode, narration). mode "cut": the video is trimmed to the narration; "fit": the video (a wait for the AI) is sped up or held to
# fit; "card": a title card. Numbers in the narration were checked against the recording.
SCENES = [
    ("title", "card", "Can we retire at sixty? It is the question every household asks. Enough is an AI retirement planner that gives you an honest answer."),
    ("how", "cut", "A team of AI advisers checks your household, one part each. The numbers come from calculations, not from the AI. Let me fold this away and begin."),
    ("type", "cut", "Here is a couple in their fifties. Two earners, about five hundred thousand dollars saved, a mortgage, and a son heading to college. They want to retire at sixty. I tell it in plain words, just as I would tell a friend."),
    ("fills", "fit", "The panel on the right fills in at once. Here is the family picture, and it stays in view. Anything I did not say is a guess, and it is tagged estimate, so I always see what was assumed."),
    ("chips", "fit", "The chat asks short follow-up questions. When its guess is close, I answer with one tap."),
    ("fix", "fit", "When a figure is wrong, I fix it with the pen. Their spending now is nearer one hundred thousand a year, so I change it here."),
    ("build", "cut", "The chat says to check the figures. Then I choose Build my plan, and confirm."),
    ("team", "fit", "Now the advisers work. Each one lights up as it checks its part, and the lines show who passes notes to whom. You can read every hand-off in Team talk. Then the lead adviser writes the plan."),
    ("honest", "cut", "Here is the honest answer. This couple is short about seventeen thousand dollars a year, and the banner says so in plain red. Below it are needs, wants and wishes: what must be paid, what you can count on, and what you hope for."),
    ("analysis", "cut", "The analysis says how sure the plan is, and what could go wrong. If prices rise fast for ten years, savings could run out at sixty five, and they would cut about nine thousand dollars a year. It also shows what each choice is worth."),
    ("whatif", "fit", "So what helps? I ask, what if we retire at sixty four. The advisers run the plan again."),
    ("tab", "cut", "Each What If opens as its own tab, built on the baseline. Here the gap closes, and every change is marked against the baseline."),
    ("second", "fit", "I can add another. Here is an idea from Worth trying."),
    ("compare", "cut", "Compare puts the baseline and both What Ifs side by side. One click on the Baseline tab takes me back."),
    ("rule", "fit", "I can also ask a rule question, like when I can sign up for Medicare. The answer comes with its source."),
    ("stock", "fit", "But ask which stock to buy, and it politely declines. Enough plans. It does not pick stocks."),
    ("cost", "fit","Under Team talk, token costs show what the plan used: a fraction of a cent. One click shows each adviser's share. And there is a dark mode, for late-night planning."),
    ("end", "card", "Enough. Can you retire when you want? This is not financial advice."),
]
CARDS = {
    "title": ("Enough<span class='dot'>.</span>", "Can you retire when you want?", "A team of AI advisers builds your retirement plan"),
    "end": ("Enough<span class='dot'>.</span>", "Can you retire when you want?", "Not financial advice."),
}


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        print(r.stdout[-1500:], r.stderr[-3000:]); raise SystemExit(f"command failed: {cmd[0]}")
    return r


def dur(path):
    return float(sh([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout.strip())


def mp3path(i, sid, text):
    h = hashlib.sha1(f"{TTS_MODEL}|{TTS_VOICE}|{TTS_STYLE}|{text}".encode()).hexdigest()[:10]
    return os.path.join(TTS_DIR, f"{sid}_{h}.mp3")   # no scene number in the name, so adding a scene does not redo the others


# ---------------------------------------------------------------- 1. narration
def tts():
    os.makedirs(TTS_DIR, exist_ok=True)
    with open(os.path.join(HERE, NARRATION), "w", encoding="utf-8") as f:
        f.write(f"Enough Lite demo: narration script (voice: OpenAI {TTS_MODEL}, '{TTS_VOICE}')\n\n")
        for i, (sid, mode, text) in enumerate(SCENES):
            f.write(f"[{i:02d} {sid}] {text}\n\n")
    client, chars, total = None, 0, 0
    for i, (sid, mode, text) in enumerate(SCENES):
        p = mp3path(i, sid, text)
        if not os.path.exists(p):
            if client is None:
                sys.path.insert(0, os.path.dirname(HERE))
                from app import config  # noqa: F401  (loads the .env files; the key is never printed)
                from openai import OpenAI
                client = OpenAI(api_key=os.environ["OPENAI_TTS_API_KEY"].strip())
            with client.audio.speech.with_streaming_response.create(model=TTS_MODEL, voice=TTS_VOICE, input=text, instructions=TTS_STYLE) as r:
                r.stream_to_file(Path(p))
            chars += len(text)
        d = dur(p); total += d + PAD_HEAD + PAD_TAIL
        print(f"{i:02d} {sid:9s} {d:5.1f}s  {len(text)} chars")
    print(f"total about {total:.0f}s; new characters sent to text-to-speech this run: {chars}")


def audio_for(i):
    sid, mode, text = SCENES[i]
    return mp3path(i, sid, text)


# ---------------------------------------------------------------- 2. recording
CURSOR_JS = """
(() => {
  const add = () => {
    if (document.getElementById('demo-cursor')) return;
    const st = document.createElement('style'); st.textContent = '.foot{display:none !important}';
    document.documentElement.appendChild(st);
    const d = document.createElement('div'); d.id = 'demo-cursor';
    d.style.cssText = 'position:fixed;left:-40px;top:-40px;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;background:rgba(79,70,229,.88);border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.35),0 2px 8px rgba(0,0,0,.35);pointer-events:none;z-index:2147483647;transition:transform .12s';
    (document.body || document.documentElement).appendChild(d);
    window.addEventListener('mousemove', e => { d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; }, true);
    window.addEventListener('mousedown', () => { d.style.transform = 'scale(.6)'; }, true);
    window.addEventListener('mouseup', () => { d.style.transform = 'scale(1)'; }, true);
  };
  if (document.body) add(); else document.addEventListener('DOMContentLoaded', add);
})();
"""


class Rec:
    def __init__(self, pg):
        self.pg, self.t0 = pg, time.time()
        self.marks, self.x, self.y = [], 720, 450
        self.sstart = 0.0

    def now(self): return time.time() - self.t0

    def scene(self, sid):
        self.marks.append((sid, self.now())); self.sstart = self.now()
        print(f"  [{self.now():6.1f}s] scene {sid}", flush=True)

    def hold_until(self, seconds):
        """Wait until this scene has run `seconds` (so a 'cut' scene has video for all of its narration)."""
        left = seconds - (self.now() - self.sstart)
        if left > 0: self.pg.wait_for_timeout(int(left * 1000))

    def move(self, x, y, steps=28):
        self.pg.mouse.move(x, y, steps=steps); self.x, self.y = x, y

    def to(self, loc, dx=0.5, dy=0.5, steps=28, scroll=True):
        if scroll: loc.scroll_into_view_if_needed()
        self.pg.wait_for_timeout(250)
        b = loc.bounding_box()
        self.move(b["x"] + b["width"] * dx, b["y"] + b["height"] * dy, steps)

    def click(self, loc, dx=0.5, dy=0.5):
        self.to(loc, dx, dy); self.pg.wait_for_timeout(250); self.pg.mouse.click(self.x, self.y); self.pg.wait_for_timeout(250)

    def scroll(self, dy, step=40, pause=14):
        n = int(abs(dy) / step)
        for _ in range(n):
            self.pg.mouse.wheel(0, step if dy > 0 else -step); self.pg.wait_for_timeout(pause)
        self.pg.wait_for_timeout(200)

    def smooth_into_view(self, loc, top=140):
        """Scroll the page by mouse wheel until the element's top is `top` px from the top of the window."""
        y = loc.bounding_box()["y"]
        self.scroll(y - top)

    def type(self, text, delay=22):
        self.pg.keyboard.type(text, delay=delay)


def wait_reply(pg, timeout=90000):
    try: pg.wait_for_selector(".typing", timeout=4000)
    except Exception: pass
    pg.wait_for_selector(".typing", state="detached", timeout=timeout); pg.wait_for_timeout(400)


def ask_and_wait(r, pg, q, result_sel):
    """Type a question in the ask box under the plan and wait for its answer."""
    ask = pg.locator("#ask-input")
    r.to(ask); pg.mouse.click(r.x, r.y)
    r.type(q, delay=40)
    pg.wait_for_timeout(300); pg.keyboard.press("Enter")
    pg.wait_for_selector(result_sel, timeout=180000)
    pg.wait_for_timeout(900)


def record():
    from playwright.sync_api import sync_playwright
    L = {sid: dur(audio_for(i)) + PAD_HEAD + PAD_TAIL for i, (sid, m, t) in enumerate(SCENES)}
    import shutil; shutil.rmtree(RAW, ignore_errors=True); os.makedirs(RAW, exist_ok=True)
    notes = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": W, "height": H}, extra_http_headers={"X-Enough-Test": "1"})
        ctx.add_init_script(CURSOR_JS)
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        r = Rec(pg)
        frames = []
        os.makedirs(os.path.join(RAW, "frames"), exist_ok=True)
        cdp = ctx.new_cdp_session(pg)
        def on_frame(ev):
            t = time.time() - r.t0
            path = os.path.join(RAW, "frames", f"{len(frames):06d}.jpg")
            with open(path, "wb") as fh: fh.write(base64.b64decode(ev["data"]))
            frames.append((t, path))
            try: cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception: pass
        cdp.on("Page.screencastFrame", on_frame)
        r.t0 = time.time()
        cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": W, "maxHeight": H, "everyNthFrame": 1})
        pg.goto(URL); pg.wait_for_timeout(1500)

        # 2. how it works (the first-visit panel), then fold it
        r.scene("how"); r.move(900, 300)
        r.hold_until(L["how"] - 2.4)
        r.click(pg.get_by_role("button", name="Got it"))
        pg.wait_for_selector("[data-testid=how-it-works]", state="detached", timeout=5000)
        r.hold_until(L["how"])

        # 3. tell it in your own words
        r.scene("type")
        ta = pg.locator("#chat-input")
        r.click(ta); pg.wait_for_timeout(300)
        r.type(EXAMPLE, delay=24)
        r.hold_until(L["type"] - 0.9)
        pg.keyboard.press("Enter")

        r.scene("fills")
        wait_reply(pg)
        est = pg.locator(".field", has_text="estimate").first
        r.to(est); pg.wait_for_timeout(1200)
        r.move(1180, 420); r.scroll(280, pause=22); pg.wait_for_timeout(900)   # the family picture stays pinned
        r.scroll(-280, pause=22)
        r.hold_until(L["fills"])

        r.scene("chips")
        for _ in range(2):
            ch = pg.locator(".quick .chip")
            if not ch.count(): break
            r.click(ch.first); wait_reply(pg)
        r.hold_until(L["chips"])

        r.scene("fix")
        # open the Costs group (it holds the estimated spending now), then fix the figure with the pen
        grp = pg.locator(".group[data-section='Costs'] .group-toggle")
        if grp.count() and grp.first.get_attribute("aria-expanded") == "false": r.click(grp.first)
        pen = pg.locator("li.field[data-key='spending_now_per_year'] .pen")
        r.click(pen); pg.wait_for_timeout(500)
        inp = pg.locator("form.editor input").first
        r.click(inp); pg.keyboard.press("Control+A"); r.type("100000", delay=90)
        pg.wait_for_timeout(500)
        r.click(pg.locator("form.editor").get_by_role("button", name="Save"))
        wait_reply(pg)
        n = 0
        while pg.get_by_role("button", name="Build my plan", exact=True).get_attribute("aria-disabled") == "true" and n < 5:
            ch = pg.locator(".quick .chip")
            if not ch.count(): break
            r.click(ch.first); wait_reply(pg); n += 1
        notes["spending_now"] = pg.locator("li.field[data-key='spending_now_per_year']").inner_text().replace("\n", " | ")
        r.hold_until(L["fix"])

        # 4. build
        r.scene("build")
        buildbtn = pg.get_by_role("button", name="Build my plan", exact=True)
        r.hold_until(2.2)
        r.click(buildbtn)
        pg.wait_for_selector(".check", timeout=5000); pg.wait_for_timeout(600)
        r.hold_until(L["build"] - 1.6)
        r.click(pg.get_by_role("button", name="Looks right, build my plan"))

        # 5. the team
        r.scene("team")
        pg.wait_for_timeout(2500)
        for key in ("family", "markets", "tax", "longevity"):
            node = pg.locator(f"[data-agent='{key}']")
            if node.count(): r.to(node.first, scroll=False, steps=18)
        r.move(1180, 520)
        pg.wait_for_selector("[data-testid=plan-headline], .alert", timeout=240000)
        pg.wait_for_timeout(1500)

        # 6. the honest answer
        r.scene("honest")
        pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(800)
        notes["banner"] = pg.locator("[data-testid=shortfall]").inner_text().replace("\n", " | ")
        notes["nww"] = pg.locator(".nww").inner_text().replace("\n", " | ")
        notes["headline"] = pg.locator("[data-testid=plan-headline]").inner_text()
        r.to(pg.locator("[data-testid=shortfall]"), 0.3, 0.5)
        r.hold_until(L["honest"] * 0.40)
        for sel in (".nww-needs", ".nww-wants", ".nww-wishes"):
            r.to(pg.locator(sel).first, 0.3, 0.5, steps=22); pg.wait_for_timeout(1500)
        r.hold_until(L["honest"])

        r.scene("analysis")
        summ = pg.locator("details.analysis summary")
        r.smooth_into_view(summ, 110)
        r.click(summ); pg.wait_for_timeout(700)
        notes["analysis"] = pg.locator("details.analysis").inner_text().replace("\n", " | ")[:2500]
        r.scroll(300, pause=24)
        r.hold_until(L["analysis"] * 0.35)
        wrong = pg.locator("[data-testid=an-stresses] li, [data-testid=an-short]").first
        if wrong.count():
            r.to(wrong, 0.4, 0.5, scroll=False)
        r.hold_until(L["analysis"] * 0.6)
        lev = pg.locator("[data-testid=an-levers]")
        if lev.count():
            r.smooth_into_view(lev, 300); r.to(lev, 0.3, 0.3, scroll=False)
        r.hold_until(L["analysis"])

        # 7. what to do about it
        r.scene("whatif")
        ask_and_wait(r, pg, WHATIF, "[data-testid=wi-change]")   # the new tab opens with the full plan
        r.marks.append(("whatif_r", r.now()))
        pg.wait_for_timeout(1200)

        r.scene("tab")
        pg.wait_for_timeout(900)    # the page scrolls itself to the top of the new tab
        notes["tab1"] = pg.locator(".scen-tab[aria-selected=true]").inner_text()
        notes["change"] = pg.locator("[data-testid=wi-change]").inner_text().replace("\n", " | ")
        notes["banner1"] = pg.locator("[data-testid=shortfall], [data-testid=plan-headline]").first.inner_text().replace("\n", " | ")
        vs = pg.locator("[data-testid=vs-goal]")
        notes["vs_goal"] = vs.inner_text().replace("\n", " | ") if vs.count() else "none"
        r.to(pg.locator(".scen-tabs"), 0.3, 0.5, scroll=False)
        r.hold_until(L["tab"] * 0.30)
        r.to(pg.locator("[data-testid=wi-change]"), 0.3, 0.5, scroll=False, steps=22)
        r.hold_until(L["tab"] * 0.55)
        if vs.count(): r.to(vs, 0.3, 0.5, scroll=False, steps=22)
        r.hold_until(L["tab"])

        # a second What If, from a Worth trying chip
        r.scene("second")
        chips = pg.locator(".quick.ideas .chip:not(.tried)")
        pick = None
        for k in range(chips.count()):
            if any(w in chips.nth(k).inner_text().lower() for w in ("spend", "sav", "contribut", "cut")): pick = chips.nth(k); break
        if pick is None: pick = chips.first
        notes["chip"] = pick.inner_text()
        r.smooth_into_view(pg.locator(".ask"), 380)
        r.click(pick)
        pg.locator(".scen-tab").nth(2).wait_for(timeout=180000)   # the second What If's tab (no page script: the app's CSP blocks it)
        pg.wait_for_timeout(700)
        r.marks.append(("second_r", r.now()))
        pg.wait_for_timeout(1200)

        r.scene("compare")
        pg.wait_for_timeout(700)
        notes["tab2"] = pg.locator(".scen-tab[aria-selected=true]").inner_text()
        notes["change2"] = pg.locator("[data-testid=wi-change]").inner_text().replace("\n", " | ")
        r.hold_until(1.2)
        r.click(pg.locator(".scen-compare"))
        pg.wait_for_selector("[data-testid=compare-table]", timeout=5000); pg.wait_for_timeout(900)
        notes["compare"] = pg.locator("[data-testid=compare-table]").inner_text().replace("\n", " | ")[:1200]
        r.move(520, 450)
        r.hold_until(L["compare"] * 0.35)
        gap = pg.locator("[data-testid=gap-row]")
        if gap.count(): r.to(gap, 0.6, 0.5, scroll=False); pg.wait_for_timeout(800)
        r.hold_until(L["compare"] - 3.0)
        r.click(pg.locator(".scen-tab", has_text="Baseline").first)
        pg.wait_for_timeout(1500)

        # 8. trust
        r.scene("rule")
        ask_and_wait(r, pg, RULE_Q, ".turn-answer, .turn .cites, .turn .turn-a")
        try: pg.locator(".turns .spinner").first.wait_for(state="detached", timeout=90000)
        except Exception: pass
        pg.wait_for_timeout(800)
        r.marks.append(("rule_r", r.now()))
        pg.locator(".turn").last.scroll_into_view_if_needed(); pg.wait_for_timeout(3500)

        r.scene("stock")
        ask_and_wait(r, pg, STOCK_Q, ".refused")
        try: pg.locator(".turns .spinner").first.wait_for(state="detached", timeout=90000)
        except Exception: pass
        r.marks.append(("stock_r", r.now()))
        pg.locator(".turn").last.scroll_into_view_if_needed(); pg.wait_for_timeout(3500)

        # 9. cost and dark mode
        r.scene("cost")
        pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(500)
        r.move(1180, 420)
        r.scroll(900, pause=20)          # the team panel scrolls by itself: down to the token costs
        cb = pg.locator("[data-testid=cost-block]")
        r.to(cb, 0.5, 0.2); pg.wait_for_timeout(1200)
        notes["cost"] = cb.inner_text().replace("\n", " | ")
        r.click(pg.locator("details.cost-detail summary"))
        r.move(1180, 420)
        r.scroll(400, pause=25)
        r.hold_until(L["cost"] - 6.0)
        pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(500)
        tog = pg.locator("[data-theme-toggle]")
        r.click(tog); pg.wait_for_timeout(2600)
        r.move(900, 500, steps=14); pg.wait_for_timeout(500)
        r.click(tog); pg.wait_for_timeout(1200)

        r.scene("end")
        pg.wait_for_timeout(500)
        log = {"marks": r.marks, "end": r.now(), "errors": errors, "notes": notes}
        pg.screenshot(path=os.path.join(WORK, "last_state.png"))
        cdp.send("Page.stopScreencast")
        ctx.close(); b.close()
    log["frames"] = frames
    json.dump(log, open(os.path.join(RAW, "marks.json"), "w"), indent=1)
    print(len(frames), "frames")
    for k, v in notes.items(): print(f"NOTE {k}: {v}")
    print("page errors:", errors)


# ---------------------------------------------------------------- 3. assembly
CARD_HTML = """<html><head><style>.dot{color:#a5b4fc}</style></head><body style="margin:0;width:1440px;height:900px;display:flex;flex-direction:column;align-items:center;justify-content:center;
background:linear-gradient(135deg,#1e1b4b,#4338ca 70%%,#4F46E5);color:#fff;font-family:Segoe UI,Arial,sans-serif;text-align:center">
<div style="font-size:150px;font-weight:700;letter-spacing:-2px">%s</div>
<div style="font-size:48px;margin-top:10px;opacity:.97">%s</div>
<div style="font-size:30px;margin-top:46px;opacity:.78">%s</div></body></html>"""


def cards():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge"); pg = b.new_page(viewport={"width": W, "height": H})
        for name, (a, c, d) in CARDS.items():
            pg.set_content(CARD_HTML % (a, c, d)); pg.screenshot(path=os.path.join(WORK, f"card_{name}.png"))
        b.close()


def assemble():
    cards()
    log = json.load(open(os.path.join(RAW, "marks.json")))
    marks = [m for m in log["marks"] if not m[0].endswith("_r")] + [["_end", log["end"]]]
    span = {marks[i][0]: (marks[i][1], marks[i + 1][1]) for i in range(len(marks) - 1)}
    span_r = {m[0]: m[1] for m in log["marks"] if m[0].endswith("_r")}
    cfr = os.path.join(WORK, "screen_cfr.mp4")
    fr = log["frames"] + [[log["end"] + 0.5, log["frames"][-1][1]]]
    lst0 = os.path.join(WORK, "frames.txt")
    with open(lst0, "w") as fh:
        for (t, pth), (t2, _) in zip(fr, fr[1:]):
            fh.write(f"file '{pth.replace(chr(92), '/')}'\nduration {max(t2 - t, 0.001):.4f}\n")
        fh.write(f"file '{fr[-1][1].replace(chr(92), '/')}'\n")
    sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst0, "-vf", f"fps={FPS},scale={W}:{H}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-an", cfr])
    segs = []
    for i, (sid, mode, text) in enumerate(SCENES):
        wav = audio_for(i); a = dur(wav); total = a + PAD_HEAD + PAD_TAIL
        seg = os.path.join(WORK, f"seg_{i:02d}.mp4"); segs.append(seg)
        afilt = f"aresample=44100,adelay={int(PAD_HEAD*1000)}|{int(PAD_HEAD*1000)},apad=whole_dur={total:.3f}"
        common = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
                  "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "1", "-t", f"{total:.3f}"]
        if mode == "card":
            img = os.path.join(WORK, f"card_{sid}.png")
            sh([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-i", img, "-i", wav, "-af", afilt, "-vf", "format=yuv420p"] + common + [seg])
            continue
        s, e = span[sid]; d = e - s
        if mode == "cut":
            vf = f"trim=start={s:.3f}:duration={total:.3f},setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=3"
            if d < total - 0.3: print(f"  warn: scene {sid} video {d:.1f}s is shorter than narration {total:.1f}s (last frame held)")
            if d > total + 0.5: print(f"  warn: scene {sid} video {d:.1f}s is longer than narration {total:.1f}s (end cut off)")
        elif sid + "_r" in span_r:
            # fit with a result: the wait for the AI is sped up, the moment the answer shows plays at normal speed (about 4 s)
            r_ = span_r[sid + "_r"]; tail = min(e - r_, 4.5); wait = total - tail
            f = max((r_ - s) / wait, 1.0)
            vf = (f"split[a][b];[a]trim=start={s:.3f}:end={r_:.3f},setpts=(PTS-STARTPTS)/{f:.4f},tpad=stop_mode=clone:stop_duration=3,trim=duration={wait:.3f}[v1];"
                  f"[b]trim=start={r_:.3f}:duration={tail:.3f},setpts=PTS-STARTPTS[v2];[v1][v2]concat=n=2:v=1:a=0,tpad=stop_mode=clone:stop_duration=3")
            print(f"  scene {sid}: wait {r_-s:.1f}s -> {wait:.1f}s (x{f:.2f}), result {tail:.1f}s")
        else:
            f = max(d / total, 1.0)   # a wait for the AI: sped up to the narration; a short one is held on its last frame, never slowed
            vf = f"trim=start={s:.3f}:end={e:.3f},setpts=(PTS-STARTPTS)/{f:.4f},tpad=stop_mode=clone:stop_duration=3"
            print(f"  scene {sid}: video {d:.1f}s -> {total:.1f}s (x{f:.2f})")
        sh([FFMPEG, "-y", "-i", cfr, "-i", wav, "-vf", vf, "-af", afilt] + common + [seg])
    lst = os.path.join(WORK, "concat.txt")
    open(lst, "w").write("".join(f"file '{s.replace(chr(92), '/')}'\n" for s in segs))
    sh([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", OUT])
    print("wrote", OUT, f"{os.path.getsize(OUT)/1e6:.1f} MB, {dur(OUT):.1f} s")


# ================================================================ v3: the redesigned app (flag --v3)
# Usage (conda Python):
#   python demo\make_demo.py --v3 figures            one live pass (about 3 AI calls, no video): reads the numbers the narration will say -> demo/figures_v3.json
#   python demo\make_demo.py --v3 tts                narration MP3s (numbers filled from figures_v3.json); only changed segments are made again
#   python demo\make_demo.py --v3 record             the recording, then the CONSISTENCY CHECK (fails loudly)
#   python demo\make_demo.py --v3 record --stop-after early      dry run: the first scenes only; estimated durations if there is no MP3 yet
#   python demo\make_demo.py --v3 assemble           ffmpeg; writes demo/enough_demo_v3.mp4
# Rules: about the app only; one voice (nova); transcript, voice and screen agree. A number is never typed into the narration as a
# fixed figure unless the page shows it: write {name} and the figure is read from the live page (figures stage) and spoken as words.
# The check after recording parses every number the narration says (digits or words) and requires it on screen, in the visible text
# captured during that scene (text hidden, folded, scrolled out of the window or covered by another element does not count).
import re

FIG_FILE = os.path.join(HERE, "figures_v3.json")
USD_FIGS = {"gap", "goal", "counton", "newgoal"}          # spoken with "dollars"

EXAMPLE_V3 = ("I'm 54 and my wife is 52, in Ohio. I make about $95,000 and she makes $60,000. We have about $520,000 saved. "
              "We owe $140,000 on our house. Our son is 16. We'd like to spend about $70,000 a year in retirement.")

# (id, mode, template, phrases that must be visible during the scene). {name} is a figure read from the live page.
# Wording on screen is being rewritten: if a phrase in the last column fails, change the phrase here, not the check.
SCENES_V3 = [
    ("title", "card", "Can we retire at sixty? Every household asks. Enough is an AI retirement planner that gives an honest answer.",
     ["retire at 60"]),
    ("intro", "fit", "This is Enough. I tell it about a couple in plain words, the way I would tell a friend. They are in their fifties.",
     ["how enough works", "54"]),
    ("send", "fit", "The moment I send it, the guide folds into one line. The panel on the right fills in. Anything I did not say is a typical figure, marked estimate.",
     ["how enough works", "estimate"]),
    ("edit", "cut", "Every figure in the panel can be changed right there. I press the pencil and pick from the list.",
     ["state"]),
    ("early", "fit", "I do not have to answer every question. I press Build my plan, and it asks me one thing first: when to retire. I pick sixty.",
     ["build my plan", "when would you like to retire", "60"]),
    ("check", "cut", "Then Enough asks me to check its guesses. The rows marked estimate are what I left out. They look fair, so I confirm.",
     ["estimate", "looks right"]),
    ("team", "fit", "Now the advisers get to work, one part each. Then the lead adviser writes the plan.",
     []),
    ("answer", "cut", "Here is the answer, in one glance. The verdict says not yet. The ring shows how ready they are: {ring0} out of one hundred. And they are short {gap} a year.",
     ["not yet", "readiness", "short"]),
    ("ladder", "cut", "Below is the money ladder. Needs are safe, wants are sure, wishes are open. Needs are paid in {paid} of one hundred market tests. The couple can count on {counton} a year. The wishes are the rest of the goal.",
     ["needs", "wants", "wishes", "safe", "sure", "open", "count on"]),
    ("moves", "cut", "Next come the moves. It is a plain list, and the first one says it closes the gap.",
     ["your next moves", "closes the gap"]),
    ("whatif", "cut", "To test a move, I press What if. The plan greys out, and the What If section lights up. I pick the first idea, the best move.",
     ["try a what if", "worth trying", "change one thing"]),
    ("run", "fit", "Now the same advisers run the plan again, with that one change.",
     ["working on", "re-running your plan with"]),
    ("tab", "cut", "The result opens as its own tab. The change is to spend {newgoal} a year in retirement. Wishes are covered now, and the page says level up. Readiness rises {delta} points, to {ring1}. That is a trade, and the choice is theirs.",
     ["what changed", "level up", "vs baseline", "closes the gap"]),
    ("compare", "fit", "Compare puts them side by side. Before, they were short {gap} a year, and the goal lasted in {lasts0} of one hundred tests. After, there is no gap, and it lasts in {lasts1}.",
     ["compare", "short", "none", "goal lasts in"]),
    ("rule", "fit", "I can also ask a rule question, like when I can sign up for Medicare. The answer comes with its source.",
     ["medicare", "sources"]),
    ("stock", "fit", "Ask which stock to buy, and Enough politely declines. It plans. It does not pick stocks.",
     ["which stock", "can't help"]),
    ("cost", "cut", "Every plan shows its token costs. This one used well under a cent.",
     ["token costs", "this plan"]),
    ("end", "card", "Enough. Can you retire when you want? This is not financial advice.",
     ["not financial advice"]),
]
CARDS_V3 = {
    "title": ("Enough<span class='dot'>.</span>", "Can we retire at 60?", "An AI retirement planner. Honest answers."),
    "end": ("Enough<span class='dot'>.</span>", "Can you retire when you want?", "Not financial advice."),
}

# ---- numbers as words, and back
_ON = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TN = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}
_W2N = {w: i for i, w in enumerate(_ON)}
_W2N.update({w: n * 10 for n, w in _TN.items()})


def n2w(n):
    n = int(n)
    if n < 20: return _ON[n]
    if n < 100: return _TN[n // 10] + ("-" + _ON[n % 10] if n % 10 else "")
    if n < 1000: return _ON[n // 100] + " hundred" + (" " + n2w(n % 100) if n % 100 else "")
    if n < 1000000: return n2w(n // 1000) + " thousand" + (" " + n2w(n % 1000) if n % 1000 else "")
    raise ValueError(n)


def spoken_numbers(text):
    """Every number a listener hears in `text`: digits, and number words ("forty-nine thousand"). A lone "one" ("one glance") is not a number."""
    out, seq = [], []
    def flush():
        if not seq: return
        if seq == ["one"]: seq.clear(); return
        total = cur = 0
        for w in seq:
            if w == "hundred": cur = (cur or 1) * 100
            elif w == "thousand": total += (cur or 1) * 1000; cur = 0
            else: cur += _W2N[w]
        out.append(total + cur); seq.clear()
    for tok in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|[a-z']+|[^\sa-z\d-]", text.lower().replace("’", "'")):
        if tok[0].isdigit(): flush(); out.append(float(tok.replace(",", "")))
        elif tok in _W2N or tok in ("hundred", "thousand"): seq.append(tok)
        else: flush()
    flush()
    return out


def page_numbers(text):
    """Every number written in the visible page text; "$312k" counts as 312000 as well as 312."""
    out = set()
    for m in re.finditer(r"((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(\s?k\b)?", text.lower()):
        v = float(m.group(1).replace(",", "")); out.add(v)
        if m.group(2): out.add(v * 1000)
    return out


def norm(t): return re.sub(r"\s+", " ", t.lower().replace("’", "'"))


def fill_text(tmpl, figs):
    def sub(m):
        k = m.group(1)
        if k not in figs: raise SystemExit(f"figure '{k}' is not in figures_v3.json: run the figures stage (python make_demo.py --v3 figures)")
        return n2w(figs[k]) + (" dollars" if k in USD_FIGS else "")
    return re.sub(r"\{(\w+)\}", sub, tmpl)


def load_figs(required=True):
    if os.path.exists(FIG_FILE): return json.load(open(FIG_FILE, encoding="utf-8"))
    if required: raise SystemExit("no demo/figures_v3.json yet: run  python demo\\make_demo.py --v3 figures  first")
    return {}


def use_v3():
    """Point the shared stages (tts, record helpers, assemble) at the v3 scenes, work folder and output."""
    global SCENES, CARDS, WORK, RAW, TTS_DIR, OUT, NARRATION, TEMPL, SHOW
    WORK = os.path.join(os.environ.get("TEMP", HERE), "enough_demo_work_v3")
    RAW, TTS_DIR = os.path.join(WORK, "raw"), os.path.join(WORK, "tts")
    OUT, NARRATION, CARDS = os.path.join(HERE, "enough_demo_v3.mp4"), "narration_v3.txt", CARDS_V3
    TEMPL = {sid: t for sid, m, t, s in SCENES_V3}
    SHOW = {sid: s for sid, m, t, s in SCENES_V3}


def build_scenes_v3(figs):
    return [(sid, mode, fill_text(t, figs)) for sid, mode, t, s in SCENES_V3]


def est_len(text): return len(text.split()) / 2.7 + 0.4          # only for a dry run with no MP3 yet


def scene_len(i):
    sid, mode, text = SCENES[i]
    p = mp3path(i, sid, text)
    return (dur(p) if os.path.exists(p) else est_len(text)) + PAD_HEAD + PAD_TAIL


# Visible text only: not sr-only, not hidden or folded, inside the window, and not covered by another element at its centre.
VISIBLE_JS = """
() => {
  const out = [], vw = innerWidth, vh = innerHeight;
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, t = n.nodeValue.trim(); if (!t) continue;
    const el = n.parentElement; if (!el || el.closest('.sr-only,script,style,[hidden],#demo-cursor')) continue;
    const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
    const r = document.createRange(); r.selectNodeContents(n);
    const b = r.getBoundingClientRect(); if (!b.width || !b.height) continue;
    const cx = Math.min(Math.max(b.left + b.width / 2, 0), vw - 1), cy = Math.min(Math.max(b.top + b.height / 2, 0), vh - 1);
    if (b.bottom < 0 || b.top > vh || b.right < 0 || b.left > vw) continue;
    const top = document.elementFromPoint(cx, cy); if (!top || !(el.contains(top) || top.contains(el))) continue;
    out.push(t);
  }
  document.querySelectorAll('textarea,input').forEach(e => { if (e.value) out.push(e.value); });
  return out.join(' ');
}
"""


class StopRun(Exception): pass


class Rec3(Rec):
    """Rec plus: a visible-text snapshot every 0.45 s inside a scene, scene ends, and the figures read from the page."""
    def __init__(self, pg, stop_after=None):
        super().__init__(pg)
        self.cur, self.snaps, self.ended, self.rmark, self.figs, self.claims = None, {}, {}, {}, {}, []
        self.stop_after = stop_after

    def snap(self):
        if self.cur: self.snaps.setdefault(self.cur, []).append((self.now(), self.pg.evaluate(VISIBLE_JS)))

    def scene(self, sid):
        self.cur = sid; super().scene(sid); self.snap()

    def wait(self, ms):
        left = ms / 1000.0
        while left > 0:
            step = min(0.45, left); self.pg.wait_for_timeout(int(step * 1000)); left -= step; self.snap()

    def hold_until(self, seconds):
        left = seconds - (self.now() - self.sstart)
        if left > 0: self.wait(int(left * 1000))

    def mark_r(self, sid):
        self.marks.append((sid + "_r", self.now())); self.rmark[sid] = self.now()

    def done(self, sid):
        self.snap(); self.ended[sid] = self.now()
        if self.stop_after == sid: raise StopRun(sid)

    def stop_point(self, name):
        if self.stop_after == name: self.snap(); raise StopRun(name)

    def claim(self, sid, what, ok):
        self.claims.append((sid, what, bool(ok)))


def _t(pg, sel): return pg.locator(sel).first.inner_text().replace("\n", " | ")
def _int(s, pat=r"(\d[\d,]*)", n=1): return int(re.findall(pat, s)[n - 1].replace(",", ""))


def flow_v3(pg, r, L):
    F = r.figs
    # 1. page 1: the guide is open on the first visit; tell it about the household
    r.scene("intro"); r.move(900, 300)
    r.claim("intro", "the 'How Enough works' guide is open on the first visit", pg.locator("[data-testid=how-it-works]").count() == 1)
    r.hold_until(2.6)
    ta = pg.locator("#chat-input"); r.click(ta); r.wait(300)
    r.type(EXAMPLE_V3, delay=24)
    r.hold_until(L["intro"] - 0.9); r.done("intro")

    # 2. send: the guide folds on the first message; the panel fills in
    r.scene("send")
    pg.keyboard.press("Enter"); wait_reply(pg)
    r.claim("send", "the guide folded to one line after the first message",
            pg.locator("[data-testid=how-it-works]").count() == 0 and pg.locator("[data-testid=how-collapsed]").count() == 1)
    r.snap()
    est = pg.locator(".field", has_text="estimate").first
    r.to(est); r.wait(1200); r.mark_r("send")
    r.move(1180, 420); r.scroll(280, pause=22); r.wait(900); r.scroll(-280, pause=22)
    r.done("send")

    # 2b. a figure can be edited right in the panel (the state: a searchable list); nothing is saved, so the plan is unchanged
    r.scene("edit")
    pen = pg.locator(".field[data-key=state] .pen").first
    if not pen.is_visible():
        grp = pg.locator(".field[data-key=state]").first.locator("xpath=ancestor::*[.//button[contains(@class,'group-toggle')]][1]").locator(".group-toggle").first
        r.click(grp); r.wait(400)
    r.to(pen, steps=26); r.wait(300); r.click(pen); r.wait(600)
    r.claim("edit", "the state editor opened inline", pg.locator("form.editor").count() == 1)
    ed = pg.locator("form.editor input").first
    r.to(ed, 0.5, 0.5, steps=20); r.wait(800)
    r.hold_until(L["edit"] - 0.7)
    pg.keyboard.press("Escape"); r.wait(500)
    r.claim("edit", "the editor closed without a change", pg.locator("form.editor").count() == 0)
    r.hold_until(L["edit"]); r.done("edit")

    # 3. early build: usable from the first answer; it asks the retirement age first, answered with its chip
    r.scene("early")
    build = pg.get_by_role("button", name="Build my plan", exact=True).first
    r.claim("early", "Build my plan is enabled before the follow-up questions are answered", build.is_enabled())
    pg.evaluate("window.scrollTo(0,0)"); r.wait(300)
    r.to(build, scroll=False); r.wait(600)
    r.hold_until(max(L["early"] * 0.15, 1.5))
    r.click(build); wait_reply(pg)
    r.claim("early", "Build my plan asks for the retirement age first", pg.get_by_text("When would you like to retire?").count() >= 1)
    chip60 = pg.locator(".quick .chip", has_text="60").first
    log_ = pg.locator("[role=log]").first
    r.to(chip60, 0.5, 0.5, steps=24); r.hold_until(L["early"] - 2.2)
    r.click(chip60); wait_reply(pg); r.wait(300)
    r.hold_until(L["early"]); r.done("early")

    # 4. check the guessed figures, confirm
    r.scene("check")
    pg.evaluate("window.scrollTo(0,0)"); r.wait(200)
    build = pg.get_by_role("button", name="Build my plan", exact=True).first
    r.click(build); pg.wait_for_selector(".check", timeout=5000); r.wait(600)
    guesses = pg.locator(".field.is-check")
    r.claim("check", "the check step highlights guessed rows", guesses.count() > 0)
    r.to(guesses.first, 0.3, 0.5); r.wait(500)
    r.hold_until(L["check"] * 0.5)
    if guesses.count() > 3: r.to(guesses.nth(3), 0.3, 0.5, steps=22)
    r.hold_until(L["check"] - 1.6)
    r.stop_point("confirm")
    r.click(pg.get_by_role("button", name="Looks right, build my plan")); r.done("check")

    # 5. the advisers at work (brief)
    r.scene("team")
    r.wait(2500)
    for key in ("family", "markets", "tax", "longevity"):
        node = pg.locator(f"[data-agent='{key}']")
        if node.count(): r.to(node.first, scroll=False, steps=18)
    r.move(1180, 520)
    pg.wait_for_selector("[data-testid=plan-hero]", timeout=240000); r.wait(1500)
    r.done("team")

    # 6. the answer in one glance
    r.scene("answer")
    pg.evaluate("window.scrollTo(0,0)"); r.wait(800)
    F["ring0"] = int(pg.locator("[data-testid=ring]").get_attribute("data-value"))
    short = pg.locator("[data-testid=verdict]")
    r.claim("answer", "the verdict reads Not yet, short $X a year", "not yet" in short.inner_text().lower())
    F["gap"] = _int(short.inner_text(), r"short \$([\d,]+)")
    F["goal"] = _int(_t(pg, "[data-testid=ladder-goal]"))
    F["counton"] = _int(_t(pg, "[data-testid=ladder-counton]"))
    F["paid"] = _int(_t(pg, "[data-layer=needs]"), r"(\d+) of 100")
    r.to(pg.locator(".verdict"), 0.3, 0.5, scroll=False); r.hold_until(L["answer"] * 0.25)
    r.to(pg.locator("[data-testid=ring]"), 0.5, 0.5, scroll=False, steps=22); r.hold_until(L["answer"] * 0.5)
    r.to(short, 0.3, 0.5, scroll=False, steps=22); r.hold_until(L["answer"]); r.done("answer")

    # 7. the money ladder
    r.scene("ladder")
    for k, frac in (("needs", 0.25), ("wants", 0.5), ("wishes", 0.78)):
        r.to(pg.locator(f"[data-layer={k}] .lad-hit"), 0.3, 0.5, scroll=False, steps=22); r.hold_until(L["ladder"] * frac)
    r.hold_until(L["ladder"]); r.done("ladder")

    # 8. the next moves (read only): the one that closes the gap
    r.scene("moves")
    closing = pg.locator(".move", has_text="Closes the gap")
    r.claim("moves", "exactly one next move is marked 'Closes the gap'", closing.count() == 1)
    if closing.count() != 1: raise SystemExit("this household has no single closing move: pick another household (see storyboard_v3.md)")
    r.claim("moves", "the moves are read only (no Try it, no Mark as planned)", pg.get_by_text("Try it").count() == 0 and pg.get_by_text("Mark as planned").count() == 0)
    r.smooth_into_view(pg.locator("[data-testid=moves]"), 120); r.wait(400)
    r.to(closing.locator(".move-title"), 0.3, 0.5, scroll=False); r.hold_until(L["moves"] * 0.5)
    r.to(closing.locator(".worth-chip").first, 0.3, 0.5, scroll=False, steps=22); r.hold_until(L["moves"]); r.done("moves")
    print("  first move:", _t(pg, ".move >> nth=0 >> .move-title"))

    # 9. "+ What if…" greys out the plan and lights the What If section; the first chip is the plan's best move
    r.scene("whatif")
    pg.evaluate("window.scrollTo(0,0)"); r.wait(500)
    add = pg.locator("#scen-add")
    r.click(add); r.wait(900)
    r.claim("whatif", "the plan is greyed out while composing", pg.locator(".scen-panel.dimmed").count() == 1 and pg.locator("section.ask.composing").count() == 1)
    first = pg.locator("[data-testid=whatif-section] .ideas .chip").first
    r.claim("whatif", "the first 'Worth trying' chip is the plan's closing move", first.inner_text().strip().lower().startswith(closing.locator(".move-title").first.inner_text().strip().lower()[:25]))
    r.to(first, 0.4, 0.5, scroll=False, steps=26)
    r.hold_until(L["whatif"] - 0.2); r.done("whatif")

    # 10. the What If runs: the same advisers, live in the team panel
    r.scene("run")
    pg.mouse.click(r.x, r.y)
    pg.wait_for_selector("[data-testid=run-wait]", timeout=20000); r.wait(1200)
    r.claim("run", "the team panel shows 'Working on' during the re-run", pg.get_by_text("Working on:").count() >= 1)
    r.move(1180, 420)
    pg.locator(".scen-tab").nth(1).wait_for(timeout=240000); r.wait(700); r.mark_r("run")
    pg.evaluate("window.scrollTo(0,0)"); r.wait(1200)
    r.done("run")

    # 11. the What If tab: level up, the gap closes
    r.scene("tab")
    pg.evaluate("window.scrollTo(0,0)"); r.wait(900)
    chg = _t(pg, "[data-testid=wi-change]")
    m = re.search(r"Spend \$([\d,]+) a year", chg)
    r.claim("tab", "the What If is a spending-goal change ('Spend $X a year')", bool(m))
    if not m: raise SystemExit(f"the closing move is not a spending-goal change ({chg!r}): the 'tab' narration must be rewritten")
    F["newgoal"] = int(m.group(1).replace(",", ""))
    F["delta"] = _int(_t(pg, "[data-testid=vs-ready]"), r"(\d+) point")
    F["ring1"] = int(pg.locator("[data-testid=ring]").get_attribute("data-value"))
    r.claim("tab", "a 'Level up' marker shows on the wishes row", pg.locator("[data-testid=levelup-wishes]").count() == 1)
    r.claim("tab", "'This change closes the gap' shows", pg.locator("[data-testid=closes-gap]").count() == 1)
    r.to(pg.locator("[data-testid=wi-change]"), 0.3, 0.5, scroll=False); r.hold_until(L["tab"] * 0.28)
    r.scroll(240, pause=18); r.wait(300)   # the sticky "Try a What If" bar covers the bottom of the ladder at the top of the page
    r.to(pg.locator("[data-testid=levelup-wishes]"), 0.5, 0.5, scroll=False, steps=22); r.hold_until(L["tab"] * 0.55)
    r.scroll(-240, pause=18); r.wait(300)
    r.to(pg.locator("[data-testid=vs-ready]"), 0.4, 0.5, scroll=False, steps=22); r.hold_until(L["tab"] * 0.8)
    r.to(pg.locator("[data-testid=closes-gap]"), 0.3, 0.5, scroll=False, steps=22); r.hold_until(L["tab"]); r.done("tab")

    # 12. compare
    r.scene("compare")
    r.click(pg.locator(".scen-compare"))
    pg.wait_for_selector("[data-testid=compare-table]", timeout=5000); r.wait(900)
    row = pg.locator("[data-testid=compare-table] tr", has_text="Goal lasts in").first.inner_text()
    lasts = re.findall(r"(\d+) of 100", row)
    r.claim("compare", "the compare table shows 'goal lasts in' for the baseline and the What If", len(lasts) >= 2)
    F["lasts0"], F["lasts1"] = int(lasts[0]), int(lasts[1])
    r.move(520, 450); r.hold_until(L["compare"] * 0.35)
    gap = pg.locator("[data-testid=gap-row]")
    if gap.count(): r.to(gap, 0.6, 0.5, scroll=False); r.wait(600)
    r.hold_until(L["compare"] - 1.8)
    r.click(pg.locator(".scen-tab", has_text="Baseline").first); r.wait(900)
    r.hold_until(L["compare"]); r.done("compare")

    # 13. trust: a cited rule answer, a refused stock pick
    for sid, q, sel in (("rule", RULE_Q, ".turn .cites"), ("stock", STOCK_Q, ".refused")):
        r.scene(sid)
        ask = pg.locator("#ask-input"); r.to(ask); pg.mouse.click(r.x, r.y)
        r.type(q, delay=40); r.wait(300); pg.keyboard.press("Enter")
        pg.wait_for_selector(sel, timeout=180000)
        try: pg.locator(".turns .spinner").first.wait_for(state="detached", timeout=90000)
        except Exception: pass
        r.wait(800); r.mark_r(sid)
        pg.locator(".turn").last.scroll_into_view_if_needed(); r.wait(3500)
        r.done(sid)

    # 14. token costs, one line
    r.scene("cost")
    pg.evaluate("window.scrollTo(0,0)"); r.wait(600)
    cb = pg.locator("[data-testid=cost-block]")
    r.to(cb, 0.5, 0.3, scroll=False); r.wait(600)
    cost = float(re.search(r"\$(\d+\.\d+)", _t(pg, "[data-testid=cost-run]")).group(1))
    r.claim("cost", f"this plan cost under one cent (page: ${cost})", cost < 0.01)
    r.hold_until(L["cost"]); r.done("cost")

    r.scene("end"); r.wait(500); r.done("end")


def consistency_v3(r, figs):
    """Every number the narration says must be in the visible page text of its scene; every phrase listed must be visible. Fails loudly."""
    problems, report = [], []
    for sid, mode, text in SCENES:
        if sid not in r.ended and sid not in ("title", "end"): continue
        tmpl = TEMPL[sid]
        if mode == "card":
            if sid == "end" and "end" not in r.ended: continue
            card = " ".join(re.sub(r"<[^>]+>", "", s) for s in CARDS[sid])
            pool = pool_all = norm(card); pnums = page_numbers(card)
        else:
            snaps = r.snaps.get(sid, [])
            pool_all = norm(" ".join(t for _, t in snaps))
            use = [t for tm, t in snaps if sid in r.rmark and tm >= r.rmark[sid]] if mode == "fit" and sid in r.rmark else [t for _, t in snaps]
            pnums = page_numbers(" ".join(use) if use else "")
            pool = pool_all
        heard = spoken_numbers(text)
        for k in re.findall(r"\{(\w+)\}", tmpl):                       # each figure placeholder: its digits are on screen
            if float(figs[k]) not in pnums: problems.append(f"[{sid}] figure {k}={figs[k]} is not in the visible page text")
        for v in spoken_numbers(re.sub(r"\{\w+\}", " ", tmpl)):         # each fixed number written in the narration
            if float(v) not in pnums: problems.append(f"[{sid}] the narration says {v:g} but the screen does not show it")
        for v in heard:
            if float(v) not in pnums: problems.append(f"[{sid}] spoken number {v:g} is not in the visible page text")
        for ph in SHOW[sid]:
            ph = norm(ph.format(**figs))
            if ph not in pool_all: problems.append(f"[{sid}] the screen never shows '{ph}'")
        report.append(f"  {sid:8s} numbers heard {sorted(set(heard)) or '-'}; phrases {len(SHOW[sid])}: ok" if not any(p.startswith(f'[{sid}]') for p in problems) else f"  {sid:8s} FAILED")
    for sid, what, ok in r.claims:
        if not ok: problems.append(f"[{sid}] claim failed: {what}")
    print("consistency check (spoken numbers and phrases against the visible text of each scene):"); print("\n".join(report))
    print(f"  claims checked: {len(r.claims)}, failed: {sum(1 for c in r.claims if not c[2])}")
    return problems


def record_v3(stop_after=None, figures_only=False):
    from playwright.sync_api import sync_playwright
    L = {sid: 0.0 for sid, *_ in SCENES_V3} if figures_only else {sid: scene_len(i) for i, (sid, m, t) in enumerate(SCENES)}
    import shutil
    if not figures_only: shutil.rmtree(RAW, ignore_errors=True)
    os.makedirs(os.path.join(RAW, "frames"), exist_ok=True)
    errors, frames, stopped = [], [], None
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        ctx = b.new_context(viewport={"width": W, "height": H}, extra_http_headers={"X-Enough-Test": "1"})
        ctx.add_init_script(CURSOR_JS)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: errors.append(str(e)))
        r = Rec3(pg, stop_after)
        if not figures_only:
            cdp = ctx.new_cdp_session(pg)
            def on_frame(ev):
                t = time.time() - r.t0; path = os.path.join(RAW, "frames", f"{len(frames):06d}.jpg")
                with open(path, "wb") as fh: fh.write(base64.b64decode(ev["data"]))
                frames.append((t, path))
                try: cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
                except Exception: pass
            cdp.on("Page.screencastFrame", on_frame)
            r.t0 = time.time()
            cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "maxWidth": W, "maxHeight": H, "everyNthFrame": 1})
        pg.goto(URL); pg.wait_for_timeout(1500)
        try: flow_v3(pg, r, L)
        except StopRun as e: stopped = str(e); print(f"  stopped after '{stopped}' (dry run)")
        r.marks.append(("_end_probe", r.now()))
        log = {"marks": [m for m in r.marks if m[0] != "_end_probe"], "end": r.now(), "errors": errors, "figs": r.figs, "partial": bool(stopped)}
        if not figures_only:
            pg.screenshot(path=os.path.join(WORK, "last_state_v3.png")); cdp.send("Page.stopScreencast")
        ctx.close(); b.close()
    print("figures read from the live page:", json.dumps(r.figs))
    print("page errors:", errors)
    if figures_only:
        json.dump(r.figs, open(FIG_FILE, "w", encoding="utf-8"), indent=1)
        failed = [c for c in r.claims if not c[2]]
        for c in failed: print("CLAIM FAILED:", c)
        print("wrote", FIG_FILE); return
    log["frames"] = frames
    json.dump(log, open(os.path.join(RAW, "marks.json"), "w"), indent=1)
    print(len(frames), "frames")
    saved = load_figs(required=False)
    problems = [f"figure {k}: live page {v}, but the narration was made with {saved[k]}: run the figures and tts stages again"
                for k, v in r.figs.items() if k in saved and saved[k] != v]
    problems += consistency_v3(r, {**saved, **r.figs})
    if problems:
        print("\nCONSISTENCY CHECK FAILED:"); [print("  -", x) for x in problems]
        raise SystemExit(1)
    print("consistency check passed")


if __name__ == "__main__":
    args = sys.argv[1:]
    v3 = "--v3" in args
    stop_after = args[args.index("--stop-after") + 1] if "--stop-after" in args else None
    stages = [a for a in args if not a.startswith("--") and a != stop_after]
    if v3:
        use_v3()
        figs = {} if "figures" in stages else load_figs()
        SCENES = build_scenes_v3(figs) if figs else []
        if "figures" in stages: record_v3(stop_after="compare", figures_only=True)
        else:
            stages = stages or ["tts", "record", "assemble"]
            if "tts" in stages: tts()
            if "record" in stages: record_v3(stop_after)
            if "assemble" in stages: assemble()
    else:
        stages = stages or ["tts", "record", "assemble"]
        if "tts" in stages: tts()
        if "record" in stages: record()
        if "assemble" in stages: assemble()
