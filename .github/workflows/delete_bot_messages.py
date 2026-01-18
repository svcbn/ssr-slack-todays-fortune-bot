import os
import time
import json
import requests
from typing import Any, Dict, List, Optional, Tuple

SLACK_API = "https://slack.com/api"

def env(name: str, default: str = "", required: bool = False) -> str:
    v = os.getenv(name, default)
    v = (v or "").strip()
    if required and not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

def env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return default

def slack_api(method: str, token: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{SLACK_API}/{method}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }

    while True:
        resp = requests.post(url, headers=headers, data=params, timeout=30)

        # Rate limit handling
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "2"))
            time.sleep(retry_after + 1)
            continue

        data = resp.json()

        # Slack sometimes rate-limits with ok=false too
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

def list_channel_messages(token: str, channel_id: str, cursor: str = "", limit: int = 200) -> Tuple[List[Dict[str, Any]], str]:
    params: Dict[str, Any] = {"channel": channel_id, "limit": str(limit)}
    if cursor:
        params["cursor"] = cursor
    data = slack_api("conversations.history", token, params)
    if not data.get("ok"):
        raise RuntimeError(f"conversations.history failed: {data}")
    messages = data.get("messages") or []
    next_cursor = (data.get("response_metadata") or {}).get("next_cursor") or ""
    return messages, next_cursor

def list_thread_replies(token: str, channel_id: str, thread_ts: str, cursor: str = "", limit: int = 200) -> Tuple[List[Dict[str, Any]], str]:
    params: Dict[str, Any] = {"channel": channel_id, "ts": thread_ts, "limit": str(limit)}
    if cursor:
        params["cursor"] = cursor
    data = slack_api("conversations.replies", token, params)
    if not data.get("ok"):
        raise RuntimeError(f"conversations.replies failed: {data}")
    messages = data.get("messages") or []
    next_cursor = (data.get("response_metadata") or {}).get("next_cursor") or ""
    return messages, next_cursor

def delete_message(token: str, channel_id: str, ts: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"[DRY_RUN] chat.delete channel={channel_id} ts={ts}")
        return True

    data = slack_api("chat.delete", token, {"channel": channel_id, "ts": ts})
    if not data.get("ok"):
        # Common cases: cant_delete_message, message_not_found, not_in_channel, missing_scope
        print(f"[WARN] chat.delete failed ts={ts}: {data}")
        return False
    return True

def is_bot_authored(msg: Dict[str, Any], bot_user_id: str, bot_id: Optional[str]) -> bool:
    # Slack message fields can vary:
    # - "user": author user id (bot user id for bot messages)
    # - "bot_id": bot id for bot messages
    # - "subtype": "bot_message" sometimes
    user = msg.get("user")
    msg_bot_id = msg.get("bot_id")
    subtype = msg.get("subtype")

    if user == bot_user_id:
        return True
    if bot_id and msg_bot_id == bot_id:
        return True
    if subtype == "bot_message" and user == bot_user_id:
        return True
    return False

def main():
    token = env("SLACK_BOT_TOKEN", required=True)
    channel_id = env("SLACK_CHANNEL_ID", required=True)

    # Safety toggles
    dry_run = env_bool("DRY_RUN", True)   # default TRUE for safety
    max_delete = int(env("MAX_DELETE", "100000"))  # large default; adjust if desired

    auth = auth_test(token)
    bot_user_id = auth.get("user_id")
    bot_id = auth.get("bot_id")

    print("=== auth.test ===")
    print(json.dumps(auth, ensure_ascii=False, indent=2))
    print(f"Target channel: {channel_id}")
    print(f"DRY_RUN={dry_run} MAX_DELETE={max_delete}")
    print("Starting scan...")

    deleted = 0
    scanned = 0

    cursor = ""
    while True:
        msgs, cursor = list_channel_messages(token, channel_id, cursor=cursor, limit=200)
        if not msgs:
            if not cursor:
                break

        for m in msgs:
            scanned += 1

            # Only consider messages authored by this bot
            if not is_bot_authored(m, bot_user_id, bot_id):
                continue

            parent_ts = str(m.get("ts"))
            reply_count = int(m.get("reply_count") or 0)

            # 1) Delete thread replies first (if any)
            if reply_count > 0:
                rep_cursor = ""
                while True:
                    replies, rep_cursor = list_thread_replies(token, channel_id, parent_ts, cursor=rep_cursor, limit=200)

                    # conversations.replies includes the parent message as the first element.
                    # We should delete ONLY bot-authored replies with ts != parent_ts.
                    for r in replies:
                        r_ts = str(r.get("ts"))
                        if r_ts == parent_ts:
                            continue
                        if not is_bot_authored(r, bot_user_id, bot_id):
                            continue

                        if deleted >= max_delete:
                            print(f"Reached MAX_DELETE={max_delete}. Stopping.")
                            return

                        ok = delete_message(token, channel_id, r_ts, dry_run=dry_run)
                        if ok:
                            deleted += 1
                            time.sleep(0.35)

                    if not rep_cursor:
                        break

            # 2) Delete parent message
            if deleted >= max_delete:
                print(f"Reached MAX_DELETE={max_delete}. Stopping.")
                return

            ok = delete_message(token, channel_id, parent_ts, dry_run=dry_run)
            if ok:
                deleted += 1
                time.sleep(0.35)

        if not cursor:
            break

    print("=== DONE ===")
    print(f"scanned_messages={scanned}")
    print(f"deleted_messages={deleted}")
    print("Tip: set DRY_RUN=false to actually delete.")

if __name__ == "__main__":
    main()
