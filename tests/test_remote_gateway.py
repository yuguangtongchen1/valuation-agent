import asyncio,hashlib,io,json,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import patch
from valuation_agent.server import Gateway,parse_json,safe_reference
from valuation_agent.remote import remote_call

class GatewaySecurity(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'principals.json';self.token='vag_'+('x'*48)
  self.path.write_text(json.dumps({'principals':[{'id':'internal-one','token_sha256':hashlib.sha256(self.token.encode()).hexdigest(),'scopes':['search','compare','contract'],'expires_at':time.time()+1000}]}))
  wb=types.SimpleNamespace(reference_pool=lambda r:r,pending_price_index=lambda r:{},source_name_index=lambda r:{})
  loaded=({'workbench':wb,'valuation':types.SimpleNamespace()},Path(self.temp.name),[],{},set(),set(),None,{'records':0})
  self.app=Gateway(self.temp.name,self.path,loader=lambda **kw:loaded)
 def tearDown(self):self.app.executor.shutdown(wait=True);self.temp.cleanup()
 def request(self,path='/v1/search',payload=b'{"phrase":"test"}',headers=None,query=b'',method='POST'):
  messages=[];events=[{'type':'http.request','body':payload,'more_body':False}]
  async def receive():return events.pop(0)
  async def send(event):messages.append(event)
  asyncio.run(self.app({'type':'http','path':path,'method':method,'headers':headers if headers is not None else[(b'authorization',('Bearer '+self.token).encode())],'query_string':query},receive,send))
  return messages[0]['status'],json.loads(messages[-1]['body'])
 def test_no_credentials_or_revocation_deny_before_engine(self):
  self.assertEqual(self.request(headers=[])[0],401)
  d=json.loads(self.path.read_text());d['principals'][0]['revoked']=True;self.path.write_text(json.dumps(d));self.assertEqual(self.request()[0],401)
 def test_duplicate_authorization_expired_or_wrong_scope_rejected(self):
  h=(b'authorization',('Bearer '+self.token).encode());self.assertEqual(self.request(headers=[h,h])[0],401)
  d=json.loads(self.path.read_text());d['principals'][0]['scopes']=[];self.path.write_text(json.dumps(d));self.assertEqual(self.request()[0],403)
  d['principals'][0]['expires_at']=0;self.path.write_text(json.dumps(d));self.assertEqual(self.request()[0],401)
 def test_fail_closed_missing_credentials_and_unknown_paths(self):
  self.path.unlink();self.assertEqual(self.request()[0],401)
  for p in ['/data/ledger.json','/v1/../data','/v1/keys','/v1/search/']:
   self.assertEqual(self.request(path=p)[0],404)
 def test_payload_limits_and_busy(self):
  self.assertEqual(self.request(payload=b'x'*(384*1024+1))[0],413)
  self.assertEqual(self.request(payload=b'{bad')[0],400)
  self.app.busy=True;self.assertEqual(self.request()[0],503)
 def test_rate_limits_and_no_private_fields_in_response(self):
  self.app.dispatch=lambda *args:{'references':[safe_reference({'item_name':'device','source_original_fields':{'secret':'x'},'source_attributes':{'contact':'x'},'unit_price_cny_yuan':'100'})]}
  code,body=self.request();self.assertEqual(code,200);self.assertNotIn('source_original_fields',str(body));self.assertNotIn('contact',str(body))
  for _ in range(29):self.request()
  self.assertEqual(self.request()[0],429)
 def test_invalid_json_and_large_quote(self):
  for raw in [b'{"x":1,"x":2}',b'{"x":NaN}']:
   with self.assertRaises(ValueError):parse_json(raw)
  with self.assertRaises(ValueError):self.app.dispatch('compare',{'document':{'rows':[{}]*51}})
 def test_health_does_not_expose_data_or_accounts(self):
  code,body=self.request(path='/health',method='GET',headers=[]);self.assertEqual(code,200);self.assertEqual(set(body),{'status','version'})
 def test_contract_resolves_original_for_each_attachment(self):
  from valuation_agent.engine import modules
  self.app.engine['workbench'].original_document_url=modules()['workbench'].original_document_url
  self.app.engine['valuation']=types.SimpleNamespace(reference=lambda r,e:dict(r),rejection=lambda *a:None,is_checked=lambda r:True)
  a,b='A'*20,'B'*20
  self.app.ledger={'r':{'attachments':[{'token':a,'type':'file'},{'token':b,'type':'docx'}]}}
  self.app.rows=[{'record_id':'r','source_token':t,'source_attributes':{'private':'hidden'}} for t in (a,b,'unknown')]
  code,body=self.request('/v1/contract',json.dumps({'record_id':'r'}).encode())
  self.assertEqual(code,200)
  self.assertTrue(body['lines'][0]['source_url'].endswith('/file/'+a))
  self.assertTrue(body['lines'][1]['source_url'].endswith('/docx/'+b))
  self.assertIsNone(body['lines'][2]['source_url'])
  self.assertNotIn('source_attributes',str(body))
 def test_contract_can_read_exact_shared_attachment_without_copying_rows(self):
  from valuation_agent.engine import modules
  self.app.engine['workbench'].original_document_url=modules()['workbench'].original_document_url
  self.app.engine['valuation']=types.SimpleNamespace(reference=lambda r,e:dict(r),rejection=lambda *a:None,is_checked=lambda r:True)
  token='A'*20
  self.app.ledger={'requested':{'attachments':[{'token':token,'type':'file'}]}}
  self.app.rows=[{'record_id':'original','line_id':'line1','source_token':token,'item_name':'人物骨骼绑定'},
                 {'record_id':'other','line_id':'line2','source_token':'B'*20,'item_name':'无关服务'}]
  result=self.app.dispatch('contract',{'record_id':'requested'})
  self.assertEqual(len(result['lines']),1)
  self.assertEqual(result['lines'][0]['record_id'],'original')
  self.assertEqual(result['lines'][0]['item_name'],'人物骨骼绑定')
  self.assertEqual(len(self.app.rows),2)
 def test_source_readability_does_not_remove_price_exclusion(self):
  from valuation_agent.engine import modules
  engine=modules()
  row={'kind':'bom_line','record_id':'r','line_id':'pending',
       'item_name':'现场保驾服务','currency':'HKD','subtotal':'23520',
       'source_fields_reviewed':True,'record_status':'line_fields_verified_price_scope_pending',
       'exclude_from_procurement_price_comparison':True}
  public=safe_reference(engine['valuation'].reference(row,None))
  self.assertTrue(public['source_fields_reviewed'])
  self.assertTrue(public['exclude_from_procurement_price_comparison'])
  self.assertEqual(engine['workbench'].reference_pool([row]),[])
 def test_nested_source_exclusion_blocks_audited_zero_quantity(self):
  from valuation_agent.engine import modules
  wb=modules()['workbench']
  row={'kind':'bom_line','item_name':'门头收银台亚克力灯管',
       'source_fields_reviewed':True,'unit':'m','unit_price':'350',
       'quantity':'0','subtotal':'0',
       'source_attributes':{'comparison_eligible':False}}
  self.assertEqual(wb.reference_pool([row]),[])
  row['quantity']='11.5';row['subtotal']='4025'
  self.assertEqual(wb.reference_pool([row]),[])
  row['source_attributes']['comparison_eligible']=True
  self.assertEqual(wb.reference_pool([row]),[row])
 def test_client_rejects_http_and_insecure_config(self):
  p=Path(self.temp.name)/'client.json';p.write_text(json.dumps({'endpoint':'http://example.com','token':self.token}));p.chmod(0o600)
  with self.assertRaisesRegex(ValueError,'HTTPS'):remote_call('search',{},p)
  p.chmod(0o644)
  with self.assertRaisesRegex(ValueError,'权限'):remote_call('search',{},p)

class RemoteProvenanceTests(unittest.TestCase):
 def test_gateway_excludes_current_family_and_superseded_rows(self):
  from types import SimpleNamespace
  from unittest.mock import Mock
  rows=[{'record_id':'self','source_token':'file-a'},
        {'record_id':'variant','source_token':'file-a','quotation_family_id':'family'},
        {'record_id':'old','quotation_family_id':'family'},
        {'record_id':'inactive','is_current_version':False},
        {'record_id':'other','source_token':'file-b'}]
  seen=[]
  wb=SimpleNamespace(reference_pool=lambda r:r,pending_price_index=lambda r:{},source_name_index=lambda r:{},
       lookup=lambda root,pool,*a,**kw:seen.extend(pool) or {'references':[]})
  with tempfile.TemporaryDirectory() as tmp:
   loaded=({'workbench':wb,'valuation':SimpleNamespace()},Path(tmp),rows,{r['record_id']:{} for r in rows},set(),set(),None,{})
   app=Gateway(tmp,Path(tmp)/'unused',loader=lambda **kw:loaded)
   try:result=app.dispatch('compare',{'document':{'rows':[{'item_name':'测试'}],'exclusion_sources':[{'source_token':'file-a'}]}})
   finally:app.executor.shutdown(wait=True)
  self.assertEqual([r['record_id'] for r in seen],['other'])
  self.assertEqual(result['retrieval_corpus'],dict(historical_rows=5,same_source_rows=3,other_inactive_version_rows=1,retained_rows=1,eligible_price_rows=1,other_retained_rows=0))

 def test_client_preserves_cross_batch_source_identity(self):
  from valuation_agent.cli import remote_compare
  captured=[]
  def call(action,payload,config):
   captured.append(payload['document']);return {'rows':[{'quote':r,'references':[]} for r in payload['document']['rows']]}
  document={'rows':[{'item_name':'测试','brand':'品牌甲','source_token':f'file-{i}'} for i in range(21)]}
  with patch('valuation_agent.remote.remote_call',side_effect=call):remote_compare(document,'unused')
  self.assertEqual(len(captured),2)
  for d in captured:
   self.assertEqual(len(d['exclusion_sources']),21)
   self.assertTrue(all(r['brand']=='品牌甲' for r in d['rows']))

 def test_gateway_preserves_brand_for_engine_conflict_check(self):
  from types import SimpleNamespace
  queries=[]
  def lookup(root,pool,ledger,duplicates,shared,query,*a,**kw):
   queries.append(query)
   return {'references':[]}
  wb=SimpleNamespace(reference_pool=lambda r:r,pending_price_index=lambda r:{},source_name_index=lambda r:{},lookup=lookup)
  with tempfile.TemporaryDirectory() as tmp:
   loaded=({'workbench':wb,'valuation':SimpleNamespace()},Path(tmp),[],{},set(),set(),None,{})
   app=Gateway(tmp,Path(tmp)/'unused',loader=lambda **kw:loaded)
   try:
    result=app.dispatch('compare',{'document':{'rows':[{'item_name':'投影机','model':'X100','brand':'品牌甲'}]}})
   finally:app.executor.shutdown(wait=True)
  self.assertEqual(queries[0]['brand'],'品牌甲')
  self.assertEqual(result['rows'][0]['quote']['brand'],'品牌甲')
