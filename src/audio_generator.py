import asyncio
import base64
import json
import logging
import shutil
import wave
from pathlib import Path
from typing import Dict, Any, Tuple

from src.config import (
    AUDIO_DIR,
    GEMINI_API_KEY,
    GOOGLE_STORAGE_STATE_B64,
    GOOGLE_STORAGE_STATE_PATH,
    HOST_PERSONAS,
    NOTEBOOKLM_CUSTOM_PROMPT,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


def prepare_storage_state_file() -> Path | None:
    """환경변수(GOOGLE_STORAGE_STATE_B64) 또는 로컬 경로에서 Playwright 세션 파일을 준비합니다."""
    state_path = Path(GOOGLE_STORAGE_STATE_PATH)

    if GOOGLE_STORAGE_STATE_B64:
        try:
            decoded = base64.b64decode(GOOGLE_STORAGE_STATE_B64).decode("utf-8")
            # 유효한 JSON인지 검증
            json.loads(decoded)
            temp_state = OUTPUT_DIR / "runtime_storage_state.json"
            temp_state.write_text(decoded, encoding="utf-8")
            return temp_state
        except Exception as e:
            logger.warning(f"GOOGLE_STORAGE_STATE_B64 디코딩 실패: {e}")

    if state_path.exists() and state_path.stat().st_size > 10:
        return state_path

    return None


async def generate_via_notebooklm(
    briefing: Dict[str, Any], target_audio_path: Path
) -> Tuple[bool, str]:
    """
    Playwright를 사용해 Google NotebookLM에 소스를 업로드하고
    맞춤형(Customize) 2인 한국어 팟캐스트 Audio Overview를 생성 및 다운로드합니다.
    반환값: (성공 여부, 상태 메시지)
    """
    state_file = prepare_storage_state_file()
    if not state_file:
        return False, "NO_STORAGE_STATE: 구글 세션 쿠키(storage_state)가 설정되지 않았습니다."

    source_md_path = Path(briefing.get("notebook_source_path", ""))
    if not source_md_path.exists():
        return False, "NO_SOURCE_MD: NotebookLM 업로드용 마크다운 파일이 없습니다."

    source_text = source_md_path.read_text(encoding="utf-8")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return False, "PLAYWRIGHT_NOT_INSTALLED: playwright 패키지가 설치되지 않았습니다."

    logger.info("[NotebookLM] Playwright 브라우저 시작 및 구글 세션 로드 중...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            storage_state=str(state_file),
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1440, "height": 900},
            accept_downloads=True,
        )
        page = await context.new_page()

        try:
            await page.goto(
                "https://notebooklm.google.com/",
                wait_until="domcontentloaded",
                timeout=45000,
            )
            await page.wait_for_timeout(4000)

            # 구글 로그인 페이지로 리다이렉트되었는지 확인
            if "accounts.google.com" in page.url:
                logger.warning("[NotebookLM] 구글 로그인 세션이 만료되었습니다 (accounts.google.com 리다이렉트).")
                await browser.close()
                return False, "SESSION_EXPIRED: 구글 로그인 세션 쿠키가 만료되었습니다."

            # 1. '새 노트북(New Notebook / 새로 만들기)' 버튼 클릭
            logger.info("[NotebookLM] 새 노트북 생성 버튼 탐색 중...")
            new_btn_selectors = [
                "button:has-text('새 노트북')",
                "button:has-text('새로 만들기')",
                "button:has-text('New notebook')",
                "button:has-text('Create')",
                "mat-card.create-new-action-button",
                "[aria-label*='새 노트북']",
                "[aria-label*='New notebook']",
            ]
            clicked_new = False
            for sel in new_btn_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click()
                    clicked_new = True
                    break

            if not clicked_new:
                return False, "UI_CHANGED: '새 노트북' 생성 버튼을 찾을 수 없습니다."

            await page.wait_for_timeout(3000)

            # 2. 소스 추가 모달에서 파일 업로드 또는 '복사된 텍스트(Copied text)' 입력
            logger.info("[NotebookLM] 20대 뉴스 심층 해설 소스 업로드 중...")
            file_input = page.locator("input[type='file']").first
            if await file_input.count() > 0:
                await file_input.set_input_files(str(source_md_path))
                await page.wait_for_timeout(6000)
            else:
                # 텍스트 붙여넣기 옵션 클릭 시도
                paste_selectors = [
                    "button:has-text('복사된 텍스트')",
                    "button:has-text('Copied text')",
                    "mat-chip:has-text('복사된 텍스트')",
                    "mat-chip:has-text('Copied text')",
                ]
                for sel in paste_selectors:
                    loc = page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.click()
                        await page.wait_for_timeout(1500)
                        break

                textarea = page.locator("textarea").first
                if await textarea.count() > 0:
                    await textarea.fill(source_text)
                    insert_btn = page.locator(
                        "button:has-text('삽입'), button:has-text('Insert')"
                    ).first
                    await insert_btn.click()
                    await page.wait_for_timeout(6000)
                else:
                    return False, "SOURCE_UPLOAD_FAILED: 소스 입력란을 찾을 수 없습니다."

            # 3. Audio Overview '맞춤설정(Customize)' 또는 '생성(Generate)' 실행
            logger.info("[NotebookLM] Audio Overview 맞춤 프롬프트 입력 및 생성 요청 중...")
            customize_selectors = [
                "button:has-text('맞춤설정')",
                "button:has-text('Customize')",
                "[aria-label*='맞춤설정']",
                "[aria-label*='Customize']",
            ]
            customized = False
            for sel in customize_selectors:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click()
                    await page.wait_for_timeout(1500)
                    prompt_box = page.locator("textarea").last
                    if await prompt_box.count() > 0:
                        await prompt_box.fill(NOTEBOOKLM_CUSTOM_PROMPT)
                        customized = True
                    break

            gen_selectors = [
                "button:has-text('생성')",
                "button:has-text('Generate')",
                "[aria-label*='오디오 개요 생성']",
                "[aria-label*='Generate Audio Overview']",
            ]
            clicked_gen = False
            for sel in gen_selectors:
                loc = page.locator(sel).last
                if await loc.count() > 0 and await loc.is_visible():
                    await loc.click()
                    clicked_gen = True
                    break

            if not clicked_gen:
                return False, "AUDIO_GEN_BTN_NOT_FOUND: Audio Overview 생성 버튼을 찾을 수 없습니다."

            # 4. 오디오 생성 완료 대기 (최대 10분 폴링)
            logger.info(
                f"[NotebookLM] 오디오 생성 시작됨 (맞춤 프롬프트 적용={customized}). 완료까지 대기합니다..."
            )
            for elapsed_sec in range(0, 600, 10):
                await page.wait_for_timeout(10000)

                # 다운로드 메뉴 또는 오디오 플레이어 등장 확인
                more_menu = page.locator(
                    "button[aria-label*='더보기'], button[aria-label*='More'], button:has(mat-icon:has-text('more_vert'))"
                ).last
                download_btn = page.locator(
                    "a[download], button:has-text('다운로드'), button:has-text('Download'), [ role='menuitem' ]:has-text('다운로드'), [ role='menuitem' ]:has-text('Download')"
                ).first

                if await download_btn.count() > 0 and await download_btn.is_visible():
                    async with page.expect_download(timeout=60000) as download_info:
                        await download_btn.click()
                    download = await download_info.value
                    await download.save_as(str(target_audio_path))
                    logger.info(f"[NotebookLM] 오디오 다운로드 성공: {target_audio_path}")
                    await browser.close()
                    return True, "NOTEBOOKLM_SUCCESS"

                if elapsed_sec >= 60 and await more_menu.count() > 0 and await more_menu.is_visible():
                    try:
                        await more_menu.click()
                        await page.wait_for_timeout(1000)
                        dl_item = page.locator(
                            "[role='menuitem']:has-text('다운로드'), [role='menuitem']:has-text('Download')"
                        ).first
                        if await dl_item.count() > 0 and await dl_item.is_visible():
                            async with page.expect_download(timeout=60000) as download_info:
                                await dl_item.click()
                            download = await download_info.value
                            await download.save_as(str(target_audio_path))
                            logger.info(f"[NotebookLM] 오디오 다운로드 성공: {target_audio_path}")
                            await browser.close()
                            return True, "NOTEBOOKLM_SUCCESS"
                    except Exception:
                        pass

            await browser.close()
            return False, "TIMEOUT: NotebookLM 오디오 생성 시간이 10분을 초과했습니다."

        except Exception as e:
            logger.warning(f"[NotebookLM] 웹 자동화 중 예외 발생: {e}")
            await browser.close()
            return False, f"EXCEPTION: {e}"


async def generate_via_edge_tts(
    briefing: Dict[str, Any], target_audio_path: Path
) -> Tuple[bool, str]:
    """
    2순위 Fallback 엔진: Microsoft Edge Neural 한국어 다중 화자(SunHi & InJoon)를 이용해
    지민(질문자)과 현우(해설자)의 2인 문답 대본을 하나의 자연스러운 MP3 파일로 합성합니다.
    """
    import edge_tts

    dialogue = briefing.get("dialogue", [])
    if not dialogue:
        return False, "대본(dialogue) 데이터가 비어 있습니다."

    q_name = HOST_PERSONAS["questioner"]["name"]
    q_voice = HOST_PERSONAS["questioner"]["voice_edge"]
    e_voice = HOST_PERSONAS["explainer"]["voice_edge"]

    temp_dir = OUTPUT_DIR / "tts_segments"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        f"[Fallback TTS] 2인 팟캐스트 음성 합성 시작 (총 {len(dialogue)}턴, 진행자: {q_name} & {HOST_PERSONAS['explainer']['name']})..."
    )

    segment_files = []
    try:
        for idx, turn in enumerate(dialogue):
            speaker = turn.get("speaker", q_name)
            text = turn.get("text", "").strip()
            if not text:
                continue

            voice = q_voice if speaker == q_name else e_voice
            rate = "+6%" if speaker == q_name else "+4%"
            seg_path = temp_dir / f"seg_{idx:04d}.mp3"

            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
            await communicate.save(str(seg_path))
            segment_files.append(seg_path)

        # MP3 세그먼트 스트림 병합
        with open(target_audio_path, "wb") as outfile:
            for seg_path in segment_files:
                outfile.write(seg_path.read_bytes())

        shutil.rmtree(temp_dir, ignore_errors=True)
        size_kb = target_audio_path.stat().st_size // 1024
        logger.info(f"[Fallback TTS] 2인 팟캐스트 MP3 생성 완료: {target_audio_path} ({size_kb} KB)")
        return True, "FALLBACK_MULTI_VOICE_TTS"
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.warning(f"[Edge TTS] 네트워크/인증서 제약으로 호출 실패: {e}")
        return False, str(e)


def generate_offline_demo_audio(target_audio_path: Path) -> Tuple[bool, str]:
    """API 키 미설정 로컬 테스트 시 오디오 파일 누락을 방지하기 위한 샘플 오디오 파일 생성."""
    import math
    import struct

    sample_rate = 24000
    duration_sec = 3
    n_samples = sample_rate * duration_sec
    with wave.open(str(target_audio_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            freq = 440.0 if t < 0.4 else (554.37 if t < 0.8 else 659.25)
            env = max(0.0, 1.0 - (t / duration_sec))
            val = int(4000 * env * math.sin(2 * math.pi * freq * t))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))
    return True, "BROWSER_WEB_SPEECH_TTS_READY"


def generate_via_gemini_multi_speaker_tts(
    briefing: Dict[str, Any], target_audio_path: Path
) -> Tuple[bool, str]:
    """
    Gemini 2.5 Native Multi-Speaker TTS를 사용하여 2인 대화 오디오를 생성합니다.
    """
    if not GEMINI_API_KEY:
        return False, "NO_GEMINI_KEY"

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        q_name = HOST_PERSONAS["questioner"]["name"]
        e_name = HOST_PERSONAS["explainer"]["name"]

        script_lines = [
            f"{turn.get('speaker', q_name)}: {turn.get('text', '')}"
            for turn in briefing.get("dialogue", [])
        ]
        full_transcript = (
            f"다음은 경제 입문자 '{q_name}'과 친절한 경제 멘토 '{e_name}'의 모닝 경제/경영 팟캐스트 대화입니다. "
            f"두 사람의 개성과 억양을 살려 자연스러운 한국어 팟캐스트 톤으로 읽어주세요.\n\n"
            + "\n".join(script_lines)
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=full_transcript,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker=q_name,
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=HOST_PERSONAS["questioner"]["voice_gemini"]
                                    )
                                ),
                            ),
                            types.SpeakerVoiceConfig(
                                speaker=e_name,
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=HOST_PERSONAS["explainer"]["voice_gemini"]
                                    )
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )

        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        wav_path = target_audio_path.with_suffix(".wav")
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(pcm_data)

        if wav_path != target_audio_path:
            shutil.move(str(wav_path), str(target_audio_path))
        return True, "GEMINI_NATIVE_MULTI_SPEAKER_TTS"
    except Exception as e:
        logger.warning(f"[Gemini TTS] 호출 실패 (Edge Neural TTS로 자동 전환합니다): {e}")
        return False, str(e)


async def produce_podcast_audio(
    briefing: Dict[str, Any], force_fallback: bool = False
) -> Dict[str, Any]:
    """
    하이브리드 오디오 파이프라인:
    1순위: NotebookLM Playwright 웹 자동화 시도
    2순위: 실패 또는 세션 만료 시 멀티 화자 TTS(Gemini / Edge Neural)로 즉시 자동 전환하여 브리핑 누락 방지
    """
    date_str = briefing.get("date", "latest")
    audio_filename = f"briefing-{date_str}.mp3"
    target_audio_path = AUDIO_DIR / audio_filename

    notebooklm_status = "SKIPPED"
    engine_used = "FALLBACK_TTS"
    session_expired = False

    if not force_fallback:
        ok, status_msg = await generate_via_notebooklm(briefing, target_audio_path)
        notebooklm_status = status_msg
        if ok and target_audio_path.exists():
            engine_used = "NOTEBOOKLM_AUDIO_OVERVIEW"
            return {
                "audio_filename": audio_filename,
                "audio_path": str(target_audio_path),
                "engine_used": engine_used,
                "notebooklm_status": notebooklm_status,
                "session_expired": False,
            }
        if "SESSION_EXPIRED" in status_msg:
            session_expired = True
        logger.info(
            f"[Hybrid Audio] NotebookLM 미사용/실패 사유({status_msg}) -> 2인 멀티 화자 TTS 엔진으로 자동 전환합니다."
        )

    # 2순위 Fallback: Gemini Multi-Speaker TTS -> Edge Neural TTS -> 로컬 데모 오디오 순으로 시도
    ok_gem, gem_msg = generate_via_gemini_multi_speaker_tts(briefing, target_audio_path)
    if ok_gem:
        engine_used = gem_msg
    else:
        ok_edge, tts_msg = await generate_via_edge_tts(briefing, target_audio_path)
        if ok_edge:
            engine_used = tts_msg
        else:
            _, demo_msg = generate_offline_demo_audio(target_audio_path)
            engine_used = demo_msg

    return {
        "audio_filename": audio_filename,
        "audio_path": str(target_audio_path),
        "engine_used": engine_used,
        "notebooklm_status": notebooklm_status,
        "session_expired": session_expired,
    }
