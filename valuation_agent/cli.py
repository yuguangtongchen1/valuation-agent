"""Installable CLI; all operations are local and read supplied sources only."""
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


def main(argv=None):
    parser = argparse.ArgumentParser(prog="valuation-agent", description="报价导入、归类、历史参考查询与采购建议（本地只读）")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    sample = commands.add_parser("demo", help="生成完全合成的输入、比价结果和建议")
    sample.add_argument("--output-dir", type=Path, default=Path("valuation-demo"))
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
            sources.add_argument("--data", type=Path, help="经校验的私有 Data Hub 目录")
            sources.add_argument("--history", type=Path, help="用户提供的历史 JSON/CSV/XLSX/XLS")
            command.add_argument("--history-worksheet")
    lookup = commands.add_parser("search", help="查询所选历史资料，含待核项并标注状态")
    lookup.add_argument("phrase")
    sources = lookup.add_mutually_exclusive_group(required=True)
    sources.add_argument("--data", type=Path)
    sources.add_argument("--history", type=Path)
    lookup.add_argument("--worksheet")
    lookup.add_argument("--limit", type=int, default=10)
    lookup.add_argument("--out", type=Path)
    report = commands.add_parser("report", help="由比价 JSON 生成结构化 Markdown 采购建议")
    report.add_argument("input", type=Path)
    report.add_argument("--out", type=Path)
    report.add_argument("--threshold", default="0.15", help="偏高/偏低提示阈值，例如 0.15 代表 15%%")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = demo(args.output_dir)
        elif args.command == "audit":
            result = audit(args.data)
        elif args.command == "import":
            result = read_input(args.input, args.worksheet)
        elif args.command == "classify":
            result = classify(read_input(args.input, args.worksheet))
        elif args.command == "search":
            result = search(args.phrase, args.data, args.history, args.limit, args.worksheet)
        elif args.command == "compare":
            result = compare(read_input(args.input, args.worksheet), args.data, args.history, args.history_worksheet)
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
