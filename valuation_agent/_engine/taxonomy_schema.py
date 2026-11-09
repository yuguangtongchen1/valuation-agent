"""Read quotation-template metadata; never turn template placeholders into history.

Category IDs are stable independently of display names or variable path depth.
Legacy codes are candidate-routing hints, never item/price equivalence assertions.
Draft-only categories are opt-in and cannot silently override formal templates.
"""
from pathlib import Path
import json


def load_schema(path):
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('source_role') != 'taxonomy_template_only':
        raise ValueError('Expected template-only taxonomy metadata')
    if payload.get('not_historical_transaction_data') is not True:
        raise ValueError('Template must be explicitly excluded from price history')
    seen = set()
    for category in payload.get('categories', []):
        key = category.get('id')
        path = category.get('path')
        if not key or key in seen:
            raise ValueError('Missing or duplicate stable category ID: %r' % key)
        if not isinstance(path, list) or not path or any(not isinstance(p, str) or not p.strip() for p in path):
            raise ValueError('Category path must contain nonempty names: %r' % key)
        if category.get('depth', len(path)) != len(path):
            raise ValueError('Category depth does not match source path: %r' % key)
        if not category.get('source_refs'):
            raise ValueError('Category needs source references: %r' % key)
        seen.add(key)
    return payload


def categories(schema, include_draft=False):
    """Return metadata only; unlike historical quote records it has no prices."""
    return [c for c in schema.get('categories', [])
            if include_draft or c.get('status') != 'draft_only']


def category_index(schema, include_draft=False):
    return {c['id']: c for c in categories(schema, include_draft)}


def compatible_legacy_categories(schema, code, include_draft=False):
    """An old code can map to several new scopes (e.g. finish vs graphics)."""
    return [c for c in categories(schema, include_draft)
            if code in c.get('legacy_codes', [])]


def requirements(category):
    """Keep source-explicit fields distinct from proposed comparison controls."""
    return {
        'source_explicit': list(category.get('source_explicit_required_fields', [])),
        'comparison_proposed': list(category.get('comparison_required_fields_proposed', [])),
        'unit_options_source': list(category.get('billing_units_explicit', [])),
        'included_scopes': list(category.get('includes', [])),
        'excluded_scopes_proposed': list(category.get('excludes_for_matching', [])),
        'source_refs': list(category.get('source_refs', [])),
    }


def classification_tree(schema, include_draft=False):
    """Variable-depth tree, preserving repeated source paths as separate IDs."""
    root = {'name': None, 'children': {}, 'category_ids': []}
    for category in categories(schema, include_draft):
        node = root
        for name in category['path']:
            node = node['children'].setdefault(name, {'name': name, 'children': {}, 'category_ids': []})
        node['category_ids'].append(category['id'])
    return root


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('schema', type=Path)
    parser.add_argument('--include-draft', action='store_true')
    args = parser.parse_args()
    schema = load_schema(args.schema)
    selected = categories(schema, args.include_draft)
    print(json.dumps({'category_count': len(selected), 'tree': classification_tree(schema, args.include_draft),
                      'history_eligible': False}, ensure_ascii=False, indent=2))

# These route actual row-level wording into the supplied template definitions.
# A match selects a scope for review; it does not establish price equivalence.
import re
PATTERNS = {
 'mc.design':r'设计深化|方案设计|造型深化|外形比例',
 'mc.technical':r'技术深化|施工图|加工图|生产拆图|安装节点图',
 'mc.structural_report':r'结构计算|结构验算|结构报告|计算书',
 'mc.structure':r'地台基础|圆地台|钢结构|主支持结构|承重|支撑骨架|固定件|底座',
 'mc.finish':r'地台面|地胶|地板|饰面|收口|包边|涂装|烤漆',
 'mc.planar_graphics':r'背胶喷绘|喷绘布|写真|平面物料|海报|画面制作',
 'mc.custom_form':r'雕塑|定制造型|异形外壳|展具|玻璃钢|道具|展柜',
 'mc.furniture':r'家具|沙发|布艺|窗帘|绿植|花艺|节庆装饰',
 'mc.luminaire':r'灯具|灯带|星星灯|星形灯|灯控网线|装置专用电源|灯光编程',
 'mc.functional_equipment':r'显示屏|电视机|投影|服务器|电脑|互动设备|发送卡|处理器',
 'mc.public_power':r'公共电|配电箱|总配电|强电|电缆|线槽',
 'mc.central_control':r'中控|中央控制|总控系统',
 'mc.sample':r'打样|试制|材料色样', 'mc.prefab':r'预搭|预拼装|试搭',
 'mc.install_labor':r'安装人工|搭建人工|施工人工', 'mc.dismantle_labor':r'拆除人工|撤场人工|拆卸人工',
 'mc.machinery':r'吊车|叉车|剪叉|曲臂车|升降车',
 'mc.freight':r'运输|货运|包装费|物流', 'mc.travel':r'差旅|人员交通|住宿|机票|餐补',
 'mc.insurance':r'保险|责任险', 'mc.enclosure':r'围挡|围蔽',
 'mc.protection':r'地面保护|现场保护|成品保护', 'mc.cleaning':r'保洁|清洁',
 'mc.waste':r'垃圾|清运', 'mc.maintenance':r'展期维护|展期值班|驻场|巡检',
 'cg.scene_model':r'场景.*(?:建模|模型|资产)|模型搭建|场景资产',
 'cg.character_model':r'(?:角色|人物|ip).*(?:建模|模型|骨骼绑定)',
 'cg.scene_animation':r'场景动画|镜头动态轨迹|镜头动画',
 'cg.character_animation':r'角色动画|角色动态|动作制作|动物.*轨迹',
 'cg.lookdev':r'材质.*灯光|灯光.*渲染|三渲二|材质制作',
 'cg.render':r'渲染', 'cg.fx':r'特效', 'cg.grade_package':r'调色|后期包装|后期制作',
 'cg.screen_unfold':r'展开反求|上屏.*适配|裸眼.*适配|裸3.*展开|屏幕反求',
 'cg.composite_output':r'合成输出|最终输出|渲染输出',
}


def applicable_categories(schema, name, detail=''):
    name,detail=str(name or '').lower(),str(detail or '').lower()
    if '/' in name and len(detail) >= 8:
        from semantic_profile import digital_path
        if digital_path('', detail):
            name = ''
    ai_only = bool(re.search(r'\bai', name))
    available=category_index(schema)
    found=[]
    for key,pattern in PATTERNS.items():
        if ai_only and key.startswith('cg.'):
            continue
        if key in available and re.search(pattern,name+' '+detail):
            score=2 if re.search(pattern,name) else 1
            # Render is an explicit worker stage, not a replacement for lookdev/output.
            if key=='cg.render' and re.search(r'材质|灯光|合成输出|渲染输出',name+' '+detail):score=0
            found.append((score,len(available[key]['path']),available[key]))
    # Template-specific named staff/equipment rows remain scopes, not historical prices.
    for category in available.values():
        if not category['id'].startswith('photo.') or len(category['path']) < 3:
            continue
        leaf=category['path'][-1].lower()
        aliases=re.findall(r'[\u4e00-\u9fff]{2,}|[a-z][a-z0-9-]*(?:[ /][a-z0-9-]+)*',leaf)
        aliases=[re.sub(r'\s+',' ',a).strip() for a in aliases]
        aliases=[a for a in aliases if a not in {'fee','other','misc','cost','staff','equipment'}]
        if any(a == name.strip() or (len(a)>=3 and (a in name if re.search(r'[\u4e00-\u9fff]', a) else re.search(r'(?<![a-z0-9])' + re.escape(a) + r'(?![a-z0-9])', name))) for a in aliases):
            found.append((3,len(category['path']),category))
    found.sort(key=lambda x:(-x[0],-x[1]))
    return [category for _,_,category in found]
