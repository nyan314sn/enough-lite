"""The partner's sex (life table only): read from what the person says, never assumed from a traditional relationship."""
from types import SimpleNamespace

import pytest

from app.agents import parser, turn_guard
from app.agents.intake import apply, question_for
from app.schemas import Profile


@pytest.mark.parametrize("text, want", [
    ("my partner is actually a man", "male"),
    ("My spouse is a woman", "female"),
    ("my partner's male", "male"),
    ("I'm married to a woman", "female"),
    ("my husband, not wife", "male"),
    ("my wife is 53", "female"),
    ("my girlfriend and I live in Ohio", "female"),
    ("my boyfriend is 50", "male"),
    ("my partner is nonbinary", "unstated"),
    ("my partner is 50", None),
])
def test_rule_reader(text, want):
    assert parser.partner_sex_said(text.lower()) == want


def test_same_sex_couple_kept():
    out = parser.parse("I'm a woman, 55, and my wife is 53")
    assert out.get("partner_sex") == "female"
    assert out.get("has_partner") is True


def test_boyfriend_counts_as_partner():
    assert parser.parse("my boyfriend is 50").get("has_partner") is True


def _upd(fp, v, quote):
    return SimpleNamespace(field_path=fp, value=v, unit="text", evidence_quote=quote, is_correction=True)


def test_guard_accepts_partner_sex():
    p = Profile(age=55, has_partner=True, partner_age=53, partner_sex="female")
    g = turn_guard.check_updates([_upd("partner_sex", "male", "my partner is actually a man")], "my partner is actually a man", p)
    assert g.facts.get("partner_sex") == "male"


def test_guard_moves_spouse_sex_off_the_person():
    p = Profile(age=55, has_partner=True, partner_age=53)
    msg = "Actually my spouse is male"
    g = turn_guard.check_updates([_upd("sex", "male", msg)], msg, p)
    assert "sex" not in g.facts and g.facts.get("partner_sex") == "male"


def test_unstated_uses_average_table():
    p = Profile(age=55, has_partner=True, partner_age=53, partner_sex="female")
    changed = apply(p, {"partner_sex": "unstated"})
    assert p.partner_sex is None and "partner_sex" in changed and p.sources.get("partner_sex") == "you said"


def test_questions_say_partner():
    p = Profile(has_partner=True, partner_sex="female")
    assert "your partner" in question_for("age", p).text


@pytest.mark.parametrize("text", ["My partner passed away last year", "We split up, so plan for me alone", "My ex and I separated",
                                  "I lost my husband in 2020", "We're divorced now, it's just me"])
def test_no_partner_now(text):
    assert parser.parse(text).get("has_partner") is False


def test_partner_parent_dying_is_not_the_partner():
    assert parser.parse("my partner is 53; my partner's mother passed away").get("has_partner") is True


def test_stated_words_beat_the_model():
    p = Profile(age=55, has_partner=True, partner_age=53)
    msg = "My spouse is a woman"
    g = turn_guard.check_updates([_upd("partner_sex", "male", msg)], msg, p)
    assert turn_guard.merge(parser.parse(msg, has_partner=True), g, msg)["partner_sex"] == "female"
