import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import {
  addDirectReference,
  alignSubtitlesAndScenes,
  createProject,
  extractReferenceAudio,
  fetchProductionState,
  fetchScriptsState,
  fetchProjects,
  fetchReferenceState,
  fetchSettingsStatus,
  finalizeScript,
  generateScriptCandidates,
  generateTtsAudio,
  getProject,
  runReferenceAnalysis,
  runReferenceStt,
  searchReferences,
  selectScriptCandidate,
  selectReference,
  updateProject
} from "../src/api";
import type {
  Project,
  ReferenceCandidate,
  ReferenceState,
  ScriptCandidate,
  ScriptsState,
  SettingsStatus
} from "../src/types";

vi.mock("../src/api", () => ({
  addDirectReference: vi.fn(),
  alignSubtitlesAndScenes: vi.fn(),
  createProject: vi.fn(),
  extractReferenceAudio: vi.fn(),
  fetchProductionState: vi.fn(),
  fetchProjects: vi.fn(),
  fetchReferenceState: vi.fn(),
  fetchScriptsState: vi.fn(),
  fetchSettingsStatus: vi.fn(),
  finalizeScript: vi.fn(),
  generateScriptCandidates: vi.fn(),
  generateTtsAudio: vi.fn(),
  getProject: vi.fn(),
  runReferenceAnalysis: vi.fn(),
  runReferenceStt: vi.fn(),
  searchReferences: vi.fn(),
  selectScriptCandidate: vi.fn(),
  selectReference: vi.fn(),
  updateProject: vi.fn()
}));

const project: Project = {
  project_id: "261011_2130",
  project_title: "테스트 쇼츠",
  display_name: "261011_테스트 쇼츠",
  created_at: "2026-10-11T21:30:00Z",
  updated_at: "2026-10-11T21:40:00Z",
  current_step: "Analysis",
  step_statuses: [
    { name: "Reference", state: "succeeded", message: "Reference selected" },
    { name: "STT", state: "succeeded", message: "Transcript ready" },
    { name: "Analysis", state: "running", message: "Finding hooks" },
    { name: "Candidates", state: "waiting", message: "" },
    { name: "Script", state: "waiting", message: "" },
    { name: "Production", state: "waiting", message: "" },
    { name: "Render", state: "waiting", message: "" }
  ],
  selected_reference_path: "inputs/reference.mp4",
  selected_candidate_id: null,
  settings_snapshot: {
    default_shorts_duration_seconds: 45,
    bgm_volume: 0.18
  },
  job_history: [],
  generated_files: {}
};

const settings: SettingsStatus = {
  openai_api_key: true,
  youtube_api_key: false,
  higgsfield_api_key: false,
  qwen3_tts_base_url: "http://127.0.0.1:8001",
  reference_voice_path: "assets/voice.wav",
  reference_voice_text: true,
  bgm_path: "assets/bgm.mp3",
  output_dir: "outputs",
  bgm_volume: 0.18
};

const candidate: ReferenceCandidate = {
  video_id: "abc123DEF45",
  url: "https://www.youtube.com/watch?v=abc123DEF45",
  title: "테스트 쇼츠",
  channel_id: "channel-1",
  channel_name: "채널",
  thumbnail_url: "https://example.com/thumb.jpg",
  upload_date: "2026-10-01T00:00:00Z",
  duration_seconds: 45,
  view_count: 120000,
  subscriber_count: 3000,
  source_type: "search",
  vs_ratio: 40
};

const referenceState: ReferenceState = {
  candidates: [candidate],
  selected_reference: null,
  reference_script: null,
  analysis: null,
  analysis_markdown: null
};

const scriptCandidate: ScriptCandidate = {
  candidate_id: "same-topic-1",
  candidate_type: "same_topic",
  title: "돈을 모으는 이상한 습관",
  hook: "돈을 못 모으는 사람은 이것부터 틀립니다.",
  target_viewer: "사회초년생",
  why_it_can_work: "자기 문제처럼 들리는 훅입니다.",
  main_curiosity_question: "왜 돈이 안 모일까?",
  structure_summary: "상식 반박, 원인, 반전, 결론.",
  draft_script: "돈을 못 모으는 사람은 의지가 약한 게 아닙니다.",
  borrowed_reference_structure: "레퍼런스의 상식 반박 구조를 빌립니다."
};

const scriptsState: ScriptsState = {
  candidates: [],
  selected_candidate: null,
  final_script: null,
  feedback: "",
  tts_validation: null
};

const addDirectReferenceMock = vi.mocked(addDirectReference);
const createProjectMock = vi.mocked(createProject);
const extractReferenceAudioMock = vi.mocked(extractReferenceAudio);
const fetchProjectsMock = vi.mocked(fetchProjects);
const fetchReferenceStateMock = vi.mocked(fetchReferenceState);
const fetchScriptsStateMock = vi.mocked(fetchScriptsState);
const fetchProductionStateMock = vi.mocked(fetchProductionState);
const fetchSettingsStatusMock = vi.mocked(fetchSettingsStatus);
const finalizeScriptMock = vi.mocked(finalizeScript);
const generateScriptCandidatesMock = vi.mocked(generateScriptCandidates);
const getProjectMock = vi.mocked(getProject);
const runReferenceAnalysisMock = vi.mocked(runReferenceAnalysis);
const runReferenceSttMock = vi.mocked(runReferenceStt);
const searchReferencesMock = vi.mocked(searchReferences);
const selectScriptCandidateMock = vi.mocked(selectScriptCandidate);
const selectReferenceMock = vi.mocked(selectReference);
const updateProjectMock = vi.mocked(updateProject);

describe("App", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    fetchProjectsMock.mockResolvedValue([project]);
    fetchReferenceStateMock.mockResolvedValue(referenceState);
    fetchScriptsStateMock.mockResolvedValue(scriptsState);
    fetchProductionStateMock.mockResolvedValue({
      has_audio: false,
      audio_filename: null,
      duration_seconds: null,
      has_scene_data: false,
      scene_count: 0,
      scenes: []
    });
    fetchSettingsStatusMock.mockResolvedValue(settings);
    generateScriptCandidatesMock.mockResolvedValue({ candidates: [scriptCandidate] });
    selectScriptCandidateMock.mockResolvedValue({ selected_candidate: scriptCandidate });
    finalizeScriptMock.mockResolvedValue({
      selected_candidate_id: "same-topic-1",
      feedback: "",
      final_script: "돈을 못 모으는 이유는 기준 때문입니다.",
      tts_validation: { is_valid: true, issues: [] }
    });
    getProjectMock.mockResolvedValue(project);
    runReferenceAnalysisMock.mockResolvedValue({
      analysis: { primary_structure: "common-sense conflict" },
      analysis_markdown: "# Reference Analysis"
    });
    runReferenceSttMock.mockResolvedValue({ reference_script: "첫 문장입니다." });
    searchReferencesMock.mockResolvedValue({ candidates: [candidate] });
    addDirectReferenceMock.mockResolvedValue({ candidate, candidates: [candidate] });
    selectReferenceMock.mockResolvedValue({ selected_reference: candidate });
    extractReferenceAudioMock.mockResolvedValue({ audio_path: "reference_audio.wav" });
    createProjectMock.mockResolvedValue({
      ...project,
      project_id: "261011_2200",
      project_title: "untitled",
      display_name: "261011_untitled"
    });
    updateProjectMock.mockResolvedValue({
      ...project,
      project_title: "변경된 제목",
      display_name: "261011_변경된 제목"
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("does not create a project when the prompt is canceled", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue(null);

    render(<App />);

    await screen.findByRole("heading", { name: project.display_name });
    await user.click(screen.getByRole("button", { name: /New Project/i }));

    expect(createProjectMock).not.toHaveBeenCalled();
  });

  it("creates an untitled project when the prompt is blank", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue("   ");

    render(<App />);

    await screen.findByRole("heading", { name: project.display_name });
    await user.click(screen.getByRole("button", { name: /New Project/i }));

    await waitFor(() => expect(createProjectMock).toHaveBeenCalledWith("untitled"));
    expect(screen.getByRole("heading", { name: "261011_untitled" })).toBeInTheDocument();
  });

  it("updates the selected project title from the project header", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "prompt").mockReturnValue("변경된 제목");

    render(<App />);

    await screen.findByRole("heading", { name: project.display_name });
    await user.click(screen.getByRole("button", { name: /Edit title/i }));

    await waitFor(() =>
      expect(updateProjectMock).toHaveBeenCalledWith(project.project_id, {
        project_title: "변경된 제목"
      })
    );
    expect(screen.getByRole("heading", { name: "261011_변경된 제목" })).toBeInTheDocument();
  });

  it("renders connected reference search and actions", async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: project.display_name });

    expect(screen.getByRole("textbox", { name: /Keyword/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Direct YouTube URL/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /최근 1개월/i }));
    expect(screen.getByLabelText(/Uploaded after/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Uploaded before/i)).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /Video length/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Minimum views/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Maximum subscribers/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Max results/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Search references/i })).toBeDisabled();

    await user.type(screen.getByRole("textbox", { name: /Keyword/i }), "돈");
    await user.click(screen.getByRole("button", { name: /Search references/i }));

    await waitFor(() =>
      expect(searchReferencesMock).toHaveBeenCalledWith(
        project.project_id,
        expect.objectContaining({ keyword: "돈" })
      )
    );
  });

  it("loads scripts state and can generate script candidates", async () => {
    const user = userEvent.setup();
    render(<App />);

    await screen.findByRole("heading", { name: project.display_name });
    await user.click(screen.getByRole("button", { name: /Generate candidates/i }));

    await waitFor(() => expect(fetchScriptsStateMock).toHaveBeenCalledWith(project.project_id));
    await waitFor(() => expect(generateScriptCandidatesMock).toHaveBeenCalledWith(project.project_id));
  });
});
