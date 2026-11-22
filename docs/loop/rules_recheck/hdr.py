import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "rules_audit"))
import lib
lib.OUT = HERE
lib.URL = os.environ.get("RECHECK_URL", "http://localhost:8120/")
from tour import *
W = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
H = 844 if W < 600 else 900
def sub(pg, label):
    t = pg.locator(".turn").last.inner_text().replace("\n"," | ") if pg.locator(".turn").count() else ""
    P(label, "->", t[:700])
