"""Quotation CLI with local sources or explicitly configured private HTTPS queries."""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys

from . import __version__
from .demo import run as demo
from .io import read_input, write_json
from .reports import render
from .service import audit, classify, compare, search


def remote_compare(document,config):
    from .remote import remote_call
    if not document['rows'] or len(document['rows'])>1000:raise ValueError('远程比价每份支持1至1000条，请拆分。')
    result=None
    fields=('item_name','spec','model','description','configuration','quantity','unit','currency','dimension_unit','row_id','source_locator','unit_price','subtotal')
    for start in range(0,len(document['rows']),20):
        rows=[{k:r[k] for k in fields if k in r} for r in document['rows'][start:start+20]]
        part=remote_call('compare',{'document':{'project':document.get('project',''),'rows':rows}},config)
        if result is None:result=part
        else:result['rows'].extend(part['rows'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="valuation-agent", description="报价导入、归类、历史参考查询与比价表")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("demo", help="生成完全合成的输入、比价结果和建议")
    sample.add_argument("--output-dir", type=Path, default=Path("valuation-demo"))
    quick = commands.add_parser("run", help="一条命令生成比价 Excel 和 JSON，不生成采购建议")
    quick.add_argument("input", type=Path)
    quick.add_argument("--worksheet")
    quick.add_argument("--currency", default="CNY", help="未标币种的新报价使用此币种，默认CNY")
    run_sources=quick.add_mutually_exclusive_group()
    run_sources.add_argument("--data", type=Path)
    run_sources.add_argument("--remote", type=Path, help="仅查询服务器，不下载历史数据库")
    quick.add_argument("--output-dir", type=Path, default=Path("比价结果"))
    activation = commands.add_parser("activate", help="通过隐藏输入或本机文件激活访问码，不回显凭证")
    activation.add_argument("--file", type=Path)
    activation.add_argument("--remote", type=Path)
    browser = commands.add_parser("launch", help="自动打开本机操作界面；首次使用输入管理员访问码")
    browser.add_argument("--remote", type=Path)
    browser.add_argument("--port", type=int, default=0)
    browser.add_argument("--no-browser", action="store_true")
    commands.add_parser("feishu-setup", help="检测并安装官方飞书 CLI 与 Skills，输出授权步骤")
    check = commands.add_parser("audit", help="只读校验 Data Hub 的项目、合同、原件与报价关联")
    check.add_argument("--data", type=Path, required=True)
    check.add_argument("--out", type=Path)
    for name in ("import", "classify", "compare"):
        command = commands.add_parser(name, help={"import": "归一 JSON/CSV/XLSX/XLS，保留原字段", "classify": "按现有多级归类引擎分类", "compare": "拆解型号、规格和组合并检索历史"}[name])
        command.add_argument("input", type=Path)
        command.add_argument("--worksheet", help="Excel 工作表名；多表时必须指定")
        command.add_argument("--out", type=Path)
        if name == "compare":
            sources = command.add_mutually_exclusive_group(required=True)
            sources.add_argument("--remote", type=Path, help="内部服务器访问配置")
            sources.add_argument("--data", type=Path, help="经校验的私有 Data Hub 目录")
            sources.add_argument("--history", type=Path, help="用户提供的历史 JSON/CSV/XLSX/XLS")
            command.add_argument("--history-worksheet")
    lookup = commands.add_parser("search", help="查询所选历史资料，含待核项并标注状态")
    lookup.add_argument("phrase")
    sources = lookup.add_mutually_exclusive_group(required=True)
    sources.add_argument("--remote", type=Path, help="内部服务器访问配置")
    sources.add_argument("--data", type=Path)
    sources.add_argument("--history", type=Path)
    lookup.add_argument("--worksheet")
    lookup.add_argument("--limit", type=int, default=10)
    lookup.add_argument("--out", type=Path)
    detail = commands.add_parser("contract", help="查看已授权的历史合同明细")
    detail.add_argument("record_id")
    detail.add_argument("--remote", type=Path, required=True)
    detail.add_argument("--out", type=Path)
    report = commands.add_parser("report", help="由比价 JSON 生成结构化 Markdown 采购建议")
    report.add_argument("input", type=Path)
    report.add_argument("--out", type=Path)
    report.add_argument("--threshold", default="0.15", help="偏高/偏低提示阈值，例如 0.15 代表 15%%")
    args = parser.parse_args(argv)
    try:
        if args.command == "feishu-setup":
            from .feishu_setup import setup
            setup()
            return
        if args.command == "activate":
            import getpass
            from .activation import activate
            code=args.file.read_text().strip() if args.file else getpass.getpass('管理员访问码（隐藏输入）：') if sys.stdin.isatty() else sys.stdin.read().strip()
            activate(code,args.remote)
            print('访问已激活。运行 valuation-agent launch 打开操作界面。')
            return
        if args.command == "launch":
            from .browser_app import launch
            launch(args.remote,args.port,args.no_browser)
            return
        if args.command == "demo":
            result = demo(args.output_dir)
        elif args.command == "run":
            from .excel_export import export_comparison
            document=read_input(args.input, args.worksheet)
            for row in document['rows']:
                if not row.get('currency'):
                    row['currency']=args.currency.upper()
                    row['currency_basis']='run --currency (default CNY)'
            if args.remote:
                result=remote_compare(document,args.remote)
            else:
                result = compare(document, data=args.data or Path(__file__).resolve().parents[1]/"private-data")
            target=args.output_dir; target.mkdir(parents=True,exist_ok=True)
            write_json(target/"比价结果.json",result)
            export_comparison(result,target/"比价结果.xlsx")
            print(json.dumps({"rows":len(result["rows"]),"excel":str((target/"比价结果.xlsx").resolve()),"json":str((target/"比价结果.json").resolve())},ensure_ascii=False))
            return
        elif args.command == "audit":
            result = audit(args.data)
        elif args.command == "import":
            result = read_input(args.input, args.worksheet)
        elif args.command == "classify":
            result = classify(read_input(args.input, args.worksheet))
        elif args.command == "search":
            if args.remote:
                from .remote import remote_call
                result=remote_call('search',{'phrase':args.phrase,'limit':args.limit},args.remote)
            else:result = search(args.phrase, args.data, args.history, args.limit, args.worksheet)
        elif args.command == "contract":
            from .remote import remote_call
            result=remote_call('contract',{'record_id':args.record_id},args.remote)
        elif args.command == "compare":
            document=read_input(args.input,args.worksheet)
            result = remote_compare(document,args.remote) if args.remote else compare(document, args.data, args.history, args.history_worksheet)
        else:
            result = render(json.loads(args.input.read_text(encoding="utf-8")), Decimal(args.threshold))
        output = getattr(args, "out", None)
        if isinstance(result, str):
            if output:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(result, encoding="utf-8")
            else:
                sys.stdout.write(result)
        elif output:
            write_json(output, result)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as exc:
        parser.exit(2, f"valuation-agent: {exc}\n")


if __name__ == "__main__":
    main()
