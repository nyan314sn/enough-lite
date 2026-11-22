"""College, child by child: read "the oldest goes to a state school and the youngest private", and set each child's own
type and share. No model call: plain rules, so the same words always give the same answer.

A reading is a list of items: {"who": {...}, "type": "public"|"private"|"none"|None, "share": 0..1|None, "ambiguous": bool}.
`who` is {"all": True}, {"age": 14}, {"rank": "oldest"|"youngest"|"middle"}, {"nth": 1} (order given; -1 is the last) or {"unknown": "son"}.
"""
from __future__ import annotations

import re
from typing import Any

from ..schemas import Child, Profile

TYPE_WORD = {"public": "public in-state", "private": "private", "none": "no college"}
_COLLEGE = re.compile(r"\bcollege|\buniversit|\btuition\b|\bschool\b", re.I)
_PRIVATE = re.compile(r"\bprivate\b", re.I)
_PUBLIC = re.compile(r"\bpublic\b|\bstate (?:school|college|univ\w*|u)\b|\bin[- ]state\b|\bcommunity college\b|\bstate\b(?!\s+of)", re.I)
_NONE = re.compile(r"\bno college\b|\bnone\b|\bno school\b|\bnot (?:going|go|to go) to (?:college|school)\b|\bwon'?t go\b|\bwill not go\b|"
                   r"\bskip(?:s|ping)? college\b|\bdoesn'?t go\b|\bnot go\b|\bno university\b", re.I)
_OR_NONE = re.compile(r"\bor (?:none|no college|nothing|no school)\b|\b(?:none|no college) or\b", re.I)
_ALL = re.compile(r"\b(?:both|all|each|every|the kids|the children|them|all of them|the three|the two)\b", re.I)

_AGE = [re.compile(p, re.I) for p in (r"\((\d{1,2})\)", r"\b(\d{1,2})[- ]?(?:years?|yrs?)[- ]?old\b", r"\bage[sd]?\s*(\d{1,2})\b", r"\b(\d{1,2})[- ]year\b")]
_NTH = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4}


def _ref(seg: str, names: dict[str, int] | None = None) -> dict | None:
    """Which child a piece of a sentence names, or None."""
    low = seg.lower()
    for nm, age in (names or {}).items():          # "Ava will go private": the name was linked to an age earlier ("Ava is 9")
        if re.search(rf"\b{re.escape(nm)}\b", seg):
            return {"age": age}
    for rx in _AGE:
        m = rx.search(low)
        if m and 0 <= int(m.group(1)) <= 40:
            return {"age": int(m.group(1))}
    m = re.search(r"\b(?:child|kid)\s*#?(\d)\b", low)
    if m:
        return {"nth": int(m.group(1))}
    if re.search(r"\b(?:oldest|eldest|older|elder)\b", low):
        return {"rank": "oldest"}
    if re.search(r"\b(?:youngest|younger|baby)\b", low):
        return {"rank": "youngest"}
    if re.search(r"\bmiddle\b", low):
        return {"rank": "middle"}
    if re.search(r"\blast\b", low):
        return {"nth": -1}
    m = re.search(r"\b(first|1st|second|2nd|third|3rd|fourth|4th)\b", low)
    if m:
        return {"nth": _NTH[m.group(1)]}
    m = _SEXED.search(low)
    if m and 0 <= int(m.group(3)) <= 30 and not re.search(r"\b(?:daughter|son|girl|boy)s?\b", m.group(2), re.I):
        return {"age": int(m.group(3))}            # "the girl of 8": the sentence itself links the word to the age
    m = re.search(r"\b(daughter|son|girl|boy)\b", low)
    if m:
        return {"unknown": m.group(1)}
    return None


# "a girl of 8", "my son (9)", "daughter who is 12": the word, a few plain words or a bracket, then the age
_SEXED = re.compile(r"\b(daughter|son|girl|boy)s?\b([^.;\d()]{0,14}?)\(?\b(\d{1,2})\b(?!\s*(?:k\b|%|percent|,\d))", re.I)
_FEMALE = ("daughter", "girl")


def child_sexes(text: str) -> dict[int, str]:
    """{age: 'female'|'male'} for every child the words link to an age ("a girl of 8 and a boy of 5"). Nothing is guessed:
    a word with no age beside it gives nothing, and two children of one age with different words give nothing."""
    out: dict[int, str] = {}
    clash: set[int] = set()
    for m in _SEXED.finditer(text or ""):
        gap = m.group(2)
        age = int(m.group(3))
        if len(gap) > 14 or re.search(r"\b(?:daughter|son|girl|boy)s?\b", gap, re.I) or not 0 <= age <= 30:
            continue
        sex = "female" if m.group(1).lower() in _FEMALE else "male"
        if age in out and out[age] != sex:
            clash.add(age)
        out[age] = sex
    return {a: s for a, s in out.items() if a not in clash}


_NOT_NAMES = {"I", "My", "We", "The", "He", "She", "It", "They", "Our", "Mom", "Dad", "Mother", "Father", "Wife", "Husband", "And", "But", "So", "That", "This", "There", "Both", "Each", "Then"}
_NAME_AGE = re.compile(r"\b([A-Z][a-z]{1,14})\s+(?:\((\d{1,2})\)|(?:is|are|was|who is|turned|turns)\s+(\d{1,2})\b(?!\s*(?:k\b|%|percent|,\d|\d))|,\s*(\d{1,2})\s*(?:years?|yrs?)[- ]old)")


def child_names(text: str) -> dict[str, int]:
    """'Ava is 9 and Ben is 4', 'Ava (9)': a capitalised name tied to an age. A name given two ages is dropped."""
    out: dict[str, int] = {}
    clash: set[str] = set()
    for m in _NAME_AGE.finditer(text or ""):
        nm, age = m.group(1), int(next(g for g in m.groups()[1:] if g))
        if nm in _NOT_NAMES or not 0 <= age <= 30:
            continue
        if nm in out and out[nm] != age:
            clash.add(nm)
        out[nm] = age
    return {k: v for k, v in out.items() if k not in clash}


def _share(seg: str) -> float | None:
    low = seg.lower()
    m = re.search(r"(\d{1,3}(?:\.\d+)?)\s?(?:%|percent)", low)
    if m:
        return max(0.0, min(1.0, float(m.group(1)) / 100))
    if re.search(r"\bhalf\b", low):
        return 0.5
    if re.search(r"\b(?:a )?quarter\b", low):
        return 0.25
    if re.search(r"\b(?:a )?third\b", low) and not re.search(r"\bthird (?:child|kid|one)\b", low):
        return 1 / 3
    if re.search(r"\b(?:pay|cover|fund)\w*\s+(?:for\s+)?(?:all|everything|in full|it all)\b|\bin full\b|\bfull cost\b", low):
        return 1.0
    return None


def _type(seg: str) -> tuple[str | None, bool]:
    """(type, ambiguous). 'community college or none' is ambiguous: ask."""
    t = "private" if _PRIVATE.search(seg) else "public" if _PUBLIC.search(seg) else None
    if _NONE.search(seg):
        if t and _OR_NONE.search(seg):
            return t, True
        if not t:
            return "none", False
    if t and _OR_NONE.search(seg):
        return t, True
    return t, False


_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+(?:and|but|while|whereas)\s+|\s*;\s*")


def parse(text: str) -> list[dict[str, Any]]:
    """The per-child reading of a message, or [] when the message names no child or says nothing a flat reading would miss.
    A message with no child named ("private college for both, we pay half") is left to the flat reader unless it says 'each'."""
    items: list[dict[str, Any]] = []
    names = child_names(text)
    for sent in re.split(r"(?<!\d)\.(?!\d)|[!?\n]", text or ""):
        if not sent.strip():
            continue
        has_college = bool(_COLLEGE.search(sent))
        pieces = [s for s in _SPLIT.split(sent) if s and s.strip()]
        segs: list[str] = []
        for s in pieces:           # a piece with no child in it belongs to the piece before ("... private and we pay half")
            if segs and _ref(s, names) is None and _ALL.search(s) is None:
                segs[-1] += " " + s
            else:
                segs.append(s)
        pending: list[dict] = []
        for s in segs:
            ref = _ref(s, names)
            typ, amb = _type(s)
            share = _share(s)
            pays_all = share is not None and (bool(_ALL.search(s)) or ref is not None) and bool(re.search(r"\b(?:pay|cover|fund)", s, re.I))
            if not has_college and not (typ and ref) and not pays_all:
                continue
            if ref is None and typ is None and share is None:
                continue
            if ref is not None and typ is None and share is None:
                pending.append(ref)
                continue
            if ref is None and _ALL.search(s):
                who = [{"all": True}]       # "both go private": the earlier ages named only the children
            else:
                who = ([ref] if ref else []) + pending
            pending = []
            if not who:
                who = [{"all": True}]
            for w in who:
                items.append({"who": w, "type": typ, "share": share, "ambiguous": amb})
    return items


def has_named_child(items: list[dict]) -> bool:
    return any(not it["who"].get("all") for it in items)


# ------------------------------------------------------------------ resolving against the children on the profile

def _name(i: int, c: Child) -> str:
    return f"the {c.age}-year-old" if c.age is not None else f"child {i + 1}"


def resolve(children: list[Child], who: dict) -> list[int] | None:
    """Indexes of the children `who` names, or None if the words do not pick them out."""
    n = len(children)
    if n == 0:
        return None
    if who.get("all"):
        return list(range(n))
    if "age" in who:
        hit = [i for i, c in enumerate(children) if c.age == who["age"]]
        return hit or None
    if "nth" in who:
        k = who["nth"]
        i = n - 1 if k == -1 else k - 1
        return [i] if 0 <= i < n else None
    if "unknown" in who:
        if n == 1:
            return [0]
        want = "female" if who["unknown"] in _FEMALE else "male"
        hit = [i for i, c in enumerate(children) if c.sex == want]      # only when the person linked the word to an age
        return hit if len(hit) == 1 else None
    r = who.get("rank")
    if n == 1:
        return [0]
    ages = [c.age for c in children]
    if any(a is None for a in ages):
        return None
    if r == "oldest":
        top = max(ages)
        return [i for i, a in enumerate(ages) if a == top] if ages.count(top) == 1 else None
    if r == "youngest":
        low = min(ages)
        return [i for i, a in enumerate(ages) if a == low] if ages.count(low) == 1 else None
    if r == "middle" and n % 2 == 1:
        order = sorted(range(n), key=lambda i: ages[i])
        return [order[n // 2]]
    return None


def apply_each(p: Profile, items: list[dict]) -> dict | None:
    """Set each named child's college. Returns None when all was clear, else {"question", "quick"} for one short question."""
    kids = p.children
    if not kids or not items:
        return None
    unclear: dict | None = None

    def put(idx: list[int], it: dict) -> None:
        for i in idx:
            c = kids[i]
            if it["type"]:
                c.college_type = it["type"]
                c.college = it["type"] != "none"
            if it["share"] is not None and it["type"] != "none":
                c.college_share = it["share"]
            c.college_source = "you said"

    for it in sorted(items, key=lambda x: 0 if x["who"].get("all") else 1):     # "pay half for each" first; named children then override
        idx = resolve(kids, it["who"])
        if idx is None:
            if unclear is None:
                unclear = _who_question(kids, it)
            continue
        if it["ambiguous"]:
            if unclear is None:
                unclear = _type_question(kids, idx[0], it)
            if it["share"] is not None:
                put(idx, {"type": None, "share": it["share"]})
            continue
        put(idx, it)
    return unclear


def _who_question(kids: list[Child], it: dict) -> dict:
    names = [_name(i, c) for i, c in enumerate(kids)]
    listed = ", ".join(names[:-1]) + " or " + names[-1]
    word = TYPE_WORD.get(it["type"] or "", "")
    verb = {"public": "goes to a state school", "private": "goes private", "none": "goes to no college"}.get(it["type"] or "", "")
    quick = [f"{n[0].upper() + n[1:]} {verb}" for n in names][:5] if verb else []
    return {"question": f"Which child do you mean{' for ' + word if word else ''}: {listed}?", "quick": quick}


def _type_question(kids: list[Child], i: int, it: dict) -> dict:
    n = _name(i, kids[i])
    return {"question": f"For {n}: {'private college' if it['type'] == 'private' else 'community college'}, or no college?",
            "quick": [f"{n[0].upper() + n[1:]} goes to {'a private college' if it['type'] == 'private' else 'community college (public)'}",
                      f"{n[0].upper() + n[1:]} goes to no college"]}


# ------------------------------------------------------------------ the panel

def line(i: int, c: Child) -> tuple[str, str]:
    """(label, display) for one child's college row: 'College, child 1, age 11' and 'public in-state, you pay 100%'."""
    label = f"College: child {i + 1}" + (f", age {c.age}" if c.age is not None else "")
    kind = c.college_type or ("public" if c.college else "none")
    disp = TYPE_WORD[kind] + ("" if kind == "none" else f", you pay {c.college_share * 100:g}%")
    return label, disp


def whatif_change(p: Profile, text: str) -> dict | None:
    """A What If about college, child by child: {"children": [...], "_college_each": [phrases]}, {"_say": question, "_chips": [...]},
    or None when the text says nothing about college. The profile `p` is not changed."""
    items = parse(text)
    if not items or not p.children:
        return None
    tmp = p.model_copy(deep=True)
    ask = apply_each(tmp, items)
    if ask:
        return {"_say": ask["question"], "_chips": ["What if " + q[0].lower() + q[1:] for q in ask["quick"]] or None}
    said = []
    for a, b in zip(p.children, tmp.children):
        ka, kb = a.college_type or "public", b.college_type or "public"
        if (ka, a.college_share) == (kb, b.college_share):
            continue
        nm = f"the {b.age}-year-old" if b.age is not None else "your child"
        what = {"private": "a private college", "public": "a public in-state college", "none": "no college"}[kb]
        said.append(f"{nm} goes to {what}" + ("" if kb == "none" or b.college_share == 1 else f" and you pay {b.college_share * 100:g}%"))
    if not said:
        return {"_say": "Your plan already has that for college, so nothing would change.", "_chips": None}
    return {"children": [c.model_dump() for c in tmp.children], "_college_each": said}


def estimate_note(c: Child) -> str:
    return "Typical choice: public in-state, you pay 100%. Change it if that is not your plan."
