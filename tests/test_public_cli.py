"""Exercise an installed package outside the checkout with synthetic inputs only."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import venv
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from valuation_agent.demo import run
from valuation_agent.io import read_input, write_json
from valuation_agent.reports import assessment, render
from valuation_agent.service import compare


class PublicCLI(unittest.TestCase):
    def comparable_entry(self, directory):
        run(directory)
        return json.loads((Path(directory) / "comparison.json").read_text())["rows"][0]

    def test_independent_projects_not_repeated_rows_determine_reference_price(self):
        with tempfile.TemporaryDirectory() as directory:
            entry = self.comparable_entry(directory)
            first = entry["references"][0]
            repeated = [deepcopy(first) for _ in range(3)]
            for index, ref in enumerate(repeated):
                ref["line_id"] = f"same-project-line-{index}"
                ref["source_locator"] = f"different actual source row {index}"
            other = deepcopy(first)
            other.update(project_key="independent-project-b", project="另一真实项目", unit_price="200", subtotal="200")
            entry["references"] = [*repeated, other]
            advice = assessment(entry)
            self.assertEqual(advice["reference_price"], "150")
            self.assertEqual(advice["status"], "偏低")
            self.assertEqual(advice["independent_project_count"], 2)
            self.assertEqual(advice["deduplicated_same_project_rows"], 2)
            self.assertEqual(len(advice["comparable"]), 2)
            self.assertEqual(len(advice["references"]), 4)

    def test_conflicting_prices_within_one_project_do_not_produce_high_low_judgment(self):
        with tempfile.TemporaryDirectory() as directory:
            entry = self.comparable_entry(directory)
            first = entry["references"][0]
            conflicting = deepcopy(first)
            conflicting.update(line_id="conflicting-version", unit_price="200", subtotal="200")
            entry["references"] = [first, conflicting]
            advice = assessment(entry)
            self.assertEqual(advice["status"], "仅供参考")
            self.assertFalse(advice["comparable"])
            self.assertNotIn("reference_price", advice)
            self.assertEqual(len(advice["references"]), 2)
            self.assertIn("同一项目存在不同历史单价", advice["reason"])
            self.assertEqual(advice["project_price_conflicts"][0]["prices_cny_yuan"], ["100", "200"])
            self.assertIn("不同历史单价", render({"rows": [entry]}))

    def test_unidentified_project_keys_never_count_as_independent_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            source = self.comparable_entry(directory)
            for key in (None, "", "unknown", "unmapped:source", "project:generated"):
                entry = deepcopy(source)
                entry["references"][0].update(project_key=key, project="")
                advice = assessment(entry)
                self.assertEqual(advice["status"], "仅供参考", key)
                self.assertEqual(advice["independent_project_count"], 0, key)
                self.assertEqual(len(advice["unidentified_project_reference_line_ids"]), 1)
                self.assertEqual(len(advice["references"]), 1)

    def test_unidentified_project_does_not_change_known_project_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            entry = self.comparable_entry(directory)
            unknown = deepcopy(entry["references"][0])
            unknown.update(line_id="unknown-source", project_key=None, project="", unit_price="200", subtotal="200")
            entry["references"].append(unknown)
            advice = assessment(entry)
            self.assertEqual(advice["reference_price"], "100")
            self.assertEqual(advice["independent_project_count"], 1)
            self.assertEqual(advice["status"], "偏高")
            self.assertEqual(advice["unidentified_project_reference_line_ids"], ["unknown-source"])

    def test_source_clarifications_union_backend_and_input_without_duplication(self):
        entry = {"quote": {"item_name": "曲臂车", "description": "安装3个台班，撤场1个台班", "quantity": "3"},
                 "references": [], "input_issues": ["后端已指出的独立疑点"]}
        rendered = render({"rows": [entry]})
        self.assertIn("原单待澄清", rendered)
        self.assertIn("后端已指出的独立疑点", rendered)
        self.assertIn("不直接改为4", rendered)
        self.assertEqual(entry["quote"]["quantity"], "3")

    def test_input_retains_nonstandard_source_fields_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text('材料名称,规格型号,数量,单位,单价,金额,备注\n灯控网线,CAT6,40,米,5,200,2个人工\n', encoding="utf-8")
            row = read_input(path)["rows"][0]
            self.assertEqual(row["item_name"], "灯控网线")
            self.assertEqual(row["spec"], "CAT6")
            self.assertEqual(row["source_original_fields"]["备注"], "2个人工")
            self.assertEqual(row["unit_price"], "5")
            write_json(path.with_suffix(".json"), [{"item_name": "名称甲", "名称": "名称乙"}])
            with self.assertRaisesRegex(ValueError, "冲突"):
                read_input(path.with_suffix(".json"))

    def test_report_boundaries_currency_role_source_and_tax(self):
        with tempfile.TemporaryDirectory() as directory:
            run(directory)
            root = Path(directory)
            result = json.loads((root / "comparison.json").read_text())
            good = result["rows"][0]
            self.assertEqual(assessment(good)["status"], "偏高")
            for role in ("package", "component", "partial", "process"):
                entry = deepcopy(good)
                entry["references"][0]["comparison_role"] = role
                self.assertEqual(assessment(entry)["status"], "仅供参考")
            foreign = deepcopy(good)
            foreign["references"][0]["currency"] = "USD"
            foreign["references"][0]["unit_price_currency"] = "USD"
            self.assertEqual(assessment(foreign)["status"], "仅供参考")
            no_scope = deepcopy(good)
            no_scope["quote"]["scope"] = ""
            no_scope["quote"]["module"] = ""
            self.assertEqual(assessment(no_scope)["status"], "仅供参考")
            tax = deepcopy(good)
            tax["quote"]["tax_basis"] = "未注明"
            tax["references"][0]["tax_basis"] = "财务已确认"
            tax["references"][0]["ledger_amount_cny_tax_inclusive"] = "99999"
            self.assertEqual(assessment(tax)["status"], "偏高")
            self.assertIn("部分子件", render(result))
            self.assertIn("缺少参考", render(result))

    def test_pending_association_and_superseded_prices_are_not_references(self):
        with tempfile.TemporaryDirectory() as directory:
            run(directory)
            root = Path(directory)
            history = json.loads((root / "history.json").read_text())
            history["rows"][0]["scope_association_pending"] = True
            history["rows"][1]["source_price_version"] = "变更前"
            write_json(root / "history.json", history)
            result = compare(read_input(root / "quote.json"), history=root / "history.json")
            self.assertFalse([r for r in result["rows"][0]["references"] if r.get("unit_price")])
            self.assertFalse([r for r in result["rows"][1]["references"] if r.get("unit_price")])

    def test_unreviewed_history_searchable_but_not_price_judgment(self):
        with tempfile.TemporaryDirectory() as directory:
            run(directory)
            root = Path(directory)
            history = json.loads((root / "history.json").read_text())
            for row in history["rows"]:
                row.pop("record_status")
            write_json(root / "history.json", history)
            result = compare(read_input(root / "quote.json"), history=root / "history.json")
            self.assertTrue(result["rows"][0]["references"])
            self.assertEqual(assessment(result["rows"][0])["status"], "仅供参考")

    def test_private_data_uses_existing_source_and_coverage_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run(root / "demo")
            history = read_input(root / "demo" / "history.json")
            row = {**history["rows"][0], "record_id": "synthetic:2", "project_key": "synthetic-project",
                   "kind": "bom_line", "line_id": "synthetic:2:1", "ledger_amount_cny_tax_inclusive": "100"}
            data = root / "data"
            write_json(data / "ledger.json", [{"record_id": row["record_id"], "project_name": row["project"],
                "contract_name": "合成采购合同", "contract_link": "合成来源", "sheet": "demo", "row": 2,
                "attachments": [{"token": row["source_token"]}], "ledger_tax_inclusive_amount": "100"}])
            write_json(data / "quote-records.json", [row])
            write_json(data / "quote-record-coverage.json", [{"record_id": row["record_id"]}])
            write_json(data / "project-hierarchy.json", {"projects": [{"main_project_key": row["project_key"],
                "owner_groups": [{"contracts": [{"record_id": row["record_id"]}]}]}]})
            write_json(data / "合同复核进度.json", {"台账记录数": 1, "完成原件复核": 1,
                "重复来源待核": [], "记录": [{"record_id": row["record_id"], "已完成原件复核": True}]})
            document = read_input(root / "demo" / "quote.json")
            result = compare(document, data=data)
            self.assertEqual(result["history"]["mode"], "private_data")
            self.assertEqual(assessment(result["rows"][0])["status"], "偏高")
            whole = {**row, "kind": "whole_scope_quote", "line_id": None,
                     "item_name": "合成整项服务", "source_locator": "synthetic whole service clause",
                     "model": "DEMO-WHOLE-SERVICE", "spec": "合成整项交付",
                     "record_status": "whole_scope_source_checked"}
            write_json(data / "quote-records.json", [row, whole])
            own_result = compare({"rows": [{**whole, "scope": whole["module"]}]}, data=data)
            self.assertEqual(own_result["rows"][0]["references"], [])
            new_quote = {k: whole[k] for k in ("item_name", "model", "spec", "unit", "currency")}
            new_quote["scope"] = whole["module"]
            whole_result = compare({"rows": [new_quote]}, data=data)
            self.assertEqual(whole_result["rows"][0]["references"][0]["comparison_role"], "package")
            self.assertEqual(assessment(whole_result["rows"][0])["status"], "仅供参考")
            self.assertIsNone(json.loads((data / "quote-records.json").read_text())[1]["line_id"])
            row["source_token"] = "unlinked-source"
            write_json(data / "quote-records.json", [row])
            with self.assertRaisesRegex(ValueError, "no source linked"):
                compare(document, data=data)

    def test_installed_wheel_runs_all_six_commands_without_repo_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Build artifacts and all test inputs stay outside the checkout.
            wheel_dir = root / "wheels"
            subprocess.run([sys.executable, "-m", "pip", "--disable-pip-version-check", "wheel", "--no-index", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheel_dir), str(REPO)], check=True, capture_output=True, text=True)
            wheel = next(wheel_dir.glob("*.whl"))
            with zipfile.ZipFile(wheel) as archive:
                self.assertTrue(any(name.endswith("_engine/workbench.py") for name in archive.namelist()))
                self.assertFalse(any(name.startswith(("data/", "ui/", "site/")) for name in archive.namelist()))
                for name in archive.namelist():
                    if name.endswith(".py"):
                        code = archive.read(name).decode("utf-8")
                        for private in (".feishu.cn/wiki/", "PRIVATE_DEFAULT_OWNER", "PRIVATE_SOURCE_TOKEN"):
                            self.assertNotIn(private, code)
            environment = root / "venv"
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / "bin" / "python"
            subprocess.run([str(python), "-m", "pip", "--disable-pip-version-check", "install", "--no-index", "--no-deps", str(wheel)], check=True, capture_output=True, text=True)
            command = environment / "bin" / "valuation-agent"

            def cli(*args, ok=True):
                process = subprocess.run([str(command), *map(str, args)], cwd=root, capture_output=True, text=True)
                if ok:
                    self.assertEqual(process.returncode, 0, process.stderr)
                return process

            sample = root / "demo"
            cli("demo", "--output-dir", sample)
            cli("import", sample / "quote.json", "--out", root / "normalized.json")
            cli("classify", root / "normalized.json", "--out", root / "classified.json")
            classified = json.loads((root / "classified.json").read_text())
            self.assertTrue(classified["rows"][0]["classification_path"])
            self.assertTrue(classified["rows"][0]["parameters"]["功率"])
            found = json.loads(cli("search", "星形灯", "--history", sample / "history.json").stdout)
            self.assertEqual(found["match_count"], 1)
            cli("compare", sample / "quote.json", "--history", sample / "history.json", "--out", root / "comparison.json")
            cli("report", root / "comparison.json", "--out", root / "advice.md")
            rendered = (root / "advice.md").read_text()
            self.assertIn("偏高", rendered)
            self.assertIn("合成供应商甲", rendered)
            self.assertIn("部分子件", rendered)
            self.assertNotIn(".feishu.cn/wiki/", (root / "comparison.json").read_text())
            result = json.loads((root / "comparison.json").read_text())
            self.assertEqual(result["rows"][0]["retrieval_trace"]["priced_rows_examined"], 3)
            self.assertFalse(result["history"]["live_feishu_search"])
            unsupported = root / "scan.pdf"
            unsupported.write_bytes(b"not a real PDF")
            failed = cli("import", unsupported, ok=False)
            self.assertEqual(failed.returncode, 2)
            self.assertIn("Skill", failed.stderr)


if __name__ == "__main__":
    unittest.main()
