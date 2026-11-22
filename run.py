"""Start Enough Lite: `python run.py` -> http://localhost:8020

Port: PORT (set by most hosting services; then the app listens on all interfaces), else BACKEND_PORT, else 8020.
HOST overrides the interface. Never uses 8000 or 8010. Opens no browser.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from app import config  # noqa: E402  (loads .env files)

FORBIDDEN = {8000, 8010}


def main() -> None:
    import uvicorn

    hosted = bool(os.getenv("PORT"))
    port = int(os.getenv("PORT") or os.getenv("BACKEND_PORT") or 8020)
    if port in FORBIDDEN:
        print(f"Port {port} is kept for other apps. Using 8020.")
        port = 8020
    host = os.getenv("HOST") or ("0.0.0.0" if hosted else "127.0.0.1")
    s = config.get_settings()
    print(f"Enough Lite on http://{'localhost' if host == '127.0.0.1' else host}:{port}  "
          f"(model {s.model}; AI key {'found' if s.has_key else 'missing: plans use tools and templates only'})")
    uvicorn.run("app.main:app", host=host, port=port, reload=False, log_level=os.getenv("LOG_LEVEL", "info"),
                app_dir=str(HERE), proxy_headers=True)


if __name__ == "__main__":
    main()
