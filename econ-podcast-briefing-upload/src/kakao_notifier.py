import json
import logging
from typing import Dict, Any, Tuple
import requests

from src.config import (
    KAKAO_REST_API_KEY,
    KAKAO_CLIENT_SECRET,
    KAKAO_REFRESH_TOKEN,
)

logger = logging.getLogger(__name__)


def refresh_kakao_access_token() -> Tuple[str | None, str | None]:
    """
    KAKAO_REFRESH_TOKEN을 사용하여 유효한 access_token을 발급받습니다.
    반환값: (access_token, 새로 갱신된 refresh_token 또는 None)
    """
    if not KAKAO_REST_API_KEY or not KAKAO_REFRESH_TOKEN:
        logger.warning("KAKAO_REST_API_KEY 또는 KAKAO_REFRESH_TOKEN이 설정되지 않았습니다.")
        return None, None

    token_url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN,
    }
    if KAKAO_CLIENT_SECRET:
        payload["client_secret"] = KAKAO_CLIENT_SECRET

    try:
        resp = requests.post(token_url, data=payload, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        access_token = data.get("access_token")
        new_refresh_token = data.get("refresh_token")
        if new_refresh_token:
            logger.info(
                "[Kakao Auth] 새로운 refresh_token이 발급되었습니다. (만료 임박 시 자동 갱신됨)"
            )
        return access_token, new_refresh_token
    except Exception as e:
        logger.error(f"[Kakao Auth] 액세스 토큰 갱신 실패: {e}")
        return None, None


def format_kakao_briefing_text(
    briefing: Dict[str, Any], audio_meta: Dict[str, Any], web_url: str
) -> str:
    """카카오톡 '나에게 보내기' 텍스트 템플릿(최대 1,000자 제한 고려)에 맞춘 핵심 요약 메시지."""
    date_str = briefing.get("date", "")
    weekday = briefing.get("weekday", "")
    themes = briefing.get("themes", [])
    glossary = briefing.get("glossary", [])

    lines = [
        f"🎧 [{date_str} ({weekday}) 07:30 경제·경영 팟캐스트]",
        "",
        "📌 오늘 아침 4대 핵심 테마 (총 20개 뉴스)",
    ]

    for t in themes[:5]:
        lines.append(f"• {t.get('title', '')}")

    lines.append("")
    lines.append("🙋 오늘 지민 & 현우가 깊게 파고든 질문:")
    deep_items = [item for item in briefing.get("news_items", []) if item.get("is_deep_dive")]
    for item in deep_items[:3]:
        q_text = item.get("beginner_qna", {}).get("question", item.get("title", ""))
        lines.append(f"Q. {q_text}")

    if glossary:
        term_names = ", ".join([g.get("term", "") for g in glossary[:5]])
        lines.append("")
        lines.append(f"📖 오늘의 용어: {term_names} 외")

    if audio_meta.get("session_expired"):
        lines.append("")
        lines.append(
            "⚠️ [안내] 구글 NotebookLM 세션이 만료되어 오늘은 AI 2인 멀티보이스로 자동 제작되었습니다."
        )

    lines.append("")
    lines.append(f"👉 웹 플레이어: {web_url}")

    full_text = "\n".join(lines)
    # 카카오톡 텍스트 템플릿 text 필드는 최대 1000자까지 지원
    if len(full_text) > 950:
        full_text = full_text[:945] + "..."
    return full_text


def send_kakao_briefing(
    briefing: Dict[str, Any], audio_meta: Dict[str, Any], web_url: str
) -> bool:
    """카카오톡 '나에게 보내기' API로 오늘의 20분 음성 브리핑 링크와 요약을 전송합니다."""
    message_text = format_kakao_briefing_text(briefing, audio_meta, web_url)

    access_token, _ = refresh_kakao_access_token()
    if not access_token:
        logger.info(
            "[Kakao Notifier] 토큰 미설정으로 실제 전송 대신 전송될 카카오톡 메시지 미리보기를 출력합니다:\n"
            + "=" * 60
            + f"\n{message_text}\n"
            + f"[버튼 클릭 시 이동 URL]: {web_url}\n"
            + "=" * 60
        )
        return False

    send_url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    template_object = {
        "object_type": "text",
        "text": message_text,
        "link": {
            "web_url": web_url,
            "mobile_web_url": web_url,
        },
        "button_title": "🎧 20분 음성 & 해설 듣기",
    }

    try:
        resp = requests.post(
            send_url,
            headers=headers,
            data={"template_object": json.dumps(template_object, ensure_ascii=False)},
            timeout=12,
        )
        resp.raise_for_status()
        res_json = resp.json()
        if res_json.get("result_code") == 0:
            logger.info("[Kakao Notifier] 카카오톡 '나에게 보내기' 브리핑 발송 성공!")
            return True
        logger.warning(f"[Kakao Notifier] 응답 코드 확인 필요: {res_json}")
        return False
    except Exception as e:
        logger.error(f"[Kakao Notifier] 메시지 발송 실패: {e}")
        return False
