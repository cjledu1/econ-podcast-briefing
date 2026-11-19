import asyncio
import logging
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Dict, Any, List, Tuple

from src.config import (
    AUDIO_DIR,
    GEMINI_API_KEY,
    HOST_PERSONAS,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


def cleanup_old_audio_files(keep_latest: int = 6) -> None:
    try:
        mp3_files = sorted(AUDIO_DIR.glob("briefing-*.mp3"), key=lambda p: p.name, reverse=True)
        for old_file in mp3_files[keep_latest:]:
            old_file.unlink(missing_ok=True)
            logger.info(f"[Storage Cleanup] 오래된 오디오 파일 정리 완료: {old_file.name}")
    except Exception as e:
        logger.warning(f"[Storage Cleanup] 오디오 정리 중 오류 (무시): {e}")


def discover_tts_models(client: Any) -> List[str]:
    """API 키에서 사용 가능한 Gemini Multi-Speaker TTS 전용 모델 목록을 동적으로 탐색합니다."""
    preferred = [
        "gemini-3.8-flash-preview-tts",
        "gemini-3.8-flash-tts",
        "gemini-2.5-flash-preview-tts",
    ]
    discovered_tts: List[str] = []
    try:
        for m in client.models.list():
            name = (getattr(m, "name", "") or "").replace("models/", "")
            low = name.lower()
            if "tts" in low:
                discovered_tts.append(name)
        discovered_tts.sort(reverse=True)
        logger.info(f"[Gemini TTS Models] 탐색된 TTS 모델 목록: {discovered_tts}")
    except Exception as e:
        logger.warning(f"[Gemini TTS Models] 모델 목록 조회 실패: {e}")

    ordered: List[str] = []
    for m in discovered_tts + preferred:
        if m not in ordered:
            ordered.append(m)
    return ordered[:4]


def chunk_dialogue_for_gemini_tts(
    dialogue: List[Dict[str, Any]], max_chars_per_chunk: int = 1900
) -> List[List[Dict[str, Any]]]:
    chunks: List[List[Dict[str, Any]]] = []
    current_chunk: List[Dict[str, Any]] = []
    current_len = 0
    for turn in dialogue:
        text = turn.get("text", "").strip()
        if not text:
            continue
        if current_chunk and (current_len + len(text) > max_chars_per_chunk):
            chunks.append(current_chunk)
            current_chunk = [turn]
            current_len = len(text)
        else:
            current_chunk.append(turn)
            current_len += len(text)
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def convert_wav_to_mp3(wav_path: Path, mp3_path: Path) -> bool:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
        return mp3_path.exists() and mp3_path.stat().st_size > 1000
    except Exception as e:
        logger.warning(f"[ffmpeg] WAV -> MP3 변환 실패: {e}")
        return False


async def generate_via_gemini_multi_speaker_tts(
    briefing: Dict[str, Any], target_audio_path: Path
) -> Tuple[bool, str]:
    if not GEMINI_API_KEY:
        return False, "NO_GEMINI_KEY"

    dialogue = briefing.get("dialogue", [])
    if not dialogue:
        return False, "EMPTY_DIALOGUE"

    from google import genai
    from google.genai import types

    client = genai.Client(
        api_key=GEMINI_API_KEY,
        http_options={"api_version": "v1beta", "timeout": 65000},
    )
    q_name = HOST_PERSONAS["questioner"]["name"]
    e_name = HOST_PERSONAS["explainer"]["name"]

    tts_models = discover_tts_models(client)
    active_tts_model: str | None = None

    chunks = chunk_dialogue_for_gemini_tts(dialogue, max_chars_per_chunk=1900)
    logger.info(
        f"[Gemini Multi-Speaker TTS] 총 {len(dialogue)}턴 대본을 {len(chunks)}개 멀티보이스 청크로 합성합니다..."
    )

    temp_dir = OUTPUT_DIR / "gemini_tts_chunks"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    chunk_mp3_files: List[Path] = []
    gemini_success_count = 0
    quota_exhausted = False

    for c_idx, chunk_turns in enumerate(chunks):
        chunk_mp3 = temp_dir / f"chunk_{c_idx:03d}.mp3"
        chunk_wav = temp_dir / f"chunk_{c_idx:03d}.wav"

        if not quota_exhausted:
            script_lines = [f"{t.get('speaker', q_name)}: {t.get('text', '')}" for t in chunk_turns]
            prompt_text = (
                f"# AUDIO PROFILE: {q_name} & {e_name}의 모닝 경제 토크\n"
                f"## THE SCENE\n"
                f"서울의 아늑한 팟캐스트 스튜디오. 친한 직장 선후배 사이인 호기심 많은 후배 '{q_name}'과 "
                f"비유를 잘하는 다정한 선배 '{e_name}'가 아침 커피를 마시며 대본 없이 편안하게 수다를 떨고 있습니다.\n\n"
                f"### DIRECTOR'S NOTES\n"
                f"- **Style & Tone**: 절대 뉴스 아나운서나 기계처럼 딱딱하게 글자를 읽지 마세요(No newsreader or robotic tone). "
                f"구글 NotebookLM 오디오 개요처럼 진짜 사람 두 명이 대화하듯 감정을 듬뿍 담아 자연스러운 일상 서울 말투(초구어체)로 연기하세요.\n"
                f"- **Breathing & Reactions**: 대사 속의 '어?', '아...', '음...', '하하', '그니까요!' 같은 추임새에서 실제로 살짝 웃거나 숨을 고르며(natural micro-pauses) 생동감 있게 리액션하세요.\n"
                f"- **Pacing**: 일상 대화처럼 완급을 조절하세요. 맞장구를 칠 때는 경쾌하고 빠르게, 중요한 경제 비유를 풀어줄 때는 친절하고 또렷하게 말하세요.\n\n"
                f"#### TRANSCRIPT\n"
                + "\n".join(script_lines)
            )

            pcm_bytes = None
            models_to_try = [active_tts_model] if active_tts_model else tts_models

            for tts_model_name in models_to_try:
                if not tts_model_name:
                    continue
                for attempt in range(2):
                    try:
                        logger.info(
                            f"   -> [Gemini Multi-Speaker ({tts_model_name})] 청크 {c_idx+1}/{len(chunks)} 합성 중 (타임아웃 65초)..."
                        )
                        response = client.models.generate_content(
                            model=tts_model_name,
                            contents=prompt_text,
                            config=types.GenerateContentConfig(
                                response_modalities=["AUDIO"],
                                http_options=types.HttpOptions(timeout=65000),
                                speech_config=types.SpeechConfig(
                                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                                        speaker_voice_configs=[
                                            types.SpeakerVoiceConfig(
                                                speaker=q_name,
                                                voice_config=types.VoiceConfig(
                                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                                        voice_name="Aoede"
                                                    )
                                                ),
                                            ),
                                            types.SpeakerVoiceConfig(
                                                speaker=e_name,
                                                voice_config=types.VoiceConfig(
                                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                                        voice_name="Puck"
                                                    )
                                                ),
                                            ),
                                        ]
                                    )
                                ),
                            ),
                        )
                        pcm_bytes = response.candidates[0].content.parts[0].inline_data.data
                        active_tts_model = tts_model_name
                        break
                    except Exception as e:
                        err_str = str(e)
                        if "404" in err_str or "NOT_FOUND" in err_str or "not supported" in err_str.lower():
                            logger.info(f"   -> [{tts_model_name}] 미지원/404, 다음 오디오 모델 탐색: {err_str[:120]}")
                            break
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            if attempt == 0:
                                logger.info("   -> [Gemini TTS] 분당 호출 제한(RPM) 대기 중 (20초 후 재시도)...")
                                await asyncio.sleep(20)
                                continue
                            else:
                                logger.warning(f"   -> [Gemini TTS] 무료 할당량(Quota) 도달. 남은 청크 고속 보완: {e}")
                                quota_exhausted = True
                                break
                        else:
                            logger.warning(f"   -> [{tts_model_name}] 청크 {c_idx+1} 호출 오류/타임아웃: {e}")
                            break
                if pcm_bytes or quota_exhausted:
                    break

            if pcm_bytes:
                with wave.open(str(chunk_wav), "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(pcm_bytes)

                if convert_wav_to_mp3(chunk_wav, chunk_mp3):
                    chunk_mp3_files.append(chunk_mp3)
                    gemini_success_count += 1
                    if c_idx < len(chunks) - 1:
                        await asyncio.sleep(5)
                    continue
            elif active_tts_model is None and c_idx == 0:
                logger.warning("[Gemini TTS] 사용 가능한 멀티스피커 TTS 모델을 찾지 못해 고속 멀티보이스 합성으로 전환합니다.")
                quota_exhausted = True

        ok_sub, _ = await synthesize_turns_with_edge_tts(chunk_turns, chunk_mp3)
        if ok_sub and chunk_mp3.exists():
            chunk_mp3_files.append(chunk_mp3)

    if not chunk_mp3_files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return False, "ALL_GEMINI_CHUNKS_FAILED"

    with open(target_audio_path, "wb") as outfile:
        for mp3_file in chunk_mp3_files:
            outfile.write(mp3_file.read_bytes())

    shutil.rmtree(temp_dir, ignore_errors=True)
    engine_label = (
        "GEMINI_NATIVE_MULTI_SPEAKER_AUDIO"
        if gemini_success_count > 0
        else "FALLBACK_MULTI_VOICE_TTS"
    )
    return True, engine_label


async def synthesize_turns_with_edge_tts(
    turns: List[Dict[str, Any]], output_mp3_path: Path
) -> Tuple[bool, str]:
    import edge_tts

    q_name = HOST_PERSONAS["questioner"]["name"]
    q_voice = HOST_PERSONAS["questioner"]["voice_edge"]
    e_voice = HOST_PERSONAS["explainer"]["voice_edge"]

    seg_dir = OUTPUT_DIR / f"edge_segs_{int(time.time() * 1000)}"
    seg_dir.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(4)

    async def _synth_one(idx: int, turn: Dict[str, Any]) -> Path | None:
        speaker = turn.get("speaker", q_name)
        text = turn.get("text", "").strip()
        if not text:
            return None
        voice = q_voice if speaker == q_name else e_voice
        seg_path = seg_dir / f"seg_{idx:04d}.mp3"
        async with sem:
            for attempt in range(2):
                try:
                    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+3%")
                    await asyncio.wait_for(communicate.save(str(seg_path)), timeout=25.0)
                    if seg_path.exists() and seg_path.stat().st_size > 100:
                        return seg_path
                except Exception as e:
                    if attempt == 1:
                        logger.warning(f"[Edge TTS] 세그먼트 {idx} 합성 지연 건너뜀: {e}")
                    await asyncio.sleep(1)
        return None

    try:
        results = await asyncio.gather(*[_synth_one(idx, t) for idx, t in enumerate(turns)])
        seg_files = [p for p in results if p is not None]
        if not seg_files:
            shutil.rmtree(seg_dir, ignore_errors=True)
            return False, "NO_SEGMENTS_GENERATED"
        with open(output_mp3_path, "wb") as outfile:
            for seg_path in seg_files:
                outfile.write(seg_path.read_bytes())
        shutil.rmtree(seg_dir, ignore_errors=True)
        return True, "FALLBACK_MULTI_VOICE_TTS"
    except Exception as e:
        shutil.rmtree(seg_dir, ignore_errors=True)
        return False, str(e)


async def produce_podcast_audio(
    briefing: Dict[str, Any], force_fallback: bool = False
) -> Dict[str, Any]:
    date_str = briefing.get("date", "latest")
    audio_filename = f"briefing-{date_str}.mp3"
    target_audio_path = AUDIO_DIR / audio_filename

    ok_gem, gem_msg = await generate_via_gemini_multi_speaker_tts(briefing, target_audio_path)
    if ok_gem and target_audio_path.exists():
        engine_used = gem_msg
    else:
        _, tts_msg = await synthesize_turns_with_edge_tts(briefing.get("dialogue", []), target_audio_path)
        engine_used = tts_msg

    cleanup_old_audio_files(keep_latest=6)
    return {
        "audio_filename": audio_filename,
        "audio_path": str(target_audio_path),
        "engine_used": engine_used,
        "notebooklm_status": "GEMINI_PRIMARY",
        "session_expired": False,
    }
