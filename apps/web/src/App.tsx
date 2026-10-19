import { useEffect, useMemo, useState } from "react";

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
  generateAllSceneImages,
  generateConcepts,
  generateSceneImage,
  generateSceneVideo,
  passContinuityToNext,
  renderShorts,
  generateScriptCandidates,
  generateTtsAudio,
  getProject,
  regenerateSceneWithFeedback,
  runReferenceAnalysis,
  runReferenceStt,
  searchReferences,
  selectScriptCandidate,
  selectReference,
  updateProject,
  updateScenePrompts
} from "./api";
import { CandidateDraftsPanel } from "./components/CandidateDraftsPanel";
import { FinalScriptPanel } from "./components/FinalScriptPanel";
import { ProductionPanel } from "./components/ProductionPanel";
import { ProjectDashboard } from "./components/ProjectDashboard";
import { ProjectWorkflow } from "./components/ProjectWorkflow";
import { ReferenceAnalysisPanel } from "./components/ReferenceAnalysisPanel";
import { ReferenceSearchPanel } from "./components/ReferenceSearchPanel";
import { ReferenceTranscriptPanel } from "./components/ReferenceTranscriptPanel";
import { SettingsPanel } from "./components/SettingsPanel";
import type {
  ProductionState,
  Project,
  ReferenceSearchPayload,
  ReferenceState,
  ScriptsState,
  SettingsStatus,
  VideoSceneItem
} from "./types";

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}

export default function App() {
  const [projects, setProjects] = useState<readonly Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [referenceState, setReferenceState] = useState<ReferenceState | null>(null);
  const [scriptsState, setScriptsState] = useState<ScriptsState | null>(null);
  const [productionState, setProductionState] = useState<ProductionState | null>(null);
  const [settings, setSettings] = useState<SettingsStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isReferenceBusy, setIsReferenceBusy] = useState(false);
  const [isAudioBusy, setIsAudioBusy] = useState(false);
  const [isSttBusy, setIsSttBusy] = useState(false);
  const [isAnalysisBusy, setIsAnalysisBusy] = useState(false);
  const [isScriptBusy, setIsScriptBusy] = useState(false);
  const [isProductionBusy, setIsProductionBusy] = useState(false);
  const [videoTitle, setVideoTitle] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedProject?.project_title) {
      setVideoTitle(selectedProject.project_title);
    } else {
      setVideoTitle("");
    }
  }, [selectedProject?.project_id, selectedProject?.project_title]);

  useEffect(() => {
    let isActive = true;

    Promise.all([fetchProjects(), fetchSettingsStatus()])
      .then(([loadedProjects, loadedSettings]) => {
        if (!isActive) {
          return;
        }
        setProjects(loadedProjects);
        setSettings(loadedSettings);
        setSelectedProject((current) => current ?? loadedProjects[0] ?? null);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setError(reason instanceof Error ? reason.message : "데이터를 불러오지 못했습니다.");
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProject) {
      setReferenceState(null);
      setScriptsState(null);
      setProductionState(null);
      return;
    }

    let isActive = true;
    Promise.all([
      fetchReferenceState(selectedProject.project_id),
      fetchScriptsState(selectedProject.project_id),
      fetchProductionState(selectedProject.project_id)
    ])
      .then(([reference, scripts, production]) => {
        if (isActive) {
          setReferenceState(reference);
          setScriptsState(scripts);
          setProductionState(production);
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (isActive) {
          setReferenceState(null);
          setScriptsState(null);
          setProductionState(null);
          setError(reason instanceof Error ? reason.message : "프로젝트 상태를 불러오지 못했습니다.");
        }
      });

    return () => {
      isActive = false;
    };
  }, [selectedProject?.project_id]);

  const generatedFiles = useMemo(() => {
    return selectedProject ? Object.entries(selectedProject.generated_files) : [];
  }, [selectedProject]);

  async function handleCreateProject() {
    const titleInput = window.prompt("Project title", "untitled");
    if (titleInput === null) {
      return;
    }
    const title = titleInput.trim() || "untitled";

    try {
      const project = await createProject(title);
      setProjects((current) => [project, ...current]);
      setSelectedProject(project);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "프로젝트를 만들지 못했습니다.");
    }
  }

  async function handleEditTitle() {
    if (!selectedProject) {
      return;
    }
    const titleInput = window.prompt("Project title", selectedProject.project_title);
    if (titleInput === null) {
      return;
    }
    const title = titleInput.trim() || "untitled";

    try {
      const project = await updateProject(selectedProject.project_id, { project_title: title });
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setSelectedProject(project);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "프로젝트 제목을 바꾸지 못했습니다.");
    }
  }

  async function runReferenceAction(action: () => Promise<unknown>) {
    if (!selectedProject) {
      return;
    }
    setIsReferenceBusy(true);
    try {
      await action();
      const [project, state] = await Promise.all([
        getProject(selectedProject.project_id),
        fetchReferenceState(selectedProject.project_id)
      ]);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setReferenceState(state);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "레퍼런스 작업에 실패했습니다.");
    } finally {
      setIsReferenceBusy(false);
    }
  }

  async function runScriptAction(action: () => Promise<unknown>) {
    if (!selectedProject) {
      return;
    }
    setIsScriptBusy(true);
    try {
      await action();
      const [project, state] = await Promise.all([
        getProject(selectedProject.project_id),
        fetchScriptsState(selectedProject.project_id)
      ]);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setScriptsState(state);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "대본 작업에 실패했습니다.");
    } finally {
      setIsScriptBusy(false);
    }
  }

  function handleReferenceSearch(payload: ReferenceSearchPayload) {
    if (!selectedProject) {
      return;
    }
    void runReferenceAction(() => searchReferences(selectedProject.project_id, payload));
  }

  function handleAddDirectReference(url: string) {
    if (!selectedProject) {
      return;
    }
    // Direct URL 추가 후 자동으로 해당 영상을 Selected Reference로 선택
    void runReferenceAction(async () => {
      const result = await addDirectReference(selectedProject.project_id, url);
      if (result.candidate?.video_id) {
        await selectReference(selectedProject.project_id, result.candidate.video_id);
      }
    });
  }

  function handleSelectReference(videoId: string) {
    if (!selectedProject) {
      return;
    }
    void runReferenceAction(() => selectReference(selectedProject.project_id, videoId));
  }

  const hasAudio = Boolean(selectedProject?.generated_files?.reference_audio);
  const hasSelectedReference = Boolean(selectedProject?.selected_reference_path || referenceState?.selected_reference);

  async function handleExtractAudio() {
    if (!selectedProject) {
      return;
    }
    setIsAudioBusy(true);
    try {
      await extractReferenceAudio(selectedProject.project_id);
      const [project, state] = await Promise.all([
        getProject(selectedProject.project_id),
        fetchReferenceState(selectedProject.project_id)
      ]);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setReferenceState(state);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "오디오 추출에 실패했습니다.");
    } finally {
      setIsAudioBusy(false);
    }
  }

  async function handleRunStt() {
    if (!selectedProject) {
      return;
    }
    setIsSttBusy(true);
    try {
      await runReferenceStt(selectedProject.project_id);
      const [project, state] = await Promise.all([
        getProject(selectedProject.project_id),
        fetchReferenceState(selectedProject.project_id)
      ]);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setReferenceState(state);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "STT 변환에 실패했습니다.");
    } finally {
      setIsSttBusy(false);
    }
  }

  async function handleAnalyzeReference() {
    if (!selectedProject) {
      return;
    }
    setIsAnalysisBusy(true);
    try {
      await runReferenceAnalysis(selectedProject.project_id);
      const [project, state] = await Promise.all([
        getProject(selectedProject.project_id),
        fetchReferenceState(selectedProject.project_id)
      ]);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setReferenceState(state);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "레퍼런스 분석에 실패했습니다.");
    } finally {
      setIsAnalysisBusy(false);
    }
  }

  function handleGenerateCandidates(feedback?: string) {
    if (!selectedProject) {
      return;
    }
    const trimmed = feedback?.trim();
    void runScriptAction(() =>
      trimmed
        ? generateScriptCandidates(selectedProject.project_id, trimmed)
        : generateScriptCandidates(selectedProject.project_id)
    );
  }

  function handleSelectScriptCandidate(candidateId: string) {
    if (!selectedProject) {
      return;
    }
    void runScriptAction(() => selectScriptCandidate(selectedProject.project_id, candidateId));
  }

  function handleFinalizeScript(feedback: string) {
    if (!selectedProject) {
      return;
    }
    void runScriptAction(async () => {
      const result = await finalizeScript(selectedProject.project_id, feedback);
      const prod = await fetchProductionState(selectedProject.project_id);
      setProductionState(prod);
      return result;
    });
  }

  async function handleGenerateProduction() {
    if (!selectedProject) {
      return;
    }
    setIsProductionBusy(true);
    try {
      const updated = await generateTtsAudio(selectedProject.project_id);
      setProductionState(updated);
      const project = await getProject(selectedProject.project_id);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "음성 생성 및 씬 분할에 실패했습니다.");
      throw reason;
    } finally {
      setIsProductionBusy(false);
    }
  }

  async function handleGenerateConcepts() {
    if (!selectedProject) {
      return;
    }
    setIsProductionBusy(true);
    try {
      const updated = await generateConcepts(selectedProject.project_id);
      setProductionState(updated);
      const project = await getProject(selectedProject.project_id);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "비디오 씬 및 연속성 설계에 실패했습니다.");
    } finally {
      setIsProductionBusy(false);
    }
  }

  async function handleGenerateSceneImage(sceneId: number, model?: string) {
    if (!selectedProject) {
      return;
    }
    // 전역 isProductionBusy를 켜지 않아 다른 씬들의 시작 이미지 생성을 동시 클릭 가능하도록 지원
    try {
      const updated = await generateSceneImage(selectedProject.project_id, sceneId, model);
      setProductionState((prev) => {
        if (!prev || !prev.video_scenes || !updated.video_scenes) return updated;
        const prevScenes = prev.video_scenes;
        const mergedScenes: readonly VideoSceneItem[] = updated.video_scenes.map((uScene) => {
          const pScene = prevScenes.find((p) => p.scene_id === uScene.scene_id);
          return {
            ...uScene,
            start_image_url: uScene.start_image_url ?? pScene?.start_image_url ?? null,
            generated_video_url: uScene.generated_video_url ?? pScene?.generated_video_url ?? null,
            final_frame_url: uScene.final_frame_url ?? pScene?.final_frame_url ?? null,
          };
        });
        return {
          ...updated,
          video_scenes: mergedScenes,
        };
      });
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Scene ${sceneId} 이미지 생성 실패`);
    }
  }

  async function handleGenerateAllSceneImages(model: string = "nano_banana_pro") {
    if (!selectedProject) {
      return;
    }
    setIsProductionBusy(true);
    try {
      const updated = await generateAllSceneImages(selectedProject.project_id, model);
      setProductionState(updated);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "전체 씬 이미지 생성 실패");
    } finally {
      setIsProductionBusy(false);
    }
  }

  async function handleGenerateSceneVideo(
    sceneId: number,
    model: string = "kling_o3_flf",
    duration: number = 5,
    multiShots: boolean = false,
    matchPrevFrame: boolean = true
  ) {
    if (!selectedProject) {
      return;
    }
    // 전역 isProductionBusy를 켜지 않아 앞씬 매칭 OFF 등 다른 씬의 비디오를 동시 생성 가능하도록 지원
    try {
      const updated = await generateSceneVideo(selectedProject.project_id, sceneId, model, duration, multiShots, matchPrevFrame);
      setProductionState((prev) => {
        if (!prev || !prev.video_scenes || !updated.video_scenes) return updated;
        const prevScenes = prev.video_scenes;
        const mergedScenes: readonly VideoSceneItem[] = updated.video_scenes.map((uScene) => {
          const pScene = prevScenes.find((p) => p.scene_id === uScene.scene_id);
          return {
            ...uScene,
            start_image_url: uScene.start_image_url ?? pScene?.start_image_url ?? null,
            generated_video_url: uScene.generated_video_url ?? pScene?.generated_video_url ?? null,
            final_frame_url: uScene.final_frame_url ?? pScene?.final_frame_url ?? null,
          };
        });
        return {
          ...updated,
          video_scenes: mergedScenes,
        };
      });
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Scene ${sceneId} 비디오 생성 실패`);
    }
  }

  async function handlePassContinuity(sceneId: number) {
    if (!selectedProject) {
      return;
    }
    setIsProductionBusy(true);
    try {
      const updated = await passContinuityToNext(selectedProject.project_id, sceneId);
      setProductionState(updated);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Scene ${sceneId} 연속성 인계 실패`);
    } finally {
      setIsProductionBusy(false);
    }
  }

  async function handleRegenerateSceneWithFeedback(
    sceneId: number,
    feedback: string,
    target: "image" | "video" | "both" | "prompt_only",
    model?: string,
    duration: number = 5,
    multiShots: boolean = false,
    matchPrevFrame: boolean = true
  ) {
    if (!selectedProject) {
      return;
    }
    setIsProductionBusy(true);
    try {
      const updated = await regenerateSceneWithFeedback(
        selectedProject.project_id,
        sceneId,
        feedback,
        target,
        model,
        duration,
        multiShots,
        matchPrevFrame
      );
      setProductionState(updated);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Scene ${sceneId} 피드백 재생성 실패`);
    } finally {
      setIsProductionBusy(false);
    }
  }

  async function handleUpdateScenePrompts(
    sceneId: number,
    startImagePrompt?: string,
    videoPrompt?: string
  ) {
    if (!selectedProject) {
      return;
    }
    try {
      const updated = await updateScenePrompts(
        selectedProject.project_id,
        sceneId,
        startImagePrompt,
        videoPrompt
      );
      setProductionState(updated);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Scene ${sceneId} 프롬프트 수정 실패`);
    }
  }

  async function handleRenderShorts(title?: string) {
    if (!selectedProject) {
      return;
    }
    setIsProductionBusy(true);
    try {
      const updated = await renderShorts(selectedProject.project_id, title);
      setProductionState(updated);
      const project = await getProject(selectedProject.project_id);
      setSelectedProject(project);
      setProjects((current) =>
        current.map((item) => (item.project_id === project.project_id ? project : item))
      );
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "최종 쇼츠 비디오 렌더링에 실패했습니다.");
    } finally {
      setIsProductionBusy(false);
    }
  }

  async function handleTitleChange(newTitle: string) {
    setVideoTitle(newTitle);
    if (!selectedProject) {
      return;
    }
    try {
      const updated = await updateProject(selectedProject.project_id, {
        project_title: newTitle
      });
      setSelectedProject(updated);
      setProjects((current) =>
        current.map((item) => (item.project_id === updated.project_id ? updated : item))
      );
    } catch {
      // 타이핑 도중 실시간 저장은 실패하더라도 조용히 무시 (화면 입력 보존)
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="Project dashboard">
        <div className="brand-block">
          <span className="brand-mark" aria-hidden="true" />
          <span>
            <strong>Shorts Auto</strong>
            <small>Phase 1</small>
          </span>
        </div>

        <ProjectDashboard
          onCreateProject={handleCreateProject}
          onSelectProject={setSelectedProject}
          projects={projects}
          selectedProjectId={selectedProject?.project_id ?? null}
        />
      </aside>

      <section className="content">
        {isLoading ? <p className="status-banner">프로젝트와 설정을 불러오는 중입니다.</p> : null}
        {error ? <p className="status-banner status-banner--warning">API 연결 전: {error}</p> : null}

        {selectedProject ? (
          <article className="dashboard">
            <header className="project-hero">
              <div>
                <p className="eyebrow">Current project</p>
                <h1>{selectedProject.display_name}</h1>
                <p className="muted">{selectedProject.project_title}</p>
              </div>
              <div className="hero-side">
                <button className="secondary-button" onClick={handleEditTitle} type="button">
                  Edit title
                </button>
                <dl className="hero-meta" aria-label="Project metadata">
                  <div>
                    <dt>Project ID</dt>
                    <dd>{selectedProject.project_id}</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatDate(selectedProject.updated_at)}</dd>
                  </div>
                </dl>
              </div>
            </header>

            <div className="dashboard-grid">
              <ReferenceSearchPanel
                candidates={referenceState?.candidates ?? []}
                isBusy={isReferenceBusy}
                onAddDirect={handleAddDirectReference}
                onSearch={handleReferenceSearch}
                onSelect={handleSelectReference}
                selectedReference={referenceState?.selected_reference ?? null}
              />
              <ProjectWorkflow
                currentStep={selectedProject.current_step}
                hasAnalysis={Boolean(referenceState?.analysis || selectedProject?.generated_files?.reference_analysis)}
                hasAudio={hasAudio}
                hasSelectedReference={hasSelectedReference}
                isAnalysisBusy={isAnalysisBusy}
                isAudioBusy={isAudioBusy}
                isSttBusy={isSttBusy}
                stepStatuses={selectedProject.step_statuses}
              />
              <ReferenceTranscriptPanel
                hasAudio={hasAudio}
                hasSelectedReference={hasSelectedReference}
                isAudioBusy={isAudioBusy}
                isSttBusy={isSttBusy}
                onExtractAudio={handleExtractAudio}
                onRunStt={handleRunStt}
                referenceScript={referenceState?.reference_script ?? null}
              />
              <ReferenceAnalysisPanel
                analysisMarkdown={referenceState?.analysis_markdown ?? null}
                isBusy={isAnalysisBusy}
                onAnalyze={handleAnalyzeReference}
              />
              <CandidateDraftsPanel
                candidates={scriptsState?.candidates ?? []}
                isBusy={isScriptBusy}
                onGenerate={handleGenerateCandidates}
                onSelect={handleSelectScriptCandidate}
                selectedCandidateId={scriptsState?.selected_candidate?.candidate_id ?? null}
                videoTitle={videoTitle}
                onTitleChange={handleTitleChange}
              />
              <FinalScriptPanel
                finalScript={scriptsState?.final_script ?? null}
                isBusy={isScriptBusy}
                onFinalize={handleFinalizeScript}
                selectedCandidate={scriptsState?.selected_candidate ?? null}
                ttsValidation={scriptsState?.tts_validation ?? null}
              />
              <ProductionPanel
                hasFinalScript={Boolean(scriptsState?.final_script || selectedProject.generated_files?.final_script)}
                isBusy={isProductionBusy}
                onGenerateAllSceneImages={handleGenerateAllSceneImages}
                onGenerateConcepts={handleGenerateConcepts}
                onGenerateProduction={handleGenerateProduction}
                onGenerateSceneImage={handleGenerateSceneImage}
                onGenerateSceneVideo={handleGenerateSceneVideo}
                onPassContinuity={handlePassContinuity}
                onRegenerateWithFeedback={handleRegenerateSceneWithFeedback}
                onUpdateScenePrompts={handleUpdateScenePrompts}
                onRenderShorts={handleRenderShorts}
                productionState={productionState}
                projectId={selectedProject.project_id}
                projectTitle={selectedProject.project_title}
                videoTitle={videoTitle}
                onTitleChange={handleTitleChange}
              />
              <SettingsPanel settings={settings} />

              <section className="panel" aria-labelledby="jobs-title">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Jobs</p>
                    <h2 id="jobs-title">Recent work</h2>
                  </div>
                  <span className="count-pill">{selectedProject.job_history.length}</span>
                </div>
                {selectedProject.job_history.length > 0 ? (
                  <ul className="job-list">
                    {selectedProject.job_history.map((job) => (
                      <li key={job.job_id}>
                        <span>
                          <strong>{job.label}</strong>
                          <small>{job.job_type}</small>
                        </span>
                        <span className={`state-pill state-pill--${job.state}`}>{job.state}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="empty-state">아직 실행된 작업이 없습니다.</p>
                )}
              </section>

              <section className="panel" aria-labelledby="files-title">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Outputs</p>
                    <h2 id="files-title">Generated files</h2>
                  </div>
                  <span className="count-pill">{generatedFiles.length}</span>
                </div>
                {generatedFiles.length > 0 ? (
                  <dl className="file-list">
                    {generatedFiles.map(([label, path]) => (
                      <div key={label}>
                        <dt>{label}</dt>
                        <dd>{path}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="empty-state">생성된 파일이 없습니다.</p>
                )}
              </section>
            </div>
          </article>
        ) : (
          <section className="panel empty-workspace" aria-label="Empty workspace">
            <p className="eyebrow">Workspace</p>
            <h1>Create a project to begin.</h1>
          </section>
        )}
      </section>
    </main>
  );
}
