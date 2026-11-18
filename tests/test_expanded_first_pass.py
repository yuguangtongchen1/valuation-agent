import unittest
from unittest.mock import patch
from pathlib import Path
from valuation_agent.engine import modules

class ExpandedFirstPass(unittest.TestCase):
    def test_whole_pass_precedes_components_and_keeps_every_result(self):
        w=modules()['workbench']; calls=[]
        def search(*args, **kwargs):
            calls.append(kwargs)
            if kwargs.get('component'):
                self.assertNotIn('spec', args[5])
                self.assertNotIn('description', args[5])
                self.assertEqual(kwargs['omit'], {str(i) for i in range(9)})
                return [{'line_id':'part','item_name':'灯带','component_name':'LED灯','comparison_role':'component'}]
            return [{'line_id':str(i),'item_name':'圆环灯','comparison_role':'candidate'} for i in range(9)]
        with patch.object(w,'priced_references',side_effect=search), patch.object(w,'quoted_components',return_value=[('LED灯',(4,'段'))]):
            result=w.lookup(Path('.'),[],{}, {}, {}, {'name':'圆环灯','unit':'项','spec':'整灯直径3米','description':'含灯架'},False)
        self.assertNotIn('component',calls[0])
        self.assertEqual(len(result['references']),10)
        self.assertEqual([r['match_rank'] for r in result['references']],list(range(1,11)))
        self.assertEqual(result['references'][-1]['match_points'],['匹配子项：LED灯'])
