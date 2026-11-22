import json
ids=[json.loads(l)['id'] for l in open('evalcopy/cases.jsonl',encoding='utf-8') if json.loads(l).get('kind','base') in ('base','savings_up','retire_later')]
print(','.join(ids[-130:]))
