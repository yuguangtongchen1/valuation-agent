import base64,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from http.server import HTTPServer
from valuation_agent.activation import parse_access_code,activate
from valuation_agent.browser_app import make_handler

class BrowserDeliveryTests(unittest.TestCase):
 def test_activation_preserves_existing_on_failure(self):
  code='VA1.'+base64.urlsafe_b64encode(json.dumps({'endpoint':'https://example.org/api','token':'a'*48}).encode()).decode().rstrip('=')
  self.assertEqual(parse_access_code(code)['endpoint'],'https://example.org/api')
  with tempfile.TemporaryDirectory()as tmp:
   path=Path(tmp)/'remote.json';path.write_text('original')
   with patch('valuation_agent.remote.remote_call',side_effect=ValueError('no')):
    with self.assertRaises(ValueError):activate(code,path)
   self.assertEqual(path.read_text(),'original')
   with patch('valuation_agent.remote.remote_call',return_value={}):activate(code,path)
   self.assertEqual(path.stat().st_mode&0o777,0o600)
  with self.assertRaises(ValueError):parse_access_code('VA1.e30')
 def test_original_workbench_remote_adapter_and_cache(self):
  with tempfile.TemporaryDirectory()as tmp:
   cfg=Path(tmp)/'remote.json';cfg.write_text('{}')
   server=HTTPServer(('127.0.0.1',0),make_handler(cfg,'session-test'))
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
   try:
    page=urllib.request.urlopen(url).read().decode();self.assertIn('<div id="root"></div>',page);self.assertIn('X-Workbench-Session',page)
    payload={'name':'地台','spec':'钢木结构','unit':'平米','quantity':'5','exclude':'self-record'}
    mocked={'rows':[{'quote':{'item_name':'地台'},'references':[{'record_id':'self-record'},{'record_id':'other','signed_date':'2025/1/1','unit_price':'30'}]}]}
    with patch('valuation_agent.browser_app.remote_compare',return_value=mocked)as compare:
     for _ in range(2):
      req=urllib.request.Request(url+'/api/valuation/lookup',data=json.dumps(payload).encode(),headers={'X-Workbench-Session':'session-test','Content-Type':'application/json'})
      out=json.load(urllib.request.urlopen(req));self.assertEqual(len(out['references']),1);self.assertEqual(out['references'][0]['sheet'],'2025')
     self.assertEqual(compare.call_count,1);self.assertEqual(compare.call_args[0][0]['rows'][0]['item_name'],'地台')
     self.assertEqual(compare.call_args[0][0]['rows'][0]['spec'],'钢木结构')
   finally:server.shutdown();server.server_close()
 def test_local_origin_session_and_ui_assets(self):
  with tempfile.TemporaryDirectory()as tmp:
   server=HTTPServer(('127.0.0.1',0),make_handler(Path(tmp)/'remote.json','session-test'))
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
   try:
    page=urllib.request.urlopen(url).read().decode();self.assertIn('session-test',page);self.assertNotIn('__SESSION__',page)
    self.assertFalse(json.load(urllib.request.urlopen(url+'/health'))['configured'])
    req=urllib.request.Request(url+'/api/import',data=b'{}',headers={'Origin':'https://evil.example','X-Workbench-Session':'session-test'})
    with self.assertRaises(urllib.error.HTTPError)as e:urllib.request.urlopen(req)
    self.assertEqual(e.exception.code,403)
    req=urllib.request.Request(url+'/api/import',data=b'{}')
    with self.assertRaises(urllib.error.HTTPError)as e:urllib.request.urlopen(req)
    self.assertEqual(e.exception.code,403)
    for path in ['/remote.json','/../activation.py']:
     with self.assertRaises(urllib.error.HTTPError)as e:urllib.request.urlopen(url+path)
     self.assertEqual(e.exception.code,404)
   finally:server.shutdown();server.server_close()
