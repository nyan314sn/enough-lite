import json,glob,os,re,collections
C=collections.Counter();ex=collections.defaultdict(list)
for f in sorted(glob.glob('eval_runs/*.json')):
    d=json.load(open(f,encoding='utf-8')); plan=[e for e in d['events'] if e.get('type')=='plan'][0]['plan']
    v=plan['verdict']; w=(plan['wishes']['line']+' '+plan['wants']['line']).lower(); n=os.path.basename(f)[:-5]
    if v=='works' and re.search(r'falls? short|does not last|not enough|runs? out in',w): C['works_but_text_says_short']+=1; ex['works_but_text_says_short'].append((n,plan['wishes']['line'][:150]))
    if v=='falls_short' and re.search(r'goal works|goal is met|covers? your goal|within the',w): C['short_but_text_says_works']+=1; ex['short_but_text_says_works'].append((n,plan['wishes']['line'][:150]))
    if v=='close' and re.search(r'\bworks\b',plan['wishes']['line'].lower()) : C['close_text_says_works']+=1; ex['close_text_says_works'].append((n,plan['wishes']['line'][:150]))
    thin=plan['wants']['above_basics_per_year']<0.05*plan['needs']['basics_per_year']
    big=plan['wants']['above_basics_per_year']>=0.25*plan['needs']['basics_per_year']
    if big and re.search(r'little room|not much|about the basics|barely',plan['wants']['line'].lower()): C['text_says_little_room_but_>=25%']+=1; ex['text_says_little_room_but_>=25%'].append((n,plan['wants']['above_basics_per_year'],plan['needs']['basics_per_year']))
    # horizon displayed
    h=plan['horizon_age']
    if h>105: C['horizon>105']+=1; ex['horizon>105'].append((n,h,d['profile'].get('age'),d['profile'].get('partner_age')))
    # first sentence of actions that are generic fillers
    for a in plan['actions']:
        if a['title']=='Check your plan once a year': C['filler_action']+=1; break
    if not plan['levers'] and False: pass
for k,v in C.items(): print(k,v,ex[k][:3])
