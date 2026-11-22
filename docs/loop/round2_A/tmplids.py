import json,glob,os
ids=[]
for f in sorted(glob.glob('eval_runs/*.json')):
    x=json.load(open(f,encoding='utf-8')); pl=[e for e in x['events'] if e.get('type')=='plan'][0]['plan']
    if pl['text_source']=='template': ids.append(os.path.basename(f)[:-5])
print(','.join(ids[::6][:20]))
