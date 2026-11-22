from pathlib import Path
H = Path(__file__).resolve().parent
F = H.parents[2] / "app/agents/adviser.py"
s = F.read_text(encoding="utf-8")
a = s.index("def assumptions(ctx: RunCtx) -> list[str]:")
b = s.index("def assemble(ctx: RunCtx, out: AdviserOut, source: str) -> dict:")
s = s[:a] + (H / "as_new.txt").read_text(encoding="utf-8") + s[b:]
F.write_text(s, encoding="utf-8")
print("ok")
