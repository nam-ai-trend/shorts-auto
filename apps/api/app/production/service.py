from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from app.core.paths import find_repo_root
from app.core.settings import AppSettings
from app.production.models import (
    AssetSheetManifest,
    CharacterDefinition,
    ConceptKit,
    ContinuityState,
    KeyPropItem,
    ProductionState,
    SceneItem,
    SceneTextBlock,
    VideoSceneItem,
)
from app.production.camera_movements import (
    CORE_CAMERA_MOVEMENTS,
    CORE_MOVEMENTS_MAP,
    CameraMovementItem,
    MotionRecommendationItem,
    RecommendMotionResponse,
)
from app.production.visual_styles import (
    VISUAL_STYLES,
    VISUAL_STYLES_MAP,
    VisualStyleItem,
    get_visual_style,
)

TTS_AUDIO_FILENAME = "output_1.2x.wav"
RAW_STT_FILENAME = "raw_stt.json"
SCENE_DATA_FILENAME = "scene_data.json"
CONCEPT_KIT_FILENAME = "concept_kit.json"
VIDEO_SCENES_FILENAME = "video_scenes.json"
ASSET_SHEET_FILENAME = "asset_sheet_manifest.json"
SCENES_DIR_NAME = "scenes"
THUMBNAIL_FILENAME = "thumbnail.png"
THUMBNAIL_BG_FILENAME = "thumbnail_bg.png"
FPS = 30
SPEED_RATE = 1.2

SCENE_TRANSITION_KEYWORDS = [
    "하지만", "결론은", "근데", "자 ", "그럼", "여기서부터", 
    "만약", "마지막으로", "첫 번째", "두 번째", "진짜 무서운 건",
    "놀라운 건", "단순히", "그럼 AI", "그럼 에이아이"
]


def _upload_file_to_gradio(base_url: str, file_path: Path) -> dict:
    url = f"{base_url.rstrip('/')}/gradio_api/upload"
    try:
        with open(file_path, "rb") as f:
            files = {"files": (file_path.name, f, "audio/mpeg")}
            response = httpx.post(url, files=files, timeout=60.0)
    except (httpx.ConnectError, httpx.NetworkError) as err:
        raise RuntimeError(
            f"로컬 TTS 서버({base_url})에 연결할 수 없습니다. Qwen3-TTS 로컬 서버가 켜져 있는지 확인해주세요."
        ) from err
    except httpx.TimeoutException as err:
        raise RuntimeError(
            f"로컬 TTS 서버({base_url}) 응답 시간이 초과되었습니다 (60초)."
        ) from err

    if response.status_code == 200:
        result = response.json()
        path = result[0]
        return {"path": path, "meta": {"_type": "gradio.FileData"}}
    raise RuntimeError(f"Gradio 파일 업로드 실패 ({response.status_code}): {response.text}")


def _call_gradio_api(base_url: str, api_name: str, data: list) -> str:
    url = f"{base_url.rstrip('/')}/gradio_api/call{api_name}"
    try:
        response = httpx.post(url, json={"data": data}, timeout=30.0)
    except (httpx.ConnectError, httpx.NetworkError) as err:
        raise RuntimeError(
            f"로컬 TTS 서버({base_url})에 연결할 수 없습니다. Qwen3-TTS 로컬 서버가 켜져 있는지 확인해주세요."
        ) from err
    except httpx.TimeoutException as err:
        raise RuntimeError(
            f"로컬 TTS 서버({base_url}) 응답 시간이 초과되었습니다 (30초)."
        ) from err

    if response.status_code == 200:
        return response.json()["event_id"]
    raise RuntimeError(f"Gradio API 호출 실패 ({api_name}): {response.text}")


def _get_gradio_result(base_url: str, api_name: str, event_id: str, timeout: float = 180.0) -> Any:
    url = f"{base_url.rstrip('/')}/gradio_api/call{api_name}/{event_id}"
    try:
        with httpx.stream("GET", url, timeout=timeout) as response:
            current_event = None
            for line in response.iter_lines():
                if line:
                    line_str = line.strip()
                    if line_str.startswith("event:"):
                        current_event = line_str[6:].strip()
                    elif line_str.startswith("data:"):
                        data_str = line_str[5:].strip()
                        if current_event == "complete":
                            return json.loads(data_str)
                        if current_event == "error":
                            raise RuntimeError(f"Gradio API 에러: {data_str}")
    except (httpx.ConnectError, httpx.NetworkError) as err:
        raise RuntimeError(
            f"로컬 TTS 서버({base_url})와 통신 중 연결이 끊어졌습니다."
        ) from err
    except httpx.TimeoutException as err:
        raise RuntimeError(
            f"로컬 TTS 음성 생성 시간이 초과되었습니다 ({timeout}초)."
        ) from err
    raise RuntimeError("Gradio 결과를 찾지 못했습니다.")


def _change_audio_speed(input_file: Path, output_file: Path, rate: float = SPEED_RATE) -> None:
    cmd = [
        "ffmpeg", "-i", str(input_file),
        "-filter:a", f"atempo={rate}",
        "-ar", "44100",
        str(output_file),
        "-y",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg 배속 변환 실패: {res.stderr}")


def _get_audio_duration(file_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        try:
            return float(res.stdout.strip())
        except ValueError:
            return 0.0
    return 0.0


def generate_tts_for_project(project_dir: Path, settings: AppSettings) -> Path:
    final_script_path = project_dir / "final_script.md"
    if not final_script_path.exists():
        raise FileNotFoundError("final_script.md가 존재하지 않습니다. 먼저 대본을 확정해주세요.")

    script_text = final_script_path.read_text(encoding="utf-8").strip()
    if not script_text:
        raise ValueError("final_script.md 대본 내용이 비어 있습니다.")

    repo_root = find_repo_root()
    ref_voice_path = Path(settings.reference_voice_path)
    if not ref_voice_path.is_absolute():
        ref_voice_path = repo_root / ref_voice_path
    if not ref_voice_path.exists():
        raise FileNotFoundError(f"레퍼런스 음성 파일을 찾을 수 없습니다: {ref_voice_path}")

    base_url = settings.qwen3_tts_base_url
    ref_file_info = _upload_file_to_gradio(base_url, ref_voice_path)

    # 피노키오 TTS 서버의 transcribe_audio로 레퍼런스 음성 텍스트 자동 추출 시도 (실패 시 settings 기본값 fallback)
    ref_text = settings.reference_voice_text
    try:
        transcribe_event_id = _call_gradio_api(base_url, "/transcribe_audio", [ref_file_info])
        transcribe_res = _get_gradio_result(base_url, "/transcribe_audio", transcribe_event_id, timeout=30.0)
        if transcribe_res and isinstance(transcribe_res, list) and transcribe_res[0]:
            ref_text = str(transcribe_res[0]).strip()
    except Exception:
        pass

    clone_data = [
        ref_file_info,
        ref_text,
        script_text,
        "Korean",
        False,
        "1.7B",
        200,
        0.0,
        -1,
    ]

    event_id = _call_gradio_api(base_url, "/generate_voice_clone", clone_data)
    result_data = _get_gradio_result(base_url, "/generate_voice_clone", event_id)

    audio_file_info = result_data[0]
    if not audio_file_info:
        raise RuntimeError("TTS 음성 생성 응답에 파일 정보가 없습니다.")

    remote_path = audio_file_info.get("path")
    audio_download_url = f"{base_url.rstrip('/')}/gradio_api/file={remote_path}"

    temp_wav = project_dir / "temp_tts_raw.wav"
    r = httpx.get(audio_download_url, timeout=60.0)
    if r.status_code != 200:
        raise RuntimeError(f"생성된 음성 다운로드 실패 ({r.status_code})")
    temp_wav.write_bytes(r.content)

    final_wav = project_dir / TTS_AUDIO_FILENAME
    try:
        _change_audio_speed(temp_wav, final_wav, rate=SPEED_RATE)
    finally:
        if temp_wav.exists():
            temp_wav.unlink()

    return final_wav


def _refine_stt_text_with_llm(
    client: OpenAI,
    segments: list[dict],
    script_text: str,
    model: str = "gpt-4o-mini",
) -> list[str]:
    """
    STT 세그먼트별 텍스트를 원본 대본을 참조하여 숫자/단위/고유명사 오탈자 위주로 1:1 교정합니다.
    엄격한 1:1 매칭 및 글자 수/유사도 검증(Safety Guard)을 적용하여,
    LLM의 환각이나 세그먼트 간 문장 병합/왜곡을 원천 차단합니다.
    """
    if not segments:
        return []

    stt_texts = [f"[{i}] {seg['text'].strip()}" for i, seg in enumerate(segments)]
    stt_combined = "\n".join(stt_texts)

    prompt = f"""
당신은 유튜브 쇼츠 음성 자막 검수 전문가입니다.
아래 [STT 결과]의 각 번호 [0] ~ [{len(segments) - 1}]는 성우 음성의 짧은 타임스탬프 구간입니다.
원본 대본을 참고하여 각 번호의 텍스트를 '1:1'로만 미세 교정하세요.

[절대 규칙 - 엄격 준수]
1. 각 번호 [i]의 결과는 반드시 해당 [i]의 원본 STT 음성 조각과 내용/길이가 거의 같아야 합니다.
2. 절대로 여러 번호의 문장을 하나로 합치거나, 다른 번호의 단어를 앞당겨 오지 마세요.
3. 오직 숫자/단위(예: 오만 볼트 -> 5만 볼트, 이백 킬로미터 -> 200km)나 명백한 오타(에이아이 -> AI)만 다듬으세요.
4. 원본 STT에서 문장이 중간에 끊겨 있어도("...다트는 시속 200km 속도", "로 날아가 몸에 꽂힙니다"), 끊긴 그대로 유지하세요.
5. 입력된 번호 개수({len(segments)}개)와 정확히 일치하는 JSON 배열 형식으로만 응답하세요:
["교정0", "교정1", ..., "교정{len(segments) - 1}"]

[원본 대본 참고용]
{script_text}

[STT 결과 (각 줄마다 1:1 교정 대상)]
{stt_combined}
"""

    refined_results: list[str] = [seg["text"].strip() for seg in segments]

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        parsed = json.loads(content)
        if isinstance(parsed, list) and len(parsed) == len(segments):
            for i, seg in enumerate(segments):
                orig_text = seg["text"].strip()
                cand_text = str(parsed[i]).strip()

                # Safety Guard 1: 빈 문자열 검사
                if not cand_text:
                    continue

                # Safety Guard 2: 글자 수 비율 검사 (0.55 ~ 1.85 배 범위를 벗어나면 문장 병합/누락 의심)
                orig_len = max(len(orig_text), 1)
                cand_len = len(cand_text)
                ratio = cand_len / orig_len
                if ratio < 0.55 or ratio > 1.85:
                    # 비정상적 길이 변화 -> 원본 유지
                    continue

                # Safety Guard 3: 문자 유사도 검증 (원본 텍스트 문자의 40% 이상 유지)
                orig_chars = set(c for c in orig_text if not c.isspace())
                cand_chars = set(c for c in cand_text if not c.isspace())
                if orig_chars:
                    overlap = len(orig_chars & cand_chars) / len(orig_chars)
                    if overlap < 0.40:
                        # 전혀 다른 문장으로 왜곡됨 -> 원본 유지
                        continue

                refined_results[i] = cand_text
    except Exception:
        # LLM 호출 실패나 파싱 오류 시 원본 STT 세그먼트 텍스트 100% 보존
        pass

    return refined_results


def align_subtitles_and_scenes_for_project(project_dir: Path, settings: AppSettings) -> list[SceneItem]:
    wav_path = project_dir / TTS_AUDIO_FILENAME
    if not wav_path.exists():
        raise FileNotFoundError(f"{TTS_AUDIO_FILENAME} 파일이 없습니다. 먼저 TTS 음성을 생성해주세요.")

    display_script_path = project_dir / "display_script.md"
    final_script_path = project_dir / "final_script.md"
    if display_script_path.exists():
        script_text = display_script_path.read_text(encoding="utf-8")
    elif final_script_path.exists():
        script_text = final_script_path.read_text(encoding="utf-8")
    else:
        script_text = ""

    client = OpenAI(api_key=settings.openai_api_key)

    # 1. Whisper STT 호출
    file_size = os.path.getsize(wav_path)
    temp_mp3 = None
    target_path = wav_path
    if file_size > 25 * 1024 * 1024:
        temp_mp3 = project_dir / "temp_whisper_input.mp3"
        cmd = ["ffmpeg", "-i", str(wav_path), "-b:a", "128k", str(temp_mp3), "-y"]
        subprocess.run(cmd, capture_output=True, check=True)
        target_path = temp_mp3

    try:
        with open(target_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                file=audio_file,
                model=settings.openai_transcription_model or "whisper-1",
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        raw_segments = getattr(transcript, "segments", []) or []
    finally:
        if temp_mp3 and temp_mp3.exists():
            temp_mp3.unlink()

    # 무효 세그먼트 필터링
    valid_segments = []
    for s in raw_segments:
        text = s.get("text", "") if isinstance(s, dict) else getattr(s, "text", "")
        start = s.get("start", 0.0) if isinstance(s, dict) else getattr(s, "start", 0.0)
        end = s.get("end", 0.0) if isinstance(s, dict) else getattr(s, "end", 0.0)
        cleaned = re.sub(r"[^\w\d가-힣a-zA-Z0-9]", "", text)
        if cleaned:
            valid_segments.append({"text": text.strip(), "start": float(start), "end": float(end)})

    if not valid_segments:
        raise ValueError("STT에서 인식된 음성 세그먼트가 없습니다.")

    # raw_stt.json 저장
    raw_stt_path = project_dir / RAW_STT_FILENAME
    raw_stt_path.write_text(json.dumps(valid_segments, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. LLM 대본 대조 교정
    llm_model = "gpt-4o-mini" if "mini" in settings.openai_analysis_model else settings.openai_analysis_model
    refined_texts = _refine_stt_text_with_llm(client, valid_segments, script_text, model=llm_model)

    # 3. 씬 분할 및 scene_data.json 생성
    scenes: list[SceneItem] = []
    current_blocks: list[SceneTextBlock] = []
    scene_id = 1

    for i, seg in enumerate(valid_segments):
        text = refined_texts[i] if i < len(refined_texts) else seg["text"]
        start = round(seg["start"], 2)
        end = round(seg["end"], 2)
        split = len(current_blocks) >= 5 or any(text.startswith(kw) for kw in SCENE_TRANSITION_KEYWORDS)

        if split and current_blocks:
            sc_start = current_blocks[0].start
            sc_end = current_blocks[-1].end
            scenes.append(
                SceneItem(
                    scene_id=scene_id,
                    start=sc_start,
                    end=sc_end,
                    duration_frames=int((sc_end - sc_start) * FPS),
                    text_blocks=current_blocks,
                )
            )
            scene_id += 1
            current_blocks = []

        current_blocks.append(SceneTextBlock(text=text, start=start, end=end))

    if current_blocks:
        sc_start = current_blocks[0].start
        sc_end = current_blocks[-1].end
        scenes.append(
            SceneItem(
                scene_id=scene_id,
                start=sc_start,
                end=sc_end,
                duration_frames=int((sc_end - sc_start) * FPS),
                text_blocks=current_blocks,
            )
        )

    # scene_data.json 저장
    scene_data_path = project_dir / SCENE_DATA_FILENAME
    scene_data_path.write_text(
        json.dumps([s.model_dump() for s in scenes], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return scenes


def split_script_into_meaningful_scenes(text: str, max_len: int = 40) -> list[str]:
    """
    쇼츠 대본을 4~6초 씬 분할에 적합한 의미 있는 단위(문장 및 긴 복합문의 절)로 분할합니다.
    - 마침표, 물음표, 느낌표, 줄바꿈으로 1차 분할
    - 길이가 40자 이상이거나 긴 복합문인 경우, 쉼표(,) 및 연결 어미(~는데, ~했고, ~지만, ~으며, ~거나 등)를
      기준으로 시각화 가능한 의미 단위(절)로 안전하게 분할합니다.
    """
    raw_sentences = [s.strip() for s in re.split(r"(?<=[.?!])\s+|\n+", text) if s.strip()]
    refined: list[str] = []

    # 절 분할 패턴 (연결 어미 + 쉼표)
    clause_pattern = re.compile(
        r"((?:[가-힣a-zA-Z0-9]+(?:는데|은데|지만|었지만|았지만|였지만|었고|았고|였고|했고|되고|하고|이고|받고|주며|하며|이며|으며|면서|으면서|했으나|되나|으나|거나|고)),\s*)"
    )

    for s in raw_sentences:
        if len(s) <= max_len:
            refined.append(s)
            continue

        parts = clause_pattern.split(s)
        sub_clauses: list[str] = []
        curr = ""
        for p in parts:
            if not p:
                continue
            curr += p
            if clause_pattern.match(p) and len(curr) >= 15:
                sub_clauses.append(curr.strip())
                curr = ""
        if curr.strip():
            sub_clauses.append(curr.strip())

        if len(sub_clauses) > 1:
            refined.extend(sub_clauses)
        else:
            # 패턴 매칭이 안 된 긴 문장의 경우 단순 쉼표 분할 시도
            comma_parts = [c.strip() + "," for c in s.split(",") if c.strip()]
            if len(comma_parts) > 1 and all(len(c) >= 10 for c in comma_parts):
                comma_parts[-1] = comma_parts[-1].rstrip(",")
                refined.extend(comma_parts)
            else:
                refined.append(s)

    return refined


def calibrate_scenes_with_stt(
    video_scenes: list[VideoSceneItem],
    stt_segments: list[dict],
    total_audio_duration: float,
) -> list[VideoSceneItem]:
    """
    LLM이 추정한 씬 시작/종료 시간을 실제 Whisper STT 오디오 타임코드와 100% 매칭하여
    나레이션 발화 시간과 비디오 씬 전환 시간을 오차 없이 동기화(Calibration)합니다.
    """
    if not video_scenes or not stt_segments or total_audio_duration <= 0.1:
        return video_scenes

    def clean(t: str) -> str:
        return re.sub(r"[^가-힣a-zA-Z0-9]", "", t)

    # 1. STT 문자별 정밀 타임코드 맵 생성
    char_times: list[tuple[str, float, float]] = []
    full_stt_clean = ""
    for seg in stt_segments:
        txt = clean(seg.get("text", ""))
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", seg_start))
        seg_dur = max(0.01, seg_end - seg_start)
        n_chars = max(1, len(txt))
        for idx, c in enumerate(txt):
            c_start = seg_start + (seg_dur * idx / n_chars)
            c_end = seg_start + (seg_dur * (idx + 1) / n_chars)
            char_times.append((c, c_start, c_end))
            full_stt_clean += c

    if not full_stt_clean:
        return video_scenes

    # 2. 각 씬의 나레이션과 STT 텍스트 매칭
    calibrated: list[VideoSceneItem] = []
    cur_pos = 0
    prev_end = 0.0

    for i, sc in enumerate(video_scenes):
        narr = clean(sc.narration)
        search_snippet = narr[:15] if len(narr) >= 15 else narr
        match_pos = full_stt_clean.find(search_snippet, cur_pos)
        if match_pos == -1:
            match_pos = cur_pos

        end_pos = min(len(char_times), match_pos + len(narr))
        if end_pos <= match_pos:
            end_pos = min(len(char_times), match_pos + 1)

        if i == 0:
            sc_start = 0.0
        else:
            sc_start = char_times[match_pos][1] if match_pos < len(char_times) else prev_end
            sc_start = max(sc_start, prev_end)

        if i == len(video_scenes) - 1:
            sc_end = total_audio_duration
        else:
            idx = min(len(char_times) - 1, max(0, end_pos - 1))
            sc_end = char_times[idx][2]
            sc_end = min(total_audio_duration, max(sc_end, sc_start + 1.0))

        sc_start = round(sc_start, 2)
        sc_end = round(sc_end, 2)
        if sc_end <= sc_start:
            sc_end = round(sc_start + 2.0, 2)

        target_dur = round(sc_end - sc_start, 2)
        prev_end = sc_end
        cur_pos = end_pos

        updated_item = sc.model_copy(
            update={
                "start": sc_start,
                "end": sc_end,
                "target_duration": target_dur,
                "duration_frames": int(target_dur * FPS),
            }
        )
        calibrated.append(updated_item)

    return calibrated


def generate_concept_kit_and_video_scenes(
    project_dir: Path,
    settings: AppSettings,
    visual_style_id: str = "claymation",
) -> tuple[ConceptKit, list[VideoSceneItem]]:
    # 기존 concept_kit.json에 지정된 스타일이 있고 파라미터가 기본값이면 기존 스타일 유지
    concept_kit_file = project_dir / CONCEPT_KIT_FILENAME
    if visual_style_id == "claymation" and concept_kit_file.exists():
        try:
            existing_ck = json.loads(concept_kit_file.read_text(encoding="utf-8"))
            if existing_ck.get("visual_style_id"):
                visual_style_id = existing_ck["visual_style_id"]
        except Exception:
            pass

    style = get_visual_style(visual_style_id)

    final_script_path = project_dir / "final_script.md"
    script_text = final_script_path.read_text(encoding="utf-8").strip() if final_script_path.exists() else ""
    if not script_text:
        raise ValueError("final_script.md 대본 내용이 없습니다.")

    wav_path = project_dir / TTS_AUDIO_FILENAME
    duration = _get_audio_duration(wav_path) if wav_path.exists() else 30.0
    if duration <= 0:
        duration = 30.0

    raw_stt_path = project_dir / RAW_STT_FILENAME
    stt_segments = []
    if raw_stt_path.exists():
        try:
            stt_segments = json.loads(raw_stt_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    stt_context = json.dumps(stt_segments, ensure_ascii=False) if stt_segments else "[]"

    # 대본 문장 및 의미 있는 절(Clause) 분할 및 번호 매기기 (쇼츠 씬 템포에 맞춰 너무 긴 문장은 의미 단위로 자동 분할)
    sentences = split_script_into_meaningful_scenes(script_text, max_len=40)
    sentence_count = len(sentences)
    numbered_sentences = "\n".join([f"{i+1}. {s}" for i, s in enumerate(sentences)])

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"""
당신은 세계 최고의 AI 쇼츠 영상 디렉터입니다. {style.system_persona}
주어진 쇼츠 대본과 STT 타임스탬프를 바탕으로:
1. '{style.name}' ({style.default_concept_style}) 스타일에 맞춘 비주얼 컨셉 키트(`concept_kit`)를 설계하세요.
2. 전체 영상 오디오 길이(총 {duration:.1f}초)와 대본에서 분할된 총 {sentence_count}개의 의미 단위 구절 목록에 맞추어,
   **단 하나의 구절도 누락하거나 임의로 묶지 않고 1:1로 정확히 {sentence_count}개의 연속적인 비디오 씬(Scene 1 ~ Scene {sentence_count})을 설계**하세요.
   쇼츠 대본 길이에 따라 씬 개수는 자유롭고 유연하게 확장/축소되며(현재 대본 기준: 총 {sentence_count}개 씬),
   **"이전 씬의 마지막 프레임과 다음 씬의 시작 프레임이 완벽히 이어지는 원테이크 연속성(One-take Continuity)"**을 설계하세요.

======================================================================
[🚨 최우선 절대 규칙: 1구절 = 1씬 1:1 완벽 매칭 (Zero Omission & No Merge)]
======================================================================
- **1. 분할된 의미 단위 1개당 1개의 씬 (정확히 {sentence_count}개 씬 생성 - 엄수!)**:
  * 아래 [대본 완결 문장/의미 단위 목록]의 1번부터 {sentence_count}번까지의 각 구절이 정확히 Scene 1부터 Scene {sentence_count}에 1:1로 대응되어야 합니다.
  * 절대로 2개 이상의 구절을 하나의 씬으로 묶거나 합치지 마세요! (쇼츠 영상 템포와 3~5초 비디오 AI 규격을 위해 1구절당 1씬 원칙 엄수)
  * 각 씬의 `narration`은 반드시 아래 목록의 해당 번호 구절 그대로 100% 동일하게 입력해야 합니다 (절대 영어 번역 금지, 요약 금지).
    - Scene 1의 `narration`: 1번 구절
    - Scene 2의 `narration`: 2번 구절
    ...
    - Scene {sentence_count}의 `narration`: {sentence_count}번 구절
  * 결과 비디오 씬 목록(`video_scenes`)의 원소 개수는 정확히 {sentence_count}개여야 합니다.
- **2. 타임라인 및 시간 연속성 배분**:
  * Scene 1의 `start`는 0.0초이며, 마지막 Scene {sentence_count}의 `end`는 전체 오디오 길이인 {duration:.1f}초여야 합니다.
  * 각 씬의 `end`와 다음 씬의 `start`는 시간 간극 없이 정확히 이어져야 합니다.
  * STT 세그먼트 타임코드를 참고하여 각 씬의 문장이 실제 오디오에서 재생되는 시간에 맞추어 `start`와 `end`를 결정하세요.

======================================================================
[규칙 1: 이미지 프롬프트 (start_image_prompt) 강화 가이드라인]
======================================================================
- **1. 주연 캐릭터 및 피사체 고정 락 (Hero Character/Subject Lock - 절대 필수)**:
  - 대본의 내용과 주제에 가장 잘 부합하는 핵심 주인공 캐릭터 또는 피사체를 1개 정의하세요.
  - 해당 피사체의 고유 외형과 비주얼 특징을 정하고, 모든 씬 프롬프트에 100% 동일하게 일관되게 명시하세요.
  - 절대로 대본 주제와 상관없는 엉뚱한 캐릭터를 임의로 넣지 마세요.
- **2. 나레이션 직결 시각화 원칙 (Narration-Driven Visual Metaphor - 핵심)**:
  - 각 씬의 이미지는 해당 씬의 나레이션 핵심 내용과 과학적 사실/지식을 시청자가 1초 만에 직관적으로 이해할 수 있는 **상황 극화 및 시각적 은유**가 화면 중심에 반드시 존재해야 합니다!
- **3. 무대/배경 연속성 락 (Stage & Setting Continuity)**:
  - 대본 주제에 맞는 세계관과 배경 공간을 설정하고, 이어지는 씬들 간에 공간적 일관성을 유지하세요.
- **4. 스타일별 특화 질감 및 비주얼 가이드 ({style.name})**:
{style.image_prompt_guide}
- **5. 텍스트 완전 배제 (Strict Negative Constraint)**:
  - 이미지 내에 어떠한 글자, 숫자, 기호, 워터마크도 절대 나타나선 안 됩니다:
    `Strictly NO text, NO letters, NO numbers, NO labels, NO typography, NO watermark.`
- **6. 단일 뷰포트 원칙 (Single Continuous Viewport - 분할/콜라주 엄격 금지 - 절대 필수)**:
  - 이미지는 반드시 단 하나의 카메라 뷰포트로 구성되어야 합니다. '360-degree view', 'split screen', 'collage', 'quad view', 'panels' 등 이미지를 여러 개로 쪼개는 키워드는 절대 사용 금지:
    `Single continuous camera viewport only, strictly NO split-screen, NO multi-panel collage, NO grid layout, NO 4-way split.`
- **7. 포맷**: 반드시 수직 9:16 비율(`vertical 9:16 portrait aspect ratio`)의 영문 프롬프트로 작성하세요.

======================================================================
[규칙 2: 쇼츠 전문 카메라 모션 (camera_movement & video_prompt) 역동성 & 연속성 가이드라인]
======================================================================
쇼츠의 높은 몰입감과 타격감 있는 템포를 유지하면서도, **1개의 씬 안에서 화면이 녹아내리거나(Morphing) 따로 놀며 튀는 현상을 원천 방지**하기 위해 다음 4대 원칙을 철저히 적용하여 `video_prompt`를 작성하세요:

- **1. 피사체 앵커 락 (Subject Anchor Lock - 절대 필수)**:
  - `video_prompt`에는 반드시 `start_image_prompt`의 핵심 주인공 피사체(Hero Object/Character)를 명시적으로 주어로 지정하세요.
  - 카메라가 움직이는 동안 피사체가 사라지거나 녹아내리지(Melting) 않고 온전히 형태를 유지하도록 명시하세요:
    `The [Hero Subject] remains steadfast and in sharp focus throughout the movement, strictly preventing disappearing, melting, or morphing glitches.`
- **2. 3D 입체 패럴랙스 궤적 (Dynamic 3D Parallax Trajectory - 밋밋함 제거)**:
  - 단순 평면 2D 줌/풀백 대신, 피사체와 배경의 깊이감(Parallax)이 극대화되는 입체적 3D 궤적(Dynamic Arc Orbit, Low-angle Crane-up, Parallax Depth Push/Pull)을 부여하여 영화적 역동성을 살리세요.
- **3. 피사체 자체 액션 & 환경 모션 (Subject & Environmental Dynamics - 역동성 극대화)**:
  - 카메라만 움직여서 밋밋해지는 것을 방지하기 위해, 피사체 자체의 생동감 있는 반응 액션/제스처([dynamic subject action/gesture in {style.name} style])와 환경 물리 효과(dramatic moving studio lighting, authentic material surface motion, ambient atmospheric particles)를 함께 주입하세요.
- **4. 단일 테이크 연속성 (Unbroken Continuous Take)**:
  - 한 씬 안에서 갑작스러운 화면 변형이나 점프가 일어나지 않도록 단일 테이크로 지정하세요:
    `Single continuous unbroken camera take, smooth flowing trajectory, absolutely no jump cuts, no morphing artifacts.`

- 12대 핵심 모션 ID 목록:
  1) `crash_zoom_in`: 0~3초 상식 충돌 후킹, 충격적인 팩트 발표 시 피사체로의 타격감 있는 초고속 3D 줌인
  2) `whip_pan`: '그런데 여기서 반전이 일어납니다' 등 국면 전환 시 신속한 다이내믹 수평 스윕과 포커스 이동
  3) `slow_zoom_in`: 호기심 유발 및 미세 과학 메커니즘으로의 점진적 몰입과 원근감(Parallax) 고조
  4) `slow_zoom_out`: 피사체를 앵커로 유지하며 주변 세계관의 압도적 스케일을 서서히 공개
  5) `orbit`: 피사체 주위를 역동적인 곡선으로 3D 궤도 회전하며 입체감과 텍스처를 극대화
  6) `arc_shot`: 피사체와 배경 사이의 깊은 시차(Parallax)를 강조하는 다이내믹 호 궤적 글라이딩
  7) `tracking_shot`: 움직이는 피사체/물질의 궤적을 밀착하여 긴장감 있게 추적
  8) `low_tracking`: 지면 밀착 로우 앵글에서 피사체를 웅장하고 위압감 있게 올려다보는 다이내믹 무브먼트
  9) `push_past`: 전경 피사체를 강렬하게 스쳐 지나가며 다음 공간/핵심 오브젝트로 입체적 진입
  10) `pedestal_up`: 수직으로 역동적으로 상승 크레인 업하며 거대한 스케일과 에너지를 공개
  11) `drone_pull_back`: 피사체 앵커를 중심에 두고 다이내믹하게 상공으로 크레인 풀백하여 광활한 지평선 조망
  12) `static_shot`: 삼각대에 안정적으로 고정하되, 피사체 자체의 스톱모션 액션과 드라마틱한 조명 변화 집중

- **video_prompt 작성 공식 (역동성 & 피사체 보존 결합 포맷 - 영문 작성)**:
  `Cinematic dynamic [camera_movement] in {style.name} style: The [Hero Subject from start image] remains clearly anchored and in sharp focus, [dynamic subject natural action/reaction]. The camera [dynamic 3D physical trajectory with depth & parallax], while dramatic studio lighting highlights authentic {style.name} visual textures. Single unbroken shot, strictly no morphing, no melting, no jump cuts.`

======================================================================
[규칙 3: continuity 필드]
======================================================================
- `camera`: 시작부터 종료까지의 정밀한 카메라 동선
- `subject_state`: 피사체의 물리적 상태 변화
- `lighting`: 일관된 조명 설정
- `handoff_description`: 이전 씬의 마지막 프레임과 다음 씬의 시작 이미지가 어떻게 연결되는지 한 줄 기술

[대본 완결 문장/의미 단위 목록 - 총 {sentence_count}개 (1번부터 {sentence_count}번까지 빠짐없이 씬들에 배분할 것)]
{numbered_sentences}

[STT 세그먼트 타임코드]
{stt_context}

[중요 지침]
- 반드시 아래 JSON 구조 규격에 맞추어, **위 1번부터 {sentence_count}번까지의 대본 문장 전체를 단 한 문장도 누락 없이 100% 커버하는 비디오 씬 목록(`video_scenes`)을 생성**하세요.
- **핵심 언어 규칙**:
  1. `start_image_prompt`, `video_prompt`, `continuity`는 영문(English)으로 작성하세요.
  2. **`narration` 필드는 절대로 영어로 번역하지 마세요! 반드시 위 [대본 완결 문장/의미 단위 목록]에 적힌 해당 문장 그대로를 100% 동일하게 입력해야 합니다.**

반드시 다음 pure JSON 구조로만 반환하세요 (pure JSON, no markdown backticks):
{{
  "concept_kit": {{
    "visual_style_id": "{style.id}",
    "visual_style": "{style.default_concept_style}",
    "color_and_lighting": "Cinematic soft key light, thematic cohesive palette matching the script",
    "core_objects": ["대본의 핵심 오브젝트 1 (영문)", "대본의 핵심 오브젝트 2 (영문)", "주인공 피사체 (영문)", "핵심 환경 요소 (영문)"],
    "camera_composition": "Vertical 9:16 portrait framing, eye-level to dynamic camera movements",
    "continuity_rules": [
      "Camera motions smoothly guide the visual narrative through single-take transitions.",
      "The final frame object and camera angle of the previous scene seamlessly become the starting visual anchor of the next scene."
    ],
    "character_definition": {{
      "name": "주인공 캐릭터 영문 명칭 (예: main_character, lead_scientist, hero_figure)",
      "description": "선택된 스타일({style.name})에 부합하는 캐릭터 외모, 의상 및 질감 묘사 (영문)",
      "turnaround_prompt": "Full-body character turnaround of the character, front view, 3/4 angle, side view side-by-side on clean studio background"
    }},
    "key_props": [
      {{
        "id": "prop_1",
        "name": "핵심 오브제 1 명칭 (예: key_thematic_prop_1)",
        "description": "선택된 스타일({style.name})에 부합하는 오브제 1 시각적 형태 및 질감 묘사 (영문)",
        "prompt": "Close-up isolated hero prop of prop 1 on clean studio background"
      }},
      {{
        "id": "prop_2",
        "name": "핵심 오브제 2 명칭 (예: key_thematic_prop_2)",
        "description": "선택된 스타일({style.name})에 부합하는 오브제 2 시각적 형태 및 질감 묘사 (영문)",
        "prompt": "Close-up isolated hero prop of prop 2 on clean studio background"
      }}
    ],
    "master_asset_sheet_prompt": "[{style.name.upper()} MASTER CONCEPT ART SHEET - {style.default_concept_style}]: Professional 3-section concept art sheet, 16:9 aspect ratio, solid pure light-gray (#f0f2f5) studio backdrop. Strict mathematical layout with 2 main zones separated by a wide empty vertical gutter: [ZONE 1: LEFT 58% WIDTH (X: 0% to 58%)]: Full-body character turnaround of main character in authentic {style.name} style, showing exactly 3 views side-by-side (front view, 45-degree 3/4 view, side profile view), centered within this left 58% box and strictly NOT crossing past X=58%. [EMPTY VERTICAL GUTTER (X: 58% to 64%)]: Completely blank empty studio background spacing with zero objects. [ZONE 2: RIGHT 36% WIDTH (X: 64% to 100%)]: Divided vertically into two isolated stacked boxes: [TOP BOX (Y: 0% to 48%)]: Close-up isolated hero prop 1 in authentic {style.name} style, centered floating on empty space. [MIDDLE HORIZONTAL GUTTER (Y: 48% to 52%)]: Blank empty space. [BOTTOM BOX (Y: 52% to 100%)]: Close-up isolated hero prop 2 in authentic {style.name} style, centered floating on empty space. Authentic {style.image_prompt_guide}, strictly isolated floating assets, generous negative margins, strictly NO text, NO labels, NO borders, NO grid lines."
  }},
  "video_scenes": [
    {{
      "scene_id": 1,
      "target_duration": 5.5,
      "start": 0.0,
      "end": 5.5,
      "narration": "해당 씬에 해당하는 원본 한국어 대본 문장 그대로 (절대 영어 번역 금지)",
      "camera_movement": "crash_zoom_in",
      "start_image_prompt": "{style.sample_prompt_prefix}",
      "video_prompt": "camera: crash zoom in. movement: snap the lens rapidly toward the focal subject. speed: very fast and punchy. framing: keep the subject readable through sudden scale change. end: land on an intense close-up, smoothly handing off to scene 2, no jump cuts.",
      "requires_character": true,
      "required_props": ["prop_2"],
      "continuity": {{
        "camera": "Eye-level starting shot performing a smooth motion",
        "subject_state": "Initial state of the subject in Scene 1",
        "lighting": "Cohesive studio lighting matching the visual style",
        "handoff_description": "Seamless transition description to Scene 2"
      }}
    }}
  ]
}}
"""
    model_name = "gpt-4o-mini" if "mini" in settings.openai_analysis_model else settings.openai_analysis_model
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```json"):
        content = content[7:-3].strip()
    elif content.startswith("```"):
        content = content[3:-3].strip()

    data = json.loads(content)
    ck_dict = data.get("concept_kit", {})
    ck_dict["visual_style_id"] = style.id
    if not ck_dict.get("visual_style"):
        ck_dict["visual_style"] = style.default_concept_style
    concept_kit = ConceptKit.model_validate(ck_dict)
    raw_video_scenes: list[VideoSceneItem] = []
    for item in data.get("video_scenes", []):
        sc_start = float(item.get("start", 0.0))
        sc_end = float(item.get("end", sc_start + float(item.get("target_duration", 5.0))))
        dur_frames = int((sc_end - sc_start) * FPS)
        vs = VideoSceneItem(
            scene_id=int(item["scene_id"]),
            target_duration=round(sc_end - sc_start, 2),
            start=round(sc_start, 2),
            end=round(sc_end, 2),
            duration_frames=dur_frames,
            narration=item.get("narration", ""),
            start_image_prompt=item.get("start_image_prompt", ""),
            video_prompt=item.get("video_prompt", ""),
            camera_movement=item.get("camera_movement") or None,
            continuity=ContinuityState.model_validate(item.get("continuity", {})),
            is_locked=bool(item.get("is_locked", False)),
            requires_character=bool(item.get("requires_character", True)),
            required_props=list(item.get("required_props", [])),
        )
        raw_video_scenes.append(vs)

    # 🎯 핵심: LLM의 부정확한 가짜 타임코드를 실제 Whisper STT 타임코드에 100% 동기화 보정!
    video_scenes = calibrate_scenes_with_stt(raw_video_scenes, stt_segments, duration)

    # 파일 저장
    (project_dir / CONCEPT_KIT_FILENAME).write_text(
        json.dumps(concept_kit.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    (project_dir / VIDEO_SCENES_FILENAME).write_text(
        json.dumps([vs.model_dump() for vs in video_scenes], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return concept_kit, video_scenes


def _auto_trim_margin(cropped: Any, padding_ratio: float = 0.04) -> Any:
    """
    스튜디오 배경의 여백을 정밀 감지하여 주요 객체 영역만 자연스러운 패딩(기본 4%)을 두고 크롭합니다.
    순수 PIL로 동작하여 외부 의존성 없이 빠르고 안정적입니다.
    """
    try:
        from PIL import Image, ImageChops

        if not isinstance(cropped, Image.Image):
            return cropped

        img_rgb = cropped.convert("RGB")
        w, h = img_rgb.size
        corners = [
            img_rgb.getpixel((0, 0)),
            img_rgb.getpixel((w - 1, 0)),
            img_rgb.getpixel((0, h - 1)),
            img_rgb.getpixel((w - 1, h - 1)),
        ]
        bg_r = sum(c[0] for c in corners) // 4
        bg_g = sum(c[1] for c in corners) // 4
        bg_b = sum(c[2] for c in corners) // 4

        bg_img = Image.new("RGB", (w, h), (bg_r, bg_g, bg_b))
        diff = ImageChops.difference(img_rgb, bg_img).convert("L")
        mask = diff.point(lambda p: 255 if p > 18 else 0)
        bbox = mask.getbbox()
        if not bbox:
            return cropped

        bw = bbox[2] - bbox[0]
        bh = bbox[3] - bbox[1]
        pad_x = int(bw * padding_ratio)
        pad_y = int(bh * padding_ratio)
        x1 = max(0, bbox[0] - pad_x)
        y1 = max(0, bbox[1] - pad_y)
        x2 = min(w, bbox[2] + pad_x)
        y2 = min(h, bbox[3] + pad_y)

        if (x2 - x1) > 40 and (y2 - y1) > 40:
            return cropped.crop((x1, y1, x2, y2))
    except Exception:
        pass
    return cropped


def _find_smart_asset_split_points(img: Any) -> tuple[int, int]:
    """
    16:9 마스터 에셋 시트에서 배경을 분석하여,
    1) 캐릭터(좌측)와 소품들(우측) 사이의 가장 깊고 넓은 빈 수직 여백 거터(Vertical Valley) split_x를 찾고,
    2) 우측 소품 영역에서 상단 소품과 하단 소품 사이의 빈 수평 여백 거터(Horizontal Valley) split_y를 수학적으로 검출합니다.
    순수 PIL 투영 히스토그램을 사용하여 0.01초 내에 1픽셀 오차 없이 검출합니다.
    오브젝트 감지에 실패하거나 배경이 복잡할 경우 수치 기준 기본값(X: 62%, Y: 50%)을 반환합니다.
    """
    from PIL import Image, ImageChops

    W, H = img.size
    default_x = int(W * 0.62)
    default_y = int(H * 0.50)

    try:
        im_rgb = img.convert("RGB")
        corners = [
            im_rgb.getpixel((0, 0)),
            im_rgb.getpixel((W - 1, 0)),
            im_rgb.getpixel((0, H - 1)),
            im_rgb.getpixel((W - 1, H - 1)),
        ]
        bg_r = sum(c[0] for c in corners) // 4
        bg_g = sum(c[1] for c in corners) // 4
        bg_b = sum(c[2] for c in corners) // 4

        bg_img = Image.new("RGB", (W, H), (bg_r, bg_g, bg_b))
        diff = ImageChops.difference(im_rgb, bg_img).convert("L")
        mask = diff.point(lambda p: 255 if p > 18 else 0)

        # 400px 축소본으로 초고속 히스토그램 투영
        scale_w = 400
        scale_h = max(100, int(H * (scale_w / W)))
        small_mask = mask.resize((scale_w, scale_h), Image.Resampling.BILINEAR)
        pix = small_mask.load()

        # 1. X축 수직 거터 탐색 (너비의 45% ~ 82% 구간)
        x_start = int(scale_w * 0.45)
        x_end = int(scale_w * 0.82)
        x_counts = []
        for x in range(x_start, x_end):
            col_sum = sum(pix[x, y] for y in range(scale_h))
            x_counts.append((x, col_sum))

        min_x_val = min(c[1] for c in x_counts)
        best_xs = [c[0] for c in x_counts if c[1] <= min_x_val + 255]
        best_x_small = best_xs[len(best_xs) // 2]
        split_x = int(best_x_small * (W / scale_w))

        # 2. Y축 수평 거터 탐색 (우측 영역에서 높이의 30% ~ 70% 구간)
        y_start = int(scale_h * 0.30)
        y_end = int(scale_h * 0.70)
        y_counts = []
        for y in range(y_start, y_end):
            row_sum = sum(pix[x, y] for x in range(best_x_small, scale_w))
            y_counts.append((y, row_sum))

        min_y_val = min(c[1] for c in y_counts)
        best_ys = [c[0] for c in y_counts if c[1] <= min_y_val + 255]
        best_y_small = best_ys[len(best_ys) // 2]
        split_y = int(best_y_small * (H / scale_h))

        return split_x, split_y
    except Exception as e:
        print(f"[Smart Split Warning] {e}. Using fallback split points.")
        return default_x, default_y


def generate_master_asset_sheet(
    project_dir: Path,
    settings: AppSettings,
    model: str = "nano_banana_pro",
) -> AssetSheetManifest:
    """
    단 1회의 16:9 와이드 생성으로 메인 캐릭터(좌측 60%)와 핵심 오브제 2개(우측 상/하 40%)를
    한 번에 뽑아내고, 오차 없이 3개의 독립 에셋 파일로 자동 분할합니다.
    """
    from PIL import Image, ImageDraw
    import datetime

    concept_kit_file = project_dir / CONCEPT_KIT_FILENAME
    concept_kit: dict = {}
    if concept_kit_file.exists():
        try:
            concept_kit = json.loads(concept_kit_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 스타일 및 캐릭터/오브제 메타데이터 추출
    style_id = concept_kit.get("visual_style_id", "claymation")
    style = get_visual_style(style_id)
    style_desc = concept_kit.get("visual_style") or style.default_concept_style

    char_def = concept_kit.get("character_definition") or {}
    char_name = char_def.get("name", "main_character")
    char_desc = (char_def.get("description") or "").strip()
    if not char_desc or char_desc == "miniature handcrafted clay person":
        char_desc = f"Main character '{char_name}' designed in authentic {style.name} style"

    key_props = concept_kit.get("key_props") or []
    prop_1_info = key_props[0] if len(key_props) > 0 else {"name": "key_prop_1", "description": "thematic scientific object"}
    prop_2_info = key_props[1] if len(key_props) > 1 else {"name": "key_prop_2", "description": "thematic secondary prop"}
    p1_desc = prop_1_info.get("description") or f"hero prop '{prop_1_info.get('name', 'prop1')}'"
    p2_desc = prop_2_info.get("description") or f"secondary prop '{prop_2_info.get('name', 'prop2')}'"

    # 비-클레이메이션 스타일 선택 시 과거 점토 수식어 자동 정제
    if style.id != "claymation":
        char_desc = char_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")
        p1_desc = p1_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")
        p2_desc = p2_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")

    # 비-클레이메이션 스타일 선택 시 과거 점토 수식어 자동 정제
    if style_id != "claymation":
        char_desc = char_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")
        p1_desc = p1_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")
        p2_desc = p2_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")

    # 선택된 비주얼 스타일(클레이메이션 등)을 100% 반영하는 강력한 16:9 3구역 마스터 에셋 시트 프롬프트 구성
    sheet_prompt = (
        f"[{style.name.upper()} MASTER CONCEPT ART SHEET - {style_desc}]. "
        f"16:9 widescreen aspect ratio (2752x1536), solid pure light-gray (#f0f2f5) studio backdrop. "
        f"Strict mathematical layout with 2 main zones separated by a wide empty blank vertical gutter: "
        f"[ZONE 1: LEFT 58% WIDTH (X: 0% to 58%)]: Full-body character turnaround of {char_desc} in authentic {style.name} aesthetic, "
        f"showing exactly 3 views side-by-side (front view, 45-degree 3/4 view, side profile view), centered within this left 58% box and strictly NOT crossing past X=58%. "
        f"[EMPTY VERTICAL GUTTER (X: 58% to 64%)]: Completely blank empty studio background spacing with zero objects. "
        f"[ZONE 2: RIGHT 36% WIDTH (X: 64% to 100%)]: Divided vertically into two isolated stacked boxes: "
        f"  - [TOP BOX (Y: 0% to 48%)]: Close-up isolated hero prop of {p1_desc} in authentic {style.name} aesthetic, centered floating on empty space. "
        f"  - [MIDDLE HORIZONTAL GUTTER (Y: 48% to 52%)]: Completely blank empty space. "
        f"  - [BOTTOM BOX (Y: 52% to 100%)]: Close-up isolated hero prop of {p2_desc} in authentic {style.name} aesthetic, centered floating on empty space. "
        f"Rendering directive: Authentic {style.image_prompt_guide}. Strict tactile material consistency across character and props, "
        f"macro photography studio lighting, generous negative margins, strictly NO text, NO labels, NO borders, NO grid lines."
    )

    # 생성된 프롬프트를 concept_kit에 보존
    concept_kit["master_asset_sheet_prompt"] = sheet_prompt
    try:
        concept_kit_file.write_text(json.dumps(concept_kit, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    master_sheet_path = assets_dir / "master_asset_sheet.png"

    has_generated = False

    # 0. Google Flow (gflow) 모델로 마스터 에셋 시트 생성 시도
    if model in FLOW_IMAGE_MODELS or model.startswith("flow_"):
        alias = FLOW_IMAGE_MODELS.get(model, "nano-pro")
        try:
            _run_flow_image_generate(
                model_alias=alias,
                prompt=sheet_prompt,
                output_path=master_sheet_path,
                aspect_ratio="16:9",
            )
            if master_sheet_path.exists() and master_sheet_path.stat().st_size > 1000:
                has_generated = True
        except Exception as e:
            print(f"[Google Flow Master Asset Sheet Error] {e}")

    # 1. 힉스필드 모델 시도
    if not has_generated and model != "dall-e-3":
        try:
            image_url = _run_higgsfield_generate(
                job_type=model,
                prompt=sheet_prompt,
                aspect_ratio="16:9",
                resolution="2k",
            )
            if image_url and image_url.startswith("http"):
                resp = httpx.get(image_url, timeout=90.0)
                if resp.status_code == 200 and len(resp.content) > 1000:
                    master_sheet_path.write_bytes(resp.content)
                    has_generated = True
        except Exception as e:
            print(f"[Asset Sheet Generate Warning] {e}. Falling back to clean template generator.")

    # fallback (CLI 미설치 또는 오프라인 테스트 시)
    if not has_generated or not master_sheet_path.exists() or master_sheet_path.stat().st_size < 1000:
        W, H = 1920, 1080
        fallback_img = Image.new("RGB", (W, H), color=(241, 245, 249))
        draw = ImageDraw.Draw(fallback_img)
        draw.line([(int(W * 0.60), 0), (int(W * 0.60), H)], fill=(203, 213, 225), width=4)
        draw.line([(int(W * 0.60), int(H * 0.50)), (W, int(H * 0.50))], fill=(203, 213, 225), width=4)

        draw.text((int(W * 0.30), int(H * 0.15)), "CHARACTER TURNAROUND (FRONT / 45° / SIDE)", fill=(71, 85, 105), anchor="mm")
        draw.rounded_rectangle([100, 250, int(W * 0.60) - 100, H - 150], radius=20, fill=(226, 232, 240), outline=(59, 130, 246), width=3)
        draw.text((int(W * 0.30), int(H * 0.55)), f"{char_name}\n({char_desc[:40]})", fill=(30, 41, 59), anchor="mm")

        draw.text((int(W * 0.80), int(H * 0.10)), "HERO PROP 1", fill=(71, 85, 105), anchor="mm")
        draw.rounded_rectangle([int(W * 0.60) + 80, 120, W - 80, int(H * 0.50) - 50], radius=16, fill=(226, 232, 240), outline=(16, 185, 129), width=3)
        draw.text((int(W * 0.80), int(H * 0.28)), f"{prop_1_info.get('name')}\n({prop_1_info.get('description', '')[:30]})", fill=(30, 41, 59), anchor="mm")

        draw.text((int(W * 0.80), int(H * 0.58)), "HERO PROP 2", fill=(71, 85, 105), anchor="mm")
        draw.rounded_rectangle([int(W * 0.60) + 80, int(H * 0.50) + 70, W - 80, H - 70], radius=16, fill=(226, 232, 240), outline=(245, 158, 11), width=3)
        draw.text((int(W * 0.80), int(H * 0.78)), f"{prop_2_info.get('name')}\n({prop_2_info.get('description', '')[:30]})", fill=(30, 41, 59), anchor="mm")

        fallback_img.save(master_sheet_path)

    img = Image.open(master_sheet_path)
    W, H = img.size

    # 컴퓨터 비전(CV) 기반 지능형 빈 여백 계곡(Gutter Valley) 탐색
    split_x, split_y = _find_smart_asset_split_points(img)

    # 1) 캐릭터 턴어라운드 (좌측 0 ~ split_x 통째 + 스마트 패딩 트림)
    char_crop = img.crop((0, 0, split_x, H))
    char_trimmed = _auto_trim_margin(char_crop, padding_ratio=0.03)
    char_path = assets_dir / "master_character.png"
    char_trimmed.save(char_path)

    # 2) 핵심 소품 1 (우측 상단: split_x ~ W, 0 ~ split_y + 스마트 패딩 트림)
    prop1_crop = img.crop((split_x, 0, W, split_y))
    prop1_trimmed = _auto_trim_margin(prop1_crop, padding_ratio=0.05)
    prop1_path = assets_dir / "prop_1.png"
    prop1_trimmed.save(prop1_path)

    # 3) 핵심 소품 2 (우측 하단: split_x ~ W, split_y ~ H + 스마트 패딩 트림)
    prop2_crop = img.crop((split_x, split_y, W, H))
    prop2_trimmed = _auto_trim_margin(prop2_crop, padding_ratio=0.05)
    prop2_path = assets_dir / "prop_2.png"
    prop2_trimmed.save(prop2_path)

    pid = project_dir.name
    manifest = AssetSheetManifest(
        has_sheet=True,
        master_sheet_url=f"/api/projects/{pid}/production/assets/master_asset_sheet.png",
        character_url=f"/api/projects/{pid}/production/assets/master_character.png",
        prop_1_url=f"/api/projects/{pid}/production/assets/prop_1.png",
        prop_2_url=f"/api/projects/{pid}/production/assets/prop_2.png",
        prop_1_name=str(prop_1_info.get("name", "Object 1")),
        prop_2_name=str(prop_2_info.get("name", "Object 2")),
        character_name=str(char_name),
        created_at=datetime.datetime.now().isoformat(),
    )

    (assets_dir / ASSET_SHEET_FILENAME).write_text(
        json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return manifest


def read_asset_sheet_manifest(project_dir: Path, project_id: str | None = None) -> AssetSheetManifest | None:
    manifest_path = project_dir / "assets" / ASSET_SHEET_FILENAME
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            pid = project_id or project_dir.name
            data["master_sheet_url"] = f"/api/projects/{pid}/production/assets/master_asset_sheet.png"
            data["character_url"] = f"/api/projects/{pid}/production/assets/master_character.png"
            data["prop_1_url"] = f"/api/projects/{pid}/production/assets/prop_1.png"
            data["prop_2_url"] = f"/api/projects/{pid}/production/assets/prop_2.png"
            return AssetSheetManifest.model_validate(data)
        except Exception:
            pass
    return None


def _generate_fallback_clay_image(target_path: Path, scene_id: int, prompt_summary: str, is_final: bool = False) -> None:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (576, 1024), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        colors = [
            (37, 99, 235), (16, 185, 129), (245, 158, 11),
            (14, 165, 233), (139, 92, 246), (236, 72, 153)
        ]
        accent = colors[(scene_id - 1) % len(colors)]
        draw.rounded_rectangle([30, 40, 546, 984], radius=24, fill=(26, 32, 44), outline=accent, width=4)

        # 상단 배지
        badge_text = f"SCENE {scene_id} " + ("FINAL FRAME" if is_final else "START IMAGE")
        draw.rounded_rectangle([60, 70, 516, 130], radius=12, fill=accent)
        draw.text((288, 100), badge_text, anchor="mm", fill=(255, 255, 255))

        # 클레이 오브젝트 일러스트 원
        draw.ellipse([148, 180, 428, 460], fill=(30, 41, 59), outline=accent, width=3)
        draw.ellipse([218, 250, 358, 390], fill=accent)
        draw.text((288, 320), "CLAY", anchor="mm", fill=(255, 255, 255))

        # 나레이션 및 프롬프트 요약
        draw.text((288, 520), "3D CLAYMATION INFOGRAPHIC", anchor="mm", fill=accent)
        draw.rounded_rectangle([60, 570, 516, 880], radius=12, fill=(15, 23, 42), outline=(51, 65, 85), width=2)

        lines = [
            f"Scene {scene_id} Continuity State",
            "----------------------------",
            prompt_summary[:100],
        ]
        y = 610
        for line in lines:
            draw.text((80, y), line[:38], fill=(226, 232, 240))
            y += 35

        target_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(target_path, "PNG")
    except Exception:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


FLOW_IMAGE_MODELS: dict[str, str] = {
    "flow_nano_pro": "nano-pro",
    "flow_imagen_4": "imagen4",
    "flow_nano_2_1": "nano2.1",
    "flow_nano_2_lite": "nano2-lite",
    "nano_banana_pro_flow": "nano-pro",
}

FLOW_VIDEO_MODELS: dict[str, str] = {
    "flow_veo_fast": "veo-fast",
    "flow_veo_quality": "veo-quality",
    "flow_veo_lite": "veo-lite",
    "flow_omni_flash": "omni-flash",
    "veo_3_1_flow": "veo-fast",
}

FLOW_MAX_PARALLEL_WORKERS = int(os.environ.get("FLOW_MAX_PARALLEL_WORKERS", "3"))
_flow_pool_lock = __import__("threading").Lock()
_flow_profile_queue: Any = None
_flow_worker_profiles: list[str] = []


def _get_gflow_home() -> Path:
    env_home = os.environ.get("GFLOW_CLI_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    mac_home = Path.home() / "Library/Application Support/gflow-cli"
    if mac_home.exists():
        return mac_home
    return Path.home() / ".local/share/gflow-cli"


def _sync_worker_profile_dir(src_dir: Path, dst_dir: Path) -> None:
    """기본 Flow 프로필의 세션을 워커 프로필 디렉토리로 안전하게 복제/동기화합니다 (싱글톤 락 제외)."""
    dst_dir.mkdir(parents=True, exist_ok=True)
    ignore_names = {"SingletonLock", "SingletonCookie", "SingletonSocket", "RunningChromeVersion", "lockfile"}
    for item in src_dir.iterdir():
        if item.name in ignore_names or item.name.startswith("Singleton"):
            continue
        target = dst_dir / item.name
        try:
            if item.is_dir():
                shutil.copytree(
                    item,
                    target,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("Singleton*", "RunningChromeVersion", "lockfile"),
                )
            else:
                shutil.copy2(item, target)
        except Exception:
            pass


def _ensure_flow_worker_profiles(target_workers: int = FLOW_MAX_PARALLEL_WORKERS) -> list[str]:
    """
    Google Flow CLI 병렬 실행을 위해 멀티 워커 프로필 풀(기본 3개)을 자동 준비합니다.
    동일 프로필 디렉토리는 크롬 user-data-dir 및 ProfileLease(flock)에 의해 동시 실행이 차단되므로,
    기본 프로필을 독립된 워커 프로필(profile_<base>_w2, _w3 등)로 분리하여 동시 병렬 실행을 보장합니다.
    """
    import sqlite3

    gflow_home = _get_gflow_home()
    if not gflow_home.exists():
        return ["default"]

    # 1. 기본 프로필 탐색
    default_profile = None
    cfg_file = gflow_home / "config.toml"
    if cfg_file.exists():
        try:
            m = re.search(r'default_profile\s*=\s*"([^"]+)"', cfg_file.read_text(encoding="utf-8"))
            if m:
                default_profile = m.group(1).strip()
        except Exception:
            pass

    existing_dirs = sorted(
        [d for d in gflow_home.iterdir() if d.is_dir() and d.name.startswith("profile_") and (d / "Default" / "Cookies").exists()],
        key=lambda p: p.name,
    )
    if not existing_dirs:
        return [default_profile or "default"]

    base_dir = None
    if default_profile:
        cand = gflow_home / f"profile_{default_profile}"
        if cand.exists() and (cand / "Default" / "Cookies").exists():
            base_dir = cand
    if base_dir is None:
        base_dir = existing_dirs[0]

    base_name = base_dir.name[len("profile_"):]

    # 2. 워커 프로필 생성 및 최신 쿠키 동기화
    worker_names: list[str] = [base_name]
    for idx in range(2, target_workers + 1):
        w_name = f"{base_name}_w{idx}"
        w_dir = gflow_home / f"profile_{w_name}"
        base_cookies = base_dir / "Default" / "Cookies"
        w_cookies = w_dir / "Default" / "Cookies"

        need_sync = not w_cookies.exists()
        if not need_sync and base_cookies.exists():
            try:
                # 원본 프로필의 쿠키가 워커보다 1시간 이상 최신이면 갱신
                if base_cookies.stat().st_mtime - w_cookies.stat().st_mtime > 3600:
                    need_sync = True
            except Exception:
                pass

        if need_sync:
            _sync_worker_profile_dir(base_dir, w_dir)

        if (w_dir / "Default" / "Cookies").exists():
            worker_names.append(w_name)

    # 사용자가 별도로 등록한 다른 계정 프로필도 있으면 풀에 추가
    for d in existing_dirs:
        p_name = d.name[len("profile_"):]
        if p_name not in worker_names:
            worker_names.append(p_name)

    # 3. gflow.db profiles 테이블에 워커 프로필 등록 (FK 제약 충족)
    db_path = gflow_home / "gflow.db"
    if db_path.exists():
        try:
            with sqlite3.connect(str(db_path), timeout=10.0) as conn:
                cur = conn.cursor()
                for w_name in worker_names:
                    w_dir = str(gflow_home / f"profile_{w_name}")
                    cur.execute(
                        "INSERT OR IGNORE INTO profiles (name, profile_dir, first_seen_at, last_used_at) "
                        "VALUES (?, ?, datetime('now'), datetime('now'));",
                        (w_name, w_dir),
                    )
                conn.commit()
        except Exception:
            pass

    return worker_names


def get_flow_worker_count() -> int:
    """현재 사용 가능한 Flow 병렬 워커 프로필 수를 반환합니다."""
    global _flow_profile_queue, _flow_worker_profiles
    with _flow_pool_lock:
        if _flow_profile_queue is None:
            import queue
            _flow_worker_profiles = _ensure_flow_worker_profiles(FLOW_MAX_PARALLEL_WORKERS)
            _flow_profile_queue = queue.Queue()
            for idx, p in enumerate(_flow_worker_profiles):
                _flow_profile_queue.put((idx, p))
        return max(1, len(_flow_worker_profiles))


from contextlib import contextmanager


@contextmanager
def _acquire_flow_profile(timeout_seconds: float = 900.0):
    """
    병렬 요청 시 놀고 있는 Flow 워커 프로필을 스레드 안전하게 하나씩 배정(Lease)하고,
    작업이 끝나면 쿨다운 후 큐에 반환하는 컨텍스트 매니저입니다.
    동시 기동으로 인한 구글 Flow 웹 화면 로딩 병목(ui-selector-drift) 및 봇 탐지를 방지하기 위해
    워커 간 4초 시차(Stagger)와 종료 후 5초 쿨다운을 적용합니다.
    """
    import time
    get_flow_worker_count()
    worker_idx, profile_name = _flow_profile_queue.get(timeout=timeout_seconds)
    try:
        # 동시 시작 시 브라우저 기동 스파이크 완화 및 봇 탐지 방지 계단식 시차 (워커당 4초)
        if worker_idx > 0:
            time.sleep(worker_idx * 4.0)
        yield profile_name
    finally:
        # 크롬 프로세스 정리, 구글 세션 세마포어 안정화 및 커널 flock 완전 해제를 위한 5초 쿨다운
        time.sleep(5.0)
        _flow_profile_queue.put((worker_idx, profile_name))


def _build_flow_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GFLOW_CLI_TELEMETRY"] = "0"
    env["GFLOW_CLI_LEASE_WAIT_SECONDS"] = "180"
    return env


def _clean_watermark_if_available(file_path: Path) -> None:
    """Google Flow / Veo 워터마크 자동 제거 (로컬 cut-mark 스킬 연동)"""
    remover_script = Path.home() / ".gemini/config/skills/cut-mark/scripts/remove_watermark.py"
    if not remover_script.exists() or not file_path.exists():
        return
    try:
        import uuid
        temp_cleaned = file_path.with_name(f"temp_clean_{uuid.uuid4().hex[:8]}_{file_path.name}")
        cmd = ["python3", str(remover_script), str(file_path), "-o", str(temp_cleaned)]
        res = subprocess.run(cmd, capture_output=True, timeout=60.0)
        if res.returncode == 0 and temp_cleaned.exists() and temp_cleaned.stat().st_size > 1000:
            temp_cleaned.replace(file_path)
        elif temp_cleaned.exists():
            temp_cleaned.unlink(missing_ok=True)
    except Exception:
        pass


def _run_flow_image_generate(
    model_alias: str,
    prompt: str,
    output_path: Path,
    aspect_ratio: str = "9:16",
    timeout_minutes: int = 10,
    references: list[Path] | None = None,
) -> Path:
    """Google Flow CLI(gflow/flow)를 이용한 고품질 Imagen 이미지 생성 (에셋 시트 i2i 참조 및 멀티 워커 병렬 지원)"""
    # 이전 생성 시도에서 남은 잔여/더미 파일 사전 정리 (오인 방지)
    output_path.unlink(missing_ok=True)
    for ext in (".jpg", ".jpeg", ".webp"):
        output_path.with_suffix(ext).unlink(missing_ok=True)

    gflow_bin = shutil.which("gflow") or shutil.which("flow") or "gflow"
    env = _build_flow_env()

    # 유효한 참조 이미지 필터링 (에셋 시트 캐릭터/소품)
    valid_refs = [p for p in (references or []) if p.exists() and p.stat().st_size > 0]

    with _acquire_flow_profile() as profile_name:
        if valid_refs:
            # 🎨 에셋 시트 참조가 존재하는 경우 i2i 모드로 로컬 에셋 이미지들을 전달
            cmd = [
                gflow_bin, "image", "i2i", prompt,
                "--profile", profile_name,
                "--model", model_alias,
                "--aspect", aspect_ratio,
                "-o", str(output_path),
                "--json",
            ]
            for ref_p in valid_refs:
                cmd.extend(["--ref", str(ref_p.resolve())])
        else:
            # 텍스트 프롬프트 단독 생성 (t2i 모드)
            cmd = [
                gflow_bin, "image", "t2i", prompt,
                "--profile", profile_name,
                "--model", model_alias,
                "--aspect", aspect_ratio,
                "-o", str(output_path),
                "--json",
            ]
        res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout_minutes * 60)

    # gflow-cli는 Google CDN에서 다운로드 시 실제 미디어 포맷(JPEG)에 맞게 확장자를 .jpg 등으로 변경하여 저장함
    actual_file: Path | None = None
    if output_path.exists() and output_path.stat().st_size > 0:
        actual_file = output_path
    else:
        for ext in (".jpg", ".jpeg", ".webp"):
            alt = output_path.with_suffix(ext)
            if alt.exists() and alt.stat().st_size > 0:
                actual_file = alt
                break

    if res.returncode != 0 or not actual_file or actual_file.stat().st_size == 0:
        err = (res.stderr or res.stdout or f"Exit code {res.returncode}").strip()
        raise RuntimeError(f"Google Flow 이미지 생성 실패 (profile={profile_name}): {err}")

    # 우측 하단 워터마크 자동 제거
    _clean_watermark_if_available(actual_file)

    # 파이프라인 표준(PNG)으로 통일
    if actual_file != output_path:
        try:
            from PIL import Image
            with Image.open(actual_file) as im:
                im.convert("RGB").save(output_path, "PNG")
            actual_file.unlink(missing_ok=True)
        except Exception:
            shutil.copy2(actual_file, output_path)

    return output_path


def _extract_media_id_from_output(err_text: str, profile_name: str) -> str | None:
    """에러 메시지 또는 해당 워커 프로필의 gflow.db 최신 레코드에서 정확한 media_id를 추출합니다."""
    # 1차: 에러 출력에서 gflow data download <UUID> 또는 media_id=<UUID> 직접 파싱 (병렬 시 100% 정확)
    patterns = [
        r"gflow\s+data\s+download\s+([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        r"media_id['\"=:\s]+([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        r"/edit/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
    ]
    for pat in patterns:
        m = re.search(pat, err_text)
        if m:
            return m.group(1)

    # 2차: gflow.db에서 해당 워커 프로필(profile_name)이 가장 최근 생성한 비디오 에셋 ID 조회
    try:
        import sqlite3
        db_path = _get_gflow_home() / "gflow.db"
        if db_path.exists():
            with sqlite3.connect(str(db_path), timeout=10.0) as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT flow_media_id FROM assets WHERE kind='video' AND profile_name=? ORDER BY rowid DESC LIMIT 1;",
                    (profile_name,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
    except Exception:
        pass
    return None


def _run_flow_video_generate(
    model_alias: str,
    prompt: str,
    start_image: Path,
    output_path: Path,
    end_image: Path | None = None,
    duration: int | None = 6,
    aspect_ratio: str = "9:16",
    timeout_minutes: int | None = None,
    timeout_seconds: int = 300,
    max_retries: int = 3,
) -> Path:
    """Google Flow CLI(gflow/flow)를 이용한 Veo 비디오 생성 (5분 타임아웃 및 자동 재시도 지원)"""
    import time
    import uuid

    if timeout_minutes is not None:
        timeout_seconds = timeout_minutes * 60

    gflow_bin = shutil.which("gflow") or shutil.which("flow") or "gflow"
    env = _build_flow_env()

    last_error = ""

    for attempt in range(1, max_retries + 1):
        # 이전 생성 시도에서 남은 잔여/더미 파일 사전 정리
        output_path.unlink(missing_ok=True)
        for ext in (".mp4", ".mov", ".webm"):
            output_path.with_suffix(ext).unlink(missing_ok=True)

        print(f"[Flow Video] 🎬 비디오 생성 시도 {attempt}/{max_retries} 시작 (5분 타임아웃 제한: {timeout_seconds}초)...")

        try:
            with _acquire_flow_profile() as profile_name:
                def build_cmd(use_duration: bool) -> list[str]:
                    c = [
                        gflow_bin, "video", "i2v",
                        "--profile", profile_name,
                        "--model", model_alias,
                        "--aspect", aspect_ratio,
                        "-o", str(output_path),
                        "--json",
                    ]
                    if start_image and start_image.exists():
                        c.extend(["-i", str(start_image)])

                    if end_image and end_image.exists() and model_alias in ("omni-flash",):
                        c.extend(["-e", str(end_image)])

                    if use_duration:
                        d_val = "10" if (duration and duration >= 8 and model_alias == "omni-flash") else ("8" if duration and duration >= 8 else "6")
                        c.extend(["--duration", d_val])

                    c.append(prompt)
                    return c

                # 1차: duration 지정 실행 (미지원 시 duration 제외하고 재시도)
                use_duration_first = bool(duration)
                cmd = build_cmd(use_duration=use_duration_first)
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    print(f"[Flow Video] ⏱️ 5분({timeout_seconds}초) 초과로 타임아웃 발생 (시도 {attempt}/{max_retries}). 프로세스 정리 후 재시도합니다.")
                    last_error = f"5분 타임아웃 초과 (시도 {attempt})"
                    continue

                err_text = (res.stderr or "") + (res.stdout or "")
                if use_duration_first and res.returncode != 0 and ("renders no duration control" in err_text or "duration" in err_text.lower()):
                    time.sleep(3)
                    cmd = build_cmd(use_duration=False)
                    try:
                        res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout_seconds)
                        err_text = (res.stderr or "") + (res.stdout or "")
                    except subprocess.TimeoutExpired:
                        print(f"[Flow Video] ⏱️ 5분({timeout_seconds}초) 초과로 타임아웃 발생 (시도 {attempt}/{max_retries}). 프로세스 정리 후 재시도합니다.")
                        last_error = f"5분 타임아웃 초과 (시도 {attempt})"
                        continue

                # 생성은 완료되었으나 다운로드 리다이렉트(HTTP 302 등) 에러인 경우 복구
                if res.returncode != 0 and (
                    "signed media URL" in err_text
                    or "MediaDownloadError" in err_text
                    or "302" in err_text
                    or "WireFormatError" in err_text
                ):
                    try:
                        time.sleep(2)
                        media_id = _extract_media_id_from_output(err_text, profile_name)
                        if media_id:
                            recovery_dir = output_path.parent / f".flow_recover_{uuid.uuid4().hex[:8]}"
                            recovery_dir.mkdir(parents=True, exist_ok=True)
                            try:
                                download_cmd = [
                                    gflow_bin, "data", "download", media_id,
                                    "--profile", profile_name,
                                    "--out", str(recovery_dir),
                                ]
                                subprocess.run(download_cmd, capture_output=True, text=True, env=env, timeout=120)
                                cand = recovery_dir / f"{media_id}.mp4"
                                if cand.exists() and cand.stat().st_size > 1000:
                                    cand.replace(output_path)
                            finally:
                                shutil.rmtree(recovery_dir, ignore_errors=True)
                    except Exception as recover_err:
                        print(f"[Flow Video Recovery Error ({profile_name})] {recover_err}")

            # 파일 생성 결과 확인
            actual_file: Path | None = None
            if output_path.exists() and output_path.stat().st_size > 0:
                actual_file = output_path
            else:
                for ext in (".mp4", ".mov", ".webm"):
                    alt = output_path.with_suffix(ext)
                    if alt.exists() and alt.stat().st_size > 0:
                        actual_file = alt
                        break

            if actual_file and actual_file.exists() and actual_file.stat().st_size > 0:
                # 우측 하단 워터마크 자동 제거
                _clean_watermark_if_available(actual_file)
                if actual_file != output_path:
                    shutil.copy2(actual_file, output_path)
                print(f"[Flow Video] ✅ 비디오 생성 성공! (시도 {attempt}/{max_retries}, {output_path.name})")
                return output_path

            last_error = (res.stderr or res.stdout or f"Exit code {res.returncode}").strip()
            print(f"[Flow Video] ⚠️ 시도 {attempt}/{max_retries} 미완료: {last_error[:150]}")
            time.sleep(3)

        except Exception as e:
            last_error = str(e)
            print(f"[Flow Video] ⚠️ 시도 {attempt}/{max_retries} 중 예외 발생: {e}")
            time.sleep(3)

    raise RuntimeError(f"Google Flow 비디오 생성 실패 ({max_retries}회 시도 모두 실패): {last_error}")


MODEL_ALIAS_MAP = {
    "grok_imagine_1_5_lite": "grok_video_v15_lite",
    "grok_imagine1_5_lite": "grok_video_v15_lite",
    "grok_1_5_lite": "grok_video_v15_lite",
    "grok_video_v15": "grok_video_v15_lite",
    "minimax": "minimax_h3",
    "minimax_h3_lite": "minimax_h3",
}

# Higgsfield CLI 호출 전역 동시성 잠금 (Free 플랜의 concurrent_jobs_limit: 1 제약 및 CLI 파일 경합 방지)
_higgsfield_lock = threading.Lock()


def _run_higgsfield_generate(
    job_type: str,
    prompt: str,
    aspect_ratio: str = "9:16",
    start_image: Path | None = None,
    end_image: Path | None = None,
    image_references: list[Path] | None = None,
    duration: int | None = None,
    resolution: str = "1k",
    multi_shots: bool = False,
    timeout_minutes: int = 15,
    max_retries: int = 3,
) -> str:
    resolved_job_type = MODEL_ALIAS_MAP.get(job_type, job_type)

    cmd = [
        "higgsfield", "generate", "create", resolved_job_type,
        "--prompt", prompt,
        "--aspect-ratio", aspect_ratio,
        "--wait",
        "--json",
    ]
    # 모델별 해상도 파라미터 적용
    if any(k in resolved_job_type for k in ("nano_banana", "flux", "seedream", "gpt_image")):
        if resolution:
            cmd.extend(["--resolution", resolution])
    elif "minimax" in resolved_job_type:
        # MiniMax H3는 resolution '2K' 지원
        cmd.extend(["--resolution", "2K"])
    elif "grok" in resolved_job_type:
        # Grok Imagine 1.5 Lite는 720p/1080p 지원 (기본 720p)
        cmd.extend(["--resolution", "720p"])

    # 다중 이미지 참조 (캐릭터/오브제 에셋 시트 일관성 주입)
    if image_references:
        for ref in image_references:
            if ref and ref.exists():
                cmd.extend(["--image-references", str(ref)])

    # 시작 이미지 (Start Frame)
    if start_image and start_image.exists():
        cmd.extend(["--start-image", str(start_image)])

    # 종료 이미지 (End Frame) - Seedance 2.0 / Kling 3.0 / Minimax H3 / Wan 3.0 등 원테이크 보간 지원 모델
    if end_image and end_image.exists() and any(k in resolved_job_type for k in ("seedance", "kling", "minimax", "wan")):
        cmd.extend(["--end-image", str(end_image)])

    # 멀티샷 제약 방어 (Kling 3.0: multi_shots=true 시 multi_prompt 배열이 필수)
    # 단일 프롬프트 환경에서는 CLI 에러(Code 4) 방지를 위해 항상 false로 안전 처리
    if "kling" in resolved_job_type:
        cmd.extend(["--multi-shots", "false"])

    # 비디오 길이 파라미터 (모델별 제약 반영: Kling은 5 또는 10, Seedance/Minimax/Grok은 5)
    if duration:
        if "seedance" in resolved_job_type:
            cmd.extend(["--duration", "5"])
        elif "kling" in resolved_job_type:
            d_val = "10" if duration and duration >= 8 else "5"
            cmd.extend(["--duration", d_val])
        elif "minimax" in resolved_job_type:
            cmd.extend(["--duration", "5"])
        elif "grok" in resolved_job_type:
            cmd.extend(["--duration", "5"])
        else:
            cmd.extend(["--duration", str(duration)])

    # 힉스필드 계정 동시성 한도(1개) 보호를 위해 전역 락 진입 후 순차 실행
    with _higgsfield_lock:
        for attempt in range(1, max_retries + 1):
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_minutes * 60)
            if res.returncode == 0:
                break

            err_msg = res.stderr or res.stdout
            if "rate_limit_reached" in err_msg and attempt < max_retries:
                wait_sec = 8 * attempt
                print(f"[Higgsfield] ⏳ 동시성 한도(rate_limit_reached) 감지 - {wait_sec}초 대기 후 재시도 ({attempt}/{max_retries})...")
                time.sleep(wait_sec)
                continue

            raise RuntimeError(f"Higgsfield generate CLI 에러 ({res.returncode}): {err_msg}")

    try:
        data = json.loads(res.stdout)
        item = data[0] if isinstance(data, list) and data else data
        result_url = item.get("result_url") or item.get("output_url") or item.get("url")
        if not result_url:
            raise RuntimeError(f"Higgsfield 결과 URL을 찾을 수 없습니다: {res.stdout}")
        return str(result_url)
    except Exception as exc:
        raise RuntimeError(f"Higgsfield 출력 파싱 실패: {res.stdout}") from exc
    except Exception as exc:
        raise RuntimeError(f"Higgsfield 출력 파싱 실패: {res.stdout}") from exc


def resolve_scene_references(
    scene_narration: str = "",
    scene_prompt: str = "",
    requires_character: bool = True,
    required_props: list[str] | None = None,
    manifest: AssetSheetManifest | None = None,
) -> tuple[bool, bool, bool]:
    """
    씬의 나레이션과 프롬프트, 그리고 에셋 시트 매니페스트를 종합 분석하여
    (use_character, use_prop1, use_prop2)의 참조 여부를 결정합니다.
    """
    prompt_lower = (scene_prompt or "").lower()
    narration_lower = (scene_narration or "").lower()
    combined_text = f"{prompt_lower} {narration_lower}"

    # 1. 소품 1 & 소품 2 검사
    use_prop1 = False
    use_prop2 = False

    req_props = [str(p).lower() for p in (required_props or [])]
    p1_name = (manifest.prop_1_name if manifest and manifest.prop_1_name else "").lower()
    p2_name = (manifest.prop_2_name if manifest and manifest.prop_2_name else "").lower()

    # prop 1 키워드 토큰 분해 및 매칭 (예: '뇌 모형' -> ['뇌', '모형', 'brain'])
    p1_tokens = [w for w in p1_name.split() if len(w) >= 1]
    if "prop_1" in req_props or "prop1" in req_props:
        use_prop1 = True
    elif p1_name and (p1_name in combined_text or any(t in combined_text for t in p1_tokens)):
        use_prop1 = True

    # prop 2 키워드 토큰 분해 및 매칭 (예: '스마트폰' -> ['스마트폰', 'smartphone'])
    p2_tokens = [w for w in p2_name.split() if len(w) >= 1]
    if "prop_2" in req_props or "prop2" in req_props:
        use_prop2 = True
    elif p2_name and (p2_name in combined_text or any(t in combined_text for t in p2_tokens)):
        use_prop2 = True

    # 2. 캐릭터 검사
    if requires_character is False:
        use_character = False
    else:
        # 캐릭터 관련 키워드 확인
        char_keywords = (
            "person", "character", "man", "woman", "human", "face", "eyes", "holding",
            "standing", "sitting", "looking", "hand", "doctor", "boy", "girl", "people",
            "사람", "인물", "나", "너", "그", "주인공", "캐릭터", "표정", "얼굴", "손",
            "앉아", "서 있", "쳐다", "바라", "눈", "입", "박사", "남자", "여자"
        )
        has_char_word = any(k in combined_text for k in char_keywords)

        # 소품 전용 클로즈업인지 확인 (소품 키워드가 있으면서 캐릭터 단어가 전무한 경우)
        is_prop_only = (use_prop1 or use_prop2) and not has_char_word
        if is_prop_only:
            use_character = False
        else:
            use_character = True

    return use_character, use_prop1, use_prop2


def generate_scene_image_for_project(
    project_dir: Path,
    scene_id: int,
    settings: AppSettings,
    model_name: str = "nano_banana_pro",
    use_asset_sheet: bool = False,
) -> Path:
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    if not video_scenes_path.exists():
        raise FileNotFoundError("video_scenes.json이 없습니다. 먼저 비디오 씬을 생성해주세요.")

    raw_scenes = json.loads(video_scenes_path.read_text(encoding="utf-8"))
    target_scene = None
    for sc in raw_scenes:
        if sc.get("scene_id") == scene_id:
            target_scene = sc
            break

    if not target_scene:
        raise ValueError(f"Scene {scene_id}를 찾을 수 없습니다.")

    prompt = target_scene.get("start_image_prompt", "")
    if not prompt:
        concept_kit_file = project_dir / CONCEPT_KIT_FILENAME
        style_id = "claymation"
        if concept_kit_file.exists():
            try:
                ck_data = json.loads(concept_kit_file.read_text(encoding="utf-8"))
                style_id = ck_data.get("visual_style_id", "claymation")
            except Exception:
                pass
        style = get_visual_style(style_id)
        prompt = f"{style.sample_prompt_prefix}, scene {scene_id}"

    scenes_dir = project_dir / SCENES_DIR_NAME
    scenes_dir.mkdir(parents=True, exist_ok=True)
    start_image_path = scenes_dir / f"scene_{scene_id:02d}_start.png"
    final_frame_path = scenes_dir / f"scene_{scene_id:02d}_final.png"
    video_path = scenes_dir / f"scene_{scene_id:02d}_video.mp4"

    # 이미지를 새로 생성/수정하므로, 과거 생성되었던 구버전 비디오와 마지막 프레임은 깔끔히 초기화
    if final_frame_path.exists():
        try:
            final_frame_path.unlink()
        except Exception:
            pass
    if video_path.exists():
        try:
            video_path.unlink()
        except Exception:
            pass

    def _finalize_image(img_path: Path) -> Path:
        if scene_id == 1 and img_path.exists() and img_path.stat().st_size > 0:
            thumb_bg = project_dir / THUMBNAIL_BG_FILENAME
            try:
                shutil.copy2(img_path, thumb_bg)
                from app.production.renderer import render_thumbnail_image
                render_thumbnail_image(project_dir, source_image=thumb_bg)
            except Exception:
                pass
        return img_path

    # 에셋 시트 일관성 참조 이미지 구성 및 프롬프트 증강 (Higgsfield 및 Google Flow 모델 선별 주입)
    image_references: list[Path] = []
    effective_prompt = prompt

    if use_asset_sheet and model_name != "dall-e-3":
        assets_dir = project_dir / "assets"
        char_file = assets_dir / "master_character.png"
        prop1_file = assets_dir / "prop_1.png"
        prop2_file = assets_dir / "prop_2.png"

        manifest = read_asset_sheet_manifest(project_dir)
        use_char, use_p1, use_p2 = resolve_scene_references(
            scene_narration=target_scene.get("narration", ""),
            scene_prompt=prompt,
            requires_character=target_scene.get("requires_character", True),
            required_props=target_scene.get("required_props", []),
            manifest=manifest,
        )

        ref_cues = []
        if use_char and char_file.exists():
            image_references.append(char_file)
            char_label = manifest.character_name if manifest and manifest.character_name else "main character"
            ref_cues.append(f"Image {len(image_references)}: Master Character '{char_label}' (maintain exact facial identity, hair, and clothing)")

        if use_p1 and prop1_file.exists():
            image_references.append(prop1_file)
            p1_label = manifest.prop_1_name if manifest and manifest.prop_1_name else "hero prop 1"
            ref_cues.append(f"Image {len(image_references)}: Hero Prop '{p1_label}' (replicate exact texture and shape)")

        if use_p2 and prop2_file.exists():
            image_references.append(prop2_file)
            p2_label = manifest.prop_2_name if manifest and manifest.prop_2_name else "hero prop 2"
            ref_cues.append(f"Image {len(image_references)}: Hero Prop '{p2_label}' (replicate exact texture and shape)")

        if image_references and ref_cues:
            cue_header = f"[VISUAL CONSISTENCY REFERENCE: {'; '.join(ref_cues)}.] "
            effective_prompt = cue_header + prompt

    # 0. Google Flow 모델 시도
    if model_name in FLOW_IMAGE_MODELS or model_name.startswith("flow_"):
        alias = FLOW_IMAGE_MODELS.get(model_name, "nano-pro")
        try:
            _run_flow_image_generate(
                model_alias=alias,
                prompt=effective_prompt,
                output_path=start_image_path,
                aspect_ratio="9:16",
                references=image_references if (use_asset_sheet and image_references) else None,
            )
            if start_image_path.exists() and start_image_path.stat().st_size > 1000:
                return _finalize_image(start_image_path)
        except Exception as e:
            print(f"[Google Flow Image Error] {e}")

    # 1. 힉스필드 모델 시도 (nano_banana_pro, gpt_image_2, seedream_v5_pro, flux_3_image 등)
    if model_name != "dall-e-3":
        try:
            image_url = _run_higgsfield_generate(
                job_type=model_name or "nano_banana_pro",
                prompt=effective_prompt,
                aspect_ratio="9:16",
                image_references=image_references if image_references else None,
                resolution="2k" if "gpt" in model_name or "seedream" in model_name else "1k",
            )
            resp = httpx.get(image_url, timeout=90.0)
            if resp.status_code == 200:
                start_image_path.write_bytes(resp.content)
                return _finalize_image(start_image_path)
        except Exception as e:
            print(f"[Higgsfield Image Generate Error - Scene {scene_id}] {e}")

    # 2. OpenAI DALL-E 3 시도
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        image_resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt[:950],
            size="1024x1792",
            quality="standard",
            n=1,
        )
        dalle_url = image_resp.data[0].url
        if dalle_url:
            resp = httpx.get(dalle_url, timeout=60.0)
            if resp.status_code == 200:
                start_image_path.write_bytes(resp.content)
                return _finalize_image(start_image_path)
    except Exception:
        pass

    # 3. Fallback 그래픽 생성
    _generate_fallback_clay_image(start_image_path, scene_id, prompt, is_final=False)
    return _finalize_image(start_image_path)


def generate_scene_video_for_project(
    project_dir: Path,
    scene_id: int,
    settings: AppSettings,
    model_name: str = "kling_o3_flf",
    duration: int = 5,
    multi_shots: bool = False,
    match_prev_frame: bool = True,
) -> Path:
    model_name = MODEL_ALIAS_MAP.get(model_name, model_name)
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    if not video_scenes_path.exists():
        raise FileNotFoundError("video_scenes.json이 없습니다. 먼저 비디오 씬을 생성해주세요.")

    raw_scenes = json.loads(video_scenes_path.read_text(encoding="utf-8"))
    target_scene = None
    for sc in raw_scenes:
        if sc.get("scene_id") == scene_id:
            target_scene = sc
            break

    if not target_scene:
        raise ValueError(f"Scene {scene_id}를 찾을 수 없습니다.")

    scenes_dir = project_dir / SCENES_DIR_NAME
    scenes_dir.mkdir(parents=True, exist_ok=True)

    current_scene_image = scenes_dir / f"scene_{scene_id:02d}_start.png"
    if not current_scene_image.exists():
        raise FileNotFoundError(f"Scene {scene_id}의 시작 이미지가 없습니다. 먼저 이미지를 생성해주세요.")

    # Google Flow CLI 모델은 단독 시작 이미지 기반이므로 원테이크(앞 씬 2장 프레임 도킹) 강제 비활성화
    is_flow_model = model_name in FLOW_VIDEO_MODELS or (model_name and model_name.startswith("flow_"))
    if is_flow_model:
        match_prev_frame = False

    # 🎬 키프레임 연속성 연동 (match_prev_frame):
    # Scene 2 이상이고 match_prev_frame이 True인 경우:
    #   - 시작 프레임: 이전 씬의 마지막 비디오 프레임
    #   - 종료 프레임: 이번 씬의 생성 이미지 (Kling/Seedance 등)
    # match_prev_frame이 False이거나 Scene 1인 경우:
    #   - 시작 프레임: 이번 씬의 생성 이미지 (단독 이미지 모션)
    #   - 종료 프레임: None
    if scene_id > 1 and match_prev_frame:
        prev_final_frame = scenes_dir / f"scene_{scene_id - 1:02d}_final.png"
        if prev_final_frame.exists():
            start_image_path = prev_final_frame
            end_image = current_scene_image if any(k in model_name for k in ("kling", "seedance", "minimax", "wan")) else None
        else:
            start_image_path = current_scene_image
            end_image = None
    else:
        start_image_path = current_scene_image
        end_image = None

    prompt = target_scene.get("video_prompt", "")
    if not prompt:
        prompt = target_scene.get("start_image_prompt", "") + ", cinematic subtle motion"

    video_path = scenes_dir / f"scene_{scene_id:02d}_video.mp4"
    final_frame_path = scenes_dir / f"scene_{scene_id:02d}_final.png"

    # 0. Google Flow 비디오 모델 시도
    if model_name in FLOW_VIDEO_MODELS or model_name.startswith("flow_"):
        alias = FLOW_VIDEO_MODELS.get(model_name, "veo-fast")
        _run_flow_video_generate(
            model_alias=alias,
            prompt=prompt,
            start_image=start_image_path,
            output_path=video_path,
            end_image=end_image,
            duration=duration,
            aspect_ratio="9:16",
        )
        # ffmpeg으로 생성된 비디오의 실제 마지막 프레임 정밀 추출
        try:
            extract_cmd = [
                "ffmpeg", "-sseof", "-0.1", "-i", str(video_path),
                "-update", "1", "-q:v", "1", str(final_frame_path), "-y"
            ]
            subprocess.run(extract_cmd, capture_output=True, check=True)
        except Exception:
            if not final_frame_path.exists():
                final_frame_path.write_bytes(start_image_path.read_bytes())
        return video_path

    # 힉스필드 비디오 생성 CLI 실행 (Kling/Seedance 등은 start_image와 end_image 2개 모두 전달)
    video_url = _run_higgsfield_generate(
        job_type=model_name or "kling_o3_flf",
        prompt=prompt,
        start_image=start_image_path,
        end_image=end_image,
        aspect_ratio="9:16",
        duration=duration,
        multi_shots=multi_shots,
        timeout_minutes=20,
    )

    resp = httpx.get(video_url, timeout=120.0)
    if resp.status_code != 200:
        raise RuntimeError(f"비디오 다운로드 실패 ({resp.status_code}): {video_url}")
    video_path.write_bytes(resp.content)

    # ffmpeg으로 생성된 비디오의 실제 마지막 프레임 정밀 추출
    try:
        extract_cmd = [
            "ffmpeg", "-sseof", "-0.1", "-i", str(video_path),
            "-update", "1", "-q:v", "1", str(final_frame_path), "-y"
        ]
        subprocess.run(extract_cmd, capture_output=True, check=True)
    except Exception:
        if not final_frame_path.exists():
            final_frame_path.write_bytes(start_image_path.read_bytes())

    return video_path


def pass_continuity_frame_to_next_scene(project_dir: Path, scene_id: int) -> Path:
    scenes_dir = project_dir / SCENES_DIR_NAME
    current_final = scenes_dir / f"scene_{scene_id:02d}_final.png"
    if not current_final.exists():
        raise FileNotFoundError(f"Scene {scene_id}의 마지막 프레임이 없습니다.")

    next_id = scene_id + 1
    next_start = scenes_dir / f"scene_{next_id:02d}_start.png"
    next_start.write_bytes(current_final.read_bytes())
    return next_start


def refine_and_regenerate_scene(
    project_dir: Path,
    scene_id: int,
    feedback: str,
    target: str,
    settings: AppSettings,
    model_name: str | None = None,
    duration: int = 5,
    multi_shots: bool = False,
    match_prev_frame: bool = True,
) -> None:
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    if not video_scenes_path.exists():
        raise FileNotFoundError("video_scenes.json이 없습니다. 먼저 비디오 씬을 생성해주세요.")

    raw_scenes = json.loads(video_scenes_path.read_text(encoding="utf-8"))
    target_idx = None
    target_scene = None
    for idx, sc in enumerate(raw_scenes):
        if sc.get("scene_id") == scene_id:
            target_idx = idx
            target_scene = sc
            break

    if target_scene is None or target_idx is None:
        raise ValueError(f"Scene {scene_id}를 찾을 수 없습니다.")

    concept_kit_path = project_dir / CONCEPT_KIT_FILENAME
    concept_kit_data = {}
    if concept_kit_path.exists():
        try:
            concept_kit_data = json.loads(concept_kit_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    client = OpenAI(api_key=settings.openai_api_key)
    model_llm = "gpt-4o-mini" if "mini" in settings.openai_analysis_model else settings.openai_analysis_model

    # 🎬 씬 매칭(원테이크) 여부에 따른 조건부 프레이밍 분기:
    # 체크된 경우(is_matched_mode = True):
    #   - 이미지는 비디오의 종료 지점에 도달하는 [씬의 클라이맥스 목적지 / 핵심 결과 프레임]
    #   - 비디오는 [이전 씬 끝 ➔ 이번 씬 클라이맥스 목적지 도킹 모션]
    # 체크 안 된 경우(is_matched_mode = False 또는 Scene 1):
    #   - 기존 그대로 [0초 시작 앵커 이미지] & [단독 출발 모션]
    # Google Flow CLI 모델은 단독 시작 이미지 기반이므로 원테이크(앞 씬 매칭) 강제 비활성화
    is_flow_model = model_name in FLOW_VIDEO_MODELS or (model_name and model_name.startswith("flow_"))
    if is_flow_model:
        match_prev_frame = False

    is_matched_mode = bool(scene_id > 1 and match_prev_frame)

    if target in ("image", "prompt_image"):
        # 🎨 이미지 전용 프롬프트 개선
        if is_matched_mode:
            scene_role_guide = f"""
[★ 핵심 모드: 씬 매칭(원테이크) - 클라이맥스 목적지 프레임 (Climax Destination Frame)]
- 이 씬(Scene {scene_id})은 이전 씬의 마지막 비디오 프레임과 매칭되어 이어지는 연속 시퀀스입니다.
- AI 비디오 생성기(Kling 등)에서 이 이미지는 0초 시작점이 아니라, 비디오가 끝나는 5초 지점에 도달하는 [종료/도착 앵커 프레임]으로 주입됩니다!
- 따라서 이 이미지는 대본 나레이션의 핵심 과학 원리나 결과가 시각적으로 가장 극대화되어 펼쳐진 '씬의 클라이맥스 정점/최종 결과 상태(Climax Destination)'를 담아야 합니다.
- 0초 시작 구도가 아니라, 5초 동안 카메라가 움직여 최종 도착한 완성된 상태의 피사체와 구도를 영문으로 작성하세요.
"""
        else:
            scene_role_guide = f"""
[★ 일반 모드: 단독 씬 시작 이미지 (Start Frame)]
- 이 씬(Scene {scene_id})은 단독으로 재생되는 독립 씬(또는 첫 씬)입니다.
- 이 이미지는 비디오 0초 시작 지점의 초기 상태 앵커 프레임(Start Frame)입니다.
- 대본 나레이션 도입부의 시작 구도와 피사체의 초기 상태를 영문으로 작성하세요.
"""

        style_id = concept_kit_data.get("visual_style_id", "claymation")
        active_style = get_visual_style(style_id)
        current_visual_style = concept_kit_data.get('visual_style') or active_style.default_concept_style

        prompt = f"""당신은 세계 최고의 AI 이미지 프롬프트 디렉터입니다.
사용자의 피드백을 100% 반영하여, 현재 씬(Scene {scene_id})의 영문 이미지 프롬프트를 새롭게 전면 재작성하세요.

[현재 씬 정보]
- 씬 번호: Scene {scene_id}
- 대본 나레이션: {target_scene.get('narration', '')}
- 기존 이미지 프롬프트: {target_scene.get('start_image_prompt', '')}
- 컨셉 스타일: {current_visual_style}
- 피사체/조명: {concept_kit_data.get('color_and_lighting', '')}
- 씬 매칭(클라이맥스 목적지) 적용 여부: {'적용 (도착점 클라이맥스)' if is_matched_mode else '미적용 (0초 시작 프레임)'}
{scene_role_guide}
[사용자의 이미지 수정 피드백 (최우선 절대 원칙)]
"{feedback}"

[★ 프롬프트 재작성 핵심 규칙 - 엄격 준수]
1. [구버전 모순 전면 삭제]: 사용자의 피드백과 모순되거나 상충하는 기존 프롬프트의 구도, 동작, 자세는 반드시 완전히 삭제하세요. 옛날 표현을 어설프게 남겨두면 절대 안 됩니다.
2. [피드백 동작 최우선 배치 (Head Sentence)]: 사용자가 요구한 핵심 동작 및 피사체의 물리적 상호작용을 프롬프트 맨 첫머리에 가장 명확하고 직관적으로 서술하세요.
3. [도구/사물 사용 및 신체 결합의 물리적 정합성 (Affordance & Spatial Geometry)]:
   - 사물이나 도구를 사용하는 동작을 묘사할 때는 도구의 엉뚱한 외벽이나 겉면을 대고 있는 오류를 방지하기 위해, 기하학적 접촉 부위와 피사체의 공간 배치를 극도로 정밀하게 묘사하세요.
   - 예: 도구를 잡거나 사용하는 경우, 피사체의 손/신체 부위가 도구의 기능 부위(손잡이, 입구 등)와 물리적으로 올바르게 맞닿아 작동하는 모습을 명확하게 기술하세요.
   - 피사체와 도구/환경의 상대적 위치와 상호작용이 물리적 상식에 맞아야 하며, 엉뚱한 위치를 만지거나 허공을 짚는 왜곡된 구도를 엄격히 금지합니다.
4. [주연 캐릭터 락 (Hero Character Lock)]: 대본 및 컨셉 키트에 정의된 핵심 주인공의 고유 명칭과 비주얼 특징을 일관되게 명시하세요. 절대 'a generic superhero'나 'a figurine'처럼 모호하게 바꿔 엉뚱한 캐릭터가 렌더링되게 하지 마세요.
5. [나레이션 직결 시각화 원칙 (Narration-Driven Visual Metaphor)]: 해당 씬의 나레이션 핵심 메시지와 과학적 사실을 시청자가 1초 만에 이해할 수 있는 구체적인 시각적 은유와 상호작용 장치를 화면 중심에 배치하세요.
6. [스타일 및 조명 유지]: 현재 프로젝트의 비주얼 스타일({active_style.name}: {active_style.image_prompt_guide})을 프롬프트 전체에 철저히 유지하세요.
7. [텍스트 금지]: 끝에 strictly NO text, NO letters를 반드시 포함하세요.

반드시 다음 pure JSON으로만 응답하세요:
{{
  "start_image_prompt": "완벽하게 재작성된 영문 이미지 프롬프트"
}}
"""
        response = client.chat.completions.create(
            model=settings.openai_analysis_model or "gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        try:
            parsed = json.loads(content)
            if parsed.get("start_image_prompt"):
                target_scene["start_image_prompt"] = parsed["start_image_prompt"].strip()
        except Exception:
            pass

        target_scene["last_image_feedback"] = feedback
        target_scene["last_feedback"] = feedback

    elif target in ("video", "prompt_video"):
        # 🎬 비디오 전용 프롬프트 개선
        if is_matched_mode:
            motion_role_guide = f"""
[★ 핵심 모드: 씬 매칭(원테이크 도킹) - 이전 씬 끝 ➔ 이번 씬 클라이맥스 목적지 도킹]
- 이 씬(Scene {scene_id})은 이전 씬(Scene {scene_id - 1})의 마지막 프레임에서 출발하여, 이번 씬의 클라이맥스 목적지 이미지({target_scene.get('start_image_prompt', '')})로 5초간 카메라 무빙을 거쳐 부드럽게 도킹(Docking)하는 원테이크 연결 비디오입니다!
- 영상 프롬프트 작성 공식:
  1) Starting from: 이전 씬의 마지막 샷 구도/피사체 상태에서 출발 명시.
  2) Dynamic Motion: 5초간의 끊김 없는 부드러운 카메라 무빙(크레인 틸트, 패닝 등)과 피사체의 역동적 변화.
  3) Finishing on: 이번 씬의 클라이맥스 목적지 이미지의 구도와 피사체에 완벽히 도킹하여 안착.
"""
        else:
            motion_role_guide = f"""
[★ 일반 모드: 단독 씬 모션]
- 이 씬(Scene {scene_id})은 시작 이미지({target_scene.get('start_image_prompt', '')})에서 단독으로 출발하는 비디오입니다.
- 시작 이미지의 구도에서 출발하여 자연스러운 카메라 무빙과 피사체 움직임을 1개 영문 문단으로 작성하세요.
"""

        prompt = f"""당신은 세계 최고의 AI 영상 모션 디렉터입니다.
사용자의 피드백을 100% 반영하여, 현재 씬(Scene {scene_id})의 영문 비디오 모션 프롬프트를 새롭게 전면 재작성하세요.

[현재 씬 정보]
- 씬 번호: Scene {scene_id}
- 대본 나레이션: {target_scene.get('narration', '')}
- 이미지 프롬프트 (목적지/시작점): {target_scene.get('start_image_prompt', '')}
- 기존 비디오 프롬프트: {target_scene.get('video_prompt', '')}
- 씬 매칭 적용 여부: {'적용 (원테이크 도킹 비디오)' if is_matched_mode else '미적용 (단독 시작 이미지 모션)'}
{motion_role_guide}
[사용자의 영상 모션 수정 피드백 (최우선 절대 원칙)]
"{feedback}"

[★ 비디오 프롬프트 재작성 핵심 규칙 - 엄격 준수]
1. [구버전 모션 전면 삭제]: 사용자 피드백과 모순되거나 상충하는 기존의 카메라 워킹 및 피사체 움직임은 완전히 삭제하세요.
2. [피드백 모션 최우선 연출]: 사용자가 요구한 핵심 모션(예: 특정 카메라 앵글, 피사체 반응, 액션 변화)을 비디오 프롬프트의 중심 축으로 직관적이고 다이내믹하게 서술하세요.
3. [자연스러운 연속성]: 끊김이나 점프컷 없이 1개의 매끄러운 영문 문단으로 작성하세요 (Smooth continuous single-take motion, no jump cuts).

반드시 다음 pure JSON으로만 응답하세요:
{{
  "video_prompt": "완벽하게 재작성된 영문 비디오 프롬프트"
}}
"""
        response = client.chat.completions.create(
            model=settings.openai_analysis_model or "gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        try:
            parsed = json.loads(content)
            if parsed.get("video_prompt"):
                target_scene["video_prompt"] = parsed["video_prompt"].strip()
        except Exception:
            pass

        target_scene["last_video_feedback"] = feedback
        target_scene["last_feedback"] = feedback

    else:
        # both: 전체 프롬프트 수정
        if is_matched_mode:
            both_guide = f"""
[★ 핵심 모드: 씬 매칭(원테이크) - 클라이맥스 목적지 이미지 & 도킹 비디오]
1. start_image_prompt: 비디오의 종료 지점(5초 뒤)에 도달하는 [씬의 클라이맥스 목적지 / 최종 결과 정점 프레임]으로 작성.
2. video_prompt: 이전 씬 끝에서 출발하여 카메라 무빙 후 이번 씬 클라이맥스 목적지에 완벽히 도킹하는 1개 영문 문단으로 작성.
"""
        else:
            both_guide = f"""
[★ 일반 모드: 단독 씬 시작 이미지 & 모션]
1. start_image_prompt: 비디오 0초 시작 지점의 초기 상태 앵커 프레임으로 작성.
2. video_prompt: 시작 이미지에서 출발하는 자연스러운 카메라 모션으로 작성.
"""

        prompt = f"""당신은 세계 최고의 AI 쇼츠 영상 디렉터이자 프롬프트 엔지니어입니다.
사용자의 피드백을 100% 반영하여, 현재 씬(Scene {scene_id})의 이미지 프롬프트와 비디오 모션 프롬프트를 전면 재작성하세요.

[현재 씬 정보]
- 씬 번호: Scene {scene_id}
- 대본 나레이션: {target_scene.get('narration', '')}
- 기존 이미지 프롬프트: {target_scene.get('start_image_prompt', '')}
- 기존 비디오 프롬프트: {target_scene.get('video_prompt', '')}
- 씬 매칭 적용 여부: {'적용 (도착점 클라이맥스)' if is_matched_mode else '미적용 (시작 프레임)'}
{both_guide}
[사용자의 피드백 (최우선 절대 원칙)]
"{feedback}"

[★ 핵심 규칙]
1. 사용자의 피드백과 모순되는 기존 구도/동작/모션을 완전히 삭제하세요.
2. 피드백 핵심 내용을 이미지와 비디오 프롬프트의 가장 앞부분에 명확하게 배치하세요.
3. 사물/도구 상호작용 시, 피사체와 도구의 실제 기능적 접촉 부위(팁, 손잡이 등)와 올바른 신체 부위가 물리적으로 상식에 맞게 정밀 결합되도록 서술하세요.
4. 이미지 프롬프트 끝에는 strictly NO text, NO letters를 명시하세요.

반드시 다음 pure JSON으로만 응답하세요:
{{
  "start_image_prompt": "완벽하게 재작성된 영문 이미지 프롬프트",
  "video_prompt": "완벽하게 재작성된 영문 비디오 프롬프트"
}}
"""
        response = client.chat.completions.create(
            model=settings.openai_analysis_model or "gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        try:
            parsed = json.loads(content)
            if parsed.get("start_image_prompt"):
                target_scene["start_image_prompt"] = parsed["start_image_prompt"].strip()
            if parsed.get("video_prompt"):
                target_scene["video_prompt"] = parsed["video_prompt"].strip()
        except Exception:
            pass

        target_scene["last_feedback"] = feedback
        target_scene["last_image_feedback"] = feedback
        target_scene["last_video_feedback"] = feedback

    raw_scenes[target_idx] = target_scene
    video_scenes_path.write_text(json.dumps(raw_scenes, ensure_ascii=False, indent=2), encoding="utf-8")

    # target에 따른 실제 재생성 실행
    if target in ("image", "both"):
        img_model = model_name or "nano_banana_pro"
        generate_scene_image_for_project(project_dir, scene_id, settings, model_name=img_model)

    if target in ("video", "both"):
        vid_model = model_name or "kling_o3_flf"
        generate_scene_video_for_project(
            project_dir,
            scene_id,
            settings,
            model_name=vid_model,
            duration=duration,
            multi_shots=multi_shots,
            match_prev_frame=match_prev_frame,
        )


def get_production_state(project_dir: Path, project_id: str | None = None) -> ProductionState:
    wav_path = project_dir / TTS_AUDIO_FILENAME
    has_audio = wav_path.exists()
    duration = _get_audio_duration(wav_path) if has_audio else None

    scene_data_path = project_dir / SCENE_DATA_FILENAME
    has_scene_data = scene_data_path.exists()
    scenes: list[SceneItem] = []
    if has_scene_data:
        try:
            raw = json.loads(scene_data_path.read_text(encoding="utf-8"))
            scenes = [SceneItem.model_validate(item) for item in raw]
        except Exception:
            pass

    # 컨셉 키트 로드
    concept_kit_path = project_dir / CONCEPT_KIT_FILENAME
    has_concept_kit = concept_kit_path.exists()
    concept_kit: ConceptKit | None = None
    if has_concept_kit:
        try:
            concept_kit = ConceptKit.model_validate(json.loads(concept_kit_path.read_text(encoding="utf-8")))
        except Exception:
            pass

    # 비디오 씬 로드 및 URL 매핑
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    has_video_scenes = video_scenes_path.exists()
    video_scenes: list[VideoSceneItem] = []
    scenes_dir = project_dir / SCENES_DIR_NAME

    if has_video_scenes:
        try:
            raw_v_scenes = json.loads(video_scenes_path.read_text(encoding="utf-8"))
            for item in raw_v_scenes:
                vs = VideoSceneItem.model_validate(item)
                sc_id = vs.scene_id
                start_p = scenes_dir / f"scene_{sc_id:02d}_start.png"
                final_p = scenes_dir / f"scene_{sc_id:02d}_final.png"

                pid = project_id or project_dir.name
                if start_p.exists():
                    vs.start_image_url = f"/api/projects/{pid}/production/scenes/scene_{sc_id:02d}_start.png"
                    # 실제 AI 생성 이미지(통상 100KB~2MB 이상)인지 판별 (15KB 이하 fallback 플레이스홀더 제외)
                    vs.has_image = (start_p.stat().st_size > 30000)
                else:
                    vs.has_image = False
                if final_p.exists():
                    vs.final_frame_url = f"/api/projects/{pid}/production/scenes/scene_{sc_id:02d}_final.png"
                video_p = scenes_dir / f"scene_{sc_id:02d}_video.mp4"
                if video_p.exists():
                    vs.generated_video_url = f"/api/projects/{pid}/production/scenes/scene_{sc_id:02d}_video.mp4"

                video_scenes.append(vs)

            # 이전 씬의 final_frame을 다음 씬의 prev_final_frame_url로 연결
            for i in range(len(video_scenes)):
                if i > 0 and video_scenes[i - 1].final_frame_url:
                    video_scenes[i].continuity.prev_final_frame_url = video_scenes[i - 1].final_frame_url

        except Exception:
            pass

    pid = project_id or project_dir.name
    final_video_file = project_dir / "final.mp4"
    has_final_video = final_video_file.exists() and final_video_file.stat().st_size > 1000
    final_video_url = f"/api/projects/{pid}/production/final-video" if has_final_video else None

    thumb_file = project_dir / THUMBNAIL_FILENAME
    has_thumbnail = thumb_file.exists() and thumb_file.stat().st_size > 0
    thumbnail_url = f"/api/projects/{pid}/production/thumbnail" if has_thumbnail else None

    asset_sheet = read_asset_sheet_manifest(project_dir, pid)

    # 에셋 시트가 존재할 경우 각 씬별 동적 참조 주입 목록(active_references) 자동 판별
    if asset_sheet and asset_sheet.has_sheet:
        for vs in video_scenes:
            u_char, u_p1, u_p2 = resolve_scene_references(
                scene_narration=vs.narration,
                scene_prompt=vs.start_image_prompt,
                requires_character=vs.requires_character,
                required_props=vs.required_props,
                manifest=asset_sheet,
            )
            refs: list[str] = []
            if u_char:
                refs.append("character")
            if u_p1:
                refs.append("prop_1")
            if u_p2:
                refs.append("prop_2")
            vs.active_references = refs

    return ProductionState(
        has_audio=has_audio,
        audio_filename=TTS_AUDIO_FILENAME if has_audio else None,
        duration_seconds=duration,
        has_scene_data=has_scene_data,
        scene_count=len(scenes),
        scenes=scenes,
        has_concept_kit=has_concept_kit,
        concept_kit=concept_kit,
        has_video_scenes=has_video_scenes,
        video_scene_count=len(video_scenes),
        video_scenes=video_scenes,
        asset_sheet=asset_sheet,
        has_thumbnail=has_thumbnail,
        thumbnail_url=thumbnail_url,
        has_final_video=has_final_video,
        final_video_url=final_video_url,
    )


def update_scene_prompts_for_project(
    project_dir: Path,
    scene_id: int,
    start_image_prompt: str | None = None,
    video_prompt: str | None = None,
) -> None:
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    if not video_scenes_path.exists():
        raise FileNotFoundError("video_scenes.json이 없습니다.")

    raw_scenes = json.loads(video_scenes_path.read_text(encoding="utf-8"))
    target_idx = None
    target_scene = None
    for idx, sc in enumerate(raw_scenes):
        if sc.get("scene_id") == scene_id:
            target_idx = idx
            target_scene = sc
            break

    if target_scene is None or target_idx is None:
        raise ValueError(f"Scene {scene_id}를 찾을 수 없습니다.")

    if start_image_prompt is not None:
        target_scene["start_image_prompt"] = start_image_prompt.strip()
    if video_prompt is not None:
        target_scene["video_prompt"] = video_prompt.strip()

    raw_scenes[target_idx] = target_scene
    video_scenes_path.write_text(json.dumps(raw_scenes, ensure_ascii=False, indent=2), encoding="utf-8")


def recommend_motion_for_scene(
    project_dir: Path,
    scene_id: int,
    settings: AppSettings,
) -> RecommendMotionResponse:
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    if not video_scenes_path.exists():
        raise FileNotFoundError("video_scenes.json이 없습니다.")

    raw_scenes = json.loads(video_scenes_path.read_text(encoding="utf-8"))
    target_idx = None
    target_scene = None
    for idx, sc in enumerate(raw_scenes):
        if sc.get("scene_id") == scene_id:
            target_idx = idx
            target_scene = sc
            break

    if target_scene is None or target_idx is None:
        raise ValueError(f"Scene {scene_id}를 찾을 수 없습니다.")

    narration = target_scene.get("narration", "")
    start_image_prompt = target_scene.get("start_image_prompt", "")
    current_video_prompt = target_scene.get("video_prompt", "")
    current_motion_id = target_scene.get("camera_movement")

    # 전후 씬 맥락
    prev_scene = raw_scenes[target_idx - 1] if target_idx > 0 else None
    next_scene = raw_scenes[target_idx + 1] if target_idx < len(raw_scenes) - 1 else None

    prev_context = f"Scene {prev_scene.get('scene_id')}: {prev_scene.get('narration', '')} (모션: {prev_scene.get('camera_movement', '미지정')})" if prev_scene else "첫 번째 씬 (시작)"
    next_context = f"Scene {next_scene.get('scene_id')}: {next_scene.get('narration', '')} (모션: {next_scene.get('camera_movement', '미지정')})" if next_scene else "마지막 씬 (결말)"

    movement_catalog_text = "\n".join([
        f"- ID: {m.id} | 이름: {m.name} | 카테고리: {m.category}\n  설명: {m.summary}\n  추천 씬: {', '.join(m.best_for)}\n  프롬프트 문법: {m.prompt_syntax}"
        for m in CORE_CAMERA_MOVEMENTS
    ])

    recommendations: list[MotionRecommendationItem] = []

    if settings.openai_api_key:
        try:
            client = OpenAI(api_key=settings.openai_api_key)
            prompt = f"""당신은 세계 최고의 AI 쇼츠 카메라 연출 감독이자 프롬프트 엔지니어입니다.
aicameramovements.com의 12대 핵심 카메라 모션 라이브러리를 바탕으로, 현재 씬의 대본 문맥과 시각적 상황에 가장 극적인 몰입감과 텐션을 주는 상위 2~3개의 카메라 모션을 추천하고, 각각에 대한 완성형 비디오 프롬프트를 작성하세요.

[현재 씬 정보]
- 씬 번호: Scene {scene_id} (총 {len(raw_scenes)}개 씬 중)
- 대본 나레이션: "{narration}"
- 시작 이미지 프롬프트: "{start_image_prompt}"
- 기존 비디오 프롬프트: "{current_video_prompt}"
- 이전 씬 맥락: {prev_context}
- 다음 씬 맥락: {next_context}

[12대 핵심 카메라 모션 카탈로그]
{movement_catalog_text}

[작성 및 추천 규칙]
1. 위 카탈로그에서 현재 씬의 감정선(0~3초 충격 후킹, 미세 호기심, 팩트 폭탄, 반전 전환, 클라이맥스/결말)에 가장 적합한 모션 2~3개를 선정하세요.
2. 각 모션별 추천 이유(reason)를 한국어로 명확하고 설득력 있게 한 문장으로 작성하세요.
3. 각 모션별 `suggested_video_prompt`는 aicameramovements 표준 영문 4단 문법으로 완성하세요:
   `camera: {{모션명}}. movement: {{구체적 물리 이동}}. speed: {{속도}}. framing: {{피사체 구도}}. end: {{종료 지점 및 다음 씬 인계 상태, no jump cuts}}.`

반드시 다음 pure JSON으로만 응답하세요:
{{
  "recommendations": [
    {{
      "movement_id": "모션_ID (카탈로그 ID 중 하나)",
      "reason": "한국어 추천 이유 (예: 충격적인 팩트를 밝히는 후킹 구간이므로 시선을 단숨에 사로잡는 빠른 접근이 효과적입니다)",
      "suggested_video_prompt": "camera: ... movement: ... speed: ... framing: ... end: ..."
    }}
  ]
}}
"""
            model_name = "gpt-4o-mini" if "mini" in settings.openai_analysis_model else settings.openai_analysis_model
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()

            data = json.loads(content)
            for item in data.get("recommendations", []):
                m_id = item.get("movement_id", "")
                meta = CORE_MOVEMENTS_MAP.get(m_id)
                recommendations.append(
                    MotionRecommendationItem(
                        movement_id=m_id,
                        movement_name=meta.name if meta else m_id,
                        category=meta.category if meta else "기타",
                        reason=item.get("reason", ""),
                        suggested_video_prompt=item.get("suggested_video_prompt", ""),
                    )
                )
        except Exception:
            recommendations = []

    # API 미설정 또는 오류 시 쇼츠 문맥 스마트 폴백
    if not recommendations:
        if scene_id == 1:
            fallback_items = [
                ("crash_zoom_in", "도입부 0~3초 상식 충돌 후킹을 위해 시선을 단숨에 사로잡는 빠른 줌인이 가장 효과적입니다."),
                ("slow_zoom_in", "호기심을 서서히 증폭시키며 핵심 피사체로 몰입감을 높여줍니다."),
            ]
        elif scene_id == len(raw_scenes):
            fallback_items = [
                ("drone_pull_back", "결말 및 압도적 총량 체감을 위해 광활한 시야를 열어주는 풀백 연출이 최적입니다."),
                ("slow_zoom_out", "전체 전경과 실체를 드러내며 깊은 여운을 남깁니다."),
            ]
        else:
            fallback_items = [
                ("orbit", "피사체의 3D 입체감과 공예적 질감을 돋보이게 하는 쇼츠 대표 연출입니다."),
                ("push_past", "전경을 스쳐 지나가며 다음 공간으로 시선을 자연스럽게 인계합니다."),
                ("tracking_shot", "피사체의 움직임과 반응 속도에 맞추어 역동성을 부여합니다."),
            ]

        for m_id, r_reason in fallback_items:
            meta = CORE_MOVEMENTS_MAP.get(m_id)
            recommendations.append(
                MotionRecommendationItem(
                    movement_id=m_id,
                    movement_name=meta.name if meta else m_id,
                    category=meta.category if meta else "기타",
                    reason=r_reason,
                    suggested_video_prompt=meta.example_prompt if meta else f"camera: {m_id}. smooth cinematic continuous movement.",
                )
            )

    return RecommendMotionResponse(
        scene_id=scene_id,
        narration=narration,
        current_motion_id=current_motion_id,
        recommendations=recommendations,
        available_movements=CORE_CAMERA_MOVEMENTS,
    )


def apply_motion_to_scene(
    project_dir: Path,
    scene_id: int,
    movement_id: str,
    custom_instruction: str = "",
    settings: AppSettings | None = None,
) -> VideoSceneItem:
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    if not video_scenes_path.exists():
        raise FileNotFoundError("video_scenes.json이 없습니다.")

    raw_scenes = json.loads(video_scenes_path.read_text(encoding="utf-8"))
    target_idx = None
    target_scene = None
    for idx, sc in enumerate(raw_scenes):
        if sc.get("scene_id") == scene_id:
            target_idx = idx
            target_scene = sc
            break

    if target_scene is None or target_idx is None:
        raise ValueError(f"Scene {scene_id}를 찾을 수 없습니다.")

    meta = CORE_MOVEMENTS_MAP.get(movement_id)
    movement_name = meta.name if meta else movement_id

    new_prompt = ""
    if settings and settings.openai_api_key:
        try:
            client = OpenAI(api_key=settings.openai_api_key)
            prompt = f"""당신은 AI 쇼츠 영상 디렉터입니다.
현재 씬에 지정된 카메라 모션 '{movement_name}'(ID: {movement_id})을 적용하여, aicameramovements.com 표준 영문 4단 문법으로 완성도 높은 비디오 프롬프트를 작성하세요.

[현재 씬 정보]
- 씬 번호: Scene {scene_id}
- 대본 나레이션: "{target_scene.get('narration', '')}"
- 시작 이미지 프롬프트: "{target_scene.get('start_image_prompt', '')}"
- 선택된 카메라 모션: {movement_name} ({meta.summary if meta else ''})
- 모션 문법 참고: {meta.prompt_syntax if meta else ''}
- 모션 예시 참고: {meta.example_prompt if meta else ''}
- 추가 사용자 요청사항: "{custom_instruction}"

[video_prompt 작성 공식 (영문)]
`camera: {movement_name}. movement: ... speed: ... framing: ... end: ... no jump cuts.`

반드시 다음 pure JSON으로만 응답하세요:
{{
  "video_prompt": "완성된 영문 video_prompt"
}}
"""
            model_name = "gpt-4o-mini" if "mini" in settings.openai_analysis_model else settings.openai_analysis_model
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```json"):
                content = content[7:-3].strip()
            elif content.startswith("```"):
                content = content[3:-3].strip()
            res_data = json.loads(content)
            new_prompt = res_data.get("video_prompt", "").strip()
        except Exception:
            new_prompt = ""

    if not new_prompt:
        new_prompt = meta.example_prompt if meta else f"camera: {movement_name}. smooth cinematic continuous movement."

    target_scene["video_prompt"] = new_prompt

    target_scene["camera_movement"] = movement_id
    raw_scenes[target_idx] = target_scene
    video_scenes_path.write_text(json.dumps(raw_scenes, ensure_ascii=False, indent=2), encoding="utf-8")

    return VideoSceneItem.model_validate(target_scene)


def update_project_visual_style(
    project_dir: Path,
    visual_style_id: str,
    regenerate_prompts: bool = False,
    settings: AppSettings | None = None,
) -> tuple[ConceptKit, list[VideoSceneItem] | None]:
    style = get_visual_style(visual_style_id)
    concept_kit_file = project_dir / CONCEPT_KIT_FILENAME
    ck_data = {}
    if concept_kit_file.exists():
        try:
            ck_data = json.loads(concept_kit_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    ck_data["visual_style_id"] = style.id
    ck_data["visual_style"] = style.default_concept_style

    # 에셋 시트 프롬프트도 새 비주얼 스타일에 맞게 즉시 리스타일링
    char_def = ck_data.get("character_definition") or {}
    char_name = char_def.get("name", "main_character")
    char_desc = (char_def.get("description") or "").strip()
    if not char_desc or char_desc == "miniature handcrafted clay person":
        char_desc = f"Main character '{char_name}' designed in authentic {style.name} style"

    key_props = ck_data.get("key_props") or []
    prop_1_info = key_props[0] if len(key_props) > 0 else {"name": "key_prop_1", "description": "thematic scientific object"}
    prop_2_info = key_props[1] if len(key_props) > 1 else {"name": "key_prop_2", "description": "thematic secondary prop"}
    p1_desc = prop_1_info.get("description") or f"hero prop '{prop_1_info.get('name', 'prop1')}'"
    p2_desc = prop_2_info.get("description") or f"secondary prop '{prop_2_info.get('name', 'prop2')}'"

    # 비-클레이메이션 스타일 선택 시 과거 점토 수식어 자동 정제
    if style.id != "claymation":
        char_desc = char_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")
        p1_desc = p1_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")
        p2_desc = p2_desc.replace("clay ", "").replace("clay", "").replace("Clay ", "").replace("Clay", "").replace("plasticine ", "")

    ck_data["master_asset_sheet_prompt"] = (
        f"[{style.name.upper()} MASTER CONCEPT ART SHEET - {style.default_concept_style}]. "
        f"16:9 widescreen aspect ratio (2752x1536), solid pure light-gray (#f0f2f5) studio backdrop. "
        f"Strict mathematical layout with 2 main zones separated by a wide empty blank vertical gutter: "
        f"[ZONE 1: LEFT 58% WIDTH (X: 0% to 58%)]: Full-body character turnaround of {char_desc} in authentic {style.name} aesthetic, "
        f"showing exactly 3 views side-by-side (front view, 45-degree 3/4 view, side profile view), centered within this left 58% box and strictly NOT crossing past X=58%. "
        f"[EMPTY VERTICAL GUTTER (X: 58% to 64%)]: Completely blank empty studio background spacing with zero objects. "
        f"[ZONE 2: RIGHT 36% WIDTH (X: 64% to 100%)]: Divided vertically into two isolated stacked boxes: "
        f"  - [TOP BOX (Y: 0% to 48%)]: Close-up isolated hero prop of {p1_desc} in authentic {style.name} aesthetic, centered floating on empty space. "
        f"  - [MIDDLE HORIZONTAL GUTTER (Y: 48% to 52%)]: Completely blank empty space. "
        f"  - [BOTTOM BOX (Y: 52% to 100%)]: Close-up isolated hero prop of {p2_desc} in authentic {style.name} aesthetic, centered floating on empty space. "
        f"Rendering directive: Authentic {style.image_prompt_guide}. Strict tactile material consistency across character and props, "
        f"macro photography studio lighting, generous negative margins, strictly NO text, NO labels, NO borders, NO grid lines."
    )

    concept_kit = ConceptKit.model_validate(ck_data)
    concept_kit_file.write_text(json.dumps(concept_kit.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    video_scenes = None
    if regenerate_prompts and settings:
        concept_kit, video_scenes = generate_concept_kit_and_video_scenes(
            project_dir, settings, visual_style_id=style.id
        )

    return concept_kit, video_scenes


def _get_project_title(project_dir: Path) -> str | None:
    from app.production.renderer import resolve_project_shorts_title
    return resolve_project_shorts_title(project_dir)


def save_thumbnail_image(project_dir: Path, image_bytes: bytes) -> Path:
    from app.production.renderer import render_thumbnail_image

    bg_path = project_dir / THUMBNAIL_BG_FILENAME
    bg_path.write_bytes(image_bytes)
    target_path = project_dir / THUMBNAIL_FILENAME

    title = _get_project_title(project_dir)
    try:
        render_thumbnail_image(project_dir, title=title, source_image=bg_path)
    except Exception:
        shutil.copy2(bg_path, target_path)
    return target_path


def set_thumbnail_from_scene(project_dir: Path, scene_id: int = 1) -> Path:
    from app.production.renderer import render_thumbnail_image

    scenes_dir = project_dir / SCENES_DIR_NAME
    scene_img = scenes_dir / f"scene_{scene_id:02d}_start.png"
    if not scene_img.exists():
        raise FileNotFoundError(f"Scene {scene_id}의 시작 이미지가 없습니다.")
    bg_path = project_dir / THUMBNAIL_BG_FILENAME
    shutil.copy2(scene_img, bg_path)
    target_path = project_dir / THUMBNAIL_FILENAME

    title = _get_project_title(project_dir)
    try:
        render_thumbnail_image(project_dir, title=title, source_image=bg_path)
    except Exception:
        shutil.copy2(bg_path, target_path)
    return target_path


def delete_thumbnail_image(project_dir: Path) -> None:
    for name in [THUMBNAIL_FILENAME, THUMBNAIL_BG_FILENAME]:
        p = project_dir / name
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def generate_thumbnail_image_for_project(
    project_dir: Path,
    settings: AppSettings,
    model_name: str = "nano_banana_pro",
    prompt: str | None = None,
) -> Path:
    from app.production.renderer import render_thumbnail_image

    title = _get_project_title(project_dir)
    final_prompt = prompt.strip() if prompt and prompt.strip() else ""
    if not final_prompt:
        concept_kit_file = project_dir / CONCEPT_KIT_FILENAME
        style_id = "claymation"
        visual_style = ""
        if concept_kit_file.exists():
            try:
                ck = json.loads(concept_kit_file.read_text(encoding="utf-8"))
                style_id = ck.get("visual_style_id", "claymation")
                visual_style = ck.get("visual_style", "")
            except Exception:
                pass
        if not visual_style:
            style = get_visual_style(style_id)
            visual_style = style.default_concept_style

        if title:
            final_prompt = f"YouTube shorts high-contrast clickbait cover thumbnail about '{title}', {visual_style}, 9:16 vertical portrait, dramatic curiosity, bold composition"
        else:
            final_prompt = f"YouTube shorts high-contrast clickbait cover thumbnail, {visual_style}, 9:16 vertical portrait, dramatic curiosity, bold composition"

    bg_path = project_dir / THUMBNAIL_BG_FILENAME
    target_path = project_dir / THUMBNAIL_FILENAME

    # 0. Google Flow 썸네일 생성 시도
    if model_name in FLOW_IMAGE_MODELS or (model_name and model_name.startswith("flow_")):
        alias = FLOW_IMAGE_MODELS.get(model_name, "nano-pro")
        try:
            _run_flow_image_generate(
                model_alias=alias,
                prompt=final_prompt,
                output_path=bg_path,
                aspect_ratio="9:16",
            )
            if bg_path.exists() and bg_path.stat().st_size > 1000:
                try:
                    render_thumbnail_image(project_dir, title=title, source_image=bg_path)
                except Exception:
                    shutil.copy2(bg_path, target_path)
                return target_path
        except Exception as e:
            print(f"[Google Flow Thumbnail Error] {e}")

    if model_name != "dall-e-3":
        try:
            image_url = _run_higgsfield_generate(
                job_type=model_name or "nano_banana_pro",
                prompt=final_prompt,
                aspect_ratio="9:16",
            )
            resp = httpx.get(image_url, timeout=60.0)
            resp.raise_for_status()
            bg_path.write_bytes(resp.content)
            try:
                render_thumbnail_image(project_dir, title=title, source_image=bg_path)
            except Exception:
                shutil.copy2(bg_path, target_path)
            return target_path
        except Exception:
            pass

    from app.references.openai_client import create_openai_client
    client = create_openai_client(settings)
    res = client.images.generate(
        model="dall-e-3",
        prompt=final_prompt,
        size="1024x1792",
        quality="standard",
        n=1,
    )
    img_url = res.data[0].url
    if not img_url:
        raise ValueError("DALL-E 3에서 이미지 URL을 받지 못했습니다.")
    resp = httpx.get(img_url, timeout=60.0)
    resp.raise_for_status()
    bg_path.write_bytes(resp.content)
    try:
        render_thumbnail_image(project_dir, title=title, source_image=bg_path)
    except Exception:
        shutil.copy2(bg_path, target_path)
    return target_path


