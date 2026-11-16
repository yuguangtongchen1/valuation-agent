"""Stage official releases without modifying credentials, quotes or the running app."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import venv

MANIFEST = 'https://raw.githubusercontent.com/yuguangtongchen1/valuation-agent/main/docs/latest.json'
ROOT = Path.home() / '.valuation-agent' / 'updates'

def version(value):
    if not re.fullmatch(r'0\.\d+\.\d+', value):
        raise ValueError('Invalid stable release')
    return tuple(map(int, value.split('.')))

def python_at(path):
    return path / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

def prepare():
    from . import __version__
    ROOT.mkdir(parents=True, exist_ok=True)
    pointer = ROOT / 'current.json'
    selected = None
    try:
        saved = json.loads(pointer.read_text())['version']
        if version(saved) > version(__version__) and (ROOT / saved / '.ready').exists() and python_at(ROOT / saved).exists():
            selected = python_at(ROOT / saved)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        with urllib.request.urlopen(MANIFEST, timeout=4) as response:
            target = json.load(response)['version']
        if version(target) <= version(saved if selected else __version__):
            return selected
        path = ROOT / target
        python = python_at(path)
        ready = path / '.ready'
        if not ready.exists():
            lock = ROOT / '.install-lock'
            try:
                lock.mkdir()
            except FileExistsError:
                return selected
            try:
                print('正在准备估价新版；访问配置和报价文件保持不变。', flush=True)
                venv.create(path, with_pip=True)
                subprocess.run([str(python), '-m', 'pip', 'install',
                    'valuation-agent[excel] @ https://codeload.github.com/yuguangtongchen1/valuation-agent/zip/v' + target],
                    check=True, timeout=240, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                actual = subprocess.check_output([str(python), '-I', '-m', 'valuation_agent.cli', '--version'], timeout=20, text=True).strip()
                if actual != target:
                    raise ValueError('Release verification failed')
                subprocess.run([str(python), '-I', '-c', 'import openpyxl,xlrd; from valuation_agent.browser_app import launch'], check=True, timeout=20)
                ready.touch()
            finally:
                lock.rmdir()
        temporary = ROOT / ('current-' + str(os.getpid()) + '.json')
        temporary.write_text(json.dumps({'version': target}))
        temporary.replace(pointer)
        return python
    except Exception:
        print('新版暂不可用，继续使用已安装版本。', flush=True)
        return selected

def launch_current(argv):
    if os.environ.get('VALUATION_UPDATE_CHILD') == '1':
        return False
    python = prepare()
    if python:
        env = dict(os.environ, VALUATION_UPDATE_CHILD='1')
        subprocess.run([str(python), '-I', '-m', 'valuation_agent.cli'] + list(argv), env=env, check=True)
        return True
    return False
