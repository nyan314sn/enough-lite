import json, collections
c=collections.Counter(json.loads(l).get('kind','base') for l in open('evalcopy/cases.jsonl',encoding='utf-8'))
print(c)
