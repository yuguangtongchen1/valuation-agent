import os
"""Read-only, source-prioritized adapter for the quotation workbench."""
import argparse
import base64
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
from subprocess import TimeoutExpired, run
import sys
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse
from zipfile import ZipFile

from estimate import call, column
from quote_classification import (billing_unit, bundled_evidence, comparable_class, process_reference, projection_purchase_role,
                                  process_terms, quote_classification)
from quote_parameters import parameter_comparison, parameter_text_only, parameters, normalize_specification_text
from reference_catalog import ReferenceCatalog, template_context
from semantic_profile import models, actions, classification_trace, scope_text, inspect_input
from valuation import is_checked, load, norm, positive, reference, rejection, price_role_block, view_only_variant

TABLE_URL = os.environ.get('VALUATION_AGENT_FEISHU_TABLE_URL', '')
GITHUB = os.environ.get('VALUATION_AGENT_SOURCE_BASE_URL', '')
YEARS = ('2024', '2025', '2026')
DEMO_NAMES = ('三维动画', '三维渲染师', '制片')


def table_fallback(phrase):
    if not TABLE_URL:
        return [], False
    def find(year):
        try:
            result = call('sheets', '+cells-search', '--url', TABLE_URL, '--sheet-name', year,
                          '--find=' + phrase, '--range', 'A2:N1100', '--max-matches', '8')
        except (RuntimeError, OSError, TimeoutExpired, ValueError, KeyError):
            return [], False
        out = []
        seen = set()
        for hit in result.get('matches', []):
            address = str(hit.get('address', ''))
            row = re.search(r'\d+$', address)
            if row and row[0] not in seen:
                seen.add(row[0])
                out.append({'kind': 'ledger_match', 'sheet': year, 'address': address,
                            'value': str(hit.get('value', ''))[:160], 'url': TABLE_URL})
        return out, True

    with ThreadPoolExecutor(max_workers=len(YEARS)) as pool:
        results = list(pool.map(find, YEARS))
    return [row for rows, _ in results for row in rows], all(ok for _, ok in results)

FAMILIES = (
    ('导演', '导演费', 'director'),
    ('摄影师', '摄影指导', 'dop'),
    ('摄影助理', '跟焦员', 'focus puller'),
    ('化妆师', '化妆费', 'makeup'),
    ('显示屏', 'led屏', '柱屏', '大屏', '拼接屏', '屏体'),
    ('播放服务器', '媒体服务器', '工控机', '工业计算机'),
    ('发光字', '发光标识', '灯箱字'),
    ('投影机', '投影仪'),
    ('灯带', '软灯条', '线性灯条'),
    ('钢结构', '钢架', '金属骨架'),
    ('玻璃钢造型', '玻璃钢道具', '玻璃钢雕塑'),
    ('亚克力字', '亚克力标识', '亚克力标牌'),
    ('三维动画', '3d动画', 'cg动画'),
    ('星星灯', '星形灯', '星型灯'),
    ('灯珠', '发光二极管'),
    ('吊灯', '吊挂灯具'),
    ('物料运输', '运输费', '运输'),
    ('人员交通', '人员差旅', '搭建差旅', '安装差旅'),
    ('人员搭建', '安装人工', '工厂试搭', '搭建人工'),
    ('升降车', '曲臂车', '高空作业车', '提升车'),
)
ACCESSORY = re.compile(r'包边|收口|支架|处理器|控制器|发送卡|接收卡|配电|电源|控制卡|连接件|辅材|钢结构')
MATERIALS = (
    ('玻璃钢', 'frp'), ('亚克力', '有机玻璃'), ('不锈钢', '304钢'),
    ('泡沫雕刻', '泡沫板', 'eps雕刻'), ('雪弗板', '雪佛板', 'pvc发泡板'),
    ('喷绘布', '刀刮布'), ('多层板', '夹板', '胶合板'),
)
REFERENCE_MATERIALS_AND_PROCESSES = (*MATERIALS, ('烤漆', '喷漆'))
SPEC_MATERIALS = (*MATERIALS, ('钢结构', '钢架', '钢方通', '方钢', '铁管', '镀锌方管'),
                  ('钢木结构',), ('金属',), ('PC板', 'pc板'), ('铝塑板',), ('铝合金',), ('pvc',), ('pp背胶',))
SCOPE_PARTS = {
    '设计': r'设计|策划', '制作': r'制作|加工|定制', '供货': r'供货|设备采购|购买|购置|网购|\bsupply\b|\bpurchase\b',
    '安装': r'安装|搭建|试搭|预搭', '调试': r'调试|测试', '运输': r'运输|运费',
    '拆除': r'拆除|撤场', '运维': r'运维|维护', '租赁': r'租赁|租用|租金|\brental\b|\brent\b|\bhire\b',
    '建模': r'建模|模型制作', '绑定': r'绑定',
    '动画': r'动画', '渲染': r'渲染', '剪辑': r'剪辑', '特效': r'特效',
}
@lru_cache(maxsize=32768)
def light_subtype(name):
    return next((key for key, terms in (
        ('星形灯', ('星星灯', '星形灯', '星型灯')), ('灯带', ('灯带', '灯条')),
        ('灯珠', ('灯珠',)), ('花灯', ('花灯',)), ('吊灯', ('吊灯',)),
    ) if any(term in name for term in terms)), '')


@lru_cache(maxsize=32768)
def scope_parts(value):
    included, excluded = set(), set()
    for phrase in re.split(r'[，,；;。+＋]|、(?=含|包含|不含|不包括|另计)', value):
        target = excluded if re.search(r'不含|不包含|不包括|不负责|不提供|不做|无需|另计', phrase) else included
        target.update(part for part, pattern in SCOPE_PARTS.items() if re.search(pattern, phrase))
    return frozenset(included - excluded), frozenset(excluded)


@lru_cache(maxsize=32768)
def specification(value):
    return re.sub(r'\s+', '', normalize_specification_text(norm(value))).replace('×', 'x').replace('*', 'x')


@lru_cache(maxsize=32768)
def informative_spec(value):
    return bool(value and not re.fullmatch(r'(?:定制|按需定制|通用|标准|无|未注明|详见图纸|见图|n/?a)[。.]?', value))


@lru_cache(maxsize=32768)
def material_terms(value):
    return {group[0]: next(term for term in group if term in value).replace('pvc', 'PVC').replace('pp背胶', 'PP背胶')
            for group in SPEC_MATERIALS if any(term in value for term in group)}


@lru_cache(maxsize=32768)
def expense_parts(value):
    return {label for label, pattern in (
        ('人工', r'人工|电工|安装|搭建|调试'), ('交通', r'机票|往返|交通'),
        ('住宿', r'住宿|酒店|食宿|餐住'), ('运输', r'运费|运输'),
        ('餐食', r'伙食|餐费|餐饮|食宿|餐住')) if re.search(pattern, value)}


def semantic_name(row, name_key):
    attrs = row.get('source_attributes') or {}
    return norm(row.get('standard_object_name') or row.get('standard_service_name')
                or attrs.get('standard_object_name') or attrs.get('standard_service_name')
                or row.get(name_key))


def line_classification(row, name_key, context_keys):
    return quote_classification(semantic_name(row, name_key), ' '.join(norm(row.get(key)) for key in context_keys))


def reference_pool(rows, allow_pending=False):
    """Reference retrieval includes source-reviewed package totals, not only unit prices."""
    pool = []
    for row in rows:
        attrs = row.get('source_attributes') or {}
        if row.get('kind') not in ('bom_line', 'whole_scope_quote'):
            continue
        user_pending = allow_pending and row.get('record_status') == 'user_history_pending_review'
        if not (is_checked(row) or row.get('source_fields_reviewed') or user_pending) or price_role_block(row):
            continue
        # Explicit duplicate evidence remains in contract detail, not a new quote sample.
        if attrs.get('duplicate_quote_reference_only'):
            continue
        scoped_out = (row.get('scope_association_pending') or row.get('comparison_eligible') is False)
        if scoped_out and not view_only_variant(row):
            continue
        if ((positive(row.get('unit_price')) and row.get('unit'))
                or positive(row.get('subtotal')) or positive(row.get('subtotal_finance_cny_yuan'))):
            pool.append(row)
    return pool


def pending_price_index(rows):
    index = defaultdict(dict)
    for row in rows:
        if row['kind'] != 'bom_line' or is_checked(row) or not row.get('unit') or not positive(row.get('unit_price')):
            continue
        path = line_classification(row, 'item_name', ('item_name', 'spec', 'description', 'module'))
        if path:
            index[(path, billing_unit(norm(row['unit'])))][row['record_id']] = row['item_name']
    return index


def source_name_index(rows):
    index = defaultdict(set)
    for row in rows:
        if row['kind'] == 'bom_line' and row.get('item_name'):
            index[norm(row['item_name'])].add(row['record_id'])
    return index


@lru_cache(maxsize=32768)
def _family_terms(name):
    return tuple((index, term) for index, group in enumerate(FAMILIES)
                 for term in group if term in name)


@lru_cache(maxsize=32768)
def _family_match(name, past):
    return max(((a, b) for ai, a in _family_terms(name) for bi, b in _family_terms(past)
                if ai == bi), key=lambda pair: len(pair[0]) + len(pair[1]), default=None)


def relationship(query, row, catalog_match=None):
    name, past = norm(query['name']), norm(row['item_name'])
    current_projection_role, historical_projection_role = projection_purchase_role(name), projection_purchase_role(past)
    if current_projection_role and historical_projection_role and current_projection_role != historical_projection_role:
        return None
    model = norm(query.get('model'))
    past_model = norm(row.get('model'))
    spec, past_spec = specification(query.get('spec')), specification(row.get('spec'))
    config = norm(query.get('configuration'))
    context = ' '.join((name, norm(query.get('spec')), norm(query.get('description')), config))
    historical_details = ' '.join((past, norm(row.get('spec')), norm(row.get('description'))))
    current_removal = bool(re.search(r'拆除|拆卸|撤场', context))
    historical_removal = bool(re.search(r'拆除|拆卸|撤场', past))
    if historical_removal and not current_removal:
        return None
    historical = f'{historical_details} {norm(row.get("module"))}'
    current_models = models(' '.join((model, context)))
    historical_models = models(' '.join((past_model, historical_details)))
    def explicit_model_code(value):
        return bool(re.search(r'[a-z]', value) and (re.search(r'\d', value) or '-' in value)
                    and not re.fullmatch(r'p\d+(?:\.\d+)?(?:mm)?', value)
                    and not re.fullmatch(r'(?:[lwh]\d+(?:mm|cm|m)?[x×*]?)+', value))
    if explicit_model_code(model):
        current_models.add(model.upper())
    if explicit_model_code(past_model):
        historical_models.add(past_model.upper())
    current_path = quote_classification(semantic_name(query, 'name'), context)
    historical_path = quote_classification(semantic_name(row, 'item_name'), f'{historical_details} {norm(row.get("module"))}')
    if (current_path[:2] == ('数字内容与技术服务', '输出适配')
            and re.search(r'策划|制片|导演|项目管理|制作统筹', past)
            and not re.search(r'适配|反求|展开|楼体|多屏', historical_details)):
        return None
    class_match = comparable_class(current_path, historical_path, name, past)
    bundle_reason = bundled_evidence(current_path, historical_path)
    labor_partial = bool(re.search(r'电箱|电缆|配电', context) and past == '电工')
    catalog_bridge = bool(catalog_match and not (current_path and historical_path))
    hardware_paths = (current_path[:2] == ('展陈物料', '多媒体硬件')
                      or current_path[:2] == ('源字段分级', '2.7'))
    current_brand, historical_brand = norm(query.get('brand')), norm(row.get('brand'))
    generic_brands = {'', '国产', '定制', '通用', '无', '/', '未注明'}
    brand_conflict = bool(hardware_paths and current_brand not in generic_brands
                          and historical_brand not in generic_brands and current_brand != historical_brand)
    same_model = bool(current_models and historical_models and current_models == historical_models and not brand_conflict)
    digital_related = bool(current_path and historical_path and current_path[0] == historical_path[0] == '数字内容与技术服务'
                           and (current_path[1] == historical_path[1] or '数字内容制作' in (current_path[1], historical_path[1]) or actions(context) & actions(historical_details)))
    same_spec = bool(informative_spec(spec) and spec == past_spec)
    family = _family_match(name, past)
    near = min(len(name), len(past)) >= 3 and (name in past or past in name)
    current_type, historical_type = light_subtype(name), light_subtype(past)
    if not same_model and current_type and historical_type and current_type != historical_type:
        return None
    separate_classes = bool(current_path or historical_path) and not (class_match or bundle_reason)
    current_processes, historical_processes = process_terms(context), process_terms(historical_details)
    shared_processes = current_processes & historical_processes
    model_bridge = same_model and bool(current_path) != bool(historical_path)
    if separate_classes and not (model_bridge or catalog_bridge or digital_related or labor_partial) and (not current_path or not historical_path or current_path[:3] != historical_path[:3]):
        return None
    if not (same_model or class_match or bundle_reason or separate_classes or catalog_bridge) and bool(ACCESSORY.search(name)) != bool(ACCESSORY.search(past)):
        return None
    current_parameters = parameters(norm(query.get('spec')), norm(query.get('dimension_unit')))
    for label, values in parameters(' '.join((name, norm(query.get('description')), config))).items():
        current_parameters.setdefault(label, {}).update(values)
    compared = parameter_comparison(current_parameters, parameters(historical))
    same_parameters = bool(compared and all(p['current'] and p['historical'] and not p['different'] for p in compared))
    equivalent_specs = same_parameters and parameter_text_only(spec) and parameter_text_only(past_spec)
    requested, requested_exclusions = scope_parts(context)
    offered, offered_exclusions = scope_parts(historical)
    current_rental, historical_rental = '租赁' in requested, '租赁' in offered
    transaction_difference = ''
    if current_rental != historical_rental:
        explicit_supply = {'制作', '供货'}
        if current_rental and offered & explicit_supply:
            transaction_difference = '交易方式不同（当前：租赁；历史：制作或供货）'
        elif historical_rental and requested & explicit_supply:
            transaction_difference = '交易方式不同（当前：制作或供货；历史：租赁）'
        else:
            transaction_difference = ('当前为租赁，历史交易方式未注明' if current_rental else
                                      '历史为租赁，当前交易方式未注明')
    attrs = row.get('source_attributes') or {}
    exact_source_names = [source.get('name') for source in row.get('contract_sources', [])
                          if source.get('token') == row.get('source_token')]
    source_scope_title = ' '.join(norm(value) for value in
                                 (row.get('work_package'), row.get('contract_name'), row.get('module'),
                                  attrs.get('contract_name'), attrs.get('source_scope_title'), *exact_source_names))
    ambiguous_removal_scope = bool(not current_removal and re.search(r'撤场|拆除|拆卸', source_scope_title)
                                  and not historical_rental and not scope_parts(historical_details)[0])

    components = [part.strip() for part in re.split(r'[、+，,；;]|搭配', config) if len(part.strip()) >= 2]
    explicit_bundle = len(components) > 1
    same_bundle = (all(part in historical for part in components) if explicit_bundle
                   else len(requested) > 1 and requested == offered)
    differences = [transaction_difference] if transaction_difference else []
    if ambiguous_removal_scope:
        differences.append('历史出自撤场或拆除清单，本行未明确交易/作业范围，不能当成新制作单价')
    spec_differences = []
    if brand_conflict:
        spec_differences.append(f'品牌不同（当前：{query["brand"]}；历史：{row["brand"]}）')
    if current_models and historical_models and current_models != historical_models:
        spec_differences.append(f'型号不同（当前：{"+".join(sorted(current_models))}；历史：{"+".join(sorted(historical_models))}）')
    elif current_models and not historical_models:
        differences.append('历史型号未注明')
    if spec and past_spec and not same_spec and not equivalent_specs:
        spec_differences.append('规格不同')
    elif spec and not past_spec and not same_parameters:
        differences.append('历史规格未注明')
    for parameter in compared:
        if parameter['current'] and not parameter['historical'] and parameter['label'] in ('屏幕形态', '屏幕尺寸', '像素间距', '刷新率', '内存', '存储', '帧率', '分辨率等级', '成片时长', '视觉风格'):
            differences.append(f'历史{parameter["label"]}未注明')
        if parameter['different']:
            spec_differences.append(f'{parameter["label"]}不同（当前：{parameter["current"]}；历史：{parameter["historical"]}）')
    materials, past_materials = material_terms(context), material_terms(historical_details)
    matching_parameters = [p['label'] for p in compared if p['current'] and p['historical'] and not p['different']]
    attribute_reason = process_reference(current_path, historical_path, shared_processes,
                                         materials.keys() & past_materials.keys(), matching_parameters) if separate_classes else ''
    if separate_classes and not (model_bridge or attribute_reason or catalog_bridge or digital_related or labor_partial):
        return None
    if materials and not past_materials:
        differences.append('历史材质未注明')
    missing_processes = current_processes - historical_processes
    if missing_processes and current_path and historical_path and current_path[:3] == historical_path[:3]:
        differences.append('历史工艺未注明：' + '、'.join(sorted(missing_processes)))
    material_conflict = bool(materials and past_materials and materials.keys() != past_materials.keys())
    if material_conflict:
        spec_differences.append(f'材质不同（当前：{"+".join(materials.values())}；历史：{"+".join(past_materials.values())}）')
    differences.extend(spec_differences)
    assembly = lambda t:{label for label,pattern in [('背架',r'背架'),('围边',r'围边|包边'),('光源',r'光源|发光'),('驱动电源',r'驱动|电源'),('造型外框',r'外框|框架')] if re.search(pattern,t)}
    current_assembly,historical_assembly=assembly(context),assembly(historical_details)
    if current_assembly and historical_assembly and current_assembly != historical_assembly:
        differences.append(f'包含构成不同（当前：{"+".join(sorted(current_assembly))}；历史：{"+".join(sorted(historical_assembly))}）')
    quantified_parts = re.findall(r'(?:灯|机|油|板|布|镜|话筒|音箱)\s*[:：x×*]?\s*\d+(?![a-z])', historical_details)
    historical_package = bool(re.search(r'布景.*[x×*]|整包|合包|套装|套餐',historical_details)
                              or len(quantified_parts) >= 2
                              or ('窗帘' in past and re.search(r'亚克力|板材|玻璃', past)))
    requested_expenses, offered_expenses = expense_parts(context), expense_parts(historical_details)
    if requested_expenses and len(offered_expenses) > 1 and requested_expenses != offered_expenses:
        historical_package = True
        differences.append(f'费用构成不同（当前：{"+".join(sorted(requested_expenses))}；历史：{"+".join(sorted(offered_expenses))}）')
    if '住宿' in requested_expenses and re.search(r'住宿由甲方提供|不含住宿|住宿另计', historical_details):
        differences.append('历史报价不含住宿，不能作为食宿完整价格')
    labor_partial = bool(re.search(r'电箱|电缆|配电',context) and past == '电工')
    scope_conflict = bool((requested & offered_exclusions) or (offered & requested_exclusions) or
                          (requested and offered and max(len(requested), len(offered)) > 1 and requested != offered))
    if scope_conflict:
        differences.append('组合或包含项不同')
    elif (config or len(requested) > 1) and not same_bundle:
        differences.append('历史组合未能确认')
    digital_differences = []
    if digital_related:
        current_actions = actions(scope_text(name, ' '.join((norm(query.get('description')), norm(query.get('spec')), config))))
        historical_actions = actions(scope_text(past, ' '.join((norm(row.get('description')), norm(row.get('spec'))))))
        if current_actions != historical_actions:
            digital_differences.append(f'工作范围不同（当前：{"+".join(sorted(current_actions)) or "未注明"}；历史：{"+".join(sorted(historical_actions)) or "未注明"}）')
        if current_path != historical_path:
            digital_differences.append(f'交付细类不同（当前：{current_path[-1]}；历史：{historical_path[-1]}）')
        count = re.search(r'(三|3|两|2|四|4|五|5)只角色', historical_details)
        if count and not re.search(r'[一二三四五六七八九十0-9]+只角色', context):
            digital_differences.append(f'历史每套含{count[0]}；当前每套角色数未注明')
    if digital_related and any(p['label'] == '视觉风格' and p['current'] and not p['historical'] for p in compared):
        digital_differences.append('历史视觉风格未注明，不能确认与当前制作风格相同')
    differences.extend(digital_differences)
    conflict = scope_conflict or bool(spec_differences) or bool(digital_differences)
    # Scope warnings describe an already relevant object; they cannot establish relevance.
    material_process_match = any(any(x in context for x in group) and
                                 any(x in historical_details for x in group)
                                 for group in REFERENCE_MATERIALS_AND_PROCESSES)
    object_related = bool(same_model or class_match or bundle_reason or attribute_reason or
                          catalog_bridge or digital_related or labor_partial or family or near or
                          name == past or (material_process_match and current_path and historical_path
                                           and current_path[:3] == historical_path[:3]))
    if not object_related:
        return None
    if historical_package and not re.search(r'整包|布景|套装',name):
        tier,label,reason=24,'整包旁证','历史价格覆盖多个物料或费用组成，当前项的独立计费依据需另核'
        differences.append('历史包含多个组成，仅覆盖当前项的一部分')
        bundle_reason=reason
    elif labor_partial:
        tier,label,reason=18,'部分工作参考','历史只列电工人工，不包含当前电箱、电缆或设备租赁费用'
        differences.append('人工与设备材料合包范围不同')
    elif transaction_difference or ambiguous_removal_scope:
        tier, label, reason = 20, '交易或作业范围参考', (transaction_difference or
                        '历史来自撤场清单，只能核对对象，不能确认是新制、拆除、回收还是其他费用')
    elif attribute_reason:
        tier, label, reason = 26, '工艺旁证', attribute_reason
        differences.append('适用范围或报价构成不同')
    elif bundle_reason:
        tier, label = 24, '整包旁证'
        reason = bundle_reason
        differences.append('整包价格与分项单价不可直接比较')
    elif digital_related and digital_differences:
        tier, label, reason = 18, '部分工作参考', '实际交付内容有交集，未覆盖或超出当前工作范围的部分需分别询价'
    elif class_match and current_path[:2] == ('展览运营服务', '人员运营') and current_path != historical_path:
        tier, label, reason = 18, '部分岗位参考', '历史仅列具体运营岗位，当前组合中的其他岗位需分别对照'
        differences.append('运营岗位覆盖范围不同')
    elif class_match and current_path != historical_path:
        tier, label = 6, '同用途参考'
        print_processes = {'UV打印', '写真喷绘'}
        if current_path[2] == '表面覆贴' and print_processes & current_processes and print_processes & historical_processes:
            current_print = 'UV打印' if 'UV打印' in current_processes else '写真喷绘'
            historical_print = 'UV打印' if 'UV打印' in historical_processes else '写真喷绘'
            reason = f'两项均为印刷类表面覆贴（当前：{current_print}；历史：{historical_print}）'
        else:
            reason = f'两项同属{current_path[2]}，细类不同，需核对配置与施工范围'
    elif same_bundle and (same_model or same_spec) and not conflict:
        tier, label = 0, '型号或规格与组合一致'
        reason = f'{"型号" if same_model else "规格"}一致，组合或包含项相符'
    elif same_model:
        tier, label = 1, '同型号'
        reason = f'两条明细的型号一致：{"+".join(sorted(current_models))}'
    elif same_spec and (class_match or family or near or name == past or same_bundle):
        tier, label = 2, '同规格'
        reason = '两条明细的规格一致，名称或组合相关'
    elif same_parameters and (class_match or family or near or name == past or same_bundle):
        tier, label = 2, '参数一致'
        reason = '已识别的参数换算后相同，名称或组合相关'
    elif same_bundle and (class_match or family or near or name == past):
        tier, label = 3, '组合相近'
        reason = '两条明细的组合或包含项相符，名称相关'
    elif class_match:
        if current_path == historical_path and len(current_path) == 4:
            tier, label = 4, '同细类参考'
            reason = f'两项均归入{current_path[-1]}，按规格、交付范围和计价口径进一步比较'
        else:
            tier, label = 6, '同用途参考'
            reason = (f'两项均归入{current_path[2]}，制作工序与交付范围需对照'
                      if current_path[0] == '数字内容与技术服务' or '服务' in current_path[0] else
                      f'两项均用于{current_path[2]}，具体材料与施工范围需对照')
    elif catalog_bridge:
        identity, catalog_path = catalog_match
        tier, label = 4, '归类库同用途参考'
        reason = f'原件和新报价均指向{identity}，已对齐计价单位，规格与交付范围需核对'
        current_path, historical_path = (*catalog_path[:2], identity), catalog_path
    elif name == past:
        tier, label = 5, '仅同名称'
        reason = '名称相同，型号、规格或组合缺少一致的证据'
    elif family or near:
        tier, label = 6, '相近装置'
        reason = (f'同类模糊匹配：“{family[0]}”与“{family[1]}”归在同一用途分类'
                  if family else '名称存在包含关系，具体做法需对照规格')
    elif any(any(x in context for x in group) and any(x in historical for x in group)
             for group in REFERENCE_MATERIALS_AND_PROCESSES):
        tier, label = 7, '同材工艺参考'
        reason = '描述中有相同的材料或工艺，装置与工作范围需另核'
    else:
        return None
    if conflict:
        label += ' · 有差异'
    chain = ' → '.join(current_path)
    if chain:
        reason = f'归类链路：{chain}。' + reason
    classification = ({'trace': classification_trace(current_path, historical_path, reason, 'partial' if digital_differences or bundle_reason or labor_partial else 'compare_attributes'), 'current': current_path, 'historical': historical_path, 'bundle_reference': bool(bundle_reason),
                       'process_reference': bool(attribute_reason)} if current_path or historical_path else None)
    return ((tier + (8 if conflict else 0), -len(requested & offered)), label,
            differences, spec_differences, reason, compared, classification)


COMPONENT = re.compile(r'(?P<name>[\u4e00-\u9fff]{2,16})\s*[×xX*：:]?\s*'
                       r'(?P<quantity>\d+(?:\.\d+)?)\s*(?P<unit>个|件|只|套|组|台|盏|面|块)?')
COMPONENT_VARIANT = re.compile(r'^(?:玻璃钢|亚克力|泡沫|不锈钢|木制|金属)|(?:造型|模型|道具|摆件)$')
COMPONENT_TERMS = re.compile(r'帆船|塔灯|游泳圈|救生圈|指南针|船舵|舵轮|地球仪|礼帽|望远镜|铃铛|船锚|礼品盒|照相机|放大镜|五角星|圣诞球|星星灯|马灯|皮箱')
COMPONENT_ALIASES = ({'船舵', '舵轮'}, {'游泳圈', '救生圈'})


def quoted_components(query):
    """Read explicit lists, leaving dimensions and unitemized prose at package level."""
    components = {}
    for field in ('configuration', 'description'):
        parts = re.split(r'[，,、；;＋+\n]', str(query.get(field) or ''))
        found = {}
        for part in parts:
            part = re.sub(r'^(?:包含|包括|含有|含)\s*[：:]?\s*', '', part.strip())
            if re.search(r'不含|不包括|另计|参考图', part):
                continue
            item = COMPONENT.fullmatch(part)
            if item:
                if positive(item['quantity']):
                    found[item['name']] = (item['quantity'], item['unit'])
                continue
            elif field == 'configuration' and re.fullmatch(r'[\u4e00-\u9fff]{2,16}', part):
                found[part] = (None, None)
            elif not re.search(r'不含|不包括|另计|参考图', part):
                found.update((term, (None, None)) for term in COMPONENT_TERMS.findall(part))
        if len(found) > 1:
            components.update(found)
    components.pop(str(query['name']).strip(), None)
    return list(components.items())


def priced_references(root, checked, ledger, duplicates, shared, query, component=None, omit=(), catalog=None):
    candidates = []
    catalog_candidates = ({row['line_id']: (label, path) for row, label, path in catalog.candidates(query)}
                          if catalog and not component else {})
    for row in checked:
        if price_role_block(row):
            continue
        if row['record_id'] == query.get('exclude') or row['line_id'] in omit:
            continue
        if component:
            name, _ = component
            past = norm(row['item_name'])
            core = COMPONENT_VARIANT.sub('', past)
            related = any(norm(name) in aliases and core in aliases for aliases in COMPONENT_ALIASES)
            if past != norm(name) and core != norm(name) and not related:
                continue
            label = '同名子件' if past == norm(name) else '相近子件'
            relation = ((0 if past == norm(name) else 1, 0), label, [], [],
                        f'当前组合中的“{name}”对应历史独立报价项“{row["item_name"]}”', [], None)
        else:
            relation = relationship(query, row, catalog_candidates.get(row['line_id']))
        if relation:
            candidates.append((row, relation))
    current_unit = billing_unit(norm(query.get('unit')))
    query_path = line_classification(query, 'name', ('name', 'spec', 'description', 'configuration'))
    def family_distance(candidate):
        classification = candidate[1][6] or {}
        past_path = classification.get('historical') or ()
        if query_path[:2] == ('数字内容与技术服务', 'AI内容'):
            return 0 if tuple(past_path[:2]) == query_path[:2] else 1
        return 0
    def evidence_rank(candidate):
        row, relation = candidate
        label = relation[1]
        if any(term in label for term in ('工艺', '同材')):
            channel = 4
        elif '旁证' in label:
            channel = 3
        elif any(term in label for term in ('部分', '交易或作业')):
            channel = 2
        elif any(term in label for term in ('同型号', '同规格', '参数一致', '型号或规格与组合一致')):
            channel = 0
        else:
            channel = 1
        historical_unit = billing_unit(norm(row.get('unit')))
        attrs = row.get('source_attributes') or {}
        monthly = attrs.get('monthly_fee_cny') is not None
        multiplier = row.get('billing_multiplier') or row.get('price_multiplier')
        label = attrs.get('rate_multiplier_label') or row.get('rate_multiplier_label')
        denominator = '月' if monthly else {'场次':'场','天数':'天','月数':'月'}.get(label) if multiplier is not None else None
        if denominator and historical_unit and not historical_unit.endswith('/'+denominator):
            historical_unit += '/'+denominator
        unit_distance = 0 if current_unit and historical_unit == current_unit else 1 if not current_unit or not historical_unit else 2
        package = row.get('kind') == 'whole_scope_quote' or not (positive(row.get('unit_price')) and row.get('unit'))
        scope_distance = int(package and current_unit not in ('项','套','组',''))
        differences = [d for d in relation[2] if d != '币种不同']
        return (channel, family_distance(candidate), scope_distance, unit_distance,
                len(differences), len(relation[3]), relation[0],
                not bool(relation[6] and relation[6]['current'] == relation[6]['historical']),
                norm(row.get('item_name')) != norm(query.get('name')),
                row.get('currency') != query.get('currency'), str(row.get('line_id','')))
    candidates.sort(key=evidence_rank)
    result = []
    seen = set()
    projects = set()
    for row, (_, label, differences, spec_differences, reason, compared, classification) in candidates:
        attrs = row.get('source_attributes') or {}
        variant = str(row.get('quotation_variant_id') or attrs.get('quotation_variant_id') or row.get('source_variant_id') or row.get('variant_id') or row.get('source_price_version') or '')
        key = (row['source_token'], row['source_locator'], variant)
        project = (row['project_key'], norm(row['item_name']), norm(row.get('spec')),
                   norm(row.get('model')), str(row.get('unit_price')), str(row.get('subtotal')), variant)
        if key in seen or project in projects:
            continue
        seen.add(key)
        projects.add(project)
        exclusion = rejection(row, duplicates, shared)
        ref = reference(row, exclusion if is_checked(row) else 'source_scope_pending')
        if not is_checked(row):
            ref['source_line_issue'] = exclusion
        ref['source_review_kind'] = 'contract_checked' if is_checked(row) else 'line_fields_checked'
        record = ledger[row['record_id']]
        folder = root / 'attachments' / hashlib.sha256(row['source_token'].encode()).hexdigest()
        source = next(iter(sorted(folder.glob('source.*'))), folder / 'document.xml')
        included_component = row.get('source_document_type') == 'included_component_amount'
        package_total = row.get('kind') == 'whole_scope_quote' or not (positive(row.get('unit_price')) and row.get('unit'))
        monthly_fee = attrs.get('monthly_fee_cny')
        multiplier = row.get('billing_multiplier') or row.get('price_multiplier')
        multiplier_label = attrs.get('rate_multiplier_label') or row.get('rate_multiplier_label')
        rate_units = {'场次':('每场单价','场'), '天数':('每日单价','天'), '月数':('每月单价','月')}
        multiplier_rate = rate_units.get(multiplier_label) if multiplier is not None else None
        if multiplier is not None:
            differences.append('历史单价另乘' + str(multiplier_label or '计费倍数') + '，不等于完整工作量总价')
        if monthly_fee is not None:
            differences.append('历史单价为每人月费用；整期小计单独保留，未注明月数不反推')
        if included_component:
            label = '子件金额注记'
            reason += '。整机配置中的子件金额注记，不是独立采购单价；不与整机金额重复加总'
            differences.append('整机配置子件金额，不代表独立采购或完整整包价格')
        elif package_total:
            label = '整包金额参考' if row.get('kind') == 'whole_scope_quote' else '明细金额参考'
            reason += '。历史仅提供范围金额，不作为当前分项单价或整项高低判断依据'
            differences.append('整包或明细总额与分项单价不可直接比较')
        if view_only_variant(row):
            label += ' · 版本范围待核'
            differences.append('历史版本或适用范围不同，不计作独立成交样本')
        if current_unit and row.get('unit') and billing_unit(norm(row['unit'])) != current_unit:
            differences.append('计价单位不同')
            reason += f'。计价单位不同（当前：{query["unit"]}；历史：{row["unit"]}）'
        if query.get('currency') and row['currency'] != query['currency']:
            differences.append('币种不同')
        if label.startswith('同材工艺参考'):
            differences.append('仅材质或工艺相近，装置和范围需另核')
        result.append({**ref, 'contract_name': record['contract_name'], 'sheet': record['sheet'],
                       'ledger_row': record['row'], 'source_name': record['contract_link'],
                       'match_kind': label, 'differences': list(dict.fromkeys(differences)), 'spec_differences': list(dict.fromkeys(spec_differences)),
                       'reference_price_type': 'package_total' if package_total else 'unit_price',
                       'reference_total': row.get('subtotal'),
                       'reference_rate_basis': 'monthly_per_person' if monthly_fee is not None else 'source_multiplier_rate' if multiplier is not None else None,
                       'reference_rate_label': '每人月费用' if monthly_fee is not None else multiplier_rate[0] if multiplier_rate else '原单价（另计倍数）' if multiplier is not None else None,
                       'reference_rate_unit': '人/月' if monthly_fee is not None else str(row.get('unit') or '') + '·' + multiplier_rate[1] if multiplier_rate else None,
                       'reference_billing_multiplier': multiplier,
                       'reference_billing_multiplier_label': multiplier_label,
                       'reference_total_cny_yuan': ref.get('subtotal_cny_yuan'),
                       'independent_sample_key': row.get('economic_purchase_group') or attrs.get('economic_purchase_group') or row.get('purchase_evidence_group') or attrs.get('purchase_evidence_group') or attrs.get('observation_family') or attrs.get('shared_quote_family') or row.get('project_key'),
                       'price_comparison_eligible': not included_component and not package_total and not view_only_variant(row) and exclusion is None and not [d for d in differences if d != '币种不同'] and not component,
                       'match_reason': reason, 'parameters': compared,
                       'comparison_role': 'component' if included_component else 'package' if package_total else 'component' if component else 'package' if '整包旁证' in label else 'process' if '工艺' in label else 'partial' if '部分' in label or '交易或作业' in label else 'candidate',
                       'classification': classification,
                       'template_categories': template_context(catalog, row, 'item_name'),
                       'source_url': f'{GITHUB}/attachments/{folder.name}/{source.name}' if GITHUB and source.is_file() else None})
        if component:
            result[-1].update(component_name=component[0], component_quantity=component[1][0],
                              component_unit=component[1][1])
        if len(result) == (1 if component else 6):
            break
    return result


def lookup(root, checked, ledger, duplicates, shared, query, live, pending=None, catalog=None, source_names=None):
    name = str(query.get('name', '')).strip()
    if not name or len(name) > 120:
        return {'references': [], 'fallback_complete': True}
    path = line_classification(query, 'name', ('name', 'spec', 'description', 'configuration'))
    partials = []
    for component in quoted_components({**query, 'name': name}):
        _, (_, unit) = component
        partials.extend(priced_references(root, checked, ledger, duplicates, shared,
                       {'name': component[0], 'unit': unit, 'currency': query.get('currency'),
                        'exclude': query.get('exclude')}, component=component))
    result = priced_references(root, checked, ledger, duplicates, shared, {**query, 'name': name},
                               omit={ref['line_id'] for ref in partials}, catalog=catalog) + partials
    review_candidates = (pending or {}).get((path, billing_unit(norm(query.get('unit')))), {})
    if not path:
        path = next((match['classification']['current'] for match in result
                     if match.get('classification') and match['classification']['current']), ())
    meta = {'input_issues': inspect_input(query), 'query_template_categories': template_context(catalog, query), 'retrieval_trace': {'stages': ['原件关联校验', '逐项功能与细类', '型号规格与组合拆解', '同层与父类候选扩展', '计价范围对照'], 'priced_rows_examined': len(checked), 'eligible_priced_history_complete': True, 'feishu_live_search_performed': bool(live and not result)},
            'query_classification': path,
            'reviewed_price_rows': len(checked),
            'known_item_in_sources': any(rid != query.get('exclude') for rid in (source_names or {}).get(norm(name), ())),
            'pending_price_sources': [item for rid, item in review_candidates.items()
                                      if rid != query.get('exclude') and comparable_class(path, path, norm(name), norm(item))]}
    if result:
        return {'references': result, 'fallback_complete': True, **meta}
    if live:
        hits, complete = table_fallback(name)
    else:
        hits = [{'kind': 'ledger_match', 'sheet': r['sheet'], 'address': f'G{r["row"]}',
                 'value': r['contract_name'] or r['project_name'], 'url': TABLE_URL}
                for r in ledger.values() if any(norm(name) in norm(r.get(k)) for k in ('project_name','contract_name'))]
        complete = False
    return {'references': hits[:6], 'fallback_complete': complete, **meta}


def selected_sheet(token, selector):
    sheets = call('sheets', '+workbook-info', '--spreadsheet-token', token)['sheets']
    matches = [s for s in sheets if selector in (s['sheet_name'], s['sheet_id'])]
    if len(matches) != 1:
        raise ValueError('找不到指定工作表。可选：' + '、'.join(s['sheet_name'] for s in sheets))
    sheet = matches[0]
    if sheet['row_count'] > 5000:
        raise ValueError('该工作表超过 5000 行，请拆分后导入')
    rows = {}
    width = min(60, sheet['column_count'])
    for start in range(1, sheet['row_count'] + 1, 20):
        for left in range(1, width + 1, 26):
            stop = min(start + 19, sheet['row_count'])
            right = min(left + 25, width)
            block = call('sheets', '+cells-get', '--spreadsheet-token', token,
                         '--sheet-id', sheet['sheet_id'], '--range', f'{column(left)}{start}:{column(right)}{stop}')
            if block.get('has_more'):
                raise ValueError('飞书返回的工作表区间不完整，请拆分后导入')
            for area in block['ranges']:
                for row_no, cells in zip(area['row_indices'], area['cells']):
                    for col_no, cell in zip(area['col_indices'], cells):
                        value = (cell or {}).get('value')
                        if isinstance(value, (str, int, float, bool)) and value != '':
                            rows.setdefault(row_no, {})[col_no] = value
    return {'filename': '飞书电子表格.xlsx', 'worksheet': sheet['sheet_name'],
            'rows': [{'row': n, 'values': [cells.get(column(c)) for c in range(1, width + 1)]}
                     for n, cells in sorted(rows.items())]}


def oa_file(link, worksheet=''):
    target = urlparse(link)
    path = re.fullmatch(r'/(?:drive/)?(file|wiki|sheets|spreadsheets)/([A-Za-z0-9_]+)/?', target.path)
    if (target.scheme != 'https' or not target.hostname or
            not target.hostname.endswith('.feishu.cn') or target.username or target.password or
            target.port not in (None, 443) or not path):
        raise ValueError('请粘贴飞书电子表格、知识库报价页或 Excel 附件链接')
    kind, token = path.groups()
    title = '飞书报价'
    if kind == 'wiki':
        node = call('wiki', '+node-get', '--node-token', token)
        kind, token = node['obj_type'], node['obj_token']
        title = node.get('title') or title
    selector = worksheet or parse_qs(target.query).get('sheet', [''])[0]
    if kind in ('sheet', 'sheets', 'spreadsheets') and selector:
        return selected_sheet(token, selector)
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        if kind in ('sheet', 'sheets', 'spreadsheets'):
            call('drive', '+export', '--token', token, '--doc-type', 'sheet',
                 '--file-extension', 'xlsx', '--output-dir', '.', '--file-name', 'quote.xlsx', cwd=tmp)
            workbook = folder / 'quote.xlsx'
            if not workbook.is_file():
                raise ValueError('飞书电子表格导出尚未返回文件，请稍后重试')
        elif kind == 'file':
            raw = folder / 'quote.xls'
            call('drive', '+download', '--file-token', token, '--output', './quote.xls', cwd=tmp)
            if raw.stat().st_size > 30 * 1024 * 1024:
                raise ValueError('附件超过 30 MB')
            with raw.open('rb') as stream:
                signature = stream.read(8)
            workbook = raw
            if signature == bytes.fromhex('d0cf11e0a1b11ae1'):
                run(['soffice', '-env:UserInstallation='+(folder/'profile').as_uri(),
                     '--headless', '--convert-to', 'xlsx', '--outdir', tmp, str(raw)],
                    check=True, capture_output=True, timeout=30)
                workbook = folder / 'quote.xlsx'
        else:
            raise ValueError('此知识库页面不指向电子表格或 Excel 附件')
        if workbook.stat().st_size > 30 * 1024 * 1024:
            raise ValueError('工作簿超过 30 MB。飞书电子表格可填写工作表名称后只读取该表。')
        with ZipFile(workbook) as book:
            if 'xl/workbook.xml' not in book.namelist():
                raise ValueError('附件不是 Excel 工作簿')
        filename = re.sub(r'\.xlsx?$', '', title, flags=re.I) + '.xlsx'
        return {'filename': filename, 'bytes': base64.b64encode(workbook.read_bytes()).decode('ascii')}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=('demo', 'lookup', 'contract', 'batch', 'oa', 'legacy-xls'))
    for key in ('quantity', 'name', 'exclude', 'unit', 'currency', 'spec', 'dimension_unit', 'model', 'description', 'configuration', 'link', 'worksheet'):
        p.add_argument(f'--{key}', default='')
    args = p.parse_args()
    if args.action == 'legacy-xls':
        from legacy_xls import legacy_xls_document
        try:
            output = legacy_xls_document(sys.stdin.buffer.read(30 * 1024 * 1024 + 1))
        except ValueError as error:
            output = {'error':str(error)}
        print(json.dumps(output, ensure_ascii=False, allow_nan=False))
        return
    if args.action == 'oa':
        try:
            print(json.dumps(oa_file(args.link, args.worksheet), ensure_ascii=False))
        except ValueError as error:
            print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return
    root = Path(__file__).resolve().parents[1] / 'data'
    rows, duplicates, shared, _, _ = load(root)
    checked = reference_pool(rows)
    if args.action == 'demo':
        output = [reference(row, rejection(row, duplicates, shared)) for name in DEMO_NAMES
                  if (row := next((r for r in checked if is_checked(r) and r['item_name'] == name and r['currency'] == 'CNY'
                                  and r.get('quantity') is not None), None))]
    elif args.action == 'contract':
        output = {'lines': [reference(r, rejection(r, duplicates, shared)) for r in rows
                            if (is_checked(r) or r.get('source_fields_reviewed')) and r['record_id'] == args.exclude]}
    else:
        ledger = {r['record_id']: r for r in json.loads((root/'ledger.json').read_text())}
        pending = pending_price_index(rows)
        catalog = ReferenceCatalog(root, checked)
        source_names = source_name_index(rows)
        if args.action == 'batch':
            queries = json.load(sys.stdin)
            if not isinstance(queries, list) or len(queries) > 5000 or not all(isinstance(q, dict) for q in queries):
                p.error('无效的报价行批次')
            output = [lookup(root, checked, ledger, duplicates, shared, q, False, pending, catalog, source_names) for q in queries]
        else:
            output = lookup(root, checked, ledger, duplicates, shared, vars(args), True, pending, catalog, source_names)
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
