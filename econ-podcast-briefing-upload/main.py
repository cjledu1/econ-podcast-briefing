#!/usr/bin/env python3
"""
월·수·금 아침 7시 30분 정기 경제·경영 2인 팟캐스트 브리핑 메인 파이프라인.
실행 예시:
  python main.py                  # 전체 파이프라인 실행 (RSS 수집 -> Gemini 해설/대본 -> NotebookLM/TTS 오디오 -> 웹 발행 -> 카톡 전송)
  python main.py --force-fallback # NotebookLM 생략하고 즉시 멀티보이스 TTS로 오디오 생성
  python main.py --skip-kakao     # 카카오톡 발송만 생략하고 웹/오디오 빌드 테스트
"""
import argparse
import asyncio
import logging
import sys
from datetime import datetime

from src.config import KST
from src.news_collector import fetch_rss_articles
from src.podcast_writer import generate_briefing_with_gemini
from src.audio_generator import produce_podcast_audio
from src.web_publisher import publish_episode_to_web
from src.kakao_notifier import send_kakao_briefing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("morning-briefing")


async def run_pipeline(force_fallback: bool = False, skip_kakao: bool = False) -> int:
    now_kst = datetime.now(KST)
    logger.info("=" * 72)
    logger.info(
        f"🌅 [{now_kst.strftime('%Y-%m-%d %H:%M KST')}] 경제·경영 2인 팟캐스트 브리핑 파이프라인 시작"
    )
    logger.info("=" * 72)

    # Step 1. 지난 2일간의 주요 경제/경영 뉴스 수집
    logger.info("[Step 1/5] 지난 2일간 국내외 경제·경영·금융·부동산 뉴스 수집 중...")
    articles = fetch_rss_articles()

    # Step 2. Gemini API로 20대 뉴스 엄선, 초보자 눈높이 의미 해설, 용어 사전, 2인 대본 작성
    logger.info("[Step 2/5] 주요 뉴스 20선 발췌, 초보자 Q&A 해설 및 2인 팟캐스트 대본 작성 중...")
    briefing = generate_briefing_with_gemini(articles, now_kst=now_kst)

    # Step 3. 하이브리드 오디오 생성 (NotebookLM 우선 -> 세션 만료 시 멀티보이스 TTS 자동 전환)
    logger.info("[Step 3/5] 2인 팟캐스트 오디오 생성 중 (NotebookLM / Fallback 멀티보이스)...")
    audio_meta = await produce_podcast_audio(briefing, force_fallback=force_fallback)
    logger.info(
        f"   -> 오디오 생성 완료: {audio_meta['audio_path']} (엔진: {audio_meta['engine_used']})"
    )

    # Step 4. GitHub Pages 모바일 웹 플레이어 및 아카이브 빌드
    logger.info("[Step 4/5] 모바일 오디오 웹 플레이어 및 용어 사전 페이지 생성 중...")
    web_url = publish_episode_to_web(briefing, audio_meta)
    logger.info(f"   -> 웹 플레이어 주소: {web_url}")

    # Step 5. 카카오톡 '나에게 보내기' 발송
    if skip_kakao:
        logger.info("[Step 5/5] --skip-kakao 옵션으로 카카오톡 전송을 건너뜁니다.")
    else:
        logger.info("[Step 5/5] 카카오톡 '나에게 보내기'로 오늘의 브리핑 발송 중...")
        send_kakao_briefing(briefing, audio_meta, web_url)

    logger.info("=" * 72)
    logger.info("✅ 모든 브리핑 파이프라인이 성공적으로 완료되었습니다!")
    logger.info("=" * 72)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="월·수·금 07:30 경제·경영 2인 팟캐스트 오디오 브리핑 자동화 파이프라인"
    )
    parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="NotebookLM 브라우저 자동화를 건너뛰고 즉시 2인 멀티보이스 TTS로 오디오를 생성합니다.",
    )
    parser.add_argument(
        "--skip-kakao",
        action="store_true",
        help="카카오톡 메시지 발송 단계를 건너뜁니다.",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run_pipeline(force_fallback=args.force_fallback, skip_kakao=args.skip_kakao)))


if __name__ == "__main__":
    main()
