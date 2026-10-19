from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field


StepName = Literal["Reference", "STT", "Analysis", "Candidates", "Script", "Production", "Render"]
StepState = Literal["waiting", "running", "succeeded", "failed"]


WORKFLOW_STEPS: list[StepName] = [
    "Reference",
    "STT",
    "Analysis",
    "Candidates",
    "Script",
    "Production",
    "Render",
]


class StepStatus(BaseModel):
    name: StepName
    state: StepState = "waiting"
    message: str = ""


class Project(BaseModel):
    project_id: str
    project_title: str
    display_name: str
    created_at: str
    updated_at: str
    current_step: StepName = "Reference"
    step_statuses: list[StepStatus] = Field(default_factory=list)
    selected_reference_path: Optional[str] = None
    selected_candidate_id: Optional[str] = None
    settings_snapshot: dict = Field(default_factory=dict)
    job_history: list[dict] = Field(default_factory=list)
    generated_files: dict[str, str] = Field(default_factory=dict)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_step_statuses() -> list[StepStatus]:
    return [
        StepStatus(name=step, state="running" if step == "Reference" else "waiting")
        for step in WORKFLOW_STEPS
    ]
