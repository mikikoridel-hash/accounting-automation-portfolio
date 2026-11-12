"""Synthetic Super Bill importer. Python standard library, no Excel installation.
Reads demo facility tabs by header; not a general Excel engine.
"""
import csv, hashlib, json, posixpath, re, os, tempfile, zipfile
from pathlib import Path
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parent
FIELDS='Shift ID|Service Date|Agency|Facility|Staff ID|Role|Unit|RT Hrs|OT Hrs|DT Hrs|Charge RT Hrs|Charge OT Hrs|Regular Rate|OT Rate|DT Rate|Charge RT Premium|Charge OT Premium|Additional|Additional Reason|Calculated Total'.split('|')
NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
D=Decimal

def read_rows(path):
    with zipfile.ZipFile(path) as z:
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        sheets=list(wb.find(NS+'sheets'))
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets={r.get('Id'):r.get('Target') for r in rels}
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(t.text or '' for t in si.iter(NS+'t')) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        def val(c):
            if c.get('t')=='inlineStr': return ''.join(t.text or '' for t in c.iter(NS+'t'))
            v=c.findtext(NS+'v') or ''
            if c.get('t')=='s': return strings[int(v)]
            if c.get('t')=='e': raise ValueError(f'{path.name}: Excel error at {c.get("r")}')
            return v
        combined=[]; matched=0
        for sheet in sheets:
            if sheet.get('name') == 'Invoice Review': continue
            target=targets[sheet.get(REL+'id')]
            target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
            rows=[]
            for row in ET.fromstring(z.read(target)).find(NS+'sheetData'):
                cells={re.match(r'[A-Z]+',c.get('r')).group():val(c) for c in row if c.tag==NS+'c'}
                values=[cells.get(chr(65+i),'') for i in range(20)]
                if not any(values): continue
                if not rows:
                    if values!=FIELDS: break
                    rows.append(None); continue
                r=dict(zip(FIELDS,values))
                if not all(r[h] for h in FIELDS[:7]): raise ValueError(f'{path.name}: missing required field')
                try: r['Service Date']=date.fromisoformat(r['Service Date']).isoformat()
                except ValueError: r['Service Date']=(date(1899,12,30)+timedelta(days=int(D(r['Service Date'])))).isoformat()
                nums=[D(r[h]) for h in FIELDS[7:18]]
                rt,ot,dt,crt,cot,base,otr,dtr,cp,op,extra=nums
                if any(not n.is_finite() or n<0 for n in nums) or rt>8 or ot>4 or crt>rt or cot>ot or (ot and rt!=8) or (dt and (rt!=8 or ot!=4)):
                    raise ValueError(f'{path.name}: invalid hours/rates for {r["Shift ID"]}')
                if otr!=base*D('1.5') or dtr!=base*2 or cp!=8 or op!=12:
                    raise ValueError(f'{path.name}: invalid demo rates')
                # Recompute independently; Excel cached formula results may be stale.
                r['Calculated Total']=str((rt*base+ot*otr+dt*dtr+crt*cp+cot*op+extra).quantize(D('.01'),rounding=ROUND_HALF_UP))
                rows.append({'SourceTab':sheet.get('name'),**r})
            if rows: combined.extend(rows[1:]); matched+=1
        if not matched: raise ValueError(f'{path.name}: no timesheet headers found')
        return combined

def atomic(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False,mode='w',encoding='utf-8',newline='') as f:
        f.write(content); name=f.name
    os.replace(name,path)

def run(root=ROOT):
    import io
    raw=root/'raw'; out=root/'output'; state=out/'state.json'
    previous=json.loads(state.read_text()) if state.exists() else {}
    files=sorted(p for p in raw.glob('*.xlsx') if not p.name.startswith('~$'))
    if not files: raise ValueError('No Excel files in raw/')
    missing=set(previous)-{p.name for p in files}
    if missing: raise ValueError('Previously imported source missing: '+', '.join(sorted(missing))+'; restore it before importing.')
    updated={}; stats={'New':0,'Changed':0,'Unchanged':0}; log=[]
    for p in files:
        digest=hashlib.sha256(p.read_bytes()).hexdigest(); old=previous.get(p.name)
        status='Unchanged' if old and old['hash']==digest else 'Changed' if old else 'New'
        rows=old['rows'] if status=='Unchanged' else read_rows(p)
        updated[p.name]={'hash':digest,'rows':rows}; stats[status]+=1
        log.append([p.name,status,len(rows),len(old['rows']) if old else 0])
    records=[]; seen=set()
    for name, entry in updated.items():
        for r in entry['rows']:
            key=r['Shift ID']
            if key in seen: raise ValueError('Duplicate Shift ID: '+key)
            seen.add(key); records.append({'SourceFile':name,**r})
    # Validate everything before committing the canonical state. CSV is a derived export.
    buf=io.StringIO(); writer=csv.DictWriter(buf,fieldnames=['SourceFile','SourceTab']+FIELDS);writer.writeheader();writer.writerows(records)
    # Mapping is reapplied each run; raw data remains unchanged.
    def mapping(name):
        with (root/'mapping'/f'{name}.csv').open(newline='',encoding='utf-8') as f:
            result={}
            for row in csv.DictReader(f):
                key=row['Raw'].strip().casefold(); value=row['Standard'].strip()
                if not key or not value or (key in result and result[key]!=value): raise ValueError('Invalid mapping: '+name)
                result[key]=value
            return result
    facilities=mapping('FacilityMap'); agencies=mapping('AgencyMap')
    clean=[]; issues=[]
    for r in records:
        facility=facilities.get(r['Facility'].strip().casefold(),'')
        agency=agencies.get(r['Agency'].strip().casefold(),'')
        status='OK' if facility and agency else 'REVIEW'
        clean.append({**r,'Facility Standard':facility,'Agency Standard':agency,'Mapping Status':status})
        for field,value in [('Facility',facility),('Agency',agency)]:
            if not value: issues.append({'SourceFile':r['SourceFile'],'SourceTab':r['SourceTab'],'Shift ID':r['Shift ID'],'Field':field,'Raw Value':r[field]})
    def export(name,fields,rows):
        b=io.StringIO(); w=csv.DictWriter(b,fieldnames=fields); w.writeheader(); w.writerows(rows); atomic(out/name,b.getvalue())
    export('CleanedData.csv',['SourceFile','SourceTab']+FIELDS+['Facility Standard','Agency Standard','Mapping Status'],clean)
    export('MappingQC.csv',['SourceFile','SourceTab','Shift ID','Field','Raw Value'],issues)
    atomic(state,json.dumps(updated,indent=2)+'\n')
    atomic(out/'MasterData.csv',buf.getvalue())
    logbuf=io.StringIO(); w=csv.writer(logbuf);w.writerow(['SourceFile','Status','CurrentRows','PreviousRows']);w.writerows(log)
    atomic(out/'ImportLog.csv',logbuf.getvalue())
    print(f"Imported {len(records)} rows | "+' | '.join(f'{k}={v}' for k,v in stats.items()))
    return stats, records

if __name__=='__main__': run()
