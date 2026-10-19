from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path

from app.core.paths import find_repo_root
from app.core.settings import AppSettings
TTS_AUDIO_FILENAME = "output_1.2x.wav"
RAW_STT_FILENAME = "raw_stt.json"
SCENE_DATA_FILENAME = "scene_data.json"
VIDEO_SCENES_FILENAME = "video_scenes.json"
SCENES_DIR_NAME = "scenes"


def split_subtitles_for_shorts(
    raw_items: list[dict],
    max_one_line: int = 16,
    target_chunk_max: int = 15,
) -> list[dict]:
    """
    유튜브 쇼츠(1080x1920)에 최적화된 1줄 자막 분할 알고리즘.
    - 16자 이하의 짧은 문장은 그대로 1줄 단일 팝업 유지.
    - 17자 이상의 긴 문장은 한국어 의미 단위(어절)로 8~15자 내외의 1줄 청크로 균형 분할.
    - 글자(음절) 수에 비례하여 start~end 시간을 정밀 배분.
    """
    result: list[dict] = []

    def _split_single_text(text: str) -> list[str]:
        cleaned = text.strip()
        if not cleaned:
            return []
        if len(cleaned) <= max_one_line:
            return [cleaned]

        words = cleaned.split()
        total_len = len(cleaned)
        k = max(2, math.ceil(total_len / target_chunk_max))
        ideal_len = total_len / k

        chunks: list[str] = []
        curr_words: list[str] = []
        curr_len = 0

        for i, w in enumerate(words):
            remaining_words = len(words) - i
            remaining_slots = k - len(chunks)
            cand_len = len(w) if not curr_words else curr_len + 1 + len(w)

            # 남은 단어 수와 슬롯 수가 같으면 강제 분할
            if remaining_slots > 1 and remaining_words <= remaining_slots - 1:
                if curr_words:
                    chunks.append(" ".join(curr_words))
                    curr_words = []
                    curr_len = 0
                    cand_len = len(w)

            # 균형 분할 판단
            if curr_words and remaining_slots > 1:
                diff_current = abs(curr_len - ideal_len)
                diff_next = abs(cand_len - ideal_len)
                if cand_len > target_chunk_max or (diff_current <= diff_next and curr_len >= 8):
                    chunks.append(" ".join(curr_words))
                    curr_words = [w]
                    curr_len = len(w)
                    continue

            curr_words.append(w)
            curr_len = cand_len

        if curr_words:
            # 마지막 청크가 4자 이하이고 앞 청크와 합쳐서 18자 이하면 결합
            if chunks and len(" ".join(curr_words)) <= 4 and (len(chunks[-1]) + 1 + len(" ".join(curr_words))) <= 18:
                chunks[-1] = chunks[-1] + " " + " ".join(curr_words)
            else:
                chunks.append(" ".join(curr_words))

        return chunks

    for item in raw_items:
        txt = str(item.get("text", "")).strip()
        start = float(item.get("start", 0.0))
        end = float(item.get("end", 0.0))
        dur = max(0.1, end - start)

        chunks = _split_single_text(txt)
        if not chunks:
            continue

        if len(chunks) == 1:
            result.append({"text": chunks[0], "start": round(start, 3), "end": round(end, 3)})
            continue

        # 글자 수(공백 제외) 비례 시간 배분
        total_chars = sum(max(1, len(re.sub(r"\s+", "", c))) for c in chunks)
        curr_t = start
        for c in chunks:
            c_chars = max(1, len(re.sub(r"\s+", "", c)))
            c_dur = dur * (c_chars / total_chars)
            c_end = curr_t + c_dur
            result.append({"text": c, "start": round(curr_t, 3), "end": round(c_end, 3)})
            curr_t = c_end

    return result


def _format_ass_time(seconds: float) -> str:
    """초 단위를 ASS 자막 시간 포맷 (H:MM:SS.cs)으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis >= 100:
        centis = 99
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def generate_ass_subtitles(project_dir: Path) -> Path:
    """
    scene_data.json 또는 raw_stt.json의 타임코드를 기반으로
    유튜브 쇼츠용 볼드 화이트 + 검정 외곽선 ASS 자막 파일 생성
    """
    ass_path = project_dir / "subtitles.ass"

    # 타임스탬프 텍스트 블록 수집
    blocks: list[dict] = []
    scene_data_path = project_dir / "scene_data.json"
    raw_stt_path = project_dir / RAW_STT_FILENAME

    if scene_data_path.exists():
        try:
            data = json.loads(scene_data_path.read_text(encoding="utf-8"))
            for item in data:
                for tb in item.get("text_blocks", []):
                    txt = tb.get("text", "").strip()
                    if txt:
                        blocks.append({
                            "start": float(tb.get("start", 0.0)),
                            "end": float(tb.get("end", 0.0)),
                            "text": txt,
                        })
        except Exception:
            blocks = []

    if not blocks and raw_stt_path.exists():
        try:
            stt = json.loads(raw_stt_path.read_text(encoding="utf-8"))
            for item in stt:
                txt = item.get("text", "").strip()
                if txt:
                    blocks.append({
                        "start": float(item.get("start", 0.0)),
                        "end": float(item.get("end", 0.0)),
                        "text": txt,
                    })
        except Exception:
            blocks = []

    # ASS 헤더 및 스타일 정의 (1080x1920 해상도 기준, 쇼츠 최적화)
    ass_content = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: ShortsDefault,AppleSDGothicNeo-Bold,56,&H00FFFFFF,&H000000FF,&H00111111,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,260,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    for b in blocks:
        st = _format_ass_time(b["start"])
        et = _format_ass_time(b["end"])
        text = b["text"].replace("\n", "\\N")
        ass_content.append(f"Dialogue: 0,{st},{et},ShortsDefault,,0,0,0,,{text}")

    ass_path.write_text("\n".join(ass_content), encoding="utf-8")
    return ass_path


def _get_video_duration(video_path: Path) -> float:
    """ffprobe로 비디오 실제 재생 시간 측정"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 6.0


def render_final_shorts(
    project_dir: Path,
    settings: AppSettings,
    title: str | None = None,
) -> Path:
    """
    모든 씬의 비디오를 나레이션 시간(target_duration)에 맞춰 배속 조절(setpts)하여 동기화하고,
    output_1.2x.wav(TTS) 및 channel BGM을 믹싱한 뒤 고품질 자막을 입혀 final.mp4를 렌더링합니다.
    """
    video_scenes_path = project_dir / VIDEO_SCENES_FILENAME
    if not video_scenes_path.exists():
        raise FileNotFoundError("video_scenes.json 파일이 없습니다.")

    scenes_data = json.loads(video_scenes_path.read_text(encoding="utf-8"))
    if not scenes_data:
        raise ValueError("렌더링할 비디오 씬 목록이 비어 있습니다.")

    # 🎯 렌더링 전 나레이션 오디오와 씬 타임코드 자동 동기화 보정:
    # STT 세그먼트와 실제 오디오 길이를 기반으로 각 씬의 start, end, target_duration을 1:1로 정밀 보정
    raw_stt_path = project_dir / RAW_STT_FILENAME
    wav_path = project_dir / TTS_AUDIO_FILENAME
    if raw_stt_path.exists() and wav_path.exists():
        try:
            from app.production.models import VideoSceneItem
            from app.production.service import calibrate_scenes_with_stt, _get_audio_duration

            audio_dur = _get_audio_duration(wav_path)
            stt_segments = json.loads(raw_stt_path.read_text(encoding="utf-8"))
            if audio_dur > 0 and stt_segments:
                vs_items = [VideoSceneItem.model_validate(sc) for sc in scenes_data]
                calibrated = calibrate_scenes_with_stt(vs_items, stt_segments, audio_dur)
                scenes_data = [item.model_dump() for item in calibrated]
                # 보정된 타임코드를 video_scenes.json에도 즉시 갱신 반영
                video_scenes_path.write_text(json.dumps(scenes_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    scenes_dir = project_dir / SCENES_DIR_NAME
    scenes_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = scenes_dir / "_render_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    normalized_clips: list[Path] = []

    # 1. 씬별 비디오 배속 조정 및 정규화 클립 생성 (24 FPS 시네마틱 모션 보존)
    for sc in scenes_data:
        scene_id = int(sc["scene_id"])
        target_dur = float(sc.get("target_duration", 6.0))
        if target_dur <= 0.1:
            target_dur = 6.0

        video_path = scenes_dir / f"scene_{scene_id:02d}_video.mp4"
        start_img_path = scenes_dir / f"scene_{scene_id:02d}_start.png"
        norm_clip_path = tmp_dir / f"norm_scene_{scene_id:02d}.mp4"

        if video_path.exists() and video_path.stat().st_size > 1000:
            # 실제 생성된 비디오가 있는 경우 -> 모션 드득거림 방지를 위해 1.0x 원본 속도 100% 유지
            actual_dur = _get_video_duration(video_path)
            if actual_dur <= 0.1:
                actual_dur = 6.0

            # 🎬 나레이션 시간(target_dur)에 맞춰 비디오 재생 속도(setpts) 정밀 동기화:
            # - 영상이 나레이션보다 짧으면 부드럽게 늘려서 정지 프레임 없이 끝까지 모션을 유지하고,
            # - 영상이 나레이션보다 길면 배속을 올려서 엔딩 목적지 프레임까지 잘림 없이 온전히 도달!
            pts_factor = target_dur / actual_dur
            filter_vf = (
                f"setpts={pts_factor:.6f}*PTS,"
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1,fps=24"
            )

            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vf", filter_vf,
                "-t", f"{target_dur:.3f}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
                str(norm_clip_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            normalized_clips.append(norm_clip_path)

        elif start_img_path.exists():
            # 비디오가 아직 없는 경우 -> 시작 이미지를 target_duration 동안 24 FPS 정지영상 클립으로 생성
            filter_vf = (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,"
                "setsar=1,fps=24"
            )
            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-i", str(start_img_path),
                "-vf", filter_vf,
                "-t", str(target_dur),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an",
                str(norm_clip_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            normalized_clips.append(norm_clip_path)
        else:
            raise FileNotFoundError(f"Scene {scene_id}의 비디오 또는 시작 이미지가 없습니다.")

    # 2. 정규화된 씬 클립들을 concat
    concat_list_path = tmp_dir / "concat_list.txt"
    concat_lines = [f"file '{clip.resolve()}'" for clip in normalized_clips]
    concat_list_path.write_text("\n".join(concat_lines), encoding="utf-8")

    concatenated_video_path = tmp_dir / "concatenated.mp4"
    concat_cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        str(concatenated_video_path)
    ]
    subprocess.run(concat_cmd, capture_output=True, check=True)

    # 3. Remotion 렌더링용 자막 데이터 및 쇼츠 1줄 최적화 분할 적용
    raw_subtitles: list[dict] = []
    scene_data_path = project_dir / SCENE_DATA_FILENAME
    raw_stt_path = project_dir / RAW_STT_FILENAME

    if scene_data_path.exists():
        try:
            sc_raw = json.loads(scene_data_path.read_text(encoding="utf-8"))
            for item in sc_raw:
                for tb in item.get("text_blocks", []):
                    txt = str(tb.get("text", "")).strip()
                    if txt:
                        raw_subtitles.append({
                            "start": float(tb.get("start", 0.0)),
                            "end": float(tb.get("end", 0.0)),
                            "text": txt,
                        })
                if not item.get("text_blocks"):
                    txt = str(item.get("subtitle") or item.get("text") or item.get("narration") or "").strip()
                    if txt:
                        raw_subtitles.append({
                            "start": float(item.get("start", 0.0)),
                            "end": float(item.get("end", 0.0)),
                            "text": txt,
                        })
        except Exception:
            raw_subtitles = []

    if not raw_subtitles and raw_stt_path.exists():
        try:
            stt = json.loads(raw_stt_path.read_text(encoding="utf-8"))
            for item in stt:
                txt = str(item.get("text", "")).strip()
                if txt:
                    raw_subtitles.append({
                        "start": float(item.get("start", 0.0)),
                        "end": float(item.get("end", 0.0)),
                        "text": txt,
                    })
        except Exception:
            raw_subtitles = []

    # 긴 문장은 쇼츠 규격(1줄 8~15자 내외)에 맞춰 의미 단위 분할 및 시간 비례 배분
    subtitles_list = split_subtitles_for_shorts(raw_subtitles, max_one_line=16, target_chunk_max=15)

    # 4. 나레이션 및 BGM 오디오 경로
    tts_audio_path = project_dir / TTS_AUDIO_FILENAME
    if not tts_audio_path.exists():
        raise FileNotFoundError(f"나레이션 오디오 파일이 없습니다: {tts_audio_path}")

    repo_root = find_repo_root()
    bgm_path = repo_root / settings.bgm_path
    final_output_path = project_dir / "final.mp4"
    has_bgm = bgm_path.exists() and bgm_path.stat().st_size > 1000

    # 총 재생 시간 및 프레임 수 (24 FPS)
    total_audio_dur = _get_video_duration(tts_audio_path)
    total_frames = int(round(total_audio_dur * 24))

    # 프로젝트 루트 기준 상대 경로로 전달 (Remotion staticFile 호환)
    rel_video = concatenated_video_path.resolve().relative_to(repo_root.resolve()).as_posix()
    rel_audio = tts_audio_path.resolve().relative_to(repo_root.resolve()).as_posix()
    rel_bgm = bgm_path.resolve().relative_to(repo_root.resolve()).as_posix() if has_bgm else None

    # 0~2초 오프닝 타이틀 설정 (인자로 없으면 project.json에서 확인)
    final_title = title.strip() if title and title.strip() else None
    if not final_title:
        try:
            pj_path = project_dir / "project.json"
            if pj_path.exists():
                pj_data = json.loads(pj_path.read_text(encoding="utf-8"))
                p_title = pj_data.get("project_title")
                if p_title and p_title.strip() and p_title.strip() != "untitled":
                    final_title = p_title.strip()
        except Exception:
            pass

    remotion_props = {
        "videoSrc": rel_video,
        "audioSrc": rel_audio,
        "bgmSrc": rel_bgm,
        "bgmVolume": float(settings.bgm_volume) if has_bgm else 0.15,
        "subtitles": subtitles_list,
        "durationInFrames": max(24, total_frames),
        "title": final_title,
    }

    props_file = tmp_dir / "remotion_props.json"
    props_file.write_text(json.dumps(remotion_props, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. Remotion 공식 Node.js 렌더러 실행
    remotion_render_script = repo_root / "apps" / "remotion" / "render.mjs"
    render_cmd = [
        "node",
        str(remotion_render_script.resolve()),
        f"--props={props_file.resolve()}",
        f"--output={final_output_path.resolve()}",
    ]

    res = subprocess.run(render_cmd, capture_output=True, text=True, cwd=str(repo_root))
    if res.returncode != 0:
        raise RuntimeError(f"Remotion 쇼츠 렌더링 실패: {res.stderr or res.stdout}")

    # project.json Render 스텝 업데이트
    project_json_path = project_dir / "project.json"
    if project_json_path.exists():
        try:
            p_data = json.loads(project_json_path.read_text(encoding="utf-8"))
            for step in p_data.get("step_statuses", p_data.get("steps", [])):
                if step.get("name") == "Render":
                    step["state"] = "succeeded"
                    step["status"] = "succeeded"
                    step["message"] = "Final 9:16 shorts video rendered with speed sync & subtitles."
            p_data.setdefault("generated_files", {})["final_video"] = "final.mp4"
            project_json_path.write_text(json.dumps(p_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    return final_output_path
