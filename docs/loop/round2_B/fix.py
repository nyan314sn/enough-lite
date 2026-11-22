L = open("v1.py", encoding="utf-8").read().split("\n")
out=[]; i=0
while i < len(L):
    if L[i].startswith('    log("SAVING SECTION:"'):
        out.append('    t = pg.locator("aside").first.inner_text().replace(chr(10), " | "); log("SAVING SECTION:", t[t.find("Savings"):][:1200])')
        i += 3; continue
    out.append(L[i]); i += 1
open("v1.py","w",encoding="utf-8").write("\n".join(out))
