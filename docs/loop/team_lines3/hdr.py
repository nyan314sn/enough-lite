import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "rules_audit"))
import lib
lib.OUT = HERE
lib.URL = "http://localhost:8124/"
from tour import *
W = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
H = 844 if W < 600 else 900
FIRST = "I'm 52, an electrician in Ohio making $96,000. My wife Maria is 50 and teaches, making $58,000. We have $510,000 saved, own our home with no mortgage, no kids, spend $6,000 a month. I want to retire at 60."
def fresh(p, first=FIRST, w=None):
    b, pg = newctx(p, w or W, H)
    say(pg, first)
    for i in range(10):
        if can_build(pg): break
        cs = chips(pg); say(pg, cs[0] if cs else "skip")
    return b, pg
