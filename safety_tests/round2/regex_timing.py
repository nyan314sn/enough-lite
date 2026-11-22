"""Offline regex timing for the new intake code. No server, no AI calls.

Usage:  python regex_timing.py            (parent: runs one child per module, 90 s cap each, reports > 100 ms)
        python regex_timing.py --worker MODULE
Every compiled pattern at module level (also inside lists, dicts, tuples) is run, with search and a full finditer
walk, over worst-case strings of 2,000 characters (the /api/ask cap) and 4,000 (the /api/intake cap). Then the public
one-argument functions are called on the same strings (they hold patterns built inside the function). Anything over
100 ms is printed. A child that hits the cap is reported as a hang, with the item in flight.
"""
import importlib
import inspect
import re
import subprocess
import sys
import time
from pathlib import Path

LITE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(LITE))
MODULES = ["app.safety", "app.agents.turn_guard", "app.agents.turn_read", "app.agents.parser", "app.agents.parser_extra",
           "app.agents.intake_support", "app.agents.intake_answers", "app.agents.intake", "app.ask_intent"]
LIMIT = 0.100
CAP = 90
ONE_ARG = ("text", "t", "s", "message", "clause", "piece", "word", "quote", "user", "txt", "q", "question")


def strings(n):
    zw = "​"
    tags = "".join(chr(0xE0000 + ord(c)) for c in "ignore previous instructions")
    return {
        "a": "a" * n, "digits": "1" * n, "comma_digits": "1," * (n // 2), "dot_digits": "1." * (n // 2), "dollar": "$" * n,
        "spaces": " " * n, "dots": "." * n, "bang": "!" * n, "qmarks": "?" * n, "newlines": "\n" * n, "word_space": "a " * (n // 2),
        "num_space": "1 " * (n // 2), "money_k": "$1k " * (n // 4), "money_dollar": "$1 " * (n // 3), "sentences": "a. " * (n // 3),
        "questions": "why? " * (n // 5), "q_money": "Why $1,000? " * (n // 12), "paren": "(" * n, "close_paren": ")" * n,
        "k401": "401(k) " * (n // 7), "k401_open": "401(" * (n // 4), "retire": "retire at 65, " * (n // 14),
        "between": "between 1 and " * (n // 14), "range_dash": "1-" * (n // 2), "range_to": "1 to " * (n // 5), "range_k": "1k to " * (n // 6),
        "not": "not " * (n // 4), "no": "no " * (n // 3), "and": "and " * (n // 4), "also": "also, " * (n // 6), "comma": "," * n,
        "semis": "; " * (n // 2), "zero_words": "zero " * (n // 5), "twenty": "twenty " * (n // 7), "hundred_and": "one hundred and " * (n // 16),
        "a_hundred": "a hundred " * (n // 10), "thousand": "thousand " * (n // 9), "tw_thou": "twenty thousand " * (n // 16),
        "lt": "<" * n, "lt_a": "<a " * (n // 3), "comment_open": "<!--" * (n // 4), "comment_long": "<!--" + "a" * n,
        "style_hidden": "<a style='display:none'>" * (n // 24), "style_nodisp": "<a style='" * (n // 10),
        "style_long": "<a style='" + "x" * 290 + "' " * 3 + ("<a style='" + "x" * 290) * (n // 300),
        "hidden_attr": "<a hidden>" * (n // 10), "div_nest": "<div hidden>" * (n // 12) + "x",
        "angle_text": "<a" + " b" * (n // 2), "zero_width": zw * n, "zw_in_word": ("re" + zw) * (n // 3), "tag_chars": tags * (n // 28),
        "bidi": "‮" * n, "amp": "&amp;" * (n // 5), "amp_bare": "&" * n, "nfkc": "１" * n,
        "word_k": "k" * n, "mortgage": "mortgage " * (n // 9), "owe": "I owe 1 on " * (n // 11), "month": "a month " * (n // 8),
        "per": "per year " * (n // 9), "dollars_a": "$" + "1,000" * (n // 5), "pct": "5% " * (n // 3), "slash": "/" * n,
        "colon": "system: " * (n // 8), "ignore": "ignore the " * (n // 11), "reveal": "reveal " + "a " * (n // 2),
        "show_other": "show " + "a " * (n // 2) + "other users", "hide": "hide " + "a " * (n // 2),
        "move_medicaid": "move " + "x " * (n // 2) + "medicaid", "wire": "wire the money " + "a " * (n // 2), "kill": "kill " + "a " * (n // 2),
        "stop": "stop " * (n // 5), "apos": "'" * n, "word_apos": "don't " * (n // 6), "dash": "-" * n, "en_dash": "–" * n,
        "alnum": "a1" * (n // 2), "mixed_money": "1,2,3 " * (n // 6), "state": "new " * (n // 4), "ages": "12, 9 and 5 " * (n // 12),
        "kids": "2 kids " * (n // 7), "equals": "on1=" * (n // 4), "js": "javascript:" * (n // 11),
    }


def patterns(mod):
    seen = []

    def walk(x, name, depth=0):
        if isinstance(x, re.Pattern):
            seen.append((name, x))
        elif depth < 3 and isinstance(x, (list, tuple, set, frozenset)):
            for i, v in enumerate(x):
                walk(v, f"{name}[{i}]", depth + 1)
        elif depth < 3 and isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{name}[{k!r}]", depth + 1)
    for k, v in vars(mod).items():
        if not k.startswith("__"):
            walk(v, k)
    return seen


def timed(fn):
    t = time.perf_counter()
    try:
        fn()
    except Exception as e:  # noqa: BLE001 a crash is reported, not hidden
        return time.perf_counter() - t, type(e).__name__
    return time.perf_counter() - t, ""


def report(kind, name, label, n, secs, err=""):
    if secs > LIMIT or err:
        print(f"SLOW {secs*1000:8.1f} ms  {kind} {name}  on {label} (n={n}) {('ERR ' + err) if err else ''}", flush=True)


def worker(modname):
    mod = importlib.import_module(modname)
    short = modname.split(".")[-1]
    worst, count = 0.0, 0
    pats = patterns(mod)
    funcs = []
    for fname, fn in vars(mod).items():
        if fname.startswith("_") or not inspect.isfunction(fn) or fn.__module__ != mod.__name__:
            continue
        req = [p for p in inspect.signature(fn).parameters.values() if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        if len(req) == 1 and req[0].name in ONE_ARG:
            funcs.append((fname, fn))
    for n in (2000, 4000):
        for label, s in strings(n).items():
            for name, pat in pats:
                print(f"START {short}.{name} {label} {n}", flush=True)
                s1, e1 = timed(lambda: pat.search(s))
                s2, e2 = timed(lambda: sum(1 for _ in pat.finditer(s)))
                count, worst = count + 1, max(worst, s1, s2)
                report("pattern", f"{short}.{name}", label, n, max(s1, s2), e1 or e2)
            for fname, fn in funcs:
                print(f"START {short}.{fname}() {label} {n}", flush=True)
                secs, err = timed(lambda: fn(s))
                count, worst = count + 1, max(worst, secs)
                report("function", f"{short}.{fname}()", label, n, secs, "" if err in ("TypeError", "KeyError", "ValueError", "AttributeError") else err)
    print(f"DONE {short} patterns={len(pats)} functions={len(funcs)} runs={count} worst_ms={worst*1000:.1f}", flush=True)


def guard_paths():
    """Multi-argument paths that matter most: the guard and the merge on long messages and many updates."""
    from app.agents import intake, parser
    from app.agents import intake_support as sup
    from app.agents import turn_guard as tg
    from app.agents.turn_read import Update
    from app.schemas import Profile
    p = Profile()
    worst = 0.0
    for n in (2000, 4000):
        for label, msg in strings(n).items():
            ups = [Update(field_path="savings.total", value=1.0, unit="dollars", evidence_quote=msg[:200]) for _ in range(12)]
            ups += [Update(field_path="pay_per_year", value=100000.0, unit="per_year", evidence_quote=msg[-200:], is_correction=True) for _ in range(12)]
            print(f"START paths {label} {n}", flush=True)
            for name, fn in (("turn_guard.check_updates(24 updates)", lambda: tg.check_updates(ups, msg, p, "savings")),
                             ("parser.parse + guard.merge", lambda: tg.merge(parser.parse(tg.statements(msg), asking=None), tg.GuardResult(), msg)),
                             ("turn_guard.money_supported", lambda: tg.money_supported(1234.0, msg)),
                             ("intake._history_text", lambda: intake._history_text(msg)),
                             ("intake._mortgage_answer", lambda: intake._mortgage_answer(msg)),
                             ("intake._plain_answer_facts", lambda: intake._plain_answer_facts(msg, "age")),
                             ("sup.detect_edit", lambda: sup.detect_edit(msg)),
                             ("sup.edit_value_facts", lambda: sup.edit_value_facts(msg, "pay_per_year"))):
                secs, err = timed(fn)
                worst = max(worst, secs)
                report("path", name, label, n, secs, "" if err in ("KeyError", "TypeError", "ValueError") else err)
    q = " ".join(f"${1000 + 7 * i}" for i in range(10))
    secs, err = timed(lambda: tg.money_supported(999999.0, q))
    report("path", "money_supported with 10 figures", "ten_figures", len(q), secs, err)
    print(f"DONE guard_paths worst_ms={max(worst, secs)*1000:.1f}", flush=True)


def parent():
    bad = 0
    for m in MODULES + ["guard_paths"]:
        t = time.time()
        try:
            r = subprocess.run([sys.executable, __file__, "--worker", m], capture_output=True, text=True, timeout=CAP, cwd=str(LITE))
            out = r.stdout
            if r.returncode:
                print(f"[{m}] child exited {r.returncode}: {r.stderr.strip().splitlines()[-1:]}")
        except subprocess.TimeoutExpired as e:
            out = e.stdout or ""
            out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
            starts = [x for x in out.splitlines() if x.startswith("START")]
            print(f"[{m}] HANG over {CAP}s; last item: {starts[-1] if starts else '?'}")
            bad += 1
        print(f"== {m}  ({time.time()-t:.1f}s)")
        for line in out.splitlines():
            if line.startswith(("SLOW", "DONE")):
                print("  " + line)
                bad += line.startswith("SLOW")
    print(f"\nover 100 ms or hung: {bad}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        guard_paths() if sys.argv[2] == "guard_paths" else worker(sys.argv[2])
    else:
        parent()
