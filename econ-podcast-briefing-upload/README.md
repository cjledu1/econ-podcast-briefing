# 🎧 월·수·금 07:30 경제·경영 2인 팟캐스트 모닝 브리핑

매주 **월, 수, 금요일 아침 7시 30분(KST)**, 지난 이틀간의 국내외 주요 경제·경영·금융·부동산 뉴스 **20개**를 발췌하여 **경제 입문자(질문자 지민)와 친절한 경제·경영 멘토(해설자 현우)의 2인 문답 팟캐스트 오디오 + 용어 사전 웹 플레이어**를 제작하고 **카카오톡 '나에게 보내기'**로 자동 발송하는 파이프라인입니다.

---

## ✨ 주요 특징

1. **단순 요약을 넘어선 '초보자 눈높이 문답 & 의미 해설'**
   - 20개 뉴스를 **4~5개 핵심 테마**로 묶어 전체 흐름을 짚어주고, 가장 파급력이 큰 **핵심 6개 이슈**는 *"이 뉴스가 왜 내 월급/대출이자/우리 회사에 중요한가요?"*, *"이 용어는 무슨 뜻인가요?"*라는 질문과 일상 비유 해설로 깊게 풀어줍니다.
2. **하이브리드 오디오 엔진 (NotebookLM + 멀티보이스 TTS 자동 전환)**
   - **1순위**: Google **NotebookLM**에 20개 뉴스 심층 해설 마크다운 소스를 자동 업로드하고 한국어 맞춤 프롬프트로 2인 Audio Overview를 생성합니다.
   - **2순위 (Fallback)**: 해외 클라우드 IP(GitHub Actions)에서 구글 로그인 세션이 만료되더라도 브리핑이 절대 누락되지 않도록 **2인 멀티보이스(지민 & 현우)** 음성 합성으로 즉시 자동 전환되며, 카톡 메시지에 세션 갱신 안내를 함께 표시합니다.
3. **출근길 모바일 전용 오디오 웹 플레이어 (GitHub Pages 무료 호스팅)**
   - 카카오톡의 **[🎧 20분 음성 & 해설 듣기]** 버튼을 누르면 스마트폰 브라우저에서 바로 오디오 재생(배속 조절, 15초 이동), **20대 뉴스 해설 카드**, **오늘의 경제 용어 사전**, **2인 대화 전체 대본**을 열람할 수 있습니다.

---

## 🚀 API 키가 전혀 없는 분들을 위한 10분 세팅 가이드

### STEP 1. Google Gemini API 키 발급 (무료, 1분 소요)
1. [Google AI Studio](https://aistudio.google.com/app/apikey)에 접속하여 구글 계정으로 로그인합니다.
2. 우측 상단의 **[Create API key]** 버튼을 클릭합니다.
3. 생성된 키(`AIzaSy...`로 시작)를 복사해 둡니다. → **`GEMINI_API_KEY`**

---

### STEP 2. 카카오톡 '나에게 보내기' API 키 & 토큰 발급 (무료, 3분 소요)
1. [Kakao Developers](https://developers.kakao.com/)에 접속해 로그인한 뒤, 상단 메뉴의 **[내 애플리케이션] -> [애플리케이션 추가하기]**를 클릭합니다.
   - 앱 이름: `모닝 경제 팟캐스트` / 회사명: `개인` 입력 후 저장
2. 생성된 앱을 클릭하고 좌측 메뉴 **[앱 키]**에서 **`REST API 키`**를 복사해 둡니다. → **`KAKAO_REST_API_KEY`**
3. 좌측 메뉴 **[제품 설정] -> [카카오 로그인]**으로 이동하여:
   - **활성화 설정** 상태를 **`ON`**으로 켭니다.
   - 하단의 **Redirect URI**에 `https://localhost:3000`을 등록하고 저장합니다.
4. 좌측 메뉴 **[제품 설정] -> [카카오 로그인] -> [동의항목]**으로 이동하여:
   - 맨 아래 **접근권한** 중 **`카카오톡 메시지 전송 (talk_message)`**의 설정을 클릭해 **선택 동의**로 활성화합니다.
5. 이제 터미널에서 아래 도우미 스크립트를 실행하면 **1분 만에 `KAKAO_REFRESH_TOKEN`**이 발급됩니다!
   ```bash
   python scripts/setup_kakao_token.py
   ```

---

### STEP 3. (선택) Google NotebookLM 로그인 쿠키 추출 (2분 소요)
> 💡 이 단계를 생략하셔도 **2인 멀티보이스 TTS 엔진**으로 월·수·금 20분 팟캐스트가 100% 정상 생성됩니다. NotebookLM 고유의 음성을 우선 사용하고 싶을 때 실행하세요.

1. 내 PC에서 아래 스크립트를 실행합니다:
   ```bash
   python scripts/export_google_cookie.py
   ```
2. 자동으로 열리는 크롬 창에서 구글 로그인을 완료해 NotebookLM 화면이 보이면 터미널에서 `Enter`를 누릅니다.
3. 생성된 `storage_state.b64.txt` 파일 안의 문자열을 복사해 둡니다. → **`GOOGLE_STORAGE_STATE_B64`**

---

### STEP 4. GitHub 저장소 업로드 & GitHub Pages / Secrets 설정 (3분 소요)
1. 본 프로젝트 폴더를 내 GitHub 계정의 새 저장소(예: `econ-podcast-briefing`, **Public 권장 - 무료 GitHub Pages 사용**)에 업로드(Push)합니다.
2. GitHub 저장소 상단 **[Settings] -> [Pages]** 메뉴로 이동합니다:
   - **Build and deployment > Source**: `Deploy from a branch` 선택
   - **Branch**: `main` (또는 `master`) / 폴더는 **`/docs`** 선택 후 **[Save]** 클릭!
   - 이제 내 웹 플레이어 주소는 `https://<내깃허브아이디>.github.io/econ-podcast-briefing`이 됩니다.
3. GitHub 저장소 상단 **[Settings] -> [Secrets and variables] -> [Actions]**로 이동하여 **[New repository secret]** 버튼으로 아래 값들을 등록합니다:

| Secret 이름 | 설명 | 필수 여부 |
| :--- | :--- | :---: |
| `GEMINI_API_KEY` | STEP 1에서 발급받은 Google Gemini API 키 | **필수** |
| `KAKAO_REST_API_KEY` | STEP 2에서 복사한 카카오 앱 REST API 키 | **필수** |
| `KAKAO_REFRESH_TOKEN` | STEP 2의 `setup_kakao_token.py`로 발급받은 리프레시 토큰 | **필수** |
| `PUBLIC_WEB_URL` | `https://<내깃허브아이디>.github.io/<저장소이름>` | **필수** |
| `GOOGLE_STORAGE_STATE_B64` | STEP 3에서 추출한 NotebookLM 구글 세션 Base64 문자열 | 선택 |

4. 설정 끝! 이제 매주 **월·수·금 아침 7시 10분**에 GitHub Actions가 자동으로 깨어나 뉴스를 분석하고 오디오를 만든 뒤 **7시 30분**에 카카오톡을 보내줍니다.
   - 지금 당장 테스트해보고 싶다면 GitHub 저장소의 **[Actions]** 탭 -> **`Morning Economic Podcast Briefing`** -> **[Run workflow]** 버튼을 누르시면 즉시 실행됩니다!

---

## 📂 프로젝트 디렉토리 구조

```
econ-podcast-briefing/
├── .github/workflows/
│   └── morning_briefing.yml     # 매주 월/수/금 07:10 KST 자동 실행 스케줄러
├── src/
│   ├── config.py                # 국내/해외 경제·경영·부동산 RSS 소스 및 지민/현우 페르소나 설정
│   ├── news_collector.py        # 지난 48~60시간 주요 경제/경영 뉴스 수집 및 중복 제거
│   ├── podcast_writer.py        # Gemini 기반 20선 발췌, 초보자 Q&A·용어사전·2인 대본 생성
│   ├── audio_generator.py       # NotebookLM 웹 자동화 + 멀티보이스 TTS 하이브리드 오디오 엔진
│   ├── web_publisher.py         # GitHub Pages 모바일 오디오 웹 플레이어 빌드 (docs/)
│   └── kakao_notifier.py        # 카카오 토큰 자동 갱신 및 '나에게 보내기' 메시지 발송
├── scripts/
│   ├── setup_kakao_token.py     # 최초 1회 카카오 Refresh Token 발급 도우미
│   └── export_google_cookie.py  # NotebookLM 구글 로그인 세션 추출 도우미
├── docs/                        # GitHub Pages로 자동 배포되는 웹 플레이어 및 MP3 아카이브
├── main.py                      # 전체 파이프라인 통합 실행 파일
└── requirements.txt             # Python 패키지 목록
```
