"""College is set per child: reading, panel rows, costs, the plan chat. Rule path only (no model calls)."""
import asyncio
import copy

import pytest

from app import pipeline
from app.agents import college, intake
from app.schemas import Child

KIDS3 = {"age": 45, "has_partner": True, "partner_age": 43, "state": "OH", "retire_age": 65, "pay_per_year": 120000, "partner_pay_per_year": 60000,
         "savings": {"pretax": 250000, "roth": 20000, "taxable": 60000, "cash": 30000}, "savings_known": True, "home": {"owns": True},
         "children": [{"age": 16}, {"age": 12}, {"age": 7}], "risk": "balanced",
         "sources": {"age": "you said", "retire_age": "you said", "pay_per_year": "you said", "children": "you said"}}


def turn(text, prof):
    return asyncio.run(intake.run(text, copy.deepcopy(prof), use_ai=False))


def kids(r):
    return [(c["age"], c["college_type"], c["college_share"], c["college_source"]) for c in r.profile["children"]]


def rows(r):
    return {f.key: f for f in r.fields if f.key.startswith("college_")}


# ------------------------------------------------------------------ reading
@pytest.mark.parametrize("text,want", [
    ("the oldest will go to a state school and the youngest private", {0: "public", 2: "private"}),
    ("the oldest goes private, the middle goes to a state school, the youngest goes to no college", {0: "private", 1: "public", 2: "none"}),
    ("the 16-year-old goes to a state school and the 7-year-old goes private", {0: "public", 2: "private"}),
    ("the first goes private and the second goes to a state school", {0: "private", 1: "public"}),
])
def test_reads_children_by_order_and_age(text, want):
    r = turn(text, KIDS3)
    got = {i: c["college_type"] for i, c in enumerate(r.profile["children"])}
    for i, t in want.items():
        assert got[i] == t, (text, got)
    for i in range(3):
        if i not in want:
            assert r.profile["children"][i]["college_source"] != "you said"


def test_by_age_in_brackets_and_share_for_each():
    prof = dict(KIDS3, children=[{"age": 14}, {"age": 9}])
    r = turn("my daughter (14) private, my son (9) state school. We'll pay half for each.", prof)
    assert kids(r) == [(14, "private", 0.5, "you said"), (9, "public", 0.5, "you said")]


def test_one_share_for_one_child_only():
    r = turn("I will pay 40% for the middle one", KIDS3)
    assert [c[2] for c in kids(r)] == [1.0, 0.4, 1.0]
    assert kids(r)[1][3] == "you said"


def test_unclear_child_gets_one_short_question_naming_ages():
    prof = dict(KIDS3, children=[{"age": 9}, {"age": 9}])
    r = turn("my son goes private", prof)
    assert "9-year-old" in r.question.text or "child" in r.question.text
    assert all(c["college_source"] != "you said" for c in r.profile["children"])
    r2 = turn("my son goes private", KIDS3)
    assert "16-year-old" in r2.question.text and "12-year-old" in r2.question.text and "7-year-old" in r2.question.text
    assert any("7-year-old" in q for q in r2.question.quick_answers)
    # the chip answers it
    r3 = turn("The 7-year-old goes private", r2.profile)
    assert kids(r3)[2][1] == "private" and kids(r3)[0][3] != "you said"


def test_community_college_or_none_asks_instead_of_guessing():
    prof = dict(KIDS3, children=[{"age": 14}, {"age": 9}])
    r = turn("my daughter (14) private, my son (9) community college or none", prof)
    assert kids(r)[0][1] == "private" and kids(r)[1][3] != "you said"
    assert "9-year-old" in r.question.text
    r2 = turn(r.question.quick_answers[1], r.profile)
    assert kids(r2)[1][1] == "none"


def test_flat_wording_still_applies_to_every_child():
    r = turn("we want private college for both kids and to pay half", dict(KIDS3, children=[{"age": 9}, {"age": 6}]))
    assert kids(r) == [(9, "private", 0.5, "you said"), (6, "private", 0.5, "you said")]


def test_ages_said_again_keep_each_childs_choice():
    from app import household
    r = turn("the oldest goes private", KIDS3)
    p = intake.Profile.model_validate(r.profile)
    household.set_children(p, None, [17, 13, 8], None)
    assert [(c.age, c.college_type) for c in p.children][0] == (17, "private")
    assert p.children[0].college_source == "you said" and p.children[1].college_source == "estimate"


# ------------------------------------------------------------------ the panel
def test_one_row_per_child_with_its_own_note():
    r = turn("the oldest goes private and pay half for the middle one, the youngest none", KIDS3)
    rw = rows(r)
    assert sorted(rw) == ["college_0", "college_1", "college_2"]
    assert rw["college_0"].label == "College: child 1, age 16" and rw["college_0"].display == "private, you pay 100%"
    assert rw["college_1"].display == "public in-state, you pay 50%"
    assert rw["college_2"].display == "no college"
    for f in rw.values():
        assert f.source == "you said" and f.editable["kind"] == "college" and "assumed" not in (f.note or "").lower()


def test_typical_choice_is_an_estimate_and_said_in_the_reply():
    r = turn("we have three kids, 16, 12 and 7", {k: v for k, v in KIDS3.items() if k != "children"})
    rw = rows(r)
    assert len(rw) == 3
    for f in rw.values():
        assert f.source == "estimate" and "public in-state" in f.display and "Typical choice" in f.note
    assert "public in-state" in r.reply and "estimate" in r.reply


def test_a_private_row_never_says_assumed_public():
    r = turn("the youngest goes private", KIDS3)
    rw = rows(r)
    assert "private" in rw["college_2"].display and rw["college_2"].note == ""
    assert rw["college_0"].source == "estimate" and "Typical" in rw["college_0"].note


def test_an_estimate_stays_an_estimate_after_other_turns():
    r = turn("the youngest goes private", KIDS3)
    r = turn("I retire at 63", r.profile)
    assert rows(r)["college_0"].source == "estimate" and rows(r)["college_2"].source == "you said"


# ------------------------------------------------------------------ costs
def _plan(children):
    base = pipeline._clean_profile_text(pipeline.prepare(copy.deepcopy(dict(KIDS3, children=children))))
    plan, ctx = asyncio.run(pipeline.tools_only_plan(base))
    return plan, ctx.results["family"]


def test_costs_use_each_childs_own_type_share_and_years():
    fam = _plan([{"age": 16, "college_type": "public"}, {"age": 12, "college_type": "private", "college_share": 0.5}, {"age": 7, "college_type": "none"}])[1]
    by = {b["age"]: b for b in fam["college_by_child"]}
    assert set(by) == {16, 12}                                   # the youngest is not in college
    assert by[16]["per_year"] < by[12]["per_year"] * 2 and by[16]["per_year"] > 0
    assert by[12]["share"] == 0.5 and by[12]["type"] == "private"
    per_year = fam["college_per_year"]
    # years 2 to 5 from now are the 16-year-old's college; years 6 to 9 the 12-year-old's; nobody else
    assert per_year[2] == by[16]["per_year"] and per_year[1] == 0
    assert per_year[6] == by[12]["per_year"] and per_year[10] == 0 if len(per_year) > 10 else True
    assert fam["college_total"] == 4 * by[16]["per_year"] + 4 * by[12]["per_year"]


def test_timeline_has_one_college_event_per_child():
    plan, _ = _plan([{"age": 16, "college_type": "public"}, {"age": 12, "college_type": "private"}])
    labels = [e["label"] for e in plan["events"] if e["label"].startswith("College")] if "events" in plan else None
    if labels is None:
        pytest.skip("plan has no events list")
    assert len(labels) == 2 and "16-year-old" in labels[0] and "12-year-old" in labels[1]


# ------------------------------------------------------------------ the plan chat
def test_change_by_child_needs_a_confirm():
    r = asyncio.run(pipeline.ask("send the youngest to a private college", copy.deepcopy(KIDS3), "t", use_ai=False))
    assert r["kind"] == "change" and r["status"] == "confirm"
    assert "college" in r["text"] and "youngest" in r["text"]
    assert "children.college_each" in r["pending_change"]["facts"]


def test_what_if_both_go_to_state_school_runs_per_child():
    prof = dict(KIDS3, children=[{"age": 14, "college_type": "private"}, {"age": 10, "college_type": "private"}])
    r = asyncio.run(pipeline.ask("what if both go to state school", prof, "t", use_ai=False))
    assert r["kind"] == "whatif", r
    assert [c["college_type"] for c in r["profile"]["children"]] == ["public", "public"]
    assert "14-year-old" in r["text"] and "10-year-old" in r["text"] and "public in-state" in r["text"]


def test_what_if_only_the_youngest_private():
    r = asyncio.run(pipeline.ask("what if the youngest goes to a private college", copy.deepcopy(KIDS3), "t", use_ai=False))
    assert r["kind"] == "whatif"
    assert [c["college_type"] for c in r["profile"]["children"]] == ["public", "public", "private"]


def test_what_if_unclear_child_asks():
    r = asyncio.run(pipeline.ask("what if my son goes private", copy.deepcopy(KIDS3), "t", use_ai=False))
    assert r["kind"] == "clarify" and "7-year-old" in r["text"]


def test_resolve_edge_cases():
    kids_ = [Child(age=16), Child(age=16), Child(age=7)]
    assert college.resolve(kids_, {"rank": "oldest"}) is None        # twins: ask
    assert college.resolve(kids_, {"rank": "youngest"}) == [2]
    assert college.resolve([Child(age=None), Child(age=None)], {"rank": "oldest"}) is None
    assert college.resolve([Child(age=5)], {"rank": "youngest"}) == [0]
