import unittest
from unittest.mock import patch
from valuation_agent.feishu_setup import setup

class FeishuSetupTests(unittest.TestCase):
    @patch('valuation_agent.feishu_setup.subprocess.run')
    @patch('valuation_agent.feishu_setup.shutil.which', return_value='/bin/lark-cli')
    def test_existing_is_not_reinstalled(self, which, run):
        setup()
        run.assert_not_called()

    @patch('valuation_agent.feishu_setup.shutil.which', return_value=None)
    def test_missing_node_explains_dependency(self, which):
        with self.assertRaisesRegex(ValueError, 'Node.js'):
            setup()

    @patch('valuation_agent.feishu_setup.subprocess.run')
    @patch('valuation_agent.feishu_setup.shutil.which', side_effect=[None,'/bin/npm','/bin/npx','/bin/lark-cli'])
    def test_missing_cli_installs_official_package_and_skills(self, which, run):
        setup()
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0], ['/bin/npm','install','-g','@larksuite/cli'])
        self.assertIn('https://open.feishu.cn', run.call_args_list[1].args[0])

if __name__ == '__main__': unittest.main()
