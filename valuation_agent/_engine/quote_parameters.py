"""Normalize comparable parameters while keeping the source wording for display."""
from decimal import Decimal
from functools import lru_cache
import re

NUMBER = r'\d+(?:\.\d+)?'
LENGTH_UNIT = r'mm|cm|毫米|厘米|米|m'
AXES = {
    'l': '长', '长': '长', 'w': '宽', '宽': '宽', 'h': '高', '高': '高',
    '直径': '直径', 'φ': '直径', 'ø': '直径', '厚度': '厚度', '厚': '厚度',
}
DIMENSION = re.compile(
    rf'(?<![a-wyz0-9])(?P<axis>l|w|h|直径|φ|ø|厚度|厚|长|宽|高)\s*[:=]?\s*'
    rf'(?P<number>{NUMBER})\s*(?P<unit>{LENGTH_UNIT})?(?![a-wyz\d.])'
)
UNLABELLED_SIZE = re.compile(rf'(?<![a-z0-9.])(?P<size>{NUMBER}(?:\s*[x×*]\s*{NUMBER}){{1,2}})'
                             rf'(?:\s*(?P<unit>{LENGTH_UNIT}))?(?![a-z\d.])')
THICKNESS = re.compile(rf'(?<![a-z0-9.])(?P<number>{NUMBER})\s*(?P<unit>{LENGTH_UNIT})\s*厚')
ELECTRICAL = re.compile(rf'(?P<number>{NUMBER})\s*(?P<unit>kw|千瓦|瓦|w|伏|v|k)(?![a-z])'
                        r'(?P<per_length>\s*[/／]\s*(?:米|m(?![a-z])))?')
LENGTH_FACTORS = {'mm': 1, '毫米': 1, 'cm': 10, '厘米': 10, 'm': 1000, '米': 1000}
ELECTRICAL_UNITS = {
    'kw': ('功率', 1000), '千瓦': ('功率', 1000), '瓦': ('功率', 1), 'w': ('功率', 1),
    '伏': ('电压', 1), 'v': ('电压', 1), 'k': ('色温', 1),
}


CABLE_SIZE = re.compile(r'(?<![a-z0-9])(?P<code>rvvp?|bvv?p?|rvsp|yjv)\s*(?P<cores>\d+)\s*[x×*]\s*(?P<area>\d+(?:[.,]\d+)?)(?![\d.])', re.I)


@lru_cache(maxsize=32768)
def normalize_specification_text(value):
    """Normalize decimal commas only inside known cable or labelled metric sizes.

    Never apply the monetary thousands-separator rule to a specification. Lists
    such as N100,8G and 320,160 stay intact.
    """
    value = re.sub(r'(?<![a-z0-9])((?:rvvp?|bvv?p?|rvsp|yjv)\s*\d+\s*[x×*]\s*\d+),(\d{1,2})(?!\d)',
                   r'\1.\2', value, flags=re.I)
    return re.sub(r'((?:直径|厚度|长|宽|高|厚|[lwhφø])\s*[:=]?\s*\d+),(\d{1,2})\s*(mm|cm|毫米|厘米|米|m)(?![a-z0-9])',
                  r'\1.\2\3', value, flags=re.I)


def parameters(value, default_dimension_unit=''):
    # Return independent dictionaries: current-query merging must not mutate a cache entry.
    return {label: dict(entries) for label, entries in _parameter_values(value, default_dimension_unit)}


@lru_cache(maxsize=32768)
def _parameter_values(value, default_dimension_unit=''):
    # Some original dimension cells omit a separator between two labelled axes.
    value = normalize_specification_text(value)
    value = re.sub(r'(?<=\d)(?=[lwh]\s*[:=]?\s*\d)', '×', value)
    output = {}
    # An explicit unit at the end of an axis chain applies to the other axes in that chain.
    for phrase in re.split(r'[，,；;。\n]', value):
        for match in THICKNESS.finditer(phrase):
            unit = match['unit']
            output.setdefault('厚度', {})[Decimal(match['number']) * LENGTH_FACTORS[unit]] = f'{match["number"]} {unit}'
        for group in re.split(r'、', phrase):
            axes = list(DIMENSION.finditer(group))
            for axis in axes:
                unit = axis['unit'] or (axes[-1]['unit'] if re.search('[x×*]', group) else '')
                unit = unit or default_dimension_unit
                factor = LENGTH_FACTORS.get(unit)
                key = AXES[axis['axis']]
                if factor is not None:
                    output.setdefault(key, {})[Decimal(axis['number']) * factor] = f'{axis["number"]} {unit}'
            if not axes:
                for size in UNLABELLED_SIZE.finditer(group):
                    unit = size['unit'] or default_dimension_unit
                    if unit in LENGTH_FACTORS:
                        key = tuple(Decimal(n) * LENGTH_FACTORS[unit] for n in re.findall(NUMBER, size['size']))
                        output.setdefault('尺寸', {})[key] = f'{size["size"]} {unit}'
        # Removing axes avoids treating a width marker such as 500×W700 as watts.
        for match in ELECTRICAL.finditer(DIMENSION.sub(' ', phrase)):
            key, factor = ELECTRICAL_UNITS[match['unit']]
            if key == '功率' and match['per_length']:
                key = '每米功率'
            amount = Decimal(match['number']) * factor
            if key != '色温' or amount >= 1000:
                output.setdefault(key, {})[amount] = match[0]
    for cable in CABLE_SIZE.finditer(value):
        area = Decimal(cable['area'].replace(',', '.'))
        output.setdefault('线缆截面积', {})[area] = cable['area'] + '（线缆规格编码）'
        output.setdefault('线缆芯数', {})[Decimal(cable['cores'])] = cable['cores'] + ' 芯'
    technical = (
        ('屏幕尺寸', rf'({NUMBER})\s*(?:英寸|寸|inch)', '寸'),
        ('刷新率', rf'({NUMBER})\s*hz', 'Hz'),
        ('像素间距', rf'(?:(?:像素间距|点间距|点距)\s*[:：]?\s*|(?<![a-z0-9])p)({NUMBER})\s*(?:mm)?', 'mm'),
        ('防护等级', r'ip\s*(\d{2})', 'IP'),
        ('帧率', rf'({NUMBER})\s*(?:fps|帧[/／]秒)', 'fps'),
        ('分辨率等级', r'(?<![a-z0-9])(2|4|8)\s*k(?![a-z])', 'K'),
    )
    for label, pattern, unit in technical:
        for match in re.finditer(pattern, value):
            number = Decimal(match[1])
            output.setdefault(label, {})[number] = f'{match[1]} {unit}'
    for match in re.finditer(rf'({NUMBER})\s*(秒|分钟|min(?:ute)?s?|seconds?|secs?)', value):
        factor = 60 if match[2] in ('分钟', 'min', 'mins', 'minute', 'minutes') else 1
        output.setdefault('成片时长', {})[Decimal(match[1]) * factor] = f'{Decimal(match[1]) * factor} 秒'
    for label, pattern in {'三渲二':r'三渲二|3d转2d', '写实':r'写实', '卡通':r'卡通|cartoon'}.items():
        if re.search(pattern, value):
            output.setdefault('视觉风格', {})[label] = label
    for match in re.finditer(rf'({NUMBER})\s*gb\s*[+＋/]\s*({NUMBER})\s*gb', value):
        output.setdefault('内存', {})[Decimal(match[1])] = f'{match[1]} GB'
        output.setdefault('存储', {})[Decimal(match[2])] = f'{match[2]} GB'
    forms = {'曲面/弧形屏': r'曲面|弧形|曲屏', '球幕/球形屏': r'球幕|球形屏|球屏',
             '超宽屏': r'超宽', '裸眼3D': r'裸眼\s*3d|裸3', '多楼层': r'多楼层|[2-6]f'}
    for label, pattern in forms.items():
        if re.search(pattern, value):
            output.setdefault('屏幕形态', {})[label] = label
    return tuple((label, tuple(values.items())) for label, values in output.items())


def parameter_comparison(current, historical):
    result = []
    for label in dict.fromkeys((*current, *historical)):
        before, after = current.get(label, {}), historical.get(label, {})
        result.append({'label': label, 'current': ' / '.join(before.values()),
                       'historical': ' / '.join(after.values()),
                       'different': bool(before and after and before.keys() != after.keys())})
    return result


def parameter_text_only(value):
    rest = ELECTRICAL.sub('', DIMENSION.sub('', UNLABELLED_SIZE.sub('', THICKNESS.sub('', value))))
    return not re.sub(r'功率|电压|色温|尺寸|[\s:：=/、,，;；x×*]+', '', rest)
