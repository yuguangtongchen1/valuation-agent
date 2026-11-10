"""Portable access cards, validated before storing locally; never logged."""
import base64,json,os,tempfile
from pathlib import Path
from urllib.parse import urlparse

def parse_access_code(code):
    if not isinstance(code,str)or not code.startswith('VA1.')or len(code)>2048:raise ValueError('访问码格式无效，请使用管理员提供的完整访问码。')
    try:
        raw=base64.b64decode(code[4:]+'='*(-len(code[4:])%4),altchars=b'-_',validate=True)
        value=json.loads(raw)
    except (ValueError,UnicodeError):raise ValueError('访问码无法读取。')from None
    if not isinstance(value,dict):raise ValueError('访问码无效。')
    endpoint=value.get('endpoint','');token=value.get('token','')
    if not isinstance(endpoint,str):raise ValueError('服务地址无效。')
    p=urlparse(endpoint)
    if p.scheme!='https'or not p.hostname or p.username or p.password or p.query or p.fragment:raise ValueError('访问码必须使用 HTTPS 服务地址。')
    if not isinstance(token,str)or not 32<=len(token)<=200 or any(c.isspace()for c in token):raise ValueError('访问凭证无效。')
    return {'endpoint':endpoint.rstrip('/'),'token':token}

def default_config():return Path.home()/'.config/valuation-agent/remote.json'

def activate(code,path=None):
    from .remote import remote_call
    value=parse_access_code(code);target=Path(path or default_config()).expanduser();target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temp=tempfile.mkstemp(prefix='.activate-',dir=target.parent)
    try:
        with os.fdopen(fd,'w')as f:json.dump(value,f)
        os.chmod(temp,0o600)
        # Check the supplied account before replacing a working configuration.
        remote_call('search',{'phrase':'连接校验','limit':1},temp)
        os.replace(temp,target)
    finally:
        Path(temp).unlink(missing_ok=True)
    return target
