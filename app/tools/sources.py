"""Sources tool: TF-IDF keyword retrieval over short official passages (app/data/passages.json). Pure Python."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache

from ..config import DATA_DIR

STOP = set("""a an and are as at be by can do does for from has have how i if in is it its my of on or our the their
this to was what when which who will with you your me we they them should would could much many any about after before
than then there these those also may more most not no yes so up out""".split())
MIN_SCORE = 0.12
SYNONYMS = {"rmds": "rmd", "401k": "401", "401(k)": "401", "medicare": "medicare", "ss": "social", "claim": "claiming",
            "claims": "claiming", "required": "required", "minimum": "minimum", "distributions": "distribution",
            "contributions": "contribution", "contribute": "contribution", "limits": "limit", "ages": "age",
            "benefits": "benefit", "credits": "credit", "penalties": "penalty", "retire": "retirement"}


def _tokens(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+(?:\(k\))?", text.lower().replace("401(k)", "401k"))
    out = []
    for t in raw:
        t = SYNONYMS.get(t, t)
        if t in STOP or len(t) < 2:
            continue
        if t.endswith("s") and len(t) > 4 and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


@lru_cache(maxsize=1)
def _index():
    data = json.load(open(DATA_DIR / "passages.json", encoding="utf-8"))
    docs = data["passages"]
    toks = [_tokens(d["title"] + " " + d["text"] + " " + d.get("topic", "").replace("_", " ")) for d in docs]
    df = Counter(t for ts in toks for t in set(ts))
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}
    vecs = []
    for ts in toks:
        tf = Counter(ts)
        v = {t: (1 + math.log(c)) * idf[t] for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({t: x / norm for t, x in v.items()})
    return docs, vecs, idf


def search(query: str, k: int = 3, min_score: float = MIN_SCORE) -> list[dict]:
    docs, vecs, idf = _index()
    q = Counter(_tokens(query))
    qv = {t: (1 + math.log(c)) * idf[t] for t, c in q.items() if t in idf}
    norm = math.sqrt(sum(x * x for x in qv.values())) or 1.0
    scored = []
    for d, v in zip(docs, vecs):
        s = sum(x / norm * v.get(t, 0.0) for t, x in qv.items())
        if s >= min_score:
            scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    return [{"id": d["id"], "title": d["title"], "url": d["url"], "topic": d.get("topic"), "text": d["text"], "score": round(s, 3)}
            for s, d in scored[:k]]


def get(passage_id: str) -> dict | None:
    docs, _, _ = _index()
    return next((d for d in docs if d["id"] == passage_id), None)


def count() -> int:
    return len(_index()[0])
