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
OUT = os.path.join(HERE, "enough_demo.mp4")
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
    with open(os.path.join(HERE, "narration.txt"), "w", encoding="utf-8") as f:
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


if __name__ == "__main__":
    stages = sys.argv[1:] or ["tts", "record", "assemble"]
    if "tts" in stages: tts()
    if "record" in stages: record()
    if "assemble" in stages: assemble()
