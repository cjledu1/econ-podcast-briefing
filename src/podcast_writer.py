import json
import logging
import re
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
    """API 키에서 사용 가능한 최신 Gemini Flash 텍스트 생성 모델 목록을 동적으로 탐색합니다."""
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
    articles_text = "\n".join(
        [
            f"[{idx+1}] ({a['category']} | {a['source']}) 제목: {a['title']}\n"
            f"    링크: {a['url']}\n"
            f"    요약: {a['summary']}"
            for idx, a in enumerate(articles[:85])
        ]
    )

    return f"""당신은 경제·경영 지식이 전혀 없는 입문자를 위해 매주 월·수·금 아침 7시 30분에 발행되는
'2인 문답형 경제/경영 모닝 팟캐스트'의 수석 에디터입니다.

오늘 날짜는 {date_str} ({weekday_ko}요일)입니다.
아래 제공된 최근 이틀간의 국내외 경제/경영/금융/부동산 뉴스 후보 목록 중에서
가장 중요하고 학습 가치가 높은 **정확히 20개의 뉴스**를 엄선하여 JSON 형식으로 작성해 주세요.

[선별 및 구성 원칙]
1. 국내 경제/산업/기업 경영, 글로벌 거시경제/미국 증시/빅테크, 금리/환율/부동산/금융지표가 균형 있게 포함되도록 20개를 고르고 4개의 핵심 테마(theme_1 ~ theme_4, 각 5개)로 분류하세요. 핵심 이슈 6~8개는 `is_deep_dive: true`로 지정하세요.
2. 각 뉴스마다 초보자의 눈높이 질문(`question`, 자연스러운 구어체)과 일상 비유를 활용한 입말 답변(`answer`, 친절한 구어체 3~4문장), 그리고 개인과 기업 경영에 미치는 파급효과(`economic_meaning`, 구어체 2~3문장)를 상세히 작성하세요.
3. 오늘의 20개 뉴스에 등장하는 핵심 경제/경영 용어 **12개**를 골라 한 줄 정의(`simple_def`)와 일상 비유(`analogy`)를 작성하세요.

[출력 JSON 스키마 (반드시 유효한 JSON 객체만 출력)]
{{
  "episode_title": "오늘의 팟캐스트 에피소드 제목",
  "executive_summary": "오늘의 핵심 흐름 3줄 요약 (줄바꿈 포함)",
  "themes": [
    {{"id": "theme_1", "title": "1. 테마 제목", "summary": "핵심 맥락 2문장 요약"}},
    {{"id": "theme_2", "title": "2. 테마 제목", "summary": "핵심 맥락 2문장 요약"}},
    {{"id": "theme_3", "title": "3. 테마 제목", "summary": "핵심 맥락 2문장 요약"}},
    {{"id": "theme_4", "title": "4. 테마 제목", "summary": "핵심 맥락 2문장 요약"}}
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
        "question": "어? 선배님, 이 뉴스에서 말하는 개념이 도대체 무슨 뜻이에요?",
        "answer": "하하, 쉽게 비유하자면요... (일상 비유를 들어 3~4문장으로 친절하게 설명)"
      }},
      "economic_meaning": "이게 우리 같은 직장인 지갑이나 회사 경영에는 어떤 영향을 주냐면요... (2~3문장)",
      "key_terms": ["핵심용어1", "핵심용어2"]
    }}
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


def build_theme_dialogue_prompt(
    theme: Dict[str, Any],
    theme_news: List[Dict[str, Any]],
    part_idx: int,
    total_parts: int,
    date_str: str,
    weekday_ko: str,
) -> str:
    q_host = HOST_PERSONAS["questioner"]
    e_host = HOST_PERSONAS["explainer"]

    news_context = json.dumps(theme_news, ensure_ascii=False, indent=2)
    position_instruction = ""
    if part_idx == 1:
        position_instruction = (
            f"- 이번 파트는 에피소드의 **오프닝 및 첫 번째 테마**입니다. "
            f"{weekday_ko}요일 아침 출근길 인사와 함께 자연스럽게 대화를 시작하세요."
        )
    elif part_idx == total_parts:
        position_instruction = (
            "- 이번 파트는 에피소드의 **마지막 테마 및 클로징**입니다. "
            "마지막에 오늘 다룬 4가지 테마를 한 줄씩 정리하고 따뜻한 출근길 응원 인사로 마무리하세요."
        )
    else:
        position_instruction = (
            f"- 이번 파트는 **파트 {part_idx}/{total_parts}**입니다. "
            "이전 파트에서 자연스럽게 화제를 전환하며 대화를 이어가세요."
        )

    return f"""당신은 구글 NotebookLM의 'Audio Overview(오디오 개요)'처럼 두 명의 호스트가
진짜 사람처럼 자연스럽게 티키타카하며 경제·경영 뉴스를 풀어주는 팟캐스트 대본 작가입니다.

[호스트 설정]
- **{q_host['name']}** ({q_host['role']}): {q_host['style']}
- **{e_host['name']}** ({e_host['role']}): {e_host['style']}

[이번 파트 테마 ({part_idx}/{total_parts})]
- 테마 제목: {theme.get('title')}
- 테마 요약: {theme.get('summary')}
{position_instruction}

[자연스러운 구어체(초구어체) 작성 절대 규칙 — 기계음/낭독투 완전 금지!]
1. **문어체 절대 금지**: "~입니다", "~했습니다", "~에 대해 알아보겠습니다" 같은 딱딱한 뉴스 브리핑 말투를 절대 쓰지 마세요.
2. **실제 사람의 입말과 맞장구(Backchanneling)**:
   - 대사 중간중간에 자연스러운 추임새와 감탄사("어?", "잠깐만요 선배님,", "아~ 그러니까요!", "헐, 진짜요?", "음... 쉽게 비유하자면요,", "하하, 맞아요!", "그니까 제가 하고 싶은 말이 그거예요!")를 풍부하게 넣으세요.
   - 문장을 너무 길게 하나로 쓰지 말고, 사람이 실제로 숨을 쉬며 말하듯 쉼표(,)와 말줄임표(...)를 적절히 사용해 호흡을 끊어주세요.
3. **5개 뉴스 전수 커버 + 핵심 이슈 딥다이브**:
   - 아래 제공된 이 테마의 뉴스 5개를 대화 흐름 속에서 모두 자연스럽게 연결해 다루세요.
   - `is_deep_dive: true`인 핵심 뉴스는 {q_host['name']}가 꼬리에 꼬리를 무는 질문("근데 왜 하필 지금 그런 거예요?", "그럼 우리 월급이나 회사에는 어떤 영향이 와요?")을 던지고, {e_host['name']}가 찰떡같은 일상 비유로 깊이 있게 풀어주세요.
4. **분량**: 이번 테마 파트에서만 두 사람의 대화 턴(turn)이 **최소 20턴 ~ 26턴**이 되도록 풍성하게 작성하세요.

[이 테마의 뉴스 5개 데이터]
{news_context}

[출력 JSON 스키마 (반드시 유효한 JSON 객체만 출력)]
{{
  "dialogue": [
    {{
      "speaker": "{q_host['name']}",
      "theme_id": "{theme.get('id')}",
      "text": "자연스러운 입말 대사"
    }},
    {{
      "speaker": "{e_host['name']}",
      "theme_id": "{theme.get('id')}",
      "text": "자연스러운 입말 대사"
    }}
  ]
}}
"""


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


def build_fallback_colloquial_dialogue(
    themes: List[Dict[str, Any]],
    news_items: List[Dict[str, Any]],
    weekday_ko: str,
    include_opening: bool = False,
    include_closing: bool = False,
) -> List[Dict[str, Any]]:
    """Stage 2 특정 파트가 타임아웃/503일 때 Stage 1의 Q&A 데이터를 초구어체 티키타카 대화로 즉시 변환합니다."""
    q_name = HOST_PERSONAS["questioner"]["name"]
    e_name = HOST_PERSONAS["explainer"]["name"]
    dialogue: List[Dict[str, Any]] = []

    if include_opening:
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

    for theme in themes:
        tid = theme.get("id", "theme_1")
        dialogue.append({
            "speaker": q_name,
            "theme_id": tid,
            "text": f"좋아요! 그럼 바로 '{theme.get('title')}' 이야기부터 들어가 볼까요? 선배님, 이번 파트에서 우리가 제일 주목해야 할 흐름이 뭔가요?",
        })
        dialogue.append({
            "speaker": e_name,
            "theme_id": tid,
            "text": f"음... 쉽게 말해서 이런 흐름이에요. {theme.get('summary')} 여기에 연결된 다섯 가지 뉴스를 하나씩 같이 뜯어볼까요?",
        })
        for n in [item for item in news_items if item.get("theme_id") == tid]:
            qna = n.get("beginner_qna", {})
            dialogue.extend([
                {
                    "speaker": q_name,
                    "theme_id": tid,
                    "text": f"어, 선배님! {n.get('id')}번 뉴스를 보니까 '{n.get('title')}'라는 소식이 있거든요? {n.get('fact_summary')} 솔직히 제목만 봐서는 감이 잘 안 오는데... {qna.get('question', '이게 도대체 무슨 뜻이고 왜 중요한 건가요?')}",
                },
                {
                    "speaker": e_name,
                    "theme_id": tid,
                    "text": f"아~ 그거 진짜 많이들 헷갈려 하시는 부분이에요! {qna.get('answer', '')}",
                },
                {
                    "speaker": q_name,
                    "theme_id": tid,
                    "text": "오... 그렇게 비유해 주시니까 진짜 단번에 이해가 되네요! 근데 선배님, 그러면 이게 실제로 우리 같은 직장인 지갑이나 회사 경영에는 어떤 영향을 주는 건가요?",
                },
                {
                    "speaker": e_name,
                    "theme_id": tid,
                    "text": f"그니까요, 바로 그 뒷배경을 읽는 게 핵심이거든요! {n.get('economic_meaning')} 그래서 앞으로 뉴스에서 {', '.join(n.get('key_terms', ['핵심지표']))} 같은 단어가 나오면 오늘 나눈 이야기를 떠올리시면 됩니다.",
                },
            ])

    if include_closing:
        dialogue.extend([
            {
                "speaker": q_name,
                "theme_id": "closing",
                "text": "와... 오늘 스무 개 뉴스를 네 가지 테마로 쭉 연결해서 듣다 보니까, 처음엔 외계어 같던 경제 용어들이 머릿속에 지도로 딱 그려지는 기분이에요!",
            },
            {
                "speaker": e_name,
                "theme_id": "closing",
                "text": "하하, 오늘도 지민님이 질문을 워낙 날카롭게 던져주신 덕분이에요! 출근길 함께해 주신 여러분도 오늘 브리핑이 작은 인사이트가 되었기를 바랍니다. 저희는 다음 브리핑 시간에 더 알찬 소식으로 찾아올게요. 오늘도 활기찬 하루 보내세요!",
            },
        ])
    return dialogue


def _call_gemini_json(
    client: Any,
    model_name: str,
    prompt: str,
    temperature: float,
    timeout_ms: int = 75000,
) -> Dict[str, Any]:
    """Thinking 지연을 최소화하고 엄격한 타임아웃(기본 75초)을 적용하여 JSON 응답을 받아옵니다."""
    from google.genai import types

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=12288,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                http_options=types.HttpOptions(timeout=timeout_ms),
            ),
        )
    except Exception as first_err:
        err_msg = str(first_err).lower()
        if "thinking" in err_msg or "invalid_argument" in err_msg or "400" in err_msg:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=12288,
                    temperature=temperature,
                    http_options=types.HttpOptions(timeout=timeout_ms),
                ),
            )
        else:
            raise
    return json.loads(clean_json_response(response.text))


def generate_briefing_with_gemini(
    articles: List[Dict[str, Any]], now_kst: datetime | None = None
) -> Dict[str, Any]:
    if now_kst is None:
        now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%d")
    weekday_ko = ["월", "화", "수", "목", "금", "토", "일"][now_kst.weekday()]

    from google import genai

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta", "timeout": 80000},
    )
    curation_prompt = build_curation_prompt(articles, date_str, weekday_ko)

    candidate_models = discover_text_models(client)
    briefing = None

    for model_name in candidate_models[:5]:
        try:
            logger.info(f"[Gemini Stage 1] {model_name} 모델로 20대 뉴스 선별 및 해설 생성 중 (타임아웃 80초)...")
            briefing = _call_gemini_json(
                client=client,
                model_name=model_name,
                prompt=curation_prompt,
                temperature=0.35,
                timeout_ms=80000,
            )
            if briefing and briefing.get("news_items"):
                logger.info(f"[Gemini Stage 1] {model_name} 호출 성공! ({len(briefing.get('news_items', []))}개 뉴스)")
                break
        except Exception as e:
            logger.warning(f"[Gemini Stage 1] {model_name} 호출 실패/타임아웃: {e}")

    if not briefing or not briefing.get("news_items"):
        raise RuntimeError("모든 Gemini 모델 Stage 1 호출에 실패했습니다.")

    themes = briefing.get("themes", [])
    news_items = briefing.get("news_items", [])
    full_dialogue: List[Dict[str, Any]] = []

    for idx, theme in enumerate(themes):
        tid = theme.get("id", f"theme_{idx+1}")
        theme_news = [n for n in news_items if n.get("theme_id") == tid]
        if not theme_news:
            theme_news = news_items[idx * 5 : (idx + 1) * 5]

        theme_prompt = build_theme_dialogue_prompt(
            theme=theme,
            theme_news=theme_news,
            part_idx=idx + 1,
            total_parts=len(themes),
            date_str=date_str,
            weekday_ko=weekday_ko,
        )

        part_turns: List[Dict[str, Any]] = []
        for stage2_model in candidate_models[:3]:
            try:
                logger.info(
                    f"[Gemini Stage 2 - 파트 {idx+1}/{len(themes)}] '{theme.get('title')}' 초구어체 2인 대본 생성 중 ({stage2_model}, 타임아웃 65초)..."
                )
                part_json = _call_gemini_json(
                    client=client,
                    model_name=stage2_model,
                    prompt=theme_prompt,
                    temperature=0.65,
                    timeout_ms=65000,
                )
                part_turns = part_json.get("dialogue", [])
                if part_turns:
                    logger.info(
                        f"   -> 파트 {idx+1} 대본 {len(part_turns)}턴 생성 완료 ({stage2_model}, 누적 {len(full_dialogue) + len(part_turns)}턴)"
                    )
                    break
            except Exception as e:
                logger.warning(f"[Gemini Stage 2] 파트 {idx+1} ({stage2_model}) 오류/타임아웃: {e}")

        if part_turns:
            full_dialogue.extend(part_turns)
        else:
            logger.info(f"   -> 파트 {idx+1}: Stage 1 심층 Q&A 기반 초구어체 대본(22턴) 즉시 적용")
            full_dialogue.extend(
                build_fallback_colloquial_dialogue(
                    [theme],
                    theme_news,
                    weekday_ko,
                    include_opening=(idx == 0),
                    include_closing=(idx == len(themes) - 1),
                )
            )

    briefing["dialogue"] = full_dialogue or build_fallback_colloquial_dialogue(
        themes, news_items, weekday_ko, include_opening=True, include_closing=True
    )
    briefing["date"] = date_str
    briefing["weekday"] = weekday_ko
    briefing["generated_at"] = now_kst.strftime("%Y-%m-%d %H:%M KST")

    md_content = compile_notebooklm_markdown(briefing, date_str, weekday_ko)
    md_path = OUTPUT_DIR / f"notebook_source_{date_str}.md"
    md_path.write_text(md_content, encoding="utf-8")
    briefing["notebook_source_path"] = str(md_path)
    return briefing
