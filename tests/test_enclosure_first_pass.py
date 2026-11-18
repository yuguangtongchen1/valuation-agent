import unittest
from valuation_agent.engine import modules

class EnclosureScope(unittest.TestCase):
    def test_scope_uses_included_services(self):
        scope = modules()['workbench'].scope_parts
        self.assertEqual(scope('搭建；拆除；不含运费')[0], {'安装', '拆除'})
        self.assertEqual(scope('含运输、报备及脚手架')[0], {'运输', '报备', '脚手架'})
