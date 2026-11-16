"""Evidence bounded completeness checks; never infer absence from extraction failure."""
import re

def assess(row):
    spec=str(row.get('spec') or row.get('dimensions') or '').strip()
    images=row.get('image_evidence') or []
    if re.search(r'依据模型深化|待设计|待深化',spec):
        return {'status':'design_pending','label':'待设计确定','reason':spec}
    if spec and spec not in ('—','-'):
        return {'status':'provided','label':'已有规格','reason':row.get('spec_basis') or '已提取规格；按来源复核'}
    if row.get('spec_review',{}).get('status')=='confirmed_absent':
        return {'status':'confirmed_absent','label':'原件未注明','reason':row['spec_review'].get('evidence','')}
    return {'status':'image_review_required' if images else 'source_review_required',
            'label':'待核图片规格' if images else '待核原件规格',
            'reason':'提取结果为空，不代表原件没有规格'}
