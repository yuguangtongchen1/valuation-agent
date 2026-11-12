"""Read-only, fail-closed ASGI gateway. Run behind HTTPS on loopback only."""
import asyncio,collections,hashlib,hmac,json,logging,os,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import __version__,service

REF_FIELDS=set('kind item_name spec model brand description unit quantity unit_price subtotal currency project project_key record_id contract_id line_id supplier owner signed_date source_locator source_name source_token record_status source_review_kind match_kind match_reason differences spec_differences parameters classification comparison_role price_comparison_eligible reference_price_type reference_total reference_total_cny_yuan unit_price_cny_yuan subtotal_cny_yuan ledger_amount_cny_tax_inclusive reference_rate_basis reference_rate_label reference_rate_unit reference_billing_multiplier reference_billing_multiplier_label component_name component_quantity component_unit quotation_variant_id quotation_variant_name independent_sample_key period billing_period'.split())
def safe_reference(row):return {key:value for key,value in row.items() if key in REF_FIELDS}
def parse_json(raw):
    def unique(pairs):
        obj={}
        for key,value in pairs:
            if key in obj:raise ValueError('Duplicate JSON key')
            obj[key]=value
        return obj
    def invalid(value):raise ValueError('Nonfinite JSON')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=invalid)

class Gateway:
    def __init__(self,data,credentials,loader=service.load_history):
        self.data=Path(data);self.credentials=Path(credentials);self.loaded=loader(data=self.data)
        self.executor=ThreadPoolExecutor(max_workers=1);self.busy=False;self.limits={}
        engine,root,rows,ledger,duplicates,shared,catalog,meta=self.loaded
        self.engine=engine;self.root=root;self.rows=rows;self.ledger=ledger;self.duplicates=duplicates;self.shared=shared;self.catalog=catalog;self.meta=meta
        wb=engine['workbench'];self.pool=wb.reference_pool(rows);self.pending=wb.pending_price_index(rows);self.names=wb.source_name_index(rows)
    def authenticate(self,headers,action):
        values=[v for k,v in headers if k.lower()==b'authorization']
        if len(values)!=1 or not values[0].startswith(b'Bearer ') or len(values[0])>256:return None,401
        digest=hashlib.sha256(values[0][7:]).hexdigest()
        try:records=json.loads(self.credentials.read_text()).get('principals',[])
        except (OSError,ValueError):return None,401
        now=time.time()
        for record in records[:200]:
            if hmac.compare_digest(digest,str(record.get('token_sha256',''))):
                if record.get('revoked') or record.get('expires_at',0)<=now:return None,401
                if action not in record.get('scopes',[]):return None,403
                key=str(record['id']);events=self.limits.setdefault(key,collections.deque())
                while events and events[0]<=now-60:events.popleft()
                if len(events)>=30:return None,429
                events.append(now);return key,200
        return None,401
    def dispatch(self,action,payload):
        wb=self.engine['workbench'];valuation=self.engine['valuation']
        if not isinstance(payload,dict):raise ValueError('Expected object')
        if action=='search':
            phrase=payload.get('phrase');limit=payload.get('limit',6)
            if not isinstance(phrase,str) or not 1<=len(phrase.strip())<=120 or type(limit)!=int or not 1<=limit<=10:raise ValueError('Invalid search')
            found=wb.lookup(self.root,self.pool,self.ledger,self.duplicates,self.shared,{'name':phrase,'currency':'CNY'},False,pending=self.pending,catalog=self.catalog,source_names=self.names)
            found['references']=[safe_reference(r)for r in found['references'][:limit]]
            return {'schema_version':1,'history':self.meta,**found}
        if action=='contract':
            rid=payload.get('record_id')
            if not isinstance(rid,str)or rid not in self.ledger:raise ValueError('Unknown record')
            return {'record_id':rid,'lines':[safe_reference(valuation.reference(r,valuation.rejection(r,self.duplicates,self.shared)))for r in self.rows if r['record_id']==rid and (valuation.is_checked(r)or r.get('source_fields_reviewed'))]}
        document=payload.get('document');rows=document.get('rows')if isinstance(document,dict)else None
        if not isinstance(rows,list)or not 1<=len(rows)<=50:raise ValueError('One to fifty rows required')
        from .source_identity import exclude_current_sources
        identity_fields=('source_url','source_token','source_sha256','quotation_family_id','economic_purchase_group','record_id')
        extra=document.get('exclusion_sources',[])
        if not isinstance(extra,list) or len(extra)>1001:raise ValueError('Invalid source identities')
        identities=[]
        for item in [document]+rows+extra:
            if not isinstance(item,dict):raise ValueError('Invalid source identity')
            ident={k:item[k] for k in identity_fields if k in item}
            if any(not isinstance(v,str) or len(v)>6000 for v in ident.values()):raise ValueError('Invalid source identity')
            identities.append(ident)
        retained=exclude_current_sources(self.rows,{'rows':identities})
        pool=wb.reference_pool(retained)
        pending=wb.pending_price_index(retained)
        names=wb.source_name_index(retained)
        retained_ids={r.get('record_id') for r in retained}
        ledger={k:v for k,v in self.ledger.items() if k in retained_ids}
        output=[]
        for row in rows:
            if not isinstance(row,dict)or not isinstance(row.get('item_name'),str)or not 1<=len(row['item_name'].strip())<=120:raise ValueError('Invalid item name')
            allowed=('item_name','spec','model','description','configuration','quantity','unit','currency','dimension_unit','row_id','source_locator','unit_price','subtotal')
            clean={k:row[k]for k in allowed if k in row}
            if any(not isinstance(v,(str,int,float,type(None)))or isinstance(v,bool)or len(str(v))>6000 for v in clean.values()):raise ValueError('Invalid field')
            query={**clean,'name':clean['item_name'],'currency':str(clean.get('currency')or'CNY').upper()}
            found=wb.lookup(self.root,pool,ledger,self.duplicates,self.shared,query,False,pending=pending,catalog=self.catalog,source_names=names)
            found['references']=[safe_reference(r)for r in found['references']]
            output.append({'quote':clean,**found})
        return {'schema_version':1,'project':str(document.get('project',''))[:200],'history':self.meta,'rows':output}
    async def __call__(self,scope,receive,send):
        if scope['type']=='lifespan':
            while True:
                event=await receive()
                if event['type']=='lifespan.startup':await send({'type':'lifespan.startup.complete'})
                elif event['type']=='lifespan.shutdown':self.executor.shutdown(wait=False);await send({'type':'lifespan.shutdown.complete'});return
            return
        if scope['type']!='http':return
        async def reply(code,body):
            raw=json.dumps(body,ensure_ascii=False,allow_nan=False,default=str).encode()
            await send({'type':'http.response.start','status':code,'headers':[(b'content-type',b'application/json; charset=utf-8'),(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff')]})
            await send({'type':'http.response.body','body':raw})
        if scope['path']=='/health'and scope['method']=='GET':return await reply(200,{'status':'ok','version':__version__})
        action=scope['path'].removeprefix('/v1/')
        if scope['method']!='POST'or action not in ('search','compare','contract')or scope['query_string']:return await reply(404,{'error':'Not found'})
        principal,status=self.authenticate(scope['headers'],action)
        if status!=200:return await reply(status,{'error':'Unauthorized'if status==401 else'Forbidden'if status==403 else'Too many requests'})
        if self.busy:return await reply(503,{'error':'Service busy'})
        body=bytearray()
        while True:
            event=await receive()
            if event['type']=='http.disconnect':return
            body.extend(event.get('body',b''))
            if len(body)>384*1024:return await reply(413,{'error':'Request too large'})
            if not event.get('more_body'):break
        try:payload=parse_json(body)
        except (ValueError,UnicodeError):return await reply(400,{'error':'Invalid JSON'})
        if self.busy:return await reply(503,{'error':'Service busy'})
        self.busy=True;started=time.monotonic()
        try:
            result=await asyncio.get_running_loop().run_in_executor(self.executor,self.dispatch,action,payload)
            await reply(200,result)
            logging.info('valuation principal=%s action=%s elapsed=%.3f',principal,action,time.monotonic()-started)
        except (ValueError,KeyError,TypeError):await reply(400,{'error':'Invalid quotation or record'})
        except Exception:logging.error('valuation action failed');await reply(500,{'error':'Internal service error'})
        finally:self.busy=False

def create_app():
    from .runtime_snapshot import load_snapshot
    return Gateway(os.environ['VALUATION_AGENT_DATA'],os.environ['VALUATION_AGENT_CREDENTIALS'],loader=load_snapshot)
