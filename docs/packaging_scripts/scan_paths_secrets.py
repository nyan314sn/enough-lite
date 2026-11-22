"""List file:line of absolute user paths and secret-looking strings. Never prints a secret value."""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SKIP = {".venv", "node_modules", "dist", "__pycache__", ".pytest_cache", "screens", "img", "packaging_scripts"}
EXT = {".py", ".md", ".json", ".jsonl", ".txt", ".html", ".ts", ".tsx", ".js", ".css", ".toml", ".example", ".mock", ".gitignore", ".yml", ".yaml", ".cfg", ".ini", ".bat", ".ps1", ".sh"}
PATHS = re.compile(r"C:[\/]+Users|C:\\Users|OneDrive|[\/]Users[\/]Pi\b|miniconda3|Yale - Class|hw-Final", re.I)
SECRETS = [
    ("anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")),
    ("openai-style key", re.compile(r"\bsk-[A-Za-z0-9]{20,}")),
    ("bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("key assignment with value", re.compile(r"(API_KEY|SECRET|TOKEN|PASSWORD)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{12,}")),
    ("aws key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
]
for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or any(s in p.relative_to(ROOT).parts for s in SKIP):
        continue
    if p.suffix.lower() not in EXT and p.name not in {".env", ".env.example", ".gitignore"}:
        continue
    if p.stat().st_size > 3_000_000:
        continue
    rel = p.relative_to(ROOT).as_posix()
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        continue
    for i, line in enumerate(lines, 1):
        if PATHS.search(line):
            print(f"PATH\t{rel}:{i}")
        for kind, rx in SECRETS:
            if rx.search(line):
                print(f"SECRET?\t{kind}\t{rel}:{i}")
