import unittest
from unittest.mock import patch
from valuation_agent.cli import remote_compare
class RemoteCli(unittest.TestCase):
 def test_chunking_and_only_query_fields(self):
  requests=[]
  def call(action,payload,config):
   requests.append(payload);return {'rows':[{'quote':r,'references':[]}for r in payload['document']['rows']]}
  doc={'rows':[{'item_name':'灯','source_original_fields':{'secret':'no'},'supplier_contact':'private','unit_price':'10'}for _ in range(41)]}
  with patch('valuation_agent.remote.remote_call',call):out=remote_compare(doc,'config')
  self.assertEqual(len(out['rows']),41);self.assertEqual([len(x['document']['rows'])for x in requests],[20,20,1]);self.assertNotIn('secret',str(requests));self.assertNotIn('supplier_contact',str(requests));self.assertEqual(out['rows'][0]['quote']['unit_price'],'10')
if __name__=='__main__':unittest.main()
