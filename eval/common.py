"""Shared helpers for the Enough Lite eval: paths, case and run loading, event digging."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
RUNS_DIR = Path(os.environ.get("EVAL_RUNS_DIR") or EVAL_DIR / "runs")   # override to keep mock runs apart
CASES_PATH = EVAL_DIR / "cases.jsonl"
REPO = EVAL_DIR.parent                           # the project folder (holds .env, app/, eval/)
# The old full app (only make_cases.py and benchmark.py read it). Not part of this repo; set ENOUGH_OLD_APP to its folder to use them.
ROOT = Path(os.environ["ENOUGH_OLD_APP"]) if os.environ.get("ENOUGH_OLD_APP") else REPO / "_old_app_not_included"
PERSONAS = ROOT / "output" / "synth" / "personas.jsonl.gz"
BENCH_FULL = ROOT / "output" / "synth_tree_full" / "raw"
BENCH_TREE = ROOT / "output" / "synth_tree" / "raw"
DEFAULT_URL = "http://127.0.0.1:8020"            # the lite app; the eval never starts or stops it


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ (never overwrites, never prints)."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export ").strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except OSError:
        pass


def load_project_env() -> None:
    """Read .env from the project folder, then up to three folders above, as the app does (nearer wins; the shell environment wins)."""
    for folder in (REPO, *list(REPO.parents)[:3]):
        load_env_file(folder / ".env")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for x in path.read_text(encoding="utf-8").splitlines():
        if x.strip():
            try:
                out.append(json.loads(x))
            except json.JSONDecodeError:
                pass        # a line torn by two writers at once in the app's meter
    return out


def load_cases(kinds: set[str] | None = None) -> list[dict]:
    cases = read_jsonl(CASES_PATH)
    if kinds:
        cases = [c for c in cases if c.get("kind", "base") in kinds]
    return cases


def run_path(case_id: str) -> Path:
    return RUNS_DIR / f"{case_id}.json"


def load_run(case_id: str) -> dict | None:
    p = run_path(case_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def dig(run: dict) -> dict:
    """Pull the parts of an event log the checks need."""
    ev = run.get("events") or []
    out = {"events": ev, "plan": None, "agents": [], "tools": [], "cost": None, "errors": [], "done": False}
    for e in ev:
        t = e.get("type")
        if t == "plan":
            out["plan"] = e.get("plan")
        elif t == "agent_done":
            out["agents"].append(e)
        elif t == "tool":
            out["tools"].append(e)
        elif t == "cost":
            out["cost"] = e
        elif t == "error":
            out["errors"].append(e.get("message", ""))
        elif t == "done":
            out["done"] = True
    return out


def usage_of(run: dict) -> dict:
    """Tokens and dollars from the events. Dollars: the cost event if present, else the sum of agent_done."""
    d = dig(run)
    tin = sum((a.get("tokens") or {}).get("input", 0) for a in d["agents"])
    tca = sum((a.get("tokens") or {}).get("cached", 0) for a in d["agents"])
    tout = sum((a.get("tokens") or {}).get("output", 0) for a in d["agents"])
    usd_agents = sum(float(a.get("cost_usd") or 0) for a in d["agents"])
    c = d["cost"] or {}
    usd = float(c["total_usd"]) if c.get("total_usd") is not None else usd_agents
    return {"input": tin, "cached": tca, "output": tout,
            "total_tokens": int(c.get("total_tokens") or (tin + tca + tout)),
            "usd": usd, "budget_usd": c.get("budget_usd")}


def plan_text(plan: dict) -> str:
    """All the adviser's words in the plan, joined."""
    if not plan:
        return ""
    parts = []
    n = plan.get("needs") or {}
    parts.append(n.get("line", ""))
    parts.append((plan.get("wants") or {}).get("line", ""))
    parts.append((plan.get("wishes") or {}).get("line", ""))
    for a in plan.get("actions") or []:
        parts += [a.get("title", ""), a.get("why", "")]
    parts += list(plan.get("family_moments") or [])
    parts.append((plan.get("neighbors") or {}).get("note", "") or "")
    return "\n".join(p for p in parts if p)


def flat_numbers(obj) -> list[float]:
    """Every numeric leaf in a JSON-like object, plus numbers written inside its strings."""
    out: list[float] = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, str):
        return [n for n, _ in extract_numbers(obj)]
    if isinstance(obj, dict):
        for v in obj.values():
            out += flat_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += flat_numbers(v)
    return out


_NUM = re.compile(r"(?<![\w.])(\$)?\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s?(k|K|m|M|million|thousand|billion|bn|%|percent)?(?![\w])")


def extract_numbers(text: str) -> list[tuple[float, str]]:
    """Numbers in prose as (value, raw). Handles $, commas, k, million, percent."""
    res = []
    for m in _NUM.finditer(text or ""):
        whole = m.group(2).replace(",", "")
        val = float(whole + (m.group(3) or ""))
        suf = (m.group(4) or "").lower()
        if suf in ("k", "thousand"):
            val *= 1e3
        elif suf in ("m", "million"):
            val *= 1e6
        elif suf in ("billion", "bn"):
            val *= 1e9
        res.append((val, m.group(0).strip()))
    return res


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    i = (len(s) - 1) * q
    lo, hi = int(i), min(int(i) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (i - lo)
