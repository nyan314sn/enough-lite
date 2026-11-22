import json,sys,glob,os
for f in sorted(glob.glob('plans/*.json')):
    if len(sys.argv)>1 and not any(a in f for a in sys.argv[1:]): continue
    d=json.load(open(f,encoding='utf-8')); ev=d['events']
    plan=[e for e in ev if e.get('type')=='plan'][0]['plan']
    print('=====',os.path.basename(f)[:-5],'verdict',plan['verdict'],'claim',plan['claim_age'],plan['partner_claim_age'],'already',plan['already_claiming'],'src',plan['text_source'])
    print(' H:',plan['headline']); print(' N:',plan['needs']['line']); print(' W:',plan['wants']['line']); print(' Wi:',plan['wishes']['line'])
    for a in plan['actions']: print('  A:',a['title'],'|',a['why'])
    for a in plan['worth_checking']: print('  WC:',a['title'])
    for a in plan['family_moments']: print('  FM:',a)
    print('  levers:',[l['key'] for l in plan['levers']])
    print('  events:',[ (e['age'],e['label'],e['change_per_year']) for e in plan['costs_by_age']['events']])
