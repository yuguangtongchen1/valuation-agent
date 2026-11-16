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
    def test_exact_attachment_precedes_contract_level_link(self):
        w=modules()['workbench']; token='B'*20
        record={'contract_url':'https://example.feishu.cn/file/'+('A'*20),
                'attachments':[{'token':token,'type':'docx'}]}
        self.assertTrue(w.original_document_url({'source_token':token},record).endswith('/docx/'+token))
        self.assertIsNone(w.original_document_url({'source_token':'C'*20},record))
        self.assertEqual(w.original_document_url({},record),record['contract_url'])
    def test_attachment_explicit_url_supports_linked_source(self):
        w=modules()['workbench'];url='https://example.feishu.cn/wiki/LinkedOriginal'
        record={'attachments':[{'token':'known-id','url':url}]}
        self.assertEqual(w.original_document_url({'source_token':'known-id'},record),url)
