import json,glob,os,re,sys,collections
sys.path.insert(0,'.')
import numcheck
files=sorted(glob.glob('eval_runs/*.json'))
C=collections.Counter(); ex=collections.defaultdict(list)
def flag(k,name,info=''):
    C[k]+=1
    if len(ex[k])<6: ex[k].append((name,info))
n=0
for f in files:
    d=json.load(open(f,encoding='utf-8')); name=os.path.basename(f)[:-5]
    if d.get('status')!='ok': flag('status_error',name,d.get('error')); continue
    plan=[e for e in d['events'] if e.get('type')=='plan'][0]['plan']; prof=d['profile']
    kind=d.get('kind','base'); n+=1
    paid=plan['needs']['paid_of_100']; v=plan['verdict']; cnt=plan['wants']['per_year']; basics=plan['needs']['basics_per_year']
    fin={e['agent']:e['finding'] for e in d['events'] if e.get('type')=='agent_done'}
    m=fin['markets']['numbers']
    # 1 verdict vs paid
    if (paid is not None and paid<90) != (v=='falls_short') and paid is not None and paid<90: flag('verdict_not_falls_short_when_paid<90',name,(paid,v))
    if v=='falls_short' and paid is not None and paid>=90: flag('falls_short_with_basics_ok',name,(paid,v,cnt,plan['spending_goal']))
    # works consistency
    goal=plan['spending_goal']
    if v=='works' and cnt<goal: flag('works_but_count<goal',name,(cnt,goal))
    if v!='works' and cnt>=goal: flag('notworks_but_count>=goal',name,(cnt,goal,v))
    if v=='close' and not (0.9*goal<=cnt<goal): flag('close_range',name,(cnt,goal))
    # headline numbers
    if f"${cnt:,.0f}" not in plan['headline']: flag('headline_count_mismatch',name,(cnt,plan['headline'][:80]))
    ab=max(0,round(cnt-basics,-2))
    if abs(plan['wants']['above_basics_per_year']-ab)>0.5: flag('above_basics_mismatch',name,(plan['wants']['above_basics_per_year'],ab))
    if plan['count_on_per_year']!=cnt: flag('count_on_field_mismatch',name)
    if m.get('wants_per_year') is not None and abs(m['wants_per_year']-cnt)>0.5: flag('markets_wants_vs_plan',name,(m['wants_per_year'],cnt))
    if cnt>basics and plan['wants']['above_basics_per_year']<=0: flag('above0_but_count>basics',name,(cnt,basics))
    # duplicates among actions
    titles=[a['title'].lower() for a in plan['actions']]
    if len(set(titles))<len(titles): flag('duplicate_action_title',name,titles)
    # actions vs levers: debt / match must have a slot
    keys=[l['key'] for l in plan['levers']]
    txt=' '.join(a['title']+' '+a['why'] for a in plan['actions']).lower()
    if 'debt' in keys and 'debt' not in txt: flag('debt_lever_no_action',name)
    if 'match' in keys and 'match' not in txt: flag('match_lever_no_action',name)
    if 'goal' in keys and not any('goal' in t or 'spend' in t for t in titles): flag('goal_lever_no_action',name)
    if len(plan['actions'])>3 or len(plan['actions'])<1: flag('action_count',name,len(plan['actions']))
    # needs line contradiction
    nl=plan['needs']['line'].lower()
    if paid is not None and paid<90 and re.search(r'you pay them|are paid|paid every|paid in (all )?100|pay them every',nl): flag('needs_line_says_paid_but_paid<90',name,(paid,plan['needs']['line'][:90]))
    if paid is not None and paid>=90 and re.search(r'not paid|cannot pay|short',nl): flag('needs_line_says_short_but_paid>=90',name,(paid,))
    # claim age display vs profile claim age
    ca=prof.get('claim_age')
    if ca is not None and plan['claim_age']!=ca and (prof['age']<ca or ca<=70): 
        if prof['age']>=ca: flag('claim_age_shown_differs_from_stated(already claiming)',name,(ca,plan['claim_age'],prof['age']))
        else: flag('claim_age_shown_differs_from_stated(not yet)',name,(ca,plan['claim_age'],prof['age']))
    # worth_checking rules
    wc={w['kind'] for w in plan['worth_checking']}
    kids=any(((c.get('age') if c.get('age') is not None else 6)<22) for c in prof.get('children',[]))
    ins=prof.get('insurance') or {}
    nolife=(ins.get('life_kind') in (None,'none')) or not (ins.get('life_face') or 0)
    if 'term_life' in wc and not (kids or (prof.get('has_partner') and not prof.get('partner_pay_per_year') and prof.get('pay_per_year'))): flag('term_life_fired_without_dependants',name)
    if 'term_life' in wc and not nolife: flag('term_life_fired_with_cover',name)
    if 'income_annuity' in wc and (prof.get('has_partner') or prof.get('pensions')): flag('annuity_fired_partner_or_pension',name)
    sv=sum((prof.get('savings') or {}).values())
    if 'income_annuity' in wc and sv<200000: flag('annuity_fired_low_savings',name,sv)
    # horizon
    # numbers
    try:
        bad=numcheck.check(d)
        if bad: flag('dollar_figure_not_in_tool_outputs',name,bad[:3])
    except Exception as e: flag('numcheck_err',name,str(e)[:60])
    if plan['text_source']!='ai' and not plan['text_source'].startswith('ai'): flag('template_text',name,plan['text_source'])
    elif 'second' in plan['text_source']: flag('ai_second_try',name)
    for e in d['events']:
        if e.get('type')=='agent_done' and str(e['finding'].get('source','')).startswith('template'): flag('agent_template_'+e['agent'],name,e['finding']['source'][:60])
print('runs ok analysed:',n)
for k,v in sorted(C.items()): print(f'{k:60s} {v:4d}  e.g. {ex[k][:3]}')
