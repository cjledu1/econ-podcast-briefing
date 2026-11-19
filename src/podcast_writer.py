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
    """API 키에서 사용 가능한 최신 Gemini Flash/Pro 텍스트 생성 모델 목록을 동적으로 탐색합니다."""
    preferred = ["gemini-3.8-flash", "gemini-3.8-pro", "gemini-3.5-flash", "gemini-3.0-flash", "gemini-2.5-flash"]
    discovered: List[str] = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            if not name.startswith("gemini-"):
                continue
            low = name.lower()
            if any(skip in low for skip in ("tts", "embedding", "imagen", "veo", "aqa", "vision")):
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
            for idx, a in enumerate(articles[:90])
        ]
    )

    return f"""당신은 경제·경영 지식이 전혀 없는 입문자를 위해 매주 월·수·금 아침 7시 30분에 발행되는
'2인 문답형 경제/경영 모닝 팟캐스트'의 수석 에디터입니다.

오늘 날짜는 {date_str} ({weekday_ko}요일)입니다.
아래 제공된 최근 이틀간의 국내외 경제/경영/금융/부동산 뉴스 후보 목록 중에서
가장 중요하고 학습 가치가 높은 **정확히 20개의 뉴스**를 엄선하여 JSON 형식으로 작성해 주세요.

[선별 및 구성 원칙]
1. 국내 경제/산업/기업 경영, 글로벌 거시경제/미국 증시/빅테크, 금리/환율/부동산/금융지표가 균형 있게 포함되도록 20개를 고르고 4개의 핵심 테마(theme_1 ~ theme_4, 각 5개)로 분류하세요. 핵심 이슈 6~8개는 `is_deep_dive: true`로 지정하세요.
2. 각 뉴스마다 초보자의 눈높이 질문(`question`)과 일상 비유를 활용한 입말 답변(`answer`), 그리고 개인과 기업 경영에 미치는 파급효과(`economic_meaning`)를 상세히 작성하세요.
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
      "summary": "뉴스 핵심 사실 요약 (2~3문장)",
      "economic_meaning": "이 뉴스가 갖는 경제·경영적 의미와 개인/기업에 미치는 나비효과 해설 (3~4문장)",
      "beginner_qna": {{
        "question": "초보자(지민)의 자연스러운 구어체 질문",
        "answer": "멘토(현우)의 쉬운 일상 비유와 구어체 답변"
      }},
      "key_terms": ["관련 용어1", "관련 용어2"]
    }}
  ],
  "glossary": [
    {{
      "term": "경제/경영 용어",
      "simple_def": "초보자용 한 줄 정의",
      "analogy": "일상생활 비유를 통한 친절한 설명 (2~3문장)",
      "related_news_id": 1
    }}
  ]
}}

[수집된 최근 2일간 경제/경영 뉴스 후보 목록]
{articles_text}
"""


def build_theme_dialogue_prompt(
    theme: Dict[str, Any],
    theme_news: List[Dict[str, Any]],
    theme_index: int,
    total_themes: int,
    date_str: str,
    weekday_ko: str,
) -> str:
    q_host = HOST_PERSONAS["questioner"]
    e_host = HOST_PERSONAS["explainer"]

    news_detail_text = json.dumps(theme_news, ensure_ascii=False, indent=2)
    section_guide = ""
    if theme_index == 0:
        section_guide += f"- 이번 파트는 팟캐스트의 **오프닝({date_str} {weekday_ko}요일 아침 인사와 오늘 다룰 4대 테마 소개)**으로 시작해 곧바로 첫 번째 테마 본론으로 들어가세요.\n"
    if theme_index == total_themes - 1:
        section_guide += "- 이번 파트의 마지막에는 오늘 배운 핵심 경제/경영 원리를 짧게 복습하고 출근길 청취자를 응원하는 **클로징 인사**를 포함하세요.\n"

    return f"""당신은 구글 NotebookLM Audio Overview(오디오 개요)처럼 실제 사람 두 명이 스튜디오에서 대본 없이 수다를 떠는 듯한 초자연스러운 경제 팟캐스트 대본 작가입니다.
전체 20분 분량(총 4개 테마 파트)의 2인 경제/경영 팟캐스트 중
지금은 **[파트 {theme_index + 1}/{total_themes}: {theme.get('title')}]**의 대화 대본을 작성합니다.

[진행자 페르소나]
- **{q_host['name']} (질문자 / 호기심 많은 직장인 후배)**: 경제 뉴스가 낯선 직장인. 짧은 호흡으로 '어? 잠깐만요 선배님, 그건 무슨 뜻이에요?', '아... 그니까 결국 내 대출이자가 안 떨어진다는 얘기네요?'처럼 추임새와 리액션을 넣고 질문을 던지는 역할.
- **{e_host['name']} (해설자 / 친절한 경제·경영 멘토 선배)**: 절대 뉴스 앵커처럼 '~했습니다', '~전망됩니다' 같은 문어체를 쓰지 않고, '그게 왜 그러냐면요...', '쉽게 말해서 이런 거예요,', '하하, 맞아요 다들 그렇게 생각하시거든요?'처럼 100% 자연스러운 일상 입말(구어체)과 찰진 비유로 맥락을 짚어주는 역할.

[NotebookLM처럼 100% 사람 같은 대화를 만드는 핵심 작성 규칙 — 반드시 지킬 것!]
{section_guide}1. **신문 기사 문어체 절대 금지 (100% 실제 입말/구어체만 사용)**:
   - '~밝혔습니다', '~시사했습니다', '~전망됩니다', '~분석됩니다' 같은 뉴스 아나운서 말투를 절대 쓰지 마세요!
   - 실제 친한 선후배가 대화하듯 '~거든요?', '~잖아요', '~인 거죠', '~더라고요', '~할까요?', '~라니까요' 같은 살아있는 구어체 어미만 사용하세요.
2. **혼자 길게 연설 금지 -> 짧은 호흡의 티키타카와 맞장구**:
   - 한 사람이 혼자 5~6문장씩 교과서 읽듯 설명하면 기계처럼 들립니다.
   - {e_host['name']}님이 2~3문장 설명하면 {q_host['name']}님이 바로 치고 들어오며 대화 템포를 빠르게 주고받으세요.
3. **사람 같은 호흡과 추임새(담화 표지어) 적극 삽입**:
   - 대사 앞과 중간에 '음...', '아, 맞아요,', '그니까요!', '하하, 사실 그게 왜 그러냐면요...', '솔직히 말해서,' 같은 자연스러운 추임새와 쉼표(,), 말줄임표(...)를 넣어 음성 합성 시 실제 사람이 숨을 쉬며 말하는 억양이 나오게 하세요.
4. **기호 및 영문 약어의 한국어 발음화**:
   - 괄호 설명이나 어색한 기호(예: '3.3㎡(평)', 'Fed(연준)', 'CAPEX(설비투자)')를 쓰지 말고, 사람이 입으로 소리 내어 말하는 그대로('평당', '미국 연준', '설비투자', '에이치비엠', '디에스알') 자연스럽게 풀어서 적으세요.
5. **내용과 분량**:
   - 이 테마에 속한 아래 **{len(theme_news)}개 뉴스를 하나도 빠짐없이 모두 대화 속에서 다루되**, 짧은 호흡의 티키타카로 **이 파트에서만 22~30턴 이상(글자 수 약 3,500자)**이 되도록 풍성하게 구성하세요.

[이 테마에서 다룰 뉴스 데이터]
{news_detail_text}

[출력 JSON 스키마 (반드시 유효한 JSON 객체만 출력)]
{{
  "dialogue": [
    {{
      "speaker": "{q_host['name']} 또는 {e_host['name']}",
      "theme_id": "{theme.get('id', 'theme_1')}",
      "text": "실제 사람이 말하듯 추임새와 호흡이 살아있는 자연스러운 구어체 대사"
    }}
  ]
}}
"""


def compile_notebooklm_markdown(briefing: Dict[str, Any], date_str: str, weekday_ko: str) -> str:
    lines = [
        f"# [{date_str} ({weekday_ko})] 모닝 경제·경영 20대 뉴스 심층 해설 노트",
        "",
        f"## 📌 오늘의 핵심 요약: {briefing.get('episode_title', '')}",
        briefing.get("executive_summary", ""),
        "",
        "---",
        "## 📚 파트 1. 테마별 20대 주요 경제/경영 뉴스 & 초보자 눈높이 해설",
        "",
    ]
    themes_map = {t["id"]: t for t in briefing.get("themes", [])}
    news_by_theme: Dict[str, List[Dict[str, Any]]] = {}
    for item in briefing.get("news_items", []):
        news_by_theme.setdefault(item.get("theme_id", "theme_1"), []).append(item)

    for tid, theme in themes_map.items():
        lines.append(f"### {theme.get('title', tid)}")
        lines.append(f"> {theme.get('summary', '')}\n")
        for item in news_by_theme.get(tid, []):
            qna = item.get("beginner_qna", {})
            lines.extend([
                f"#### 뉴스 #{item.get('id')}. {item.get('title')} ({item.get('source')})",
                f"- 요약: {item.get('summary')}",
                f"- 경제·경영적 의미: {item.get('economic_meaning')}",
                f"- 초보자 질문: {qna.get('question', '')}",
                f"- 쉬운 비유 해설: {qna.get('answer', '')}\n",
            ])

    lines.append("---\n## 🎙️ 파트 2. 2인 팟캐스트 대화 대본\n")
    for turn in briefing.get("dialogue", []):
        lines.append(f"**{turn.get('speaker')}**: {turn.get('text')}\n")
    return "\n".join(lines)


def build_fallback_colloquial_dialogue(
    themes: List[Dict[str, Any]], news_items: List[Dict[str, Any]], weekday_ko: str
) -> List[Dict[str, str]]:
    q_name = HOST_PERSONAS["questioner"]["name"]
    e_name = HOST_PERSONAS["explainer"]["name"]
    dialogue: List[Dict[str, str]] = [
        {
            "speaker": q_name,
            "theme_id": "opening",
            "text": f"안녕하세요 여러분! 상쾌한 {weekday_ko}요일 아침 7시 30분입니다. 경제 뉴스만 보면 외계어 같아서 한숨부터 쉬던 경제 입문자 지민이에요! 현우 선배님, 지난 이틀 동안에도 우리 지갑이랑 회사 경영에 직결되는 뉴스들이 엄청 쏟아졌더라고요?",
        },
        {
            "speaker": e_name,
            "theme_id": "opening",
            "text": "하하, 맞아요 지민님! 출근길에 함께해 주시는 청취자분들도 반갑습니다. 오늘도 지난 이틀 동안 나온 뉴스 중에서 진짜 꼭 알아야 할 스무 개만 딱 골라서 네 가지 테마로 묶어 왔거든요. 어려운 용어는 오늘도 제가 커피 한 잔 마시면서 수다 떨듯이 아주 쉽게 비유로 풀어드릴게요!",
        },
    ]
    for theme in themes:
        tid = theme.get("id", "theme_1")
        dialogue.append({
            "speaker": q_name,
            "theme_id": tid,
            "text": f"좋아요! 그럼 바로 {theme.get('title')} 이야기부터 해볼까요? 선배님, 이번 파트에서 제일 중요한 핵심 흐름이 뭔가요?",
        })
        dialogue.append({
            "speaker": e_name,
            "theme_id": tid,
            "text": f"음... 쉽게 말해서 이런 흐름이에요. {theme.get('summary')} 여기에 연결된 뉴스들을 하나씩 같이 볼까요?",
        })
        for n in [item for item in news_items if item.get("theme_id") == tid]:
            qna = n.get("beginner_qna", {})
            dialogue.extend([
                {
                    "speaker": q_name,
                    "theme_id": tid,
                    "text": f"어, 선배님! {n.get('id')}번 뉴스를 보니까 '{n.get('title')}'라는 소식이 있거든요? 솔직히 제목만 봐서는 감이 잘 안 오는데... {qna.get('question', '이게 왜 중요한 건가요?')}",
                },
                {
                    "speaker": e_name,
                    "theme_id": tid,
                    "text": f"아, 그거 진짜 많이들 헷갈려 하시는 부분이에요! {qna.get('answer', '')}",
                },
                {
                    "speaker": q_name,
                    "theme_id": tid,
                    "text": "오... 그렇게 비유해 주시니까 진짜 단번에 이해가 되네요! 그러면 이게 실제로 우리 같은 직장인 지갑이나 회사 경영에는 어떤 영향을 주는 건가요?",
                },
                {
                    "speaker": e_name,
                    "theme_id": tid,
                    "text": f"그니까요, 바로 그 뒷배경을 읽는 게 핵심이거든요! {n.get('economic_meaning')} 그래서 앞으로 뉴스에서 {', '.join(n.get('key_terms', ['핵심지표']))} 같은 단어가 나오면 오늘 나눈 이야기를 떠올리시면 됩니다.",
                },
            ])
    return dialogue


def generate_briefing_with_gemini(
    articles: List[Dict[str, Any]], now_kst: datetime | None = None
) -> Dict[str, Any]:
    if now_kst is None:
        now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y-%m-%d")
    weekday_ko = ["월", "화", "수", "목", "금", "토", "일"][now_kst.weekday()]

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1beta"})
    curation_prompt = build_curation_prompt(articles, date_str, weekday_ko)

    candidate_models = discover_text_models(client)
    briefing = None
    active_model = candidate_models[0]

    for model_name in candidate_models:
        try:
            logger.info(f"[Gemini Stage 1] {model_name} 모델로 20대 뉴스 선별 및 해설 생성 중...")
            response = client.models.generate_content(
                model=model_name,
                contents=curation_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    temperature=0.35,
                ),
            )
            briefing = json.loads(clean_json_response(response.text))
            active_model = model_name
            logger.info(f"[Gemini Stage 1] {model_name} 호출 성공!")
            break
        except Exception as e:
            logger.warning(f"[Gemini Stage 1] {model_name} 호출 실패: {e}")

    if not briefing or not briefing.get("news_items"):
        raise RuntimeError("모든 Gemini 모델 호출에 실패했습니다.")

    themes = briefing.get("themes", [])
    news_items = briefing.get("news_items", [])
    full_dialogue: List[Dict[str, Any]] = []

    for idx, theme in enumerate(themes):
        tid = theme.get("id", f"theme_{idx+1}")
        theme_news = [n for n in news_items if n.get("theme_id") == tid]
        if not theme_news:
            continue
        theme_prompt = build_theme_dialogue_prompt(
            theme=theme,
            theme_news=theme_news,
            theme_index=idx,
            total_themes=len(themes),
            date_str=date_str,
            weekday_ko=weekday_ko,
        )
        try:
            logger.info(f"[Gemini Stage 2 - 파트 {idx+1}/{len(themes)}] '{theme.get('title')}' 초구어체 2인 대본 생성 중 ({active_model})...")
            resp_part = client.models.generate_content(
                model=active_model,
                contents=theme_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=16384,
                    temperature=0.65,
                ),
            )
            part_json = json.loads(clean_json_response(resp_part.text))
            part_turns = part_json.get("dialogue", [])
            full_dialogue.extend(part_turns)
            logger.info(f"   -> 파트 {idx+1} 대본 {len(part_turns)}턴 생성 완료 (누적 {len(full_dialogue)}턴)")
        except Exception as e:
            logger.warning(f"[Gemini Stage 2] 파트 {idx+1} 오류(입말 폴백 적용): {e}")
            full_dialogue.extend(build_fallback_colloquial_dialogue([theme], theme_news, weekday_ko))

    briefing["dialogue"] = full_dialogue or build_fallback_colloquial_dialogue(themes, news_items, weekday_ko)
    briefing["date"] = date_str
    briefing["weekday"] = weekday_ko
    briefing["generated_at"] = now_kst.strftime("%Y-%m-%d %H:%M KST")

    md_content = compile_notebooklm_markdown(briefing, date_str, weekday_ko)
    md_path = OUTPUT_DIR / f"notebook_source_{date_str}.md"
    md_path.write_text(md_content, encoding="utf-8")
    briefing["notebook_source_path"] = str(md_path)
    return briefing
