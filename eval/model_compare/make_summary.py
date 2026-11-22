"""Build summary.json (read by GET /api/admin/model-compare) from REPORT.md: the results table, the per-user cost table, caveats, recommendation.
Run: python eval/model_compare/make_summary.py   The figures are copied from the report's tables; nothing is recomputed or invented."""
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
text = (HERE / "REPORT.md").read_text(encoding="utf-8")


def section(name: str) -> str:
    m = re.search(rf"^## {re.escape(name)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1) if m else ""


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table(block: str) -> list[list[str]]:
    rows = [cells(l) for l in block.splitlines() if l.startswith("|")]
    return [r for r in rows if not set("".join(r)) <= set("-: ")][1:]


def plain(s: str) -> str:
    return re.sub(r"\*\*|`", "", s).strip()


def split_winner(w: str) -> tuple[str, str | None]:
    w = plain(w)
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", w)
    if not m:
        return w, None
    return m.group(1).strip() or w, m.group(2).strip()


rows = []
for metric, haiku, gpt, n, win in table(section("Results")):
    winner, note = split_winner(win)
    for name in ("Tie", "Haiku", "gpt-6-luna"):
        if winner.startswith(name) and winner != name:
            note = note or winner[len(name):].strip(" ,:;")
            winner = name
            break
    row = {"metric": plain(metric), "haiku": plain(haiku), "gpt": plain(gpt), "n": plain(n), "winner": winner}
    if note:
        row["note"] = note
    rows.append(row)

cost_rows = [{"model": plain(r[0]), "per_plan": r[1], "per_user_month": r[2], "users_100": r[3], "users_10000": r[4]} for r in table(section("Cost and speed per user"))]
res = section("Results")
dollar = re.search(r"\*\*Dollar note\.\*\*\s*(.+)", res)
rec = section("Recommendation")
rec_lines = [plain(l) for l in rec.splitlines() if l.strip() and not l.startswith("**Cost of")]
cost_total = re.search(r"about \$([\d.]+)", rec)
date = re.search(r"Run (\d{4}-\d{2}-\d{2})", text)

summary = {
    "date": date.group(1) if date else None,
    "models": ["Claude Haiku 5.5", "gpt-6-luna"],
    "rows": rows,
    "recommendation": " ".join(l.split(". ")[0].rstrip(".") + "." for l in rec_lines[:2]),
    "recommendation_detail": rec_lines,
    "cost_usd": float(cost_total.group(1)) if cost_total else None,
    "cost_per_user": cost_rows,
    "dollar_note": plain(dollar.group(1)) if dollar else None,
    "caveats": [plain(l[2:]) for l in section("Caveats").splitlines() if l.startswith("- ")],
}
(HERE / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(rows)} rows, {len(summary['caveats'])} caveats, cost {summary['cost_usd']}")
