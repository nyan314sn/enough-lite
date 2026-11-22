"""WCAG AA contrast for the Royal Indigo tokens in web/src/styles.css, light and dark. Writes contrast.txt beside this file.
Run: python docs/loop/theme/contrast.py (the conda python)"""
import re, pathlib
here = pathlib.Path(__file__).parent
css = (here.parent.parent.parent / "web/src/styles.css").read_text(encoding="utf-8")

def block(sel):
    i = css.index(sel + " {"); j = css.index("\n}", i)
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", css[i:j]))
light = block(":root"); dark = {**light, **block('[data-theme="dark"]')}

def parse(v, toks, over=None):
    v = v.strip()
    m = re.match(r"var\((--[\w-]+)\)", v)
    if m: return parse(toks[m.group(1)], toks, over)
    if v.startswith("#"):
        v = v[1:]; return tuple(int(v[i:i+2], 16) for i in (0, 2, 4)) + (1.0,)
    m = re.match(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", v)
    return (int(m[1]), int(m[2]), int(m[3]), float(m[4]))

def flat(c, under):
    a = c[3]; return tuple(c[i] * a + under[i] * (1 - a) for i in range(3))

def lum(c):
    f = lambda x: (x / 255 / 12.92) if x / 255 <= 0.03928 else (((x / 255) + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])

def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True); return (la + 0.05) / (lb + 0.05)

# (foreground, background, minimum, what). Backgrounds with alpha are laid over the surface (cards) first.
T = 4.5; L = 3.0
pairs = [
 ("text-primary", "bg-canvas", T, "body text on the page"), ("text-primary", "bg-surface", T, "body text on a card"),
 ("text-secondary", "bg-surface", T, "secondary text on a card"), ("text-secondary", "bg-subtle", T, "secondary text on a subtle fill"),
 ("text-muted-aa", "bg-surface", T, "app muted text (--muted) on a card"), ("text-muted-aa", "bg-canvas", T, "app muted text on the page"), ("text-muted-aa", "bg-subtle", T, "app muted text on a subtle fill"),
 ("text-muted", "bg-surface", T, "muted text on a card"), ("text-muted", "bg-canvas", 3.0, "raw token on canvas: not used for small text (use -aa)"), ("text-muted", "bg-subtle", 3.0, "raw token on subtle: not used for small text (use -aa)"),
 ("brand-accent", "bg-surface", T, "link and small accent text on a card"), ("brand-accent", "bg-canvas", T, "accent text on the page"),
 ("brand-accent-hover", "bg-surface", T, "accent hover text on a card"), ("brand-accent-hover", "brand-accent-tint", T, "chip and badge text on the accent tint"),
 ("brand-accent", "brand-accent-tint", T, "step link on accent tint"),
 ("on-accent", "brand-accent", T, "primary button text"), ("on-accent", "brand-accent-hover", T, "primary button hover text"),
 ("text-primary", "bg-user-bubble", T, "user chat bubble"), ("brand-accent-hover", "bg-surface", T, "assistant-side labels"),
 ("status-gain-ink", "status-gain-bg", T, "gain tag and delta text"), ("status-gain", "bg-surface", T, "gain figure on a card"),
 ("on-gain", "status-gain", T, "check mark on gain"),
 ("status-loss", "status-loss-bg", T, "Short $X a year banner"), ("status-loss-ink", "status-loss-bg", T, "shortfall sub text"), ("status-loss", "bg-surface", T, "shortfall figure on a card"),
 ("status-warn", "status-warn-bg", T, "amber text on its fill (warning figures)"), ("status-warn-ink", "status-warn-bg", T, "close banner and warning text"),
 ("status-warn", "bg-surface", T, "amber figure on a card"), ("status-warn", "bg-subtle", 3.0, "amber on subtle: only large figures (token as given: 4.47)"), ("status-gain", "bg-subtle", 3.0, "gain on subtle: only the large Needs figure (4.46)"), ("status-loss", "bg-subtle", T, "loss on subtle"),
 ("status-loss", "bg-canvas", T, "loss text on the page"),
 ("text-primary", "status-warn-bg", T, "text on the starting-points box"),
 ("brand-accent", "bg-surface", L, "focus ring against a card (3:1 for UI)"), ("brand-accent", "bg-canvas", L, "focus ring against the page"),
 ("chart-1", "bg-surface", L, "chart line 1"), ("chart-2", "bg-surface", L, "chart 2"), ("chart-3", "bg-surface", L, "chart 3"), ("chart-4", "bg-surface", L, "chart 4"),
 ("chart-5", "bg-surface", L, "chart 5 (costs line)"), ("chart-6", "bg-surface", L, "chart 6"), ("chart-8", "bg-surface", L, "chart 8"),
 ("border-strong", "bg-surface", 1.0, "hairline (decorative, no minimum)"),
]
out = []; bad = 0
for name, toks in (("LIGHT", light), ("DARK", dark)):
    out.append(f"== {name} ==")
    surf = parse(toks["--bg-surface"], toks)[:3]
    for fg, bg, mn, what in pairs:
        b = flat(parse(toks["--" + bg], toks), surf)
        f = flat(parse(toks["--" + fg], toks), b)
        r = ratio(f, b); ok = r >= mn
        bad += (not ok)
        out.append(f"{'PASS' if ok else 'FAIL'}  {r:5.2f}  (min {mn})  {fg} on {bg}  -  {what}")
out.append(f"\nfailures: {bad}")
(here / "contrast.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
