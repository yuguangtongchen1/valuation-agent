import json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from http.server import HTTPServer
from valuation_agent.browser_app import make_handler
class SyncTest(unittest.TestCase):
 def test_sync_revision_and_access(self):
  with tempfile.TemporaryDirectory() as tmp:
   src=Path(tmp)/'quote.json';cfg=Path(tmp)/'remote.json';cfg.write_text('{}')
   def write(name):src.write_text(json.dumps({'project':'联动测试','rows':[{'item_name':name,'quantity':2,'unit':'套','unit_price':100,'subtotal':200}]}))
   write('数字内容');server=HTTPServer(('127.0.0.1',0),make_handler(cfg,'test',src));threading.Thread(target=server.serve_forever,daemon=True).start()
   url=f'http://127.0.0.1:{server.server_port}/api/valuation/handoff'
   def get():return json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'X-Workbench-Session':'test'})))
   try:
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url)
    self.assertEqual(e.exception.code,403)
    first=get();self.assertEqual(first['revision'],get()['revision']);self.assertEqual(first['document']['rows'][0]['subtotal'],'200')
    write('数字内容修订');second=get();self.assertNotEqual(first['revision'],second['revision']);self.assertEqual(second['document']['rows'][0]['item_name'],'数字内容修订')
    src.write_text('{bad')
    with self.assertRaises(urllib.error.HTTPError):get()
   finally:server.shutdown();server.server_close()
if __name__=='__main__':unittest.main()
