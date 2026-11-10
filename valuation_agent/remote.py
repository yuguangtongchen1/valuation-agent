"""Authenticated remote queries; credentials stay in a user-owned local file."""
import json,os,stat
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('远程接口不允许重定向，请核对服务器地址。')

def remote_call(action,payload,config=None):
    path=Path(config or os.environ.get('VALUATION_AGENT_REMOTE_CONFIG') or Path.home()/'.config/valuation-agent/remote.json').expanduser()
    if os.name!='nt' and stat.S_IMODE(path.stat().st_mode)&0o077:
        raise ValueError('访问配置权限过宽，请执行 chmod 600 后重试。')
    settings=json.loads(path.read_text());endpoint=settings.get('endpoint','').rstrip('/')
    target=urlparse(endpoint)
    if target.scheme!='https' or not target.hostname or target.username or target.password or target.query or target.fragment:
        raise ValueError('服务器地址必须是无凭证、无查询参数的HTTPS地址。')
    token=settings.get('token','')
    if not isinstance(token,str) or len(token)<32 or any(c.isspace() for c in token):raise ValueError('访问凭证无效。')
    if action not in ('search','compare','contract'):raise ValueError('不支持此远程操作。')
    request=Request(endpoint+'/v1/'+action,data=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'},method='POST')
    try:
        with build_opener(NoRedirect).open(request,timeout=90) as response:
            raw=response.read(12*1024*1024+1)
            if len(raw)>12*1024*1024:raise ValueError('远程结果过大，请拆分报价。')
            return json.loads(raw)
    except HTTPError as exc:
        messages={401:'访问凭证无效或已撤销，请联系管理员。',403:'当前账号没有此操作权限。',413:'报价内容过大，请拆分。',429:'查询过于频繁，请稍后重试。',503:'服务正在处理其他查询，请稍后重试。'}
        raise ValueError(messages.get(exc.code,'远程请求失败，请检查输入或联系管理员。')) from None
    except URLError:
        raise ValueError('无法连接估价服务器，请检查网络及服务地址。') from None
