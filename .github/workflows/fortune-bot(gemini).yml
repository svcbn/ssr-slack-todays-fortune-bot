import os
import json
import time
import requests
from typing import Any, Dict, List, Optional, Tuple


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
    v = os.getenv(name, default)
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


# -----------------------------
# Prompt builder (your "자리 고정 / 제목 유동" 설계)
# -----------------------------
def build_prompt(r: Dict[str, Any]) -> str:
    gender_ko = "남성" if r["gender"] == "m" else "여성"
    time_ko = TIME_CODE_TO_LABEL.get(r["time_code"], "모름")

    return f"""
너는 한국어로 작성되는 고급 일일 운세 칼럼의 전문 작가다.
아래 출력은 엔터테인먼트와 자기 성찰 목적의 창작물이며,
과학적 사실이나 실제 예언을 주장하지 않는다.

⚠️ 매우 중요:
- 아래에 제시된 것은 '형식의 자리'일 뿐, 제목·소제목·항목명은 절대 고정하지 않는다.
- 그날의 운세 흐름을 보고 가장 어울리는 제목과 항목 구조를 스스로 판단해 작성한다.
- 사주·운세 전문 용어는 직접 나열하지 말고, 반드시 비유와 이야기로 풀어 설명한다.
- 단정적 표현(반드시/확정/무조건) 금지.
- 공포·질병·재난·죽음·폭력, 특정 투자 종목 추천 금지.
- 말투는 차분하고 설득력 있게, 과장하거나 가볍지 않게 유지한다.

[입력 정보]
- 이름: {r["name"]}
- 생년월일(양력): {r["birthday"]}
- 성별: {gender_ko}
- 출생시간: {time_ko}

────────────────────
[출력 형식 — 자리만 고정, 내용·제목은 전부 자유]
────────────────────

① 오늘의 운세 전체를 대표하는 메인 제목
   - 사자성어, 은유, 상징적 문구 중 가장 어울리는 형태로 작성
   - 날짜(YYYY년 M월 D일 요일)를 그 아래 한 줄로 표기

② 오늘 하루의 흐름을 압축한 한 문장 인용문
   - 따옴표 사용
   - 감정과 방향성이 드러나야 함

③ 오늘의 전체 운세 해설 (2문단)
   - 1문단: 오늘의 분위기, 흐름, 기회와 평가
   - 2문단: 장애물 → 전환 → 긍정적 결말의 서사
   - 사람, 환경, 타이밍의 작용을 자연스럽게 포함

④ 오늘의 운을 이해하기 위한 심층 해석 파트
   - 이 섹션의 제목은 자유롭게 생성
   - ‘타고난 나의 성향’과 ‘오늘 마주한 흐름’을
     자연물·상황·이야기 구조로 대비시켜 설명

⑤ 오늘의 핵심 포인트들 (2~4개)
   - 각 포인트는 소제목 + 설명 문단으로 구성
   - 소제목은 오늘의 운을 가장 잘 상징하는 문구로 자유 생성

⑥ 오늘을 위한 현실적인 행동 조언 (3문장)
   - 줄바꿈으로만 구분 (번호·불릿 금지)
   - 태도 / 관계 / 자기확신 관점에서 각각 하나씩

⑦ 따뜻하게 마무리되는 마지막 문장
   - 독자를 다독이며 여운을 남길 것

[분량 가이드]
- 전체 900~1400자 내외
- 읽는 사람이 “오늘 나를 위해 쓴 글”이라고 느낄 것
""".strip()


# -----------------------------
# Gemini call (REST generateContent)
# -----------------------------
def gemini_generate_text(api_key: str, model: str, prompt: str) -> str:
    # Gemini API: generateContent endpoint :contentReference[oaicite:3]{index=3}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        # 필요 시 조절
        "generationConfig": {
            "temperature": 0.8,
            "topP": 0.95,
            "maxOutputTokens": 1400,
        },
    }
    resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
    data = resp.json()
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {data}")

    # Typical shape: candidates[0].content.parts[0].text
    cands = data.get("candidates") or []
    if not cands:
        raise RuntimeError(f"Gemini returned no candidates: {data}")

    content = cands[0].get("content") or {}
    parts = content.get("parts") or []
    texts = []
    for p in parts:
        t = p.get("text")
        if isinstance(t, str) and t.strip():
            texts.append(t.strip())
    out = "\n".join(texts).strip()
    if not out:
        raise RuntimeError(f"Gemini returned empty text: {data}")
    return out


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
    # chat.postMessage :contentReference[oaicite:5]{index=5}
    slack_api("chat.postMessage", token, {"channel": channel, "text": text})


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
        "gemini_model": env("GEMINI_MODEL", "gemini-1.5-flash-001"),
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


def run() -> None:
    cfg = load_config()

    # Quick auth check (optional but helpful)
    auth = slack_api("auth.test", cfg["slack_token"], {})
    print("=== auth.test ===")
    print(json.dumps(auth, ensure_ascii=False, indent=2))

    items = fetch_all_list_items(cfg["slack_token"], cfg["list_id"])
    if not items:
        print("No items in list. Done.")
        return

    # 처리 대상: 일단 전부. (나중에 'enabled' 컬럼이나 'last_sent'로 필터링 가능)
    for it in items:
        item_id = it.get("id", "")
        try:
            r = build_rec_from_item(cfg, it)
            prompt = build_prompt(r)
            fortune_text = gemini_generate_text(cfg["gemini_key"], cfg["gemini_model"], prompt)

            # Slack 전송 텍스트 (그대로 전달)
            # 필요하면 여기서 상단에 멘션/헤더 추가 가능
            out_text = fortune_text

            if r["is_private"]:
                if not r["dm_targets"]:
                    raise RuntimeError("private=true but no dm_targets (assignee/admin)")

                for uid in r["dm_targets"]:
                    dm_channel = slack_open_dm(cfg["slack_token"], uid)
                    slack_post(cfg["slack_token"], dm_channel, out_text)
                    time.sleep(0.4)  # API 레이트 리밋 완화
                print(f"OK private DM sent for {r['name']} ({item_id}) to {len(r['dm_targets'])} users")
            else:
                slack_post(cfg["slack_token"], cfg["channel_id"], out_text)
                print(f"OK channel post sent for {r['name']} ({item_id}) -> {cfg['channel_id']}")

        except Exception as e:
            # 실패는 채널에 올리지 않고, 로그만 남김
            print(f"ERROR item={item_id}: {e}")


if __name__ == "__main__":
    run()
