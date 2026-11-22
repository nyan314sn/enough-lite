"""What the intake does with an edit of 'Yearly saving' typed in the chat. Usage: diag_edit.py"""
import asyncio
import os
import sys
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ENOUGH_RUN_LOG"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import diag  # noqa: E402
from app.agents import intake  # noqa: E402


async def main():
    r = await diag.household("teacher")
    f = {x.key: x for x in r.fields}
    print("before:", f["save_rate"].display, f["save_rate"].editable, r.profile.get("save_rate"), r.profile.get("saving"))
    for t in ("Change Yearly saving to: $20,000 a year", "Change Yearly saving to: 15%"):
        r2 = await intake.run(t, r.profile, use_ai=False)
        f2 = {x.key: x for x in r2.fields}
        print(t, "->", f2["save_rate"].display, r2.profile.get("save_rate"), r2.profile.get("saving"), "|", r2.reply[:200])


asyncio.run(main())
