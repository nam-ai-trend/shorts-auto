import type {
  ProductionState,
  Project,
  ProjectResponse,
  ProjectsResponse,
  ReferenceCandidate,
  ReferenceSearchPayload,
  ReferenceState,
  ScriptCandidate,
  ScriptsState,
  SettingsStatus,
  TtsValidationResult,
  UpdateProjectPayload
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function fetchProjects(): Promise<readonly Project[]> {
  return request<ProjectsResponse>("/api/projects").then((data) => data.projects);
}

export function getProject(projectId: string): Promise<Project> {
  return request<ProjectResponse>(`/api/projects/${encodeURIComponent(projectId)}`).then((data) => data.project);
}

export function createProject(projectTitle: string): Promise<Project> {
  return request<ProjectResponse>("/api/projects", {
    method: "POST",
    body: JSON.stringify({ project_title: projectTitle })
  }).then((data) => data.project);
}

export function fetchSettingsStatus(): Promise<SettingsStatus> {
  return request<SettingsStatus>("/api/settings/status");
}

export function updateProject(projectId: string, payload: UpdateProjectPayload): Promise<Project> {
  return request<ProjectResponse>(`/api/projects/${encodeURIComponent(projectId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  }).then((data) => data.project);
}

export function fetchReferenceState(projectId: string): Promise<ReferenceState> {
  return request<ReferenceState>(`/api/projects/${encodeURIComponent(projectId)}/reference`);
}

export function searchReferences(
  projectId: string,
  payload: ReferenceSearchPayload
): Promise<{ candidates: readonly ReferenceCandidate[] }> {
  return request<{ candidates: readonly ReferenceCandidate[] }>(
    `/api/projects/${encodeURIComponent(projectId)}/reference/search`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export function addDirectReference(
  projectId: string,
  url: string
): Promise<{ candidate: ReferenceCandidate; candidates: readonly ReferenceCandidate[] }> {
  return request<{ candidate: ReferenceCandidate; candidates: readonly ReferenceCandidate[] }>(
    `/api/projects/${encodeURIComponent(projectId)}/reference/direct`,
    {
      method: "POST",
      body: JSON.stringify({ url })
    }
  );
}

export function selectReference(
  projectId: string,
  videoId: string
): Promise<{ selected_reference: ReferenceCandidate }> {
  return request<{ selected_reference: ReferenceCandidate }>(
    `/api/projects/${encodeURIComponent(projectId)}/reference/select`,
    {
      method: "POST",
      body: JSON.stringify({ video_id: videoId })
    }
  );
}

export function extractReferenceAudio(projectId: string): Promise<{ audio_path: string }> {
  return request<{ audio_path: string }>(
    `/api/projects/${encodeURIComponent(projectId)}/reference/audio/extract`,
    { method: "POST" }
  );
}

export function runReferenceStt(projectId: string): Promise<{ reference_script: string }> {
  return request<{ reference_script: string }>(
    `/api/projects/${encodeURIComponent(projectId)}/reference/stt`,
    { method: "POST" }
  );
}

export function runReferenceAnalysis(
  projectId: string
): Promise<Pick<ReferenceState, "analysis" | "analysis_markdown">> {
  return request<Pick<ReferenceState, "analysis" | "analysis_markdown">>(
    `/api/projects/${encodeURIComponent(projectId)}/reference/analyze`,
    { method: "POST" }
  );
}

export function fetchScriptsState(projectId: string): Promise<ScriptsState> {
  return request<ScriptsState>(`/api/projects/${encodeURIComponent(projectId)}/scripts`);
}

export function generateScriptCandidates(
  projectId: string,
  feedback?: string
): Promise<{ candidates: readonly ScriptCandidate[] }> {
  return request<{ candidates: readonly ScriptCandidate[] }>(
    `/api/projects/${encodeURIComponent(projectId)}/scripts/candidates`,
    {
      method: "POST",
      body: JSON.stringify({ feedback: feedback ?? "" })
    }
  );
}

export function selectScriptCandidate(
  projectId: string,
  candidateId: string
): Promise<{ selected_candidate: ScriptCandidate }> {
  return request<{ selected_candidate: ScriptCandidate }>(
    `/api/projects/${encodeURIComponent(projectId)}/scripts/select`,
    {
      method: "POST",
      body: JSON.stringify({ candidate_id: candidateId })
    }
  );
}

export function finalizeScript(
  projectId: string,
  feedback: string
): Promise<{
  selected_candidate_id: string;
  feedback: string;
  final_script: string;
  tts_validation: TtsValidationResult;
}> {
  return request<{
    selected_candidate_id: string;
    feedback: string;
    final_script: string;
    tts_validation: TtsValidationResult;
  }>(`/api/projects/${encodeURIComponent(projectId)}/scripts/finalize`, {
    method: "POST",
    body: JSON.stringify({ feedback })
  });
}

export function fetchProductionState(projectId: string): Promise<ProductionState> {
  return request<ProductionState>(`/api/projects/${encodeURIComponent(projectId)}/production`);
}

export function generateTtsAudio(projectId: string): Promise<ProductionState> {
  return request<ProductionState>(`/api/projects/${encodeURIComponent(projectId)}/production/tts`, {
    method: "POST"
  });
}

export function alignSubtitlesAndScenes(projectId: string): Promise<ProductionState> {
  return request<ProductionState>(`/api/projects/${encodeURIComponent(projectId)}/production/align`, {
    method: "POST"
  });
}

export function generateConcepts(projectId: string): Promise<ProductionState> {
  return request<ProductionState>(`/api/projects/${encodeURIComponent(projectId)}/production/concepts`, {
    method: "POST"
  });
}

export function generateSceneImage(
  projectId: string,
  sceneId: number,
  model: string = "nano_banana_pro"
): Promise<ProductionState> {
  return request<ProductionState>(
    `/api/projects/${encodeURIComponent(projectId)}/production/scenes/${sceneId}/image?model=${encodeURIComponent(model)}`,
    { method: "POST" }
  );
}

export function generateAllSceneImages(
  projectId: string,
  model: string = "nano_banana_pro"
): Promise<ProductionState> {
  return request<ProductionState>(
    `/api/projects/${encodeURIComponent(projectId)}/production/scenes/images?model=${encodeURIComponent(model)}`,
    { method: "POST" }
  );
}

export function generateSceneVideo(
  projectId: string,
  sceneId: number,
  model: string = "kling_o3_flf",
  duration: number = 5,
  multiShots: boolean = false,
  matchPrevFrame: boolean = true
): Promise<ProductionState> {
  return request<ProductionState>(
    `/api/projects/${encodeURIComponent(projectId)}/production/scenes/${sceneId}/video?model=${encodeURIComponent(model)}&duration=${duration}&multi_shots=${multiShots}&match_prev_frame=${matchPrevFrame}`,
    { method: "POST" }
  );
}

export function passContinuityToNext(
  projectId: string,
  sceneId: number
): Promise<ProductionState> {
  return request<ProductionState>(
    `/api/projects/${encodeURIComponent(projectId)}/production/scenes/${sceneId}/pass-next`,
    { method: "POST" }
  );
}

export function renderShorts(projectId: string, title?: string): Promise<ProductionState> {
  return request<ProductionState>(
    `/api/projects/${encodeURIComponent(projectId)}/production/render`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(title !== undefined ? { title } : {})
    }
  );
}

export function regenerateSceneWithFeedback(
  projectId: string,
  sceneId: number,
  feedback: string,
  target: "image" | "video" | "both" | "prompt_only",
  model?: string,
  duration: number = 5,
  multiShots: boolean = false,
  matchPrevFrame: boolean = true
): Promise<ProductionState> {
  return request<ProductionState>(
    `/api/projects/${encodeURIComponent(projectId)}/production/scenes/${sceneId}/feedback-regenerate`,
    {
      method: "POST",
      body: JSON.stringify({
        feedback,
        target,
        model,
        duration,
        multi_shots: multiShots,
        match_prev_frame: matchPrevFrame,
      }),
    }
  );
}

export function updateScenePrompts(
  projectId: string,
  sceneId: number,
  startImagePrompt?: string,
  videoPrompt?: string
): Promise<ProductionState> {
  return request<ProductionState>(
    `/api/projects/${encodeURIComponent(projectId)}/production/scenes/${sceneId}/prompts`,
    {
      method: "PUT",
      body: JSON.stringify({
        start_image_prompt: startImagePrompt,
        video_prompt: videoPrompt,
      }),
    }
  );
}
