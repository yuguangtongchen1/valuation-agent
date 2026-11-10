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
 def test_client_rejects_http_and_insecure_config(self):
  p=Path(self.temp.name)/'client.json';p.write_text(json.dumps({'endpoint':'http://example.com','token':self.token}));p.chmod(0o600)
  with self.assertRaisesRegex(ValueError,'HTTPS'):remote_call('search',{},p)
  p.chmod(0o644)
  with self.assertRaisesRegex(ValueError,'权限'):remote_call('search',{},p)
