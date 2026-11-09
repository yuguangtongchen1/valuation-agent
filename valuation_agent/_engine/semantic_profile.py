"""Evidence-first internal identities; HS reasoning adapted without claiming tariff codes."""
import re
from functools import lru_cache
import unicodedata


def text(value):
    return unicodedata.normalize('NFKC', str(value or '')).lower()


DIGITAL = (
    ('角色资产/建模与骨骼绑定', r'(?:角色|人物|ip).*?(?:建模|模型).*?(?:绑定|骨骼)|(?:建模|模型).*?(?:骨骼绑定)'),
    ('角色资产/建模', r'(?:角色|人物|ip).*?(?:建模|模型)'),
    ('动画制作/角色与特效动画', r'角色动画|特效制作|动画设计|动物.*(?:动作|轨迹)|动作制作|骨骼动画'),
    ('场景资产/建模与资产整合', r'场景.*(?:建模|模型|资产)|素材资产整合|模型搭建'),
    ('渲染制作/材质灯光与渲染', r'材质.*灯光|灯光.*渲染|三渲二|细腻材质|毛发.*渲染'),
    ('后期制作/合成与调色', r'后期.*(?:调整|制作|调色)|合成调色|合成.*(?:特效|输出)|2d动效'),
    ('输出适配/预览与最终渲染', r'渲染输出|预览渲染|最终渲染|4k渲染|渲染合成输出'),
    ('AI内容/生成与三维控制', r'ai生成.*3d|ai.*三维.*控制|ai.*3d.*控制'),
    ('AI内容/动态生成', r'ai.*(?:动态|视频|动画).*生成|ai动态生成'),
    ('AI内容/静态视觉资产', r'ai.*(?:视觉资产|图片|画面|概念|风格)|ai生成'),
    ('输出适配/多屏多楼层', r'多楼层适配|多屏.*适配|异形屏.*适配|楼层.*适配'),
    ('前期设计/视觉与分镜', r'分镜|故事板|视觉设计|创意策划|脚本创作'),
    ('动画制作/三维动画综合', r'三维动画|3d动画|cg动画|场景动画'),
    ('制作人员/按人天服务', r'三维渲染师|动画师|制片|项目管理|制作统筹'),
)


@lru_cache(maxsize=32768)
def digital_path(name, context):
    name, context = text(name), text(context)
    hardware = r'服务器|适配器|转接器|多屏宝|多屏保|分配器|显卡|网卡|电脑主机|视频处理器'
    if re.search(hardware, name) and not re.search(r'内容制作|程序开发|软件开发', name):
        return ()
    ai_task = re.search(r'\bai\s*(?:视觉|图片|画面|动态|视频|生成|辅助|制作)|aigc\s*(?:制作|生成|设计)', name)
    if ai_task:
        moving = re.search(r'动态|动画|视频', name) or re.search(r'ai\s*(?:视频|动态画面)|视频动态', context)
        leaf = '生成与三维控制' if re.search(r'3d.*控制|三维.*控制', context) else '动态生成' if moving else '静态视觉资产'
        return ('数字内容与技术服务', 'AI内容', leaf)
    if re.search(r'(?:产品|商品|模型|资产).*(?:适配|改模)', name):
        return ('数字内容与技术服务', '资产适配', '产品模型与资产适配')
    if re.search(r'适配|展开反求|反求处理', name):
        return ('数字内容与技术服务', '输出适配', '多屏多楼层')
    # The line description refines merged/generic headers; never borrow contract-wide prose here.
    detail = context[len(name):].strip() if context.startswith(name) else context
    if name in ('渲染输出', '最终输出', '预览渲染'):
        return ('数字内容与技术服务', '输出适配', '预览与最终渲染')
    if '/' in name and len(detail) >= 8 and any(re.search(pattern, detail) for _, pattern in DIGITAL):
        context = detail
    for leaf, pattern in DIGITAL:
        if leaf.startswith('AI内容') and not re.search(r'\bai\s*(?:视觉|图片|画面|动态|视频|生成|辅助|制作)', context):
            continue
        if re.search(pattern, context):
            return ('数字内容与技术服务', *leaf.split('/'))
    if re.search(r'数字(?:多媒体)?内容|多媒体内容', name):
        return ('数字内容与技术服务', '数字内容制作', '工序未细列')
    return ()


@lru_cache(maxsize=32768)
def procurement_service_path(name, context=''):
    """Resolve reusable deliverables, keeping campaign names out of class identity."""
    name, context = text(name), text(context)
    if re.search(r'(?:内容管理|媒体播放|播放端|播控).*(?:软件|程序|系统|授权)|(?:软件|程序).*(?:播放端|内容管理|播放管理)', name):
        return ('软件与交互服务', '内容管理与播放', '软件及许可交付')
    if re.search(r'(?:公司|企业|经营)运营|企业管理', name):
        return ('管理费用', '企业运营管理', '管理费')
    if re.search(r'运营服务|运营管理|(?:前台|衍生品).*(?:运营|管理)|(?:展览|展厅).*(?:运营|接待)', name):
        role = ('前台运营' if '前台' in name and '衍生品' not in name else
                '衍生品运营' if '衍生品' in name and '前台' not in name else '运营岗位组合')
        return ('展览运营服务', '人员运营', role)
    if re.search(r'(?:视频|照片|素材|作品).*拍摄|拍摄(?:服务|制作)', name) and not re.search(r'器材|摄像机|摄影机|镜头|灯具', name):
        return ('影像制作服务', '拍摄服务', '素材拍摄' if re.search(r'素材|源文件', name + ' ' + context) else '摄制整包')
    if re.search(r'plant and equipment|机械设备(?:合包|组合)|施工设备(?:费|组合)', name) and re.search(r'剪叉|scissor', context) and re.search(r'起重机|crane', context):
        return ('项目服务', '物流与设备', '机械作业设备', '升降及起重设备组合')
    # An integrator's package is not a reference for every device mentioned in it.
    if re.search(r'(?:多媒体|音视频|影音).*(?:建设|集成|工程|采购)', name):
        return ('多媒体集成服务', '系统建设与采购', '整项范围')
    if re.search(r'(?:展厅|展馆|楼层).*(?:硬件|软件)', name):
        return ('多媒体集成服务', '系统建设与采购',
                '软件工作包' if '软件' in name and '硬件' not in name else
                '硬件工作包' if '硬件' in name and '软件' not in name else '整项范围')
    if re.search(r'扩声(?:系统|设备)?|音响系统|音频系统', name):
        if re.search(r'租赁|租用', name):
            return ('音视频设备服务', '扩声系统', '租赁整包')
        return ('音视频设备服务', '扩声系统', '系统整包')
    return ()


def models(value):
    return set(_models(text(value)))


@lru_cache(maxsize=32768)
def _models(value):
    result = set()
    # Explicit mixed alphanumeric identifiers; dimensions, RAM and resolution are parameters.
    for token in re.findall(r'(?<![a-z0-9])[a-z][a-z0-9]*(?:[-_][a-z0-9]+)+(?![a-z0-9])|(?<![a-z0-9])[a-z]{1,8}\d{2,}[a-z0-9]*(?![a-z0-9])', value):
        if re.fullmatch(r'(?:[lwh]\d+(?:mm|cm|m)?[x×*]?)+', token):
            continue
        if re.search(r'\d', token) and not re.fullmatch(r'(?:[lwh]\d+(?:mm|cm|m)?|\d+k|\d+gb)', token):
            result.add(token.upper())
    return frozenset(result)


ACTIONS = {
    '建模': r'建模|模型搭建|模型制作', '绑定': r'骨骼|绑定',
    '动画': r'动画|动态|动作|轨迹', '特效': r'特效', '材质': r'材质|贴图|毛发',
    '灯光': r'灯光', '渲染': r'渲染', '合成': r'合成|后期',
    '调色': r'调色', 'AI生成': r'ai.*生成', '三维控制': r'3d.*控制|三维.*控制',
    '多屏适配': r'多屏|多楼层|楼层.*适配|楼体.*适配',
    '屏幕适配': r'屏幕.*适配|展开|反求|超宽|弧形.*适配|裸眼.*适配',
}


@lru_cache(maxsize=32768)
def actions(value):
    return frozenset(label for label, pattern in ACTIONS.items() if re.search(pattern, text(value)))


def classification_trace(current, historical, reason, scope_status):
    common = []
    for a, b in zip(current or (), historical or ()):
        if a != b:
            break
        common.append(a)
    return {'method': '功能—技术细类—规格配置—组合范围—计价依据',
            'current_path': list(current or ()), 'historical_path': list(historical or ()),
            'common_path': common, 'scope_status': scope_status,
            'decision': reason,
            'principles': ['先查包含与排除条件', '同层比较、细项优先', '整包与零件分别计价', '差异不靠猜测消除']}


def scope_text(name, details):
    details = text(details)
    name = text(name)
    if '/' in name and len(details) >= 8 and digital_path('', details):
        return details
    return name + ' ' + details


def inspect_input(row):
    name = text(row.get('name') or row.get('item_name'))
    description = text(row.get('description'))
    quantity = str(row.get('quantity') or '')
    issues = []
    if re.search(r'剪叉|剪刀升降', name) and '吊车' in description:
        issues.append('名称为剪叉升降设备，说明写吊车；请确认实际设备类型，原值未改。')
    if re.search(r'安装.*3.*撤场.*1', description) and quantity == '3':
        issues.append('描述含安装3台班及撤场1台班，数量列为3；请确认计费范围，不直接改为4。')
    if '多楼层' in name and all(f'{n}f' in description for n in range(2, 7)) and quantity == '3':
        issues.append('说明涉及2F至6F五层，数量为3套；请明确一套覆盖的范围。')
    if re.search(r'建模|模型搭建', description) and row.get('unit') == '秒' and quantity == '1':
        issues.append('资产建模以1秒计量；请确认按成片时长、资产还是工作包计费，保留原单位。')
    return issues
