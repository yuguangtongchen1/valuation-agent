"""Source-linked catalogue aliases for discovering independently priced references."""
from collections import defaultdict
import json
import re

from quote_classification import billing_unit
from valuation import norm
from taxonomy_schema import load_schema, applicable_categories

# Each group describes a deliverable, rather than a broad shared material or process.
IDENTITIES = (
    ('发光字', '2.5', r'发光字|发光店招|背发光招牌|发光亚克力logo|亚克力无边发光'),
    ('结构计算与报告', '1.3', r'结构计算|结构验算|承重验算|结构安全计算'),
    ('施工围挡', '3.10', r'施工围挡|^围挡$|施工隔挡|工地隔挡'),
    ('投影设备', '2.7', r'投影机|投影仪|工程投影'),
    ('表面覆贴', '2.2', r'地台面|地胶|地贴|pp背胶'),
    ('物料货运', '3.7', r'^运输(?:费)?$|货物运输|物料运输|物料货运|展品运输'),
    ('三维动画', '4.3', r'三维动画|三维动效|3d动画|cg动画'),
    ('视频剪辑', '4.4', r'视频剪辑|影片剪辑|素材剪辑|视频剪接'),
    ('素材拍摄', '4.2', r'拍摄视频及照片|视频及照片素材拍摄|视频与照片拍摄|视频和照片拍摄'),
)
COMPILED_IDENTITIES = [(label, parent, re.compile(pattern)) for label, parent, pattern in IDENTITIES]
ROLE_EXCLUSION = re.compile(r'底座|包边|收口|吊架|支架|遮挡|控制器|辅材|运维|拆卸|搬运|折扣|喷绘布|材料$')
PACKAGED_NAME = re.compile(r'[+＋]|合包|整包|套餐|(?<!不)及人员交通|整项')


def identity(name, detail=''):
    name = norm(name)
    if ROLE_EXCLUSION.search(name) or PACKAGED_NAME.search(name):
        return None
    text = f'{name} {norm(detail)}'.strip()
    found = {(label, parent) for label, parent, pattern in COMPILED_IDENTITIES
             if pattern.search(name) or pattern.search(text)}
    return next(iter(found)) if len(found) == 1 else None


class ReferenceCatalog:
    def __init__(self, root, rows):
        self.template_schema = load_schema(root/'catalog/template-v2.json') if (root/'catalog/template-v2.json').exists() else None
        self.entries = {}
        self.aliases = defaultdict(list)
        catalog = root / 'catalog'
        if not (catalog / 'classification.json').is_file() or not (catalog / 'project-bom.json').is_file():
            return
        categories = json.loads((catalog / 'classification.json').read_text())['categories']
        category_by_id = {category['id']: tuple(category['path']) for category in categories}
        prices = {row.get('line_id'): row for row in rows}
        dataset = json.loads((catalog / 'project-bom.json').read_text())
        for project in dataset['projects']:
            for contract in project['contracts']:
                for line in contract['lines']:
                    line_id = line.get('line_id')
                    source = prices.get(line_id)
                    if (line.get('kind') != 'bom_line' or not source or source['record_id'] != contract['record_id']
                            or source['project_key'] != project['id']
                            or norm(source['item_name']) != norm(line['item_name'])):
                        continue
                    category_id = line['category_id']
                    path = category_by_id.get(category_id)
                    if not path or category_id == '待核':
                        continue
                    parent = '.'.join(category_id.split('.')[:2])
                    self.entries[line_id] = (parent, path)
                    detail = ' '.join(str(value or '') for value in (source.get('spec'), source.get('description'),
                                                                    line.get('description'), line.get('specification')))
                    tagged = identity(source['item_name'], detail)
                    if tagged and tagged[1] == parent:
                        self.aliases[tagged].append(source)

    def candidates(self, query):
        tagged = identity(query['name'], ' '.join(norm(query.get(field)) for field in ('description', 'spec', 'configuration')))
        if not tagged:
            return []
        label, _ = tagged
        unit = billing_unit(norm(query.get('unit')))
        if not unit:
            return []
        return [(row, label, self.entries[row['line_id']][1]) for row in self.aliases.get(tagged, [])
                if billing_unit(norm(row['unit'])) == unit]


def template_context(catalog, row, name_key='name'):
    if not catalog or not catalog.template_schema:
        return []
    detail=' '.join(str(row.get(key) or '') for key in ('description','spec','configuration'))
    return [{'id':c['id'],'path':c['path'], 'included_scopes':c['includes'],
             'excluded_scopes':c['excludes_for_matching'],
             'source_explicit_required_fields':c.get('source_explicit_required_fields',[]),
             'comparison_fields_proposed':c.get('comparison_required_fields_proposed',[]),
             'source_refs':c['source_refs']}
            for c in applicable_categories(catalog.template_schema,row.get(name_key),detail)]
