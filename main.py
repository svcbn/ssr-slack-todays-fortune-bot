import os
import json
import time
import requests
from typing import Any, Dict, List, Optional, Tuple
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo

# -----------------------------
# Slack Lists/Fields defaults (your known IDs)
# -----------------------------
DEFAULT_COLS = {
    "gender_col": "Col0A8FH3BN7L",
    "time_col": "Col0A8K6V4HDJ",
    "birthday_col": "Col0A8JMV8N5A",
    "private_col": "Col0A8BMFER7F",
    "assignee_col": "Col0A8G4DUAMQ",
}

# Gender option ids (your known mapping)
DEFAULT_GENDER_OPT_TO_MF = {
    "OptQIPU5CQN": "m",
    "Opt0UQXFE0P": "f",
}

# Time option ids -> code: 0=자 ... 11=해, 12=모름
DEFAULT_TIME_OPT_TO_CODE = {
    "OptTK8JIX80": "0",
    "OptA92NTRBY": "1",
    "OptLKAW5WA1": "2",
    "OptV3N31RHW": "3",
    "Opt76B43XGY": "4",
    "Opt1Z92W5ML": "5",
    "Opt605DLXQ7": "6",
    "OptCZI2JJS4": "7",
    "OptTMERF71G": "8",
    "Opt8862IDXI": "9",
    "OptCP7RGTD8": "10",
    "OptFOHK1YTJ": "11",
    "OptUZH3DWEL": "12",
}

TIME_CODE_TO_LABEL = {
    "0": "子(자) 23:30 ~ 01:29",
    "1": "丑(축) 01:30 ~ 03:29",
    "2": "寅(인) 03:30 ~ 05:29",
    "3": "卯(묘) 05:30 ~ 07:29",
    "4": "辰(진) 07:30 ~ 09:29",
    "5": "巳(사) 09:30 ~ 11:29",
    "6": "午(오) 11:30 ~ 13:29",
    "7": "未(미) 13:30 ~ 15:29",
    "8": "申(신) 15:30 ~ 17:29",
    "9": "酉(유) 17:30 ~ 19:29",
    "10": "戌(술) 19:30 ~ 21:29",
    "11": "亥(해) 21:30 ~ 23:29",
    "12": "모름",
}


# -----------------------------
# Utilities
# -----------------------------
def env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    v = os.getenv(name)
    if v is None:
        v = default

    # 핵심: 빈 문자열/공백이면 default로 대체
    if isinstance(v, str) and v.strip() == "":
        v = default

    if required and (v is None or str(v).strip() == ""):
        raise RuntimeError(f"Missing required env var: {name}")

    return str(v).strip() if v is not None else ""


def slack_api(method: str, token: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    # Slack Web API is form-encoded for most methods; JSON works for some, but form is safest.
    url = f"https://slack.com/api/{method}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
    }
    resp = requests.post(url, headers=headers, data=payload, timeout=30)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"{method} failed: {data}")
    return data


def slack_lists_items_list(token: str, list_id: str, cursor: str = "", limit: int = 200) -> Dict[str, Any]:
    # This is a Slack Web API method family for Lists; your workspace already validated it works.
    payload: Dict[str, Any] = {"list_id": list_id, "limit": str(limit)}
    if cursor:
        payload["cursor"] = cursor
    return slack_api("slackLists.items.list", token, payload)


def parse_admin_ids(raw: str) -> List[str]:
    raw = (raw or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def field_by_column(fields: List[Dict[str, Any]], col_id: str) -> Optional[Dict[str, Any]]:
    for f in fields:
        if f.get("column_id") == col_id:
            return f
    return None


def extract_name(item: Dict[str, Any]) -> str:
    # Prefer "name" key field if present, else fallback to any text field.
    for f in item.get("fields", []):
        if f.get("key") == "name" and (f.get("text") or "").strip():
            return (f.get("text") or "").strip()
    # fallback: find first field with "text"
    for f in item.get("fields", []):
        if (f.get("text") or "").strip():
            return (f.get("text") or "").strip()
    return "(이름없음)"


def extract_birthday(item: Dict[str, Any], birthday_col: str) -> Optional[str]:
    f = field_by_column(item.get("fields", []), birthday_col)
    if not f:
        return None
    # Slack lists date field seen as: value="YYYY-MM-DD", date=["YYYY-MM-DD"]
    v = f.get("value")
    if isinstance(v, str) and v.strip():
        return v.strip()
    d = f.get("date")
    if isinstance(d, list) and d and isinstance(d[0], str):
        return d[0].strip()
    return None


def extract_select_option(item: Dict[str, Any], col_id: str) -> Optional[str]:
    f = field_by_column(item.get("fields", []), col_id)
    if not f:
        return None
    sel = f.get("select")
    if isinstance(sel, list) and len(sel) > 0:
        return str(sel[0])
    v = f.get("value")
    if isinstance(v, str) and v.strip().startswith("Opt"):
        return v.strip()
    return None


def extract_checkbox(item: Dict[str, Any], col_id: str) -> Optional[bool]:
    f = field_by_column(item.get("fields", []), col_id)
    if not f:
        return None
    v = f.get("value")
    if isinstance(v, bool):
        return v
    cb = f.get("checkbox")
    if isinstance(cb, bool):
        return cb
    return None


def extract_user_ids(item: Dict[str, Any], col_id: str) -> List[str]:
    f = field_by_column(item.get("fields", []), col_id)
    if not f:
        return []
    u = f.get("user")
    if isinstance(u, list):
        return [str(x) for x in u if str(x).strip()]
    v = f.get("value")
    if isinstance(v, str) and v.startswith("U"):
        return [v]
    return []

import re

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def validate_item(cfg: Dict[str, Any], item: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Returns: (ok, errors[])
    """
    cols = cfg["cols"]
    errs: List[str] = []
    item_id = item.get("id", "")

    # name
    name = extract_name(item)
    if not name or name == "(이름없음)":
        errs.append("name: missing or empty")

    # birthday: strict, only from configured column (NO auto-detect)
    b = extract_birthday(item, cols["birthday_col"])
    if not b or not DATE_RE.match(b):
        errs.append(f"birthday: missing/invalid in col={cols['birthday_col']} (value={b})")

    # gender
    gopt = extract_select_option(item, cols["gender_col"])
    if not gopt:
        errs.append(f"gender: missing select in col={cols['gender_col']}")
    else:
        g = cfg["gender_opt_to_mf"].get(gopt)
        if g not in ("m", "f"):
            errs.append(f"gender: unknown option_id={gopt} (col={cols['gender_col']})")

    # time
    topt = extract_select_option(item, cols["time_col"])
    if not topt:
        errs.append(f"time: missing select in col={cols['time_col']}")
    else:
        tcode = cfg["time_opt_to_code"].get(topt)
        if tcode is None:
            errs.append(f"time: unknown option_id={topt} (col={cols['time_col']})")

    # private checkbox
    priv = extract_checkbox(item, cols["private_col"])
    if priv is None:
        # not fatal, but report
        errs.append(f"private: missing checkbox field in col={cols['private_col']} (treated as False)")

    # assignee users
    assignees = extract_user_ids(item, cols["assignee_col"])
    # if private is true, require dm targets (assignee or admin)
    is_private = bool(priv) if priv is not None else False
    if is_private:
        dm_targets = list(dict.fromkeys([*assignees, *cfg["admin_user_ids"]]))
        if not dm_targets:
            errs.append(f"dm_targets: private=true but no assignee in col={cols['assignee_col']} and ADMIN_USER_IDS empty")

    ok = (len([e for e in errs if not e.startswith("private:")]) == 0)  # private missing is warning only
    return ok, errs


def audit_list(cfg: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
    """
    Prints a strict audit report of all items against known column ids and option ids.
    """
    total = len(items)
    ok_count = 0
    bad: List[Dict[str, Any]] = []

    for it in items:
        ok, errs = validate_item(cfg, it)
        if ok:
            ok_count += 1
        else:
            bad.append({
                "id": it.get("id"),
                "name": extract_name(it),
                "errors": errs,
            })

    print("=== LIST AUDIT REPORT ===")
    print(f"total_items={total} ok_items={ok_count} bad_items={len(bad)}")
    if bad:
        print("=== BAD ITEMS (need fixing in Slack List) ===")
        print(json.dumps(bad, ensure_ascii=False, indent=2))
    else:
        print("All items passed strict validation.")

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

def today_kst() -> str:
    return datetime.now(KST).strftime("%Y년 %-m월 %-d일 %A")



def make_daily_signature(item_id: str, date_str: str) -> str:
    raw = f"{item_id}:{date_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def notify_admins_of_error(token: str, admin_ids: List[str], item_id: str, name: str, error: Exception) -> None:
    if not admin_ids:
        return

    msg = (
        f"⚠️ 운세봇 처리 오류\n\n"
        f"- 이름: {name}\n"
        f"- item_id: {item_id}\n"
        f"- 오류: {str(error)}\n\n"
        f"해당 항목만 스킵하고 나머지는 정상 처리되었습니다."
    )

    for uid in admin_ids:
        try:
            ch = slack_open_dm(token, uid)
            slack_post(token, ch, msg)
            time.sleep(0.3)
        except Exception:
            pass  # 관리자 알림 실패는 무시



# -----------------------------
# Prompt builder (your "자리 고정 / 제목 유동" 설계)
# -----------------------------
def build_prompt(r: Dict[str, Any]) -> str:
    gender_ko = "남성" if r["gender"] == "m" else "여성"
    time_ko = TIME_CODE_TO_LABEL.get(r["time_code"], "모름")
    today = r["today"]

    return f"""
너는 한국어로 작성되는 고급 일일 운세 칼럼의 전문 작가다.
아래 출력은 엔터테인먼트와 자기 성찰을 위한 창작물이며,
과학적 사실이나 실제 예언을 주장하지 않는다.

⚠️ 매우 중요 (톤 & 가독성 규칙)
- 문단당 최대 3~4문장으로 제한한다.
- 문장은 말하듯 자연스럽게 쓴다. 시처럼 끊어 나열하지 않는다.
- 문장 길이는 보통 25~35자 내외로 유지하되,
  의미 설명이 필요한 경우 자연스럽게 늘려도 된다.
- 비유와 은유는 섹션당 최대 1개만 사용하며,
  비유를 쓴 뒤에는 반드시 의미를 바로 풀어 설명한다.
- 현학적인 표현, 과도한 수식어, 추상명사 남용을 피한다.
- 독자가 읽자마자 이해할 수 있게 명확하게 쓴다.
- Slack 메시지에 적합하도록 문단 사이에 충분한 줄 간격을 둔다.

⚠️ 구조 규칙
- 아래는 ‘형식의 자리’만 고정이며,
  제목·소제목·표현은 매번 새롭게 만든다.
- 제목이나 항목명을 반복하거나 고정하지 않는다.
- 단정적 표현(반드시 / 확정 / 무조건)은 사용하지 않는다.
- 공포, 질병, 재난, 죽음, 폭력, 특정 투자 종목 언급 금지.
- 사주 용어는 최대 2개까지만 사용하며,
  반드시 일상적인 설명과 함께 쓴다.
- 사주 용어가 글의 주인공이 되지 않도록 한다.

[입력 정보]
- 이름: {r["name"]}
- 생년월일(양력): {r["birthday"]}
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

② 오늘의 전체 운세 해설 (2문단)
- 1문단: 오늘의 분위기, 흐름, 기회와 평가
- 2문단: 작은 장애물 → 전환 → 안정적인 결말의 흐름
- 오늘 하루를 어떻게 보내면 좋은지가 자연스럽게 드러나야 한다.

③ 오늘의 운을 이해하기 위한 심층 해석
- 제목은 자유롭게 생성한다.
- ‘타고난 나의 성향’과 ‘오늘의 환경’을 대비해 설명한다.
- 사주 용어는 설명을 돕는 이름표로만 사용한다.
- 비유는 1개까지만 사용하고, 바로 의미를 풀어 설명한다.

④ 오늘의 핵심 포인트 (2개)
- 각 포인트는:
  · 짧은 소제목 1줄
  · 설명 문장 1~2문장
- 오늘 특히 기억하면 좋은 태도나 선택을 제시한다.

⑤ 오늘을 위한 행동 조언 (3줄)
- 각 줄은 하나의 문장
- 태도 / 관계 / 자기 확신 관점에서 하나씩 제시한다.
- 읽고 바로 실천할 수 있는 내용이어야 한다.

[분량 가이드]
- 전체 650~850자 내외
- 읽는 사람이 “오늘 나를 위해 정리된 글”이라고 느끼게 할 것
- 끝까지 읽어도 부담이 없을 것

""".strip()


# -----------------------------
# Gemini call (REST generateContent)
# -----------------------------
def gemini_generate_text(api_key: str, model: str, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    def call(parts_text: str) -> Dict[str, Any]:
        payload = {
            "contents": [{"role": "user", "parts": [{"text": parts_text}]}],
            "generationConfig": {
                "temperature": 0.8,
                "topP": 0.95,
                "maxOutputTokens": 4096,  # 상향
            },
        }
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
        data = resp.json()
        if resp.status_code >= 400:
            raise RuntimeError(f"Gemini HTTP {resp.status_code}: {data}")
        return data

    def extract_text(data: Dict[str, Any]) -> Tuple[str, str]:
        cands = data.get("candidates") or []
        if not cands:
            raise RuntimeError(f"Gemini returned no candidates: {data}")
        cand0 = cands[0]
        finish = str(cand0.get("finishReason") or "")
        content = cand0.get("content") or {}
        parts = content.get("parts") or []
        texts = [p.get("text", "").strip() for p in parts if isinstance(p.get("text"), str) and p.get("text", "").strip()]
        return "\n".join(texts).strip(), finish

    # 1차
    data1 = call(prompt)
    text1, finish1 = extract_text(data1)

    if not text1:
        raise RuntimeError("Gemini returned empty text (first call)")

    # MAX_TOKENS이면 1회만 이어쓰기
    if finish1.upper() == "MAX_TOKENS":
        cont_prompt = (
            "아래 글은 길이 제한으로 중간에서 끊겼다.\n"
            "바로 이어서 남은 부분만 한국어로 작성하되, 중복 없이 자연스럽게 마무리해라.\n"
            "추가 설명이나 머리말 없이 '이어지는 본문'만 출력해라.\n\n"
            "=== 끊긴 글 ===\n"
            f"{text1}\n"
            "=== 여기서부터 이어쓰기 ==="
        )
        data2 = call(cont_prompt)
        text2, _ = extract_text(data2)
        if text2:
            return (text1.rstrip() + "\n" + text2.lstrip()).strip()

    return text1


# -----------------------------
# Slack messaging
# -----------------------------
def slack_open_dm(token: str, user_id: str) -> str:
    # conversations.open opens/resumes a DM :contentReference[oaicite:4]{index=4}
    data = slack_api("conversations.open", token, {"users": user_id})
    ch = data.get("channel", {})
    channel_id = ch.get("id")
    if not channel_id:
        raise RuntimeError(f"conversations.open missing channel id: {data}")
    return channel_id


def slack_post(token: str, channel: str, text: str) -> None:
    data = slack_api("chat.postMessage", token, {"channel": channel, "text": text})
    posted = ((data.get("message") or {}).get("text")) or ""
    print(f"DEBUG post len: local={len(text)} slack={len(posted)}")


# -----------------------------
# Main flow
# -----------------------------
def load_config() -> Dict[str, Any]:
    cfg = {
        "slack_token": env("SLACK_BOT_TOKEN", required=True),
        "list_id": env("SLACK_LIST_ID", required=True),
        "channel_id": env("SLACK_CHANNEL_ID", required=True),
        "admin_user_ids": parse_admin_ids(env("ADMIN_USER_IDS", "")),
        "gemini_key": env("GEMINI_API_KEY", required=True),
        "gemini_model": env("GEMINI_MODEL", "gemini-3-flash-preview"),
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


def fetch_all_list_items(token: str, list_id: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    cursor = ""
    while True:
        data = slack_lists_items_list(token, list_id, cursor=cursor, limit=200)
        items.extend(data.get("items") or [])
        cursor = (data.get("response_metadata") or {}).get("next_cursor") or ""
        if not cursor:
            break
    return items


def build_rec_from_item(cfg: Dict[str, Any], item: Dict[str, Any]) -> Dict[str, Any]:
    cols = cfg["cols"]

    name = extract_name(item)
    birthday = extract_birthday(item, cols["birthday_col"])
    if not birthday:
        raise RuntimeError("birthday missing")

    gender_opt = extract_select_option(item, cols["gender_col"])
    if not gender_opt:
        raise RuntimeError("gender select missing")
    gender = cfg["gender_opt_to_mf"].get(gender_opt)
    if gender not in ("m", "f"):
        raise RuntimeError(f"unknown gender option: {gender_opt}")

    time_opt = extract_select_option(item, cols["time_col"])
    if not time_opt:
        raise RuntimeError("time select missing")
    time_code = cfg["time_opt_to_code"].get(time_opt)
    if time_code is None:
        raise RuntimeError(f"unknown time option: {time_opt}")

    is_private = extract_checkbox(item, cols["private_col"])
    if is_private is None:
        # treat missing as False
        is_private = False

    assignees = extract_user_ids(item, cols["assignee_col"])
    # DM 대상: 담당자 + 관리자
    dm_targets = list(dict.fromkeys([*assignees, *cfg["admin_user_ids"]]))  # uniq preserve order

    return {
        "item_id": item.get("id"),
        "name": name,
        "birthday": birthday,
        "gender": gender,
        "time_code": time_code,
        "is_private": bool(is_private),
        "dm_targets": dm_targets,
    }

def today_ymd_kst() -> str:
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    return now.strftime("%Y-%m-%d")

def run() -> None:
    cfg = load_config()
    sent_signatures = set()
    today_key = today_ymd_kst()

    # Quick auth check (optional but helpful)
    auth = slack_api("auth.test", cfg["slack_token"], {})
    print("=== auth.test ===")
    print(json.dumps(auth, ensure_ascii=False, indent=2))

    items = fetch_all_list_items(cfg["slack_token"], cfg["list_id"])
    if not items:
        print("No items in list. Done.")
        return

    # Audit-only mode
    if env("AUDIT_ONLY", "false").lower() == "true":
        audit_list(cfg, items)
        return

    for it in items:
        item_id = it.get("id", "")
        name_for_log = extract_name(it)

        # 실행 중 중복 방지(하루 1회 기준)
        sig = make_daily_signature(item_id, today_key)
        if sig in sent_signatures:
            print(f"SKIP duplicate for today: {name_for_log} ({item_id})")
            continue

        try:
            r = build_rec_from_item(cfg, it)
            r2 = {**r, "today": today_kst()}
            prompt = build_prompt(r2)
            fortune_text = gemini_generate_text(cfg["gemini_key"], cfg["gemini_model"], prompt)
            out_text = fortune_text

            if r["is_private"]:
                for uid in r["dm_targets"]:
                    dm_channel = slack_open_dm(cfg["slack_token"], uid)
                    slack_post(cfg["slack_token"], dm_channel, out_text)
                    time.sleep(0.4)

                print(f"OK private DM sent for {r['name']} ({item_id}) to {len(r['dm_targets'])} users")

            else:
                slack_post(cfg["slack_token"], cfg["channel_id"], out_text)
                print(f"OK channel post sent for {r['name']} ({item_id}) -> {cfg['channel_id']}")

            # ✅ 성공했을 때만 기록
            sent_signatures.add(sig)

        except Exception as e:
            print(f"ERROR item={item_id} ({name_for_log}): {e}")
            notify_admins_of_error(
                cfg["slack_token"],
                cfg["admin_user_ids"],
                item_id,
                name_for_log,
                e,
            )
            continue

if __name__ == "__main__":
    run()
