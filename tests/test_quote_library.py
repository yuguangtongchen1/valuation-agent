import copy
import tempfile
import unittest
from pathlib import Path
from valuation_agent.quote_library import ingest, export, unit_price

class QuoteLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.db=Path(self.tmp.name)/'offers.sqlite'
        self.doc={'project':'测试项目','source_sha256':'a'*64,'source_url':'https://example.test/quote',
                  'rows':[{'line_id':'one','item_name':'灯具组合','supplier':'供应商甲','supplier_basis':'原表抬头',
                           'record_role':'quote_line','source_locator':'报价!A3','subtotal':'100',
                           'record_status':'confirmed','purchase_executed':True}]}
    def tearDown(self):self.tmp.cleanup()
    def test_idempotent_and_no_status_promotion(self):
        ingest(self.doc,self.db)
        self.assertTrue(ingest(self.doc,self.db)['already_present'])
        rows=export(self.db,'供应商甲')['rows'];self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['record_status'],'supplier_quotation')
        self.assertFalse(rows[0]['purchase_executed'])
    def test_revisions_not_duplicate_active_and_self_excluded(self):
        ingest(self.doc,self.db);other=copy.deepcopy(self.doc);other['rows'][0]['subtotal']='120'
        ingest(other,self.db)
        self.assertEqual(export(self.db)['rows'][0]['subtotal'],'120')
        self.assertEqual(export(self.db,exclude_source=self.doc['source_url'])['rows'],[])
    def test_reference_export_requires_current_source(self):
        ingest(self.doc,self.db)
        with self.assertRaises(ValueError):export(self.db,references_only=True)

    def test_old_reimport_does_not_reactivate(self):
        ingest(self.doc,self.db)
        new=copy.deepcopy(self.doc);new['rows'][0]['subtotal']='200'
        ingest(new,self.db);ingest(self.doc,self.db)
        self.assertEqual(export(self.db)['rows'][0]['subtotal'],'200')

    def test_sharing_urls_hash_copies_and_versions(self):
        self.doc['source_url']='https://tenant.feishu.cn/file/ABC?from=from_copylink'
        self.doc['quotation_family_id']='quote-001'
        ingest(self.doc,self.db)
        self.assertEqual(export(self.db,exclude_source='https://tenant.feishu.cn/file/ABC')['rows'],[])
        duplicate=copy.deepcopy(self.doc);duplicate['source_url']='https://tenant.feishu.cn/file/COPY'
        ingest(duplicate,self.db)
        self.assertEqual(export(self.db,exclude_source=self.doc['source_url'])['rows'],[])
        newer=copy.deepcopy(self.doc);newer['source_url']='https://tenant.feishu.cn/file/NEW';newer['source_sha256']='b'*64
        newer['rows'][0]['subtotal']='300';ingest(newer,self.db)
        self.assertEqual(len(export(self.db)['rows']),1)
        self.assertEqual(export(self.db)['rows'][0]['subtotal'],'300')
        self.assertEqual(export(self.db,exclude_source=self.doc['source_url'])['rows'],[])

    def test_compare_guard_expands_source_to_whole_family(self):
        from valuation_agent.source_identity import exclude_current_sources
        rows=[{'source_url':'https://tenant.feishu.cn/file/ABC?from=copy','quotation_family_id':'Q','source_sha256':'a'},
              {'source_url':'https://tenant.feishu.cn/file/NEW','quotation_family_id':'Q','source_sha256':'b'},
              {'source_url':'https://tenant.feishu.cn/file/COPY','source_sha256':'a'},
              {'source_url':'https://tenant.feishu.cn/file/OTHER','source_sha256':'c'}]
        selected=exclude_current_sources(rows,{'source_url':'https://tenant.feishu.cn/file/ABC','rows':[]})
        self.assertEqual(selected,[rows[-1]])

    def test_compare_cannot_use_its_own_newly_imported_quote(self):
        import json
        from valuation_agent.service import compare
        self.doc['rows'][0].update(comparable_price=True,quantity='1',unit='套',unit_price='100',currency='CNY')
        ingest(self.doc,self.db)
        history=Path(self.tmp.name)/'history.json'
        history.write_text(json.dumps(export(self.db),ensure_ascii=False))
        result=compare(self.doc,history=history)
        self.assertEqual(result['rows'][0]['references'],[])

    def test_price_factors_and_missing(self):
        self.assertEqual(unit_price('2500','5','2'),'250.00')
        self.assertEqual(unit_price('9540','1'),'9540.00')
        self.assertEqual(unit_price('1','3'),'0.33')
        self.assertIsNone(unit_price('100',None))
        self.assertIsNone(unit_price('100','0'))
    def test_orphan_and_supplier_evidence_rejected(self):
        self.doc['rows'][0]['parent_line_id']='missing'
        with self.assertRaises(ValueError):ingest(self.doc,self.db)
        del self.doc['rows'][0]['parent_line_id'];del self.doc['rows'][0]['supplier_basis']
        with self.assertRaises(ValueError):ingest(self.doc,self.db)
if __name__=='__main__':unittest.main()
