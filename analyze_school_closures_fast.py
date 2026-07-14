
import pandas as pd, numpy as np, re, json
from difflib import SequenceMatcher
from pathlib import Path

df=pd.read_csv('/mnt/data/all_schools.csv', dtype=str, keep_default_na=False)
if df.columns[0].startswith('Unnamed') or df.columns[0]=='': df=df.drop(columns=[df.columns[0]])
for c in df.columns: df[c]=df[c].astype(str).str.strip()
df['open_dt']=pd.to_datetime(df.get('EntityOpenDate',''), errors='coerce')
df['close_dt']=pd.to_datetime(df.get('EntityCloseDate',''), errors='coerce')
df['is_closed_status']=df['EntityStatus'].str.lower().str.contains('closed', na=False)
df['is_active_status']=df['EntityStatus'].str.lower().str.contains('open-active|active', na=False)
df['closed_since_2000_calc']=df['is_closed_status'] & (df['close_dt']>=pd.Timestamp('2000-01-01'))
df['ClosedSince2000_bool']=df['ClosedSince2000'].str.lower().isin(['true','1','yes']) if 'ClosedSince2000' in df.columns else df['closed_since_2000_calc']

generic_emails={'none@none.com','none@non.com','none@mi.gov','unknown@unknown.unknown','nonpublicschools@michigan.gov',''}
def norm_phone(s):
    d=re.sub(r'\D','',str(s or ''))
    if len(d)==11 and d.startswith('1'): d=d[1:]
    return d if len(d)==10 and d not in {'0000000000','9999999999'} else ''
abbr={'street':'st','st.':'st','avenue':'ave','ave.':'ave','road':'rd','rd.':'rd','drive':'dr','dr.':'dr','boulevard':'blvd','blvd.':'blvd','highway':'hwy','north':'n','south':'s','east':'e','west':'w','mount':'mt','saint':'st','center':'ctr','court':'ct','lane':'ln','place':'pl','circle':'cir','parkway':'pkwy'}
def norm_zip(s):
    d=re.sub(r'\D','',str(s or '')); return d[:5] if len(d)>=5 else ''
def norm_text(s):
    s=str(s or '').lower().replace('&',' and ')
    s=re.sub(r'[^a-z0-9]+',' ',s)
    return ' '.join(abbr.get(t,t) for t in s.split() if t not in {'po','box','p','o','suite','ste','unit'})
def norm_name(s):
    s=str(s or '').lower().replace('&',' and '); s=re.sub(r"['’]",'',s); s=re.sub(r'[^a-z0-9]+',' ',s); return ' '.join(s.split())
root_stop=set('school academy acad preschool pre nursery child children childrens center centre inc association of the for and at in lower upper campus elementary middle high jr junior senior north south east west facility facilities learning education preparatory prep corporation corp llc ltd association'.split())
def name_root(s): return ' '.join(t for t in norm_name(s).split() if t not in root_stop)
def sim(a,b): return SequenceMatcher(None,a,b).ratio() if a and b else 0.0

for col in ['EntityOfficialName','EntityEmail','EntityPhone','EntityPhysicalStreet','EntityPhysicalCity','EntityPhysicalZip4','EntityMailingStreet','EntityMailingCity','EntityMailingZip4','EntityCountyName','EntityGeographicLEADistrictOfficialName']:
    if col not in df.columns: df[col]=''
df['name_norm']=df['EntityOfficialName'].map(norm_name); df['name_root']=df['EntityOfficialName'].map(name_root)
df['email_norm']=df['EntityEmail'].str.lower().str.strip(); df.loc[df['email_norm'].isin(generic_emails),'email_norm']=''
df['phone_norm']=df['EntityPhone'].map(norm_phone)
df['phys_addr_norm']=(df['EntityPhysicalStreet'].map(norm_text)+'|'+df['EntityPhysicalCity'].map(norm_text)+'|'+df['EntityPhysicalZip4'].map(norm_zip)).str.strip('|')
df['mail_addr_norm']=(df['EntityMailingStreet'].map(norm_text)+'|'+df['EntityMailingCity'].map(norm_text)+'|'+df['EntityMailingZip4'].map(norm_zip)).str.strip('|')
df['county_norm']=df['EntityCountyName'].map(norm_text); df['district_norm']=df['EntityGeographicLEADistrictOfficialName'].map(norm_text)
closed=df[df['ClosedSince2000_bool']].copy(); active=df[df['is_active_status']].copy()
email_counts=df.loc[df['email_norm']!='','email_norm'].value_counts().to_dict(); phone_counts=df.loc[df['phone_norm']!='','phone_norm'].value_counts().to_dict(); addr_counts=df.loc[df['phys_addr_norm'].str.len()>5,'phys_addr_norm'].value_counts().to_dict()

def make_idx(frame, col):
    idx={}
    for i,v in frame[col].items():
        if v: idx.setdefault(v,set()).add(i)
    return idx
idxs={c:make_idx(active,c) for c in ['name_norm','name_root','email_norm','phone_norm','phys_addr_norm','mail_addr_norm']}
# token+county blocking index
active_token_county={}
for i,r in active.iterrows():
    for t in set(r['name_root'].split()):
        if len(t)>=4 and t not in {'christian','catholic','lutheran','baptist','montessori','academy'}:
            active_token_county.setdefault((r['county_norm'],t),set()).add(i)

rows=[]
for ci,cr in closed.iterrows():
    cand=set()
    for c in idxs:
        v=cr[c]
        if v: cand |= idxs[c].get(v,set())
    for t in set(cr['name_root'].split()):
        if len(t)>=4 and t not in {'christian','catholic','lutheran','baptist','montessori','academy'}:
            cand |= active_token_county.get((cr['county_norm'],t),set())
    best=None
    for ai in cand:
        ar=df.loc[ai]
        ns=sim(cr['name_norm'],ar['name_norm']); rs=sim(cr['name_root'],ar['name_root'])
        n_exact=cr['name_norm']==ar['name_norm'] and cr['name_norm']!=''; r_exact=cr['name_root']==ar['name_root'] and cr['name_root']!=''
        same_county=cr['county_norm']==ar['county_norm'] and cr['county_norm']!=''; same_dist=cr['district_norm']==ar['district_norm'] and cr['district_norm']!=''
        same_email=bool(cr['email_norm'] and cr['email_norm']==ar['email_norm'] and email_counts.get(cr['email_norm'],0)<=3)
        same_phone=bool(cr['phone_norm'] and cr['phone_norm']==ar['phone_norm'] and phone_counts.get(cr['phone_norm'],0)<=5)
        same_addr=bool(cr['phys_addr_norm'] and cr['phys_addr_norm']==ar['phys_addr_norm'] and addr_counts.get(cr['phys_addr_norm'],0)<=5)
        same_mail=bool(cr['mail_addr_norm'] and cr['mail_addr_norm']==ar['mail_addr_norm'])
        temporal=False
        if pd.notna(ar['open_dt']) and pd.notna(cr['close_dt']): temporal=ar['open_dt'] >= cr['close_dt'] - pd.Timedelta(days=730)
        elif pd.isna(ar['open_dt']): temporal=True
        reasons=[]; score=0
        if n_exact and same_county: score+=45; reasons.append('exact same name in same county')
        elif n_exact: score+=35; reasons.append('exact same name')
        if r_exact and same_county: score+=20; reasons.append('same simplified/root name in same county')
        if ns>=0.92 and same_county: score+=25; reasons.append(f'very similar name ({ns:.2f}) in same county')
        elif ns>=0.82 and same_county: score+=15; reasons.append(f'similar name ({ns:.2f}) in same county')
        if same_email: score+=35; reasons.append('same non-generic email')
        if same_phone: score+=25; reasons.append('same phone')
        if same_addr: score+=30; reasons.append('same physical address')
        if same_mail: score+=10; reasons.append('same mailing address')
        if same_dist: score+=5
        if temporal: score+=8; reasons.append('active/open date fits continuation window')
        confidence=''
        if score>=75 or (same_addr and (n_exact or ns>=0.72 or same_phone or same_email)) or (same_email and (ns>=0.65 or same_addr or same_phone)) or (same_phone and (ns>=0.72 or same_addr)) or (n_exact and same_county and (temporal or same_addr or same_phone or same_email)):
            confidence='high'
        elif score>=55 or (n_exact and same_county) or (same_addr and rs>=0.55) or (same_phone and rs>=0.55): confidence='medium'
        elif score>=40: confidence='low'
        if confidence:
            rec={'closed_index':ci,'active_index':ai,'score':score,'confidence':confidence,'reasons':'; '.join(reasons),'closed_name':cr['EntityOfficialName'],'active_name':ar['EntityOfficialName'],'closed_entity_code':cr.get('EntityCode',''),'active_entity_code':ar.get('EntityCode',''),'closed_date':str(cr['close_dt'].date()) if pd.notna(cr['close_dt']) else '','active_open_date':str(ar['open_dt'].date()) if pd.notna(ar['open_dt']) else '','closed_city':cr['EntityPhysicalCity'],'active_city':ar['EntityPhysicalCity'],'closed_county':cr.get('EntityCountyName',''),'active_county':ar.get('EntityCountyName',''),'name_similarity':round(ns,3),'root_similarity':round(rs,3)}
            if best is None or rec['score']>best['score']: best=rec
    if best: rows.append(best)

m=pd.DataFrame(rows)
high=m[m['confidence']=='high'] if len(m) else m
medium=m[m['confidence'].isin(['high','medium'])] if len(m) else m
baseline=len(closed); calc_baseline=int(df['closed_since_2000_calc'].sum()); col_baseline=int(df['ClosedSince2000_bool'].sum())
pre_terms=r"preschool|nursery|day care|child care|child dev|childrens|children's|coop|cooperative"
closed_pre=closed[closed['EntityOfficialName'].str.lower().str.contains(pre_terms, regex=True, na=False)]
out_cols=['confidence','score','closed_name','closed_entity_code','closed_date','active_name','active_entity_code','active_open_date','closed_city','active_city','closed_county','reasons','name_similarity','root_similarity']
if len(m):
    co={'high':0,'medium':1,'low':2}
    match_out=m[out_cols].assign(_ord=m['confidence'].map(co)).sort_values(['_ord','score'],ascending=[True,False]).drop(columns=['_ord'])
else: match_out=pd.DataFrame(columns=out_cols)
match_out.to_csv('/mnt/data/closure_continuation_candidates.csv', index=False)
closed_report=closed.copy(); closed_report['duplicate_match_confidence']=''; closed_report['matched_active_name']=''; closed_report['matched_active_entity_code']=''; closed_report['match_reasons']=''
for _,r in m.iterrows():
    ci=r['closed_index']; closed_report.loc[ci,'duplicate_match_confidence']=r['confidence']; closed_report.loc[ci,'matched_active_name']=r['active_name']; closed_report.loc[ci,'matched_active_entity_code']=r['active_entity_code']; closed_report.loc[ci,'match_reasons']=r['reasons']
closed_report['recommended_count_as_real_closure']=~closed_report['duplicate_match_confidence'].eq('high')
selected=['EntityCode','EntityOfficialName','EntityStatus','EntityOpenDate','EntityCloseDate','EntityTypeName','EntityTypeCategoryName','EntityCountyName','EntityEmail','EntityPhone','EntityPhysicalStreet','EntityPhysicalCity','EntityPhysicalZip4','duplicate_match_confidence','matched_active_name','matched_active_entity_code','match_reasons','recommended_count_as_real_closure']
closed_report[selected].to_csv('/mnt/data/closed_since_2000_classified.csv', index=False)
reason_counts={}
for rsn in m.get('reasons',[]):
    for r in rsn.split('; '):
        if r and not r.startswith('similar name') and not r.startswith('very similar'): reason_counts[r]=reason_counts.get(r,0)+1
summary={'rows':int(len(df)),'active_count':int(len(active)),'closed_since_2000_column_count':int(col_baseline),'closed_since_2000_calc_count':int(calc_baseline),'high_conf_continuations':int(len(high)),'medium_or_high_continuations':int(len(medium)),'low_or_better_continuations':int(len(m)),'estimate_real_closures_high_only':int(baseline-len(high)),'estimate_if_medium_excluded':int(baseline-len(medium)),'closed_preschool_nursery_named':int(len(closed_pre)),'common_close_dates':closed['close_dt'].dt.strftime('%Y-%m-%d').value_counts().head(10).to_dict(),'close_year_counts':{int(k):int(v) for k,v in closed['close_dt'].dt.year.value_counts().sort_index().dropna().items()},'reason_counts':reason_counts,'examples':match_out.head(25).to_dict(orient='records')}
Path('/mnt/data/closure_analysis_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary, indent=2))
