import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
for e in d['events']:
    if e.get('type')=='agent_done':
        print('==',e['agent']); print(json.dumps(e['finding'],indent=1)[:int(sys.argv[2]) if len(sys.argv)>2 else 3000])
