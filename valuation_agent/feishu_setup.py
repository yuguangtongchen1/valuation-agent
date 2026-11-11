"""Install the optional official Feishu CLI without copying user credentials."""
import os
import shutil
import subprocess

GUIDE = "https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide.md"

def setup():
    cli = shutil.which("lark-cli")
    if not cli:
        npm = shutil.which("npm")
        npx = shutil.which("npx")
        if not npm or not npx:
            raise ValueError("飞书导入需要 Node.js LTS（含 npm/npx）。请让 Codex 按官方指南安装 Node.js 后重新运行 valuation-agent feishu-setup：" + GUIDE)
        print("正在安装官方飞书 CLI 和 Skills…", flush=True)
        # Windows npm/npx are command wrappers; no user input is interpolated.
        for executable, args in ((npm, ["install", "-g", "@larksuite/cli"]),
                                 (npx, ["-y", "skills", "add", "https://open.feishu.cn", "--skill", "-y"])):
            try:
                subprocess.run([executable, *args], check=True, timeout=600, shell=os.name == "nt")
            except (OSError, subprocess.SubprocessError) as exc:
                raise ValueError("飞书安装未完成，请检查网络和 npm 安装权限后重试；不会使用 sudo 自动提权。官方指南：" + GUIDE) from exc
        cli = shutil.which("lark-cli")
        if not cli:
            raise ValueError("安装结束但当前 PATH 找不到 lark-cli。重新打开终端并运行 valuation-agent feishu-setup。")
    print("飞书 CLI 已就绪。请运行 lark-cli auth status --json --verify 检查当前账号。")
    print("首次未配置：lark-cli config init --new（已有配置不要重建）。")
    print("未登录：lark-cli auth login --recommend；按官方流程在浏览器完成授权，再重试飞书导入。")
    print("估价访问码不代替飞书授权；文件需对当前飞书账号可读。")
