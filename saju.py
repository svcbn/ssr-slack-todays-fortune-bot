"""
Korean Four Pillars of Destiny (사주팔자) Calculator
A comprehensive module for calculating and analyzing Korean astrology/fortune reading.

Author: Claude Code
Date: 2026-04-05
"""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json


# ============================================================================
# CONSTANTS AND MAPPINGS
# ============================================================================

# Heavenly Stems (천간)
HEAVENLY_STEMS = ['갑', '을', '병', '정', '무', '기', '경', '신', '임', '계']
HEAVENLY_STEMS_CH = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸']

# Earthly Branches (지지)
EARTHLY_BRANCHES = ['자', '축', '인', '묘', '진', '사', '오', '미', '신', '유', '술', '해']
EARTHLY_BRANCHES_CH = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

# Hours mapping (시간대)
HOUR_CODES = {
    0: ('자시', '자'),      # 23:00-01:00
    1: ('축시', '축'),      # 01:00-03:00
    2: ('인시', '인'),      # 03:00-05:00
    3: ('묘시', '묘'),      # 05:00-07:00
    4: ('진시', '진'),      # 07:00-09:00
    5: ('사시', '사'),      # 09:00-11:00
    6: ('오시', '오'),      # 11:00-13:00
    7: ('미시', '미'),      # 13:00-15:00
    8: ('신시', '신'),      # 15:00-17:00
    9: ('유시', '유'),      # 17:00-19:00
    10: ('술시', '술'),     # 19:00-21:00
    11: ('해시', '해'),     # 21:00-23:00
    12: ('모름', '모름'),   # Unknown
}

# Five Elements (오행) mapping - SEPARATE for stems and branches
# to avoid key collision (천간 신(辛)=금 vs 지지 신(申)=금)
STEM_ELEMENT = {
    '갑': '목', '을': '목',
    '병': '화', '정': '화',
    '무': '토', '기': '토',
    '경': '금', '신': '금',
    '임': '수', '계': '수',
}
BRANCH_ELEMENT = {
    '인': '목', '묘': '목',
    '사': '화', '오': '화',
    '진': '토', '술': '토', '축': '토', '미': '토',
    '신': '금', '유': '금',
    '해': '수', '자': '수',
}

# Yin-Yang (음양) mapping - SEPARATE to avoid collision
# 천간 신(辛)=음, 지지 신(申)=양 ← 같은 글자지만 음양이 다름!
STEM_YINYANG = {
    '갑': '양', '을': '음',
    '병': '양', '정': '음',
    '무': '양', '기': '음',
    '경': '양', '신': '음',
    '임': '양', '계': '음',
}
BRANCH_YINYANG = {
    '자': '양', '축': '음',
    '인': '양', '묘': '음',
    '진': '양', '사': '음',
    '오': '양', '미': '음',
    '신': '양', '유': '음',
    '술': '양', '해': '음',
}

# Production cycle (상생): A produces B
PRODUCTION_CYCLE = {
    '목': '화', '화': '토', '토': '금', '금': '수', '수': '목'
}

# Overcoming cycle (상극): A overcomes B
OVERCOMING_CYCLE = {
    '목': '토', '토': '수', '수': '화', '화': '금', '금': '목'
}

# Solar Terms Boundaries (approximate dates)
SOLAR_TERMS = [
    (2, 4, '인'),      # 입춘 - Start of Spring
    (3, 6, '묘'),      # 경칩 - Awakening of Insects
    (4, 5, '진'),      # 청명 - Clear and Bright
    (5, 6, '사'),      # 입하 - Start of Summer
    (6, 6, '오'),      # 망종 - Grain in Ear
    (7, 7, '미'),      # 소서 - Minor Heat
    (8, 8, '신'),      # 입추 - Start of Autumn
    (9, 8, '유'),      # 백로 - White Dew
    (10, 8, '술'),     # 한로 - Cold Dew
    (11, 7, '해'),     # 입동 - Start of Winter
    (12, 7, '자'),     # 대설 - Major Snow
    (1, 6, '축'),      # 소한 - Minor Cold
]

# Harmonies and Clashes
HEAVENLY_STEM_HARMONY = {
    ('갑', '기'): '합', ('기', '갑'): '합',
    ('을', '경'): '합', ('경', '을'): '합',
    ('병', '신'): '합', ('신', '병'): '합',
    ('정', '임'): '합', ('임', '정'): '합',
    ('무', '계'): '합', ('계', '무'): '합',
}

HEAVENLY_STEM_CLASH = {
    ('갑', '경'): '충', ('경', '갑'): '충',
    ('을', '신'): '충', ('신', '을'): '충',
    ('병', '임'): '충', ('임', '병'): '충',
    ('정', '계'): '충', ('계', '정'): '충',
}

EARTHLY_BRANCH_SIX_HARMONY = {
    ('자', '축'): '합', ('축', '자'): '합',
    ('인', '해'): '합', ('해', '인'): '합',
    ('묘', '술'): '합', ('술', '묘'): '합',
    ('진', '유'): '합', ('유', '진'): '합',
    ('사', '신'): '합', ('신', '사'): '합',
    ('오', '미'): '합', ('미', '오'): '합',
}

EARTHLY_BRANCH_CLASH = {
    ('자', '오'): '충', ('오', '자'): '충',
    ('축', '미'): '충', ('미', '축'): '충',
    ('인', '신'): '충', ('신', '인'): '충',
    ('묘', '유'): '충', ('유', '묘'): '충',
    ('진', '술'): '충', ('술', '진'): '충',
    ('사', '해'): '충', ('해', '사'): '충',
}

# Three Harmonies (삼합)
THREE_HARMONIES = {
    ('신', '자', '진'): '합', ('자', '신', '진'): '합', ('진', '신', '자'): '합',
    ('해', '묘', '미'): '합', ('묘', '해', '미'): '합', ('미', '해', '묘'): '합',
    ('인', '오', '술'): '합', ('오', '인', '술'): '합', ('술', '인', '오'): '합',
    ('사', '유', '축'): '합', ('유', '사', '축'): '합', ('축', '사', '유'): '합',
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def stem_to_index(stem: str) -> int:
    """Convert stem character to index (0-9)."""
    return HEAVENLY_STEMS.index(stem) if stem in HEAVENLY_STEMS else -1

def branch_to_index(branch: str) -> int:
    """Convert branch character to index (0-11)."""
    return EARTHLY_BRANCHES.index(branch) if branch in EARTHLY_BRANCHES else -1

def index_to_stem(index: int) -> str:
    """Convert index to stem character."""
    return HEAVENLY_STEMS[index % 10]

def index_to_branch(index: int) -> str:
    """Convert index to branch character."""
    return EARTHLY_BRANCHES[index % 12]

def get_stem_element(stem: str) -> str:
    """Get the Five Element for a heavenly stem."""
    return STEM_ELEMENT.get(stem, '')

def get_branch_element(branch: str) -> str:
    """Get the Five Element for an earthly branch."""
    return BRANCH_ELEMENT.get(branch, '')

def get_element(char: str) -> str:
    """Get the Five Element for a stem or branch (auto-detect)."""
    return STEM_ELEMENT.get(char, '') or BRANCH_ELEMENT.get(char, '')

def get_stem_yinyang(stem: str) -> str:
    """Get the Yin-Yang for a heavenly stem."""
    return STEM_YINYANG.get(stem, '')

def get_branch_yinyang(branch: str) -> str:
    """Get the Yin-Yang for an earthly branch."""
    return BRANCH_YINYANG.get(branch, '')

def get_yinyang(char: str, is_stem: bool = True) -> str:
    """Get the Yin-Yang for a stem or branch. is_stem disambiguates 신(辛) vs 신(申)."""
    if is_stem:
        return STEM_YINYANG.get(char, '') or BRANCH_YINYANG.get(char, '')
    else:
        return BRANCH_YINYANG.get(char, '') or STEM_YINYANG.get(char, '')

def is_same_yinyang(stem1: str, stem2: str) -> bool:
    """Check if two heavenly stems have the same Yin-Yang."""
    return get_stem_yinyang(stem1) == get_stem_yinyang(stem2)

def get_month_branch_for_date(month: int, day: int) -> str:
    """
    Get the Earthly Branch for the month based on solar terms.
    Solar terms determine month boundaries in lunar calendar calculation.
    """
    for term_month, term_day, branch in SOLAR_TERMS:
        if month == term_month:
            if day >= term_day:
                return branch
            else:
                # Return the branch from the previous solar term
                for i, (tm, td, br) in enumerate(SOLAR_TERMS):
                    if tm == month - 1 or (month == 1 and tm == 12):
                        return br
    return EARTHLY_BRANCHES[month - 1]  # Fallback


# ============================================================================
# CORE PILLAR CALCULATIONS
# ============================================================================

def calculate_day_pillar(date_str: str) -> Tuple[str, str]:
    """
    Calculate Day Pillar (일주) using the Julian Day Number algorithm.
    Reference: January 1, 1900 is 甲子(갑자) - index 0 in 60-cycle.

    Args:
        date_str: Date in format YYYY-MM-DD

    Returns:
        Tuple of (stem, branch)
    """
    # Parse the date
    year, month, day = map(int, date_str.split('-'))

    # Reference: Jan 1, 1900 is 갑자 (index 0)
    reference_date = datetime(1900, 1, 1)
    target_date = datetime(year, month, day)

    # Calculate days difference
    days_diff = (target_date - reference_date).days

    # 갑자 is at position 0 in the 60-cycle
    cycle_index = days_diff % 60

    stem_index = cycle_index % 10
    branch_index = cycle_index % 12

    stem = index_to_stem(stem_index)
    branch = index_to_branch(branch_index)

    return stem, branch


def calculate_year_pillar(date_str: str) -> Tuple[str, str]:
    """
    Calculate Year Pillar (년주).
    The year changes at 입춘 (Start of Spring, ~Feb 4).
    If the birth date is before 입춘, use the previous year.

    Args:
        date_str: Date in format YYYY-MM-DD

    Returns:
        Tuple of (stem, branch)
    """
    year, month, day = map(int, date_str.split('-'))

    # If date is before Feb 4 (입춘), use previous year
    if month < 2 or (month == 2 and day < 4):
        year -= 1

    # Calculate the day pillar for Jan 1 of that year
    jan_1_str = f"{year}-01-01"
    ref_stem, _ = calculate_day_pillar("1900-01-01")  # Get reference

    # The year stem cycles every 10 years
    # We need to find what stem corresponds to this year
    # Use a known reference: 1900 is 庚子 (경자)
    # Actually, let's use the lunar new year day to get the year pillar

    # Alternative: Calculate from a known reference year
    # 1984-02-04 was 甲子 year (입춘)
    reference_year = 1984
    reference_stem_idx = 0  # 갑
    reference_branch_idx = 0  # 자

    years_from_ref = year - reference_year

    stem_idx = (reference_stem_idx + years_from_ref) % 10
    branch_idx = (reference_branch_idx + years_from_ref) % 12

    stem = index_to_stem(stem_idx)
    branch = index_to_branch(branch_idx)

    return stem, branch


def calculate_month_pillar(year: int, month: int, day: int, year_stem: str) -> Tuple[str, str]:
    """
    Calculate Month Pillar (월주).
    The month branch is determined by solar terms (절기).
    The month stem follows a pattern based on the year stem.

    Args:
        year: Year
        month: Month (1-12)
        day: Day of month
        year_stem: The year stem (needed for month stem calculation)

    Returns:
        Tuple of (stem, branch)
    """
    # Get month branch from solar terms
    month_branch = get_month_branch_for_date(month, day)

    # Month stem is calculated based on the year stem
    # The pattern follows a fixed cycle:
    # If year is 甲(0) or 己(5): 寅月(1)=丙寅, 卯月(2)=丁卯, etc.
    # The month stem advances by 2 from a base point

    year_stem_idx = stem_to_index(year_stem)
    branch_idx = branch_to_index(month_branch)

    # Month stem = (year_stem_idx * 2 + branch_idx) % 10
    # Actually, the formula is: month_stem_idx = (year_stem_idx * 2 + branch_idx) % 10
    month_stem_idx = (year_stem_idx * 2 + branch_idx) % 10
    month_stem = index_to_stem(month_stem_idx)

    return month_stem, month_branch


def calculate_hour_pillar(day_stem: str, hour_code: int) -> Tuple[str, str]:
    """
    Calculate Hour Pillar (시주).
    The hour branch is determined by the hour code (0-11 for 12 double-hours).
    The hour stem follows a pattern based on the day stem.

    Args:
        day_stem: The day stem
        hour_code: Hour code (0-11), where 0=자시, 11=해시, 12=unknown

    Returns:
        Tuple of (stem, branch) or ('모름', '모름') if hour_code == 12
    """
    if hour_code == 12:  # Unknown hour
        return '모름', '모름'

    hour_branch = index_to_branch(hour_code)

    # Hour stem is calculated based on day stem and hour branch
    # The cycle repeats every 5 days (5 stems x 12 hours = 60 hours, but simplified)
    # Formula: hour_stem_idx = (day_stem_idx * 2 + hour_code) % 10

    day_stem_idx = stem_to_index(day_stem)
    hour_stem_idx = (day_stem_idx * 2 + hour_code) % 10
    hour_stem = index_to_stem(hour_stem_idx)

    return hour_stem, hour_branch


def calculate_four_pillars(birth_date: str, hour_code: int) -> Dict[str, Tuple[str, str]]:
    """
    Calculate all four pillars of destiny.

    Args:
        birth_date: Date in format YYYY-MM-DD
        hour_code: Hour code (0-11, 12 for unknown)

    Returns:
        Dictionary with keys: year, month, day, hour
        Each value is a tuple of (stem, branch)
    """
    year, month, day = map(int, birth_date.split('-'))

    # Calculate pillars in order
    year_stem, year_branch = calculate_year_pillar(birth_date)
    day_stem, day_branch = calculate_day_pillar(birth_date)
    month_stem, month_branch = calculate_month_pillar(year, month, day, year_stem)
    hour_stem, hour_branch = calculate_hour_pillar(day_stem, hour_code)

    return {
        'year': (year_stem, year_branch),
        'month': (month_stem, month_branch),
        'day': (day_stem, day_branch),
        'hour': (hour_stem, hour_branch),
    }


# ============================================================================
# TEN GODS (십성) CALCULATION
# ============================================================================

def calculate_ten_god(day_stem: str, target_stem: str) -> str:
    """
    Calculate the Ten God relationship between day stem and target stem.
    Both arguments must be heavenly stems (천간).

    The Ten Gods (십성):
    - 비견: Same element, same Yin-Yang
    - 겁재: Same element, different Yin-Yang
    - 식신: Day stem produces target, same Yin-Yang
    - 상관: Day stem produces target, different Yin-Yang
    - 편인: Target produces day stem, same Yin-Yang
    - 정인: Target produces day stem, different Yin-Yang
    - 편재: Day stem overcomes target, same Yin-Yang
    - 정재: Day stem overcomes target, different Yin-Yang
    - 편관: Target overcomes day stem, same Yin-Yang
    - 정관: Target overcomes day stem, different Yin-Yang
    """
    day_element = get_stem_element(day_stem)
    target_element = get_stem_element(target_stem)
    same_yinyang = is_same_yinyang(day_stem, target_stem)

    if day_element == target_element:
        return '비견' if same_yinyang else '겁재'
    elif PRODUCTION_CYCLE[day_element] == target_element:
        return '식신' if same_yinyang else '상관'
    elif PRODUCTION_CYCLE[target_element] == day_element:
        return '편인' if same_yinyang else '정인'
    elif OVERCOMING_CYCLE[day_element] == target_element:
        return '편재' if same_yinyang else '정재'
    elif OVERCOMING_CYCLE[target_element] == day_element:
        return '편관' if same_yinyang else '정관'
    else:
        return '기타'


def calculate_ten_gods(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, Dict]:
    """
    Calculate Ten God relationships for all stems in the chart.

    Args:
        pillars: Dictionary with year, month, day, hour pillars

    Returns:
        Dictionary with ten gods for each pillar position
    """
    day_stem = pillars['day'][0]

    ten_gods = {}
    for position in ['year', 'month', 'day', 'hour']:
        stem, branch = pillars[position]
        if stem != '모름':
            ten_god = calculate_ten_god(day_stem, stem)
            ten_gods[position] = {
                'stem': stem,
                'branch': branch,
                'ten_god': ten_god,
                'element': get_stem_element(stem),
                'yinyang': get_stem_yinyang(stem),
            }
        else:
            ten_gods[position] = {
                'stem': '모름',
                'branch': '모름',
                'ten_god': '모름',
                'element': '모름',
                'yinyang': '모름',
            }

    return ten_gods


# ============================================================================
# HARMONIES AND CLASHES CALCULATION
# ============================================================================

def find_harmonies_and_clashes(pillars: Dict[str, Tuple[str, str]]) -> Dict[str, List[str]]:
    """
    Find all harmonies and clashes in the four pillars.

    Returns a dictionary with:
    - heavenly_stem_harmony: List of harmonious stem pairs
    - heavenly_stem_clash: List of clashing stem pairs
    - earthly_branch_six_harmony: List of six harmony pairs
    - earthly_branch_clash: List of clash pairs
    - earthly_branch_three_harmony: List of three harmony groups
    """
    stems = []
    branches = []

    for position in ['year', 'month', 'day', 'hour']:
        stem, branch = pillars[position]
        if stem != '모름':
            stems.append((position, stem))
            branches.append((position, branch))

    result = {
        'heavenly_stem_harmony': [],
        'heavenly_stem_clash': [],
        'earthly_branch_six_harmony': [],
        'earthly_branch_clash': [],
        'earthly_branch_three_harmony': [],
    }

    # Check heavenly stem harmonies and clashes
    for i, (pos1, stem1) in enumerate(stems):
        for pos2, stem2 in stems[i+1:]:
            key = (stem1, stem2)
            if key in HEAVENLY_STEM_HARMONY:
                result['heavenly_stem_harmony'].append({
                    'positions': [pos1, pos2],
                    'stems': [stem1, stem2],
                    'type': '천간합'
                })
            elif key in HEAVENLY_STEM_CLASH:
                result['heavenly_stem_clash'].append({
                    'positions': [pos1, pos2],
                    'stems': [stem1, stem2],
                    'type': '천간충'
                })

    # Check earthly branch harmonies and clashes
    for i, (pos1, branch1) in enumerate(branches):
        for pos2, branch2 in branches[i+1:]:
            key = (branch1, branch2)
            if key in EARTHLY_BRANCH_SIX_HARMONY:
                result['earthly_branch_six_harmony'].append({
                    'positions': [pos1, pos2],
                    'branches': [branch1, branch2],
                    'type': '지지육합'
                })
            elif key in EARTHLY_BRANCH_CLASH:
                result['earthly_branch_clash'].append({
                    'positions': [pos1, pos2],
                    'branches': [branch1, branch2],
                    'type': '지지충'
                })

    # Check earthly branch three harmonies
    branch_set = [b for _, b in branches if b != '모름']
    for i, (pos1, branch1) in enumerate(branches):
        if branch1 != '모름':
            for j, (pos2, branch2) in enumerate(branches[i+1:], i+1):
                if branch2 != '모름':
                    for k, (pos3, branch3) in enumerate(branches[j+1:], j+1):
                        if branch3 != '모름':
                            key = tuple(sorted([branch1, branch2, branch3]))
                            if key in THREE_HARMONIES or (branch1, branch2, branch3) in THREE_HARMONIES:
                                result['earthly_branch_three_harmony'].append({
                                    'positions': [pos1, pos2, pos3],
                                    'branches': [branch1, branch2, branch3],
                                    'type': '지지삼합'
                                })

    return result


# ============================================================================
# TODAY'S PILLAR CALCULATION
# ============================================================================

def calculate_today_pillar(today_date: str) -> Dict[str, Tuple[str, str]]:
    """
    Calculate today's pillar (오늘의 간지).

    Args:
        today_date: Date in format YYYY-MM-DD

    Returns:
        Dictionary with day pillar (stem, branch)
    """
    day_stem, day_branch = calculate_day_pillar(today_date)
    return {
        'day': (day_stem, day_branch)
    }


# ============================================================================
# MAIN CALCULATION FUNCTION
# ============================================================================

def calculate_fortune_data(
    birthday: str,
    gender: str,
    time_code: str,
    today_date: str
) -> Dict:
    """
    Calculate comprehensive fortune data based on birth date and time.

    Args:
        birthday: Birth date in format YYYY-MM-DD
        gender: Gender ('남' or '여')
        time_code: Time code as string ('0'-'12')
        today_date: Today's date in format YYYY-MM-DD

    Returns:
        Dictionary containing all calculated fortune data
    """
    hour_code = int(time_code)

    # Validate inputs
    try:
        datetime.strptime(birthday, '%Y-%m-%d')
        datetime.strptime(today_date, '%Y-%m-%d')
    except ValueError:
        return {'error': 'Invalid date format. Use YYYY-MM-DD'}

    if hour_code < 0 or hour_code > 12:
        return {'error': 'Invalid hour code. Use 0-12'}

    # Calculate four pillars
    pillars = calculate_four_pillars(birthday, hour_code)

    # Calculate ten gods
    ten_gods = calculate_ten_gods(pillars)

    # Calculate harmonies and clashes
    harmonies_clashes = find_harmonies_and_clashes(pillars)

    # Calculate today's pillar
    today_pillar = calculate_today_pillar(today_date)
    today_stem, today_branch = today_pillar['day']
    today_ten_god = calculate_ten_god(pillars['day'][0], today_stem)

    # Find harmonies/clashes between today's pillar and birth pillars
    extended_pillars = dict(pillars)
    extended_pillars['today'] = (today_stem, today_branch)
    today_interactions = find_harmonies_and_clashes(extended_pillars)

    # Compile results
    result = {
        'input': {
            'birthday': birthday,
            'gender': gender,
            'time_code': hour_code,
            'time_name': HOUR_CODES[hour_code][0],
            'today_date': today_date,
        },
        'four_pillars': {
            'year': {
                'stem': pillars['year'][0],
                'branch': pillars['year'][1],
                'stem_element': get_stem_element(pillars['year'][0]),
                'branch_element': get_branch_element(pillars['year'][1]),
                'stem_yinyang': get_stem_yinyang(pillars['year'][0]),
            },
            'month': {
                'stem': pillars['month'][0],
                'branch': pillars['month'][1],
                'stem_element': get_stem_element(pillars['month'][0]),
                'branch_element': get_branch_element(pillars['month'][1]),
                'stem_yinyang': get_stem_yinyang(pillars['month'][0]),
            },
            'day': {
                'stem': pillars['day'][0],
                'branch': pillars['day'][1],
                'stem_element': get_stem_element(pillars['day'][0]),
                'branch_element': get_branch_element(pillars['day'][1]),
                'stem_yinyang': get_stem_yinyang(pillars['day'][0]),
            },
            'hour': {
                'stem': pillars['hour'][0],
                'branch': pillars['hour'][1],
                'stem_element': get_stem_element(pillars['hour'][0]) if pillars['hour'][0] != '모름' else '모름',
                'branch_element': get_branch_element(pillars['hour'][1]) if pillars['hour'][1] != '모름' else '모름',
                'stem_yinyang': get_stem_yinyang(pillars['hour'][0]) if pillars['hour'][0] != '모름' else '모름',
            },
        },
        'ten_gods': ten_gods,
        'harmonies_and_clashes': harmonies_clashes,
        'today_pillar': {
            'stem': today_stem,
            'branch': today_branch,
            'stem_element': get_stem_element(today_stem),
            'branch_element': get_branch_element(today_branch),
            'stem_yinyang': get_stem_yinyang(today_stem),
            'ten_god_with_day_stem': today_ten_god,
        },
        'today_interactions': today_interactions,
        'day_stem_info': {
            'stem': pillars['day'][0],
            'element': get_stem_element(pillars['day'][0]),
            'yinyang': get_stem_yinyang(pillars['day'][0]),
        }
    }

    return result


# ============================================================================
# UTILITY FUNCTIONS FOR DISPLAY
# ============================================================================

def format_pillar(stem: str, branch: str) -> str:
    """Format a pillar for display."""
    if stem == '모름' or branch == '모름':
        return '모름'
    return f"{stem}{branch}"


def pillars_to_string(pillars: Dict[str, Tuple[str, str]]) -> str:
    """Convert pillars dictionary to a readable string."""
    result = []
    for position in ['year', 'month', 'day', 'hour']:
        stem, branch = pillars[position]
        result.append(f"{position}: {format_pillar(stem, branch)}")
    return '\n'.join(result)


# ============================================================================
# TEST AND EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Test case: Born 1990-05-15, male, 자시 (0), today 2026-04-05
    test_birthday = "1990-05-15"
    test_gender = "남"
    test_time_code = "0"
    test_today = "2026-04-05"

    print("=" * 70)
    print("Korean Four Pillars of Destiny (사주팔자) Calculator")
    print("=" * 70)
    print()

    result = calculate_fortune_data(test_birthday, test_gender, test_time_code, test_today)

    # Pretty print as JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()

    # Additional formatted output
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nBirth Date: {result['input']['birthday']}")
    print(f"Gender: {result['input']['gender']}")
    print(f"Birth Time: {result['input']['time_name']}")
    print(f"Today: {result['input']['today_date']}")
    print()

    print("FOUR PILLARS (사주):")
    print("-" * 70)
    pillars = result['four_pillars']
    for position in ['year', 'month', 'day', 'hour']:
        p = pillars[position]
        print(f"  {position.upper():6} : {p['stem']}{p['branch']:4} ({p['stem_yinyang']} {p['stem_element']})")
    print()

    print("TEN GODS (십성):")
    print("-" * 70)
    ten_gods = result['ten_gods']
    for position in ['year', 'month', 'day', 'hour']:
        tg = ten_gods[position]
        if tg['stem'] != '모름':
            print(f"  {position.upper():6} : {tg['ten_god']:4} ({tg['stem']}{tg['branch']})")
    print()

    print("HARMONIES AND CLASHES:")
    print("-" * 70)
    hc = result['harmonies_and_clashes']
    if hc['heavenly_stem_harmony']:
        print("  Heavenly Stem Harmonies (천간합):")
        for item in hc['heavenly_stem_harmony']:
            print(f"    {item['stems']}")
    if hc['heavenly_stem_clash']:
        print("  Heavenly Stem Clashes (천간충):")
        for item in hc['heavenly_stem_clash']:
            print(f"    {item['stems']}")
    if hc['earthly_branch_six_harmony']:
        print("  Earthly Branch Six Harmonies (지지육합):")
        for item in hc['earthly_branch_six_harmony']:
            print(f"    {item['branches']}")
    if hc['earthly_branch_clash']:
        print("  Earthly Branch Clashes (지지충):")
        for item in hc['earthly_branch_clash']:
            print(f"    {item['branches']}")
    if hc['earthly_branch_three_harmony']:
        print("  Earthly Branch Three Harmonies (지지삼합):")
        for item in hc['earthly_branch_three_harmony']:
            print(f"    {item['branches']}")
    if not any([hc['heavenly_stem_harmony'], hc['heavenly_stem_clash'],
                hc['earthly_branch_six_harmony'], hc['earthly_branch_clash'],
                hc['earthly_branch_three_harmony']]):
        print("  None found")
    print()

    print("TODAY'S PILLAR (오늘의 간지):")
    print("-" * 70)
    today = result['today_pillar']
    print(f"  Date: {result['input']['today_date']}")
    print(f"  Pillar: {today['stem']}{today['branch']} ({today['yinyang']} {today['element']})")
    print(f"  Relationship with Day Stem: {today['ten_god_with_day_stem']}")
    print()
