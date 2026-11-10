"""Loopback-only browser workbench for the separately supplied internal dataset."""
import argparse,json,threading,webbrowser
from http.server import HTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
from .runtime_snapshot import load_snapshot


def make_handler(data,web):
    engine,root,rows,ledger,duplicates,shared,catalog,meta=load_snapshot(data)
    wb=engine['workbench'];val=engine['valuation']
    pool=wb.reference_pool(rows);pending=wb.pending_price_index(rows);names=wb.source_name_index(rows)
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self,*a,**kw):super().__init__(*a,directory=str(web),**kw)
        def log_message(self,*args):pass
        def end_headers(self):
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');super().end_headers()
        def json(self,value,status=200):
            raw=json.dumps(value,ensure_ascii=False,default=str,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def allowed(self):
            host=f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host')==host and self.headers.get('Origin',f'http://{host}')==f'http://{host}'
        def do_GET(self):
            if not self.allowed():return self.json({'error':'只允许本机访问'},403)
            parsed=urlsplit(self.path)
            if parsed.path.startswith('/api/valuation/'):return self.api(parsed.path.rsplit('/',1)[1],{k:v[0]for k,v in parse_qs(parsed.query).items()})
            decoded=unquote(parsed.path)
            target=(Path(web)/decoded.lstrip('/')).resolve()
            if decoded not in ('/','/index.html','/报价单示例.xlsx') and not (decoded.startswith('/assets/') and target.is_relative_to(Path(web).resolve())):return self.json({'error':'未找到文件'},404)
            return super().do_GET()
        def do_POST(self):
            if not self.allowed():return self.json({'error':'只允许本机访问'},403)
            action=urlsplit(self.path).path.removeprefix('/api/valuation/')
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>30*1024*1024:return self.json({'error':'文件或请求过大'},413)
                raw=self.rfile.read(size)
                if action=='legacy-xls':
                    from legacy_xls import legacy_xls_document
                    return self.json(legacy_xls_document(raw))
                if size>2*1024*1024:return self.json({'error':'请求过大'},413)
                return self.api(action,json.loads(raw))
            except (ValueError,KeyError,TypeError):return self.json({'error':'无法读取文件或请求内容'},400)
        def api(self,action,query):
            try:
                if action=='demo':
                    output=[val.reference(r,val.rejection(r,duplicates,shared))for name in wb.DEMO_NAMES if(r:=next((r for r in pool if val.is_checked(r)and r['item_name']==name and r.get('quantity')is not None and r['currency']=='CNY'),None))]
                elif action=='contract':output={'lines':[val.reference(r,val.rejection(r,duplicates,shared))for r in rows if r['record_id']==query.get('exclude')and(val.is_checked(r)or r.get('source_fields_reviewed'))]}
                elif action in ('lookup','batch'):
                    queries=query if action=='batch'else[query]
                    if not isinstance(queries,list)or len(queries)>1000 or not all(isinstance(q,dict)for q in queries):raise ValueError()
                    output=[wb.lookup(root,pool,ledger,duplicates,shared,q,False,pending,catalog,names)for q in queries]
                    if action=='lookup':output=output[0]
                elif action=='oa':return self.json({'error':'此离线版不含飞书登录凭据。请先从飞书下载 Excel，再上传本地文件。'},400)
                else:return self.json({'error':'未知操作'},404)
                return self.json(output)
            except (ValueError,KeyError,TypeError):return self.json({'error':'请求内容无法处理'},400)
    return Handler


def main(argv=None):
    p=argparse.ArgumentParser(description='启动本机采购比价网页');p.add_argument('--data',type=Path,required=True);p.add_argument('--web',type=Path,required=True);p.add_argument('--port',type=int,default=5183);p.add_argument('--no-browser',action='store_true');a=p.parse_args(argv)
    handler=make_handler(a.data,a.web)
    try:server=HTTPServer(('127.0.0.1',a.port),handler)
    except OSError:server=HTTPServer(('127.0.0.1',0),handler)
    url=f'http://127.0.0.1:{server.server_port}/';print('网页已启动：'+url,flush=True)
    if not a.no_browser:threading.Timer(0.6,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
