"""Settings for Enough Lite.

.env files are read from the project folder first, then from each parent folder up to three levels (the course folder).
A variable that is already set in the environment always wins, and a nearer .env file wins over a farther one.
The model names live here and only here. Provider: Claude Haiku 5.5 when ANTHROPIC_API_KEY is set (override the model with
ANTHROPIC_MODEL); otherwise gpt-6-luna on the OpenAI API when OPENAI_API_KEY is set (override with OPENAI_MODEL).
ENOUGH_PROVIDER=anthropic|openai forces one.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent          # app
LITE_DIR = APP_DIR.parent   # project root
DATA_DIR = APP_DIR / "data"
RUNS_DIR = LITE_DIR / "runs"
WEB_DIST = LITE_DIR / "web" / "dist"

DEFAULT_MODEL = "claude-haiku-5-5"        # Anthropic (ANTHROPIC_API_KEY)
DEFAULT_OPENAI_MODEL = "gpt-6-luna"      # OpenAI (OPENAI_API_KEY)
ENV_LEVELS_UP = 3
# planning rules (not secrets; change them here)
HIGH_RATE_DEBT = 0.07          # debt at or above 7% a year is "high rate": paying it off beats expected real returns
MATCH_MIN_YEARS_LEFT = 2       # no employer-match advice with fewer than this many working years left
SURVIVOR_SPEND_SHARE = 0.75    # after the first death of a couple, the survivor spends this share (a common rule of thumb)


def load_env_files() -> list[Path]:
    """Load .env from the project root and up to three parent folders. Returns the files read (paths only, never values)."""
    read = []
    folder = LITE_DIR
    for _ in range(ENV_LEVELS_UP + 1):
        f = folder / ".env"
        if f.is_file():
            load_dotenv(f, override=False)
            read.append(f)
        if folder.parent == folder:
            break
        folder = folder.parent
    return read


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    model: str
    has_key: bool
    run_budget_usd: float
    session_budget_usd: float
    total_budget_usd: float
    rate_per_minute: int
    rate_per_day: int
    trust_proxy: bool
    write_run_log: bool
    provider: str = "anthropic"


def pick_provider() -> str:
    """Anthropic when its key is set, else OpenAI when OPENAI_API_KEY is set. ENOUGH_PROVIDER forces one."""
    forced = os.getenv("ENOUGH_PROVIDER", "").strip().lower()
    if forced in ("anthropic", "openai"):
        return forced
    if os.getenv("ANTHROPIC_API_KEY", "").strip():
        return "anthropic"
    return "openai" if os.getenv("OPENAI_API_KEY", "").strip() else "anthropic"


def get_settings() -> Settings:
    provider = pick_provider()
    if provider == "openai":
        model = os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_OPENAI_MODEL
        has_key = bool(os.getenv("OPENAI_API_KEY", "").strip())
    else:
        model = os.getenv("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL
        has_key = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    return Settings(
        model=model,
        has_key=has_key,
        run_budget_usd=_float("ENOUGH_RUN_BUDGET_USD", 0.05),
        session_budget_usd=_float("ENOUGH_SESSION_BUDGET_USD", 0.50),
        total_budget_usd=_float("ENOUGH_TOTAL_BUDGET_USD", 5.00),
        rate_per_minute=_int("ENOUGH_RATE_PER_MINUTE", 6),
        rate_per_day=_int("ENOUGH_RATE_PER_DAY", 60),
        trust_proxy=os.getenv("ENOUGH_TRUST_PROXY", "0") == "1",
        write_run_log=os.getenv("ENOUGH_RUN_LOG", "1") != "0",
        provider=provider,
    )


load_env_files()
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
