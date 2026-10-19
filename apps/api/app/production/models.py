from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SceneTextBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    start: float = 0.0
    end: float = 0.0


class SceneItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene_id: int
    start: float
    end: float
    duration_frames: int
    text_blocks: list[SceneTextBlock] = Field(default_factory=list)


class ContinuityState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    camera: str = ""
    subject_state: str = ""
    lighting: str = ""
    handoff_description: str = ""
    prev_final_frame_url: str | None = None


class VideoSceneItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene_id: int
    target_duration: float
    start: float
    end: float
    duration_frames: int
    narration: str
    start_image_prompt: str
    start_image_url: str | None = None
    video_prompt: str = ""
    generated_video_url: str | None = None
    final_frame_url: str | None = None
    continuity: ContinuityState = Field(default_factory=ContinuityState)
    is_locked: bool = False
    last_feedback: str | None = None
    last_image_feedback: str | None = None
    last_video_feedback: str | None = None


class FeedbackRegenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    feedback: str = ""
    target: str = "image"  # "image" | "video" | "both" | "prompt_only"
    model: str | None = None
    duration: int = 5
    multi_shots: bool = False
    match_prev_frame: bool = True


class UpdateScenePromptsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start_image_prompt: str | None = None
    video_prompt: str | None = None


class RenderShortsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None



class ConceptKit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    visual_style: str = "Cute professional claymation infographic"
    color_and_lighting: str = ""
    core_objects: list[str] = Field(default_factory=list)
    camera_composition: str = "9:16 vertical composition, shallow depth of field"
    continuity_rules: list[str] = Field(default_factory=list)


class ProductionState(BaseModel):
    model_config = ConfigDict(extra="ignore")

    has_audio: bool = False
    audio_filename: str | None = None
    duration_seconds: float | None = None
    has_scene_data: bool = False
    scene_count: int = 0
    scenes: list[SceneItem] = Field(default_factory=list)

    # 비디오 씬 및 연속성 관리
    has_concept_kit: bool = False
    concept_kit: ConceptKit | None = None
    has_video_scenes: bool = False
    video_scene_count: int = 0
    video_scenes: list[VideoSceneItem] = Field(default_factory=list)

    # 최종 쇼츠 렌더링 결과
    has_final_video: bool = False
    final_video_url: str | None = None
