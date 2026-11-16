import unittest
from pathlib import Path
import re

class HighlightDeliveryTests(unittest.TestCase):
 def test_shipped_styles_highlight_entire_row(self):
  root=Path(__file__).resolve().parents[1]/"valuation_agent/web"
  css_path=re.search(r'href="(/assets/[^"]+\.css)"', (root/"index.html").read_text()).group(1)
  css=(root/css_path.lstrip("/")).read_text()
  for selector in [".evidence-highlight td", ".valuation-evidence .evidence-highlight td"]:
   self.assertRegex(css,re.escape(selector)+r"\{background:#fff1b8(?:!important)?\}")
