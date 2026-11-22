from pathlib import Path
f = Path(__file__).resolve().parents[3] / "app/agents/adviser.py"
s = f.read_text(encoding="utf-8")
rep = [
# verdict
('''def verdict(m: dict) -> str:
    """works / close / falls_short. The spending goal is compared with safe spending, but a plan whose basics are paid
    in fewer than 90 of 100 scenarios always falls short, whatever the goal (so the verdict, needs and headline agree)."""
    goal, safe = m.get("spending_goal_per_year") or 0, m.get("safe_spending_per_year") or 0
    paid = m.get("basics_paid_of_100")
    if paid is not None and paid < BASICS_SAFE:
        return "falls_short"
    if safe >= goal:
        return "works"
    if safe >= 0.9 * goal:
        return "close"
    return "falls_short"''',
'''def verdict(m: dict) -> str:
    """works / close / below_goal / falls_short. "Falls short" has one meaning: the basics are paid in fewer than 90
    of 100 scenarios. With the basics safe, the spending goal is compared with what you can count on: works (at or
    above it), close (within 10%), below_goal (further below)."""
    goal, safe = m.get("spending_goal_per_year") or 0, m.get("safe_spending_per_year") or 0
    paid = m.get("basics_paid_of_100")
    if paid is not None and paid < BASICS_SAFE:
        return "falls_short"
    if safe >= goal:
        return "works"
    if safe >= 0.9 * goal:
        return "close"
    return "below_goal"


VERDICT_WORDS = {"works": "works", "close": "close to your goal", "below_goal": "below your goal",
                 "falls_short": "falls short: the basics are not safe"}


def needs_line(m: dict, basics: float) -> str:
    """The needs line, built in code from basics paid of 100 (never written by the model)."""
    paid = m.get("basics_paid_of_100")
    head = f"Your basics cost about {money(basics)} a year."
    if paid is None:
        return head
    if paid >= 100:
        return head + " They are paid in all 100 scenarios."
    if paid >= BASICS_SAFE:
        return head + f" They are paid in {paid} of 100 scenarios."
    if paid == 0:
        return head + " On these numbers they are not paid in any of 100 scenarios, so the plan starts there."
    return head + f" They are paid in only {paid} of 100 scenarios, so the plan starts there."'''),
# headline: explain count-on below Social Security
('''def headline(m: dict, basics: float) -> str:
    """One plain sentence on what the person can count on (plan.wants.per_year). Built in code from the simulation."""
    safe = m.get("safe_spending_per_year") or 0
    if safe < 0.95 * basics:''',
'''def below_ss_note(m: dict) -> str:
    """Why what you can count on is below your Social Security, when it is: built from the plan's own inputs."""
    safe, ss = m.get("safe_spending_per_year") or 0, m.get("social_security_per_year") or 0
    if not ss or safe >= ss:
        return ""
    why = []
    if (m.get("ss_tax_rate") or 0) > 0:
        why.append("income tax on it")
    if m.get("health_extra_in_retirement"):
        why.append("health costs on top of your spending")
    if m.get("social_security_survivor_per_year"):
        why.append("the drop to one benefit after the first death")
    if m.get("ss_starts_later"):
        why.append("the years before it starts")
    if not why:
        return ""
    lst = why[0] if len(why) == 1 else ", ".join(why[:-1]) + " and " + why[-1]
    return f" That is less than your Social Security of {money(ss)} a year because of {lst}."


def headline(m: dict, basics: float) -> str:
    """One plain sentence on what the person can count on (plan.wants.per_year). Built in code from the simulation."""
    return _headline(m, basics) + below_ss_note(m)


def _headline(m: dict, basics: float) -> str:
    safe = m.get("safe_spending_per_year") or 0
    if safe < 0.95 * basics:'''),
# claim ages from the simulation
('''def claim_ages(p, claim: int | None) -> tuple[int | None, int | None]:''',
'''def plan_claims(p, m: dict) -> tuple[int | None, int | None, bool]:
    """(your claiming age, your partner's, already claiming) as the kept strategy uses them: each person's own age;
    someone already claiming keeps the age they gave."""
    claim = m.get("claim_age")
    if claim is None:
        return None, None, False
    partner = m.get("partner_claim_age") if (p.has_partner and p.partner_age) else None
    already = bool(m.get("already_claiming")) if "already_claiming" in m else (p.age or 0) >= int(claim)
    return int(claim), (int(partner) if partner is not None else None), already


def claim_ages(p, claim: int | None) -> tuple[int | None, int | None]:'''),
# goal lever: not for a small gap
('''    if verdict(m) != "works" and gap > 0:''', '''    if verdict(m) != "works" and gap >= max(GOAL_GAP_MIN, GOAL_GAP_SHARE * (m.get("spending_goal_per_year") or 0)):'''),
('''GOAL_KEY = "goal"''', '''GOAL_KEY = "goal"
GOAL_GAP_MIN, GOAL_GAP_SHARE = 1000, 0.03     # a smaller gap to the goal is noise, not the first thing to act on'''),
# template
('''    needs = f"Your basics cost about {money(basics)} a year. They are paid in {paid} of 100 scenarios."''',
 '''    needs = needs_line(m, basics)'''),
('''    claim, _ = claim_ages(p, m.get("claim_age"))
    if claim is not None and (p.age or 0) < claim:''',
 '''    claim, _, already = plan_claims(p, m)
    if claim is not None and not already and (p.age or 0) < claim:'''),
# order_actions: next ranked levers before filler
('''    head = ranked[:2]
    head += [x for x in ranked[2:] if x["key"] in CONCRETE][:1]       # a third slot for a debt or match the top two skipped''',
 '''    head = ranked[:2]
    head += [x for x in ranked[2:] if x["key"] in CONCRETE][:1]       # a third slot for a debt or match the top two skipped
    if len(head) < 3:
        head += [x for x in ranked[2:] if x not in head][:3 - len(head)]   # then the next real lever, before any filler'''),
('''    # the adviser's own actions that say something new, then the standing ones, and only then one that echoes a lever
    add([a for a in cands if not repeats_lever(a)])
    add([dict(a) for a in SPARES])
    add(cands)''',
 '''    def status(a: dict) -> bool:
        # "Keep your spending goal at or below ...", "Keep saving toward 70": a state of affairs, not a thing to do
        return bool(STATUS_RE.match(a["title"] or ""))

    # the adviser's own actions that say something new, then the standing ones, and only then one that echoes a lever
    add([a for a in cands if not repeats_lever(a) and not status(a)])
    add([dict(a) for a in SPARES])
    add([a for a in cands if not status(a)])'''),
('''CONCRETE = ("debt", "match")''', '''CONCRETE = ("debt", "match")
STATUS_RE = re.compile(r"^\s*(?:keep (?:your spending|saving|spending|going|on)|continue|stay)\b", re.I)'''),
]
for a, b in rep:
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)
f.write_text(s, encoding="utf-8")
print("ok")
