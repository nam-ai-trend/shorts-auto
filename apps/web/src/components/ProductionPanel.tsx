import { useEffect, useState } from "react";
import type { ProductionState } from "../types";
import {
  IMAGE_MODELS,
  VIDEO_MODELS,
  ModelSelectorModal,
  type ModelOption
} from "./ModelSelectorModal";

interface ProductionPanelProps {
  readonly projectId: string;
  readonly productionState: ProductionState | null;
  readonly isBusy: boolean;
  readonly hasFinalScript: boolean;
  readonly onGenerateProduction: () => void;
  readonly onGenerateConcepts?: () => void;
  readonly onGenerateSceneImage?: (sceneId: number, model?: string) => void;
  readonly onGenerateAllSceneImages?: (model?: string) => void;
  readonly onGenerateSceneVideo?: (sceneId: number, model?: string, duration?: number, multiShots?: boolean, matchPrevFrame?: boolean) => void;
  readonly onPassContinuity?: (sceneId: number) => void;
  readonly onRegenerateWithFeedback?: (
    sceneId: number,
    feedback: string,
    target: "image" | "video" | "both" | "prompt_only",
    model?: string,
    duration?: number,
    multiShots?: boolean,
    matchPrevFrame?: boolean
  ) => void;
  readonly onUpdateScenePrompts?: (
    sceneId: number,
    startImagePrompt?: string,
    videoPrompt?: string
  ) => Promise<void>;
  readonly onRenderShorts?: (title?: string) => void;
  readonly projectTitle?: string;
  readonly videoTitle?: string;
  readonly onTitleChange?: (title: string) => void;
}

export function ProductionPanel({
  projectId,
  productionState,
  isBusy,
  hasFinalScript,
  onGenerateProduction,
  onGenerateConcepts,
  onGenerateSceneImage,
  onGenerateAllSceneImages,
  onGenerateSceneVideo,
  onPassContinuity,
  onRegenerateWithFeedback,
  onUpdateScenePrompts,
  onRenderShorts,
  projectTitle,
  videoTitle: propVideoTitle,
  onTitleChange
}: ProductionPanelProps) {
  const [expandedPromptId, setExpandedPromptId] = useState<number | null>(null);
  const [imageModel, setImageModel] = useState<string>("nano_banana_pro");
  const [videoModel, setVideoModel] = useState<string>("kling_o3_flf");
  const [modalMode, setModalMode] = useState<"image" | "video" | null>(null);
  const [multiShotsMap, setMultiShotsMap] = useState<Record<number, boolean>>({});
  const [matchPrevMap, setMatchPrevMap] = useState<Record<number, boolean>>({});
  const [imageFeedbackMap, setImageFeedbackMap] = useState<Record<number, string>>({});
  const [videoFeedbackMap, setVideoFeedbackMap] = useState<Record<number, string>>({});
  const [feedbackLoadingMap, setFeedbackLoadingMap] = useState<Record<string, string | null>>({});
  const [busySceneId, setBusySceneId] = useState<number | null>(null);
  const [busyAction, setBusyAction] = useState<"image" | "video" | "all_images" | "all_videos" | "render" | "tts" | null>(null);
  const [busyImageScenes, setBusyImageScenes] = useState<Record<number, boolean>>({});
  const [busyVideoScenes, setBusyVideoScenes] = useState<Record<number, boolean>>({});
  const [batchProgressText, setBatchProgressText] = useState<string | null>(null);
  const [cacheBuster, setCacheBuster] = useState<number>(Date.now());
  const [editingPromptSceneId, setEditingPromptSceneId] = useState<number | null>(null);
  const [editImagePrompt, setEditImagePrompt] = useState<string>("");
  const [editVideoPrompt, setEditVideoPrompt] = useState<string>("");
  const [isSavingPrompts, setIsSavingPrompts] = useState<boolean>(false);
  const [videoTitle, setVideoTitle] = useState<string>(() => propVideoTitle ?? projectTitle ?? "");
  const [ttsError, setTtsError] = useState<string | null>(null);

  useEffect(() => {
    if (propVideoTitle !== undefined) {
      setVideoTitle(propVideoTitle);
    } else if (projectTitle && !videoTitle) {
      setVideoTitle(projectTitle);
    }
  }, [propVideoTitle, projectTitle]);

  const handleTitleInputChange = (newTitle: string) => {
    setVideoTitle(newTitle);
    onTitleChange?.(newTitle);
  };

  const startEditingPrompts = (sceneId: number, currentImagePrompt: string, currentVideoPrompt: string) => {
    setEditingPromptSceneId(sceneId);
    setEditImagePrompt(currentImagePrompt);
    setEditVideoPrompt(currentVideoPrompt);
  };

  const cancelEditingPrompts = () => {
    setEditingPromptSceneId(null);
    setEditImagePrompt("");
    setEditVideoPrompt("");
  };

  const handleSavePrompts = async (sceneId: number) => {
    if (!onUpdateScenePrompts) return;
    setIsSavingPrompts(true);
    try {
      await onUpdateScenePrompts(sceneId, editImagePrompt, editVideoPrompt);
      setEditingPromptSceneId(null);
    } finally {
      setIsSavingPrompts(false);
    }
  };

  useEffect(() => {
    setCacheBuster(Date.now());
    setRenderKey(Date.now());
  }, [productionState]);

  const handleProductionTtsClick = async () => {
    if (!onGenerateProduction) return;
    setTtsError(null);
    setBusyAction("tts");
    try {
      await onGenerateProduction();
    } catch (err) {
      setTtsError(err instanceof Error ? err.message : "음성 생성에 실패했습니다. 로컬 TTS 서버가 켜져 있는지 확인해주세요.");
    } finally {
      setBusyAction(null);
    }
  };

  const handleSceneImageClick = async (sceneId: number) => {
    if (!onGenerateSceneImage) return;
    setBusyImageScenes((prev) => ({ ...prev, [sceneId]: true }));
    try {
      await onGenerateSceneImage(sceneId, imageModel);
    } finally {
      setBusyImageScenes((prev) => {
        const next = { ...prev };
        delete next[sceneId];
        return next;
      });
    }
  };

  const handleSceneVideoClick = async (sceneId: number, duration: number, isMultiShot: boolean, isMatched: boolean) => {
    if (!onGenerateSceneVideo) return;
    setBusyVideoScenes((prev) => ({ ...prev, [sceneId]: true }));
    try {
      await onGenerateSceneVideo(sceneId, videoModel, duration, isMultiShot, isMatched);
    } finally {
      setBusyVideoScenes((prev) => {
        const next = { ...prev };
        delete next[sceneId];
        return next;
      });
    }
  };

  const handleAllImagesClick = async () => {
    if (!onGenerateAllSceneImages) return;
    setBusyAction("all_images");
    try {
      await onGenerateAllSceneImages(imageModel);
    } finally {
      setBusyAction(null);
    }
  };

  const handleFeedbackRegenerate = async (
    sceneId: number,
    target: "image" | "video" | "prompt_image" | "prompt_video",
    duration: number,
    isMultiShot: boolean,
    isMatched: boolean
  ) => {
    const isImage = target === "image" || target === "prompt_image";
    const feedbackText = isImage ? imageFeedbackMap[sceneId]?.trim() : videoFeedbackMap[sceneId]?.trim();
    if (!feedbackText) {
      alert(isImage ? "수정하고 싶은 이미지 피드백 내용을 입력해주세요!" : "수정하고 싶은 영상(모션) 피드백 내용을 입력해주세요!");
      return;
    }
    if (!onRegenerateWithFeedback) return;

    const loadingKey = `${sceneId}_${isImage ? "image" : "video"}`;
    const actionLabel =
      target === "image"
        ? "AI 이미지 프롬프트 수정 및 재생성 중..."
        : target === "video"
        ? "AI 비디오 모션 프롬프트 수정 및 렌더링 중..."
        : "프롬프트 AI 수정 중...";

    setFeedbackLoadingMap((prev) => ({ ...prev, [loadingKey]: actionLabel }));
    setBusySceneId(sceneId);
    setBusyAction(isImage ? "image" : "video");

    try {
      const selectedModel = isImage ? imageModel : videoModel;
      await onRegenerateWithFeedback(
        sceneId,
        feedbackText,
        target as "image" | "video" | "both" | "prompt_only",
        selectedModel,
        duration,
        isMultiShot,
        isMatched
      );
    } finally {
      setFeedbackLoadingMap((prev) => ({ ...prev, [loadingKey]: null }));
      setBusySceneId(null);
      setBusyAction(null);
    }
  };

  const [renderError, setRenderError] = useState<string | null>(null);
  const [renderKey, setRenderKey] = useState<number>(() => Date.now());

  const handleAllVideosAndRender = async () => {
    if (!onGenerateSceneVideo || videoScenes.length === 0) return;
    setBusyAction("all_videos");
    setRenderError(null);
    try {
      for (let i = 0; i < videoScenes.length; i++) {
        const sc = videoScenes[i];
        const scId = sc.scene_id;
        const isMatched = matchPrevMap[scId] ?? (scId > 1);
        const isMulti = multiShotsMap[scId] ?? false;
        const dur = Math.max(4, Math.round(sc.target_duration));

        setBatchProgressText(`[${i + 1}/${videoScenes.length}] Scene ${scId} AI 비디오 생성 중... (${currentVideoModel.name})`);
        setBusySceneId(scId);

        await onGenerateSceneVideo(scId, videoModel, dur, isMulti, isMatched);
      }

      setBusySceneId(null);
      if (onRenderShorts) {
        setBatchProgressText("🎬 모든 씬 비디오 생성 완료! Remotion 9:16 최종 쇼츠 렌더링 중...");
        await onRenderShorts(videoTitle);
        setRenderKey(Date.now());
      }
    } catch (err) {
      setRenderError(err instanceof Error ? err.message : "비디오 일괄 생성 및 렌더링 중 오류가 발생했습니다.");
    } finally {
      setBusySceneId(null);
      setBusyAction(null);
      setBatchProgressText(null);
    }
  };

  const handleRenderClick = async () => {
    if (!onRenderShorts) return;
    setBusyAction("render");
    setRenderError(null);
    try {
      await onRenderShorts(videoTitle);
      setRenderKey(Date.now());
    } catch (err) {
      setRenderError(err instanceof Error ? err.message : "렌더링 중 오류가 발생했습니다.");
    } finally {
      setBusyAction(null);
    }
  };

  const currentImageModel: ModelOption =
    IMAGE_MODELS.find((m) => m.id === imageModel) ?? IMAGE_MODELS[0];
  const currentVideoModel: ModelOption =
    VIDEO_MODELS.find((m) => m.id === videoModel) ?? VIDEO_MODELS[0];

  const hasAudio = Boolean(productionState?.has_audio);
  const audioUrl = hasAudio ? `/api/projects/${encodeURIComponent(projectId)}/production/audio` : null;
  const duration = productionState?.duration_seconds;
  const conceptKit = productionState?.concept_kit;
  const videoScenes = productionState?.video_scenes ?? [];
  const hasFinalVideo = Boolean(productionState?.has_final_video);
  const finalVideoUrl = productionState?.final_video_url ?? (hasFinalVideo ? `/api/projects/${encodeURIComponent(projectId)}/production/final-video` : null);

  // 전체 멀티샷 일괄 켜기 / 끄기 토글
  const allMultiShotsOn = videoScenes.length > 0 && videoScenes.every((s) => multiShotsMap[s.scene_id]);
  const toggleAllMultiShots = () => {
    const nextVal = !allMultiShotsOn;
    const nextMap: Record<number, boolean> = {};
    videoScenes.forEach((s) => {
      nextMap[s.scene_id] = nextVal;
    });
    setMultiShotsMap(nextMap);
  };

  // 전체 앞 씬 매칭 일괄 켜기 / 끄기 토글 (Scene 2 이상)
  const allMatchPrevOn = videoScenes.filter((s) => s.scene_id > 1).every((s) => matchPrevMap[s.scene_id] !== false);
  const toggleAllMatchPrev = () => {
    const nextVal = !allMatchPrevOn;
    const nextMap: Record<number, boolean> = {};
    videoScenes.filter((s) => s.scene_id > 1).forEach((s) => {
      nextMap[s.scene_id] = nextVal;
    });
    setMatchPrevMap(nextMap);
  };

  return (
    <section className="panel production-panel" aria-labelledby="production-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Production & Visual Continuity</p>
          <h2 id="production-title">TTS Voice & Video Scene Continuity</h2>
        </div>
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
          {/* 7번 단계 상태 뱃지 (진행 중 ⏳ / 완료 ✓) */}
          {busyAction === "tts" ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(56, 189, 248, 0.2)",
                color: "#38bdf8",
                border: "1.5px solid #38bdf8",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold"
              }}
            >
              <span className="spinner-icon">⏳</span> 7단계 1.2배속 음성 생성 & 씬 분할 진행 중...
            </span>
          ) : busyAction === "video" && busySceneId ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(168, 85, 247, 0.2)",
                color: "#c084fc",
                border: "1.5px solid #c084fc",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold"
              }}
            >
              <span className="spinner-icon">⏳</span> Scene {busySceneId} 비디오 생성 진행 중 ({currentVideoModel.name})...
            </span>
          ) : busyAction === "image" && busySceneId ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(56, 189, 248, 0.2)",
                color: "#38bdf8",
                border: "1.5px solid #38bdf8",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold"
              }}
            >
              <span className="spinner-icon">⏳</span> Scene {busySceneId} 이미지 생성 진행 중 ({currentImageModel.name})...
            </span>
          ) : busyAction === "all_videos" ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(168, 85, 247, 0.2)",
                color: "#c084fc",
                border: "1.5px solid #c084fc",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold"
              }}
            >
              <span className="spinner-icon">⏳</span> {batchProgressText || "전체 비디오 일괄 생성 진행 중..."}
            </span>
          ) : busyAction === "all_images" ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(56, 189, 248, 0.2)",
                color: "#38bdf8",
                border: "1.5px solid #38bdf8",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold"
              }}
            >
              <span className="spinner-icon">⏳</span> 전체 씬 AI 이미지 일괄 생성 진행 중...
            </span>
          ) : isBusy ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(56, 189, 248, 0.2)",
                color: "#38bdf8",
                border: "1.5px solid #38bdf8",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold"
              }}
            >
              <span className="spinner-icon">⏳</span> 7단계 음성 생성 및 씬 분할 진행 중...
            </span>
          ) : hasAudio ? (
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(34, 197, 94, 0.18)",
                color: "#4ade80",
                border: "1.5px solid #4ade80",
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold"
              }}
            >
              ✓ 7단계 음성 생성 & 씬 분할 완료 ({videoScenes.length > 0 ? `총 ${videoScenes.length}개 씬` : "완료"})
            </span>
          ) : null}

          <button
            className={hasAudio ? "secondary-button" : "primary-button"}
            disabled={isBusy || busyAction === "tts" || !hasFinalScript}
            onClick={handleProductionTtsClick}
            type="button"
            aria-label="Generate TTS voice"
            style={{
              padding: "6px 14px",
              fontSize: "13px",
              fontWeight: "bold",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            {busyAction === "tts" || isBusy ? (
              <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                <span className="spinner-icon">⏳</span> 7. 1.2배속 음성 생성 진행 중...
              </span>
            ) : hasAudio ? (
              "🔄 7. 음성 다시 생성"
            ) : (
              "7. 🎙️ 1.2배속 음성 생성 & 씬 분할"
            )}
          </button>

          {onGenerateAllSceneImages && videoScenes.length > 0 && (
            <button
              className="primary-button"
              disabled={isBusy || Object.keys(busyImageScenes).length > 0}
              onClick={handleAllImagesClick}
              type="button"
              aria-label="Generate all scene images"
            >
              {busyAction === "all_images" ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span className="spinner-icon">⏳</span> 전체 씬 AI 이미지 일괄 생성 중...
                </span>
              ) : Object.keys(busyImageScenes).length > 0 ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span className="spinner-icon">⏳</span> 개별 씬 이미지 생성 중 ({Object.keys(busyImageScenes).length}개)...
                </span>
              ) : isBusy ? (
                "처리 중..."
              ) : (
                `🖼️ 전체 씬 AI 이미지 일괄 생성 (${currentImageModel.name})`
              )}
            </button>
          )}

          {onGenerateSceneVideo && videoScenes.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "100%" }}>
              <button
                className="primary-button"
                disabled={isBusy || Object.keys(busyVideoScenes).length > 0 || Object.keys(busyImageScenes).length > 0}
                onClick={handleAllVideosAndRender}
                type="button"
                aria-label="Generate all scene videos and render final shorts"
                style={{
                  background: "linear-gradient(90deg, #7c3aed 0%, #db2777 100%)",
                  border: "none",
                  boxShadow: "0 4px 14px rgba(124, 58, 237, 0.4)",
                  fontWeight: "bold",
                  color: "#ffffff"
                }}
                title="각 씬의 [앞 씬 매칭] 및 [멀티샷] 체크 설정을 바탕으로 비디오를 일괄 생성한 뒤 Remotion 최종 쇼츠로 자동 합성합니다"
              >
                {busyAction === "all_videos" ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                    <span className="spinner-icon">⏳</span> {batchProgressText || "비디오 일괄 생성 및 렌더링 중..."}
                  </span>
                ) : Object.keys(busyVideoScenes).length > 0 ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                    <span className="spinner-icon">⏳</span> 개별 씬 영상 생성 중 ({Object.keys(busyVideoScenes).length}개)...
                  </span>
                ) : isBusy ? (
                  "처리 중..."
                ) : (
                  `🎬 전체 씬 AI 영상 일괄 생성 & 렌더링 (${currentVideoModel.name})`
                )}
              </button>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "6px 12px",
                  background: "rgba(124, 58, 237, 0.12)",
                  border: "1px dashed rgba(168, 85, 247, 0.45)",
                  borderRadius: "8px",
                  fontSize: "12px",
                  color: "#e2e8f0"
                }}
              >
                <span style={{ color: "#c084fc", fontWeight: "bold" }}>🏷️ 자동 렌더링될 오프닝 타이틀:</span>
                {videoTitle.trim() ? (
                  <span style={{ color: "#38bdf8", fontWeight: "bold", whiteSpace: "pre-line" }}>
                    "{videoTitle.replace(/\n/g, " / ")}"
                  </span>
                ) : (
                  <span style={{ color: "#94a3b8", fontStyle: "italic" }}>
                    (대본 초안 피드백 밑에서 입력한 제목이 여기에 자동 반영됩니다 / 비워둘 경우 제목 생략)
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 🚀 씬별 비디오 설정 퀵 컨트롤 매트릭스 (씬 개수에 따라 동적 렌더링) */}
      {videoScenes.length > 0 && (
        <div
          style={{
            background: "linear-gradient(180deg, rgba(30, 41, 59, 0.75) 0%, rgba(15, 23, 42, 0.85) 100%)",
            border: "1.5px solid rgba(56, 189, 248, 0.3)",
            borderRadius: "12px",
            padding: "1rem 1.25rem",
            margin: "0.4rem 0 1.2rem 0",
            display: "flex",
            flexDirection: "column",
            gap: "0.85rem",
            boxShadow: "0 4px 20px rgba(0, 0, 0, 0.25)"
          }}
        >
          {/* 헤더 & 일괄 전체 토글 버튼 */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.8rem", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", paddingBottom: "0.75rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "20px" }}>🎛️</span>
              <div>
                <strong style={{ color: "#38bdf8", fontSize: "14px" }}>
                  씬별 비디오 생성 퀵 설정 바 (총 {videoScenes.length}개 씬)
                </strong>
                <p style={{ margin: "2px 0 0 0", color: "#94a3b8", fontSize: "12px" }}>
                  각 씬마다 [앞 씬 매칭]과 [멀티샷]을 여기서 한 번에 설정할 수 있습니다. (아래 씬 카드와 실시간 양방향 동기화)
                </p>
              </div>
            </div>

            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
              <button
                type="button"
                onClick={toggleAllMatchPrev}
                disabled={isBusy}
                style={{
                  fontSize: "12px",
                  padding: "5px 11px",
                  borderRadius: "6px",
                  cursor: isBusy ? "not-allowed" : "pointer",
                  background: allMatchPrevOn ? "rgba(56, 189, 248, 0.25)" : "rgba(255, 255, 255, 0.05)",
                  border: allMatchPrevOn ? "1.5px solid #38bdf8" : "1px solid rgba(255, 255, 255, 0.2)",
                  color: allMatchPrevOn ? "#38bdf8" : "#94a3b8",
                  fontWeight: "bold",
                  transition: "all 0.15s ease"
                }}
                title="Scene 2 이상 모든 씬의 앞 씬 매칭을 한 번에 켜거나 끕니다"
              >
                ⚡ 전체 매칭: {allMatchPrevOn ? "전체 ON (2장 연결)" : "전체/일부 OFF"}
              </button>

              <button
                type="button"
                onClick={toggleAllMultiShots}
                disabled={isBusy}
                style={{
                  fontSize: "12px",
                  padding: "5px 11px",
                  borderRadius: "6px",
                  cursor: isBusy ? "not-allowed" : "pointer",
                  background: allMultiShotsOn ? "rgba(244, 63, 94, 0.25)" : "rgba(255, 255, 255, 0.05)",
                  border: allMultiShotsOn ? "1.5px solid #f43f5e" : "1px solid rgba(255, 255, 255, 0.2)",
                  color: allMultiShotsOn ? "#fb7185" : "#94a3b8",
                  fontWeight: "bold",
                  transition: "all 0.15s ease"
                }}
                title="모든 씬의 멀티샷을 한 번에 켜거나 끕니다"
              >
                ⚡ 전체 멀티샷: {allMultiShotsOn ? "전체 ON" : "전체 OFF"}
              </button>
            </div>
          </div>

          {/* 씬 개수(N개)에 맞게 가로 그리드로 척척 렌더링되는 씬별 칩 목록! */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: "0.6rem"
            }}
          >
            {videoScenes.map((sc) => {
              const scId = sc.scene_id;
              const isMatched = scId > 1 ? (matchPrevMap[scId] !== false) : false;
              const isMulti = multiShotsMap[scId] ?? false;

              return (
                <div
                  key={scId}
                  style={{
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid rgba(255, 255, 255, 0.09)",
                    borderRadius: "8px",
                    padding: "0.5rem 0.75rem",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "0.5rem"
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span
                      style={{
                        background: "#2563eb",
                        color: "#fff",
                        padding: "2px 7px",
                        borderRadius: "4px",
                        fontSize: "11px",
                        fontWeight: "bold"
                      }}
                    >
                      S{scId}
                    </span>
                    <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                      ({sc.target_duration.toFixed(1)}s)
                    </span>
                  </div>

                  <div style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
                    {scId > 1 && (
                      <button
                        type="button"
                        onClick={() => setMatchPrevMap((prev) => ({ ...prev, [scId]: !isMatched }))}
                        disabled={isBusy}
                        style={{
                          fontSize: "11px",
                          padding: "3px 7px",
                          borderRadius: "5px",
                          cursor: isBusy ? "not-allowed" : "pointer",
                          background: isMatched ? "rgba(56, 189, 248, 0.2)" : "rgba(255, 255, 255, 0.05)",
                          border: isMatched ? "1.5px solid #38bdf8" : "1px dashed rgba(255, 255, 255, 0.25)",
                          color: isMatched ? "#38bdf8" : "#94a3b8",
                          fontWeight: isMatched ? "bold" : "normal",
                          transition: "all 0.15s ease"
                        }}
                        title={`Scene ${scId} 앞 씬 매칭 (클릭하여 토글)`}
                      >
                        {isMatched ? "🔗 앞씬매칭 ON" : "🔗 앞씬매칭 OFF"}
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => setMultiShotsMap((prev) => ({ ...prev, [scId]: !isMulti }))}
                      disabled={isBusy}
                      style={{
                        fontSize: "11px",
                        padding: "3px 7px",
                        borderRadius: "5px",
                        cursor: isBusy ? "not-allowed" : "pointer",
                        background: isMulti ? "rgba(244, 63, 94, 0.2)" : "rgba(255, 255, 255, 0.05)",
                        border: isMulti ? "1.5px solid #f43f5e" : "1px dashed rgba(255, 255, 255, 0.25)",
                        color: isMulti ? "#fb7185" : "#94a3b8",
                        fontWeight: isMulti ? "bold" : "normal",
                        transition: "all 0.15s ease"
                      }}
                      title={`Scene ${scId} 멀티샷 (클릭하여 토글)`}
                    >
                      {isMulti ? "🎥 멀티샷 ON" : "🎥 멀티샷 OFF"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 일괄 생성 진행 중 실시간 진행 상황 배너 */}
      {busyAction === "all_videos" && batchProgressText && (
        <div
          style={{
            background: "linear-gradient(135deg, rgba(124, 58, 237, 0.18) 0%, rgba(219, 39, 119, 0.18) 100%)",
            border: "2px solid #a855f7",
            borderRadius: "12px",
            padding: "1rem 1.5rem",
            margin: "0.5rem 0 1rem 0",
            display: "flex",
            alignItems: "center",
            gap: "14px",
            boxShadow: "0 8px 24px rgba(124, 58, 237, 0.25)",
            animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite"
          }}
        >
          <span style={{ fontSize: "28px" }}>🚀</span>
          <div>
            <strong style={{ fontSize: "1.05rem", color: "#f3e8ff", display: "block" }}>
              {batchProgressText}
            </strong>
            <span style={{ fontSize: "0.83rem", color: "#d8b4fe" }}>
              각 씬별 [앞 씬 매칭]과 [멀티샷] 설정을 바탕으로 비디오를 순차 생성하고, 완료 시 Remotion 자막 & 오디오 합성이 자동 시작됩니다.
            </span>
          </div>
        </div>
      )}

      {!hasFinalScript ? (
        <p className="empty-state">
          최종 대본(Final TTS script)을 먼저 확정한 후 TTS 음성 및 씬을 생성할 수 있습니다.
        </p>
      ) : (
        <div className="production-content" style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
          {/* 🎛️ AI 생성 모델 선택 듀얼 카드 (첨부 이미지 스타일 모달 연동) */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: "0.75rem",
              background: "rgba(255, 255, 255, 0.02)",
              padding: "0.85rem",
              borderRadius: "10px",
              border: "1px solid rgba(255, 255, 255, 0.08)"
            }}
          >
            {/* 이미지 모델 셀렉터 */}
            <div
              onClick={() => setModalMode("image")}
              style={{
                background: "rgba(15, 23, 42, 0.7)",
                border: "1px solid rgba(56, 189, 248, 0.3)",
                borderRadius: "10px",
                padding: "0.85rem 1rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "all 0.15s ease"
              }}
              title="클릭하여 다른 이미지 생성 모델로 변경"
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", minWidth: 0 }}>
                <div style={{ width: "38px", height: "38px", borderRadius: "8px", background: "rgba(56, 189, 248, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "20px", flexShrink: 0 }}>
                  🖼️
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: "11px", color: "#38bdf8", fontWeight: "600", marginBottom: "2px" }}>
                    이미지 모델 선택 (클릭하여 변경)
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <strong style={{ fontSize: "0.95rem", color: "#f8fafc" }}>{currentImageModel.name}</strong>
                    {currentImageModel.badge && (
                      <span style={{ fontSize: "10px", background: "#0284c7", color: "#fff", padding: "1px 5px", borderRadius: "3px", fontWeight: "bold" }}>
                        {currentImageModel.badge}
                      </span>
                    )}
                  </div>
                  <p style={{ margin: 0, color: "#94a3b8", fontSize: "11px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {currentImageModel.description}
                  </p>
                </div>
              </div>
              <div style={{ color: "#38bdf8", fontSize: "18px", fontWeight: "bold", paddingLeft: "0.5rem" }}>›</div>
            </div>

            {/* 비디오 모델 셀렉터 */}
            <div
              onClick={() => setModalMode("video")}
              style={{
                background: "rgba(15, 23, 42, 0.7)",
                border: "1px solid rgba(167, 139, 250, 0.3)",
                borderRadius: "10px",
                padding: "0.85rem 1rem",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                transition: "all 0.15s ease"
              }}
              title="클릭하여 다른 비디오 생성 모델로 변경"
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", minWidth: 0 }}>
                <div style={{ width: "38px", height: "38px", borderRadius: "8px", background: "rgba(167, 139, 250, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "20px", flexShrink: 0 }}>
                  🎬
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: "11px", color: "#a78bfa", fontWeight: "600", marginBottom: "2px" }}>
                    비디오 모델 선택 (클릭하여 변경)
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <strong style={{ fontSize: "0.95rem", color: "#f8fafc" }}>{currentVideoModel.name}</strong>
                    {currentVideoModel.badge && (
                      <span
                        style={{
                          fontSize: "10px",
                          background:
                            currentVideoModel.badgeType === "value"
                              ? "#10b981"
                              : currentVideoModel.badgeType === "recommended"
                              ? "#2563eb"
                              : currentVideoModel.badgeType === "free" || currentVideoModel.badgeType === "new"
                              ? "#eab308"
                              : "#7c3aed",
                          color: currentVideoModel.badgeType === "free" || currentVideoModel.badgeType === "new" ? "#000" : "#fff",
                          padding: "1px 6px",
                          borderRadius: "4px",
                          fontWeight: "bold"
                        }}
                      >
                        {currentVideoModel.badge}
                      </span>
                    )}
                  </div>
                  <p style={{ margin: 0, color: "#94a3b8", fontSize: "11px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {currentVideoModel.description}
                  </p>
                </div>
              </div>
              <div style={{ color: "#a78bfa", fontSize: "18px", fontWeight: "bold", paddingLeft: "0.5rem" }}>›</div>
            </div>
          </div>

          {/* 오디오 플레이어 영역 */}
          <div className="audio-player-box" style={{ background: "rgba(255, 255, 255, 0.04)", padding: "1rem", borderRadius: "8px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
              <strong>🔊 1.2배속 나레이션 오디오 (output_1.2x.wav)</strong>
              {duration ? (
                <span className="state-pill state-pill--succeeded">
                  재생 시간: {duration.toFixed(1)}초
                </span>
              ) : (
                <span className="state-pill state-pill--waiting">미생성</span>
              )}
            </div>
            {audioUrl ? (
              <audio controls src={audioUrl} style={{ width: "100%", marginTop: "0.25rem" }} />
            ) : (
              <p className="muted" style={{ margin: "0.25rem 0" }}>
                [🎙️ 1.2배속 음성 생성] 버튼을 누르면 Qwen3-TTS를 통해 성우 나레이션이 생성됩니다.
              </p>
            )}
          </div>

          {/* 컨셉 키트 요약 카드 */}
          {conceptKit && (
            <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", borderRadius: "8px", padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                <strong style={{ color: "#0284c7" }}>🎨 Visual Concept Kit (클레이메이션 인포그래픽)</strong>
                <span className="count-pill">9:16 Portrait</span>
              </div>
              <p style={{ margin: "0.25rem 0", fontSize: "0.9rem", color: "#1e293b" }}>
                <strong>스타일:</strong> {conceptKit.visual_style}
              </p>
              <p style={{ margin: "0.25rem 0", fontSize: "0.85rem", color: "#475569" }}>
                <strong>조명 & 색감:</strong> {conceptKit.color_and_lighting}
              </p>
              <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                {conceptKit.core_objects.map((obj, i) => (
                  <span key={i} style={{ fontSize: "11px", background: "#e2e8f0", color: "#334155", padding: "2px 8px", borderRadius: "4px", border: "1px solid #cbd5e1" }}>
                    🏺 {obj}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* 6개 비디오 씬 & 연속성 검사기 영역 */}
          <div className="video-scenes-box">
            {/* 🚨 로컬 TTS 연결 실패 / 에러 알림 배너 */}
            {ttsError && (
              <div
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  background: "rgba(239, 68, 68, 0.12)",
                  border: "2px solid #ef4444",
                  borderRadius: "8px",
                  padding: "1rem 1.25rem",
                  marginBottom: "1rem",
                  boxShadow: "0 0 15px rgba(239, 68, 68, 0.2)"
                }}
              >
                <span style={{ fontSize: "28px", lineHeight: 1 }}>🚨</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: "15px", fontWeight: "bold", color: "#dc2626" }}>
                    로컬 TTS 서버 연결 실패!
                  </div>
                  <div style={{ fontSize: "13px", color: "#b91c1c", marginTop: "4px", lineHeight: "1.5" }}>
                    {ttsError}
                  </div>
                  <div style={{ fontSize: "12px", color: "#7f1d1d", marginTop: "8px", background: "rgba(255, 255, 255, 0.8)", padding: "8px 12px", borderRadius: "6px", border: "1px solid #fca5a5" }}>
                    💡 <strong>해결 방법:</strong> 로컬 터미널에서 Qwen3-TTS 서버를 먼저 실행하신 후 다시 [7. 음성 생성] 버튼을 눌러주세요.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setTtsError(null)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#dc2626",
                    fontSize: "18px",
                    cursor: "pointer",
                    fontWeight: "bold",
                    padding: "0 4px"
                  }}
                  aria-label="닫기"
                >
                  ✕
                </button>
              </div>
            )}

            {/* ⏳ 실시간 작업 진행 알림 배너 */}
            {busyAction === "tts" && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  background: "rgba(56, 189, 248, 0.15)",
                  border: "2px solid #0284c7",
                  borderRadius: "8px",
                  padding: "1rem 1.25rem",
                  marginBottom: "1rem",
                  boxShadow: "0 0 15px rgba(2, 132, 199, 0.25)"
                }}
              >
                <span className="spinner-icon" style={{ fontSize: "28px" }}>⏳</span>
                <div>
                  <div style={{ fontSize: "15px", fontWeight: "bold", color: "#0369a1" }}>
                    7단계 1.2배속 음성 생성 & 씬 분할 진행 중... (Qwen3-TTS)
                  </div>
                  <div style={{ fontSize: "12px", color: "#075985", marginTop: "3px" }}>
                    로컬 Qwen3-TTS 서버로 고품질 성우 나레이션을 생성하고, Whisper STT로 문장별 타임스탬프를 자동 분할하고 있습니다 (약 10~25초 소요). 잠시만 기다려주세요!
                  </div>
                </div>
              </div>
            )}

            {busyAction === "video" && busySceneId && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  background: "rgba(168, 85, 247, 0.15)",
                  border: "2px solid #a855f7",
                  borderRadius: "8px",
                  padding: "1rem 1.25rem",
                  marginBottom: "1rem",
                  boxShadow: "0 0 15px rgba(168, 85, 247, 0.3)"
                }}
              >
                <span className="spinner-icon" style={{ fontSize: "28px" }}>⏳</span>
                <div>
                  <div style={{ fontSize: "15px", fontWeight: "bold", color: "#9333ea" }}>
                    Scene {busySceneId} AI 비디오 렌더링 진행 중... ({currentVideoModel.name})
                  </div>
                  <div style={{ fontSize: "12px", color: "#6b21a8", marginTop: "3px" }}>
                    Higgsfield를 통해 고화질 비디오를 생성하고 있습니다 (약 30초~1분 30초 소요). 완료되면 비디오가 자동으로 화면에 표시됩니다!
                  </div>
                </div>
              </div>
            )}

            {busyAction === "image" && busySceneId && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  background: "rgba(56, 189, 248, 0.15)",
                  border: "2px solid #0284c7",
                  borderRadius: "8px",
                  padding: "1rem 1.25rem",
                  marginBottom: "1rem",
                  boxShadow: "0 0 15px rgba(2, 132, 199, 0.25)"
                }}
              >
                <span className="spinner-icon" style={{ fontSize: "28px" }}>⏳</span>
                <div>
                  <div style={{ fontSize: "15px", fontWeight: "bold", color: "#0369a1" }}>
                    Scene {busySceneId} AI 이미지 생성 진행 중... ({currentImageModel.name})
                  </div>
                  <div style={{ fontSize: "12px", color: "#075985", marginTop: "3px" }}>
                    대본에 맞춘 클레이메이션 프롬프트로 이미지를 렌더링하고 있습니다. 잠시만 기다려주세요!
                  </div>
                </div>
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
              <div>
                <strong>🎬 쇼츠 비디오 씬 & 원테이크 연속성 인스펙터 (video_scenes.json)</strong>
                <p className="muted" style={{ margin: "0.2rem 0 0" }}>
                  이전 씬의 마지막 프레임이 다음 씬의 첫 번째 시작 이미지로 자연스럽게 연결되는지 직접 눈으로 검사할 수 있습니다.
                </p>
              </div>
              <span className="count-pill">총 {videoScenes.length}개 비디오 씬</span>
            </div>

            {/* 💡 시작 가이드 안내 배너 */}
            <div
              style={{
                background: "#f0f9ff",
                border: "1.5px solid #38bdf8",
                borderRadius: "8px",
                padding: "0.9rem 1.1rem",
                marginBottom: "1rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.45rem",
                boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span style={{ fontSize: "18px" }}>🚀</span>
                <strong style={{ color: "#0369a1", fontSize: "1rem" }}>이미지 & 비디오 제작 시작 가이드</strong>
              </div>
              <div style={{ fontSize: "0.88rem", color: "#1e293b", lineHeight: "1.6" }}>
                <p style={{ margin: "0 0 0.35rem 0" }}>
                  대본을 바탕으로 <strong>총 {videoScenes.length}개 씬의 이미지 & 비디오 프롬프트가 이미 100% 설계 완료</strong>되어 있습니다.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.25rem", background: "white", padding: "0.6rem 0.8rem", borderRadius: "6px", border: "1px solid #e0f2fe" }}>
                  <div>
                    <strong style={{ color: "#0284c7" }}>• [순차 진행 권장]:</strong> 아래 <strong>Scene 1</strong>의 <strong>[🖼️ 이미지 생성 ({currentImageModel.name})]</strong>을 먼저 눌러 시작 이미지를 뽑으세요. 이미지가 마음에 들면 활성화되는 <strong>[🎬 비디오 생성 ({currentVideoModel.name})]</strong>을 눌러 영상 클립을 완성합니다.
                  </div>
                  <div>
                    <strong style={{ color: "#7c3aed" }}>• [일괄 진행]:</strong> 상단 큰 버튼 <strong>[🖼️ 전체 씬 AI 이미지 일괄 생성]</strong>을 누르면 {videoScenes.length}개 씬의 시작 이미지가 한 번에 일괄 생성됩니다.
                  </div>
                </div>
              </div>
            </div>

            {videoScenes.length === 0 ? (
              <p className="empty-state">
                {hasAudio
                  ? "음성이 준비되었습니다. [🎨 6개 비디오 씬 & 연속성 설계] 버튼을 눌러 원테이크 씬들을 구성하세요."
                  : "먼저 음성을 생성해주세요."}
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                {videoScenes.map((scene) => {
                  const hasStartImage = Boolean(scene.start_image_url);
                  const hasVideo = Boolean(scene.generated_video_url);
                  const hasFinalFrame = Boolean(scene.final_frame_url && hasVideo);
                  const isLastScene = scene.scene_id === videoScenes.length;
                  const isMatched = scene.scene_id > 1 ? (matchPrevMap[scene.scene_id] !== false) : false;
                  const isMultiShot = multiShotsMap[scene.scene_id] ?? false;

                  const isThisImageBusy = Boolean(busyImageScenes[scene.scene_id]) || (busyAction === "image" && busySceneId === scene.scene_id) || busyAction === "all_images";
                  const isThisVideoBusy = Boolean(busyVideoScenes[scene.scene_id]) || (busyAction === "video" && busySceneId === scene.scene_id) || busyAction === "all_videos";

                  return (
                    <article
                      key={scene.scene_id}
                      className={isThisImageBusy || isThisVideoBusy ? "busy-pulse-card" : ""}
                      style={{
                        background: "rgba(255, 255, 255, 0.03)",
                        border: isThisImageBusy || isThisVideoBusy ? "1.5px solid #38bdf8" : "1px solid rgba(255, 255, 255, 0.12)",
                        borderRadius: "10px",
                        padding: "1.2rem",
                        display: "flex",
                        flexDirection: "column",
                        gap: "1rem"
                      }}
                    >
                      {/* 씬 헤더 & 액션 버튼들 */}
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span style={{ background: "#2563eb", color: "#fff", padding: "3px 9px", borderRadius: "5px", fontWeight: "bold", fontSize: "13px" }}>
                            SCENE {scene.scene_id}
                          </span>
                          <strong>{scene.start.toFixed(1)}s ~ {scene.end.toFixed(1)}s</strong>
                          <span className="muted" style={{ fontSize: "12px" }}>({scene.target_duration.toFixed(1)}초 / {scene.duration_frames}프레임)</span>

                          {isThisImageBusy && (
                            <span style={{ background: "#0284c7", color: "#fff", padding: "2px 8px", borderRadius: "4px", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px", fontWeight: "600" }}>
                              <span className="spinner-icon">⏳</span> AI 이미지 생성 진행 중...
                            </span>
                          )}
                          {isThisVideoBusy && (
                            <span style={{ background: "#7c3aed", color: "#fff", padding: "2px 8px", borderRadius: "4px", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px", fontWeight: "600" }}>
                              <span className="spinner-icon">⏳</span> AI 비디오 렌더링 진행 중...
                            </span>
                          )}
                        </div>

                        {/* 작업 버튼 모음 */}
                        <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                          {scene.scene_id > 1 && (
                            <label
                              style={{
                                fontSize: "12px",
                                color: isMatched ? "#38bdf8" : "#94a3b8",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "6px",
                                cursor: "pointer",
                                background: isMatched ? "rgba(56, 189, 248, 0.16)" : "rgba(255, 255, 255, 0.06)",
                                border: isMatched ? "1.5px solid #38bdf8" : "1px dashed rgba(255, 255, 255, 0.25)",
                                padding: "5px 10px",
                                borderRadius: "6px",
                                fontWeight: isMatched ? "bold" : "normal",
                                userSelect: "none",
                                transition: "all 0.15s ease"
                              }}
                              title="체크: 이전 씬 마지막 프레임과 이번 씬 시작 이미지를 2장 매칭하여 원테이크로 연결합니다. 체크 해제: 이번 씬 단독 이미지로 생성합니다."
                            >
                              <input
                                type="checkbox"
                                checked={isMatched}
                                onChange={(e) => setMatchPrevMap((prev) => ({ ...prev, [scene.scene_id]: e.target.checked }))}
                                style={{ cursor: "pointer", accentColor: "#0284c7", width: "15px", height: "15px" }}
                              />
                              {isMatched ? "🔗 앞 씬 매칭 (ON)" : "🔗 앞 씬 매칭 (OFF)"}
                            </label>
                          )}

                          <label
                            style={{
                              fontSize: "12px",
                              color: isMultiShot ? "#f43f5e" : "#94a3b8",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "6px",
                              cursor: "pointer",
                              background: isMultiShot ? "rgba(244, 63, 94, 0.18)" : "rgba(255, 255, 255, 0.06)",
                              border: isMultiShot ? "1.5px solid #f43f5e" : "1px dashed rgba(255, 255, 255, 0.25)",
                              padding: "5px 10px",
                              borderRadius: "6px",
                              fontWeight: isMultiShot ? "bold" : "normal",
                              userSelect: "none",
                              transition: "all 0.15s ease"
                            }}
                            title="체크: 카메라 앵글이 전환되는 멀티샷(다각도 연출)을 활성화합니다."
                          >
                            <input
                              type="checkbox"
                              checked={isMultiShot}
                              onChange={(e) => setMultiShotsMap((prev) => ({ ...prev, [scene.scene_id]: e.target.checked }))}
                              style={{ cursor: "pointer", accentColor: "#e11d48", width: "15px", height: "15px" }}
                            />
                            {isMultiShot ? "🎥 멀티샷 (ON)" : "🎥 멀티샷 (OFF)"}
                          </label>

                          {onGenerateSceneImage && (
                            <button
                              className="secondary-button"
                              disabled={isBusy || isThisImageBusy}
                              onClick={() => handleSceneImageClick(scene.scene_id)}
                              type="button"
                              style={{ padding: "4px 10px", fontSize: "12px" }}
                              title={`${currentImageModel.name} 모델로 ${isMatched ? "클라이맥스 목적지 이미지" : "시작 이미지"}를 생성합니다`}
                            >
                              {isThisImageBusy ? (
                                <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", color: "#0284c7", fontWeight: "bold" }}>
                                  <span className="spinner-icon">⏳</span> 이미지 생성 중...
                                </span>
                              ) : isMatched ? (
                                `🏁 클라이맥스 이미지 생성 (${currentImageModel.name})`
                              ) : (
                                `🖼️ 시작 이미지 생성 (${currentImageModel.name})`
                              )}
                            </button>
                          )}

                          {onGenerateSceneVideo && (
                            (() => {
                              // 앞 씬 매칭 ON인 경우: 앞 씬의 비디오가 완료되었는지 확인 (앞 씬이 비디오 생성 중이거나 결과가 없으면 대기 필요)
                              const isMatchedNeedWait = scene.scene_id > 1 && isMatched && (
                                !Boolean(videoScenes.find((s) => s.scene_id === scene.scene_id - 1)?.final_frame_url || videoScenes.find((s) => s.scene_id === scene.scene_id - 1)?.generated_video_url)
                                || Boolean(busyVideoScenes[scene.scene_id - 1])
                              );

                              return (
                                <button
                                  className="primary-button"
                                  disabled={isBusy || !hasStartImage || isThisImageBusy || isThisVideoBusy || isMatchedNeedWait}
                                  onClick={() => handleSceneVideoClick(scene.scene_id, Math.max(4, Math.round(scene.target_duration)), isMultiShot, isMatched)}
                                  type="button"
                                  style={{
                                    padding: "4px 10px",
                                    fontSize: "12px",
                                    ...(isThisVideoBusy
                                      ? { background: "#9333ea", color: "#ffffff", border: "1.5px solid #d8b4fe", cursor: "wait", opacity: 1 }
                                      : !hasStartImage || isMatchedNeedWait
                                      ? { opacity: 0.6 }
                                      : {})
                                  }}
                                  title={
                                    !hasStartImage
                                      ? "⚠️ 시작 이미지가 아직 없습니다. 먼저 왼쪽의 [이미지 생성] 버튼을 눌러주세요."
                                      : isThisVideoBusy
                                      ? "비디오 생성이 진행 중입니다..."
                                      : isMatchedNeedWait
                                      ? `⚠️ Scene ${scene.scene_id - 1}의 비디오가 완료되어야 [앞 씬 매칭] 생성을 시작할 수 있습니다 (단독 생성을 원하시면 [앞 씬 매칭]을 OFF로 꺼주세요).`
                                      : `${currentVideoModel.name} 모델로 비디오를 생성합니다 (목표: ${scene.target_duration.toFixed(1)}초)`
                                  }
                                >
                                  {isThisVideoBusy ? (
                                    <span style={{ display: "inline-flex", alignItems: "center", gap: "6px", color: "#ffffff", fontWeight: "bold" }}>
                                      <span className="spinner-icon">⏳</span> 🎬 비디오 생성 중...
                                    </span>
                                  ) : !hasStartImage ? (
                                    `🎬 비디오 생성 (⚠️ 시작 이미지 필요)`
                                  ) : isMatchedNeedWait ? (
                                    `🎬 비디오 생성 (⏳ Scene ${scene.scene_id - 1} 완료 대기)`
                                  ) : hasVideo ? (
                                    `🔄 비디오 다시 생성 (${scene.scene_id > 1 && isMatched ? "도킹 매칭" : "단독 모션"}${isMultiShot ? " + 멀티샷" : ""})`
                                  ) : (
                                    `🎬 비디오 생성 (${scene.scene_id > 1 && isMatched ? "도킹 매칭" : "단독 모션"}${isMultiShot ? " + 멀티샷" : ""})`
                                  )}
                                </button>
                              );
                            })()
                          )}

                          {onPassContinuity && hasFinalFrame && !isLastScene && (
                            <button
                              className="secondary-button"
                              disabled={isBusy}
                              onClick={() => onPassContinuity(scene.scene_id)}
                              type="button"
                              style={{ padding: "4px 10px", fontSize: "12px", borderColor: "#38bdf8", color: "#38bdf8" }}
                              title="이 씬의 마지막 비디오 프레임을 다음 씬의 시작 이미지로 복사합니다"
                            >
                              ➡️ 다음 씬(Scene {scene.scene_id + 1})으로 프레임 인계
                            </button>
                          )}
                        </div>
                      </div>

                      {/* 나레이션 */}
                      <div style={{ background: "#f8fafc", border: "1px solid #cbd5e1", padding: "0.6rem 0.8rem", borderRadius: "6px", fontSize: "0.92rem", color: "#0f172a" }}>
                        🎙️ <strong>나레이션:</strong> <em>"{scene.narration}"</em>
                      </div>

                      {/* 💡 AI 생성 프롬프트 박스 (이미지 프롬프트 & 비디오 모션 프롬프트) */}
                      {editingPromptSceneId === scene.scene_id ? (
                        <div
                          style={{
                            background: "#0f172a",
                            border: "1.5px solid #38bdf8",
                            borderRadius: "8px",
                            padding: "0.85rem 1rem",
                            display: "flex",
                            flexDirection: "column",
                            gap: "0.6rem",
                            fontSize: "12px",
                            boxShadow: "0 0 15px rgba(56, 189, 248, 0.2)"
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ color: "#38bdf8", fontWeight: "bold" }}>
                              ✏️ Scene {scene.scene_id} 프롬프트 직접 편집
                            </span>
                            <span style={{ fontSize: "11px", color: "#94a3b8" }}>영문 단어를 자유롭게 수정하세요</span>
                          </div>

                          <div>
                            <label style={{ color: "#38bdf8", fontWeight: "bold", fontSize: "11px", marginBottom: "4px", display: "block" }}>
                              🖼️ 시작/클라이맥스 이미지 프롬프트:
                            </label>
                            <textarea
                              rows={3}
                              value={editImagePrompt}
                              onChange={(e) => setEditImagePrompt(e.target.value)}
                              disabled={isSavingPrompts}
                              style={{
                                width: "100%",
                                background: "rgba(0,0,0,0.6)",
                                border: "1px solid #38bdf8",
                                borderRadius: "5px",
                                color: "#f8fafc",
                                fontSize: "12px",
                                padding: "8px 10px",
                                fontFamily: "monospace",
                                resize: "vertical",
                                boxSizing: "border-box"
                              }}
                            />
                          </div>

                          <div>
                            <label style={{ color: "#c084fc", fontWeight: "bold", fontSize: "11px", marginBottom: "4px", display: "block" }}>
                              🎬 비디오 모션 프롬프트:
                            </label>
                            <textarea
                              rows={3}
                              value={editVideoPrompt}
                              onChange={(e) => setEditVideoPrompt(e.target.value)}
                              disabled={isSavingPrompts}
                              style={{
                                width: "100%",
                                background: "rgba(0,0,0,0.6)",
                                border: "1px solid #c084fc",
                                borderRadius: "5px",
                                color: "#f8fafc",
                                fontSize: "12px",
                                padding: "8px 10px",
                                fontFamily: "monospace",
                                resize: "vertical",
                                boxSizing: "border-box"
                              }}
                            />
                          </div>

                          <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end", marginTop: "4px" }}>
                            <button
                              type="button"
                              className="primary-button"
                              disabled={isSavingPrompts}
                              onClick={() => handleSavePrompts(scene.scene_id)}
                              style={{ fontSize: "11px", padding: "5px 12px", background: "#0284c7" }}
                            >
                              {isSavingPrompts ? "⏳ 저장 중..." : "💾 프롬프트 저장"}
                            </button>
                            <button
                              type="button"
                              className="secondary-button"
                              disabled={isSavingPrompts}
                              onClick={cancelEditingPrompts}
                              style={{ fontSize: "11px", padding: "5px 10px" }}
                            >
                              취소
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div
                          style={{
                            background: "#0f172a",
                            border: "1px solid #334155",
                            borderRadius: "8px",
                            padding: "0.85rem 1rem",
                            display: "flex",
                            flexDirection: "column",
                            gap: "0.6rem",
                            fontSize: "12px",
                            fontFamily: "monospace"
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ color: "#38bdf8", fontWeight: "bold", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                              {isMatched ? "🏁 클라이맥스(종료) 이미지 프롬프트" : "🖼️ 시작 이미지 프롬프트"} ({currentImageModel.name}):
                              {isMatched && (
                                <span style={{ fontSize: "10px", background: "rgba(56, 189, 248, 0.2)", color: "#38bdf8", padding: "1px 6px", borderRadius: "3px", fontWeight: "normal" }}>
                                  도착점 앵커(End Frame) 매칭 ON
                                </span>
                              )}
                            </span>
                            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                              <button
                                type="button"
                                className="secondary-button"
                                onClick={() => startEditingPrompts(scene.scene_id, scene.start_image_prompt, scene.video_prompt)}
                                style={{ fontSize: "11px", padding: "2px 8px", color: "#38bdf8", borderColor: "rgba(56, 189, 248, 0.4)" }}
                                title="프롬프트 영문 텍스트를 직접 수정합니다"
                              >
                                ✏️ 프롬프트 직접 편집
                              </button>
                              <span style={{ fontSize: "11px", color: "#4ade80", fontWeight: "bold" }}>✓ 설계 완료</span>
                            </div>
                          </div>
                          <p style={{ margin: 0, color: "#e2e8f0", lineHeight: "1.45", background: "rgba(255,255,255,0.06)", padding: "0.55rem 0.75rem", borderRadius: "5px", border: "1px solid rgba(255,255,255,0.1)" }}>
                            {scene.start_image_prompt}
                          </p>

                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "2px" }}>
                            <span style={{ color: "#c084fc", fontWeight: "bold", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                              {isMatched ? "🎬 비디오 도킹 모션 프롬프트" : "🎬 비디오 모션 프롬프트"} ({currentVideoModel.name}):
                              {isMatched && (
                                <span style={{ fontSize: "10px", background: "rgba(192, 132, 252, 0.2)", color: "#d8b4fe", padding: "1px 6px", borderRadius: "3px", fontWeight: "normal" }}>
                                  이전 씬 끝 ➔ 클라이맥스 도킹
                                </span>
                              )}
                            </span>
                          </div>
                          <p style={{ margin: 0, color: "#e2e8f0", lineHeight: "1.45", background: "rgba(255,255,255,0.06)", padding: "0.55rem 0.75rem", borderRadius: "5px", border: "1px solid rgba(255,255,255,0.1)" }}>
                            {scene.video_prompt}
                          </p>
                        </div>
                      )}

                      {/* 4단계 비주얼 파이프라인 (이전 끝 -> 시작 이미지 -> Veo 비디오 -> 마지막 프레임) */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
                          gap: "0.75rem",
                          background: "rgba(0, 0, 0, 0.4)",
                          padding: "1rem",
                          borderRadius: "8px",
                          border: "1px solid rgba(255, 255, 255, 0.08)"
                        }}
                      >
                        {/* 1. 이전 씬 마지막 프레임 */}
                        <div
                          style={{
                            textAlign: "center",
                            display: "flex",
                            flexDirection: "column",
                            opacity: scene.scene_id > 1 && !isMatched ? 0.4 : 1,
                            transition: "opacity 0.2s ease"
                          }}
                        >
                          <div style={{ fontSize: "11px", color: scene.scene_id > 1 && !isMatched ? "#94a3b8" : "#38bdf8", marginBottom: "4px", fontWeight: "600", display: "flex", alignItems: "center", justifyContent: "center", gap: "4px" }}>
                            {scene.scene_id > 1 && !isMatched ? (
                              <span style={{ background: "rgba(255,255,255,0.1)", color: "#94a3b8", fontSize: "10px", padding: "1px 6px", borderRadius: "3px" }}>
                                🚫 앞 씬 연결 안함 (단독 모드)
                              </span>
                            ) : scene.continuity.prev_final_frame_url ? (
                              `⬅️ Scene ${scene.scene_id - 1} 끝 (출발 앵커)`
                            ) : (
                              "🎬 쇼츠 오프닝 (첫 씬 출발점)"
                            )}
                          </div>
                          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            {scene.continuity.prev_final_frame_url ? (
                              <img
                                src={`${scene.continuity.prev_final_frame_url}?t=${cacheBuster}`}
                                alt={`Scene ${scene.scene_id - 1} final frame`}
                                style={{ width: "100%", maxHeight: "200px", objectFit: "contain", borderRadius: "6px", border: scene.scene_id > 1 && !isMatched ? "1px dashed rgba(255,255,255,0.2)" : "1.5px solid #38bdf8" }}
                              />
                            ) : (
                              <div style={{ width: "100%", height: "180px", display: "flex", alignItems: "center", justifyContent: "center", border: "1px dashed rgba(255,255,255,0.15)", borderRadius: "6px", color: "#64748b", fontSize: "12px" }}>
                                영상 시작 프레임
                              </div>
                            )}
                          </div>
                        </div>

                        {/* 2. 현재 씬 이미지 (매칭 여부에 따라 클라이맥스 도착점 vs 시작 앵커) */}
                        <div style={{ textAlign: "center", display: "flex", flexDirection: "column" }}>
                          <div style={{ fontSize: "11px", color: isMatched ? "#38bdf8" : "#38bdf8", marginBottom: "4px", fontWeight: "bold" }}>
                            {isMatched
                              ? `🏁 Scene ${scene.scene_id} 클라이맥스 (종료) 이미지`
                              : `🎯 Scene ${scene.scene_id} 시작 이미지`}
                            <span style={{ marginLeft: "4px", fontSize: "10px", color: isMatched ? "#7dd3fc" : "#94a3b8" }}>
                              {isMatched ? "[도착 앵커]" : "[시작 앵커]"}
                            </span>
                          </div>
                          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            {hasStartImage ? (
                              <img
                                src={`${scene.start_image_url}?t=${cacheBuster}`}
                                alt={`Scene ${scene.scene_id} ${isMatched ? "climax frame" : "start frame"}`}
                                style={{ width: "100%", maxHeight: "200px", objectFit: "contain", borderRadius: "6px", border: isMatched ? "2px solid #38bdf8" : "2px solid #0284c7", boxShadow: "0 2px 8px rgba(56, 189, 248, 0.2)" }}
                              />
                            ) : (
                              <div style={{ width: "100%", height: "180px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", border: "1px dashed rgba(56,189,248,0.4)", borderRadius: "6px", color: "#94a3b8", fontSize: "12px", padding: "0.5rem" }}>
                                <span>이미지 미생성</span>
                                <small className="muted">[이미지 생성] 클릭</small>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* 3. 현재 씬 비디오 */}
                        <div style={{ textAlign: "center", display: "flex", flexDirection: "column" }}>
                          <div style={{ fontSize: "11px", color: "#a78bfa", marginBottom: "4px", fontWeight: "bold" }}>
                            {isMatched
                              ? `🎬 Scene ${scene.scene_id} 비디오 (도킹 매칭)`
                              : `🎬 Scene ${scene.scene_id} 비디오 (단독 모션)`}
                          </div>
                          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            {hasVideo ? (
                              <video
                                controls
                                loop
                                muted
                                playsInline
                                src={`${scene.generated_video_url}?t=${cacheBuster}`}
                                style={{ width: "100%", maxHeight: "200px", borderRadius: "6px", border: "2px solid #a78bfa", background: "#000" }}
                              />
                            ) : (
                              <div style={{ width: "100%", height: "180px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", border: "1px dashed rgba(167,139,250,0.4)", borderRadius: "6px", color: "#94a3b8", fontSize: "12px", padding: "0.5rem" }}>
                                <span>비디오 미생성</span>
                                <small className="muted">[비디오 생성] 클릭</small>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* 4. 추출된 마지막 프레임 (Final Frame) */}
                        <div style={{ textAlign: "center", display: "flex", flexDirection: "column" }}>
                          <div style={{ fontSize: "11px", color: "#34d399", marginBottom: "4px", fontWeight: "bold" }}>
                            🏁 Scene {scene.scene_id} 마지막 프레임 (ffmpeg 추출)
                          </div>
                          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                            {hasFinalFrame ? (
                              <img
                                src={`${scene.final_frame_url}?t=${cacheBuster}`}
                                alt={`Scene ${scene.scene_id} final frame`}
                                style={{ width: "100%", maxHeight: "200px", objectFit: "contain", borderRadius: "6px", border: "2px solid #34d399", boxShadow: "0 2px 8px rgba(52, 211, 153, 0.2)" }}
                              />
                            ) : (
                              <div style={{ width: "100%", height: "180px", display: "flex", alignItems: "center", justifyContent: "center", border: "1px dashed rgba(52,211,153,0.3)", borderRadius: "6px", color: "#64748b", fontSize: "12px" }}>
                                비디오 완료 후 자동 추출
                              </div>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* 연속성 인계 정보 */}
                      <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "0.6rem 0.8rem", borderRadius: "6px", fontSize: "0.85rem", display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "0.5rem" }}>
                        <div>🎥 <strong>카메라:</strong> <span className="muted">{scene.continuity.camera}</span></div>
                        <div>📦 <strong>피사체:</strong> <span className="muted">{scene.continuity.subject_state}</span></div>
                        <div>💡 <strong>조명:</strong> <span className="muted">{scene.continuity.lighting}</span></div>
                        <div style={{ gridColumn: "1 / -1", color: "#38bdf8" }}>
                          🔗 <strong>연속성 인계(Handoff):</strong> {scene.continuity.handoff_description}
                        </div>
                      </div>

                      {/* 💬 씬 피드백 & 프롬프트 AI 수정 & 다시 생성 박스 (이미지 / 영상 완전 분리) */}
                      <div
                        style={{
                          background: "linear-gradient(135deg, rgba(30, 41, 59, 0.75) 0%, rgba(15, 23, 42, 0.85) 100%)",
                          border: "1px solid rgba(56, 189, 248, 0.35)",
                          borderRadius: "10px",
                          padding: "1rem",
                          display: "flex",
                          flexDirection: "column",
                          gap: "0.85rem"
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
                          <span style={{ fontSize: "13px", fontWeight: "bold", color: "#38bdf8", display: "inline-flex", alignItems: "center", gap: "6px" }}>
                            💬 Scene {scene.scene_id} 피드백 & AI 프롬프트 수정
                          </span>
                          <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                            이미지와 영상 피드백을 각각 독립적으로 입력하고 다시 생성할 수 있습니다.
                          </span>
                        </div>

                        {/* 2단 분할 그리드: 왼쪽 이미지 피드백 / 오른쪽 영상 피드백 */}
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "0.85rem" }}>
                          
                          {/* 🎨 1. 이미지 전용 피드백 */}
                          <div
                            style={{
                              background: "rgba(2, 132, 199, 0.08)",
                              border: "1px solid rgba(56, 189, 248, 0.3)",
                              borderRadius: "8px",
                              padding: "0.75rem",
                              display: "flex",
                              flexDirection: "column",
                              gap: "0.5rem"
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <strong style={{ fontSize: "12px", color: "#38bdf8", display: "inline-flex", alignItems: "center", gap: "5px" }}>
                                {isMatched ? "🏁 클라이맥스(종료) 이미지 피드백" : "🎨 시작 이미지 피드백"} ({currentImageModel.name})
                              </strong>
                              {scene.last_image_feedback && (
                                <span style={{ fontSize: "10px", color: "#7dd3fc" }} title={scene.last_image_feedback}>
                                  최근: "{scene.last_image_feedback.slice(0, 18)}..."
                                </span>
                              )}
                            </div>

                            <textarea
                              rows={2}
                              value={imageFeedbackMap[scene.scene_id] ?? ""}
                              onChange={(e) => setImageFeedbackMap((prev) => ({ ...prev, [scene.scene_id]: e.target.value }))}
                              placeholder={
                                isMatched
                                  ? "씬의 클라이맥스 정점 / 완성된 결과 이미지 수정사항 입력 (예: 결과물이 화려하게 펼쳐진 모습, 캐릭터의 통쾌한 표정, 빨대 꼭대기의 장관...)"
                                  : "0초 시작 이미지 수정사항 입력 (예: 캐릭터 표정을 깜짝 놀란 표정으로, 빨대를 더 투명하게, 배경을 밝은 하늘로...)"
                              }
                              disabled={Boolean(feedbackLoadingMap[`${scene.scene_id}_image`]) || isBusy}
                              style={{
                                width: "100%",
                                background: "rgba(0, 0, 0, 0.4)",
                                border: "1px solid rgba(56, 189, 248, 0.25)",
                                borderRadius: "6px",
                                padding: "0.5rem 0.7rem",
                                color: "#f8fafc",
                                fontSize: "12px",
                                resize: "vertical",
                                boxSizing: "border-box"
                              }}
                            />

                            {feedbackLoadingMap[`${scene.scene_id}_image`] && (
                              <div style={{ fontSize: "11px", color: "#38bdf8", fontWeight: "bold", display: "flex", alignItems: "center", gap: "4px" }}>
                                <span className="spinner-icon">⏳</span> {feedbackLoadingMap[`${scene.scene_id}_image`]}
                              </div>
                            )}

                            <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap", marginTop: "auto" }}>
                              <button
                                type="button"
                                className="primary-button"
                                disabled={Boolean(feedbackLoadingMap[`${scene.scene_id}_image`]) || isBusy || !imageFeedbackMap[scene.scene_id]?.trim()}
                                onClick={() => handleFeedbackRegenerate(scene.scene_id, "image", Math.max(4, Math.round(scene.target_duration)), isMultiShot, isMatched)}
                                style={{
                                  fontSize: "11px",
                                  padding: "5px 10px",
                                  background: "#0284c7",
                                  border: "none",
                                  color: "#ffffff",
                                  fontWeight: "bold"
                                }}
                                title="이미지 프롬프트를 AI가 수정한 뒤 이미지를 즉시 새로 만듭니다"
                              >
                                {isMatched ? "🏁 클라이맥스 이미지 다시 생성" : "🎨 시작 이미지 다시 생성"}
                              </button>

                              <button
                                type="button"
                                className="secondary-button"
                                disabled={Boolean(feedbackLoadingMap[`${scene.scene_id}_image`]) || isBusy || !imageFeedbackMap[scene.scene_id]?.trim()}
                                onClick={() => handleFeedbackRegenerate(scene.scene_id, "prompt_image", Math.max(4, Math.round(scene.target_duration)), isMultiShot, isMatched)}
                                style={{ fontSize: "11px", padding: "4px 8px" }}
                                title="생성은 하지 않고 이미지 프롬프트만 수정합니다"
                              >
                                ✏️ 프롬프트만 수정
                              </button>
                            </div>
                          </div>

                          {/* 🎬 2. 영상(모션) 전용 피드백 */}
                          <div
                            style={{
                              background: "rgba(124, 58, 237, 0.08)",
                              border: "1px solid rgba(168, 85, 247, 0.3)",
                              borderRadius: "8px",
                              padding: "0.75rem",
                              display: "flex",
                              flexDirection: "column",
                              gap: "0.5rem"
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <strong style={{ fontSize: "12px", color: "#c084fc", display: "inline-flex", alignItems: "center", gap: "5px" }}>
                                {isMatched ? "🎬 원테이크 도킹 모션 피드백" : "🎬 영상(모션) 피드백"} ({currentVideoModel.name})
                              </strong>
                              {scene.last_video_feedback && (
                                <span style={{ fontSize: "10px", color: "#d8b4fe" }} title={scene.last_video_feedback}>
                                  최근: "{scene.last_video_feedback.slice(0, 18)}..."
                                </span>
                              )}
                            </div>

                            <textarea
                              rows={2}
                              value={videoFeedbackMap[scene.scene_id] ?? ""}
                              onChange={(e) => setVideoFeedbackMap((prev) => ({ ...prev, [scene.scene_id]: e.target.value }))}
                              placeholder={
                                isMatched
                                  ? "이전 씬 끝에서 클라이맥스 목적지까지의 카메라 워킹 및 모션 수정 (예: 크레인 틸트업 속도 증가, 물방울 모션 강조...)"
                                  : "카메라 워킹 및 동작 수정사항 입력 (예: 카메라가 아래에서 위로 빠르게 틸트업, 물방울이 튀는 움직임 강조...)"
                              }
                              disabled={Boolean(feedbackLoadingMap[`${scene.scene_id}_video`]) || isBusy}
                              style={{
                                width: "100%",
                                background: "rgba(0, 0, 0, 0.4)",
                                border: "1px solid rgba(168, 85, 247, 0.25)",
                                borderRadius: "6px",
                                padding: "0.5rem 0.7rem",
                                color: "#f8fafc",
                                fontSize: "12px",
                                resize: "vertical",
                                boxSizing: "border-box"
                              }}
                            />

                            {feedbackLoadingMap[`${scene.scene_id}_video`] && (
                              <div style={{ fontSize: "11px", color: "#c084fc", fontWeight: "bold", display: "flex", alignItems: "center", gap: "4px" }}>
                                <span className="spinner-icon">⏳</span> {feedbackLoadingMap[`${scene.scene_id}_video`]}
                              </div>
                            )}

                            <div style={{ display: "flex", gap: "0.4rem", alignItems: "center", flexWrap: "wrap", marginTop: "auto" }}>
                              <button
                                type="button"
                                className="primary-button"
                                disabled={Boolean(feedbackLoadingMap[`${scene.scene_id}_video`]) || isBusy || !hasStartImage || !videoFeedbackMap[scene.scene_id]?.trim()}
                                onClick={() => handleFeedbackRegenerate(scene.scene_id, "video", Math.max(4, Math.round(scene.target_duration)), isMultiShot, isMatched)}
                                style={{
                                  fontSize: "11px",
                                  padding: "5px 10px",
                                  background: "linear-gradient(90deg, #7c3aed 0%, #db2777 100%)",
                                  border: "none",
                                  color: "#ffffff",
                                  fontWeight: "bold"
                                }}
                                title="비디오 모션 프롬프트를 AI가 수정한 뒤 비디오를 즉시 새로 만듭니다"
                              >
                                🎬 피드백 반영 영상 다시 생성
                              </button>

                              <button
                                type="button"
                                className="secondary-button"
                                disabled={Boolean(feedbackLoadingMap[`${scene.scene_id}_video`]) || isBusy || !videoFeedbackMap[scene.scene_id]?.trim()}
                                onClick={() => handleFeedbackRegenerate(scene.scene_id, "prompt_video", Math.max(4, Math.round(scene.target_duration)), isMultiShot, isMatched)}
                                style={{ fontSize: "11px", padding: "4px 8px" }}
                                title="생성은 하지 않고 비디오 모션 프롬프트만 수정합니다"
                              >
                                ✏️ 프롬프트만 수정
                              </button>
                            </div>
                          </div>

                        </div>
                      </div>


                    </article>
                  );
                })}
              </div>
            )}
          </div>

          {/* 🎬 3단계: 최종 9:16 쇼츠 렌더링 (Remotion / FFmpeg 엔진) */}
          <div
            style={{
              background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)",
              border: "1.5px solid #818cf8",
              borderRadius: "12px",
              padding: "1.5rem",
              marginTop: "1.5rem",
              boxShadow: "0 10px 25px -5px rgba(99, 102, 241, 0.25)",
              color: "#f8fafc"
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "1rem", marginBottom: "1rem" }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "20px" }}>🎬</span>
                  <strong style={{ fontSize: "1.1rem", color: "#a5b4fc" }}>
                    최종 9:16 쇼츠 비디오 렌더링 (배속 싱크 & 자막 & BGM 합성)
                  </strong>
                </div>
                <p style={{ margin: "0.4rem 0 0", fontSize: "0.88rem", color: "#cbd5e1", lineHeight: "1.5", maxWidth: "700px" }}>
                  각 씬 비디오를 <strong>나레이션 목표 시간(target_duration)</strong>에 맞춰 <strong>속도(배속)를 0.95x~1.05x로 자동 미세 조절</strong>하여 오디오 싱크를 칼같이 맞추고, 고화질 볼드 자막과 채널 BGM을 믹싱하여 최종 <code>final.mp4</code>를 완성합니다.
                </p>
              </div>

              {hasFinalVideo && (
                <span className="state-pill state-pill--succeeded" style={{ padding: "6px 12px", fontSize: "13px" }}>
                  ✓ 렌더링 완료 (final.mp4)
                </span>
              )}
            </div>

            {/* 0~2초 오프닝 타이틀 입력란 */}
            <div
              style={{
                background: "rgba(15, 23, 42, 0.65)",
                border: "1px solid rgba(165, 180, 252, 0.35)",
                borderRadius: "10px",
                padding: "12px 16px",
                marginBottom: "1.2rem",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px", flexWrap: "wrap", gap: "4px" }}>
                <label
                  htmlFor="shorts-video-title"
                  style={{
                    fontSize: "13px",
                    fontWeight: "bold",
                    color: "#e2e8f0",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                  }}
                >
                  <span>🏷️</span>
                  <span>쇼츠 오프닝 제목 (영상 시작 0~2초 상단 노출)</span>
                </label>
                <span style={{ fontSize: "11px", color: "#94a3b8" }}>
                  💡 줄바꿈(Enter) 시 2줄 타이틀 카드 적용, 비워둘 경우 제목 생략
                </span>
              </div>
              <textarea
                id="shorts-video-title"
                value={videoTitle}
                onChange={(e) => handleTitleInputChange(e.target.value)}
                placeholder={"예:\n빨대는 10m가 한계인데,\n나무는 어떻게 100m까지?"}
                rows={2}
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  background: "#0b0f19",
                  border: "1px solid #334155",
                  borderRadius: "8px",
                  color: "#ffffff",
                  padding: "10px 14px",
                  fontSize: "14px",
                  lineHeight: "1.4",
                  fontFamily: "inherit",
                  resize: "vertical",
                }}
              />
            </div>

            <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap", marginBottom: hasFinalVideo ? "1.5rem" : "0" }}>
              {onRenderShorts && (
                <button
                  className="primary-button"
                  disabled={isBusy || !hasAudio || videoScenes.length === 0}
                  onClick={handleRenderClick}
                  type="button"
                  style={{
                    background: "linear-gradient(90deg, #6366f1 0%, #a855f7 100%)",
                    border: "none",
                    padding: "10px 20px",
                    fontSize: "14px",
                    fontWeight: "bold",
                    boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)",
                    cursor: (isBusy || !hasAudio || videoScenes.length === 0) ? "not-allowed" : "pointer"
                  }}
                  title="모든 씬을 배속 동기화하고 자막과 오디오를 합성하여 final.mp4를 렌더링합니다"
                >
                  {busyAction === "render" ? (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
                      <span className="spinner-icon">⏳</span> 최종 쇼츠 렌더링 중 (약 10~20초 소요)...
                    </span>
                  ) : isBusy ? (
                    "⏳ 처리 중..."
                  ) : hasFinalVideo ? (
                    "🔄 최종 쇼츠 다시 렌더링"
                  ) : (
                    "🚀 최종 9:16 쇼츠 렌더링 시작"
                  )}
                </button>
              )}

              <div style={{ display: "flex", gap: "0.4rem", fontSize: "11px", color: "#94a3b8", flexWrap: "wrap" }}>
                <span style={{ background: "rgba(255,255,255,0.08)", padding: "4px 8px", borderRadius: "4px" }}>
                  📐 1080x1920 (9:16)
                </span>
                <span style={{ background: "rgba(255,255,255,0.08)", padding: "4px 8px", borderRadius: "4px" }}>
                  🎞️ 24 FPS (시네마틱 모션 무손실)
                </span>
                <span style={{ background: "rgba(255,255,255,0.08)", padding: "4px 8px", borderRadius: "4px" }}>
                  ⚡ 자연스러운 모션 보존 싱크
                </span>
                <span style={{ background: "rgba(255,255,255,0.08)", padding: "4px 8px", borderRadius: "4px" }}>
                  📝 볼드 화이트 자막
                </span>
                <span style={{ background: "rgba(255,255,255,0.08)", padding: "4px 8px", borderRadius: "4px" }}>
                  🎵 채널 BGM 페이드아웃
                </span>
              </div>
            </div>

            {/* 렌더링 진행 중 실시간 상태 알림 카드 */}
            {busyAction === "render" && (
              <div
                style={{
                  background: "linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%)",
                  border: "2px solid #818cf8",
                  borderRadius: "12px",
                  padding: "1.2rem 1.5rem",
                  margin: "1rem 0",
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.75rem",
                  boxShadow: "0 8px 24px rgba(99, 102, 241, 0.25)",
                  animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite"
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "24px" }}>⏳</span>
                  <div>
                    <h4 style={{ margin: 0, fontSize: "1rem", color: "#e0e7ff", fontWeight: 700 }}>
                      Remotion 4.x 최종 쇼츠 렌더링이 진행 중입니다...
                    </h4>
                    <p style={{ margin: "2px 0 0", fontSize: "0.82rem", color: "#c7d2fe" }}>
                      FFmpeg 씬 배속 동기화 후 Remotion 번들러가 단어 팝업 자막 및 1.2x 오디오를 합성합니다.
                    </p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "1rem", fontSize: "0.8rem", color: "#a5b4fc", flexWrap: "wrap", borderTop: "1px solid rgba(255, 255, 255, 0.1)", paddingTop: "0.5rem" }}>
                  <span>✓ 1단계: 씬별 영상 속도(setpts) 미세 조절</span>
                  <span>🔄 2단계: React Remotion 컴포지션 빌드</span>
                  <span>⏳ 3단계: 1080x1920 MP4 렌더링 (약 15~25초 소요)</span>
                </div>
              </div>
            )}

            {/* 렌더링 실패 에러 표시 */}
            {renderError && (
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.15)",
                  border: "1px solid #ef4444",
                  borderRadius: "8px",
                  padding: "0.8rem 1.2rem",
                  margin: "0.75rem 0",
                  color: "#fca5a5",
                  fontSize: "0.85rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px"
                }}
              >
                <span>❌</span>
                <span>렌더링 실패: {renderError}</span>
              </div>
            )}

            {/* 렌더링 완료된 비디오 플레이어 영역 */}
            {hasFinalVideo && finalVideoUrl && (
              <div
                style={{
                  background: "rgba(0, 0, 0, 0.4)",
                  border: "1px solid rgba(255, 255, 255, 0.12)",
                  borderRadius: "10px",
                  padding: "1.2rem",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "1rem"
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", width: "100%", alignItems: "center" }}>
                  <strong style={{ color: "#38bdf8", fontSize: "0.95rem" }}>
                    🎉 완성된 쇼츠 미리보기 (final.mp4)
                  </strong>
                  <a
                    href={finalVideoUrl}
                    download="final.mp4"
                    className="secondary-button"
                    style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "4px", padding: "6px 12px", fontSize: "12px" }}
                  >
                    ⬇️ MP4 비디오 다운로드
                  </a>
                </div>

                <div
                  style={{
                    width: "280px",
                    height: "498px",
                    background: "#000",
                    borderRadius: "12px",
                    overflow: "hidden",
                    boxShadow: "0 8px 30px rgba(0,0,0,0.8)",
                    border: "2px solid #38bdf8"
                  }}
                >
                  <video
                    key={renderKey}
                    controls
                    playsInline
                    src={`${finalVideoUrl}?t=${renderKey}`}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 첨부 이미지 스타일의 모델 선택 모달 */}
      {modalMode && (
        <ModelSelectorModal
          mode={modalMode}
          title={modalMode === "image" ? "🖼️ 이미지 생성 모델 선택" : "🎬 비디오 생성 모델 선택"}
          selectedModelId={modalMode === "image" ? imageModel : videoModel}
          onSelect={(id) => {
            if (modalMode === "image") {
              setImageModel(id);
            } else {
              setVideoModel(id);
            }
          }}
          onClose={() => setModalMode(null)}
        />
      )}
    </section>
  );
}

