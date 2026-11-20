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


class FactCheckItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str = Field(default="", max_length=500)
    status: str = Field(default="verified", max_length=100)
    evidence: str = Field(default="", max_length=1000)


class LoopDesign(BaseModel):
    model_config = ConfigDict(extra="ignore")

    loop_type: str = Field(default="", max_length=100)
    tail_bridge: str = Field(default="", max_length=500)
    head_hook: str = Field(default="", max_length=500)
    connected_preview: str = Field(default="", max_length=1200)


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
    display_script: str = Field(default="", max_length=5000)
    borrowed_reference_structure: str = Field(max_length=1600)
    fact_check_qa: list[FactCheckItem] = Field(default_factory=list)
    loop_design: Optional[LoopDesign] = None

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

    @field_validator("tags")
    @classmethod
    def clean_tags_text(cls, value: str) -> str:
        # #쇼츠, #shorts 제거
        tokens = [t.strip() for t in value.split() if t.strip()]
        filtered = [t for t in tokens if t not in ("#쇼츠", "#shorts", "쇼츠", "shorts")]
        return " ".join(filtered)

    @field_validator("keywords")
    @classmethod
    def clean_keywords_text(cls, value: str) -> str:
        # 쉼표 구분 키워드 파싱 및 맨 뒤에 과학쇼츠, 쇼츠, 과학지식 필수 추가 (# 없이 순수 키워드)
        mandatory = ["과학쇼츠", "쇼츠", "과학지식"]
        parts = [p.strip().lstrip("#") for p in value.split(",") if p.strip()]
        filtered: list[str] = [p for p in parts if p not in mandatory]
        filtered.extend(mandatory)
        return ", ".join(filtered)


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


class LoopValidationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_valid: bool
    score: int = Field(default=100, ge=0, le=100)
    loop_type: str = Field(default="상황 유발형", max_length=100)
    tail_bridge: str = Field(default="", max_length=500)
    head_hook: str = Field(default="", max_length=500)
    connected_preview: str = Field(default="", max_length=1200)
    evaluation: str = Field(default="", max_length=1000)
    issues: list[str] = Field(default_factory=list)


class FinalScriptState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    selected_candidate_id: str
    feedback: str = ""
    final_script: str
    display_script: str = ""
    tts_validation: TtsValidationResult
    loop_validation: Optional[LoopValidationResult] = None

    @field_validator("selected_candidate_id", "final_script")
    @classmethod
    def clean_required_text(cls, value: str, info) -> str:
        max_length = FINAL_SCRIPT_MAX_LENGTH if info.field_name == "final_script" else 80
        return clean_text(value, info.field_name, max_length)


class ScriptsState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: list[ScriptCandidate] = Field(default_factory=list)
    selected_candidate: Optional[ScriptCandidate] = None
    final_script: Optional[str] = None
    display_script: Optional[str] = None
    feedback: str = ""
    tts_validation: Optional[TtsValidationResult] = None
    loop_validation: Optional[LoopValidationResult] = None


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


class UpdateFinalScriptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_script: str = Field(min_length=1, max_length=FINAL_SCRIPT_MAX_LENGTH)

    @field_validator("final_script")
    @classmethod
    def clean_script(cls, value: str) -> str:
        return clean_text(value, "final_script", FINAL_SCRIPT_MAX_LENGTH)

