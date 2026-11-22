"""Shared helpers for the simulated-user tester: env, Haiku calls with usage metering, paths, turn normalising."""
import json
import os
import pathlib
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
RUNS = HERE / "runs"
JUDGED = HERE / "judged"
RUNS.mkdir(exist_ok=True)
JUDGED.mkdir(exist_ok=True)
APP = os.getenv("ENOUGH_APP_URL", "http://localhost:8020")
MODEL = os.getenv("SIM_MODEL", "claude-haiku-5-5")
# prices per million tokens, as the app reports them in /api/costs
PRICE_IN, PRICE_OUT = 0.10, 0.50
USAGE_FILE = HERE / "usage.json"
_lock = threading.Lock()


def load_env():
    """Load ANTHROPIC_API_KEY from .env in the project folder, then up to three folders above (as the app does), without printing it."""
    for d in [HERE.parent, *list(HERE.parent.parents)[:3]]:
        f = d / ".env"
        if f.exists():
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY=") and not os.getenv("ANTHROPIC_API_KEY"):
                    os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY not found (set it, or put it in .env in the project folder or the folder above)")


_client = None


def client():
    global _client
    if _client is None:
        load_env()
        import anthropic
        _client = anthropic.Anthropic(max_retries=3)
    return _client


def add_usage(role, i, o):
    with _lock:
        u = json.loads(USAGE_FILE.read_text()) if USAGE_FILE.exists() else {}
        r = u.setdefault(role, {"input": 0, "output": 0, "calls": 0})
        r["input"] += i
        r["output"] += o
        r["calls"] += 1
        USAGE_FILE.write_text(json.dumps(u))


def usage_cost():
    u = json.loads(USAGE_FILE.read_text()) if USAGE_FILE.exists() else {}
    out = {}
    for k, v in u.items():
        out[k] = dict(v, usd=round(v["input"] * PRICE_IN / 1e6 + v["output"] * PRICE_OUT / 1e6, 5))
    return out


def haiku(role, system, user, max_tokens=1000):
    """One Haiku call. No temperature or sampling params; effort low."""
    c = client()
    last = None
    for attempt in range(3):
        try:
            r = c.messages.create(model=MODEL, max_tokens=max_tokens, system=system,
                                  messages=[{"role": "user", "content": user}],
                                  extra_body={"output_config": {"effort": "low"}})
            add_usage(role, r.usage.input_tokens, r.usage.output_tokens)
            return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()
        except Exception as e:  # network blips, overload
            last = e
            time.sleep(2 + attempt * 3)
    raise RuntimeError(f"haiku failed: {type(last).__name__}")


def parse_json(text):
    """Pull the first JSON object or array out of a model reply."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        s = s[s.find("\n") + 1:] if "\n" in s else s
    for opener, closer in (("[", "]"), ("{", "}")):
        a, b = s.find(opener), s.rfind(closer)
        if a != -1 and b > a:
            try:
                return json.loads(s[a:b + 1])
            except Exception:
                pass
    return None


def load_personas():
    return json.loads((HERE / "personas.json").read_text(encoding="utf-8"))


def normalize_turns(run):
    """Flat list of app turns for the judge: each has the person's message, the app's reply and what it assumed."""
    out = []
    for t in run.get("intake_turns", []):
        out.append(dict(ref=f"i{t['n']}", phase="intake", user=t["user"], clicked=t.get("clicked"),
                        app=t["reply"], question=(t.get("question") or {}).get("text"),
                        chips=(t.get("question") or {}).get("quick_answers"), new_assumed=t.get("new_assumed", []),
                        missing=t.get("missing", [])))
    for t in run.get("plan_turns", []):
        out.append(dict(ref=f"a{t['n']}", phase="plan", user=t["user"], clicked=t.get("clicked"),
                        app=t["text"], question=None, chips=t.get("quick_answers"), kind=t.get("kind"),
                        status=t.get("status"), new_assumed=[], missing=[]))
    return out
