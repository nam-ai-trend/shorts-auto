from __future__ import annotations

from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.core.settings import AppSettings
from app.jobs.service import append_job, update_job_state
from app.production.models import (
    ApplyMotionRequest,
    FeedbackRegenerateRequest,
    GeneratePromptsRequest,
    ProductionState,
    RenderShortsRequest,
    ThumbnailFromSceneRequest,
    ThumbnailGenerateRequest,
    UpdateScenePromptsRequest,
    UpdateVisualStyleRequest,
)
from app.production.camera_movements import CORE_CAMERA_MOVEMENTS
from app.production.visual_styles import VISUAL_STYLES
from app.production.service import (
    CONCEPT_KIT_FILENAME,
    RAW_STT_FILENAME,
    SCENE_DATA_FILENAME,
    SCENES_DIR_NAME,
    THUMBNAIL_FILENAME,
    TTS_AUDIO_FILENAME,
    VIDEO_SCENES_FILENAME,
    align_subtitles_and_scenes_for_project,
    apply_motion_to_scene,
    delete_thumbnail_image,
    generate_concept_kit_and_video_scenes,
    generate_scene_image_for_project,
    generate_scene_video_for_project,
    generate_thumbnail_image_for_project,
    generate_tts_for_project,
    get_flow_worker_count,
    get_production_state,
    pass_continuity_frame_to_next_scene,
    recommend_motion_for_scene,
    refine_and_regenerate_scene,
    save_thumbnail_image,
    set_thumbnail_from_scene,
    update_project_visual_style,
    update_scene_prompts_for_project,
)
from app.production.renderer import render_final_shorts
from app.projects.service import _display_name, read_project, save_project


def create_production_router(
    outputs_dir_provider: Callable[[], Path],
    settings_provider: Callable[[], AppSettings],
) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/production", tags=["production"])

    def project_dir(outputs_dir: Path, project_id: str) -> Path:
        read_project(outputs_dir, project_id)
        return outputs_dir / project_id

    def fail_job(outputs_dir: Path, project_id: str, job_id: str | None, message: str) -> None:
        if job_id is None:
            return
        update_job_state(outputs_dir, project_id, job_id, "failed", message, error_message=message)

    @router.get("", response_model=ProductionState)
    def get_state(project_id: str, outputs: Path = Depends(outputs_dir_provider)):
        try:
            path = project_dir(outputs, project_id)
            return get_production_state(path, project_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @router.get("/audio")
    def get_audio(project_id: str, outputs: Path = Depends(outputs_dir_provider)):
        try:
            path = project_dir(outputs, project_id)
            audio_path = path / TTS_AUDIO_FILENAME
            if not audio_path.exists():
                raise HTTPException(status_code=404, detail="TTS audio not found")
            return FileResponse(path=str(audio_path), media_type="audio/wav", filename=TTS_AUDIO_FILENAME)
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @router.post("/tts")
    def generate_tts(
        project_id: str,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            path = project_dir(outputs, project_id)
            job = append_job(
                outputs,
                project_id,
                "production_tts",
                "Generate 1.2x TTS audio",
                input_paths=["final_script.md"],
                provider="qwen3_tts",
                command="generate_voice_clone",
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Generating TTS voice with Qwen3-TTS")

            generate_tts_for_project(path, settings)

            update_job_state(outputs, project_id, job.job_id, "running", "Transcribing and aligning scenes")
            align_subtitles_and_scenes_for_project(path, settings)

            project = read_project(outputs, project_id)
            project.generated_files["tts_audio"] = TTS_AUDIO_FILENAME
            project.generated_files["raw_stt"] = RAW_STT_FILENAME
            project.generated_files["scene_data"] = SCENE_DATA_FILENAME
            for status in project.step_statuses:
                if status.name == "Production":
                    status.state = "succeeded"
                    status.message = "TTS and scene alignment complete."
                elif status.name == "Render":
                    status.state = "waiting"
                    status.message = "Ready for visual concept & Remotion rendering."
            save_project(outputs, project)

            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "1.2x TTS audio and scene data generated successfully",
                output_paths=[TTS_AUDIO_FILENAME, RAW_STT_FILENAME, SCENE_DATA_FILENAME],
            )
            return get_production_state(path).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.post("/align")
    def align_scenes(
        project_id: str,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            path = project_dir(outputs, project_id)
            job = append_job(
                outputs,
                project_id,
                "production_align",
                "Align subtitles and split scenes",
                input_paths=[TTS_AUDIO_FILENAME, "final_script.md"],
                provider="openai",
                command="whisper-1",
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Transcribing and aligning scenes")

            align_subtitles_and_scenes_for_project(path, settings)

            project = read_project(outputs, project_id)
            project.generated_files["raw_stt"] = RAW_STT_FILENAME
            project.generated_files["scene_data"] = SCENE_DATA_FILENAME
            for status in project.step_statuses:
                if status.name == "Production":
                    status.state = "succeeded"
                    status.message = "TTS and scene alignment complete."
                elif status.name == "Render":
                    status.state = "waiting"
                    status.message = "Ready for visual concept & Remotion rendering."
            save_project(outputs, project)

            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Subtitles and scene data aligned successfully",
                output_paths=[RAW_STT_FILENAME, SCENE_DATA_FILENAME],
            )
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.get("/scenes/{filename}")
    def get_scene_image(project_id: str, filename: str, outputs: Path = Depends(outputs_dir_provider)):
        try:
            path = project_dir(outputs, project_id)
            file_path = path / SCENES_DIR_NAME / filename
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="Scene asset not found")
            media_type = "video/mp4" if filename.endswith(".mp4") else "image/png"
            return FileResponse(
                path=str(file_path),
                media_type=media_type,
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc

    @router.post("/concepts")
    def generate_concepts(
        project_id: str,
        req: GeneratePromptsRequest | None = None,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            path = project_dir(outputs, project_id)
            visual_style_id = req.visual_style_id if req and req.visual_style_id else "claymation"
            job = append_job(
                outputs,
                project_id,
                "production_concepts",
                f"Generate visual concept kit and continuous video scenes ({visual_style_id})",
                input_paths=["final_script.md", SCENE_DATA_FILENAME],
                provider="openai",
                command="generate_concepts",
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", f"Designing concept kit and continuity video scenes ({visual_style_id})")

            generate_concept_kit_and_video_scenes(path, settings, visual_style_id=visual_style_id)

            project = read_project(outputs, project_id)
            project.generated_files["concept_kit"] = CONCEPT_KIT_FILENAME
            project.generated_files["video_scenes"] = VIDEO_SCENES_FILENAME
            save_project(outputs, project)

            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Concept kit and continuous video scenes created",
                output_paths=[CONCEPT_KIT_FILENAME, VIDEO_SCENES_FILENAME],
            )
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.post("/scenes/{scene_id}/image")
    def generate_scene_image(
        project_id: str,
        scene_id: int,
        model: str = "nano_banana_pro",
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            generate_scene_image_for_project(path, scene_id, settings, model_name=model)
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/scenes/images")
    def generate_all_scene_images(
        project_id: str,
        model: str = "nano_banana_pro",
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            state = get_production_state(path, project_id)
            unlocked_scenes = [sc for sc in state.video_scenes if not sc.is_locked]

            # Flow CLI는 멀티 워커 프로필 풀 개수(기본 3개)만큼, API 기반(Higgsfield/DALL-E)은 최대 4개 병렬 실행
            is_flow = model.startswith("flow_") or "flow" in model.lower()
            worker_limit = get_flow_worker_count() if is_flow else 4
            max_workers = min(worker_limit, len(unlocked_scenes) or 1)

            if max_workers > 1:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(generate_scene_image_for_project, path, sc.scene_id, settings, model)
                        for sc in unlocked_scenes
                    ]
                    for f in futures:
                        f.result()
            else:
                for sc in unlocked_scenes:
                    generate_scene_image_for_project(path, sc.scene_id, settings, model_name=model)

            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/scenes/{scene_id}/video")
    def generate_scene_video(
        project_id: str,
        scene_id: int,
        model: str = "kling_o3_flf",
        duration: int = 5,
        multi_shots: bool = False,
        match_prev_frame: bool = True,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            generate_scene_video_for_project(
                path,
                scene_id,
                settings,
                model_name=model,
                duration=duration,
                multi_shots=multi_shots,
                match_prev_frame=match_prev_frame,
            )
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/scenes/{scene_id}/feedback-regenerate")
    def feedback_regenerate_scene(
        project_id: str,
        scene_id: int,
        req: FeedbackRegenerateRequest,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            refine_and_regenerate_scene(
                path,
                scene_id,
                feedback=req.feedback,
                target=req.target,
                settings=settings,
                model_name=req.model,
                duration=req.duration,
                multi_shots=req.multi_shots,
                match_prev_frame=req.match_prev_frame,
            )
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/scenes/{scene_id}/prompts")
    def update_scene_prompts(
        project_id: str,
        scene_id: int,
        req: UpdateScenePromptsRequest,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            update_scene_prompts_for_project(
                path,
                scene_id,
                start_image_prompt=req.start_image_prompt,
                video_prompt=req.video_prompt,
            )
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/scenes/{scene_id}/pass-next")
    def pass_continuity(
        project_id: str,
        scene_id: int,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            pass_continuity_frame_to_next_scene(path, scene_id)
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/camera-movements")
    def get_camera_movements():
        return [m.model_dump() for m in CORE_CAMERA_MOVEMENTS]

    @router.post("/scenes/{scene_id}/recommend-motion")
    def recommend_scene_motion(
        project_id: str,
        scene_id: int,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            return recommend_motion_for_scene(path, scene_id, settings).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/scenes/{scene_id}/apply-motion")
    def apply_scene_motion(
        project_id: str,
        scene_id: int,
        req: ApplyMotionRequest,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            updated_scene = apply_motion_to_scene(
                path,
                scene_id,
                movement_id=req.movement_id,
                custom_instruction=req.custom_instruction,
                settings=settings,
            )
            return {
                "scene": updated_scene.model_dump(),
                "production": get_production_state(path, project_id).model_dump(),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/visual-styles")
    def get_visual_styles():
        return [s.model_dump() for s in VISUAL_STYLES]

    @router.post("/visual-style")
    def update_visual_style(
        project_id: str,
        req: UpdateVisualStyleRequest,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            concept_kit, _ = update_project_visual_style(
                path,
                visual_style_id=req.visual_style_id,
                regenerate_prompts=req.regenerate_prompts,
                settings=settings,
            )
            return {
                "concept_kit": concept_kit.model_dump(),
                "production": get_production_state(path, project_id).model_dump(),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/render")
    def render_shorts(
        project_id: str,
        req: RenderShortsRequest | None = None,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id = None
        try:
            path = project_dir(outputs, project_id)
            title = req.title.strip() if req and req.title and req.title.strip() else None
            if not title:
                try:
                    project = read_project(outputs, project_id)
                    if project.project_title and project.project_title.strip() and project.project_title.strip() != "untitled":
                        title = project.project_title.strip()
                except Exception:
                    pass
            job = append_job(
                outputs,
                project_id,
                "production_render",
                "Render final shorts video with speed sync and subtitles",
                input_paths=["video_scenes.json", "output_1.2x.wav", "scene_data.json"],
                provider="ffmpeg",
                command="render_final_shorts",
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Rendering 9:16 shorts video with subtitles and BGM")

            thumb_frames = req.thumbnail_duration_frames if req and req.thumbnail_duration_frames else 15
            render_final_shorts(path, settings, title=title, thumbnail_duration_frames=thumb_frames)

            project = read_project(outputs, project_id)
            project.generated_files["final_video"] = "final.mp4"
            if title:
                project.project_title = title
                project.display_name = _display_name(project.project_id, title)
            save_project(outputs, project)

            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Final shorts video rendered successfully",
                output_paths=["final.mp4"],
            )
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.get("/final-video")
    def get_final_video(
        project_id: str,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            final_p = path / "final.mp4"
            if not final_p.exists():
                raise HTTPException(status_code=404, detail="final.mp4 영상이 아직 생성되지 않았습니다.")
            return FileResponse(
                path=str(final_p),
                media_type="video/mp4",
                filename=f"{project_id}_final.mp4",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/thumbnail")
    def get_thumbnail(project_id: str, outputs: Path = Depends(outputs_dir_provider)):
        try:
            path = project_dir(outputs, project_id)
            thumb_p = path / THUMBNAIL_FILENAME
            if not thumb_p.exists():
                raise HTTPException(status_code=404, detail="썸네일 이미지가 없습니다.")
            return FileResponse(
                path=str(thumb_p),
                media_type="image/png",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/thumbnail")
    async def upload_thumbnail(
        project_id: str,
        file: UploadFile = File(...),
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="업로드된 파일이 비어 있습니다.")
            save_thumbnail_image(path, content)
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/thumbnail/generate")
    def generate_thumbnail(
        project_id: str,
        req: ThumbnailGenerateRequest | None = None,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            model = req.model if req and req.model else "nano_banana_pro"
            prompt = req.prompt if req else None
            generate_thumbnail_image_for_project(path, settings, model_name=model, prompt=prompt)
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/thumbnail/from-scene")
    def set_thumbnail_scene(
        project_id: str,
        req: ThumbnailFromSceneRequest | None = None,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            scene_id = req.scene_id if req and req.scene_id else 1
            set_thumbnail_from_scene(path, scene_id=scene_id)
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/thumbnail")
    def delete_thumbnail(
        project_id: str,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            delete_thumbnail_image(path)
            return get_production_state(path, project_id).model_dump()
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router

