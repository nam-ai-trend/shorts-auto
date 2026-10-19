from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.core.settings import AppSettings
from app.jobs.service import append_job, update_job_state
from app.projects.service import read_project, save_project
from app.references.files import REFERENCE_ANALYSIS_FILE, REFERENCE_SCRIPT_FILE
from app.references.openai_clients import AnalysisClient
from app.production.service import (
    CONCEPT_KIT_FILENAME,
    VIDEO_SCENES_FILENAME,
    generate_concept_kit_and_video_scenes,
)
from app.scripts.files import (
    FINAL_SCRIPT_FILE,
    FINAL_SCRIPT_STATE_FILE,
    SCRIPT_CANDIDATES_FILE,
    SELECTED_SCRIPT_CANDIDATE_FILE,
    read_script_candidates,
    read_script_state,
    write_final_script_state,
    write_script_candidates,
    write_selected_script_candidate,
)
from app.scripts.generation import (
    build_candidate_generation_prompt,
    build_final_script_prompt,
    build_final_script_state,
    extract_final_script,
    validate_candidate_payload,
)
from app.scripts.models import (
    FinalizeScriptRequest,
    GenerateCandidatesRequest,
    SelectScriptCandidateRequest,
)


def create_scripts_router(
    outputs_dir_provider: Callable[[], Path],
    settings_provider: Callable[[], AppSettings],
    script_client_factory: Callable[[str, str], AnalysisClient],
) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/scripts", tags=["scripts"])

    def project_dir(outputs_dir: Path, project_id: str) -> Path:
        read_project(outputs_dir, project_id)
        return outputs_dir / project_id

    def fail_job(outputs_dir: Path, project_id: str, job_id: str | None, message: str) -> None:
        if job_id is None:
            return
        update_job_state(outputs_dir, project_id, job_id, "failed", message, error_message=message)

    @router.get("")
    def get_scripts(project_id: str, outputs: Path = Depends(outputs_dir_provider)):
        try:
            return read_script_state(project_dir(outputs, project_id)).model_dump()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/candidates")
    def generate_candidates(
        project_id: str,
        payload: GenerateCandidatesRequest | None = None,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        feedback = payload.feedback.strip() if payload else ""
        try:
            path = project_dir(outputs, project_id)
            script_path = path / REFERENCE_SCRIPT_FILE
            analysis_path = path / REFERENCE_ANALYSIS_FILE
            if not script_path.exists() or not analysis_path.exists():
                raise HTTPException(status_code=400, detail="Reference script and analysis are required")

            reference_script = script_path.read_text(encoding="utf-8")
            reference_analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            job = append_job(
                outputs,
                project_id,
                "script_candidates",
                "Generate script candidates",
                input_paths=[REFERENCE_SCRIPT_FILE, REFERENCE_ANALYSIS_FILE],
                provider="openai",
                command=settings.openai_analysis_model,
            )
            job_id = job.job_id
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "running",
                "Generating script drafts based on analysis and feedback",
            )
            client = script_client_factory(settings.openai_api_key, settings.openai_analysis_model)
            prompt = build_candidate_generation_prompt(reference_script, reference_analysis, feedback)
            response_payload = client.analyze(prompt)
            candidates = validate_candidate_payload(response_payload)
            write_script_candidates(path, candidates)

            project = read_project(outputs, project_id)
            project.generated_files["script_candidates"] = SCRIPT_CANDIDATES_FILE
            project.current_step = "Candidates"
            for status in project.step_statuses:
                if status.name == "Candidates":
                    status.state = "succeeded"
                    status.message = f"{len(candidates)} candidate drafts are ready for selection."
                elif status.name == "Script":
                    status.state = "waiting"
                    status.message = "Candidate drafts generated. Select a candidate to finalize script."
            save_project(outputs, project)
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Script candidates generated",
                output_paths=[SCRIPT_CANDIDATES_FILE],
            )
            return {"candidates": [item.model_dump() for item in candidates]}
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    @router.post("/select")
    def select_candidate(
        project_id: str,
        payload: SelectScriptCandidateRequest,
        outputs: Path = Depends(outputs_dir_provider),
    ):
        try:
            path = project_dir(outputs, project_id)
            matches = [
                item
                for item in read_script_candidates(path)
                if item.candidate_id == payload.candidate_id
            ]
            if not matches:
                raise HTTPException(status_code=404, detail="Script candidate not found")
            selected = matches[0]
            write_selected_script_candidate(path, selected)

            project = read_project(outputs, project_id)
            project.selected_candidate_id = selected.candidate_id
            project.generated_files["selected_script_candidate"] = SELECTED_SCRIPT_CANDIDATE_FILE
            project.current_step = "Script"
            for status in project.step_statuses:
                if status.name == "Candidates":
                    status.state = "succeeded"
                    status.message = "Script candidate selected."
                elif status.name == "Script":
                    status.state = "running"
                    status.message = "Ready to finalize TTS script."
            save_project(outputs, project)
            return {"selected_candidate": selected.model_dump()}
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/finalize")
    def finalize_script(
        project_id: str,
        payload: FinalizeScriptRequest,
        outputs: Path = Depends(outputs_dir_provider),
        settings: AppSettings = Depends(settings_provider),
    ):
        job_id: str | None = None
        try:
            path = project_dir(outputs, project_id)
            selected = read_script_state(path).selected_candidate
            if selected is None:
                raise HTTPException(status_code=400, detail="Select a script candidate before finalizing")

            job = append_job(
                outputs,
                project_id,
                "final_script",
                "Finalize TTS script",
                input_paths=[SELECTED_SCRIPT_CANDIDATE_FILE],
                provider="openai",
                command=settings.openai_analysis_model,
            )
            job_id = job.job_id
            update_job_state(outputs, project_id, job.job_id, "running", "Finalizing TTS-ready script")
            client = script_client_factory(settings.openai_api_key, settings.openai_analysis_model)
            response = client.analyze(build_final_script_prompt(selected, payload.feedback))
            final_script = extract_final_script(response)
            state = build_final_script_state(selected.candidate_id, payload.feedback, final_script)
            write_final_script_state(path, state)

            project = read_project(outputs, project_id)
            project.generated_files["final_script"] = FINAL_SCRIPT_FILE
            project.generated_files["final_script_state"] = FINAL_SCRIPT_STATE_FILE

            # Finalize script 시 대본과 함께 각 씬의 이미지 & 비디오 프롬프트 자동 생성!
            try:
                generate_concept_kit_and_video_scenes(path, settings)
                project.generated_files["concept_kit"] = CONCEPT_KIT_FILENAME
                project.generated_files["video_scenes"] = VIDEO_SCENES_FILENAME
            except Exception:
                pass

            project.current_step = "Production"
            for status in project.step_statuses:
                if status.name == "Script":
                    status.state = "succeeded"
                    status.message = "Final TTS-ready script complete."
                elif status.name == "Production":
                    status.state = "waiting"
                    status.message = "Script and scene prompts ready. Ready for TTS voice and images."
            save_project(outputs, project)
            update_job_state(
                outputs,
                project_id,
                job.job_id,
                "succeeded",
                "Final script complete",
                output_paths=[FINAL_SCRIPT_FILE, FINAL_SCRIPT_STATE_FILE],
            )
            return state.model_dump()
        except HTTPException:
            raise
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Project not found") from exc
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            fail_job(outputs, project_id, job_id, message)
            raise HTTPException(status_code=400, detail=message) from exc

    return router
