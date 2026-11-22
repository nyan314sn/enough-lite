import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "rules_audit"))
import lib
lib.OUT = HERE
import replay_intake as R
lib.URL = os.environ.get("RECHECK_URL", "http://localhost:8120/")
from tour import *
with sync_playwright() as p:
    for n in sys.argv[1:]:
        P(f"===== {n} =====")
        safe(n, dict(idk=R.idk, long=R.longmsg, parent=R.parent, edit=R.edit, misc=R.misc)[n], p)
