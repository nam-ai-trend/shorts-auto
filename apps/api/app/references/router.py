from __future__ import annotations

from pathlib import Path
from typing import Callable

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.core.settings import AppSettings
from app.jobs.service import append_job, update_job_state
from app.projects.models import WORKFLOW_STEPS
from app.projects.service import read_project, save_project
from app.references.analysis import build_analysis_prompt, write_reference_analysis
from app.references.audio import (
    AudioExtractionError,
    extract_reference_audio,
    save_uploaded_audio,
    validate_audio_upload_name,
)
from app.references.files import (
    clear_derived_reference_outputs,
    clear_downstream_reference_outputs,
    clear_reference_analysis_outputs,
    clear_reference_audio_files,
    REFERENCE_RAW_STT_FILE,
    REFERENCE_SCRIPT_FILE,
    read_reference_candidates,
    read_reference_state,
    read_selected_reference,
    write_reference_candidates,
    write_selected_reference,
)
from app.references.models import (
    DirectReferenceRequest,
    ReferenceSearchRequest,
    SelectReferenceRequest,
)
from app.references.openai_clients import (
    AnalysisClient,
    OpenAIAnalysisClient,
    OpenAITranscriptionClient,
    TranscriptionClient,
    write_reference_stt_outputs,
)
from app.references.youtube import YouTubeClient, sort_by_vs_ratio


SCRIPT_GENERATED_FILE_KEYS = [
    "script_candidates",
    "selected_script_candidate",
    "final_script",
    "final_script_state",
]


def create_references_router(
    outputs_dir_provider: Callable[[], Path],
    settings_provider: Callable[[], AppSettings],
    youtube_client_factory: Callable[[str], YouTubeClient] = YouTubeClient,
    audio_extractor: Callable[[Path, str, str], Path] = extract_reference_audio,
    transcription_client_factory: Callable[[str, str], TranscriptionClient] = OpenAITranscriptionClient,
    analysis_client_factory: Callable[[str, str], AnalysisClient] = OpenAIAnalysisClient,
) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/reference", tags=["reference"])

    def project_dir(outputs_dir: Path, project_id: str) -> Path:
        read_project(outputs_dir, project_id)
        return outputs_dir / project_id

    def fail_job(
        outputs_dir: Path,
        project_id: str,
        job_id: str | None,
        message: str,
    ) -> None:
        if job_id is None:
            return
        update_job_state(
            outputs_dir,
            project_id,
            job_id,
            "failed",
            message,
            error_message=message,
        )

    def provider_error_message(exc: Exception) -> str:
        return str(exc) or exc.__class__.__name__

    def clear_audio_derivatives(outputs: Path, path: Path, project_id: str, audio_name: str) -> None:
        clear_reference_audio_files(path, audio_name)
        clear_derived_reference_outputs(path)
        project = read_project(outputs, project_id)
        project.generated_files["reference_audio"] = audio_name
        for key in [
            "reference_raw_stt",
            "reference_script",
            "reference_analysis",
            "reference_analysis_markdown",
            *SCRIPT_GENERATED_FILE_KEYS,
        ]:
            project.generated_files.pop(key, None)
        for status in project.step_statuses:
            if status.name == "STT":
                status.state = "waiting"
                status.message = "Reference audio is ready for STT."
            elif status.name in WORKFLOW_STEPS[2:]:
                status.state = "waiting"
                status.message = ""
        project.current_step = "STT"
        save_project(outputs, project)

    def reference_audio_path(outputs: Path, path: Path, project_id: str) -> Path:
        project = read_project(outputs, project_id)
        audio_name = project.generated_files.get("reference_audio")
        if audio_name is None:
            return path / "reference_audio.wav"
        candidate = path / audio_name
        return candidate

    def clear_analysis_state(
        outputs: Path,
        path: Path,
        project_id: str,
        analysis_state: str | None = None,
        analysis_message: str = "",
    ) -> None:
        clear_reference_analysis_outputs(path)
        project = read_project(outputs, project_id)
        project.generated_files.pop("reference_analysis", None)
        project.generated_files.pop("reference_analysis_markdown", None)
        for key in SCRIPT_GENERATED_FILE_KEYS:
            project.generated_files.pop(key, None)
        for status in project.step_statuses:
            if status.name == "Analysis" and analysis_state is not None:
                status.state = analysis_state
                status.message = analysis_message
            if status.name in ("Candidates", "Script", "Production", "Render"):
                status.state = "waiting"
                status.message = ""
        if analysis_state is not None:
            project.current_step = "Analysis"
        save_project(outputs, project)

    def mark_analysis_failed(outputs: Path, project_id: str, message: str) -> None:
        project = read_project(outputs, project_id)
        project.current_step = "Analysis"
        for status in project.step_statuses:
            if status.name == "Analysis":
                status.state = "failed"
                status.message = message
            elif status.name == "Candidates":
                status.state = "waiting"
                status.message = ""
        save_project(outputs, project)

    @router.get("")
    def get_reference(project_id: str, outputs: Path = Depends(outputs_dir_provider)):
        try:
            return read_reference_state(project_dir(outputs, project_id)).model_dump()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/search")
    def search_reference(
        project_id: str,
        payload: ReferenceSearchRequest,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            job = append_job(
                outputs,
                project_id,
                "youtube_search",
                "YouTube search",
                provider="youtube",
                command="search.list",
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Searching YouTube")
            client = youtube_client_factory(settings.youtube_api_key)
            candidates = client.search(payload)
            write_reference_candidates(project_dir(outputs, project_id), candidates)
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                f"Found {len(candidates)} reference candidates",
                output_paths=["reference_candidates.json"],
            )
            return {"candidates": [candidate.model_dump() for candidate in candidates]}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except (ValueError, httpx.HTTPError) as exc:
            message = provider_error_message(exc)
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.post("/direct")
    def add_direct_reference(
        project_id: str,
        payload: DirectReferenceRequest,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            job = append_job(
                outputs,
                project_id,
                "youtube_direct",
                "Direct reference metadata",
                provider="youtube",
                command="videos.list",
            )
            job_id = job.job_id
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "running",
                "Fetching direct link metadata",
            )
            client = youtube_client_factory(settings.youtube_api_key)
            candidate = client.get_direct(payload.url)
            path = project_dir(outputs, project_id)
            candidates = [
                item
                for item in read_reference_candidates(path)
                if item.video_id != candidate.video_id
            ]
            candidates.append(candidate)
            candidates = sort_by_vs_ratio(candidates)
            write_reference_candidates(path, candidates)
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Direct reference added",
                output_paths=["reference_candidates.json"],
            )
            return {
                "candidate": candidate.model_dump(),
                "candidates": [item.model_dump() for item in candidates],
            }
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except (ValueError, httpx.HTTPError) as exc:
            message = provider_error_message(exc)
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.post("/select")
    def select_reference(
        project_id: str,
        payload: SelectReferenceRequest,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            candidates = read_reference_candidates(path)
            matches = [candidate for candidate in candidates if candidate.video_id == payload.video_id]
            if not matches:
                raise HTTPException(status_code=404, detail="Reference candidate not found")
            selected = matches[0]
            clear_downstream_reference_outputs(path)
            write_selected_reference(path, selected)

            project = read_project(outputs, project_id)
            project.selected_reference_path = "selected_reference.json"
            project.selected_candidate_id = selected.video_id
            project.generated_files["selected_reference"] = "selected_reference.json"
            for key in [
                "reference_audio",
                "reference_raw_stt",
                "reference_script",
                "reference_analysis",
                "reference_analysis_markdown",
                *SCRIPT_GENERATED_FILE_KEYS,
            ]:
                project.generated_files.pop(key, None)
            project.current_step = "STT"
            for status in project.step_statuses:
                if status.name == "Reference":
                    status.state = "succeeded"
                    status.message = "Reference selected."
                elif status.name == "STT":
                    status.state = "waiting"
                    status.message = "Reference selected. Ready for audio and STT."
                elif status.name in WORKFLOW_STEPS[2:]:
                    status.state = "waiting"
                    status.message = ""
            save_project(outputs, project)
            return {"selected_reference": selected.model_dump()}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/audio/extract")
    def extract_audio(
        project_id: str,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            path = project_dir(outputs, project_id)
            selected = read_selected_reference(path)
            if selected is None:
                raise HTTPException(
                    status_code=400,
                    detail="Select a reference before extracting audio",
                )
            job = append_job(
                outputs,
                project_id,
                "reference_audio_extract",
                "Extract reference audio",
                input_paths=[selected.url],
                provider="yt-dlp",
                command=settings.yt_dlp_binary,
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Extracting reference audio")
            audio_path = audio_extractor(path, selected.url, settings.yt_dlp_binary)
            clear_audio_derivatives(outputs, path, project_id, audio_path.name)
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Reference audio extracted",
                output_paths=[audio_path.name],
            )
            return {"audio_path": audio_path.name}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except AudioExtractionError as exc:
            message = str(exc)
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/audio/upload")
    async def upload_audio(
        project_id: str,
        file: UploadFile,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            output_name = validate_audio_upload_name(file.filename or "")
            output_path = path / output_name
            await save_uploaded_audio(file, output_path)
            clear_audio_derivatives(outputs, path, project_id, output_name)
            return {"audio_path": output_name}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/stt")
    def run_reference_stt(
        project_id: str,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            path = project_dir(outputs, project_id)
            audio_path = reference_audio_path(outputs, path, project_id)
            if not audio_path.exists():
                selected = read_selected_reference(path)
                if selected is not None:
                    extract_job = append_job(
                        outputs,
                        project_id,
                        "reference_audio_extract",
                        "Extract reference audio",
                        input_paths=[selected.url],
                        provider="yt-dlp",
                        command=settings.yt_dlp_binary,
                    )
                    update_job_state(
                        outputs,
                        project_id,
                        extract_job.job_id,
                        "running",
                        "Extracting reference audio",
                    )
                    extracted = audio_extractor(path, selected.url, settings.yt_dlp_binary)
                    clear_audio_derivatives(outputs, path, project_id, extracted.name)
                    update_job_state(
                        outputs,
                        project_id,
                        extract_job.job_id,
                        "succeeded",
                        "Reference audio extracted",
                        output_paths=[extracted.name],
                    )
                    audio_path = extracted
                else:
                    raise HTTPException(status_code=400, detail="Reference audio is missing")
            job = append_job(
                outputs,
                project_id,
                "reference_stt",
                "Reference STT",
                input_paths=[audio_path.name],
                provider="openai",
                command=settings.openai_transcription_model,
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Running OpenAI STT")
            project = read_project(outputs, project_id)
            project.current_step = "STT"
            for status in project.step_statuses:
                if status.name == "STT":
                    status.state = "running"
                    status.message = "Running OpenAI STT."
            save_project(outputs, project)
            client = transcription_client_factory(
                settings.openai_api_key,
                settings.openai_transcription_model,
            )
            raw_stt = client.transcribe(audio_path)
            script = write_reference_stt_outputs(path, raw_stt)
            clear_analysis_state(outputs, path, project_id)
            project = read_project(outputs, project_id)
            project.generated_files["reference_raw_stt"] = REFERENCE_RAW_STT_FILE
            project.generated_files["reference_script"] = REFERENCE_SCRIPT_FILE
            save_project(outputs, project)
            project = read_project(outputs, project_id)
            project.current_step = "Analysis"
            for status in project.step_statuses:
                if status.name == "STT":
                    status.state = "succeeded"
                    status.message = "Reference STT complete."
                if status.name == "Analysis":
                    status.state = "waiting"
                    status.message = "Reference script is ready for analysis."
            save_project(outputs, project)
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Reference STT complete",
                output_paths=[REFERENCE_RAW_STT_FILE, REFERENCE_SCRIPT_FILE],
            )
            return {"reference_script": script}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except HTTPException:
            raise
        except Exception as exc:
            message = provider_error_message(exc)
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.post("/analyze")
    def analyze_reference(
        project_id: str,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            path = project_dir(outputs, project_id)
            script_path = path / REFERENCE_SCRIPT_FILE
            if not script_path.exists():
                raise HTTPException(status_code=400, detail="Reference script is missing")
            script = script_path.read_text(encoding="utf-8")
            job = append_job(
                outputs,
                project_id,
                "reference_analysis",
                "Analyze reference script",
                input_paths=[REFERENCE_SCRIPT_FILE],
                provider="openai",
                command=settings.openai_analysis_model,
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Analyzing reference script")
            clear_analysis_state(
                outputs,
                path,
                project_id,
                analysis_state="running",
                analysis_message="Analyzing reference script.",
            )
            client = analysis_client_factory(settings.openai_api_key, settings.openai_analysis_model)
            analysis = client.analyze(build_analysis_prompt(script))
            markdown = write_reference_analysis(path, analysis)
            project = read_project(outputs, project_id)
            project.generated_files["reference_analysis"] = "reference_analysis.json"
            project.generated_files["reference_analysis_markdown"] = "reference_analysis.md"
            project.current_step = "Candidates"
            for status in project.step_statuses:
                if status.name == "Analysis":
                    status.state = "succeeded"
                    status.message = "Reference analysis complete."
                elif status.name == "Candidates":
                    status.state = "waiting"
                    status.message = "Ready to generate candidates."
            save_project(outputs, project)
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Reference analysis complete",
                output_paths=["reference_analysis.json", "reference_analysis.md"],
            )
            return {"analysis": analysis, "analysis_markdown": markdown}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except HTTPException:
            raise
        except Exception as exc:
            message = provider_error_message(exc)
            fail_job(outputs, project_id, job_id, message)
            if job_id is not None:
                mark_analysis_failed(outputs, project_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    return router
