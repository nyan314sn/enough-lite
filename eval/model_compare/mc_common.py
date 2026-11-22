import json, os, sys, threading, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "eval"), str(ROOT)]
JUDGE_MODEL = "claude-sonnet-5-5"
JUDGE_PRICE = (3.0, 15.0)      # USD per million tokens (assumed Sonnet-class list price; not read from the API)
COST_LOG = HERE / "cost_log.jsonl"
_l = threading.Lock()

def load_env():
    import common
    common.load_project_env()

def log_cost(what, usd, note=""):
    with _l:
        with open(COST_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%H:%M:%S"), "what": what, "usd": round(usd, 5), "note": note}) + "\n")

def total_cost():
    if not COST_LOG.exists(): return 0.0
    return sum(json.loads(l)["usd"] for l in COST_LOG.read_text(encoding="utf-8").splitlines() if l.strip())

def judge_call(system, user, max_tokens=600, what="judge"):
    import anthropic
    load_env()
    c = getattr(judge_call, "_c", None)
    if c is None:
        c = judge_call._c = anthropic.Anthropic(max_retries=3)
    kw = dict(model=JUDGE_MODEL, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}])
    try:
        r = c.messages.create(thinking={"type": "disabled"}, **kw)
    except anthropic.BadRequestError:
        r = c.messages.create(**kw)
    usd = (r.usage.input_tokens * JUDGE_PRICE[0] + r.usage.output_tokens * JUDGE_PRICE[1]) / 1e6
    log_cost(what, usd, f"{r.usage.input_tokens} in {r.usage.output_tokens} out")
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")

def parse_json(text):
    import re
    m = re.search(r"\{.*\}", text, re.S)
    try: return json.loads(m.group(0)) if m else {}
    except Exception: return {}

def load_plans(arm):
    d = HERE / "raw" / f"plans_{arm}"
    out = {}
    for f in d.glob("*.json"):
        r = json.loads(f.read_text(encoding="utf-8"))
        r["plan"] = next((e["plan"] for e in r["events"] if e.get("type") == "plan"), None)
        out[r["id"]] = r
    return out

def strip_text(plan):
    p = json.loads(json.dumps(plan))
    p.pop("chart", None)
    for k in ("needs", "wants", "wishes"):
        (p.get(k) or {}).pop("line", None)
    p.pop("actions", None); p.pop("family_moments", None)
    (p.get("neighbors") or {}).pop("note", None)
    return p
