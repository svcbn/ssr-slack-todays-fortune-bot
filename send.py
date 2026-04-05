"""
send.py - Slack 전송 모듈
generate.py가 생성한 JSON 파일을 읽어서 Slack 채널/DM으로 전송합니다.
"""

import os
import sys
import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from main import (
    env,
    env_bool,
    slack_api,
    slack_open_dm,
    slack_post,
    parse_admin_ids,
    today_kst_dates,
    notify_admins_of_error,
    WEEKDAY_KO,
)


# ============================================================================
# Config
# ============================================================================

def load_config() -> Dict[str, Any]:
    """Load configuration for sending."""
    return {
        "slack_token": env("SLACK_BOT_TOKEN", required=True),
        "channel_id": env("SLACK_CHANNEL_ID", required=True),
        "admin_user_ids": parse_admin_ids(env("ADMIN_USER_IDS", "")),
        "output_dir": env("OUTPUT_DIR", "output"),
    }


# ============================================================================
# Send logic
# ============================================================================

def send_fortune_to_channel(
    token: str,
    channel_id: str,
    fortune: Dict[str, Any],
    today_pretty: str,
) -> None:
    """
    채널에 운세를 스레드로 전송합니다.
    부모 메시지: 날짜 + 멘션
    스레드: 운세 본문
    """
    name = fortune["name"]
    dm_targets = fortune.get("dm_targets", [])
    fortune_text = fortune["fortune_text"]

    mention_uid = dm_targets[0] if dm_targets else None
    mention = f"<@{mention_uid}>" if mention_uid else ""

    parent_text = f"{today_pretty} 오늘의 운세 도착! {mention}".strip()
    parent_ts = slack_post(token, channel_id, parent_text)
    slack_post(token, channel_id, fortune_text, thread_ts=parent_ts)

    print(f"  → 채널 전송 완료: {name}")


def send_fortune_as_dm(
    token: str,
    fortune: Dict[str, Any],
) -> None:
    """
    DM으로 운세를 전송합니다 (private 모드).
    """
    name = fortune["name"]
    dm_targets = fortune.get("dm_targets", [])
    fortune_text = fortune["fortune_text"]

    for uid in dm_targets:
        dm_channel = slack_open_dm(token, uid)
        slack_post(token, dm_channel, fortune_text)
        time.sleep(0.4)

    print(f"  → DM 전송 완료: {name} ({len(dm_targets)}명)")


def send_fortune_admin_only(
    token: str,
    admin_uid: str,
    fortune: Dict[str, Any],
) -> None:
    """
    관리자에게만 DM으로 전송합니다 (테스트 모드).
    """
    name = fortune["name"]
    fortune_text = fortune["fortune_text"]

    dm_channel = slack_open_dm(token, admin_uid)
    # 테스트 모드에서는 누구의 운세인지 헤더를 붙여서 전송
    header = f"──── [{name}] ────\n"
    slack_post(token, dm_channel, header + fortune_text)

    print(f"  → 관리자 DM 전송: {name} → {admin_uid}")


# ============================================================================
# Main
# ============================================================================

def run() -> None:
    cfg = load_config()
    test_mode = env("TEST_MODE", "off").strip().lower()  # off / single / all
    force_send = env_bool("FORCE_SEND", False)

    # Get target date (from env or today)
    target_date_str = env("TARGET_DATE", "").strip()
    if target_date_str:
        today_date = target_date_str
        today_pretty = target_date_str  # simplified for test mode
        print(f"Using target date: {today_date}")
    else:
        today_date, today_pretty = today_kst_dates()

    # JSON 파일 경로 결정
    json_path = env("FORTUNE_JSON", "")
    if not json_path:
        json_path = os.path.join(cfg["output_dir"], f"fortunes_{today_date}.json")

    if not os.path.exists(json_path):
        print(f"ERROR: Fortune JSON not found: {json_path}")
        print("generate.py를 먼저 실행하세요.")
        sys.exit(1)

    # JSON 로드
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    fortunes = data.get("fortunes", [])
    if not fortunes:
        print("No fortunes to send.")
        return

    # 성공한 항목만 필터
    ok_fortunes = [f for f in fortunes if f["status"] == "ok"]
    if not ok_fortunes:
        print("No successful fortunes to send. Check generate.py output.")
        return

    print(f"Sending {len(ok_fortunes)} fortunes (from {json_path})")

    # Quick auth check
    auth = slack_api("auth.test", cfg["slack_token"], {})
    if not auth.get("ok"):
        raise RuntimeError(f"Slack auth failed: {auth}")
    print(f"Authenticated as: {auth.get('user', 'unknown')}")

    sent_count = 0

    for i, fortune in enumerate(ok_fortunes, 1):
        name = fortune["name"]
        item_id = fortune["item_id"]
        is_private = fortune.get("is_private", False)

        print(f"[{i}/{len(ok_fortunes)}] {name}...", end="")

        try:
            if test_mode in ("single", "all"):
                # 테스트 모드: admin에게만 DM 전송
                if not cfg["admin_user_ids"]:
                    raise RuntimeError("TEST_MODE requires ADMIN_USER_IDS")
                send_fortune_admin_only(
                    cfg["slack_token"],
                    cfg["admin_user_ids"][0],
                    fortune,
                )
                sent_count += 1

            elif is_private:
                # DM 전송
                send_fortune_as_dm(cfg["slack_token"], fortune)
                sent_count += 1

            else:
                # 채널 스레드 전송
                send_fortune_to_channel(
                    cfg["slack_token"],
                    cfg["channel_id"],
                    fortune,
                    today_pretty,
                )
                sent_count += 1

            # Rate limiting
            time.sleep(0.5)

        except Exception as e:
            print(f" ERROR: {e}")
            notify_admins_of_error(
                cfg["slack_token"],
                cfg["admin_user_ids"],
                item_id,
                name,
                e,
            )
            continue

    print(f"\n=== SEND COMPLETE ===")
    print(f"Sent: {sent_count}/{len(ok_fortunes)}")


if __name__ == "__main__":
    run()
