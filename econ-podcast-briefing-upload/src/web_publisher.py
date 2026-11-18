import json
import logging
from pathlib import Path
from typing import Dict, Any, List

from src.config import DOCS_DIR, EPISODES_DIR, PUBLIC_WEB_URL

logger = logging.getLogger(__name__)


def publish_episode_to_web(briefing: Dict[str, Any], audio_meta: Dict[str, Any]) -> str:
    """
    브리핑 JSON 데이터와 오디오 메타데이터를 GitHub Pages용 정적 폴더(docs/)에 발행하고
    모바일 최적화 웹 플레이어(docs/index.html)를 갱신합니다.
    반환값: 발행된 에피소드 웹 URL
    """
    date_str = briefing.get("date", "latest")
    episode_data = {
        **briefing,
        "audio": {
            "filename": audio_meta.get("audio_filename", f"briefing-{date_str}.mp3"),
            "url": f"audio/{audio_meta.get('audio_filename', f'briefing-{date_str}.mp3')}",
            "engine_used": audio_meta.get("engine_used", "FALLBACK_TTS"),
            "session_expired": audio_meta.get("session_expired", False),
        },
    }

    # 1. 개별 에피소드 JSON 저장
    ep_json_path = EPISODES_DIR / f"{date_str}.json"
    ep_json_path.write_text(
        json.dumps(episode_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 최신 에피소드를 latest.json으로도 복사
    latest_json_path = EPISODES_DIR / "latest.json"
    latest_json_path.write_text(
        json.dumps(episode_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 2. 전체 에피소드 목록 인덱스 갱신
    index_path = EPISODES_DIR / "index.json"
    episodes_list: List[Dict[str, str]] = []
    if index_path.exists():
        try:
            episodes_list = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            episodes_list = []

    episodes_list = [ep for ep in episodes_list if ep.get("date") != date_str]
    episodes_list.insert(
        0,
        {
            "date": date_str,
            "weekday": briefing.get("weekday", ""),
            "title": briefing.get("episode_title", ""),
            "audio_url": episode_data["audio"]["url"],
        },
    )
    episodes_list = episodes_list[:30]  # 최근 30회분 유지
    index_path.write_text(
        json.dumps(episodes_list, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3. 모바일 웹 플레이어 HTML 생성 (초기 데이터 인라인 내장으로 로딩 속도 극대화)
    html_content = build_mobile_player_html(episode_data, episodes_list)
    index_html_path = DOCS_DIR / "index.html"
    index_html_path.write_text(html_content, encoding="utf-8")

    # GitHub Pages에서 Jekyll 처리를 건너뛰도록 .nojekyll 생성
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    episode_web_url = f"{PUBLIC_WEB_URL}/?ep={date_str}"
    logger.info(f"[Web Publisher] 모바일 오디오 웹 플레이어 생성 완료: {index_html_path}")
    return episode_web_url


def build_mobile_player_html(
    initial_episode: Dict[str, Any], episodes_index: List[Dict[str, str]]
) -> str:
    """출근길 스마트폰에서도 즉시 열리고 오디오 재생·해설 열람이 가능한 반응형 웹앱 HTML."""
    inline_ep_json = json.dumps(initial_episode, ensure_ascii=False)
    inline_idx_json = json.dumps(episodes_index, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0" />
  <title>모닝 경제·경영 2인 팟캐스트 브리핑 | 07:30 AM</title>
  <meta name="description" content="월·수·금 아침 7시 30분, 지난 이틀간의 주요 경제·경영 뉴스 20개를 초보자 눈높이 문답과 용어 해설로 풀어주는 20분 오디오 브리핑" />
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-page: hsl(40, 25%, 97%);
      --bg-surface: hsl(0, 0%, 100%);
      --bg-subtle: hsl(38, 22%, 93%);
      --bg-highlight: hsl(160, 35%, 95%);
      --bg-qna: hsl(210, 33%, 96%);
      --text-primary: hsl(215, 28%, 14%);
      --text-secondary: hsl(215, 16%, 36%);
      --text-muted: hsl(215, 12%, 52%);
      --border-soft: hsl(35, 18%, 87%);
      --border-strong: hsl(215, 20%, 78%);
      --accent-primary: hsl(162, 72%, 24%);
      --accent-primary-hover: hsl(162, 72%, 19%);
      --accent-warm: hsl(24, 85%, 44%);
      --accent-blue: hsl(212, 78%, 38%);
      --shadow-card: 0 2px 10px rgba(15, 23, 42, 0.04);
      --shadow-player: 0 -4px 20px rgba(15, 23, 42, 0.08);
      --radius-lg: 14px;
      --radius-md: 10px;
      --radius-sm: 6px;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: 'Noto Sans KR', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg-page);
      color: var(--text-primary);
      line-height: 1.65;
      letter-spacing: -0.015em;
      padding-bottom: 148px;
      -webkit-font-smoothing: antialiased;
    }}

    .app-container {{
      max-width: 760px;
      margin: 0 auto;
      padding: 20px 16px 40px;
    }}

    /* Header */
    .masthead {{
      border-bottom: 2px solid var(--text-primary);
      padding-bottom: 16px;
      margin-bottom: 18px;
    }}

    .masthead-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }}

    .brand-tag {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.76rem;
      font-weight: 600;
      color: var(--accent-primary);
      background: var(--bg-highlight);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
    }}

    .episode-selector {{
      font-family: inherit;
      font-size: 0.85rem;
      padding: 5px 10px;
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-sm);
      background: var(--bg-surface);
      color: var(--text-primary);
      cursor: pointer;
    }}

    .masthead h1 {{
      font-size: 1.38rem;
      font-weight: 700;
      line-height: 1.35;
      margin-bottom: 10px;
      color: var(--text-primary);
    }}

    .host-strip {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      font-size: 0.84rem;
      color: var(--text-secondary);
    }}

    .host-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--bg-subtle);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
    }}

    /* Executive Summary Box */
    .exec-summary-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-soft);
      border-radius: var(--radius-lg);
      padding: 16px 18px;
      margin-bottom: 20px;
      box-shadow: var(--shadow-card);
    }}

    .exec-summary-title {{
      font-size: 0.85rem;
      font-weight: 700;
      color: var(--accent-primary);
      text-transform: uppercase;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .exec-summary-text {{
      font-size: 0.93rem;
      color: var(--text-primary);
      white-space: pre-line;
      line-height: 1.65;
    }}

    /* Navigation Tabs */
    .nav-tabs {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
      background: var(--bg-subtle);
      padding: 5px;
      border-radius: var(--radius-md);
      margin-bottom: 20px;
    }}

    .tab-btn {{
      border: none;
      background: transparent;
      padding: 10px 8px;
      font-family: inherit;
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--text-secondary);
      border-radius: var(--radius-sm);
      cursor: pointer;
      transition: all 0.18s ease;
    }}

    .tab-btn.active {{
      background: var(--bg-surface);
      color: var(--text-primary);
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
    }}

    /* Theme Filter Pills */
    .filter-bar {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 10px;
      margin-bottom: 14px;
      scrollbar-width: none;
    }}

    .filter-bar::-webkit-scrollbar {{
      display: none;
    }}

    .filter-chip {{
      white-space: nowrap;
      border: 1px solid var(--border-soft);
      background: var(--bg-surface);
      color: var(--text-secondary);
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 0.82rem;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.15s ease;
    }}

    .filter-chip.active {{
      background: var(--text-primary);
      color: var(--bg-surface);
      border-color: var(--text-primary);
    }}

    /* Theme Section */
    .theme-section {{
      margin-bottom: 28px;
    }}

    .theme-header {{
      background: var(--bg-subtle);
      padding: 12px 16px;
      border-radius: var(--radius-md);
      margin-bottom: 12px;
    }}

    .theme-header h2 {{
      font-size: 1.05rem;
      font-weight: 700;
      margin-bottom: 4px;
      color: var(--text-primary);
    }}

    .theme-header p {{
      font-size: 0.86rem;
      color: var(--text-secondary);
    }}

    /* News Card */
    .news-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-soft);
      border-radius: var(--radius-lg);
      padding: 18px;
      margin-bottom: 14px;
      box-shadow: var(--shadow-card);
      transition: transform 0.15s ease;
    }}

    .news-card.deep-dive {{
      border-color: hsl(162, 45%, 65%);
    }}

    .news-meta {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      flex-wrap: wrap;
    }}

    .news-badges {{
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }}

    .num-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-secondary);
      background: var(--bg-subtle);
      padding: 2px 8px;
      border-radius: var(--radius-sm);
    }}

    .cat-badge {{
      font-size: 0.76rem;
      font-weight: 600;
      color: var(--accent-blue);
      background: var(--bg-qna);
      padding: 2px 8px;
      border-radius: var(--radius-sm);
    }}

    .deep-badge {{
      font-size: 0.76rem;
      font-weight: 700;
      color: var(--accent-warm);
      background: hsl(24, 90%, 94%);
      padding: 2px 8px;
      border-radius: var(--radius-sm);
    }}

    .news-title {{
      font-size: 1.06rem;
      font-weight: 700;
      line-height: 1.42;
      margin-bottom: 10px;
      color: var(--text-primary);
    }}

    .news-summary {{
      font-size: 0.92rem;
      color: var(--text-secondary);
      margin-bottom: 12px;
    }}

    .meaning-box {{
      background: var(--bg-highlight);
      border-radius: var(--radius-md);
      padding: 12px 14px;
      margin-bottom: 12px;
    }}

    .meaning-label {{
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--accent-primary);
      margin-bottom: 4px;
    }}

    .meaning-text {{
      font-size: 0.9rem;
      color: var(--text-primary);
    }}

    .qna-box {{
      background: var(--bg-qna);
      border-radius: var(--radius-md);
      padding: 12px 14px;
      margin-bottom: 10px;
    }}

    .qna-q {{
      font-size: 0.88rem;
      font-weight: 700;
      color: var(--accent-blue);
      margin-bottom: 6px;
    }}

    .qna-a {{
      font-size: 0.89rem;
      color: var(--text-primary);
    }}

    .news-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      padding-top: 8px;
      border-top: 1px dashed var(--border-soft);
      font-size: 0.8rem;
    }}

    .term-tags {{
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }}

    .term-tag {{
      background: var(--bg-subtle);
      color: var(--text-secondary);
      padding: 2px 8px;
      border-radius: var(--radius-sm);
    }}

    .source-link {{
      color: var(--accent-primary);
      text-decoration: none;
      font-weight: 600;
    }}

    .source-link:hover {{
      text-decoration: underline;
    }}

    /* Glossary Grid */
    .glossary-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-soft);
      border-radius: var(--radius-lg);
      padding: 16px 18px;
      margin-bottom: 12px;
      box-shadow: var(--shadow-card);
    }}

    .glossary-term {{
      font-size: 1.04rem;
      font-weight: 700;
      color: var(--accent-primary);
      margin-bottom: 6px;
    }}

    .glossary-def {{
      font-size: 0.92rem;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 8px;
    }}

    .glossary-analogy {{
      font-size: 0.89rem;
      color: var(--text-secondary);
      background: var(--bg-subtle);
      padding: 10px 12px;
      border-radius: var(--radius-sm);
    }}

    /* Dialogue Transcript */
    .dialogue-turn {{
      background: var(--bg-surface);
      border: 1px solid var(--border-soft);
      border-radius: var(--radius-lg);
      padding: 14px 16px;
      margin-bottom: 10px;
    }}

    .dialogue-turn.speaker-q {{
      background: var(--bg-qna);
    }}

    .speaker-name {{
      font-size: 0.82rem;
      font-weight: 700;
      margin-bottom: 4px;
      display: inline-block;
    }}

    .speaker-q .speaker-name {{
      color: var(--accent-blue);
    }}

    .speaker-e .speaker-name {{
      color: var(--accent-primary);
    }}

    .dialogue-text {{
      font-size: 0.93rem;
      color: var(--text-primary);
    }}

    /* Sticky Bottom Audio Player */
    .sticky-player {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: var(--bg-surface);
      border-top: 1px solid var(--border-strong);
      box-shadow: var(--shadow-player);
      padding: 12px 16px 16px;
      z-index: 100;
    }}

    .player-inner {{
      max-width: 760px;
      margin: 0 auto;
    }}

    .player-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      gap: 8px;
    }}

    .now-playing-label {{
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--text-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .time-readout {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      color: var(--text-secondary);
      flex-shrink: 0;
    }}

    .scrubber {{
      width: 100%;
      accent-color: var(--accent-primary);
      cursor: pointer;
      height: 6px;
      margin-bottom: 10px;
    }}

    .player-controls {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}

    .ctrl-group {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .btn-play {{
      background: var(--accent-primary);
      color: #fff;
      border: none;
      padding: 9px 18px;
      border-radius: 999px;
      font-family: inherit;
      font-size: 0.88rem;
      font-weight: 700;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}

    .btn-play:hover {{
      background: var(--accent-primary-hover);
    }}

    .btn-skip, .btn-speed {{
      background: var(--bg-subtle);
      color: var(--text-primary);
      border: 1px solid var(--border-soft);
      padding: 7px 11px;
      border-radius: var(--radius-sm);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      font-weight: 600;
      cursor: pointer;
    }}

    .hidden {{
      display: none !important;
    }}
  </style>
</head>
<body>
  <main class="app-container">
    <header class="masthead">
      <div class="masthead-top">
        <span class="brand-tag" id="engine-badge">MON·WED·FRI 07:30 BRIEFING</span>
        <select id="episode-select" class="episode-selector" aria-label="지난 브리핑 선택"></select>
      </div>
      <h1 id="ep-title">모닝 경제·경영 2인 팟캐스트 브리핑</h1>
      <div class="host-strip">
        <span class="host-badge">🙋 질문자 <strong>지민</strong> (경제 입문자)</span>
        <span class="host-badge">🎙️ 해설자 <strong>현우</strong> (경제·경영 멘토)</span>
      </div>
    </header>

    <section class="exec-summary-card" aria-label="오늘의 핵심 3줄 요약">
      <div class="exec-summary-title">
        <span>📌 오늘 아침 핵심 맥락 요약</span>
        <span id="ep-date-label"></span>
      </div>
      <p class="exec-summary-text" id="ep-summary"></p>
    </section>

    <nav class="nav-tabs" aria-label="콘텐츠 보기 전환">
      <button type="button" class="tab-btn active" id="tab-btn-news" data-tab="news">📰 20대 뉴스 & 의미</button>
      <button type="button" class="tab-btn" id="tab-btn-glossary" data-tab="glossary">📖 용어 사전 (<span id="glossary-count">0</span>)</button>
      <button type="button" class="tab-btn" id="tab-btn-script" data-tab="script">💬 2인 대화 대본</button>
    </nav>

    <!-- 탭 1: 20대 뉴스 & 의미 해설 -->
    <section id="view-news">
      <div class="filter-bar" id="filter-bar"></div>
      <div id="news-list-container"></div>
    </section>

    <!-- 탭 2: 경제/경영 용어 사전 -->
    <section id="view-glossary" class="hidden">
      <div id="glossary-list-container"></div>
    </section>

    <!-- 탭 3: 2인 팟캐스트 대본 -->
    <section id="view-script" class="hidden">
      <div id="script-list-container"></div>
    </section>
  </main>

  <!-- 하단 고정 오디오 플레이어 -->
  <aside class="sticky-player" aria-label="팟캐스트 오디오 플레이어">
    <div class="player-inner">
      <audio id="podcast-audio" preload="metadata"></audio>
      <div class="player-top">
        <span class="now-playing-label" id="player-status-text">🎧 출근길 2인 경제/경영 팟캐스트 오디오 브리핑</span>
        <span class="time-readout" id="player-time">00:00 / 00:00</span>
      </div>
      <input type="range" id="audio-scrubber" class="scrubber" min="0" max="100" value="0" step="0.1" aria-label="오디오 탐색 바" />
      <div class="player-controls">
        <div class="ctrl-group">
          <button type="button" class="btn-play" id="btn-play-toggle">▶ 브리핑 재생</button>
          <button type="button" class="btn-skip" id="btn-rw-15">-15초</button>
          <button type="button" class="btn-skip" id="btn-ff-15">+15초</button>
        </div>
        <div class="ctrl-group">
          <button type="button" class="btn-speed" id="btn-speed-cycle">1.0x 배속</button>
        </div>
      </div>
    </div>
  </aside>

  <script>
    const INITIAL_EPISODE = {inline_ep_json};
    const EPISODES_INDEX = {inline_idx_json};

    let currentEpisode = INITIAL_EPISODE;
    let activeFilter = 'all';
    const speeds = [1.0, 1.25, 1.5, 1.75];
    let speedIdx = 0;
    let synthSpeaking = false;

    const audioEl = document.getElementById('podcast-audio');
    const playBtn = document.getElementById('btn-play-toggle');
    const scrubber = document.getElementById('audio-scrubber');
    const timeLabel = document.getElementById('player-time');
    const statusText = document.getElementById('player-status-text');

    function formatTime(sec) {{
      if (!sec || isNaN(sec)) return '00:00';
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0');
    }}

    function renderEpisode(ep) {{
      currentEpisode = ep;
      document.getElementById('ep-title').textContent = ep.episode_title || '모닝 경제·경영 2인 팟캐스트';
      document.getElementById('ep-date-label').textContent = ep.generated_at || ep.date || '';
      document.getElementById('ep-summary').textContent = ep.executive_summary || '';
      document.getElementById('glossary-count').textContent = (ep.glossary || []).length;

      const engine = (ep.audio && ep.audio.engine_used) || 'NOTEBOOKLM';
      const badgeEl = document.getElementById('engine-badge');
      badgeEl.textContent = engine.includes('NOTEBOOKLM')
        ? 'NOTEBOOKLM 2인 오디오 브리핑'
        : 'AI 2인 멀티보이스 브리핑';

      if (ep.audio && ep.audio.url) {{
        audioEl.src = ep.audio.url;
      }}

      renderFilters(ep);
      renderNewsList(ep);
      renderGlossary(ep);
      renderDialogue(ep);
    }}

    function renderFilters(ep) {{
      const bar = document.getElementById('filter-bar');
      bar.innerHTML = '';
      const filters = [
        {{ id: 'all', label: '전체 뉴스 (20)' }},
        {{ id: 'deep', label: '★ 심층 해설 이슈' }},
        ...(ep.themes || []).map(t => ({{ id: t.id, label: t.title.replace(/^[0-9]+\\.\\s*/, '') }}))
      ];
      filters.forEach(f => {{
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'filter-chip' + (activeFilter === f.id ? ' active' : '');
        btn.textContent = f.label;
        btn.addEventListener('click', () => {{
          activeFilter = f.id;
          renderFilters(currentEpisode);
          renderNewsList(currentEpisode);
        }});
        bar.appendChild(btn);
      }});
    }}

    function renderNewsList(ep) {{
      const container = document.getElementById('news-list-container');
      container.innerHTML = '';
      const themes = ep.themes || [];
      const items = ep.news_items || [];

      themes.forEach(theme => {{
        if (activeFilter !== 'all' && activeFilter !== 'deep' && activeFilter !== theme.id) return;

        const themeItems = items.filter(item => {{
          if (item.theme_id !== theme.id) return false;
          if (activeFilter === 'deep') return Boolean(item.is_deep_dive);
          return true;
        }});

        if (themeItems.length === 0) return;

        const sec = document.createElement('div');
        sec.className = 'theme-section';
        sec.innerHTML = `
          <div class="theme-header">
            <h2>${{theme.title}}</h2>
            <p>${{theme.summary}}</p>
          </div>
        `;

        themeItems.forEach(item => {{
          const card = document.createElement('article');
          card.className = 'news-card' + (item.is_deep_dive ? ' deep-dive' : '');
          const qna = item.beginner_qna || {{}};
          const termsHtml = (item.key_terms || [])
            .map(t => `<span class="term-tag">#${{t}}</span>`)
            .join('');

          card.innerHTML = `
            <div class="news-meta">
              <div class="news-badges">
                <span class="num-badge">NEWS #${{item.id}}</span>
                <span class="cat-badge">${{item.category || '경제/경영'}}</span>
                ${{item.is_deep_dive ? '<span class="deep-badge">★ 핵심 심층해설</span>' : ''}}
              </div>
              <span style="font-size:0.78rem;color:var(--text-muted)">${{item.source || ''}}</span>
            </div>
            <h3 class="news-title">${{item.title}}</h3>
            <p class="news-summary">${{item.summary}}</p>
            <div class="meaning-box">
              <div class="meaning-label">💡 경제·경영적 의미 (왜 중요할까요?)</div>
              <div class="meaning-text">${{item.economic_meaning}}</div>
            </div>
            ${{qna.question ? `
            <div class="qna-box">
              <div class="qna-q">🙋 지민의 질문: "${{qna.question}}"</div>
              <div class="qna-a">🎙️ 현우의 해설: "${{qna.answer}}"</div>
            </div>` : ''}}
            <div class="news-footer">
              <div class="term-tags">${{termsHtml}}</div>
              <a class="source-link" href="${{item.url || '#'}}" target="_blank" rel="noopener noreferrer">원문 기사 보기 ↗</a>
            </div>
          `;
          sec.appendChild(card);
        }});

        container.appendChild(sec);
      }});
    }}

    function renderGlossary(ep) {{
      const container = document.getElementById('glossary-list-container');
      container.innerHTML = '';
      (ep.glossary || []).forEach(g => {{
        const div = document.createElement('div');
        div.className = 'glossary-card';
        div.innerHTML = `
          <div class="glossary-term">🔹 ${{g.term}}</div>
          <div class="glossary-def">${{g.simple_def}}</div>
          <div class="glossary-analogy">💬 <strong>일상 비유:</strong> ${{g.analogy}}</div>
        `;
        container.appendChild(div);
      }});
    }}

    function renderDialogue(ep) {{
      const container = document.getElementById('script-list-container');
      container.innerHTML = '';
      (ep.dialogue || []).forEach(turn => {{
        const isQ = turn.speaker === '지민';
        const div = document.createElement('div');
        div.className = 'dialogue-turn ' + (isQ ? 'speaker-q' : 'speaker-e');
        div.innerHTML = `
          <span class="speaker-name">${{isQ ? '🙋 지민 (질문자)' : '🎙️ 현우 (경제 멘토)'}}</span>
          <p class="dialogue-text">${{turn.text}}</p>
        `;
        container.appendChild(div);
      }});
    }}

    // 탭 전환
    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.getElementById('view-news').classList.toggle('hidden', tab !== 'news');
        document.getElementById('view-glossary').classList.toggle('hidden', tab !== 'glossary');
        document.getElementById('view-script').classList.toggle('hidden', tab !== 'script');
      }});
    }});

    // 오디오 컨트롤
    playBtn.addEventListener('click', () => {{
      if (audioEl.paused) {{
        audioEl.play().then(() => {{
          playBtn.textContent = '⏸ 일시정지';
        }}).catch(() => {{
          // 오디오 파일 로드 전이거나 브라우저 내장 음성 테스트 시
          statusText.textContent = '🎧 오디오 파일을 불러오는 중입니다...';
        }});
      }} else {{
        audioEl.pause();
        playBtn.textContent = '▶ 브리핑 재생';
      }}
    }});

    audioEl.addEventListener('timeupdate', () => {{
      if (audioEl.duration) {{
        scrubber.value = (audioEl.currentTime / audioEl.duration) * 100;
        timeLabel.textContent = `${{formatTime(audioEl.currentTime)}} / ${{formatTime(audioEl.duration)}}`;
      }}
    }});

    audioEl.addEventListener('loadedmetadata', () => {{
      timeLabel.textContent = `00:00 / ${{formatTime(audioEl.duration)}}`;
    }});

    audioEl.addEventListener('ended', () => {{
      playBtn.textContent = '▶ 다시 재생';
    }});

    scrubber.addEventListener('input', () => {{
      if (audioEl.duration) {{
        audioEl.currentTime = (scrubber.value / 100) * audioEl.duration;
      }}
    }});

    document.getElementById('btn-rw-15').addEventListener('click', () => {{
      audioEl.currentTime = Math.max(0, audioEl.currentTime - 15);
    }});

    document.getElementById('btn-ff-15').addEventListener('click', () => {{
      audioEl.currentTime = Math.min(audioEl.duration || 9999, audioEl.currentTime + 15);
    }});

    document.getElementById('btn-speed-cycle').addEventListener('click', (e) => {{
      speedIdx = (speedIdx + 1) % speeds.length;
      audioEl.playbackRate = speeds[speedIdx];
      e.target.textContent = `${{speeds[speedIdx].toFixed(2).replace(/\\.00$/, '.0')}}x 배속`;
    }});

    // 에피소드 드롭다운 초기화
    const selectEl = document.getElementById('episode-select');
    EPISODES_INDEX.forEach(item => {{
      const opt = document.createElement('option');
      opt.value = item.date;
      opt.textContent = `${{item.date}} (${{item.weekday}}) 브리핑`;
      selectEl.appendChild(opt);
    }});

    selectEl.addEventListener('change', async (e) => {{
      const epDate = e.target.value;
      try {{
        const res = await fetch(`episodes/${{epDate}}.json`);
        if (res.ok) {{
          const data = await res.json();
          renderEpisode(data);
        }}
      }} catch (err) {{
        console.error(err);
      }}
    }});

    renderEpisode(INITIAL_EPISODE);
  </script>
</body>
</html>
"""
