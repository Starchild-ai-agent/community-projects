"""
生辰八字计算核心算法
"""

from datetime import date


# 天干
STEMS = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']
# 地支
BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

# 天干五行
STEM_ELEMENT = {
    '甲': '木', '乙': '木',
    '丙': '火', '丁': '火',
    '戊': '土', '己': '土',
    '庚': '金', '辛': '金',
    '壬': '水', '癸': '水',
}

# 地支五行
BRANCH_ELEMENT = {
    '寅': '木', '卯': '木',
    '巳': '火', '午': '火',
    '申': '金', '酉': '金',
    '亥': '水', '子': '水',
    '辰': '土', '戌': '土', '丑': '土', '未': '土',
}

# 月支（1月=寅, 2月=卯, ... 12月=丑）
MONTH_BRANCH = [
    None,   # index 0 placeholder
    '寅',   # 1月
    '卯',   # 2月
    '辰',   # 3月
    '巳',   # 4月
    '午',   # 5月
    '未',   # 6月
    '申',   # 7月
    '酉',   # 8月
    '戌',   # 9月
    '亥',   # 10月
    '子',   # 11月
    '丑',   # 12月
]

# 五虎遁：年干 -> 正月（寅月）天干
# 甲己之年丙作首
# 乙庚之年戊为头
# 丙辛必定寻庚起
# 丁壬壬位顺行流
# 戊癸甲寅好追求
YEAR_STEM_TO_FIRST_MONTH_STEM = {
    0: 2,   # 甲 -> 丙
    5: 2,   # 己 -> 丙
    1: 4,   # 乙 -> 戊
    6: 4,   # 庚 -> 戊
    2: 6,   # 丙 -> 庚
    7: 6,   # 辛 -> 庚
    3: 8,   # 丁 -> 壬
    8: 8,   # 壬 -> 壬
    4: 0,   # 戊 -> 甲
    9: 0,   # 癸 -> 甲
}

# 五鼠遁：日干 -> 子时天干
# 甲己还加甲
# 乙庚丙作初
# 丙辛从戊起
# 丁壬庚子居
# 戊癸壬子头
DAY_STEM_TO_ZI_HOUR_STEM = {
    0: 0,   # 甲 -> 甲
    5: 0,   # 己 -> 甲
    1: 2,   # 乙 -> 丙
    6: 2,   # 庚 -> 丙
    2: 4,   # 丙 -> 戊
    7: 4,   # 辛 -> 戊
    3: 6,   # 丁 -> 庚
    8: 6,   # 壬 -> 庚
    4: 8,   # 戊 -> 壬
    9: 8,   # 癸 -> 壬
}

# 基准日：2000年1月1日 = 戊午日
# 戊 = index 4, 午 = index 6
BASE_DATE = date(2000, 1, 1)
BASE_STEM_INDEX = 4
BASE_BRANCH_INDEX = 6


def _year_pillar(year):
    """年柱：以公历年份为准（简化版，不做立春精确分界）"""
    stem_idx = (year - 4) % 10
    branch_idx = (year - 4) % 12
    return STEMS[stem_idx] + BRANCHES[branch_idx], stem_idx


def _month_pillar(year, month, year_stem_idx):
    """月柱：固定月支 + 五虎遁推月干"""
    branch = MONTH_BRANCH[month]
    branch_idx = BRANCHES.index(branch)
    # 正月（寅月）天干
    first_stem_idx = YEAR_STEM_TO_FIRST_MONTH_STEM[year_stem_idx]
    # 从寅月（index 2 in BRANCHES 即正月）顺推到当前月
    # 寅月 = month 1, branch_idx=2
    offset = month - 1
    stem_idx = (first_stem_idx + offset) % 10
    return STEMS[stem_idx] + branch, stem_idx


def _day_pillar(year, month, day):
    """日柱：基于2000-01-01=戊午日"""
    target = date(year, month, day)
    days_diff = (target - BASE_DATE).days
    stem_idx = (BASE_STEM_INDEX + days_diff) % 10
    branch_idx = (BASE_BRANCH_INDEX + days_diff) % 12
    return STEMS[stem_idx] + BRANCHES[branch_idx], stem_idx


def _hour_pillar(hour, day_stem_idx):
    """时柱：时支 + 五鼠遁推时干"""
    # 时辰地支索引：子=0, 丑=1, ... 亥=11
    # 23-1点=子(idx 0), 1-3=丑(idx 1), 3-5=寅(idx 2), ...
    if hour == 23 or hour == 0:
        hour_branch_idx = 0  # 子
    else:
        # hour in [1,22], map to idx (hour+1)//2
        hour_branch_idx = (hour + 1) // 2
    branch = BRANCHES[hour_branch_idx]
    # 子时天干
    first_stem_idx = DAY_STEM_TO_ZI_HOUR_STEM[day_stem_idx]
    stem_idx = (first_stem_idx + hour_branch_idx) % 10
    return STEMS[stem_idx] + branch, stem_idx


def _count_elements(year_stem, month_stem, day_stem, hour_stem,
                    year_branch, month_branch, day_branch, hour_branch):
    """统计八字中五行数量"""
    elements = {'金': 0, '木': 0, '水': 0, '火': 0, '土': 0}
    for s in [year_stem, month_stem, day_stem, hour_stem]:
        elements[STEM_ELEMENT[s]] += 1
    for b in [year_branch, month_branch, day_branch, hour_branch]:
        elements[BRANCH_ELEMENT[b]] += 1
    return elements


def _analyze(day_master, day_master_element, elements):
    """简单命理分析"""
    count = elements[day_master_element]
    if count >= 3:
        strength = '偏强'
        advice = (
            f"你的日主为{day_master}（{day_master_element}），"
            f"在八字中出现{count}次，五行偏{day_master_element}气较旺，"
            f"属于「{strength}」格局。建议行事宜柔和、谦逊，"
            f"宜从事泄秀或耗{day_master_element}之行业（如{'火' if day_master_element == '木' else '土' if day_master_element == '火' else '金' if day_master_element == '土' else '水' if day_master_element == '金' else '木'}相关），"
            f"以平衡五行。"
        )
    elif count <= 1:
        strength = '偏弱'
        advice = (
            f"你的日主为{day_master}（{day_master_element}），"
            f"在八字中仅出现{count}次，五行{day_master_element}气不足，"
            f"属于「{strength}」格局。建议多接触生助{day_master_element}之事物，"
            f"可借助同类或生扶之五行来增强运势，"
            f"生活中宜稳健、循序渐进，避免过度消耗。"
        )
    else:
        strength = '中和'
        advice = (
            f"你的日主为{day_master}（{day_master_element}），"
            f"在八字中出现{count}次，五行较为均衡，"
            f"属于「{strength}」格局。命局整体协调，性格稳重，"
            f"宜顺势而为，根据流年五行变化灵活调整，"
            f"可发挥自身优势，把握机遇。"
        )
    return strength, advice


def calculate_bazi(year, month, day, hour):
    """
    计算生辰八字

    Args:
        year: 公历年 (int)
        month: 月 (1-12, int)
        day: 日 (1-31, int)
        hour: 时 (0-23, int)

    Returns:
        dict 包含四柱、日主、五行分布、强度、命理分析
    """
    year_pillar, year_stem_idx = _year_pillar(year)
    month_pillar, _ = _month_pillar(year, month, year_stem_idx)
    day_pillar, day_stem_idx = _day_pillar(year, month, day)
    hour_pillar, _ = _hour_pillar(hour, day_stem_idx)

    # 提取天干地支
    year_stem, year_branch = year_pillar[0], year_pillar[1]
    month_stem, month_branch = month_pillar[0], month_pillar[1]
    day_stem, day_branch = day_pillar[0], day_pillar[1]
    hour_stem, hour_branch = hour_pillar[0], hour_pillar[1]

    # 日主
    day_master = day_stem
    day_master_element = STEM_ELEMENT[day_master]

    # 统计五行
    elements = _count_elements(
        year_stem, month_stem, day_stem, hour_stem,
        year_branch, month_branch, day_branch, hour_branch,
    )

    # 命理分析
    strength, analysis = _analyze(day_master, day_master_element, elements)

    return {
        'year_pillar': year_pillar,
        'month_pillar': month_pillar,
        'day_pillar': day_pillar,
        'hour_pillar': hour_pillar,
        'day_master': day_master,
        'day_master_element': day_master_element,
        'elements': elements,
        'strength': strength,
        'analysis': analysis,
        'year': year,
        'month': month,
        'day': day,
        'hour': hour,
    }
