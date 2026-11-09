import argparse, json, re, subprocess, hashlib, os, tempfile
from pathlib import Path
from decimal import Decimal, InvalidOperation
from concurrent.futures import ThreadPoolExecutor

def call(*args,cwd=None):
    p=subprocess.run(['lark-cli',*args,'--as','user'],cwd=cwd,capture_output=True,text=True,timeout=120)
    if p.returncode: raise RuntimeError((p.stderr or p.stdout)[-1500:])
    x=json.loads(p.stdout)
    if not x.get('ok'): raise RuntimeError(str(x.get('error')))
    return x['data']

def write(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=p.parent,mode='w',delete=False) as f:
        json.dump(x,f,ensure_ascii=False,indent=2); name=f.name
    os.replace(name,p)

def column(n):
    s=''
    while n:n,r=divmod(n-1,26);s=chr(65+r)+s
    return s

def ledger(url,out):
    token=call('wiki','+node-get','--node-token',url)['obj_token'] if '/wiki/' in url else url
    base=['--spreadsheet-token',token]
    book=call('sheets','+workbook-info',*base)
    records=[]
    for s in book['sheets']:
        args=[*base,'--sheet-id',s['sheet_id']]
        layout=call('sheets','+sheet-info',*args,'--include','merges')
        grid={}
        for start in range(1,s['row_count']+1,20):
            stop=min(start+19,s['row_count'])
            for a in range(1,s['column_count']+1,26):
                end=min(a+25,s['column_count'])
                d=call('sheets','+cells-get',*args,'--range',f'{column(a)}{start}:{column(end)}{stop}')
                if d.get('has_more'):raise RuntimeError('Incomplete range')
                for block in d['ranges']:
                    for n,row in zip(block['row_indices'],block['cells']):
                        grid.setdefault(n,{}).update(zip(block['col_indices'],row))
        def cell(n,c):return (grid.get(n,{}).get(c) or {})
        def val(n,c):return cell(n,c).get('value')
        merged={}
        for m in layout.get('merged_cells',[]):
            k=re.fullmatch(r'([ABC])(\d+):\1(\d+)',m['range'])
            if k:
                c,a,b=k.groups()
                for n in range(int(a),int(b)+1):merged[n,c]=int(a)
        for n in sorted(grid):
            if n==1 or not val(n,'E'):continue
            fields=dict(zip(('project_id','project_name','owner','contract_link','contract_id','agreement_type','contract_name','buyer','supplier','ledger_tax_inclusive_amount','signed_date','handler','note','quote_link'),'ABCDEFGHIJKLMN'))
            r={k:val(merged.get((n,c),n),c) for k,c in fields.items()}
            r.update(sheet=s['sheet_name'],row=n,record_id=f"{s['sheet_id']}:{n}",attachments=[{'token':t['mention_token'],'type':t.get('mention_type'),'name':t.get('text','')} for c in ('D','N') for t in cell(n,c).get('rich_text',[]) if t.get('mention_token')])
            records.append(r)
    write(out,records)
    print(f'{len(records)} ledger rows')

def attachments(src,out,workers):
    root=Path(out).resolve(); root.mkdir(parents=True,exist_ok=True)
    refs={}
    for r in json.loads(Path(src).read_text()):
        for a in r['attachments']:
            item=refs.setdefault(a['token'],{**a,'record_ids':[]});item['record_ids'].append(r['record_id'])
    def one(a):
        key=hashlib.sha256(a['token'].encode()).hexdigest()
        folder=root/key;folder.mkdir(exist_ok=True); cache=folder/'result.json'
        if cache.exists():
            old=json.loads(cache.read_text())
            if old['status']=='downloaded':return {**old,**a}
        try:
            if a['type']==22:
                data=call('docs','+fetch','--doc',a['token'])
                (folder/'document.xml').write_text(data['document']['content'])
            else:
                suffix=Path(a['name'].strip()).suffix.lower()
                call('drive','+download','--file-token',a['token'],'--output','source'+suffix,'--overwrite',cwd=folder)
            result={**a,'artifact_dir':key,'status':'downloaded'}
        except Exception as e:result={**a,'artifact_dir':key,'status':'failed','error':str(e)}
        write(cache,result);return result
    with ThreadPoolExecutor(max_workers=workers) as pool: result=list(pool.map(one,refs.values()))
    write(root/'manifest.json',result)
    print(f"{sum(r['status']=='downloaded' for r in result)}/{len(result)} references downloaded")

def number(v):
    try:
        x=Decimal(str(v).replace(',',''))
        return x if x.is_finite() else None
    except InvalidOperation:return None

def compare(data,query):
    keys=['category','currency','tax_basis','scope','price_stage']
    if query['level']=='bom':keys+=['unit','spec']
    amount='unit_price' if query['level']=='bom' else 'amount'
    if any(query.get(k) in ('',None,'unknown') for k in keys):return []
    return [r for r in data if r.get('verified') is True and r.get('level')==query['level'] and r.get('id')!=query.get('id') and all(r.get(k)==query[k] for k in keys) and number(r.get(amount)) is not None and number(r[amount])>0]

def main():
    p=argparse.ArgumentParser();sp=p.add_subparsers(dest='command',required=True)
    for name,fields in [('ledger',('url','out')),('attachments',('src','out')),('compare',('src','query','out')),('ocr',('src','out'))]:
        q=sp.add_parser(name)
        for f in fields:q.add_argument(f)
        if name=='attachments':q.add_argument('--workers',type=int,choices=range(1,9),default=2)
    a=p.parse_args()
    if a.command=='ledger':ledger(a.url,a.out)
    elif a.command=='attachments':attachments(a.src,a.out,a.workers)
    elif a.command=='compare':write(a.out,compare(json.loads(Path(a.src).read_text()),json.loads(Path(a.query).read_text())))
    else:
        from ocr import run
        run(Path(a.src),Path(a.out))
if __name__=='__main__':main()
