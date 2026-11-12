"""Exhibition procurement concepts, not price-equivalence synonym substitution.

The name identifies a purchased object; row-level context only disambiguates it.
Source rationale: skills/procurement-estimation/references/exhibition-terminology.md.
"""
import re
import unicodedata
from functools import lru_cache

# id, canonical procurement object, class path, name expressions, exclusion.
CONCEPTS = (
 ('projector_mount','投影设备安装支架','展陈物料/多媒体硬件/安装附件/投影支架', r'^(?:投影机|投影仪|投影)(?:吊架|支架|吊杆)$', r''),
 ('led_module','LED显示模组','展陈物料/多媒体硬件/显示部件/LED显示模组', r'^led(?:显示屏|屏体|显示)?模组$', r''),
 ('suspended_structure','吊挂支撑结构','展陈制作/结构工程/吊挂结构/吊挂支撑', r'吊挂钢结构|悬吊钢结构|吊挂支撑结构|吊挂承重结构', r'计算|设计费'),
 ('ceiling','吊顶系统','展陈制作/顶面工程/吊顶/吊顶系统', r'天花|吊顶|吊平顶', r'投影|影片|动画|服务器|logo|标识|屏|灯|维修|修复|修补|补洞'),
 ('partition','轻质隔墙','展陈制作/墙面工程/隔墙/轻质隔墙', r'隔墙|隔断', r'活动隔断|移动隔断|玻璃隔断|成品隔断'),
 ('display_wall','展陈造型墙','展陈制作/墙面工程/展墙/造型展墙', r'展墙|展示墙|造型墙|主题墙|背景墙', r'服务器|影片|视频|数字内容|展陈系统'),
 ('display_system','可调展陈系统','展陈制作/展具系统/可调展陈/展陈系统', r'多功能展陈系统|可调展陈系统|可调展示平台及支架', r''),
 ('case','展示柜','展陈制作/展具系统/展柜/展示柜', r'展柜|展示柜|陈列柜', r'灯具|灯带|照明|玻璃板|玻璃罩|柜锁|展柜玻璃'),
 ('plinth','展品底座','展陈制作/展具系统/展台/展品底座', r'展品底座|陈列台|陈列底座|展品基座|独立.*底座|展示台', r'旋转|电动|服务器'),
 ('turntable','旋转展示平台','展陈制作/机械展具/旋转平台/旋转展台', r'旋转平台|旋转展台|旋转地台|电动转台|电动旋转台', r'电机|轴承|滑环'),
 ('wood_finish','木饰面系统','展陈制作/饰面工程/板材饰面/木饰面', r'木饰面|木皮饰面|木质饰面', r'展墙|地台|吊顶|天花|展柜'),
 ('graphic_panel','图文展板','展陈物料/标识与图文/图文展板/成品展板', r'图文展板|说明牌|说明板|介绍牌|展板', r'支架|底座|灯具|灯箱|设计费'),
 ('screen_print','丝网印图文','展陈制作/图文制作/直接印刷/丝网印', r'丝网印|丝印|丝网印刷', r'立体字|金属字|修改|修复|设计费|设备|印刷机'),
 ('sign_stand','导视立牌','展陈物料/标识与图文/导视标识/立牌', r'导视牌|导向牌|指示牌|立牌|导览牌', r'底座|安装费|设计费'),
 ('letter','立体字','展陈物料/标识与照明/标识/立体字', r'立体字|金属字|水晶字|亚克力字|有机玻璃字', r'发光|灯箱'),
 ('lit_letter','发光字','展陈物料/标识与照明/标识/发光字', r'发光字|灯箱字|发光标识字', r''),
 ('lightbox','灯箱成品','展陈物料/标识与图文/灯箱/灯箱成品', r'灯箱', r'灯箱布|灯箱片|软膜画面|灯箱画面|灯箱光源|灯箱电源|灯箱膜'),
 ('lightbox_face','灯箱画面','展陈物料/标识与图文/灯箱/透光画面', r'灯箱布|灯箱片|软膜画面|灯箱画面|灯箱膜', r''),
 ('strip','柔性灯带','展陈物料/标识与照明/照明/灯带', r'灯带|软灯条|柔性灯条', r'电源|驱动|型材|灯槽|解码器'),
 ('linear','线性灯具','展陈物料/标识与照明/照明/线性灯具', r'线性灯|线条灯|条形灯具', r'灯带|电源|驱动|解码器'),
 ('track_spot','轨道射灯','展陈物料/标识与照明/照明/轨道射灯', r'轨道射灯|导轨式射灯|导轨射灯|轨道灯|导轨灯', r'轨道条|轨道接头|灯光控制|轨道安装'),
 ('wallwasher','洗墙灯','展陈物料/标识与照明/照明/洗墙灯', r'洗墙灯|洗墙射灯|wallwasher', r''),
 ('ring','环形灯具','展陈物料/标识与照明/照明/环形灯具', r'环.*led灯|圆.*led灯|环形灯|圆环灯', r'灯箱'),
 ('player','媒体播放主机','展陈物料/多媒体硬件/计算设备/媒体播放主机', r'播控主机|播放主机|媒体服务器|播放服务器|播控服务器', r'软件|程序|授权|维修|租赁软件'),
 ('controller','中控主机','展陈物料/多媒体硬件/控制设备/中央控制主机', r'中控主机|中央控制主机|控制处理器', r'软件|程序|开发'),
 ('show_control','中控系统','软件与交互服务/系统控制/中控系统/整项范围', r'中控系统|中央控制系统|集中控制系统', r'主机|硬件|控制器'),
 ('projection','投影设备','展陈物料/多媒体硬件/显示设备/投影机', r'投影机|投影仪', r'吊架|支架|镜头|遮罩|维修|安装|校准|融合|改色|内容|影片|滤网|灯泡'),
 ('screen','投影幕面','展陈物料/多媒体硬件/投影承载/投影幕', r'投影幕|投影屏幕|投影银幕|正投幕|背投幕|投影纱幕', r'安装|内容|影片|制作费'),
 ('directional_speaker','定向扬声器','展陈物料/多媒体硬件/扩声设备/定向扬声器', r'定向音响|定向音箱|定向扬声器|定向声扬声器', r'系统|控制器'),
 ('speaker','扬声器','展陈物料/多媒体硬件/扩声设备/扬声器', r'音箱|扬声器|喇叭|吸顶音响', r'定向|系统|功放|线缆|音箱线'),
 ('amplifier','功率放大器','展陈物料/多媒体硬件/扩声设备/功率放大器', r'功率放大器|功放', r'系统|音箱'),
 ('ethernet','以太网线','展陈物料/多媒体硬件/线缆/网络线缆', r'网线|网络线|以太网线|cat[5678]线|六类线|超五类线', r'测试仪|水晶头|交换机|无线'),
 ('dmx','灯光控制信号线','展陈物料/多媒体硬件/线缆/DMX信号线', r'dmx.*(?:线|电缆)|灯控信号线', r'网关|控台|解码器|控制器'),
 ('physical_model','实体模型','展陈制作/场景与模型/实体模型/模型制作', r'沙盘|山体模型|建筑模型|实物模型|实体模型|洞藏模型', r'数字|三维建模|虚拟|动画|影片|视频'),
 ('diagram_design','图文设计','设计与技术服务/视觉设计/图文设计/平面设计', r'图文设计|平面设计|版式设计|平面美术', r'软件许可'),
 ('shopdrawing','施工图深化','项目服务/技术与保障/设计深化/施工图深化', r'施工图深化|施工图设计|展陈优化设计|深化设计', r'结构计算|计算报告'),
)
COMPILED = tuple((cid,label,tuple(path.split('/')),re.compile(pattern,re.I),re.compile(exclude,re.I) if exclude else None)
                 for cid,label,path,pattern,exclude in CONCEPTS)

@lru_cache(maxsize=32768)
def concept(name, context=''):
    name=unicodedata.normalize('NFKC',str(name or '')).lower()
    context=unicodedata.normalize('NFKC',str(context or '')).lower()
    # Design scope outranks the physical subject mentioned in parentheses.
    if re.search(r'施工图深化|施工图设计|施工图绘制|制图费|^制图$|制图服务',name) or (re.search(r'深化设计',name) and re.search(r'施工图',context)):
        return ('shopdrawing','施工图深化',('项目服务','技术与保障','设计深化','施工图深化'))
    if re.search(r'深化设计',name):
        scope = '体验流程设计' if re.search(r'体验|流程|交互',name) else '模型设计' if '模型' in name else '未注明专业'
        return ('design_scope','深化设计',('设计与技术服务','方案深化','专业范围',scope))
    if re.search(r'天花|吊顶',name) and re.search(r'维修|修复|修补|补洞|重新刷漆|翻新',name):
        return ('ceiling_repair','顶面维修',('项目服务','装饰维修','顶面维修','维修工序'))
    if re.search(r'丝网印|丝印',name) and re.search(r'修改|修复',name):
        return ('print_revision','图文印刷修改',('项目服务','图文修改','印刷修改','现场修订'))
    # A noun inside a combined deliverable does not identify the entire package.
    if re.search(r'天花|吊顶',name) and re.search(r'展墙|展示墙',name):
        return None
    if re.search(r'消防|应急疏散|安全出口|逃生', name) and re.search(r'标识|指示牌|导向牌|指示灯', name):
        return ('safety_sign','消防疏散标识',('安全设施','消防与疏散','安全标识','消防疏散标识'))
    if re.search(r'立体字|金属字', name) and re.search(r'丝网印|丝印', name):
        return ('compound_graphics','组合图文制作',('展陈物料','标识与图文','组合图文','立体字与印刷组合'))
    if '灯带' in name and re.search(r'型材|灯槽',name):
        return ('strip_assembly','型材灯带组合',('展陈物料','标识与照明','照明组合','型材与灯带'))
    if re.search(r'展墙',name) and re.search(r'顶面|造型顶|吊顶',context) and re.search(r'展台|橱窗|展柜',context):
        return ('fitout_package','展陈装饰组合',('展陈制作','组合工程','装饰与展具','综合交付'))
    # Multiple named deliverables stay a combined scope, not whichever word matched first.
    if re.search(r'隔墙|隔断',name) and re.search(r'橱窗|展柜',name) and re.search(r'灯|饰面|复合板',name):
        return ('fitout_package','展陈装饰组合',('展陈制作','组合工程','装饰与展具','综合交付'))
    # Context can clarify a generic name, but cannot turn a component into a whole system.
    if re.search(r'立体字|字体|标识字',name) and re.search(r'发光字',context) and not re.search(r'不发光|非发光',context):
        return ('lit_letter','发光字',('展陈物料','标识与照明','标识','发光字'))
    if re.search(r'亚克力|有机玻璃',name) and re.search(r'uv|印刷|图文',name) and not re.search(r'雕刻|剪影|发光|灯箱|立体字|模型|造型',name):
        return ('graphic_panel','图文展板',('展陈物料','标识与图文','图文展板','成品展板'))
    for cid,label,path,pattern,exclude in COMPILED:
        if pattern.search(name) and not (exclude and exclude.search(name)):
            # Physical models and digital assets require different procurement scopes.
            if cid=='physical_model' and re.search(r'数字模型|虚拟模型|三维建模|骨骼绑定',context) and not re.search(r'实物|实体|打印|雕刻|浇筑',context):
                return None
            return cid,label,path
    return None

# Relations are explicit and directional; never close synonyms transitively.
RELATED = {
 ('lightbox_face','lightbox'): '历史为灯箱成品，包含画面以外的框体和光源；不是画面独立价格',
 ('strip','linear'): '历史为线性灯具，可能含型材、扩散罩或驱动；灯带独立价格未分列',
}

def bundle_relation(current, historical):
    if current and historical:
        return RELATED.get((current[0],historical[0]),'')
    return ''

def concept_path(name, context=''):
    c=concept(name,context)
    return c[2] if c else ()

# Explicit material aliases only. GRG is gypsum based; GRP/FRP is not GRG.
MATERIAL_ALIASES = (
 ('玻纤增强水泥', r'(?<![a-z])gfrc(?![a-z])|(?<![a-z])grc(?![a-z])|玻璃纤维增强水泥|玻纤增强水泥'),
 ('GRG石膏复合材料', r'(?<![a-z])grg(?![a-z])|(?<![a-z])gfrg(?![a-z])|玻璃纤维增强石膏|玻纤增强石膏'),
 ('玻璃钢', r'玻璃钢|(?<![a-z])grp(?![a-z])|(?<![a-z])gfrp(?![a-z])|(?<![a-z])frp(?![a-z])'),
 ('亚克力', r'亚克力|有机玻璃|(?<![a-z])pmma(?![a-z])'),
 ('PC板', r'\bpc板|聚碳酸酯'),
 ('胶合板', r'胶合板|夹板|多层板'),
 ('铝塑复合板', r'铝塑板|铝塑复合板'),
 ('铝单板', r'铝单板'),
 ('实体面材', r'可丽耐|corian|实体面材'),
 ('石膏板', r'石膏板'),
 ('铝方通', r'铝方通'),
 ('铜材', r'铜质(?!效果|纹理|质感)|铜板|纯铜'),
 ('PVC发泡板', r'雪弗板|雪佛板|pvc发泡板'),
 ('泡沫材料', r'泡沫(?!混凝土)|eps雕刻'),
)

def material_identity_text(value):
    value=str(value or '').lower()
    # An appearance target is not evidence that the specified material was purchased.
    return re.sub(r'[（(][^）)]*(?:效果对标|参考效果|外观参照)[^）)]*[）)]', '', value)

def material_identities(value):
    value=material_identity_text(value)
    return {label for label,pattern in MATERIAL_ALIASES if re.search(pattern,value)}
