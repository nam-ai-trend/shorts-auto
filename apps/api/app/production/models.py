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
    camera_movement: str | None = None
    is_locked: bool = False
    has_image: bool = False
    requires_character: bool = True
    required_props: list[str] = Field(default_factory=list)
    active_references: list[str] = Field(default_factory=list)
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


class ApplyMotionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    movement_id: str
    custom_instruction: str = ""


class RenderShortsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    thumbnail_duration_frames: int = 15


class ThumbnailGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = "nano_banana_pro"
    prompt: str | None = None


class ThumbnailFromSceneRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    scene_id: int = 1


class CharacterDefinition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "main_character"
    description: str = ""
    turnaround_prompt: str = ""


class KeyPropItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str  # "prop_1" | "prop_2"
    name: str = ""
    description: str = ""
    prompt: str = ""


class AssetSheetManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    has_sheet: bool = False
    master_sheet_url: str | None = None
    character_url: str | None = None
    prop_1_url: str | None = None
    prop_2_url: str | None = None
    prop_1_name: str = "Object 1"
    prop_2_name: str = "Object 2"
    character_name: str = "Main Character"
    created_at: str | None = None


class GenerateAssetSheetRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = "nano_banana_pro"


class BatchImageGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = "nano_banana_pro"
    use_asset_sheet: bool = False


class ConceptKit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    visual_style_id: str = "claymation"
    visual_style: str = "Cute professional claymation infographic"
    color_and_lighting: str = ""
    core_objects: list[str] = Field(default_factory=list)
    camera_composition: str = "9:16 vertical composition, shallow depth of field"
    continuity_rules: list[str] = Field(default_factory=list)
    character_definition: CharacterDefinition | None = None
    key_props: list[KeyPropItem] = Field(default_factory=list)
    master_asset_sheet_prompt: str = ""


class GeneratePromptsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    visual_style_id: str = "claymation"


class UpdateVisualStyleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    visual_style_id: str
    regenerate_prompts: bool = False


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

    # 썸네일 관리
    has_thumbnail: bool = False
    thumbnail_url: str | None = None

    # 에셋 시트 관리 (Visual Consistency)
    asset_sheet: AssetSheetManifest | None = None

    # 최종 쇼츠 렌더링 결과
    has_final_video: bool = False
    final_video_url: str | None = None

