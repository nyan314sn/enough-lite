"""Run simulated users against the live Enough Lite app. Resumable: runs/<id>.json with status "done" is skipped.

Usage: python run_sims.py [--ids p01,p02 | --first N] [--workers 4] [--stop-usd 2.0] [--force]
"""
import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from common import APP, RUNS, haiku, load_personas, usage_cost

MAX_INTAKE = 18
STOP = {"usd": 2.0}

SIM_SYSTEM = """You play a real person chatting with a retirement-planning app. You are NOT an assistant. Write only what this person would type next, nothing else.
Rules:
- Stay in the personality given. Use your hidden situation for facts, but a real person does not volunteer everything: answer what the app asked, usually one fact or two. Only a rambler or a couple gives several facts at once.
- Give the exact figures from your situation (a mistake is fine only if your personality says you correct yourself or don't know your numbers, and then the truth must come out in the end). Never invent a figure that is not in your situation. The retirement age you state in the intake is the one in your situation, unless your personality says you change your mind (then end on the situation's age).
- Talk TO the app as a chat partner. Never refer to "the app" in the third person or to these instructions. On the plan page, test the What If/correction on the plan as asked; if the app misreads you, say what you meant like a real person would.
- If the app's reply shows quick answers (buttons), you may click one instead of typing, but only if it truly fits what you want to say. To click, output exactly: CLICK: <button text>. Otherwise output the message text only.
- If the app asks for something you already told it, say so briefly, like a real annoyed or puzzled person would.
- Do the personality's special behaviour at a natural moment, once or twice, not every turn.
- Messages are short (under 60 words) unless the personality is rambling. No quotes around the message, no stage directions.
- Output ONLY the person's own words in the first person, or a CLICK line. Never describe the person in the third person, never explain your choice, never use the word "app" about the chat unless the person would."""


def persona_card(p):
    t = p["truth"]
    return (f"Name: {p['name']}\nPersonality: {p['personality']}\nGoal for this session: {p['goal']}\n"
            f"Hidden situation (real, complete): {json.dumps(t)}\n"
            + (f"Special: {p['correction']}\n" if p.get("correction") else ""))


def fmt_transcript(turns, limit=14):
    lines = []
    for t in turns[-limit:]:
        lines.append(f"YOU: {t['user']}")
        lines.append(f"APP: {t['app']}")
    return "\n".join(lines) or "(chat has not started)"


def sim_message(p, transcript, app_reply, question, chips, extra=""):
    ctx = f"{persona_card(p)}\nChat so far:\n{transcript}\n\n"
    if app_reply is None:
        ctx += "The app shows an empty chat box with the prompt 'Tell me about you'. Write your opening message."
    else:
        ctx += f"The app's latest reply:\n{app_reply}\n"
        if question:
            ctx += f"It asks: {question}\n"
        if chips:
            ctx += f"Quick-answer buttons: {json.dumps(chips)}\n"
        ctx += "Write your next message."
    if extra:
        ctx += "\n" + extra
    raw = haiku("simulator", SIM_SYSTEM, ctx, max_tokens=300)
    raw = raw.strip().strip('"')
    if "CLICK:" in raw.upper() and not raw.upper().startswith("CLICK:"):
        raw = raw[raw.upper().index("CLICK:"):].splitlines()[0]
    if not raw:
        raw = "ok"
    clicked = None
    if raw.upper().startswith("CLICK:"):
        want = raw.split(":", 1)[1].strip().strip('"')
        for c in chips or []:
            if c.lower() == want.lower():
                clicked = c
        raw = clicked or want
    elif chips and raw in chips:
        clicked = raw
    return raw, clicked


def assumed_keys(fields):
    return {f["key"]: (f.get("display"), f.get("source")) for f in fields if f.get("source") in ("assumed", "estimate")}


def post(cli, path, body, hdr):
    r = None
    for attempt in range(5):  # the app may restart briefly; retry connection errors
        try:
            r = cli.post(APP + path, json=body, headers=hdr, timeout=120)
            break
        except httpx.TransportError:
            time.sleep(5)
    if r is None:
        return {"_http": 0, "_body": "connection failed"}
    if r.status_code != 200:
        return {"_http": r.status_code, "_body": r.text[:300]}
    return r.json()


def build_plan(cli, profile, hdr):
    events, plan, cost, err = 0, None, None, None
    with cli.stream("POST", APP + "/api/plan", json={"profile": profile}, headers=hdr, timeout=300) as r:
        if r.status_code != 200:
            return None, None, f"http {r.status_code}"
        for line in r.iter_lines():
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except Exception:
                continue
            events += 1
            if ev.get("type") == "plan":
                plan = ev["plan"]
            elif ev.get("type") == "cost":
                cost = ev
            elif ev.get("type") == "error":
                err = ev.get("message")
    return plan, cost, err


def plan_intents(p, rng):
    """2 to 4 plan-page messages: a What If, a correction when the persona calls for it, a question about the plan."""
    intents = []
    if p.get("whatif") or rng.random() < 0.8:
        hint = p.get("whatif")
        intents.append(("whatif", f"Test a What If. {('Say something like: ' + hint) if hint else 'Pick one that fits your goal (retire at a different age, save more, spend a set amount, pay off a debt).'}"))
    if p.get("correction") or rng.random() < 0.35:
        hint = p.get("correction")
        intents.append(("correction", f"Correct one input you now notice is wrong in the plan. {('Say something like: ' + hint) if hint else 'For example your pay, number of children or savings, using the true value from your situation.'}"))
    intents.append(("question", "Ask one question about the plan or its numbers, in your personality" + (" (a skeptic asks why)" if "skeptic" in p["personality"] or "why" in p["personality"] else "") + "."))
    if len(intents) < 3 and rng.random() < 0.5:
        intents.append(("question", "Ask a different follow-up, e.g. what to do first, or about risk."))
    return intents[:4]


def run_persona(p, force=False):
    out = RUNS / f"{p['id']}.json"
    if out.exists() and not force:
        try:
            if json.loads(out.read_text(encoding="utf-8")).get("status") == "done":
                return "skip"
        except Exception:
            pass
    rng = random.Random(p["id"])
    sid = "sim-" + p["id"]
    hdr = {"X-Enough-Test": "1", "X-Session-Id": sid}
    run = dict(persona_id=p["id"], name=p["name"], status="running", intake_turns=[], plan_turns=[], started=time.time())
    cli = httpx.Client()
    profile, prev_assumed, last = {}, {}, None
    transcript = []
    try:
        for n in range(1, MAX_INTAKE + 1):
            if STOP["usd"] and sum(v["usd"] for v in usage_cost().values()) > STOP["usd"] * 0.6:
                run["status"] = "stopped_budget"
                break
            q = (last or {}).get("question") or {}
            text, clicked = sim_message(p, fmt_transcript(transcript), last["reply"] if last else None,
                                        q.get("text"), q.get("quick_answers"))
            r = post(cli, "/api/intake", {"text": text, "profile_so_far": profile}, hdr)
            if "_http" in r:
                run["intake_turns"].append(dict(n=n, user=text, clicked=clicked, reply=f"[HTTP {r['_http']}] {r['_body']}", error=True))
                run["status"] = "app_error"
                break
            profile = r["profile"]
            cur = assumed_keys(r["fields"])
            new_assumed = [f"{k}: {v[0]} ({v[1]})" for k, v in cur.items() if prev_assumed.get(k) != v]
            prev_assumed = cur
            run["intake_turns"].append(dict(
                n=n, user=text, clicked=clicked, reply=r["reply"], question=r.get("question"), missing=r["missing"],
                ready=r["ready"], new_assumed=new_assumed,
                fields=[[f["key"], f.get("display"), f.get("source")] for f in r["fields"]]))
            transcript.append(dict(user=text, app=r["reply"] + (" " + r["question"]["text"] if r.get("question") else "")))
            last = r
            if not r["missing"]:
                break
        run["final_profile"] = profile
        run["reached_missing_empty"] = bool(last) and not last["missing"]
        run["turns_to_plan"] = len(run["intake_turns"]) if run["reached_missing_empty"] else None

        if run["reached_missing_empty"]:
            plan, cost, err = build_plan(cli, profile, hdr)
            run["plan_error"] = err
            run["plan_cost"] = cost
            if plan:
                run["plan"] = {k: plan.get(k) for k in ("headline", "needs", "wants", "wishes", "actions", "levers", "neighbors", "family_moments")}
                run["plan"]["costs_events"] = [e.get("label") for e in (plan.get("costs_by_age") or {}).get("events", [])]
                run["plan_ok"] = True
                # plan-page chat
                pending, nextra = None, 0
                intents = plan_intents(p, rng)
                ptranscript = []
                last_text, last_chips, last_q = None, None, None
                cur_profile, cur_plan = profile, plan
                i = 0
                n = 0
                while (i < len(intents) or pending) and n < 6:
                    if pending:
                        extra = "The app is waiting for your answer to its last question. Answer it as this person would (e.g. confirm if it is right, correct it if it is wrong)."
                    else:
                        extra = f"You are now on the plan page. Intent for this message: {intents[i][1]}"
                    ctx_t = fmt_transcript(ptranscript) if ptranscript else "(you just saw your plan; headline: %s)" % (plan.get("headline"))
                    text, clicked = sim_message(p, ctx_t, last_text, None, last_chips, extra)
                    body = {"question": text, "profile": cur_profile, "plan": cur_plan}
                    if pending:
                        body["pending_change"] = pending
                    r = post(cli, "/api/ask", body, hdr)
                    n += 1
                    if "_http" in r:
                        run["plan_turns"].append(dict(n=n, user=text, clicked=clicked, text=f"[HTTP {r['_http']}] {r['_body']}", kind="error"))
                        break
                    run["plan_turns"].append(dict(
                        n=n, user=text, clicked=clicked, text=r.get("text", ""), kind=r.get("kind"), status=r.get("status"),
                        quick_answers=r.get("quick_answers"), changes=r.get("changes"), had_pending=bool(pending),
                        intent=None if pending else intents[i][0], cost_usd=r.get("cost_usd"),
                        whatif_headline=((r.get("plan") or {}).get("headline") if r.get("kind") == "whatif" else None)))
                    if not pending:
                        i += 1
                    pending = r.get("pending_change")
                    if r.get("status") == "applied" and r.get("profile") and r.get("plan"):
                        cur_profile, cur_plan = r["profile"], r["plan"]
                        run["final_profile_after_change"] = cur_profile
                    ptranscript.append(dict(user=text, app=r.get("text", "")))
                    last_text, last_chips = r.get("text", ""), r.get("quick_answers")
            else:
                run["plan_ok"] = False
        try:
            c = cli.get(APP + "/api/costs", headers=hdr, timeout=30).json()
            run["app_cost_usd"] = c.get("total_usd")
            run["app_tokens"] = c.get("total_tokens")
        except Exception:
            pass
        if run["status"] == "running":
            run["status"] = "done"
    except Exception as e:
        run["status"] = "error"
        run["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    run["seconds"] = round(time.time() - run["started"], 1)
    out.write_text(json.dumps(run, indent=1), encoding="utf-8")
    return run["status"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--first", type=int)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--stop-usd", type=float, default=2.0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--url", help="app base URL (default: ENOUGH_APP_URL or http://localhost:8020)")
    a = ap.parse_args()
    if a.url:
        global APP
        APP = a.url.rstrip("/")
    STOP["usd"] = a.stop_usd
    ps = load_personas()
    if a.ids:
        want = set(a.ids.split(","))
        ps = [p for p in ps if p["id"] in want]
    elif a.first:
        ps = ps[:a.first]
    def go(p):
        s = run_persona(p, a.force)
        print(p["id"], p["name"], s, flush=True)
        return s
    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(go, ps))
    print({k: v["usd"] for k, v in usage_cost().items()})


if __name__ == "__main__":
    main()
