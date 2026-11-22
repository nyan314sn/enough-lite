import json,glob,os
for f in sorted(glob.glob('plans/*.json')):
    d=json.load(open(f,encoding='utf-8')); ev=d['events']
    plan=[e for e in ev if e.get('type')=='plan'][0]['plan']
    fin={e['agent']:e['finding'] for e in ev if e.get('type')=='agent_done'}
    m=fin['markets']['numbers']; t=fin['tax']['numbers']
    print(os.path.basename(f)[:-5], plan['verdict'], 'ret',plan['retire_age'],'claim',plan['claim_age'],'goal',plan['spending_goal'],'count',plan['wants']['per_year'],'above',plan['wants']['above_basics_per_year'],'basics',plan['needs']['basics_per_year'],'paid',plan['needs']['paid_of_100'],'goal_lasts',m['goal_lasts_of_100'],'SS',m.get('social_security_per_year'),'save/yr',m.get('saving_per_year'),'savings',m.get('savings_now'),'hor',m['horizon_age'])
    print('    tax: fed',t['federal_tax'],'st',t['state_tax'],'fica',t['payroll_tax'],'after',t['after_tax_pay'],'ret_tax',t['tax_per_year_retired'],'wdrate',t['effective_rate_on_withdrawals'],'src',fin['tax'].get('source'), '| actions', [a['title'][:40] for a in plan['actions']], '| wc',[w['kind'] for w in plan['worth_checking']])
