import json,glob,os,sys
sys.path.insert(0,'.')
import recompute as R
for f in sorted(glob.glob('plans/*.json')):
    name=os.path.basename(f)[:-5]
    prof,plan,fin=R.load(f); t=fin['tax']['numbers']; m=fin['markets']['numbers']
    married=bool(prof.get('has_partner')); filing='married_joint' if married else 'single'
    sv=prof['savings']; tot=sum(sv.values()) or 1
    pre=sv['pretax']/tot; tx=(sv['taxable']+sv['cash'])/tot
    ss=m['social_security_per_year']; pen=sum(p['per_year'] for p in prof.get('pensions',[]))
    spend=plan['spending_goal']
    # years: typical retirement year with everything flowing; over-65 count
    n65=2 if married else 1
    def tax_total(W):
        ordi=0.85*ss+pen+W*pre; gains=W*tx*0.5
        g=ordi+gains
        return R.fed(ordi,filing,n65,gains)+R.strate(prof['state'],g,filing)*g
    # solve W: ss+pen+W-tax(W)=spend
    lo,hi=0,5e6
    for _ in range(60):
        mid=(lo+hi)/2
        if ss+pen+mid-tax_total(mid)>=spend: hi=mid
        else: lo=mid
    W=max(0,hi) if ss+pen<spend else 0
    mine=tax_total(W)
    app=t['tax_per_year_retired']
    flag=' **' if app and abs(mine-app)/max(app,1)>.05 else ''
    print(f"{name:32s} spend {spend:>8,.0f} ss {ss:>7,.0f} pen {pen:>6,.0f} | my tax {mine:>8,.0f} (W {W:>8,.0f}) app {app:>8,.0f} app_gross_wd {t['gross_withdrawal_per_year']:>8,.0f}{flag}")
