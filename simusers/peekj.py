"""Quick look at judged results."""
import glob
import json

for f in sorted(glob.glob("judged/*.json")):
    d = json.load(open(f, encoding="utf-8"))
    print(f, round(d["accuracy"]["share"] or 0, 2), [(i["ref"], i["type"], i["severity"], (i["quote"] or "")[:60]) for i in d["issues"]][:8])
    print("   wrong:", [(x["field"], x["got"], x["truth"]) for x in d["accuracy"]["fields"] if not x["ok"]])
