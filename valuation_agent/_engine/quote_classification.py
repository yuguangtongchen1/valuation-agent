"""Internal classification by use, deliverable, and scope for exhibition quotes."""
import re
from functools import lru_cache
from semantic_profile import digital_path, procurement_service_path
from row_classification import row_route


def floor_classification(name, context):
    prefix = ('展陈制作', '地台与饰面工程')
    if re.search(r'地台.*(?:\+|及|含).*(?:包边|收口|饰面|面层)', name):
        return (*prefix, '地台整包')
    if re.search(r'地台收口|装饰包边|收口条|收口线|(?:地胶|地贴).*收边', name):
        return (*prefix, '边缘收口')
    if re.search(r'地台面(?!板)|地台饰面|地胶|地贴|地板|地毯|pp背胶', name):
        if re.search(r'地板|地毯', name):
            return (*prefix, '地面铺装', '地毯' if '地毯' in name else '地板')
        if 'pp背胶' in context:
            return (*prefix, '表面覆贴', 'PP背胶')
        if re.search(r'pvc.*(?:地胶|地贴)|地胶.*pvc', context):
            return (*prefix, '表面覆贴', 'PVC地胶及地贴')
        return (*prefix, '表面覆贴')
    if re.search(r'地台基础|地台基层|地台钢结构|(?:圆形?|二层|方形|异形)地台|^地台$', name):
        return (*prefix, '承重基层')
    return ()


RULES = (
    ('展陈制作/饰面工程/柱面包覆/非承重饰面', r'包立柱|柱面包覆|柱面饰面'),
    ('展陈物料/多媒体硬件/处理与传输/硬件适配及分配', r'适配器|转接器|多屏宝|多屏保|分配器'),
    ('展陈物料/多媒体硬件/计算设备/服务器与工作站', r'服务器|电脑主机|工作站|工控机'),
    ('拍摄与制作/摄影器材/摄影机与机身', r'摄影机|摄像机|camera|arri|alexa|red\s*(?:komodo|v-raptor)|fx[369]'),
    ('拍摄与制作/摄影器材/摄影镜头', r'镜头|lens', r'租赁|焦距|mm|镜头组|arri|zeiss|cooke'),
    ('拍摄与制作/摄影器材/Grip辅助器材', r'摇臂|摄影轨道|斯坦尼康|稳定器|三脚架|跟焦器|监视器'),
    ('拍摄与制作/摄制人员/摄影岗位', r'摄影师|摄影指导|dop|摄影助理|跟焦员'),
    ('拍摄与制作/摄制人员/灯光岗位', r'灯光师|灯光助理|gaffer|best boy'),
    ('拍摄与制作/摄制人员/导演岗位', r'导演|director'),
    ('拍摄与制作/摄制人员/场务岗位', r'场务|场记|runner|continuity'),
    ('拍摄与制作/摄制人员/化妆造型', r'化妆师|造型师|服装师|makeup'),
    ('项目服务/技术与保障/结构安全/计算与审核', r'结构计算书|结构验算|围挡验算|安全计算书'),
    ('项目服务/技术与保障/结构安全/施工图', r'围挡施工图|施工图绘制'),
    ('项目服务/技术与保障/保险/设备与人员组合保险', r'设备.*人员.*保险|人员.*设备.*保险'),
    ('项目服务/技术与保障/保险/人员保险', r'保险', r'施工人员|人员保险|雇主责任|意外伤害'),
    ('项目服务/技术与保障/保险/工程及第三者责任', r'保险', r'第三方责任|施工一切险|工程一切险'),
    ('项目服务/技术与保障/保险/范围未明', r'保险'),
    ('项目服务/安装与运维/工厂预搭/预搭与货运合包', r'预搭.*运费|试搭.*运费'),
    ('项目服务/安装与运维/工厂预搭/预搭综合', r'工厂试搭|预搭|预拼装'),
    ('项目服务/安装与运维/现场搭拆/施工人工', r'人员搭建|安装人工|搭建人工|撤场人工|^人工$'),
    ('项目服务/安装与运维/现场保障/值班驻场', r'现场值班(?!.*差旅)|驻场技术人工|驻场运维'),
    ('项目服务/安装与运维/现场保障/鲜花维护', r'维护', r'送花|鲜花|花艺'),
    ('项目服务/安装与运维/现场保障/实体维护', r'活动期间维护|物料维护'),
    ('项目服务/安装与运维/现场保障/范围未明', r'^维护$'),
    ('项目服务/安装与运维/临时供电/临电服务', r'^电工$|临电|临时用电'),
    ('项目服务/物流与设备/包装/实体物料包装', r'物料包装|设备打包|展品包装|包装费$'),
    ('项目服务/物流与设备/交通运输/货运与人员交通合包', r'物料运输.*人员交通|货运.*人员交通'),
    ('项目服务/物流与设备/交通运输/人员出行', r'人员交通|差旅交通|差旅机票'),
    ('项目服务/物流与设备/人员差旅/餐住', r'差旅', r'餐住|餐饮|住宿|餐食'),
    ('项目服务/物流与设备/人员差旅/范围未明', r'搭建差旅|安装差旅|人员差旅|^差旅$'),
    ('项目服务/物流与设备/交通运输/物料货运', r'^运输(费)?$|物料运输|货运'),
    ('项目服务/物流与设备/设备租赁/剪叉式升降', r'剪刀升降车|剪叉式升降|剪叉车'),
    ('项目服务/物流与设备/设备租赁/曲臂式升降', r'曲臂车|曲臂式升降'),
    ('项目服务/物流与设备/设备租赁/装卸叉车', r'叉车'),
    ('展陈制作/临时设施/施工围挡/围挡整项', r'^(?:施工)?围挡(?:\s*\(|$)|施工围挡'),
    ('展陈制作/临时设施/施工围挡/覆面材料', r'围挡喷绘布|围挡灯布'),
    ('展陈制作/结构件/围护构件/栏杆围栏', r'围栏|栏杆'),
    ('展陈制作/结构件/支撑骨架/屏体支撑', r'大屏钢结构|显示屏钢结构|安装结构|^钢结构$', r'屏|led'),
    ('展陈制作/结构件/支撑骨架/装置主结构', r'主支持结构|^结构骨架$'),
    ('展陈制作/结构件/支撑骨架/用途未明钢构', r'^钢结构$|立钢架结构|道具钢架|立钢结构'),
    ('展陈制作/结构件/支撑骨架/改造', r'结构骨架修改|骨架变更'),
    ('展陈制作/结构件/支撑骨架/立柱桅杆', r'立柱|桅杆'),
    ('展陈制作/结构件/支撑骨架/设备底座', r'投影灯.*底座|设备底座'),
    ('展陈制作/结构件/支撑骨架/装饰底座', r'望远镜底座|表盘底座'),
    ('展陈制作/结构件/围护构件/瞭望平台', r'瞭望圆台'),
    ('展陈制作/结构件/支撑骨架/造型框架', r'门框|球形外框|中心圆柱装置圆环|铁管装饰|铁链|金属件|梯子|底部美化'),
    ('展陈制作/结构件/地台与通行/台阶', r'台阶'),
    ('展陈制作/结构件/地台与通行/踢脚线', r'地脚线|踢脚线'),
    ('展陈物料/标识与照明/标识/发光字', r'发光字|立体字体', r'发光'),
    ('展陈物料/标识与照明/照明/灯珠', r'灯珠'),
    ('展陈物料/标识与照明/照明/星形灯', r'星星灯|星形灯|星型灯|发光多角星'),
    ('展陈物料/标识与照明/照明/线性灯具', r'线性灯|线条灯|灯槽灯', r'灯具|灯壳|铝槽|成品'),
    ('展陈物料/标识与照明/照明/灯带', r'灯带|软灯条|柔性灯条'),
    ('展陈物料/标识与照明/照明/灯具组合', r'^灯$', r'吊灯.*落地灯|吊灯.*落地装饰灯'),
    ('展陈物料/标识与照明/照明/吊灯', r'吊灯'),
    ('展陈物料/标识与照明/照明/花灯', r'花灯|菱形灯'),
    ('展陈物料/标识与照明/照明/氛围灯', r'氛围灯'),
    ('展陈物料/多媒体硬件/显示设备/电视机', r'电视(?:机)?$|会议电视'),
    ('展陈物料/多媒体硬件/显示设备/工程显示屏', r'显示屏|led屏|拼接屏|户外屏|室内屏|户外大屏|室内大屏'),
    ('展陈物料/家具软装/窗帘/电动', r'布帘|窗帘', r'电动|电机'),
    ('展陈物料/家具软装/窗帘/布艺', r'布帘|窗帘'),
    ('展陈物料/家具软装/家具/沙发', r'沙发'),
    ('展陈物料/家具软装/家具/桌', r'吧桌|桌子|吧台桌'),
    ('展陈物料/家具软装/家具/椅', r'吧台椅|座椅'),
    ('展陈物料/家具软装/布艺/毛毯', r'毛毯'),
    ('展陈物料/造型与装饰/节庆陈设/发光礼盒', r'礼盒|礼物盒', r'光源|发光|内置灯'),
    ('展陈物料/造型与装饰/节庆陈设/礼盒', r'礼盒|礼物盒|雪弗板\s*box'),
    ('展陈物料/造型与装饰/节庆陈设/花环藤条', r'花环|圣诞藤条|藤条装饰'),
    ('展陈物料/造型与装饰/节庆陈设/箱包摆件', r'皮箱|顶木箱'),
    ('展陈物料/造型与装饰/节庆陈设/独立道具', r'船舵|望远镜|救生圈|锚|摆件|铃铛挂件|杯子|玻璃钢.*造型|表盘|发光球|亚克力圆球|顶五角星'),
    ('展陈物料/造型与装饰/节庆陈设/组合道具', r'装饰道具|圣诞元素|软装饰|其他配饰|篓筐|帆布\+|配件'),
    ('展陈物料/造型与装饰/节庆陈设/装饰辅件', r'毛线球|飘带|装饰红绳|异形贴纸'),
)
COMPILED_RULES = [(tuple(path.split('/')), re.compile(name), re.compile(context[0]) if context else None)
                  for path, name, *context in RULES]


def _routed_path(route, name):
    # Broad filing leaves are not synonym declarations. Keep the explicit item
    # identity at the leaf so a cabinet cannot become a motherboard comparable.
    return ('源字段分级', route['code'], *route['leaf'], name)


def classify_row(row):
    """Shared row-aware entry used by CLI, preserving parent-operation evidence."""
    name = str(row.get('item_name') or row.get('name') or '').lower().strip()
    context = ' '.join(str(row.get(field) or '') for field in ('spec','model','description','configuration','scope','module'))
    route = row_route({**row, 'item_name':name})
    if route and route.get('priority'):
        return _routed_path(route,name)
    path = quote_classification(name, context.lower())
    return path or (_routed_path(route,name) if route else ())


@lru_cache(maxsize=32768)
def quote_classification(name, context):
    service = procurement_service_path(name, context)
    if service:
        return service
    digital = digital_path(name, context)
    if digital and re.search(r'数字(?:多媒体)?内容|多媒体内容', name):
        return digital
    if '梯子' in name:
        ladder_context = name + ' ' + context
        if re.search(r'租赁|租用|登高|施工工具|人字梯|伸缩梯', ladder_context):
            return ('项目服务', '物流与设备', '设备租赁', '登高梯具')
        if re.search(r'铁艺|金属', ladder_context) and re.search(r'定做|定制|喷漆|烤漆|造型|装饰', ladder_context):
            return ('展陈制作', '道具制作', '金属造型道具', '定制装饰梯子')
    route = row_route({'item_name':name,'description':context})
    if route and (route.get('priority') or re.search(r'插件|程序开发|软件开发|硬件驱动|框架编程',name)):
        return _routed_path(route,name)
    if re.search(r'地面保护|地毯保护|地板保护', name):
        return ('项目服务', '施工保障', '现场保护', '保护材料或围护组合')
    digital = digital_path(name, context)
    if digital:
        return digital
    floor = floor_classification(name, context)
    if floor:
        return floor
    for path, names, attributes in COMPILED_RULES:
        if names.search(name) and (attributes is None or attributes.search(context)):
            return path
    return _routed_path(route,name) if route else ()


def comparable_class(current, historical, name, past):
    if not current or not historical:
        return False
    if current[0] == historical[0] == '数字内容与技术服务' and '数字内容制作' in (current[1], historical[1]):
        return True
    if current[:2] == historical[:2] == ('展览运营服务', '人员运营'):
        return current == historical or '运营岗位组合' in (current[-1], historical[-1])
    if current[:2] == historical[:2] == ('多媒体集成服务', '系统建设与采购'):
        return True
    if current == historical:
        # The generic prop leaf is a filing category, not evidence that two props serve the same function.
        if current[-1] == '独立道具':
            return any(term in name and term in past for term in ('船舵', '望远镜', '救生圈', '锚', '铃铛', '杯子', '表盘'))
        return current[-1] not in ('组合道具', '装饰辅件', '造型框架', '范围未明') or name == past
    return current[:2] == historical[:2] and current[1] in ('AI内容', '角色资产', '渲染制作', '输出适配')


def bundled_evidence(current, historical):
    if len(current) < 3 or len(historical) < 3:
        return ''
    if historical[-1] == '设备与人员组合保险' and current[-1] == '人员保险':
        return '历史保险同时覆盖设备和人员，未拆人员保险独立费用'
    if historical[-1] == '升降及起重设备组合' and current[-1] == '剪叉式升降':
        return '历史包含剪叉平台及起重机等设备合包，未列剪叉平台独立台班价'
    if historical[2] == '地台整包' and current[2] in ('承重基层', '边缘收口'):
        return f'历史报价合计了地台与包边，未列{current[2]}独立单价'
    if historical[-1] == '货运与人员交通合包' and current[-1] in ('物料货运', '人员出行'):
        return f'历史报价合计了货运与人员交通，未列{current[-1]}独立单价'
    if historical[-1] == '预搭与货运合包' and current[-1] == '预搭综合':
        return '历史报价合计了预搭人工和运费，未列预搭独立单价'
    return ''


PROCESS_TERMS = {
    'UV打印': r'uv\s*(?:打印|喷印|喷绘)|定制uv画面',
    '写真喷绘': r'写真|喷绘',
    '表面覆贴': r'覆贴|贴膜|裱画|覆膜|背胶|包覆',
    '涂装': r'喷漆|烤漆|油漆',
    '焊接': r'焊接|满焊',
    '折弯': r'折弯|热弯',
    '切割': r'激光雕刻|激光切割|数控切割|裁型',
    '吊装': r'吊装|吊挂',
}


@lru_cache(maxsize=32768)
def process_terms(text):
    return frozenset(label for label, pattern in PROCESS_TERMS.items() if re.search(pattern, text))


def process_reference(current, historical, processes, materials, parameters):
    if not current or not historical or current == historical:
        return ''
    if current[:3] == historical[:3] and current[2] == '表面覆贴':
        return '均涉及表面图文制作；底材、耐磨防滑用途和安装环境不同，仅作工艺线索'
    if current[:3] != historical[:3]:
        return ''
    if (current[-1], historical[-1]) == ('围挡整项', '覆面材料') and '写真喷绘' in processes:
        return '两项均用于围挡喷绘，历史仅列覆面材料单价，桁架与搭拆需另核'
    if current[2] == '支撑骨架' and '用途未明钢构' in (current[-1], historical[-1]):
        if materials or (parameters and processes):
            return '骨架的材质、工艺或规格有共同证据，历史钢构用途仍需核对'
    return ''


def billing_unit(value):
    if value in {'m2', 'm²', '平方', '平米', '平方米', 'sqm'}:
        return 'm2'
    if value in {'m', '米', '延米'}:
        return 'm'
    if value in {'个', '只', '件', 'pc', 'pcs', 'piece', 'pieces'}:
        return 'piece'
    if value in {'项', 'item', 'items'}:
        return 'item'
    if value in {'天', 'day', 'days'}:
        return 'day'
    if value in {'套', 'set', 'sets'}:
        return 'set'
    return value
