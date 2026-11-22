"""Prints the before/after table for REPORT.md from the saved results files."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = [("Before (old rules)", "results_baseline.json"), ("Rules now", "results_rules.json"), ("Rules + AI, first live run", "results_ai_run1.json"),
        ("Rules + AI, final", "results_ai.json")]


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))["rows"]


def main():
    data = {label: load(f) for label, f in RUNS if (HERE / f).exists()}
    labels = list(data)
    for split in ("tune", "holdout"):
        rows = {label: [r for r in data[label] if r["split"] == split] for label in labels}
        types = sorted({r["type"] for r in rows[labels[0]]})
        print(f"\n### {split} set ({len(rows[labels[0]])} cases)\n")
        print("| Change type | Cases | " + " | ".join(labels) + " |")
        print("|---|---:|" + "---:|" * len(labels))
        for t in types + ["ALL"]:
            n = sum(1 for r in rows[labels[0]] if t == "ALL" or r["type"] == t)
            cells = []
            for label in labels:
                ok = sum(r["ok"] for r in rows[label] if t == "ALL" or r["type"] == t)
                cells.append(f"{ok} ({100 * ok / n:.0f}%)")
            name = f"**{t}**" if t == "ALL" else t
            print(f"| {name} | {n} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
