"""Local browser UI proxies authorized queries; no historical database on disk."""
import argparse,base64,io,json,secrets,tempfile,threading,webbrowser,mimetypes,copy,subprocess
from urllib.parse import unquote,parse_qs
from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
from .activation import activate,default_config
from .remote import remote_call
from .io import read_input
from .cli import remote_compare
from .excel_export import export_comparison

MAX_BODY=32*1024*1024

def make_handler(config,session_key,input_path=None,worksheet=None):
    config=Path(config)
    assets=Path(__file__).with_name('web');cache={}
    handoff_state = {}
    def handoff():
        if input_path is None:return {'revision':None}
        source=Path(input_path)
        stamp=(source.stat().st_mtime_ns,source.stat().st_size)
        if handoff_state.get('stamp')!=stamp:
            document=read_input(source,worksheet)
            if not document.get('rows'):raise ValueError('报价文件没有可展示的明细。')
            for row in document['rows']:
                row.setdefault('currency','CNY')
            revision=secrets.token_hex(12)
            handoff_state.update(stamp=stamp,revision=revision,document=document)
            cache.clear()
        if not config.is_file():raise ValueError('请先激活工作台。')
        return {'revision':handoff_state['revision'],'document':handoff_state['document'],'filename':source.name}
    def query_row(query):
        return {'item_name':str(query.get('name')or query.get('item_name')or ''),**{k:v for k,v in query.items()if k in ('quantity','unit','currency','model','spec','configuration','dimension_unit','description')}}
    def enrich(found):
        for row in found.get('references',[]):
            row.setdefault('sheet',str(row.get('signed_date')or '')[:4])
        return found
    def lookups(queries):
        if not isinstance(queries,list)or not 1<=len(queries)<=1000 or not all(isinstance(q,dict)for q in queries):raise ValueError('报价格式无法处理。')
        keys=[json.dumps(q,sort_keys=True,ensure_ascii=False)for q in queries]
        missing=list(dict.fromkeys(k for k in keys if k not in cache))
        if missing:
            doc={'rows':[query_row(json.loads(k))for k in missing]}
            compared=remote_compare(doc,config)
            if len(compared['rows'])!=len(missing):raise ValueError('比价结果行数不一致。')
            for key,item in zip(missing,compared['rows']):
                item=copy.deepcopy(item);query=json.loads(key)
                item['references']=[r for r in item.get('references',[])if not query.get('exclude')or r.get('record_id')!=query['exclude']]
                cache[key]=enrich(item)
        output=[copy.deepcopy(cache[k])for k in keys]
        if len(cache)>1500:cache.clear()
        return output
    def original_api(action,query):
        if action=='handoff':return handoff()
        if action in ('lookup','batch'):
            results=lookups(query if action=='batch'else[query]);return results if action=='batch'else results[0]
        if action=='contract':
            result=remote_call('contract',{'record_id':query.get('exclude')},config)
            for row in result['lines']:row.setdefault('sheet',str(row.get('signed_date')or '')[:4])
            return result
        if action=='demo':
            result=remote_call('search',{'phrase':'数字内容','limit':3},config)
            return result.get('references',[])
        if action == 'oa':
            from .engine import modules
            link = query.get('link')
            worksheet = query.get('worksheet', '')
            if not isinstance(link, str) or len(link) > 1200 or not isinstance(worksheet, str) or len(worksheet) > 120:
                raise ValueError('请检查飞书链接和工作表名称。')
            try:
                return modules()['workbench'].oa_file(link, worksheet)
            except FileNotFoundError as exc:
                raise ValueError('缺少飞书读取依赖。请让 Codex 运行 valuation-agent feishu-setup 自动检测并安装飞书 CLI，然后完成飞书授权并重启工作台。') from exc
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                raise ValueError('飞书读取未成功。请让 Codex 运行 lark-cli auth status --json --verify 检查授权；授权正常则核对当前账号的文件权限及读取错误。估价访问码不包含飞书权限。也可下载 Excel 后上传。') from exc
        raise ValueError('未知操作。')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def allowed(self):
            host=f'127.0.0.1:{self.server.server_port}'
            return self.headers.get('Host')==host and self.headers.get('Origin',f'http://{host}')==f'http://{host}'
        def respond(self,status,body,kind='application/json; charset=utf-8'):
            raw=body if isinstance(body,bytes)else json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if not self.allowed():return self.respond(403,{'error':'仅允许本机访问。'})
            path=urlsplit(self.path).path
            if path in ('/','/index.html'):
                template=assets/('index.html'if config.is_file()else'activation.html')
                html=template.read_text(encoding='utf-8').replace('__SESSION__',session_key)
                if config.is_file():
                    bridge="<script>window.fetch=((original)=>function(input,options){const url=new URL(typeof input==='string'?input:input.url,location.href);if(url.origin===location.origin&&url.pathname.startsWith('/api/')){options={...options,headers:new Headers(options?.headers)};options.headers.set('X-Workbench-Session',%s);}return original(input,options);})(window.fetch.bind(window));</script>"%json.dumps(session_key)
                    html=html.replace('<head>','<head>'+bridge,1)
                return self.respond(200,html.encode(),'text/html; charset=utf-8')
            decoded=unquote(path)
            if decoded.startswith('/assets/')or decoded=='/报价单示例.xlsx':
                target=(assets/decoded.lstrip('/')).resolve()
                if target.is_relative_to(assets.resolve())and target.is_file():return self.respond(200,target.read_bytes(),mimetypes.guess_type(target.name)[0]or'application/octet-stream')
            if path.startswith('/api/valuation/'):
                if self.headers.get('X-Workbench-Session')!=session_key:return self.respond(403,{'error':'请从本机工作台重新打开。'})
                try:
                    query={k:v[0]for k,v in parse_qs(urlsplit(self.path).query).items()}
                    return self.respond(200,original_api(path.rsplit('/',1)[1],query))
                except (OSError,ValueError,KeyError,TypeError)as exc:return self.respond(400,{'error':str(exc)})
            if path=='/health':return self.respond(200,{'status':'ok','configured':config.is_file()})
            return self.respond(404,{'error':'未找到文件。'})
        def do_POST(self):
            if not self.allowed()or self.headers.get('X-Workbench-Session')!=session_key:return self.respond(403,{'error':'请从本机工作台重新打开。'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_BODY:return self.respond(413,{'error':'文件过大，请拆分。'})
                raw=self.rfile.read(length);action=urlsplit(self.path).path
                if action=='/api/valuation/legacy-xls':
                    from .engine import modules
                    return self.respond(200,modules()['legacy'].legacy_xls_document(raw))
                obj=json.loads(raw)
                if action.startswith('/api/valuation/'):
                    return self.respond(200,original_api(action.rsplit('/',1)[1],obj))
                if not isinstance(obj,dict):raise ValueError('请求格式无效。')
                if action=='/api/activate':
                    activate(obj.get('code'),config);return self.respond(200,{'ok':True})
                if action=='/api/import':
                    suffix=Path(str(obj.get('filename',''))).suffix.lower()
                    if suffix not in ('.xlsx','.xls','.csv','.json'):raise ValueError('请上传 Excel、CSV 或 JSON。')
                    raw=base64.b64decode(obj.get('content',''),validate=True)
                    with tempfile.TemporaryDirectory(prefix='valuation-import-')as tmp:
                        path=Path(tmp)/('报价'+suffix);path.write_bytes(raw)
                        if suffix=='.xlsx' and not obj.get('worksheet'):
                            from openpyxl import load_workbook
                            book=load_workbook(path,read_only=True,data_only=True)
                            sheets=book.sheetnames;book.close()
                            if len(sheets)>1:return self.respond(200,{'worksheets':sheets})
                        if suffix=='.xls'and not obj.get('worksheet'):
                            from .engine import modules
                            sheets=[s['name']for s in modules()['legacy'].legacy_xls_document(raw)['sheets']]
                            if len(sheets)>1:return self.respond(200,{'worksheets':sheets})
                        doc=read_input(path,obj.get('worksheet'))
                        for row in doc['rows']:
                            if not row.get('currency'):row['currency']='CNY'
                        return self.respond(200,{'document':doc})
                if action=='/api/compare':return self.respond(200,remote_compare(obj['document'],config))
                if action=='/api/contract':return self.respond(200,remote_call('contract',{'record_id':obj['record_id']},config))
                if action=='/api/export':
                    with tempfile.TemporaryDirectory(prefix='valuation-export-')as tmp:
                        path=Path(tmp)/'比价结果.xlsx';export_comparison(obj['result'],path);raw=path.read_bytes()
                    return self.respond(200,raw,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                return self.respond(404,{'error':'未知操作。'})
            except (OSError,ValueError,KeyError,TypeError)as exc:
                # Never echo submitted activation data or low-level network headers.
                message='访问码激活失败，请核对访问码和网络。'if urlsplit(self.path).path=='/api/activate'else str(exc)
                return self.respond(400,{'error':message})
            except Exception:return self.respond(500,{'error':'处理失败，请检查文件格式或稍后重试。'})
    return Handler

def launch(config=None,port=0,no_browser=False,input_path=None,worksheet=None):
    handler=make_handler(config or default_config(),secrets.token_urlsafe(32),input_path,worksheet)
    server=HTTPServer(('127.0.0.1',port),handler)
    url=f'http://127.0.0.1:{server.server_port}/'+('?handoff=1' if input_path else '')
    print('估价工作台已启动：'+url+'\n请保持此进程运行；关闭请按 Ctrl+C。',flush=True)
    if not no_browser:threading.Timer(0.5,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
