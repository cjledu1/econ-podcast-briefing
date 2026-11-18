import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
EPISODES_DIR = DOCS_DIR / "episodes"
AUDIO_DIR = DOCS_DIR / "audio"
OUTPUT_DIR = BASE_DIR / "output"

for directory in [DOCS_DIR, EPISODES_DIR, AUDIO_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

KST = timezone(timedelta(hours=9))

# API Keys & Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "").strip()
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "").strip()
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "").strip()
PUBLIC_WEB_URL = os.getenv(
    "PUBLIC_WEB_URL", "https://cjledu1.github.io/econ-podcast-briefing"
).rstrip("/")

GOOGLE_STORAGE_STATE_B64 = os.getenv("GOOGLE_STORAGE_STATE_B64", "").strip()
GOOGLE_STORAGE_STATE_PATH = os.getenv(
    "GOOGLE_STORAGE_STATE_PATH", str(BASE_DIR / "storage_state.json")
)

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()

# ==========================================================
# 뉴스 수집 소스 설정 (국내 경제/기업, 글로벌 거시/빅테크, 금리/환율/부동산)
# ==========================================================
RSS_FEEDS = [
    # 1. 국내 경제 / 산업 / 기업 경영
    {
        "name": "매일경제 경제",
        "category": "국내 경제/기업",
        "url": "https://www.mk.co.kr/rss/30100041/",
        "lang": "ko",
    },
    {
        "name": "매일경제 기업/경영",
        "category": "국내 경제/기업",
        "url": "https://www.mk.co.kr/rss/50100032/",
        "lang": "ko",
    },
    {
        "name": "연합뉴스TV 경제",
        "category": "국내 경제/기업",
        "url": "https://www.yonhapnewstv.co.kr/category/news/economy/feed/",
        "lang": "ko",
    },
    {
        "name": "SBS 뉴스 경제",
        "category": "국내 경제/기업",
        "url": "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02&plink=RSSREADER",
        "lang": "ko",
    },
    {
        "name": "한겨레 경제",
        "category": "국내 경제/기업",
        "url": "https://www.hani.co.kr/rss/economy/",
        "lang": "ko",
    },
    # 2. 금리 / 환율 / 부동산 / 금융시장 지표
    {
        "name": "매일경제 증권/금융",
        "category": "금융/금리/환율",
        "url": "https://www.mk.co.kr/rss/50200011/",
        "lang": "ko",
    },
    {
        "name": "매일경제 부동산",
        "category": "부동산/재테크",
        "url": "https://www.mk.co.kr/rss/50300009/",
        "lang": "ko",
    },
    # 3. 글로벌 거시경제 & 미국 증시 / 빅테크
    {
        "name": "매일경제 국제경제",
        "category": "글로벌 거시/빅테크",
        "url": "https://www.mk.co.kr/rss/30300018/",
        "lang": "ko",
    },
    {
        "name": "CNBC Top Economy & Tech",
        "category": "글로벌 거시/빅테크",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "lang": "en",
    },
    {
        "name": "CNBC Finance & Markets",
        "category": "글로벌 거시/빅테크",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "lang": "en",
    },
]

# ==========================================================
# 2인 팟캐스트 페르소나 및 프롬프트 설정
# ==========================================================
HOST_PERSONAS = {
    "questioner": {
        "name": "지민",
        "role": "경제·경영 입문자 (질문자)",
        "voice_edge": "ko-KR-SunHiNeural",
        "voice_gemini": "Kore",
        "description": (
            "경제와 경영 뉴스가 낯선 평범한 직장인. 뉴스에 나오는 전문 용어나 숫자를 보면 "
            "'잠깐만요, 이게 정확히 무슨 뜻이에요?', '금리가 동결되면 내 대출이자나 월급, 우리 회사에는 어떤 영향이 있는 건가요?'처럼 "
            "청취자가 속으로 궁금해할 법한 핵심 질문을 솔직하고 활기차게 던지는 역할."
        ),
    },
    "explainer": {
        "name": "현우",
        "role": "친절한 경제·경영 멘토 (해설자)",
        "voice_edge": "ko-KR-InJoonNeural",
        "voice_gemini": "Puck",
        "description": (
            "어려운 거시경제 흐름과 기업 경영 전략을 일상 속 비유(카페 창업, 가계부, 장보기, 보일러 온도 조절 등)로 "
            "누구나 단번에 이해할 수 있게 설명해주는 따뜻한 멘토. 단순 사실 전달을 넘어 '왜 이 뉴스가 지금 중요한지', "
            "'앞으로 어떤 연쇄 작용(나비효과)이 일어날지' 맥락을 짚어주는 역할."
        ),
    },
}

NOTEBOOKLM_CUSTOM_PROMPT = """반드시 한국어(Korean)로 진행해 주세요.
이 오디오 브리핑의 목적은 경제/경영 지식이 전혀 없는 청취자가 지난 이틀간의 주요 경제/경영 뉴스 20개의 핵심 흐름과 의미를 완벽히 이해하도록 돕는 것입니다.

[진행 방식 및 역할 설정]
1. 두 명의 진행자 중 한 명(질문자)은 경제 초보자 입장에서 뉴스가 왜 중요한지, 어려운 경제/경영 용어가 무슨 뜻인지 적극적으로 질문합니다.
2. 다른 한 명(해설자)은 일상적인 비유와 쉬운 언어로 용어를 풀이해주고, 이 뉴스가 개인의 자산(월급, 금리, 환율, 부동산)과 기업의 경영 환경에 어떤 실질적 의미를 갖는지 친절하게 설명합니다.
3. 제공된 소스의 4~5개 핵심 테마를 따라 20개 뉴스를 전체적으로 짚어주되, 가장 파급력이 큰 핵심 5~7개 이슈는 충분한 시간을 들여 깊이 있게 문답을 주고받으며 약 20분 분량으로 풍성하게 대화해 주세요."""


def get_lookback_hours(now_kst: datetime | None = None) -> int:
    """월요일 아침(weekday==0)에는 금/토/일 흐름을 놓치지 않도록 60시간, 수/금요일에는 48시간을 조회합니다."""
    if now_kst is None:
        now_kst = datetime.now(KST)
    if now_kst.weekday() == 0:  # 월요일
        return 60
    return 48
