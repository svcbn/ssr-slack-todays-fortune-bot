import os
import json
import time
import requests
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from zoneinfo import ZoneInfo
import re

# Import saju calculation module
from saju import calculate_fortune_data

# Import shared utilities from main.py
from main import (
    env,
    env_bool,
    slack_api,
    slack_lists_items_list,
    parse_admin_ids,
    field_by_column,
    extract_name,
    extract_birthday,
    extract_select_option,
    extract_checkbox,
    extract_user_ids,
    validate_item,
    audit_list,
    fetch_all_list_items,
    build_rec_from_item,
    today_kst_dates,
    DEFAULT_COLS,
    DEFAULT_GENDER_OPT_TO_MF,
    DEFAULT_TIME_OPT_TO_CODE,
    TIME_CODE_TO_LABEL,
    WEEKDAY_KO,
)

# ============================================================================
# Constants
# ============================================================================

FOCUS_THEMES = [
    "관계운",
    "재물운",
    "건강운",
    "직장/학업운",
    "자기성찰",
]

# ============================================================================
# Utilities
# ============================================================================

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    cfg = {
        "slack_token": env("SLACK_BOT_TOKEN", required=True),
        "list_id": env("SLACK_LIST_ID", required=True),
        "admin_user_ids": parse_admin_ids(env("ADMIN_USER_IDS", "")),
        "anthropic_key": env("ANTHROPIC_API_KEY", required=True),
        "anthropic_model": env("CLAUDE_MODEL", "claude-sonnet-4-6"),
        "output_dir": env("OUTPUT_DIR", "output"),
    }

    # Column overrides
    cfg["cols"] = {
        "gender_col": env("GENDER_COL_ID", DEFAULT_COLS["gender_col"]),
        "time_col": env("TIME_COL_ID", DEFAULT_COLS["time_col"]),
        "birthday_col": env("BIRTHDAY_COL_ID", DEFAULT_COLS["birthday_col"]),
        "private_col": env("PRIVATE_COL_ID", DEFAULT_COLS["private_col"]),
        "assignee_col": env("ASSIGNEE_COL_ID", DEFAULT_COLS["assignee_col"]),
    }

    # Option overrides (gender)
    gender_opt_m = env("GENDER_OPT_M", "")
    gender_opt_f = env("GENDER_OPT_F", "")
    gender_map = dict(DEFAULT_GENDER_OPT_TO_MF)
    if gender_opt_m:
        gender_map[gender_opt_m] = "m"
    if gender_opt_f:
        gender_map[gender_opt_f] = "f"
    cfg["gender_opt_to_mf"] = gender_map

    cfg["time_opt_to_code"] = dict(DEFAULT_TIME_OPT_TO_CODE)
    return cfg


def ensure_output_dir(output_dir: str) -> None:
    """Ensure output directory exists."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)


def get_today_date_str() -> str:
    """Get today's date in YYYY-MM-DD format (KST)."""
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    return now.strftime("%Y-%m-%d")


def get_today_ganji() -> str:
    """
    Get today's heavenly stem and earthly branch (간지).
    Returns format like "갑자" based on calculation.
    """
    from saju import calculate_today_pillar
    today = get_today_date_str()
    pillar = calculate_today_pillar(today)
    stem, branch = pillar['day']
    return f"{stem}{branch}"


def build_improved_prompt(
    name: str,
    birthday: str,
    gender: str,
    time_code: str,
    today: str,
    saju_data: Dict[str, Any]
) -> str:
    """
    Build an improved prompt that includes pre-calculated saju data.

    Args:
        name: Person's name
        birthday: Birth date (YYYY-MM-DD)
        gender: Gender ('m' or 'f')
        time_code: Birth time code ('0'-'12')
        today: Today's date in Korean format (from today_kst())
        saju_data: Pre-calculated saju data from calculate_fortune_data

    Returns:
        Korean prompt string for Claude
    """
    gender_ko = "남성" if gender == "m" else "여성"
    time_ko = TIME_CODE_TO_LABEL.get(time_code, "모름")

    # Extract key saju data for prompt injection
    four_pillars = saju_data.get("four_pillars", {})
    day_pillar = four_pillars.get("day", {})
    day_stem = day_pillar.get("stem", "")
    day_branch = day_pillar.get("branch", "")
    day_ganzi = f"{day_stem}{day_branch}" if day_stem and day_branch else ""

    # Extract ten gods
    ten_gods = saju_data.get("ten_gods", {})
    day_ten_gods_str = "정보 없음"
    if ten_gods and "day" in ten_gods:
        day_god = ten_gods["day"]
        god_info = day_god.get("ten_god", "")
        if god_info:
            day_ten_gods_str = god_info

    # Extract harmonies and clashes
    harmonies_clashes = saju_data.get("harmonies_and_clashes", {})
    harmony_clash_str = json.dumps(harmonies_clashes, ensure_ascii=False) if harmonies_clashes else "정보 없음"

    # Get today's pillar info
    today_pillar = saju_data.get("today_pillar", {})
    today_stem = today_pillar.get("stem", "")
    today_branch = today_pillar.get("branch", "")
    today_ganzi = f"{today_stem}{today_branch}" if today_stem and today_branch else ""

    # Randomly pick a focus theme for variation
    import random
    focus_theme = random.choice(FOCUS_THEMES)

    prompt = f"""너는 한국어로 작성되는 고급 일일 운세 칼럼의 전문 작가다.
아래 출력은 엔터테인먼트와 자기 성찰을 위한 창작물이며,
과학적 사실이나 실제 예언을 주장하지 않는다.

⚠️ 중요 지시사항
아래 사주 데이터는 만세력 기반으로 정확히 계산된 값입니다. 이 값을 그대로 사용하세요. 절대 임의로 변경하지 마세요.

[사주팔자 데이터]
- 나이(생년월일): {birthday} ({day_ganzi})
- 성별: {gender_ko}
- 출생시간: {time_ko}
- 현재의 십성: {day_ten_gods_str}
- 합충 관계: {harmony_clash_str}
- 오늘의 간지: {today_ganzi}

[변동 요소 — 콘텐츠의 다양성을 위해 오늘마다 초점을 변경]
- 오늘의 주요 해석 각도: {focus_theme}
- 오늘 간지({today_ganzi})의 특성을 고려하여 해석하세요.
- 위의 합충 데이터와 오늘의 관계를 구체적으로 언급하세요.

⚠️ 작성 규칙
- 문단당 3~4문장, 말하듯 자연스럽게 작성한다.
- 과장·현학 표현을 피하고, 읽자마자 이해되게 쓴다.
- 섹션당 비유는 1개 이하로 사용하고, 의미를 바로 설명한다.
- Slack 메시지에 맞게 문단 사이에 여백을 둔다.

⚠️ 해석 규칙
- 사주 용어는 최대 3~4개, 즉시 일상 언어로 풀어 쓴다.
- 오늘 해석의 중심은 하나만 선택해 글 전체에 일관되게 사용한다.
  (십성 변화 / 오행 흐름 / 합·충 중 하나)
- 항상 긍정 일변도가 되지 않도록 균형 톤을 유지한다.

⚠️ 구조 규칙
- 개별 소제목은 쓰지 않는다.
- 아래에 지정된 고정 섹션 제목만 사용한다.
- 모든 제목은 Slack 굵은 글씨(*)로 표기한다.
- 각 고정 섹션 제목 앞에 의미에 맞는 이모지 1개를 사용한다.
- 공포·질병·재난·죽음·폭력·투자 종목은 언급하지 않는다.

[입력 정보]
- 이름: {name}
- 생년월일(양력): {birthday}
- 성별: {gender_ko}
- 출생시간: {time_ko}
- 오늘 날짜: {today}

────────────────────
[출력 형식 — 자리만 고정, 내용·제목은 전부 자유]
────────────────────

① 오늘의 운세 전체를 대표하는 메인 제목
- 첫 줄: 오늘 날짜를 그대로 사용한다 ({today})
- 날짜는 절대 새로 만들거나 수정하지 않는다.
- 둘째 줄: 오늘의 흐름을 상징하는 짧은 문구 또는 비유 1개
- 이 제목의 이모지는, 둘째 줄의 양쪽에만 생성한다.

② 오늘의 전체 운세 해설은 반드시 균형을 가진다.
- 1문단: 오늘의 분위기, 흐름, 기회와 평가
- 2문단: 오늘 관리가 필요한 지점(실수/오해/지연/집중력/체력 중 1~2개)
- 주의점은 공포를 만들지 않고, '관리하면 좋아지는 요소'로 설명한다.
- 결론은 희망적으로 마무리하되, 과장된 낙관은 피한다.

③ 오늘의 운을 이해하기 위한 심층 해석
- 제목은 자유롭게 생성한다.
- 타고난 성향({day_ganzi})과 오늘의 작용 요소({today_ganzi})를 대비해 설명한다.
- 위의 십성과 합충 데이터를 적절히 참고하여 구체적으로 설명한다.
- 사주 용어는 설명을 돕는 이름표로만 사용한다.
- 비유는 1개까지만 사용하고, 바로 의미를 풀어 설명한다.

④ 오늘의 핵심 포인트 (2개)
- 이 섹션의 제목은 반드시 "오늘 눈에 띄는 두 가지 흐름"로 사용한다.
- 오늘 특히 기억하면 좋은 요소 2가지를 다룬다.
- 각 포인트는 문단으로만 구분하며,
  별도의 소제목이나 강조 표시를 사용하지 않는다.

⑤ 오늘을 위한 행동 조언 (2줄)
- 이 섹션의 제목은 반드시 "하루를 위한 작은 기준"으로 사용한다.
- 각 줄은 하나의 문장
- 태도 / 관계 관점에서 하나씩 제시한다.
- 각 문장의 앞에 글머리 기호 목록(•) 을 붙일 것.

[분량 가이드]
- 전체 650~850자 내외
- 읽는 사람이 "오늘 나를 위해 정리된 글"이라고 느끼게 할 것
- 끝까지 읽어도 부담이 없을 것
"""
    return prompt.strip()


def claude_generate_fortune(api_key: str, model: str, prompt: str) -> str:
    """
    Call Claude API to generate fortune text.

    Args:
        api_key: Anthropic API key
        model: Model name (e.g., "claude-sonnet-4-6")
        prompt: The prompt to send

    Returns:
        Generated fortune text
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=model,
        max_tokens=1500,
        temperature=1.0,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    # Extract text from response
    text_parts = []
    for block in message.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)

    result = "\n".join(text_parts).strip()
    if not result:
        raise RuntimeError("Claude returned empty response")

    return result


def generate_fortune_for_item(
    cfg: Dict[str, Any],
    item: Dict[str, Any],
    today_date: str,
    today_kst_str: str,
) -> Dict[str, Any]:
    """
    Generate a fortune for a single item.

    Args:
        cfg: Configuration dictionary
        item: Item from Slack Lists
        today_date: Today's date in YYYY-MM-DD format
        today_kst_str: Today's date in Korean format

    Returns:
        Dictionary with fortune generation result
    """
    item_id = item.get("id", "")
    name = extract_name(item)

    result = {
        "item_id": item_id,
        "name": name,
        "is_private": False,
        "dm_targets": [],
        "saju_data": {},
        "fortune_text": "",
        "status": "error",
        "error": None,
    }

    try:
        # Build record from item
        rec = build_rec_from_item(cfg, item)

        result["is_private"] = rec.get("is_private", False)
        result["dm_targets"] = rec.get("dm_targets", [])

        # Calculate saju data
        saju_data = calculate_fortune_data(
            birthday=rec["birthday"],
            gender="남" if rec["gender"] == "m" else "여",
            time_code=rec["time_code"],
            today_date=today_date,
        )

        if "error" in saju_data:
            raise RuntimeError(f"Saju calculation error: {saju_data['error']}")

        result["saju_data"] = saju_data

        # Build improved prompt with saju data
        prompt = build_improved_prompt(
            name=rec["name"],
            birthday=rec["birthday"],
            gender=rec["gender"],
            time_code=rec["time_code"],
            today=today_kst_str,
            saju_data=saju_data,
        )

        # Call Claude API
        fortune_text = claude_generate_fortune(
            api_key=cfg["anthropic_key"],
            model=cfg["anthropic_model"],
            prompt=prompt,
        )

        result["fortune_text"] = fortune_text
        result["status"] = "ok"

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def run() -> None:
    """Main execution function."""
    cfg = load_config()

    # Ensure output directory exists
    ensure_output_dir(cfg["output_dir"])

    # Get target date (from env or today)
    target_date_str = env("TARGET_DATE", "").strip()
    if target_date_str:
        # Validate format
        try:
            td = datetime.strptime(target_date_str, "%Y-%m-%d")
            today_date = target_date_str
            weekday_ko = WEEKDAY_KO[td.weekday()]
            today_kst_full = f"{td.year}년 {td.month}월 {td.day}일 {weekday_ko}요일"
            print(f"Using target date: {today_date}")
        except ValueError:
            raise RuntimeError(f"Invalid TARGET_DATE format: {target_date_str} (expected YYYY-MM-DD)")
    else:
        today_date, today_pretty = today_kst_dates()
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        weekday_ko = WEEKDAY_KO[now.weekday()]
        today_kst_full = f"{now.year}년 {now.month}월 {now.day}일 {weekday_ko}요일"

    # Check audit mode
    audit_only = env_bool("AUDIT_ONLY", False)
    test_mode = env("TEST_MODE", "off").strip().lower()  # off / single / all

    # Fetch items
    print("Fetching items from Slack Lists...")
    items = fetch_all_list_items(cfg["slack_token"], cfg["list_id"])

    if not items:
        print("No items in list. Done.")
        return

    # Run audit if requested
    if audit_only:
        print("\n=== AUDIT MODE ===")
        audit_list(cfg, items)
        return

    # Test mode handling
    if test_mode == "single":
        print(f"TEST_MODE=single: Generating for admin user only")
        if not cfg["admin_user_ids"]:
            raise RuntimeError("TEST_MODE=single requires ADMIN_USER_IDS")
        items = [
            item for item in items
            if set(extract_user_ids(item, cfg["cols"]["assignee_col"])) & set(cfg["admin_user_ids"])
        ]
        print(f"Filtered to {len(items)} admin-associated items")
    elif test_mode == "all":
        print(f"TEST_MODE=all: Generating for all users (send will go to admin only)")

    # Generate fortunes
    fortunes = []
    print(f"\nGenerating fortunes for {len(items)} items...")

    for i, item in enumerate(items, 1):
        name = extract_name(item)
        print(f"[{i}/{len(items)}] Processing {name}...", end=" ")

        result = generate_fortune_for_item(cfg, item, today_date, today_kst_full)
        fortunes.append(result)

        if result["status"] == "ok":
            print("OK")
        else:
            print(f"ERROR: {result['error']}")

    # Prepare output
    output = {
        "date": today_date,
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "fortunes": fortunes,
    }

    # Save to JSON
    filename = f"fortunes_{today_date}.json"
    filepath = os.path.join(cfg["output_dir"], filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to {filepath}")

    # Summary
    ok_count = sum(1 for f in fortunes if f["status"] == "ok")
    error_count = len(fortunes) - ok_count

    print(f"\n=== SUMMARY ===")
    print(f"Total: {len(fortunes)}")
    print(f"Success: {ok_count}")
    print(f"Errors: {error_count}")

    if error_count > 0:
        print("\nErrors:")
        for f in fortunes:
            if f["status"] == "error":
                print(f"  - {f['name']} ({f['item_id']}): {f['error']}")


if __name__ == "__main__":
    run()
