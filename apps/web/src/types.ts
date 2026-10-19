export type StepName =
  | "Reference"
  | "STT"
  | "Analysis"
  | "Candidates"
  | "Script"
  | "Production"
  | "Render";

export type StepState = "waiting" | "running" | "succeeded" | "failed";

export type JobState = "pending" | "running" | "succeeded" | "failed";

export interface StepStatus {
  readonly name: StepName;
  readonly state: StepState;
  readonly message: string;
}

export interface JobLog {
  readonly timestamp: string;
  readonly message: string;
}

export interface JobRecord {
  readonly job_id: string;
  readonly job_type: string;
  readonly label: string;
  readonly provider: string | null;
  readonly command: string | null;
  readonly state: JobState;
  readonly created_at: string;
  readonly updated_at: string;
  readonly started_at: string | null;
  readonly ended_at: string | null;
  readonly error_message: string | null;
  readonly input_paths: readonly string[];
  readonly output_paths: readonly string[];
  readonly logs: readonly JobLog[];
}

export interface Project {
  readonly project_id: string;
  readonly project_title: string;
  readonly display_name: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly current_step: StepName;
  readonly step_statuses: readonly StepStatus[];
  readonly selected_reference_path: string | null;
  readonly selected_candidate_id: string | null;
  readonly settings_snapshot: Readonly<Record<string, unknown>>;
  readonly job_history: readonly JobRecord[];
  readonly generated_files: Readonly<Record<string, string>>;
}

export interface ProjectsResponse {
  readonly projects: readonly Project[];
}

export interface ProjectResponse {
  readonly project: Project;
}

export interface SettingsStatus {
  readonly openai_api_key: boolean;
  readonly youtube_api_key: boolean;
  readonly higgsfield_api_key: boolean;
  readonly qwen3_tts_base_url: string;
  readonly reference_voice_path: string;
  readonly reference_voice_text: boolean;
  readonly bgm_path: string;
  readonly output_dir: string;
  readonly bgm_volume: number;
}

export interface CreateProjectPayload {
  readonly project_title: string;
}

export interface UpdateProjectPayload {
  readonly project_title: string;
}

export interface ReferenceCandidate {
  readonly video_id: string;
  readonly url: string;
  readonly title: string;
  readonly channel_id: string;
  readonly channel_name: string;
  readonly thumbnail_url: string;
  readonly upload_date: string;
  readonly duration_seconds: number;
  readonly view_count: number;
  readonly subscriber_count: number | null;
  readonly source_type: "search" | "direct";
  readonly vs_ratio: number | null;
}

export interface ReferenceState {
  readonly candidates: readonly ReferenceCandidate[];
  readonly selected_reference: ReferenceCandidate | null;
  readonly reference_script: string | null;
  readonly analysis: Readonly<Record<string, unknown>> | null;
  readonly analysis_markdown: string | null;
}

export type DurationFilter =
  | "under_60"
  | "under_120"
  | "under_180"
  | "under_300"
  | "over_300"
  | "all";

export interface ReferenceSearchPayload {
  readonly keyword?: string;
  readonly channel_query?: string;
  readonly published_after?: string;
  readonly published_before?: string;
  readonly duration_filter: DurationFilter;
  readonly max_duration_seconds: number;
  readonly minimum_views: number;
  readonly maximum_subscribers?: number;
  readonly max_results: number;
}

export interface ScriptCandidate {
  readonly candidate_id: string;
  readonly candidate_type: "draft_a" | "draft_b" | "same_topic" | "different_topic";
  readonly title: string;
  readonly title_options?: readonly string[];
  readonly description?: string;
  readonly tags?: string;
  readonly keywords?: string;
  readonly hook: string;
  readonly target_viewer: string;
  readonly why_it_can_work: string;
  readonly main_curiosity_question: string;
  readonly structure_summary: string;
  readonly draft_script: string;
  readonly borrowed_reference_structure: string;
}

export interface TtsValidationResult {
  readonly is_valid: boolean;
  readonly issues: readonly string[];
}

export interface ScriptsState {
  readonly candidates: readonly ScriptCandidate[];
  readonly selected_candidate: ScriptCandidate | null;
  readonly final_script: string | null;
  readonly feedback: string;
  readonly tts_validation: TtsValidationResult | null;
}

export interface SceneTextBlock {
  readonly text: string;
  readonly start: number;
  readonly end: number;
}

export interface SceneItem {
  readonly scene_id: number;
  readonly start: number;
  readonly end: number;
  readonly duration_frames: number;
  readonly text_blocks: readonly SceneTextBlock[];
}

export interface ContinuityState {
  readonly camera: string;
  readonly subject_state: string;
  readonly lighting: string;
  readonly handoff_description: string;
  readonly prev_final_frame_url: string | null;
}

export interface VideoSceneItem {
  readonly scene_id: number;
  readonly target_duration: number;
  readonly start: number;
  readonly end: number;
  readonly duration_frames: number;
  readonly narration: string;
  readonly start_image_prompt: string;
  readonly start_image_url: string | null;
  readonly video_prompt: string;
  readonly generated_video_url: string | null;
  readonly final_frame_url: string | null;
  readonly continuity: ContinuityState;
  readonly is_locked: boolean;
  readonly last_feedback?: string | null;
  readonly last_image_feedback?: string | null;
  readonly last_video_feedback?: string | null;
}

export interface ConceptKit {
  readonly visual_style: string;
  readonly color_and_lighting: string;
  readonly core_objects: readonly string[];
  readonly camera_composition: string;
  readonly continuity_rules: readonly string[];
}

export interface ProductionState {
  readonly has_audio: boolean;
  readonly audio_filename: string | null;
  readonly duration_seconds: number | null;
  readonly has_scene_data: boolean;
  readonly scene_count: number;
  readonly scenes: readonly SceneItem[];
  readonly has_concept_kit?: boolean;
  readonly concept_kit?: ConceptKit | null;
  readonly has_video_scenes?: boolean;
  readonly video_scene_count?: number;
  readonly video_scenes?: readonly VideoSceneItem[];
  readonly has_final_video?: boolean;
  readonly final_video_url?: string | null;
}


