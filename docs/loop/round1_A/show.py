import json,sys
d=json.load(open(sys.argv[1],encoding='utf-8'))
for e in d['events']:
    if e.get('type')=='plan':
        print(json.dumps(e['plan'] if 'plan' in e else e,indent=1)[:int(sys.argv[2]) if len(sys.argv)>2 else 9000])
    else:
        print(e.get('type'), str(e)[:150])
