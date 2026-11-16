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
 def test_source_conflict_takes_priority_over_present_dimensions(self):
  row={'spec':'报价直径3500mm；图纸外径3520',
       'spec_review':{'status':'source_conflict','evidence':'图号4.a.5'}}
  result=assess(row)
  self.assertEqual(result['status'],'source_conflict')
  self.assertEqual(result['reason'],'图号4.a.5')
  self.assertEqual(row['spec'],'报价直径3500mm；图纸外径3520')
 def test_source_conflict_without_note_keeps_original_values(self):
  self.assertEqual(assess({'spec':'3300mm / 3325',
    'spec_review':{'status':'source_conflict'}})['reason'],'3300mm / 3325')
