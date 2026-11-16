import unittest
from valuation_agent.completeness import assess
class CompletenessTests(unittest.TestCase):
 def test_empty_is_not_absent(self):
  self.assertEqual(assess({})['status'],'source_review_required')
  self.assertEqual(assess({'image_evidence':[{}]})['status'],'image_review_required')
 def test_design_note_is_not_dimension(self):
  self.assertEqual(assess({'spec':'依据模型深化'})['status'],'design_pending')
 def test_confirmed_absence_requires_review(self):
  self.assertEqual(assess({'spec_review':{'status':'confirmed_absent','evidence':'原页及附图'}})['status'],'confirmed_absent')
