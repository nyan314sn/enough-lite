import json,glob,collections
c=collections.Counter()
for f in glob.glob('eval_runs_tmpl/*.json'):
    x=json.load(open(f,encoding='utf-8')); pl=[e for e in x['events'] if e.get('type')=='plan'][0]['plan']; c[pl['text_source'][:40]]+=1
print(c)
