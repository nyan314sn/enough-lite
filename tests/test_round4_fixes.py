"""Round 4 simulated-user fixes (simusers/round4/REPORT.md). Rule path and tools-only plans: no model calls.

1. First moves are actions with their figure, each with the What If that runs it.
2. An early build asks the retirement age first; a stated age is never moved.
3. A What If asked during the intake is never a change to a stored figure.
4. A typical figure worked out again is said as old -> new.
5. "Why do you need my age?" gets a real reason, never "type skip".
6. "idk what to say" first gets an example sentence; an assumed state is said and shown.
"""
import asyncio
import importlib.util
import re
from pathlib import Path

import pytest

from app import pipeline, samples
from app.agents import adviser, intake

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("readability_measure", ROOT / "eval" / "readability" / "measure.py")
measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure)

SAMPLE_IDS = [h["id"] for h in samples.load()]
_PLANS: dict = {}


def _plan(sid: str) -> dict:
    if sid not in _PLANS:
        h = next(x for x in samples.load() if x["id"] == sid)
        base = pipeline._clean_profile_text(pipeline.prepare(h["profile"]))
        _PLANS[sid] = asyncio.run(pipeline.tools_only_plan(base))
    return _PLANS[sid]


def step(text, prof):
    r = asyncio.run(intake.run(text, prof, use_ai=False))
    assert r.reply.strip(), f"empty reply to {text!r}"
    return r


def play(turns, prof=None):
    prof, out = prof or {}, []
    for t in turns:
        r = step(t, prof)
        prof = r.profile
        out.append(r)
    return out


# ------------------------------------------------------------------ 1. first moves: actions with a number
GOALS = re.compile(r"^(?:make your needs safe|set your spending goal|save a little more|plan for long-term care|close the gap|"
                   r"build an emergency fund|save enough to get)", re.I)
VERBS = ("Spend", "Retire", "Save", "Pay", "Get", "Keep", "Add", "Claim", "Lower", "Plan", "Check", "Use", "Look")


def test_fifteen_admin_samples():
    assert len(SAMPLE_IDS) == 15


@pytest.mark.parametrize("sid", SAMPLE_IDS)
def test_actions_are_concrete_with_their_figure(sid):
    plan, ctx = _plan(sid)
    acts = plan["actions"]
    assert len(acts) == 3
    for a in acts:
        t = a["title"]
        assert set(a) >= {"title", "why", "whatif_text"}, a
        assert len(measure.words(t)) <= 8, t
        assert not GOALS.match(t), t
        assert t.split()[0] in VERBS, t
        assert a["why"].strip(), a
    # the levers the tools found are said with their figure
    ranked = {x["key"]: x for x in adviser.ranked_levers(ctx.profile, ctx.results["markets"])}
    for a in acts:
        lv = next((x for x in ranked.values() if x["title"] == a["title"]), None)
        if lv is None:
            continue
        if lv["key"] in ("debt", "match", "life") or (lv["key"] == "goal" and plan["verdict"] != "falls_short" and "goal_cut_per_year" in lv["numbers"]
                                                       and lv["numbers"]["goal_cut_per_year"] >= 1000):
            assert re.search(r"\$\d", a["title"]), a["title"]
        if lv["key"] == "goal" and plan["verdict"] == "falls_short" and plan["starting_points"]:
            assert re.search(r"\d", a["title"]), a["title"]


@pytest.mark.parametrize("sid", SAMPLE_IDS)
def test_action_whatif_runs_the_same_change(sid):
    plan, ctx = _plan(sid)
    p = ctx.profile
    for a in plan["actions"]:
        w = a["whatif_text"]
        if not w:
            continue
        assert adviser.lever_ok(p, w), w
        assert f"retire at {p.retire_age}" not in w.lower(), w
        ch = pipeline.parse_whatif(w, p)
        assert ch, (a["title"], w)
        m = re.match(r"Save \$([\d,]+) more a month", a["title"])
        if m:
            assert m.group(1) in w, (a["title"], w)
        m = re.match(r"Spend \$([\d,]+) less a year", a["title"])
        if m and "in retirement" in a["title"]:
            new_goal = plan["spending_goal"] - int(m.group(1).replace(",", ""))
            assert ch.get("spending_per_year") == new_goal, (a["title"], w, ch)


def test_falls_short_first_move_is_the_best_starting_point():
    found = 0
    for sid in SAMPLE_IDS:
        plan, _ = _plan(sid)
        if plan["verdict"] != "falls_short":
            continue
        first = plan["actions"][0]
        pts = plan["starting_points"]
        assert first["title"] != "Make your needs safe first"
        if pts:
            found += 1
            assert first["title"] == pts[0]["action_title"] and first["whatif_text"] == pts[0]["whatif_text"]
            assert re.search(r"\d", first["title"])
        else:
            assert first["title"] == "Lower your housing costs or add income"
    assert found >= 1


def test_action_title_shapes():
    one = adviser.action_title([{"key": "retire", "ch": {"retire_age": 64}}], 62)
    assert one == ("Retire at 64 instead of 62", "")
    two = adviser.action_title([{"key": "retire", "ch": {"retire_age": 66}}, {"key": "spend_now", "amt": 3000}], 62)
    assert two == ("Retire at 66 and spend $3,000 less now", "")
    three = adviser.action_title([{"key": "retire", "ch": {"retire_age": 66}}, {"key": "spend_now", "amt": 3000},
                                  {"key": "claim", "ch": {"claim_age": 70}}], 62)
    assert three[0] == "Retire at 66 and spend $3,000 less now" and three[1] == "claim Social Security at 70"
    assert len(three[0].split()) <= 8


def test_debt_and_match_titles_carry_the_figure():
    from app.tools import costs
    from app.schemas import Profile
    p = Profile.model_validate({"age": 40, "retire_age": 65, "pay_per_year": 60000})
    debts = {"high_rate_balance": 8000, "high_rate": 0.24, "high_rate_interest_per_year": 1920,
             "rows": [{"kind": "credit_card", "rate": 0.24, "balance": 8000}]}
    out = costs.levers(p, debts, {"rate": 0.5, "missed": 1740, "full_contribution": 3600}, 48000, 20000)
    titles = {x["key"]: x["title"] for x in out}
    assert titles["debt"] == "Pay off your $8,000 card debt first"
    assert titles["match"] == "Get the full employer match: $1,740 a year"


# ------------------------------------------------------------------ 2. an early build asks the retirement age
ESC = intake.ESCAPE


def test_early_build_asks_retirement_age_first():
    rs = play(["I'm 45, a teacher in Ohio", ESC])
    r = rs[-1]
    assert r.question is not None and r.question.text.startswith("When would you like to retire?")
    assert "I'll use 65" in r.question.text
    assert r.question.quick_answers == ["60", "62", "65", "67", "Use 65"]
    assert r.profile["asking"] == "retire_age" and r.profile["sources"].get("retire_age") != "you said"
    assert "typical figures for" not in r.reply           # nothing built yet
    r2 = step("62", r.profile)
    assert r2.profile["retire_age"] == 62 and r2.profile["sources"]["retire_age"] == "you said"
    assert "retire at 62" in r2.reply and "typical figures for" in r2.reply and r2.ready


def test_early_build_use_65_then_builds():
    rs = play(["I'm 45, a teacher in Ohio", ESC, "Use 65"])
    r = rs[-1]
    assert r.profile["retire_age"] == 65 and "retirement at 65" in r.reply and r.ready
    assert "When would you like to retire" not in (r.question.text if r.question else "")


def test_early_build_never_moves_a_stated_age():
    rs = play(["I'm 45, a teacher in Ohio, I want to retire at 60", ESC])
    r = rs[-1]
    assert r.profile["retire_age"] == 60 and r.profile["sources"]["retire_age"] == "you said"
    assert not (r.question and r.question.text.startswith("When would you like to retire"))
    assert "typical figures for" in r.reply


def test_early_build_with_partner_one_combined_question():
    rs = play(["I'm 45, a teacher in Ohio, married, my wife is 43", ESC])
    q = rs[-1].question
    assert q.text.startswith("When would you like to retire?") and "partner" in q.text
    r = step("62 and 64", rs[-1].profile)
    assert r.profile["retire_age"] == 62 and r.profile["partner_retire_age"] == 64
    assert r.profile["sources"]["partner_retire_age"] == "you said"


def test_early_build_asks_once_only():
    rs = play(["I'm 45, a teacher in Ohio", ESC, "what does Roth mean?", ESC])
    assert "typical figures for" in rs[-1].reply
    assert not (rs[-1].question and rs[-1].question.text.startswith("When would you like to retire"))


# ------------------------------------------------------------------ 3. a What If during the intake is never a change
P37 = ("Yes, that's about right. Spending now is around 72k a year. But before we go on, I want to try something: what if I save "
       "more each month? Say an extra 1,000 a month into my 401k. How does that change when I could retire?")
P37_SETUP = ["I'm Marta, 39, live in Illinois, and I work full time earning about 92k a year. I'd like to retire at 63. I have a house "
             "worth around 350k with about 250k left on the mortgage.",
             "Total is about 188k across the 401k, Roth, brokerage and cash.",
             "No, my payment is 1,850 a month. Please change that one.", "No other debts", "2 children", "7 and 4"]


@pytest.fixture(scope="module")
def p37_before():
    return play(P37_SETUP)[-1]


def test_intake_whatif_never_proposes_a_change(p37_before):
    before = p37_before.profile
    r = step(P37, before)
    assert intake.WHATIF_LATER in r.reply
    assert "without your yes" not in r.reply
    assert not (r.question and r.question.text.startswith("Change your"))
    assert "pending_change" not in r.profile["notes"]
    assert r.profile["savings"] == before["savings"]
    assert r.profile.get("saving") == before.get("saving")
    assert r.profile["retire_age"] == before["retire_age"]
    # the fact in the same message is recorded as usual
    assert r.profile["spending_now_per_year"] == 72000 and r.profile["sources"]["spending_now_per_year"] == "you said"


@pytest.mark.parametrize("msg", ["what if I retire at 60?", "What if we save $500 more a month? How would that change things?",
                                 "Suppose I sell the house. What happens then?"])
def test_pure_whatif_changes_nothing(p37_before, msg):
    before = p37_before.profile
    r = step(msg, before)
    assert r.reply.startswith(intake.WHATIF_LATER)
    for k in ("retire_age", "savings", "saving", "spending_now_per_year", "home", "pay_per_year"):
        assert r.profile.get(k) == before.get(k), k
    assert r.question is not None and not r.question.text.startswith("Change your")


@pytest.mark.parametrize("msg", ["what if I don't know my savings?", "I'd like to retire at 62", "Let's say 60k a year"])
def test_not_a_whatif(msg):
    assert intake.whatif_split(msg)[0] == ""


# ------------------------------------------------------------------ 4. a re-derived typical figure is announced
def test_rederived_figure_is_said_old_to_new(p37_before):
    before = p37_before.profile
    old = before["spending_per_year"]
    r = step(P37, before)
    new = r.profile["spending_per_year"]
    assert new != old
    assert f"Spending in retirement: ${old:,.0f} → ${new:,.0f}, since you spend $72,000 now." in r.reply


# ------------------------------------------------------------------ 5. why the age
@pytest.mark.parametrize("msg", ["Why do you need my age?", "Why does it matter how old I am for a plan?"])
def test_why_age_has_a_real_reason_and_no_skip(msg):
    r = step(msg, {})
    assert "how long your money must last" in r.reply and "Social Security" in r.reply
    assert "skip" not in r.reply.lower()
    assert r.question is not None and r.question.text == "How old are you?"


def test_why_age_asked_again_is_not_a_canned_repeat():
    rs = play(["Why do you need my age?", "Why does it matter how old I am for a plan?", "Why would you need it at all?"])
    replies = [r.reply for r in rs]
    assert all(a != b for a, b in zip(replies, replies[1:]))       # never the same reply twice in a row
    for t in replies:
        assert "skip" not in t.lower() and "I still need this one" not in t


# ------------------------------------------------------------------ 6. small ones
def test_idk_first_message_gets_an_example():
    r = step("idk what to say", {})
    assert "For example: I'm 45, a teacher in Ohio, I earn $60,000 and I've saved $80,000." in r.reply


def test_assumed_state_is_said_and_shown():
    rs = play(["I'm 45 and I earn $60,000", ESC, "62"])
    r = rs[-1]
    assert "With no state, I use typical US taxes and costs." in r.reply
    row = next(f for f in r.fields if f.key == "state")
    assert row.source == "assumed" and "typical US" in row.display
