import unittest
from valuation_agent.engine import modules

class SourceLinks(unittest.TestCase):
    def test_attachment_identity_and_type_required(self):
        w=modules()['workbench']; token='AbCdEfGhIjKlMnOpQrStUvWx'
        row={'source_token':token}
        self.assertIsNone(w.original_document_url(row, {}))
        self.assertIsNone(w.original_document_url(row, {'attachments':[{'token':'other','type':12}]}))
        self.assertTrue(w.original_document_url(row, {'attachments':[{'token':token,'type':12}]}).endswith('/file/'+token))
        self.assertTrue(w.original_document_url(row, {'attachments':[{'token':token,'type':'docx'}]}).endswith('/docx/'+token))
    def test_explicit_original_link_survives(self):
        w=modules()['workbench'];url='https://example.feishu.cn/wiki/OriginalNode'
        self.assertEqual(w.original_document_url({'source_url':url},{}),url)
        self.assertIsNone(w.original_document_url({'source_url':'javascript:alert(1)'},{}))
