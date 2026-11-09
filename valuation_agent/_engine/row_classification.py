"""Evidence-bounded row routing across physical, digital and project-service scopes.

Names identify the object; descriptions/modules disambiguate generic source names.
Routing is not price equivalence. Unknown attributes remain unknown and packages
are not split into fictitious component transactions.
"""
import re

# code, variable-depth leaf, name pattern. Specific operations precede objects.
_RULES = [
('6.1', ('结算调整','押金或保证金'), r'押金|保证金'),
('6.1', ('结算调整','税费及开票'), r'税收|税费|税金|开票|发票费用'),
('6.1', ('结算调整','终止结算或取消费'), r'终止.*尾款|cancellation'),
('1.3', ('技术鉴定与审核','结构审查'),r'结构.*(?:评估|加固设计|分析|稽核|蓝图)|鉴定检测报告|图审|风险评估|安全认证|监理|安全健康|tcp监督|吊索具.*检查'),
('1.2', ('技术咨询与实施','顾问与技术文件'),r'技术咨询|技术指导|顾问服务|咨询建议|设计.*安装指导|技术可行性|关键文档|文件提交管理|技术攻克'),
('1.1', ('视觉与体验设计','方案及视觉规范'),r'品牌规划|品牌策略|标志图形|标准色|标准字体|辅助图形|使用禁忌|组合方式|材质工艺建议|vi设计|美学指导|美陈装置设计|图表设计|原型图|体验设计|体验流程|交互.*(?:设计|方案)|深化交互|美术稿|单帧.*设计|单帧设定|角色设定|场景设定|场景设计|插画|插图|视觉美术|角色设计|场景原画|涂鸦艺术家|艺术人物demo'),
('4.4', ('后期制作','抠像及擦除'),r'抠像|擦除|画面修补|照片.*(?:精修|修图)|图片精修|kv擦除'),
('4.4', ('后期制作','动效与画面调整'),r'动效|动态制作|字幕|尺寸调整|视频修改|画面处理|排版|视频内容自适应|画面内容素材|屏幕定位匹配|楼体替换|新增修改'),
('4.3', ('数字资产','模型与扫描重建'),r'扫描|解析重建|模型数据|模型文件|线模型|数字资产|宇宙资产|数据可视化|资产制作|资产整合|模型构造'),
('4.3', ('数字内容','模拟解算'),r'解算|烘焙|动力学'),
('4.3', ('数字内容','材质灯光'),r'模型材质|角色材质|灯光材质|灯光氛围|灯光&材质|场景灯光'),
('4.3', ('数字内容','视频整项制作'),r'视频制作|短片|影片|数字影像|多媒体内容|内容制作|内容深化|循环背景|待机视频|待机循环|入场光效|数字艺术品待机|内容定制|球形表情|人物动作|屏幕内容发布'),
('4.5', ('声音制作','选曲与作曲'),r'选曲|作曲|配乐|bgm|^声音$|音棚|声音制作'),
('5.1', ('软件与交互','程序及接口开发'),r'插件|程序开发|软件开发|模组开发|框架编程|内容编程|控制界面|基础界面|核心功能|互动系统|互动引擎|交互制作|互动增补|新增互动|按压识别|硬件驱动|设备控制模块|线上分享|播放设置逻辑|程序功能|数字艺术.*交互|互动测试'),
('5.2', ('软件及内容许可','授权与订阅'),r'解密狗|非独占授权|知识授权|厂商功能调用'),
('5.3', ('系统实施','测试联调与运维'),r'系统联调|整体系统测试|功能及集成测试|系统搭建|多媒体集成|技术支持|屏幕运营|影片更换|内容发布|验收配合|系统技术|o&m manual'),
('4.2', ('摄制与采集','拍摄整项及素材'),r'实拍素材|延时素材|素材购买|素材采买|素材采集|^素材$|街拍|明星合拍|航拍|飞手|现场图像数据采集'),
('4.2', ('摄制人员','编导与现场岗位'),r'编导|高级视频人员|高级音频人员|高级灯光人员|视频.*老师|视频人员|视频老师|灯光老师|激光控台人员|技术助理|^助理$|^工作人员$|跟焦|调酒师'),
('4.2', ('摄制器材','器材及车辆'),r'qtake|器材车|制作用车|制作组车辆|场务车辆|房车|b机增补|摄影器材|^机器费用$'),
('4.2', ('服装与道具','服装采买'),r'服装|衬衫|t恤|^衣服$'),
('4.2', ('前期制作','现场杂项及物资'),r'前期杂费|场务物资|^跑腿$'),
('3.8', ('人员餐旅','餐食与住宿'),r'餐费|餐食|茶歇|冷餐|f&b|酒店|住宿'),
('3.7', ('物流与车辆','运输或交通费用'),r'车费|油费|加油|依维柯|车辆租赁|商务车|人员车辆|设备托运|打包费|快递|上料|运输'),
('3.6', ('施工机械','机械台班'),r'通架租赁|机力费|工程车费用'),
('3.5', ('施工操作','拆除及拆装'),r'拆卸工程|拆除|拆场|拆装|拆卸及|removal|dismantl'),
('3.4', ('施工操作','安装与现场人工'),r'安装服务|安装费|屏幕安装|标准屏体安装|安装固定|人工|技工|工人|技术工时|劳动力|general labour|临时增补人员|加兼职|兼职.*日|现场保驾|现场保架|赶工|夜班|加班|overtime|normal shift|mobilization'),
('3.13', ('项目执行','活动运营与管理'),r'现场协调|项目经理|执行人员|现场管理|公司运营管理|第三方管理|现场监督|^督导$|参观保障|现场保障|兼职协议|人员工作|人员现场|^执行$|pm\b|project.*management|event coordinator|^account$|客户及项目会议|服务团队|服务生|服务员|waiter|waitress|hostess|etiquette|向导|^翻译$|统一保管|统一管理'),
('7.1', ('施工保障','报批及安全措施'),r'资质|报批|报备|许可|安保|公安咨询|城管咨询|四方验收|ehs|文明施工|措施项目|环境保护|安全管理|statutory requirements'),
('3.13', ('维护服务','质保与设备维护'),r'维保|质保|维护工具'),
('3.11', ('现场保护','保护材料及施工'),r'保护的材料|移动保护|屏体防护|地面硬保护'),
('3.3', ('预装与检验','工厂试验及验收'),r'工厂.*(?:测试|检验)|电气.*测试|后处理与检测|干胶实验|实验辅材|测试工程师|验收费'),
('3.1', ('电气及公共线路','线缆与连接'),r'电源线|电路电线|馈线|平方芯线|弱电线|6类网络线|电话线|系统连接线|线缆|线路改造|线管|接线盒|配线|配管|电器机箱.*放线|内部接驳|电力系统'),
('3.1', ('电气及公共线路','供配电元件'),r'断路器|段路器|接触器|继电器|变频器|整流块|防水插头|接插件|电源箱|^电源$|移动电源|风机双电源|风机控制箱|基站供电模块|滤波器|电费'),
('2.6', ('照明系统','灯具与控制'),r'轨道灯|射灯|洗墙灯|激光灯|^激光$|应急照明|应急灯|疏散指示|出口指示|标志灯|^四眼$|灯光费用|主视频灯光|开业秀灯光|鳞片灯光|照明|控制器|分控器|指示器|按钮|灯架|光照架|光照'),
('2.7', ('显示与交互硬件','显示与投影设备'),r'(?:\d+\s*寸|lcd|液晶|画框屏|屏幕|彩屏|霓彩屏|透明屏|^led$|独立led|会议一体机|百变屏)'),
('2.7', ('显示与交互硬件','音视频处理与传输'),r'光电转换|光纤|信号线|信号放大|音频|话筒|音柱|麦架|信号系统|4k40|融合系统|播放盒|control console'),
('2.7', ('显示与交互硬件','计算与控制配件'),r'机柜|机箱|内存|主板|键盘|鼠标|散热|控制面板|控制终端|工控主机|kincet|kinect|体感设备|传输设备|输入板卡|网络托盘|恒温恒湿箱'),
('2.7', ('设备机械','运动与流体系统'),r'液压|千斤顶|旋转可变机构|卷线器|编码器|轴控制|气管|给水管|软管|排水阀|空压机|反应器|光生物|机械电气|台上机械|机械组装|气缸|水舞'),
('2.7', ('网络服务','连接及专线'),r'5g网络|专线网络|^网络$|熔纤'),
('2.5', ('平面标识','印刷及品牌展示'),r'指引|挂牌|展牌|立牌|卡片|打卡折页|明信片|门票|手提袋|报纸|专业现场印刷|二维码|口播|易拉宝|logo露出|赞助致谢'),
('2.4', ('家具软装','桌椅与柜体'),r'椅|桌|书架|柜子|柜体|服务台|倚靠|靠凳|储物柜'),
('2.4', ('家具软装','遮光布帘'),r'纱幕|幕布|遮光布|棚布|filled cloth|confection fee|电磁屏蔽布'),
('2.3', ('造型及展具','定制造型及配件'),r'造型|雕刻|泡雕|蛋壳|DP点|dp点|模型|海洋球|泳圈|扇子|艺术装置|奖杯|扭蛋机|烟雾机|fog machine|拍报亭|烟灰缸|衣架|^鞋子制作$|海岸线|鳞片|广告装饰|气膜'),
('2.1', ('结构及建材','金属骨架和板材'),r'框架|背架|桁架|支撑|桅杆|钢网|钢材|钢板|铁板|方管|龙骨|铝合金|碳钢|不锈钢|结构层|平台结构|维修马道|钢木结构|牛腿|散力结构|夹治具|铁构件|铁艺|立杆|结构工程|主框架'),
('2.1', ('结构及建材','墙体及基层'),r'隔墙|板墙|基层|砖砌墙|导墙|阻燃板|多层板|夹板|石膏板|纤维板|泡沫板|雪弗板|矿棉板'),
('2.2', ('建筑围护与饰面','门窗玻璃及五金'),r'玻璃|暗门|隐藏门|单开门|双开门|侧开门|防火门|门窗套|密封条|电子锁|^增加锁$|窗洞|百叶窗'),
('2.2', ('建筑围护与饰面','吊顶及墙地面'),r'吊顶|天棚|顶面|封板|盖板|墙体|背景板|墙金属板|地坪|地面|地砖|石板路|石子铺|找平|水磨石|地槽|收边|防水|涂层|喷黑|刷油|喷漆|贴色|覆膜|作色|软膜|彩白彩|宣绒布|紫膜|装饰线|铝扣板|伸缩缝|井盖'),
('2.2', ('材料及加工','聚合物与粘接'),r'亚克力|有机玻璃|聚氨酯|树脂|^pla$|玻钢|胶水|胶条|软胶皮|棉花|大力胶|毛刷|发光植物'),
('7.8', ('建筑机电','消防及暖通给排水'),r'消火栓|喷淋|消防|防排烟|排烟|通风|轴流|送风口|回风口|给排水|下水槽|污水管|暖通|风口|减震器|手动报警|声光报警|点型探测|监控模块|远程执行机构|洗手盆'),
]
# Further scopes have no narrower supplied-template slot: keep the operation
# explicit rather than pretending they are the same product as another quote.
_RULES[0:0] = [
('7.5',('媒体与传播','公关及广告发布'),r'pr and business|(?:户外|大屏组)广告发布|媒体变更|稿件角度规划|设计&传播'),
('1.1',('设计服务','概念与制图'),r'奖项咨询|设计咨询|前期方案.*设计|概念设计师|手绘地图|制图费|矩阵动态设计'),
('1.2',('技术咨询','技术文件及专家服务'),r'制作规范|专家费|场地勘查咨询|投标阶段'),
('1.3',('结构审核与设计','加固设计及稽核'),r'加固.*设计|独立稽核工程师'),
('4.2',('摄制与采集','数据解析与管理'),r'解析师|数据录入.*QAQC'),
('4.2',('摄制与制作','人员和器材合包'),r'人员及器材'),
('4.3',('数字内容','扫描与视频特效'),r'结构粗扫|^fx$'),
('4.3',('数字内容','视频整项制作'),r'走秀定制视频|^MR$|数字人导游|^视频设计$'),
('4.4',('后期制作','调整与转制'),r'竖版装置横版|视频直播及画面边框'),
('5.1',('软件与交互','功能开发与调整'),r'按空格键.*视频|运动控制|绘画互动|表格AI美化'),
('7.2',('项目执行','统筹与技术支持'),r'项目进度管理|技术人员|硬件工程师|增补服务人员|武汉兼职|PT面试|现场协调'),
('7.3',('项目保障','场地租用及配套费用'),r'场地租|场地使用|场地增加|场地物业|场地/设备差价|仓储费|临时设施费'),
('7.4',('项目保障','施工措施与配合'),r'异地施工|原遗留问题整改|水平及垂直放样|夜间施工补贴|^配合费$|空气处理|后勤保障物料'),
('3.4',('施工操作','安装与修复'),r'柱屏PAD固定|屏.*调整位置|摇头灯移位|搭建修复|搭建撤场|安装设备|^安装物料$|^安装工具$|装饰.*守场|^搭景费$|遮黑搭建|拼接.{0,2}组装|外包电工'),
('3.4',('施工操作','美工人工'),r'^美工$|美工人工'),
('3.7',('物流运输','包装及运费'),r'物料运费|包装及运费|定制航空箱'),
('2.1',('结构与固定','部件及辅助材料'),r'真空吸盘|固定辅材|滑轨屏结构|架子制作|架子打印|螺丝垫片|^分层架$|包立柱|楼板加固|挡水梁|木结构|下牛腿'),
('2.2',('表面及围护','装饰面层与线槽'),r'侧墙板|扇形折叠板|圆形外框|海绵墙|海绵护角|灯槽|撕膜|金属贴片|磁吸画面|原墙修补|机械手臂改色|^固化$|防炫光膜|玻璃.*处理'),
('2.3',('造型及陈设','定制造型及装饰'),r'艺术定位跟随装置|圆盘制作|火山岩|室内造景|粉砂岩|地基底面刷|^蜀绣$|护罩制作|汽车采购|汽车切割|定制木板盒|制作木板盒|数字孪生.*(?:圆形台|沙盘)'),
('2.4',('家具软装','陈设及器具'),r'演讲台|^BOSS flower$|软地垫|酒杯及冰块|接水盆|包凳子'),
('2.6',('照明系统','灯具及灯光配件'),r'补光灯材料'),
('2.7',('媒体与交互硬件','监控及传输设备'),r'枪机|测温半球|网络高清球机|价签基站|功率放大器|空白面板|打印设备|异形模组|^lax4$'),
('2.7',('设备配套','保护及附件'),r'其他工程辅件|眼镜保护罩|眼镜收纳盒|一次性眼罩|近视眼镜|屏体内部材料|展厅硬件|室外箱.*杆'),
('7.8',('建筑机电','消防及管道'),r'灭火器|管道安装|^模块箱$|控制模块安装'),
('2.7',('机械设备','轨道及控制'),r'火车轨道'),
('7.4',('项目保障','临时设施及设备合包'),r'水马.*帐篷|Ground Installation & AV Equipment'),
('1.1',('整项设计制作','水秀综合服务'),r'水景开幕秀设计制作及落地服务'),
('4.1',('创意与撰稿','文字内容'),r'英文原稿|文档笔译'),
]
_RULES[0:0] = [
('7.2',('项目执行','项目经理'),r'project manager|event manager'),
('7.3',('场地服务','租用'),r'venue rental'),
('7.6',('餐饮服务','餐饮整包'),r'catering'),
('7.7',('网络服务','专线升级'),r'dedicated line network'),
('4.5',('音频服务','音频及音乐处理'),r'audio and music handling'),
('2.3',('定制道具','品牌道具'),r'branded props'),
('7.9',('表演服务','节目整包'),r'special performances'),
('1.2',('技术咨询与图纸','踏勘及法定提交整包'),r'site condition survey'),
('1.2',('技术文档','报告副本或修订'),r'certified true copy of report'),
('2.1',('结构工程','加垫钢板'),r'installation of additional steel shim'),
('1.3',('技术监督','注册监督人员'),r'RGBC TCP'),
('1.2',('现场测量','测量放样'),r'setting out and survey'),
('2.1',('通行结构','爬梯和维修平台'),r'additional cat ladder'),
('3.13',('现场保障','紧急到场及现场协调'),r'emergency attendance'),
('4.2',('表演人员','模特及走秀'),r'\bmodels\b|runway area'),
('2.5',('平面制作','印刷品及报告印制'),r'printed materials|printing report'),
('2.7',('显示设备','屏体配套材料'),r'materials for led wall'),
('5.3',('系统实施','系统技术专家'),r'system specialist'),
('2.2',('表面处理','热浸镀锌'),r'hot dip galvanized'),
('3.4',('建筑施工','灌浆及模板'),r'forming and non-shrink grouting'),
('1.2',('技术测量','复测'),r're-surveying'),
('2.2',('建筑改造','开孔及恢复'),r'reinstatement|cutting and opening|opening (?:for|on|at)'),
('3.4',('施工措施','临时改造及恢复合包'),r'associated temporary.*reinstatement'),
('7.5',('品牌传播','视频播出权益'),r'开场视频轮播'),
('2.7',('设备采购','多媒体设备整包'),r'^.*多媒体设备(?:采购合同|租赁)$'),
('3.4',('制作搭建','整体承揽'),r'^.*搭建承揽(?:合同)?$'),
]
_COMPILED=[(code,leaf,re.compile(pattern,re.I)) for code,leaf,pattern in _RULES]


def row_route(row):
    """Return code/leaf/evidence only when actual row wording supports a scope."""
    if row.get('kind') == 'ledger_only': return None
    name=str(row.get('item_name') or '').strip()
    detail=' '.join(str(row.get(k) or '') for k in ('spec','description'))
    module=str(row.get('module') or row.get('work_package') or '')
    # The deliverable is explicit here. Projection is a playback context, not
    # proof of a projector purchase, when the item itself is digital content.
    if re.match(r'^数字(?:内容|模型)[（(]', name):
        post = bool(re.search(r'剪辑|调色|合成', detail))
        leaf = ('数字内容制作', '剪辑与画面制作' if post else
                '虚拟模型与动画' if name.startswith('数字模型') else '内容制作；工序未细列')
        return {'code':'4.4' if post else '4.3', 'leaf':leaf,
                'evidence_field':'item_name', 'evidence_text':name,
                'method':'explicit_digital_deliverable_not_playback_hardware', 'priority':True}
    if re.search(r'灯光.*设计.*编程|水舞设计',name):
        return {'code':'1.2','leaf':('演艺技术服务','灯光或水舞设计编程'),'evidence_field':'item_name','evidence_text':name,'method':'explicit_service_operation','priority':True}
    if re.search(r'二维码.*快递',name):
        return {'code':'7.4','leaf':('复合采购服务','二维码印制＋加急快递'),'evidence_field':'item_name','evidence_text':name,'method':'explicit_package_not_split','priority':True}
    if re.search(r'安装费|安装人工',module) and re.search(r'门|玻璃|设备',name):
        return {'code':'3.4','leaf':('现场安装','门窗或设备安装；不含材料采购认定'),'evidence_field':'module','evidence_text':module,'method':'explicit_parent_operation','priority':True}
    if re.search(r'资质|许可|报批|报备|公安咨询|城管咨询|statutory requirements',name,re.I):
        return {'code':'7.1','leaf':('行政与报批','资质或施工许可'),'evidence_field':'item_name','evidence_text':name,'method':'explicit_administrative_service','priority':True}
    # An unread name must not inherit an arbitrary object from project-wide text.
    if not name or re.fullmatch(r'\d+|\[不清\]|原空名称赠送行|国产定制|/',name):return None
    if re.search(r'供稿直发|品牌稿件',detail):
        return {'code':'7.5','leaf':('媒体传播','供稿发布'),'evidence_field':'spec','evidence_text':detail,'method':'row_description'}
    if name == '内容' and row.get('unit') == '秒':
        return {'code':'4.3','leaf':('数字内容','按时长内容；工序未细列'),'evidence_field':'unit','evidence_text':'内容／秒','method':'explicit_billing_and_object'}
    if name == 'source_package_amount' and re.search(r'独立结构服务',detail):
        return {'code':'2.1','leaf':('整项结构服务','具体构件未细列'),'evidence_field':'description','evidence_text':detail,'method':'explicit_parent_scope'}
    if name == '设备空间' and re.search(r'板木结构',detail):
        return {'code':'2.3','leaf':('定制展具','设备围护空间'),'evidence_field':'spec','evidence_text':detail,'method':'row_description'}
    if name == 'YAMAHA' and re.search(r'接口箱.*进.*出',detail):
        return {'code':'2.7','leaf':('音频系统','接口及调音设备；具体型号未列'),'evidence_field':'spec','evidence_text':detail,'method':'row_description'}
    if name == '辅料' and re.search(r'镜钉|螺丝',detail):
        return {'code':'2.1','leaf':('固定件','螺钉及镜钉'),'evidence_field':'spec','evidence_text':detail,'method':'row_description'}
    for code,leaf,rx in _COMPILED:
        found=rx.search(name)
        if found:
            return {'code':code,'leaf':leaf,'evidence_field':'item_name','evidence_text':found[0],
                    'method':'source_object_and_operation'}
    if name == '控制系统':
        code,leaf=('5.1',('软件控制','中控程序')) if re.search(r'开发|运行|后台',detail) else ('2.7',('控制系统','具体配置未列'))
        return {'code':code,'leaf':leaf,'evidence_field':'description' if detail else 'item_name','evidence_text': detail or name,'method':'explicit_scope_not_component_inference'}
    if name in {'辅材','辅料','辅助材料','辅材及辅件','其他工程辅件','辅材及大型机具'}:
        specifics=[('网络线缆及跳线',r'cat.?6|网线|跳线'),('视频转换与连接',r'视频.*转接|视频.*连接'),('音频线缆',r'音响线|音频线'),('供电线材',r'供电线|平方线径')]
        for leaf,pattern in specifics:
            m=re.search(pattern,detail,re.I)
            if m:return {'code':'2.7' if leaf != '供电线材' else '2.6','leaf':('系统配套',leaf),'evidence_field':'spec_or_description','evidence_text':m[0],'method':'explicit_configuration','priority':True}
        if re.search(r'电|网络|设备|灯箱|集成|供电|VR|智能化',module+' '+detail,re.I):
            return {'code':'2.7','leaf':('系统配套','辅材合包；具体配置未列'),'evidence_field':'module','evidence_text':module,'method':'explicit_parent_scope'}
    if name == '轨道' and '灯具' in module:
        return {'code':'2.6','leaf':('灯具配件','轨道'),'evidence_field':'module','evidence_text':module,'method':'explicit_parent_scope'}
    # Modules are scopes, not names: a room name in an explicitly digital-model
    # schedule may identify a scene, whereas a room name alone proves nothing.
    scoped = [
      ('4.3',('数字资产','场景或画面明细'),r'效果图|model.*模型|模型制作|数字内容|美术内容|裸眼3d|cg视频|tvc三维|mr视频|内容制作'),
      ('4.4',('后期制作','画面调整明细'),r'合成与调色|剪辑|ae短片'),
      ('5.1',('软件与交互','功能明细'),r'软件开发|程序功能|互动.*技术开发|ui.*中控'),
      ('1.1',('品牌设计','视觉规范明细'),r'品牌标志设计|品牌视觉系统|品牌设计规划|衍生品设计'),
      ('7.2',('项目执行','活动协作明细'),r'活动前|人员执行|运营|安全健康管理顾问'),
      ('7.5',('媒体与传播','广告发布或品牌合作'),r'品牌稿件发布|品牌曝光|赛事共建|户外广告发布|tower ooh|广告刊例|媒体变更'),
    ]
    for code,leaf,pattern in scoped:
        m=re.search(pattern,module,re.I)
        if m:return {'code':code,'leaf':leaf,'evidence_field':'module','evidence_text':m[0],
                     'method':'explicit_parent_scope'}
    # A generic item can use its own source description; never scan all other
    # contract items to transplant their material identity.
    if name in {'确认函','内容','调整','制作费','新增内容','增补服务','服务费','换新','定制','辅助器材','灯光费用','材料费'}:
        for code,leaf,rx in _COMPILED:
            found=rx.search(detail)
            if found:return {'code':code,'leaf':leaf,'evidence_field':'description',
                             'evidence_text':found[0],'method':'row_description'}
    title = str(row.get('work_package') or row.get('contract_name') or '')
    if name == '场地':
        return {'code':'7.3','leaf':('场地服务','范围及设施未细列'),'evidence_field':'item_name','evidence_text':name,'method':'explicit_scope_not_component_inference'}
    if name == '辅助器材' and re.search(r'拍摄',title):
        return {'code':'4.2','leaf':('摄制器材','辅助器材；配置未列'),'evidence_field':'contract_name','evidence_text':title,'method':'explicit_parent_scope'}
    if name == '换新' and re.search(r'鲜花',module):
        return {'code':'2.4','leaf':('花艺服务','鲜花换新'),'evidence_field':'module','evidence_text':module,'method':'explicit_parent_scope'}
    if name in {'第一次追加','第二次追加'} and module == '场地部分':
        return {'code':'7.3','leaf':('场地服务','追加费用；配置未列'),'evidence_field':'module','evidence_text':module,'method':'explicit_parent_scope'}
    if name in {'确认函','调整','内容','材质','曲水流觞','笔墨丹青','粒子星河','综合控制','梅兰竹菊','新增内容'}:
        text = detail+' '+module+' '+title
        scoped_context = [('4.1',('创意策划','方案及时间规划'),r'策划方案PPT'),
                          ('4.4',('后期制作','画面调整'),r'画幅|KV制作|构图调整'),
                          ('4.3',('数字内容','内容演绎；工序未细列'),r'数字内容|内容开发协议（无硬件）|MR|定制内容演绎|粒子化|IP形象活化'),
                          ('4.3',('数字内容','材质制作'),r'CG|建模')]
        for code,leaf,pattern in scoped_context:
            m=re.search(pattern,text,re.I)
            if m:return {'code':code,'leaf':leaf,'evidence_field':'source_scope','evidence_text':m[0],'method':'explicit_parent_scope'}
    return None
