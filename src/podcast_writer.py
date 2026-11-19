import json
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any

from src.config import (
    GEMINI_API_KEY,
    HOST_PERSONAS,
    KST,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


def clean_json_response(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def discover_text_models(client: Any) -> List[str]:
    """API 키에서 사용 가능한 최신 Gemini Flash 텍스트 생성 모델 목록을 탐색합니다."""
    preferred = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-flash-latest",
        "gemini-omni-flash-preview",
        "gemini-pro-latest",
    ]
    discovered: List[str] = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            if not name.startswith("gemini-"):
                continue
            low = name.lower()
            if any(skip in low for skip in ("tts", "embedding", "imagen", "veo", "aqa", "vision", "lite")):
                continue
            if "flash" in low or "pro" in low:
                discovered.append(name)
        discovered.sort(reverse=True)
        logger.info(f"[Gemini Models] 탐색된 텍스트 모델 목록: {discovered[:8]}")
    except Exception as e:
        logger.warning(f"[Gemini Models] 모델 목록 조회 실패 (기본 목록 사용): {e}")

    ordered: List[str] = []
    for m in preferred + discovered:
        if m not in ordered:
            ordered.append(m)
    return ordered


def build_curation_prompt(articles: List[Dict[str, Any]], date_str: str, weekday_ko: str) -> str:
    q_host = HOST_PERSONAS["questioner"]
    e_host = HOST_PERSONAS["explainer"]

    articles_text = "\n".join(
        [
            f"[{idx+1}] ({a['category']} | {a['source']}) 제목: {a['title']}\n"
            f"    링크: {a['url']}\n"
            f"    요약: {a['summary']}"
            for idx, a in enumerate(articles[:80])
        ]
    )

    return f"""당신은 구글 NotebookLM의 'Audio Overview(오디오 개요)'처럼 두 명의 호스트가
진짜 사람처럼 자연스럽게 수다 떨며 경제·경영 뉴스를 풀어주는 모닝 팟캐스트의 수석 작가입니다.

오늘 날짜는 {date_str} ({weekday_ko}요일)입니다.
아래 제공된 최근 이틀간의 국내외 경제/경영/금융/부동산 뉴스 후보 목록 중에서
가장 중요하고 학습 가치가 높은 **정확히 20개의 뉴스**를 엄선하여 JSON 형식으로 작성해 주세요.

[호스트 페르소나]
- 질문자 **{q_host['name']}** ({q_host['role']}): {q_host['style']}
- 해설자 **{e_host['name']}** ({e_host['role']}): {e_host['style']}

[초구어체(NotebookLM 스타일) 대사 작성 절대 규칙 — 기계음/낭독투 절대 금지!]
1. **문어체 완전 금지**: "~입니다", "~했습니다", "~에 대해 알아보겠습니다" 같은 딱딱한 뉴스 낭독투를 절대 쓰지 마세요.
2. **진짜 사람의 입말과 추임새(Backchanneling)**:
   - 모든 질문과 답변 대사에 실제 사람이 대화할 때 쓰는 추임새("어? 선배님,", "잠깐만요, 그러니까...", "헐, 진짜요?", "아~ 이제 감이 딱 오네요!", "하하, 맞아요 지민님!", "음... 쉽게 비유하자면요,", "그니까 제가 하고 싶은 말이 바로 그거예요!")를 자연스럽게 넣으세요.
   - 사람이 숨을 쉬며 말하듯 쉼표(,)와 말줄임표(...)로 호흡을 자연스럽게 끊어주세요.
3. **각 뉴스마다 4턴 티키타카 대화(`q1`, `a1`, `q2`, `a2`) 작성**:
   - `question`(`q1`): {q_host['name']}가 뉴스 팩트를 언급하며 초보자 눈높이에서 솔직하고 호기심 넘치게 던지는 첫 질문 (구어체 2~3문장)
   - `answer`(`a1`): {e_host['name']}가 찰떡같은 일상 비유를 들어 친절하게 풀어주는 첫 번째 답변 (구어체 3~4문장)
   - `followup_question`(`q2`): {q_host['name']}가 비유에 맞장구치며 "그럼 이게 당장 우리 직장인 지갑이나 회사 경영에는 어떤 영향을 주는 거예요?"라고 한 단계 더 파고드는 꼬리 질문 (구어체 1~2문장)
   - `economic_meaning`(`a2`): {e_host['name']}가 개인 재테크와 기업 경영에 미치는 나비효과와 핵심 포인트를 짚어주는 두 번째 답변 (구어체 3~4문장)
   - ※ 주의: 20개 뉴스마다 `followup_question`과 맞장구 표현을 똑같이 반복하지 말고, 각 뉴스 내용에 맞게 매번 다르게 생동감 있게 변주하세요!

[출력 JSON 스키마 (반드시 유효한 JSON 객체만 출력)]
{{
  "episode_title": "오늘의 팟캐스트 에피소드 제목",
  "executive_summary": "오늘의 핵심 흐름 3줄 요약 (줄바꿈 포함)",
  "opening_banter": [
    {{"speaker": "{q_host['name']}", "text": "{weekday_ko}요일 아침 출근길 생동감 넘치는 오프닝 인사와 오늘 경제 뉴스에 대한 호기심 (구어체 3문장)"}},
    {{"speaker": "{e_host['name']}", "text": "반갑게 맞장구치며 오늘 다룰 4가지 핵심 테마를 커피 한 잔 마시듯 쉽게 풀어주겠다는 다정한 인사 (구어체 3문장)"}}
  ],
  "themes": [
    {{
      "id": "theme_1",
      "title": "1. 테마 제목",
      "summary": "핵심 맥락 2문장 요약",
      "intro_q": "{q_host['name']}가 이 테마를 시작하며 던지는 자연스러운 화제 전환 질문 (구어체)",
      "intro_a": "{e_host['name']}가 이 테마의 큰 그림을 쉽게 짚어주는 도입 답변 (구어체)"
    }},
    {{
      "id": "theme_2",
      "title": "2. 테마 제목",
      "summary": "핵심 맥락 2문장 요약",
      "intro_q": "화제 전환 질문 (구어체)",
      "intro_a": "테마 도입 답변 (구어체)"
    }},
    {{
      "id": "theme_3",
      "title": "3. 테마 제목",
      "summary": "핵심 맥락 2문장 요약",
      "intro_q": "화제 전환 질문 (구어체)",
      "intro_a": "테마 도입 답변 (구어체)"
    }},
    {{
      "id": "theme_4",
      "title": "4. 테마 제목",
      "summary": "핵심 맥락 2문장 요약",
      "intro_q": "화제 전환 질문 (구어체)",
      "intro_a": "테마 도입 답변 (구어체)"
    }}
  ],
  "news_items": [
    {{
      "id": 1,
      "theme_id": "theme_1",
      "is_deep_dive": true,
      "category": "국내 경제/기업 | 글로벌 거시/빅테크 | 금융/금리/환율 | 부동산/재테크",
      "title": "뉴스 제목 (한국어)",
      "source": "언론사명",
      "url": "원문 링크",
      "fact_summary": "핵심 팩트 요약 (2~3문장)",
      "beginner_qna": {{
        "question": "지민의 첫 번째 호기심 질문 (초구어체 2~3문장)",
        "answer": "현우의 일상 비유 해설 답변 (초구어체 3~4문장)",
        "followup_question": "지민의 맞장구 및 심화 꼬리 질문 (초구어체 1~2문장)"
      }},
      "economic_meaning": "현우의 꼬리 질문 답변 및 개인/기업 파급효과 해설 (초구어체 3~4문장)",
      "key_terms": ["핵심용어1", "핵심용어2"]
    }}
  ],
  "closing_banter": [
    {{"speaker": "{q_host['name']}", "text": "오늘 20개 뉴스를 들으며 느낀 소감과 청취자 인사 (구어체 2~3문장)"}},
    {{"speaker": "{e_host['name']}", "text": "오늘의 핵심 한 줄 정리와 따뜻한 출근길 응원 마무리 인사 (구어체 2~3문장)"}}
  ],
  "glossary": [
    {{
      "term": "경제/경영 용어",
      "simple_def": "초보자용 한 줄 정의",
      "analogy": "일상 비유 설명"
    }}
  ]
}}

[후보 뉴스 목록]
{articles_text}
"""


def assemble_colloquial_dialogue(
    briefing: Dict[str, Any], weekday_ko: str
) -> List[Dict[str, Any]]:
    """Gemini가 생성한 오프닝, 4대 테마 도입부, 20개 뉴스별 4턴 티키타카, 클로징을 92턴 대화로 조립합니다."""
    q_name = HOST_PERSONAS["questioner"]["name"]
    e_name = HOST_PERSONAS["explainer"]["name"]
    dialogue: List[Dict[str, Any]] = []

    opening = briefing.get("opening_banter", [])
    if opening and len(opening) >= 2:
        for turn in opening:
            dialogue.append({
                "speaker": turn.get("speaker", q_name),
                "theme_id": "opening",
                "text": turn.get("text", ""),
            })
    else:
        dialogue.extend([
            {
                "speaker": q_name,
                "theme_id": "opening",
                "text": f"안녕하세요 여러분! 상쾌한 {weekday_ko}요일 아침 7시 30분입니다. 경제 뉴스만 보면 외계어 같아서 한숨부터 쉬던 경제 입문자 지민이에요! 어우, 현우 선배님, 지난 이틀 동안에도 우리 지갑이랑 회사 경영에 직결되는 뉴스들이 엄청 쏟아졌더라고요?",
            },
            {
                "speaker": e_name,
                "theme_id": "opening",
                "text": "하하, 맞아요 지민님! 출근길에 함께해 주시는 청취자분들도 반갑습니다. 오늘도 지난 이틀 동안 나온 뉴스 중에서 진짜 꼭 알아야 할 스무 개만 딱 골라서 네 가지 테마로 묶어 왔거든요. 어려운 용어는 오늘도 제가 커피 한 잔 마시면서 수다 떨듯이 아주 쉽게 비유로 풀어드릴게요!",
            },
        ])

    themes = briefing.get("themes", [])
    news_items = briefing.get("news_items", [])

    for idx, theme in enumerate(themes):
        tid = theme.get("id", f"theme_{idx+1}")
        intro_q = theme.get("intro_q") or f"좋아요! 그럼 바로 '{theme.get('title')}' 이야기부터 들어가 볼까요? 선배님, 이번 파트에서 우리가 제일 주목해야 할 흐름이 뭔가요?"
        intro_a = theme.get("intro_a") or f"음... 쉽게 말해서 이런 흐름이에요. {theme.get('summary')} 여기에 연결된 다섯 가지 뉴스를 하나씩 같이 뜯어볼까요?"

        dialogue.append({"speaker": q_name, "theme_id": tid, "text": intro_q})
        dialogue.append({"speaker": e_name, "theme_id": tid, "text": intro_a})

        theme_news = [item for item in news_items if item.get("theme_id") == tid]
        if not theme_news:
            theme_news = news_items[idx * 5 : (idx + 1) * 5]

        for n in theme_news:
            qna = n.get("beginner_qna", {})
            q1 = qna.get("question") or f"어, 선배님! '{n.get('title')}'라는 소식이 있거든요? {n.get('fact_summary')} 이게 도대체 무슨 뜻이고 왜 중요한 건가요?"
            a1 = qna.get("answer") or n.get("fact_summary", "")
            q2 = qna.get("followup_question") or "아~ 그렇게 비유해 주시니까 단번에 이해가 되네요! 근데 선배님, 그러면 이게 실제로 우리 지갑이나 회사 경영에는 어떤 영향을 주는 건가요?"
            a2 = n.get("economic_meaning") or "바로 그 뒷배경을 읽는 게 핵심이에요!"

            dialogue.extend([
                {"speaker": q_name, "theme_id": tid, "text": q1},
                {"speaker": e_name, "theme_id": tid, "text": a1},
                {"speaker": q_name, "theme_id": tid, "text": q2},
                {"speaker": e_name, "theme_id": tid, "text": a2},
            ])

    closing = briefing.get("closing_banter", [])
    if closing and len(closing) >= 2:
        for turn in closing:
            dialogue.append({
                "speaker": turn.get("speaker", q_name),
                "theme_id": "closing",
                "text": turn.get("text", ""),
            })
    else:
        dialogue.extend([
            {
                "speaker": q_name,
                "theme_id": "closing",
                "text": "와... 오늘 스무 개 뉴스를 네 가지 테마로 쭉 연결해서 듣다 보니까, 처음엔 외계어 같던 경제 용어들이 머릿속에 지도로 딱 그려지는 기분이에요!",
            },
            {
                "speaker": e_name,
                "theme_id": "closing",
                "text": "하하, 오늘도 지민님이 질문을 워낙 날카롭게 던져주신 덕분이에요! 출근길 함께해 주신 여러분도 오늘 브리핑이 작은 인사이트가 되었기를 바랍니다. 오늘도 활기찬 하루 보내세요!",
            },
        ])

    return dialogue


def compile_notebooklm_markdown(briefing: Dict[str, Any], date_str: str, weekday_ko: str) -> str:
    lines = [
        f"# [{date_str} ({weekday_ko}) 아침 7:30] 경제·경영 모닝 팟캐스트 브리핑 20선",
        "",
        "## 1. 오늘의 핵심 3줄 요약",
        briefing.get("executive_summary", ""),
        "",
        "## 2. 4대 핵심 테마 브리핑",
    ]
    for t in briefing.get("themes", []):
        lines.append(f"- **{t.get('title')}**: {t.get('summary')}")
    lines.append("")
    lines.append("## 3. 오늘의 주요 경제·경영 뉴스 20선 (초보자 눈높이 Q&A 해설)")

    for item in briefing.get("news_items", []):
        qna = item.get("beginner_qna", {})
        deep_badge = "🔥 [핵심 딥다이브]" if item.get("is_deep_dive") else "[주요 뉴스]"
        lines.extend(
            [
                f"### 뉴스 #{item.get('id')}. {deep_badge} [{item.get('category')}] {item.get('title')} ({item.get('source')})",
                f"- **핵심 팩트**: {item.get('fact_summary')}",
                f"- **초보자 질문 (Q)**: {qna.get('question')}",
                f"- **쉬운 비유 해설 (A)**: {qna.get('answer')}",
                f"- **경제/경영 파급효과**: {item.get('economic_meaning')}",
                f"- **관련 핵심 용어**: {', '.join(item.get('key_terms', []))}",
                "",
            ]
        )

    lines.append("## 4. 오늘의 전체 2인 팟캐스트 대화 스크립트")
    for turn in briefing.get("dialogue", []):
        lines.append(f"- **{turn.get('speaker')}**: {turn.get('text')}")

    return "\n".join(lines)


def generate_briefing_with_gemini(
    articles: List[Dict[str, Any]], now_kst: datetime | None = None
) -> Dict[str, Any]:
    if now_kst is None:
        now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%d")
    weekday_ko = ["월", "화", "수", "목", "금", "토", "일"][now_kst.weekday()]

    from google import genai
    from google.genai import types

    # Stage 1 대용량 JSON 생성(약 3~4.5분 소요)을 위해 330초(5.5분) 타임아웃 설정
    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta", "timeout": 330000},
    )
    curation_prompt = build_curation_prompt(articles, date_str, weekday_ko)

    candidate_models = discover_text_models(client)
    briefing = None

    for model_name in candidate_models[:4]:
        # 503 일시적 과부하 대비 모델당 최대 2회 시도
        for attempt in range(2):
            try:
                logger.info(
                    f"[Gemini] {model_name} 모델로 20대 뉴스 선별 및 92턴 초구어체 대본 생성 중 (시도 {attempt+1}/2, 최대 5.5분)..."
                )
                response = client.models.generate_content(
                    model=model_name,
                    contents=curation_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        max_output_tokens=16384,
                        temperature=0.55,
                        http_options=types.HttpOptions(timeout=330000),
                    ),
                )
                briefing = json.loads(clean_json_response(response.text))
                if briefing and briefing.get("news_items"):
                    logger.info(
                        f"[Gemini] {model_name} 호출 성공! (뉴스 {len(briefing.get('news_items', []))}개)"
                    )
                    break
            except Exception as e:
                err_str = str(e)
                logger.warning(f"[Gemini] {model_name} (시도 {attempt+1}/2) 실패: {e}")
                if "404" in err_str or "NOT_FOUND" in err_str:
                    break
                if attempt == 0 and ("503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str):
                    logger.info("   -> 서버 일시 과부하(503/429)로 10초 대기 후 재시도합니다...")
                    time.sleep(10)
                    continue
        if briefing and briefing.get("news_items"):
            break

    if not briefing or not briefing.get("news_items"):
        raise RuntimeError("Gemini 뉴스 및 대본 생성에 실패했습니다.")

    full_dialogue = assemble_colloquial_dialogue(briefing, weekday_ko)
    logger.info(f"[Podcast Script] 총 {len(full_dialogue)}턴의 초구어체 2인 팟캐스트 대본 조립 완료!")

    briefing["dialogue"] = full_dialogue
    briefing["date"] = date_str
    briefing["weekday"] = weekday_ko
    briefing["generated_at"] = now_kst.strftime("%Y-%m-%d %H:%M KST")

    md_content = compile_notebooklm_markdown(briefing, date_str, weekday_ko)
    md_path = OUTPUT_DIR / f"notebook_source_{date_str}.md"
    md_path.write_text(md_content, encoding="utf-8")
    briefing["notebook_source_path"] = str(md_path)
    return briefing
