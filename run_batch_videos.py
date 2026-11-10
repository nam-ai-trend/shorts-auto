import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# api 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent / "apps" / "api"))

from app.core.settings import load_settings
from app.production.service import generate_scene_video_for_project, get_flow_worker_count
from app.production.renderer import render_final_shorts


def _resolve_project_dir(base_outputs: Path, project_id: str | None) -> Path:
    if project_id:
        target = (base_outputs / project_id).resolve()
        if not target.exists():
            raise FileNotFoundError(f"지정한 프로젝트 폴더를 찾을 수 없습니다: {target}")
        return target

    candidates = sorted(
        [d for d in base_outputs.iterdir() if d.is_dir() and (d / "video_scenes.json").exists()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"video_scenes.json이 존재하는 프로젝트를 찾을 수 없습니다: {base_outputs}")
    return candidates[0].resolve()


def _resolve_project_title(project_dir: Path, cli_title: str | None) -> str | None:
    if cli_title is not None:
        return cli_title
    pj_file = project_dir / "project.json"
    if pj_file.exists():
        try:
            data = json.loads(pj_file.read_text(encoding="utf-8"))
            title = data.get("project_title", "").strip()
            if title and title != "untitled":
                return title
        except Exception:
            pass
    return None


def _process_single_scene(
    project_dir: Path,
    sc: dict,
    total_scenes: int,
    settings,
    model_name: str,
    duration: int,
) -> tuple[int, bool]:
    scene_id = sc["scene_id"]
    scenes_dir = project_dir / "scenes"
    video_path = scenes_dir / f"scene_{scene_id:02d}_video.mp4"

    if video_path.exists() and video_path.stat().st_size > 10000:
        print(f"[Scene {scene_id}/{total_scenes}] 기존 비디오 파일 유지 ({video_path.name})")
        return scene_id, True

    print(f"[Scene {scene_id}/{total_scenes}] 비디오 생성 시작 (model={model_name})...")
    start_time = time.time()
    for attempt in range(1, 3):
        try:
            if attempt > 1:
                print(f"[Scene {scene_id}] 5초 후 재시도 (시도 {attempt}/2)...")
                time.sleep(5)

            res_video = generate_scene_video_for_project(
                project_dir=project_dir,
                scene_id=scene_id,
                settings=settings,
                model_name=model_name,
                duration=duration,
                match_prev_frame=False,
            )
            elapsed = time.time() - start_time
            print(f"[Scene {scene_id}/{total_scenes}] 생성 완료 ({elapsed:.1f}초, {res_video.name})")
            return scene_id, True
        except Exception as e:
            print(f"[Scene {scene_id}/{total_scenes}] 시도 {attempt} 오류: {e}")

    print(f"[Scene {scene_id}/{total_scenes}] 비디오 생성 최종 실패")
    return scene_id, False


def main():
    parser = argparse.ArgumentParser(description="프로젝트 전체 씬 비디오 병렬 생성 및 렌더링 스크립트")
    parser.add_argument("--project", "-p", type=str, default=None, help="대상 프로젝트 ID (미지정 시 최신 프로젝트 자동 선택)")
    parser.add_argument("--model", "-m", type=str, default="flow_veo_fast", help="비디오 생성 모델 ID (기본값: flow_veo_fast)")
    parser.add_argument("--duration", "-d", type=int, default=6, help="비디오 목표 길이(초)")
    parser.add_argument("--workers", "-w", type=int, default=None, help="동시 실행 워커 수 (미지정 시 모델별 최적값 자동 적용)")
    parser.add_argument("--title", "-t", type=str, default=None, help="렌더링할 오프닝 타이틀 문구 (미지정 시 project.json 제목 사용)")
    parser.add_argument("--no-render", action="store_true", help="비디오 생성만 수행하고 최종 렌더링은 생략")
    args = parser.parse_args()

    base_outputs = Path(__file__).resolve().parent / "outputs"
    project_dir = _resolve_project_dir(base_outputs, args.project)
    settings = load_settings()

    video_scenes_file = project_dir / "video_scenes.json"
    scenes = json.loads(video_scenes_file.read_text(encoding="utf-8"))
    total_scenes = len(scenes)

    is_flow = args.model.startswith("flow_") or "flow" in args.model.lower()
    default_workers = get_flow_worker_count() if is_flow else 4
    max_workers = args.workers or min(default_workers, max(1, total_scenes))

    print(
        f"프로젝트 [{project_dir.name}] 총 {total_scenes}개 씬 병렬 비디오 생성 시작 "
        f"(모델: {args.model}, 동시 워커: {max_workers}개)"
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                _process_single_scene,
                project_dir,
                sc,
                total_scenes,
                settings,
                args.model,
                args.duration,
            )
            for sc in scenes
        ]
        for f in as_completed(futures):
            f.result()

    print("모든 씬의 비디오 생성 작업이 완료되었습니다.")
    if not args.no_render:
        print("최종 Remotion 9:16 쇼츠 비디오 렌더링 시작...")
        try:
            title = _resolve_project_title(project_dir, args.title)
            final_video = render_final_shorts(project_dir, settings, title=title)
            print(f"최종 쇼츠 렌더링 완료: {final_video}")
        except Exception as e:
            print(f"렌더링 중 오류: {e}")


if __name__ == "__main__":
    main()
