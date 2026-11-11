"""Generate a private, recipient-specific installation command."""
import json
import os
from pathlib import Path
from .activation import parse_access_code

RELEASE = "156aca03aa2d848227caddb57d0b53023105c5e3"

def write_command(code, output, windows=False):
    parse_access_code(code)
    # Credential is inside the private command, never printed by this generator.
    script = ("import pathlib,venv,os,subprocess;"
        "d=pathlib.Path.home()/'.valuation-agent/workbench';"
        "venv.create(d,with_pip=True);"
        "p=str(d/('Scripts/python.exe' if os.name=='nt' else 'bin/python'));"
        "subprocess.run([p,'-m','pip','install','valuation-agent[excel] @ https://codeload.github.com/yuguangtongchen1/valuation-agent/zip/" + RELEASE + "'],check=True);"
        "c=[p,'-m','valuation_agent.cli'];"
        "subprocess.run(c+['activate'],input=" + repr(code) + ",text=True,check=True);"
        "subprocess.run(c+['launch'],check=True)")
    command = ("py" if windows else "python3") + " -c " + json.dumps(script,ensure_ascii=False) + "\n"
    target=Path(output).expanduser()
    target.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(str(target),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:stream.write(command)
    return target
