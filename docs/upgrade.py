"""One-time migration for official installations; never re-activate or erase data."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import time
from urllib.parse import urlsplit


def main():
    parser = argparse.ArgumentParser(description='保留原配置和浏览器地址升级估价 Agent')
    parser.add_argument('--url', help='原工作台地址')
    parser.add_argument('--no-launch', action='store_true')
    args = parser.parse_args()
    home = Path.home()
    python = home / '.valuation-agent/workbench' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        raise SystemExit('未找到官网安装环境。请让 Codex 定位原安装目录；不会新建环境或移动数据。')
    url = urlsplit(args.url or input('粘贴原工作台地址（请先关闭旧启动终端，不要清除浏览器数据）：').strip())
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or url.username or url.password:
        raise SystemExit('请输入原来的 http://127.0.0.1:端口/ 地址；不猜测原端口。')
    # An occupied port may belong to another project. Never stop it.
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', url.port)) == 0:
            raise SystemExit('原端口仍在使用。请关闭旧估价启动终端后重试；未停止任何进程。')
    config = home / '.config/valuation-agent'
    config.mkdir(parents=True, exist_ok=True)
    backup = home / '.valuation-agent/upgrade-backups' / str(time.time_ns())
    backup.mkdir(parents=True, mode=0o700)
    for name in ('remote.json', 'workbench-port.json'):
        source = config / name
        if source.is_file():
            shutil.copy2(source, backup / name)
            (backup / name).chmod(0o600)
    subprocess.run([str(python), '-m', 'pip', 'install', '--upgrade',
        'valuation-agent[excel] @ https://codeload.github.com/yuguangtongchen1/valuation-agent/zip/v0.2.21'], check=True)
    actual = subprocess.check_output([str(python), '-I', '-m', 'valuation_agent.cli', '--version'], text=True).strip()
    if actual != '0.2.21':
        raise SystemExit('版本核验失败，未改启动地址。')
    (config / 'workbench-port.json').write_text(json.dumps({'port': url.port}), encoding='utf-8')
    command = [str(python), '-I', '-m', 'valuation_agent.cli', 'launch']
    desktop = home / 'Desktop'
    desktop.mkdir(exist_ok=True)
    launcher = desktop / ('启动估价Agent.cmd' if os.name == 'nt' else '启动估价Agent.command')
    if launcher.exists():
        shutil.copy2(launcher, backup / launcher.name)
    launcher.write_text(('@echo off\n' + subprocess.list2cmdline(command) + '\npause\n') if os.name == 'nt' else ('#!/bin/sh\nexec ' + shlex.join(command) + '\n'), encoding='utf-8')
    launcher.chmod(0o700)
    print('升级完成。以后使用桌面“启动估价Agent”；沿用原浏览器和用户配置。')
    print('访问配置已备份，原报价文件未移动。历史参考缓存会重新查询。')
    if not args.no_launch:
        subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
