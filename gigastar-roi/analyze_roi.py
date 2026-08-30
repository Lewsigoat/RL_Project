import json, csv, datetime as dt

TODAY = dt.date(2026, 8, 30)
rois = json.load(open('offerRois.json'))
pv   = {x['name']: x for x in json.load(open('offer_previews.json'))['offerPreviews']}
wb   = {o['symbol']: o for o in json.load(open('offerings_meta.json'))}
MANUAL_GOLD = {'CVT.1': 15.0}          # SEC Form C: "Price per RSU: $15"
MANUAL_CLOSE= {'CVT.1': '2023-05-05'}  # CVT.1 closed May 2023

rows=[]
for r in rois:
    p = pv.get(r['offerName']); w = wb.get(p['wbSymbol']) if p else None
    gold = (w or {}).get('unitPrice') or MANUAL_GOLD.get(r['offerName'])
    aggC = r.get('aggregateCost') or 0
    aggD = r.get('aggregateNetDistributionAll') or 0
    if not aggC or not gold: 
        rows.append(dict(drop=r['displayName'], channel=r['channelName'], cat=r['category'],
            status=(p or {}).get('status'), close=None, gold=gold, raised=aggC,
            dist_total=aggD, per_unit=None, roi=None, months=None, ann=None)); continue
    roi  = aggD/aggC
    per  = gold*roi
    close= (w or {}).get('endDate','')[:10] or MANUAL_CLOSE.get(r['offerName'])
    mo = None; ann=None
    if close:
        d = dt.date(*map(int, close.split('-')))
        mo = (TODAY - d).days/30.44
        if mo >= 6: ann = roi/(mo/12)
    rows.append(dict(drop=r['displayName'], channel=r['channelName'], cat=r['category'],
        status=(p or {}).get('status'), close=close, gold=gold, raised=aggC,
        dist_total=aggD, per_unit=per, roi=roi, months=mo, ann=ann))

funded  = [x for x in rows if x['raised'] and x['gold']]
dead    = [x for x in rows if not x['raised']]
live    = [x for x in funded if x['status']=='open']
closed  = [x for x in funded if x['status']!='open']

cost = sum(x['gold'] for x in funded); recv = sum(x['per_unit'] for x in funded)
c2   = sum(x['gold'] for x in closed); r2  = sum(x['per_unit'] for x in closed)

print("="*74)
print("GIGASTAR — 1 GOLD (LOWEST) TIER CRT IN EVERY HISTORIC DROP, as of 2026-08-30")
print("="*74)
print(f"Drops ever filed/listed ............ {len(rows)}")
print(f"  funded & purchasable ............ {len(funded)}   ({len(closed)} closed + {len(live)} still open)")
print(f"  never funded / withdrawn ........ {len(dead)}  -> {', '.join(x['drop'] for x in dead)}")
print()
print(f"Total invested (1 Gold CRT each) .. ${cost:>9,.2f}")
print(f"Total distributions to date ....... ${recv:>9,.2f}")
print(f"Net position ...................... ${recv-cost:>9,.2f}")
print(f"ROI to date ....................... {recv/cost*100:>9.2f}%")
print(f"  excluding the still-open drop ... {r2/c2*100:>9.2f}%  (${c2:,.0f} in, ${r2:,.2f} back)")
print()
wins=[x for x in closed if x['roi']>0]
print(f"Drops that have paid anything ..... {len(wins)}/{len(closed)}")
print(f"Drops that returned >100% ......... {sum(1 for x in closed if x['roi']>1)}")
print(f"Median drop ROI ................... {sorted(x['roi'] for x in closed)[len(closed)//2]*100:.2f}%")
print(f"Best  ............................. {max(closed,key=lambda z:z['roi'])['drop']} {max(x['roi'] for x in closed)*100:.1f}%")
print(f"Worst ............................. {min(closed,key=lambda z:z['roi'])['drop']} {min(x['roi'] for x in closed)*100:.1f}%")
seasoned=[x for x in closed if x['months'] and x['months']>=24]
print(f"\nDrops seasoned >=24 months ({len(seasoned)}): ROI {sum(x['per_unit'] for x in seasoned)/sum(x['gold'] for x in seasoned)*100:.2f}%")
for f_ in (8,):
    fc=cost+f_*len(funded); print(f"With ${f_}/order fees ({len(funded)} orders): invested ${fc:,.2f} -> ROI {recv/fc*100:.2f}%")
print()
hdr=f"{'Drop':<25}{'Closed':<11}{'Mo':>5}{'Gold$':>7}{'Paid/CRT':>10}{'ROI%':>8}{'Ann%':>7}"
print(hdr); print('-'*len(hdr))
for x in sorted(funded,key=lambda z:-(z['roi'] or 0)):
    mo = "%.0f" % x['months'] if x['months'] else '-'
    an = "%.1f" % (x['ann']*100) if x['ann'] else '-'
    print("%-25s%-11s%5s%7.0f%10.2f%8.2f%7s" % (x['drop'][:24], x['close'] or '-', mo, x['gold'], x['per_unit'], x['roi']*100, an))
with open('gigastar_roi.csv','w',newline='') as f:
    w_=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w_.writeheader(); w_.writerows(rows)
json.dump(rows,open('gigastar_roi.json','w'),indent=1,default=str)
print(f"\nsum of all drop distributions ${sum(x['dist_total'] for x in rows):,.2f} vs platform keyMetrics $1,478,488.85")
