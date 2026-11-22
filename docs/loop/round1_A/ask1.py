import json,sys,urllib.request
sys.path.insert(0,'.')
d=json.load(open('plans/'+sys.argv[1]+'.json',encoding='utf-8'))
plan=[e for e in d['events'] if e.get('type')=='plan'][0]['plan']
body=json.dumps({'question':sys.argv[2],'profile':d['profile'],'plan':plan}).encode()
req=urllib.request.Request('http://127.0.0.1:8030/api/ask',data=body,headers={'Content-Type':'application/json','X-Enough-Test':'1','X-Session-Id':'auditA-ask'},method='POST')
r=json.loads(urllib.request.urlopen(req,timeout=120).read())
print(json.dumps({k:v for k,v in r.items() if k not in('plan','chart')},indent=1)[:3500])
if 'plan' in r: print('PLAN count',r['plan']['wants']['per_year'],'verdict',r['plan']['verdict'])
