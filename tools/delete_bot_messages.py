import os
import time
import json
import requests
from typing import Any, Dict, List, Optional, Tuple

SLACK_API = "https://slack.com/api"

def env(name: str, required: bool = False) -> str:
    v = (os.getenv(name) or "").strip()
    if required and not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

def slack_api(method: str, token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{SLACK_API}/{method}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }

    while True:
        resp = requests.post(url, headers=headers, data=params, timeout=30)

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "2"))
            time.sleep(retry_after + 1)
            continue

        data = resp.json()
        if data.get("error") == "ratelimited":
            retry_after = int(resp.headers.get("Retry-After", "2"))
            time.sleep(retry_after + 1)
            continue

        return data

def auth_test(token: str) -> Dict[str, Any]:
    data = slack_api("auth.test", token, {})
    if not data.get("ok"):
        raise RuntimeError(f"auth.test failed: {data}")
    return data

def list_channel_messages(token: str, channel_id: str, cursor: str = "", limit: int = 200):
    params = {"channel": channel_id, "limit": str(limit)}
    if cursor:
        params["cursor"] = cursor
    data = slack_api("conversations.history", token, params)
    if not data.get("ok"):
        raise RuntimeError(f"conversations.history failed: {data}")
    return data.get("messages") or [], (data.get("response_metadata") or {}).get("next_cursor") or ""

def list_thread_replies(token: str, channel_id: str, thread_ts: str, cursor: str = "", limit: int = 200):
    params = {"channel": channel_id, "ts": thread_ts, "limit": str(limit)}
    if cursor:
        params["cursor"] = cursor
    data = slack_api("conversations.replies", token, params)
    if not data.get("ok"):
        raise RuntimeError(f"conversations.replies failed: {data}")
    return data.get("messages") or [], (data.get("response_metadata") or {}).get("next_cursor") or ""

def delete_message(token: str, channel_id: str, ts: str) -> None:
    data = slack_api("chat.delete", token, {"channel": channel_id, "ts": ts})
    if not data.get("ok"):
        print(f"[WARN] chat.delete failed ts={ts}: {data}")

def is_bot_authored(msg: Dict[str, Any], bot_user_id: str, bot_id: Optional[str]) -> bool:
    if msg.get("user") == bot_user_id:
        return True
    if bot_id and msg.get("bot_id") == bot_id:
        return True
    if msg.get("subtype") == "bot_message" and msg.get("user") == bot_user_id:
        return True
    return False

def main():
    token = env("SLACK_BOT_TOKEN", required=True)
    channel_id = env("SLACK_TEST_CHANNEL_ID", required=True)

    auth = auth_test(token)
    bot_user_id = auth.get("user_id")
    bot_id = auth.get("bot_id")

    print("=== auth.test ===")
    print(json.dumps(auth, ensure_ascii=False, indent=2))
    print(f"Purging bot messages in channel: {channel_id}")

    deleted = 0
    scanned = 0
    cursor = ""

    while True:
        msgs, cursor = list_channel_messages(token, channel_id, cursor=cursor)

        for m in msgs:
            scanned += 1
            if not is_bot_authored(m, bot_user_id, bot_id):
                continue

            parent_ts = str(m.get("ts"))
            reply_count = int(m.get("reply_count") or 0)

            # 스레드 답글부터 삭제
            if reply_count > 0:
                rep_cursor = ""
                while True:
                    replies, rep_cursor = list_thread_replies(token, channel_id, parent_ts, cursor=rep_cursor)
                    for r in replies:
                        r_ts = str(r.get("ts"))
                        if r_ts == parent_ts:
                            continue
                        if not is_bot_authored(r, bot_user_id, bot_id):
                            continue
                        delete_message(token, channel_id, r_ts)
                        deleted += 1
                        time.sleep(0.35)
                    if not rep_cursor:
                        break

            # 부모 메시지 삭제
            delete_message(token, channel_id, parent_ts)
            deleted += 1
            time.sleep(0.35)

        if not cursor:
            break

    print("=== DONE ===")
    print(f"scanned_messages={scanned}")
    print(f"deleted_messages={deleted}")

if __name__ == "__main__":
    main()
