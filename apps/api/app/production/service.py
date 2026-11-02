from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI

from app.core.paths import find_repo_root
from app.core.settings import AppSettings
from app.production.models import (
    ConceptKit,
    ContinuityState,
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
    ref_text = settings.reference_voice_text

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

    final_script_path = project_dir / "final_script.md"
    script_text = final_script_path.read_text(encoding="utf-8") if final_script_path.exists() else ""

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
- **6. 포맷**: 반드시 수직 9:16 비율(`vertical 9:16 portrait aspect ratio`)의 영문 프롬프트로 작성하세요.

======================================================================
[규칙 2: 쇼츠 전문 카메라 모션 (camera_movement & video_prompt) 가이드라인]
======================================================================
쇼츠의 몰입감과 템포를 위해, 다음 12대 핵심 카메라 모션 중 각 씬의 역할(후킹, 반전, 설명, 클라이맥스)에 가장 적합한 모션을 선정하여 `camera_movement`에 지정하고, aicameramovements.com 표준 4단 문법으로 `video_prompt`를 작성하세요:

- 12대 핵심 모션 ID 목록:
  1) `crash_zoom_in`: 0~3초 상식 충돌 후킹, 충격적인 팩트 발표 시 급격한 타격감 있는 줌인
  2) `whip_pan`: '그런데 여기서 반전이 일어납니다' 등 국면 전환 시 신속한 수평 채찍 회전과 전환
  3) `slow_zoom_in`: 호기심 유발 및 미세 과학 메커니즘으로의 점진적 몰입/긴장감 고조
  4) `slow_zoom_out`: 숨겨진 실체나 주변 환경의 실체를 서서히 드러내며 시야 확장
  5) `orbit`: 피사체 주위를 360도 회전하며 3D 입체감과 오브젝트 형태 감상
  6) `arc_shot`: 얕은 곡선 궤적으로 돌아가 피사체와 배경의 거리감(시차) 강조
  7) `tracking_shot`: 움직이는 피사체/물질의 흐름을 일정 거리 유지하며 역동적 추적
  8) `low_tracking`: 지면 밀착 로우 앵글로 피사체를 거대하고 웅장하게 위압감 있게 연출
  9) `push_past`: 전경 피사체를 스쳐 지나가며 다음 공간/다음 씬 오브젝트를 원테이크로 공개
  10) `pedestal_up`: 수직으로 상승하며 거대한 높이나 스케일, 상승하는 에너지를 공개
  11) `drone_pull_back`: 빠르게 뒤로 멀어지며 엔딩 클리프행어/압도적 총량 체감
  12) `static_shot`: 카메라를 고정하여 미세한 액션이나 텍스처 자체에 안정적 집중

- **video_prompt 작성 공식 (aicameramovements 표준 4단 포맷 - 영문 작성)**:
  `camera: {{모션명}}. movement: {{현재 시작 이미지 상태에서 물리적 이동 경로}}. speed: {{모션 속도 및 템포}}. framing: {{피사체 구도 및 프레이밍}}. end: {{종료 지점 구도 및 다음 씬으로의 자연스러운 원테이크 인계 상태, no jump cuts}}.`

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
    ]
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


MODEL_ALIAS_MAP = {
    "grok_imagine_1_5_lite": "grok_video_v15_lite",
    "grok_imagine1_5_lite": "grok_video_v15_lite",
    "grok_1_5_lite": "grok_video_v15_lite",
    "grok_video_v15": "grok_video_v15_lite",
    "minimax": "minimax_h3",
    "minimax_h3_lite": "minimax_h3",
}


def _run_higgsfield_generate(
    job_type: str,
    prompt: str,
    aspect_ratio: str = "9:16",
    start_image: Path | None = None,
    end_image: Path | None = None,
    duration: int | None = None,
    resolution: str = "1k",
    multi_shots: bool = False,
    timeout_minutes: int = 15,
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

    # 시작 이미지 (Start Frame)
    if start_image and start_image.exists():
        cmd.extend(["--start-image", str(start_image)])

    # 종료 이미지 (End Frame) - Seedance 2.0 / Kling 3.0 / Minimax H3 등 원테이크 보간 지원 모델
    if end_image and end_image.exists() and any(k in resolved_job_type for k in ("seedance", "kling", "minimax")):
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

    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_minutes * 60)
    if res.returncode != 0:
        raise RuntimeError(f"Higgsfield generate CLI 에러 ({res.returncode}): {res.stderr or res.stdout}")

    try:
        data = json.loads(res.stdout)
        item = data[0] if isinstance(data, list) and data else data
        result_url = item.get("result_url") or item.get("output_url") or item.get("url")
        if not result_url:
            raise RuntimeError(f"Higgsfield 결과 URL을 찾을 수 없습니다: {res.stdout}")
        return str(result_url)
    except Exception as exc:
        raise RuntimeError(f"Higgsfield 출력 파싱 실패: {res.stdout}") from exc


def generate_scene_image_for_project(
    project_dir: Path,
    scene_id: int,
    settings: AppSettings,
    model_name: str = "nano_banana_pro",
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
        prompt = f"Claymation style vertical 9:16 portrait scene {scene_id}, cute plasticine texture"

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

    # 1. 힉스필드 모델 시도 (nano_banana_pro, gpt_image_2, seedream_v5_pro, flux_3_image 등)
    if model_name != "dall-e-3":
        try:
            image_url = _run_higgsfield_generate(
                job_type=model_name or "nano_banana_pro",
                prompt=prompt,
                aspect_ratio="9:16",
                resolution="2k" if "gpt" in model_name or "seedream" in model_name else "1k",
            )
            resp = httpx.get(image_url, timeout=90.0)
            if resp.status_code == 200:
                start_image_path.write_bytes(resp.content)
                return _finalize_image(start_image_path)
        except Exception:
            pass

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
            end_image = current_scene_image if any(k in model_name for k in ("kling", "seedance", "minimax")) else None
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

        prompt = f"""당신은 세계 최고의 AI 이미지 프롬프트 디렉터입니다.
사용자의 피드백을 100% 반영하여, 현재 씬(Scene {scene_id})의 영문 이미지 프롬프트를 새롭게 전면 재작성하세요.

[현재 씬 정보]
- 씬 번호: Scene {scene_id}
- 대본 나레이션: {target_scene.get('narration', '')}
- 기존 이미지 프롬프트: {target_scene.get('start_image_prompt', '')}
- 컨셉 스타일: {concept_kit_data.get('visual_style', 'Cute professional miniature claymation infographic')}
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
6. [스타일 및 조명 유지]: 클레이 질감(Claymation style vertical 9:16 portrait, handcrafted plasticine texture, visible fingerprints, soft studio directional lighting)은 일관되게 유지하세요.
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
  2) Dynamic Motion: 5초간의 끊김 없는 부드러운 카메라 무빙(크레인 틸트, 패닝 등)과 클레이 피사체의 역동적 변화.
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
3. [자연스러운 연속성]: 끊김이나 점프컷 없이 1개의 매끄러운 영문 문단으로 작성하세요 (Smooth continuous stop-motion animation, no jump cuts).

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
    concept_kit = ConceptKit.model_validate(ck_data)
    concept_kit_file.write_text(json.dumps(concept_kit.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")

    video_scenes = None
    if regenerate_prompts and settings:
        concept_kit, video_scenes = generate_concept_kit_and_video_scenes(
            project_dir, settings, visual_style_id=style.id
        )

    return concept_kit, video_scenes


def _get_project_title(project_dir: Path) -> str | None:
    pj_file = project_dir / "project.json"
    if pj_file.exists():
        try:
            p_data = json.loads(pj_file.read_text(encoding="utf-8"))
            title = p_data.get("project_title", "")
            if title and title.strip() and title.strip() != "untitled":
                return title.strip()
        except Exception:
            pass
    return None


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
        visual_style = "Cute professional claymation infographic, vibrant colors, clean lighting"
        if concept_kit_file.exists():
            try:
                ck = json.loads(concept_kit_file.read_text(encoding="utf-8"))
                visual_style = ck.get("visual_style", visual_style)
            except Exception:
                pass

        if title:
            final_prompt = f"YouTube shorts high-contrast clickbait cover thumbnail about '{title}', {visual_style}, 9:16 vertical portrait, dramatic curiosity, bold composition"
        else:
            final_prompt = f"YouTube shorts high-contrast clickbait cover thumbnail, {visual_style}, 9:16 vertical portrait, dramatic curiosity, bold composition"

    bg_path = project_dir / THUMBNAIL_BG_FILENAME
    target_path = project_dir / THUMBNAIL_FILENAME

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


