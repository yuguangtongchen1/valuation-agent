"""Load the same engine used by the workbench, or its portable snapshot."""
import importlib
import os
from pathlib import Path
import re
import sys


ENGINE_FILES = (
    "workbench.py", "valuation.py", "estimate.py", "quote_classification.py",
    "exhibition_knowledge.py", "quote_parameters.py", "semantic_profile.py", "reference_catalog.py", "row_classification.py",
    "source_registry.py", "money_units.py", "taxonomy_schema.py", "finance_view.py", "legacy_xls.py",
)


def refresh_bundled_engine(source=None):
    """Maintainer operation: copy generic engine code, never private data."""
    source = Path(source) if source else Path(__file__).resolve().parents[1] / "scripts"
    target = Path(__file__).parent / "_engine"
    target.mkdir(exist_ok=True)
    (target / "__init__.py").write_text('"""Portable workbench engine snapshot."""\n', encoding="utf-8")
    for filename in ENGINE_FILES:
        code = (source / filename).read_text(encoding="utf-8")
        if filename == "workbench.py":
            code = "import os\n" + code
            code = re.sub(r"^TABLE_URL = .*?$", "TABLE_URL = os.environ.get('VALUATION_AGENT_FEISHU_TABLE_URL', '')", code, flags=re.M)
            code = re.sub(r"^GITHUB = .*?$", "GITHUB = os.environ.get('VALUATION_AGENT_SOURCE_BASE_URL', '')", code, flags=re.M)
            code = code.replace("if source.is_file() else None", "if GITHUB and source.is_file() else None")
            code = code.replace("def table_fallback(phrase):\n", "def table_fallback(phrase):\n    if not TABLE_URL:\n        return [], False\n")
        (target / filename).write_text(code, encoding="utf-8")
    return target


def modules():
    # Editable development uses the current engine; installed wheels are self-contained.
    development = Path(__file__).resolve().parents[1] / "scripts"
    directory = development if (development / "workbench.py").is_file() else Path(__file__).parent / "_engine"
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    workbench = importlib.import_module("workbench")
    workbench.TABLE_URL = os.environ.get("VALUATION_AGENT_FEISHU_TABLE_URL", "")
    workbench.GITHUB = os.environ.get("VALUATION_AGENT_SOURCE_BASE_URL", "")
    return {
        "workbench": workbench,
        "valuation": importlib.import_module("valuation"),
        "classification": importlib.import_module("quote_classification"),
        "parameters": importlib.import_module("quote_parameters"),
        "catalog": importlib.import_module("reference_catalog"),
        "registry": importlib.import_module("source_registry"),
        "money": importlib.import_module("money_units"),
        "legacy": importlib.import_module("legacy_xls"),
    }
