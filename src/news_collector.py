import re
import html
import logging
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any

import feedparser
import requests
from bs4 import BeautifulSoup

from src.config import (
    RSS_FEEDS,
    KST,
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    get_lookback_hours,
)

logger = logging.getLogger(__name__)


def clean_html_text(raw_html: str) -> str:
    """HTML 태그 및 불필요한 공백을 제거합니다."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_entry_date(entry: Any, now_kst: datetime) -> datetime:
    """RSS 엔트리의 발행 시각을 파싱하여 KST datetime으로 반환합니다."""
    for field in ("published", "updated", "created"):
        val = getattr(entry, field, None) or entry.get(field)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=KST)
                return dt.astimezone(KST)
            except Exception:
                pass

    for parsed_field in ("published_parsed", "updated_parsed"):
        st = getattr(entry, parsed_field, None) or entry.get(parsed_field)
        if st:
            try:
                dt = datetime(*st[:6], tzinfo=KST)
                return dt
            except Exception:
                pass

    return now_kst


def normalize_title_for_dedup(title: str) -> str:
    """중복 기사 제거를 위해 특수문자와 공백을 제거한 앞 22글자 키를 생성합니다."""
    cleaned = re.sub(r"\[.*?\]|\(.*?\)", "", title)
    cleaned = re.sub(r"[^가-힣a-zA-Z0-9]", "", cleaned).lower()
    return cleaned[:22]


def fetch_rss_articles(lookback_hours: int | None = None) -> List[Dict[str, Any]]:
    """설정된 국내외 경제/경영/금융/부동산 RSS 피드에서 지난 2일간의 뉴스를 수집합니다."""
    now_kst = datetime.now(KST)
    if lookback_hours is None:
        lookback_hours = get_lookback_hours(now_kst)
    cutoff_time = now_kst - timedelta(hours=lookback_hours)

    collected: List[Dict[str, Any]] = []
    seen_keys = set()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
    }

    for feed_info in RSS_FEEDS:
        feed_name = feed_info["name"]
        feed_url = feed_info["url"]
        category = feed_info["category"]
        lang = feed_info.get("lang", "ko")

        try:
            resp = requests.get(feed_url, headers=headers, timeout=12)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)

            count_from_feed = 0
            for entry in parsed.entries:
                title = clean_html_text(entry.get("title", ""))
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                pub_dt = parse_entry_date(entry, now_kst)
                if pub_dt < cutoff_time:
                    continue

                dedup_key = normalize_title_for_dedup(title)
                if not dedup_key or dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)

                summary = clean_html_text(
                    entry.get("summary", "") or entry.get("description", "")
                )
                if len(summary) > 380:
                    summary = summary[:380] + "..."

                collected.append(
                    {
                        "title": title,
                        "url": link,
                        "source": feed_name,
                        "category": category,
                        "lang": lang,
                        "published_at": pub_dt.strftime("%Y-%m-%d %H:%M"),
                        "summary": summary,
                    }
                )
                count_from_feed += 1
                if count_from_feed >= 25:
                    break

            logger.info(f"[RSS] {feed_name}: {count_from_feed}개 기사 수집 완료")
        except Exception as e:
            logger.warning(f"[RSS] {feed_name} 수집 중 오류 발생 (무시하고 계속): {e}")

    # 선택사항: 네이버 뉴스 검색 API가 설정되어 있다면 키워드 보강 수집
    if NAVER_CLIENT_ID and NAVER_CLIENT_SECRET:
        naver_keywords = ["한국은행 기준금리 환율", "반도체 수출 실적 경영", "미국 연준 증시 빅테크", "부동산 대출 금리"]
        for kw in naver_keywords:
            try:
                r = requests.get(
                    "https://openapi.naver.com/v1/search/news.json",
                    params={"query": kw, "display": 10, "sort": "sim"},
                    headers={
                        "X-Naver-Client-Id": NAVER_CLIENT_ID,
                        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        title = clean_html_text(item.get("title", ""))
                        dedup_key = normalize_title_for_dedup(title)
                        if dedup_key and dedup_key not in seen_keys:
                            seen_keys.add(dedup_key)
                            collected.append(
                                {
                                    "title": title,
                                    "url": item.get("originallink") or item.get("link"),
                                    "source": "네이버 경제뉴스",
                                    "category": "국내 경제/기업",
                                    "lang": "ko",
                                    "published_at": now_kst.strftime("%Y-%m-%d %H:%M"),
                                    "summary": clean_html_text(item.get("description", "")),
                                }
                            )
            except Exception as e:
                logger.warning(f"[Naver API] '{kw}' 검색 중 오류: {e}")

    logger.info(f"총 {len(collected)}개의 후보 경제/경영 뉴스 수집 완료 (기준: 최근 {lookback_hours}시간)")
    return collected
