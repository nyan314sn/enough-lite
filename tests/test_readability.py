"""R26: a high-school graduate can use it. Reading grade 8 or lower, short sentences, short lines.

The score is eval/readability/measure.py (Flesch-Kincaid grade, words per sentence, the longest sentence). It runs on
(a) the string templates in app/, and (b) tools-only plans for sample households (no model call): the headline, the
needs/wants/wishes lines, the actions, the analysis, the assumptions, the What If replies and the intake replies for the
example chat. The AI-written text is held to the same limits by the agents' instructions (app/agents/base.py STYLE) and
measured live in eval/readability/REPORT.md; here only the code-built text is tested.
"""
import asyncio
import importlib.util
import re
import statistics
from pathlib import Path

import pytest

from app import pipeline
from app.agents import intake

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("readability_measure", ROOT / "eval" / "readability" / "measure.py")
measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measure)

GRADE_MAX = 8.0
SENTENCE_MAX = 20           # words: the hard cap for any one sentence of the plan
SAMPLES = ("doctor", "s071", "e24")        # a comfortable couple, a struggling household, an average one


# ------------------------------------------------------------------ the score itself
def test_score_is_sane():
    easy = measure.stats("You can count on $40,000 a year. That is about your needs. Little is left for wants.")
    hard = measure.stats("Notwithstanding considerable uncertainty regarding macroeconomic conditions, prospective "
                         "retirement expenditures necessitate comprehensive actuarial reconsideration of contribution trajectories.")
    assert easy["grade"] < 6 and easy["longest"] <= 9
    assert hard["grade"] > 16 and hard["sentences"] == 1
    assert measure.syllables("retirement") in (3, 4) and measure.syllables("make") == 1 and measure.syllables("$53,400") == 2


# ------------------------------------------------------------------ (a) the templates in app/
def test_templates_read_at_grade_8_or_lower():
    items = [{"type": "template", "text": t["text"]} for t in measure.template_strings() if measure.keep_template(t["text"])]
    rows = measure.summarize(items)["template"]
    assert rows["mean_grade"] <= GRADE_MAX, rows
    assert rows["share_over_grade8"] <= 0.12, rows
    assert rows["share_sentence_over_20"] <= 0.06, rows


def test_one_vocabulary_in_the_templates():
    """The owner's wording: needs, wants, wishes (never 'basics' to the person) and 'market tests' for the made-up runs."""
    bad = [t["text"] for t in measure.template_strings()
           if measure.keep_template(t["text"]) and re.search(r"baseline plan:|market paths?\b", t["text"])]
    assert bad == [], bad


# ------------------------------------------------------------------ (b) tools-only plans for sample households
def _sample(sid: str) -> dict:
    from app import samples
    return next(h for h in samples.load() if h["id"] == sid)


_CACHE: dict = {}


def _plan(sid: str) -> dict:
    if sid not in _CACHE:
        base = pipeline._clean_profile_text(pipeline.prepare(_sample(sid)["profile"]))
        plan, _ = asyncio.run(pipeline.tools_only_plan(base))
        _CACHE[sid] = plan
    return _CACHE[sid]


def _plan_texts(plan: dict) -> list[tuple[str, str]]:
    out: list = []
    measure.walk(plan, "", out)
    return [(measure.kind_of(label), t) for label, t in out]


def _check_sentences(texts: list[str], what: str, cap: int = SENTENCE_MAX) -> None:
    for t in texts:
        longest = measure.stats(t)["longest"]
        assert longest <= cap, f"{what}: a {longest}-word sentence: {t}"


@pytest.mark.parametrize("sid", SAMPLES)
def test_plan_text_uses_needs_wants_wishes_and_market_tests(sid):
    for kind, t in _plan_texts(_plan(sid)):
        assert not re.search(r"\bbasics\b|\bscenarios?\b|market paths?\b|baseline plan", t, re.I), (kind, t)
    plan = _plan(sid)
    assert "needs" in plan["needs"]["line"].lower() and "market tests" in plan["wishes"]["line"]


@pytest.mark.parametrize("sid", SAMPLES)
def test_headline_is_short(sid):
    h = _plan(sid)["headline"]
    first = measure.sentences(h)[0]
    assert len(measure.words(first)) <= 15, h
    assert len(measure.words(h)) <= 36, h
    _check_sentences([h], "headline")
    assert measure.stats(h)["grade"] <= GRADE_MAX, h


@pytest.mark.parametrize("sid", SAMPLES)
def test_actions_are_a_short_title_and_one_line(sid):
    acts = _plan(sid)["actions"]
    assert len(acts) == 3
    for a in acts:
        assert len(measure.words(a["title"])) <= 8, a["title"]
        assert len(measure.words(a["why"])) <= 24, a["why"]
        assert len(measure.sentences(a["why"])) <= 2, a["why"]
        _check_sentences([a["why"]], "action")


@pytest.mark.parametrize("sid", SAMPLES)
def test_plan_lines_and_analysis_read_at_grade_8(sid):
    plan = _plan(sid)
    texts = _plan_texts(plan)
    lines = [plan["needs"]["line"], plan["wants"]["line"], plan["wishes"]["line"]]
    _check_sentences(lines, "needs/wants/wishes")
    by_kind: dict[str, list[str]] = {}
    for kind, t in texts:
        by_kind.setdefault(kind, []).append(t)
    for kind in ("analysis", "assumptions", "needs/wants/wishes", "action line", "notes"):
        xs = by_kind.get(kind) or []
        if not xs:
            continue
        grade = measure.stats("\n".join(xs))["grade"]
        assert grade <= GRADE_MAX, (kind, grade)
        _check_sentences(xs, kind)


# ------------------------------------------------------------------ What If replies and the intake chat
@pytest.mark.parametrize("sid", SAMPLES)
def test_what_if_replies_are_short(sid):
    h = _sample(sid)
    for q in measure.whatif_questions(h["profile"]):
        r = asyncio.run(pipeline.ask(q, h["profile"], "t", use_ai=False))
        text = r["text"]
        assert "baseline plan" not in text and "(" not in text, text
        _check_sentences([text], "what if", 24)       # the head names the change in full, so a sentence may run a little longer
        assert len(measure.sentences(text)) <= 5, text
        assert measure.stats(text)["grade"] <= GRADE_MAX + 1, text


def test_intake_replies_for_the_example_chat_are_short():
    replies = []
    for conv in measure.EXAMPLE_TURNS[:4]:
        prof: dict = {}
        for turn in conv:
            r = asyncio.run(intake.run(turn, prof, use_ai=False))
            prof = r.profile
            replies.append(r.reply or "")
            if r.question:
                assert len(measure.words(r.question.text)) <= 32, r.question.text
    replies = [x for x in replies if x]
    assert statistics.mean(len(measure.words(x)) for x in replies) <= 32
    for x in replies:
        _check_sentences([x], "intake reply", 24)
        assert len(measure.words(x)) <= 90, x
    assert measure.stats("\n".join(replies))["grade"] <= GRADE_MAX
