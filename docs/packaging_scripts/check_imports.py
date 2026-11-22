"""Compile the edited scripts and import eval/common (no network, no server)."""
import py_compile, sys
from pathlib import Path
L = Path(__file__).resolve().parents[2]
for rel in ["eval/common.py", "eval/judge.py", "eval/report.py", "eval/make_cases.py", "simusers/common.py", "report/build_report.py", "report/build_slides.py"]:
    py_compile.compile(str(L / rel), doraise=True, cfile=str(Path(__file__).resolve().parent / "_tmp.pyc"))
    print("compiles", rel)
sys.path.insert(0, str(L / "eval"))
import common, report
print("REPO", common.REPO.name, "ROOT", common.ROOT.name)
