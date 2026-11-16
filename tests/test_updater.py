import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from valuation_agent import updater

class UpdaterTests(unittest.TestCase):
    def test_untrusted_version_rejected(self):
        for value in ['../bad','1.2.3;bad','0.2.20-beta','https://other']:
            with self.assertRaises(ValueError):updater.version(value)
    def test_offline_keeps_cached_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); target=root/'0.2.99';target.mkdir()
            python=updater.python_at(target);python.parent.mkdir();python.touch();(target/'.ready').touch()
            (root/'current.json').write_text(json.dumps({'version':'0.2.99'}))
            with patch.object(updater,'ROOT',root),patch.object(updater.urllib.request,'urlopen',side_effect=OSError):
                self.assertEqual(updater.prepare(),python)
    def test_failed_install_preserves_config_and_quotes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);config=root/'remote.json';quote=root/'quote.json'
            config.write_text('private');quote.write_text('quotation')
            with patch.object(updater,'ROOT',root/'updates'),patch.object(updater.urllib.request,'urlopen',return_value=io.BytesIO(b'{"version":"0.2.99"}')),patch.object(updater.venv,'create',side_effect=OSError):
                self.assertIsNone(updater.prepare())
            self.assertEqual(config.read_text(),'private');self.assertEqual(quote.read_text(),'quotation')
            self.assertFalse((root/'updates/current.json').exists())
    def test_child_does_not_recurse(self):
        with patch.dict(updater.os.environ,{'VALUATION_UPDATE_CHILD':'1'}),patch.object(updater,'prepare') as prepare:
            self.assertFalse(updater.launch_current(['launch']));prepare.assert_not_called()
    def test_forwards_arguments(self):
        with patch.dict(updater.os.environ,{'VALUATION_UPDATE_CHILD':'0'}),patch.object(updater,'prepare',return_value=Path('/tmp/new/python')),patch.object(updater.subprocess,'run') as run:
            self.assertTrue(updater.launch_current(['launch','--port','59067','--input','quote.json']))
            self.assertEqual(run.call_args.args[0][-5:],['launch','--port','59067','--input','quote.json'])
    def test_success_switches_only_after_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def create(path,**kwargs):path.mkdir(parents=True)
            with patch.object(updater,'ROOT',root),patch.object(updater.urllib.request,'urlopen',return_value=io.BytesIO(b'{"version":"0.2.99"}')),patch.object(updater.venv,'create',side_effect=create),patch.object(updater.subprocess,'run'),patch.object(updater.subprocess,'check_output',return_value='0.2.99\n'):
                self.assertEqual(updater.prepare(),updater.python_at(root/'0.2.99'))
            self.assertTrue((root/'0.2.99/.ready').exists())
            self.assertEqual(json.loads((root/'current.json').read_text())['version'],'0.2.99')
    def test_saved_port_reused(self):
        from valuation_agent.browser_app import launch
        with tempfile.TemporaryDirectory() as temp:
            cfg=Path(temp)/'remote.json'
            (cfg.parent/'workbench-port.json').write_text('{"port":59067}')
            with patch('valuation_agent.browser_app.HTTPServer') as server:
                server.return_value.server_port=59067
                launch(cfg,no_browser=True)
                self.assertEqual(server.call_args.args[0],('127.0.0.1',59067))
