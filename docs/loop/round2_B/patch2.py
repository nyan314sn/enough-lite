s=open("jr.py",encoding="utf-8").read()
s=s.replace('''  steps=["Retire at 62","what about my husband's age?","What if I get a dog"])''','''  rules=[(r"mortgage","No, I own it outright"),(r"pension","No pension")], steps=["Retire at 62","what about my husband's age?","What if I get a dog"])''')
s=s.replace('''  steps=["Retire at 65","Markets fall 30%"])''','''  rules=[(r"mortgage payment","$2,000 a month")], steps=["Retire at 65","Markets fall 30%","Retire when my wife is 65"])''')
open("jr.py","w",encoding="utf-8").write(s)
