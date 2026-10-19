from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CandidateKind = Literal["draft_a", "draft_b", "same_topic", "different_topic"]
FINAL_SCRIPT_MAX_LENGTH = 5000
ISSUE_MAX_LENGTH = 300


def clean_text(value: str, field_name: str, max_length: int = 4000) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    if len(stripped) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return stripped


class ScriptCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_id: str = Field(max_length=80)
    candidate_type: CandidateKind
    title: str = Field(max_length=200)
    title_options: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=1500)
    tags: str = Field(default="", max_length=1000)
    keywords: str = Field(default="", max_length=1000)
    hook: str = Field(max_length=500)
    target_viewer: str = Field(max_length=500)
    why_it_can_work: str = Field(max_length=1200)
    main_curiosity_question: str = Field(max_length=500)
    structure_summary: str = Field(max_length=1200)
    draft_script: str = Field(max_length=5000)
    borrowed_reference_structure: str = Field(max_length=1600)

    @field_validator(
        "candidate_id",
        "title",
        "hook",
        "target_viewer",
        "why_it_can_work",
        "main_curiosity_question",
        "structure_summary",
        "draft_script",
        "borrowed_reference_structure",
    )
    @classmethod
    def clean_required_text(cls, value: str, info) -> str:
        return clean_text(value, info.field_name)

    @field_validator("description")
    @classmethod
    def clean_description_text(cls, value: str) -> str:
        # 설명란 문구에서 ** 나 ", ' 문자 제거
        cleaned = value.replace("**", "").replace('"', "").replace("'", "")
        return cleaned.strip()


class TtsValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_valid: bool
    issues: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("issues")
    @classmethod
    def clean_issues(cls, value: list[str]) -> list[str]:
        return [clean_text(issue, "issue", ISSUE_MAX_LENGTH) for issue in value]

    @model_validator(mode="after")
    def validate_issue_consistency(self) -> "TtsValidationResult":
        if self.is_valid and self.issues:
            raise ValueError("valid TTS results must not include issues")
        if not self.is_valid and not self.issues:
            raise ValueError("invalid TTS results must include at least one issue")
        return self


class FinalScriptState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_candidate_id: str
    feedback: str = ""
    final_script: str
    tts_validation: TtsValidationResult

    @field_validator("selected_candidate_id", "final_script")
    @classmethod
    def clean_required_text(cls, value: str, info) -> str:
        max_length = FINAL_SCRIPT_MAX_LENGTH if info.field_name == "final_script" else 80
        return clean_text(value, info.field_name, max_length)


class ScriptsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ScriptCandidate] = Field(default_factory=list)
    selected_candidate: Optional[ScriptCandidate] = None
    final_script: Optional[str] = None
    feedback: str = ""
    tts_validation: Optional[TtsValidationResult] = None


class SelectScriptCandidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1, max_length=80)

    @field_validator("candidate_id")
    @classmethod
    def clean_candidate_id(cls, value: str) -> str:
        return clean_text(value, "candidate_id", 80)


class FinalizeScriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback: str = Field(default="", max_length=2000)

    @field_validator("feedback")
    @classmethod
    def clean_feedback(cls, value: str) -> str:
        return value.strip()


class GenerateCandidatesRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    feedback: str = Field(default="", max_length=2000)

    @field_validator("feedback")
    @classmethod
    def clean_feedback(cls, value: str) -> str:
        return value.strip()
