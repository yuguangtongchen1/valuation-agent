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
 def test_conflict_status_is_forwarded_without_private_review_payload(self):
  sent=[]
  def call(action,payload,config):
   sent.append(payload)
   return {'rows':[{'quote':r,'references':[]} for r in payload['document']['rows']]}
  row={'item_name':'圆环灯','spec':'3500mm / 3520',
       'spec_review':{'status':'source_conflict','private_note':'not transmitted'}}
  with patch('valuation_agent.remote.remote_call',call):remote_compare({'rows':[row]},'config')
  query=sent[0]['document']['rows'][0]
  self.assertEqual(query['spec_status'],'source_conflict')
  self.assertEqual(query['spec'],'3500mm / 3520')
  self.assertNotIn('spec_review',query)
  self.assertNotIn('private_note',str(sent))
if __name__=='__main__':unittest.main()
