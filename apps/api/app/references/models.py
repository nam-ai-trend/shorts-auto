from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator


SourceType = Literal["search", "direct"]
DurationFilter = Literal[
    "under_60",
    "under_120",
    "under_180",
    "under_300",
    "over_300",
    "all",
]
DURATION_FILTER_MAX_SECONDS: dict[DurationFilter, Optional[int]] = {
    "under_60": 60,
    "under_120": 120,
    "under_180": 180,
    "under_300": 300,
    "over_300": None,
    "all": None,
}
TEXT_FIELD_LENGTHS = {
    "video_id": 32,
    "url": 500,
    "title": 500,
    "channel_id": 120,
    "channel_name": 200,
    "thumbnail_url": 1000,
    "upload_date": 80,
}


def _bounded_non_empty(value: str, field_name: str, max_length: int) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    if len(stripped) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return stripped


class ReferenceSearchRequest(BaseModel):
    keyword: Optional[str] = Field(default="", max_length=200)
    channel_query: Optional[str] = Field(default=None, max_length=200)
    published_after: Optional[str] = None
    published_before: Optional[str] = None
    duration_filter: DurationFilter = "under_60"
    max_duration_seconds: int = Field(default=60, ge=1, le=600)
    minimum_views: int = Field(default=0, ge=0)
    maximum_subscribers: Optional[int] = Field(default=None, ge=0)
    max_results: int = Field(default=25, ge=1, le=50)

    @model_validator(mode="after")
    def validate_keyword_or_channel(self) -> ReferenceSearchRequest:
        kw = (self.keyword or "").strip()
        cq = (self.channel_query or "").strip()
        if not kw and not cq:
            raise ValueError("Either keyword or channel_query must be provided and non-empty")
        self.keyword = kw
        self.channel_query = cq if cq else None
        return self

    @computed_field
    @property
    def effective_max_duration_seconds(self) -> Optional[int]:
        return DURATION_FILTER_MAX_SECONDS[self.duration_filter]

    def matches_duration(self, duration_seconds: int) -> bool:
        if self.duration_filter == "over_300":
            return duration_seconds > 300
        if self.duration_filter == "all":
            return True
        max_seconds = self.effective_max_duration_seconds
        return max_seconds is not None and duration_seconds <= max_seconds


class DirectReferenceRequest(BaseModel):
    url: str = Field(min_length=1, max_length=500)

    @field_validator("url")
    @classmethod
    def clean_url(cls, value: str) -> str:
        return _bounded_non_empty(value, "url", 500)


class SelectReferenceRequest(BaseModel):
    video_id: str = Field(min_length=1, max_length=32)

    @field_validator("video_id")
    @classmethod
    def clean_video_id(cls, value: str) -> str:
        return _bounded_non_empty(value, "video_id", 32)


class ReferenceCandidate(BaseModel):
    video_id: str = Field(max_length=32)
    url: str = Field(max_length=500)
    title: str = Field(max_length=500)
    channel_id: str = Field(max_length=120)
    channel_name: str = Field(max_length=200)
    thumbnail_url: str = Field(max_length=1000)
    upload_date: str = Field(max_length=80)
    duration_seconds: int = Field(ge=0)
    view_count: int = Field(ge=0)
    subscriber_count: Optional[int] = Field(default=None, ge=0)
    source_type: SourceType

    @field_validator(
        "video_id",
        "url",
        "title",
        "channel_id",
        "channel_name",
        "thumbnail_url",
        "upload_date",
    )
    @classmethod
    def clean_required_text(cls, value: str, info) -> str:
        return _bounded_non_empty(value, info.field_name, TEXT_FIELD_LENGTHS[info.field_name])

    @computed_field
    @property
    def vs_ratio(self) -> Optional[float]:
        if self.subscriber_count is None or self.subscriber_count <= 0:
            return None
        return round(self.view_count / self.subscriber_count, 4)


class ReferenceState(BaseModel):
    candidates: list[ReferenceCandidate] = Field(default_factory=list)
    selected_reference: Optional[ReferenceCandidate] = None
    reference_script: Optional[str] = None
    analysis: Optional[dict] = None
    analysis_markdown: Optional[str] = None
