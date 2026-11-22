"""Free (no AI) recompute for the 16 round-1 households and the 16 new ones: tax, Social Security, withdrawal rate,
simulation (rule of thumb and each claiming age), survivor step-down effect."""
import sys, asyncio, copy, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[2])); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "round1_A"))
import lib2 as L
import hh2
import get_plans as G
from app import pipeline
from app.agents import markets as mk
from app.tools import neighbors, simulate

ALL = dict(G.H); ALL.update(hh2.N)


async def go(prof):
    p = pipeline.prepare(copy.deepcopy(prof))
    plan, ctx = await pipeline.tools_only_plan(p)
    return p, plan, ctx


def pct(a, b):
    return (a - b) / b if b else 0.0


def main(names):
    for name in names:
        prof = ALL[name]
        p, plan, ctx = asyncio.run(go(prof))
        pd = p.model_dump()
        tx = ctx.results["tax"]; inp = mk.sim_inputs(ctx)
        age, ra = p.age, p.retire_age
        out = [f"=== {name} age {age} ret {ra} verdict {plan['verdict']} count {plan['wants']['per_year']:,.0f} basics {plan['needs']['basics_per_year']:,.0f} paid {plan['needs']['paid_of_100']} goal {plan['spending_goal']:,.0f}"]
        # working tax
        if p.household_pay() > 0 and ra > age:
            from app.tools import costs
            c = costs.contributions(p)
            lim = 25500
            def cap(a): return lim + (8500 if (a or 0) >= 50 else 0)
            pre = min(c["you"], cap(age)) if (p.pay_per_year or 0) > 0 else 0
            if p.has_partner and (p.partner_pay_per_year or 0) > 0:
                pre += min(c["partner"], cap(p.partner_age))
            kids = sum(1 for k in p.children if k.age is not None and k.age < 17)
            m = L.work_tax(p.pay_per_year or 0, p.partner_pay_per_year or 0, p.state, p.has_partner, kids, pre)
            m2 = L.work_tax(p.pay_per_year or 0, p.partner_pay_per_year or 0, p.state, p.has_partner, kids, pre, True)
            out.append(f"  tax working ({m['filing']}, kids<17 {kids}, pretax {pre:,.0f}): fed mine {m['fed']:,.0f} app {tx['federal_tax']:,.0f} | state {m['state']:,.0f}/{tx['state_tax']:,.0f} | fica {m['fica']:,.0f}/{tx['payroll_tax']:,.0f} (with +0.9% Medicare {m2['fica']:,.0f}) credit app {tx['child_tax_credit']}")
        # SS
        stated = p.sources.get("social_security_per_year") != "estimate" and prof.get("social_security_per_year")
        n = inp["horizon_age"] - age
        death = inp["ss_first_death_t"]
        if not stated:
            ppl = L.ss_people(pd)
            mine, claims = L.schedule(ppl, n, None, death)
            app = np.array(inp["ss_by_year"][:n])
            d = np.abs(mine - app).max()
            out.append(f"  SS (estimated) claims mine {claims} app {inp['ss_people'] and [x['claim'] for x in inp['ss_people']]} max abs diff by year {d:,.0f}; total yr0.. mine max {mine.max():,.0f} app {app.max():,.0f}; death_t {death}")
        else:
            out.append(f"  SS stated {prof['social_security_per_year']:,} -> app by-year max {max(inp['ss_by_year']):,.0f} claims {[ (x['who'], x['claim'], x['fixed']) for x in inp['ss_people']]} death_t {death} horizon {inp['horizon_age']}")
        # withdrawal rate
        over65 = int(ra >= 65) + int(p.has_partner and (p.partner_age or 0) + (ra - age) >= 65)
        pen = sum(x.per_year for x in p.pensions) + (p.part_time.per_year if p.part_time else 0)
        r, sr = L.ret_rate(p.spending_per_year, p.social_security_per_year or 0, p.savings.model_dump(), p.state, p.has_partner, over65, pen)
        out.append(f"  withdrawal rate mine {r:.4f} app {tx['effective_rate_on_withdrawals']:.4f} | SS tax rate mine {sr:.4f} app {tx['social_security_tax_rate']:.4f}")
        # simulation: rule + each claim
        person = p.model_dump()
        sim_in = mk.sim_inputs(ctx)
        cands = plan["neighbors"]["candidates_tested"]
        rule = [c for c in cands if c["source"] == "rule"][0]
        ppl_app = sim_in["ss_people"]
        def run_cand(cl, label, stock=None):
            ss, claims = L.schedule([dict(x, sp=x.get("spousal_pia", 0.0), amount=x.get("amount")) for x in ppl_app], n, cl, death)
            safe, ok = L.sim({**sim_in}, ss, stock_path=stock, ss_tax_rate=sim_in["ss_tax_rate"], paths=12000)
            return safe, ok, ss
        safe, ok, ss = run_cand(None, "rule")
        out.append(f"  rule: app safe {rule['safe_spending_per_year']:,.0f} mine {safe:,.0f} ({pct(safe, rule['safe_spending_per_year']):+.1%}) | goal lasts app {rule['goal_lasts_of_100']} mine {ok(sim_in['spend_per_year'])*100:.0f} | basics app {rule['basics_paid_of_100']} mine {ok(sim_in['basics_per_year'])*100:.0f}")
        for cc in [c for c in cands if c["source"].startswith("rule-claim-") and c["source"].split("-")[-1] in ("62", "67", "70")]:
            cl = int(cc["source"].split("-")[-1])
            s2, ok2, _ = run_cand(cl, cc["source"])
            out.append(f"    {cc['source']}: app {cc['safe_spending_per_year']:,.0f} mine {s2:,.0f} ({pct(s2, cc['safe_spending_per_year']):+.1%})")
        # survivor spending 75% variant (couples only)
        if death is not None and p.has_partner:
            s75, _ = L.sim({**sim_in}, ss, ss_tax_rate=sim_in["ss_tax_rate"], paths=12000, survivor_spend=.75, death=death)
            s0, _ = L.sim({**sim_in}, L.schedule([dict(x, sp=x.get("spousal_pia", 0.0)) for x in ppl_app], n, None, None)[0], ss_tax_rate=sim_in["ss_tax_rate"], paths=12000)
            out.append(f"  survivor: spending same {safe:,.0f} | spending 75% after first death {s75:,.0f} ({pct(s75, safe):+.1%}) | no step-down at all {s0:,.0f} ({pct(s0, safe):+.1%})")
        print("\n".join(out), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(ALL))
