import sys, json, copy, asyncio
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE))
from app import pipeline
cases = {json.loads(l)["id"]: json.loads(l) for l in open(HERE/"evalcopy"/"cases.jsonl", encoding="utf-8")}
R1 = HERE.parent/"round1_A"/"eval_runs"; R2 = HERE.parent/"round2_A"/"eval_runs"
def load(d,i):
    f=d/(i+".json")
    if not f.exists(): return None
    x=json.load(open(f,encoding="utf-8"))
    pl=[e for e in x["events"] if e.get("type")=="plan"]
    return pl[0]["plan"] if pl else None
# find low-income cases where round2 count-on > 0 but now (tools) is 0 : first list r2 >0 candidates with pay<40000
ids = sys.argv[1:]
if not ids:
    ids=[]
    for i,c in cases.items():
        if c["kind"]!="base": continue
        pr=c["profile"]
        pay=(pr.get("pay_per_year") or 0)+(pr.get("partner_pay_per_year") or 0)
        pl=load(R2,i)
        if pl and pay and pay<45000 and pr.get("retire_age",0)>pr.get("age",0): ids.append(i)
for i in ids:
    pr=cases[i]["profile"]
    r1=load(R1,i); r2=load(R2,i)
    p=pipeline.prepare(copy.deepcopy(pr))
    plan,ctx=asyncio.run(pipeline.tools_only_plan(p))
    tx=ctx.results["tax"]; ms=ctx.results["money"]
    print(i, "age",p.age,"ret",p.retire_age,"pay",p.pay_per_year,"ppay",p.partner_pay_per_year,"spend_now",p.spending_now_per_year,"goal",p.spending_per_year,"sav",p.savings.total,
          "| r1", r1 and r1["wants"]["per_year"], "r2", r2 and r2["wants"]["per_year"], "now", plan["wants"]["per_year"], plan["verdict"], "paid", plan["needs"]["paid_of_100"],
          "| after-tax", tx.get("after_tax_pay"), "save_now", ms["save_now"], "SS", plan["social_security_per_year"])
