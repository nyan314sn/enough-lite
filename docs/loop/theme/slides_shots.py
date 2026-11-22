"""Screenshot each of the 10 slides at 1280x720 (file:// URL + #/N)."""
import os, sys, pathlib
from playwright.sync_api import sync_playwright
root = pathlib.Path(__file__).resolve().parents[3]
out = pathlib.Path(__file__).parent
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge"); pg = b.new_page(viewport={"width": 1280, "height": 720})
    for n in range(1, 11):
        pg.goto((root / "slides.html").as_uri() + f"#/{n-1}"); pg.reload(); pg.wait_for_timeout(900)
        pg.screenshot(path=str(out / f"slide_{n:02d}.png"))
    b.close()
