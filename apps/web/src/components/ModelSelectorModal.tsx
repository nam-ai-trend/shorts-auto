import { useState } from "react";

export interface ModelOption {
  readonly id: string;
  readonly name: string;
  readonly provider: string;
  readonly description: string;
  readonly badge?: string;
  readonly badgeType?: "new" | "free" | "popular" | "recommended" | "value";
  readonly tags?: readonly string[];
  readonly iconType: "flux" | "kling" | "google" | "higgsfield" | "wan" | "seedance" | "grok" | "banana" | "gpt" | "minimax";
}

export const IMAGE_MODELS: readonly ModelOption[] = [
  {
    id: "nano_banana_pro",
    name: "Nano Banana Pro",
    provider: "Higgsfield",
    description: "3D 클레이메이션 및 인포그래픽 텍스처에 최적화된 고화질 세로형 모델",
    badge: "나노바나나 대표",
    badgeType: "popular",
    tags: ["9:16 특화", "1K-4K"],
    iconType: "banana"
  },
  {
    id: "gpt_image_2",
    name: "GPT Image 2",
    provider: "OpenAI / Higgsfield",
    description: "복합 지시 프롬프트와 논리적 사물 배치, 텍스트 렌더링에 강한 모델",
    badge: "GPT 대표",
    badgeType: "recommended",
    tags: ["2K", "정밀 프롬프트"],
    iconType: "gpt"
  },
  {
    id: "seedream_v5_pro",
    name: "Seedream 5.0 Pro",
    provider: "ByteDance / Seedance",
    description: "바이트댄스 시댄스 생태계의 고품질 시네마틱 감성 이미지 모델",
    badge: "시댄스 대표",
    badgeType: "new",
    tags: ["시네마틱", "2K"],
    iconType: "seedance"
  },
  {
    id: "flux_3_image",
    name: "FLUX 3 Image",
    provider: "Black Forest Labs",
    description: "극사실적 질감 표현과 조명, 포토리얼리즘 디테일에 특화된 모델",
    badge: "플럭스 대표",
    badgeType: "popular",
    tags: ["포토리얼", "텍스처"],
    iconType: "flux"
  },
  {
    id: "dall-e-3",
    name: "OpenAI DALL-E 3",
    provider: "OpenAI Direct",
    description: "OpenAI API 직접 연결을 통한 창의적 스타일 일러스트레이션",
    tags: ["클래식"],
    iconType: "gpt"
  }
];

export const VIDEO_MODELS: readonly ModelOption[] = [
  {
    id: "kling_o3_flf",
    name: "Kling 3.0 Omni (Frames)",
    provider: "Kuaishou",
    description: "시작 이미지와 종료 이미지(2개 프레임)를 완벽하게 연결하는 원테이크 연속성 특화 모델",
    badge: "원테이크 추천",
    badgeType: "recommended",
    tags: ["시작+종료 2장 보간", "멀티샷 지원"],
    iconType: "kling"
  },
  {
    id: "minimax_h3",
    name: "Minimax H3",
    provider: "MiniMax",
    description: "시작+종료 2장 프레임 보간과 10크레딧의 뛰어난 가성비를 갖춘 원테이크 모델",
    badge: "원테이크 + 최고가성비",
    badgeType: "recommended",
    tags: ["원테이크", "10 크레딧", "2K"],
    iconType: "minimax"
  },
  {
    id: "grok_video_v15_lite",
    name: "Grok Imagine 1.5 Lite",
    provider: "xAI",
    description: "단 5크레딧으로 초고속 생성하는 압도적인 최고가성비 모션 영상",
    badge: "최고가성비",
    badgeType: "value",
    tags: ["최고가성비", "5 크레딧", "720p/1080p"],
    iconType: "grok"
  },
  {
    id: "veo3_1",
    name: "Google Veo 3.1",
    provider: "Google DeepMind",
    description: "사운드 컨트롤이 가능한 정밀 영상과 물리 시뮬레이션 (시작 1장 지원)",
    badge: "인기",
    badgeType: "popular",
    tags: ["1080p", "6초"],
    iconType: "google"
  },
  {
    id: "seedance_2_0",
    name: "Seedance 2.0",
    provider: "ByteDance",
    description: "시네마틱 멀티샷 영상 제작 및 시작/종료 프레임 키프레임 보간",
    badge: "시댄스 대표",
    badgeType: "popular",
    tags: ["시작+종료 프레임", "720p/1080p"],
    iconType: "seedance"
  },
  {
    id: "wan3_0",
    name: "Wan 3.0",
    provider: "Alibaba",
    description: "사운드와 함께 카메라를 제어하는 영상, 더 자유로운 표현",
    tags: ["오디오 동기화", "카메라 제어"],
    iconType: "wan"
  },
  {
    id: "flux_3_video",
    name: "FLUX.3 Video",
    provider: "Black Forest Labs",
    description: "동기화된 오디오와 함께 텍스트, 이미지, 영상 생성",
    badge: "신규",
    badgeType: "new",
    tags: ["오디오 포함", "텍스트/이미지"],
    iconType: "flux"
  },
  {
    id: "hf_mult_motion_control",
    name: "Higgsfield Genjutsu",
    provider: "Higgsfield",
    description: "고급 카메라 제어와 모션 이펙트 프리셋",
    badge: "신규",
    badgeType: "free",
    tags: ["1080p", "4s-30s"],
    iconType: "higgsfield"
  },
  {
    id: "gemini_omni",
    name: "Gemini Omni Flash",
    provider: "Google",
    description: "Google의 멀티 이미지 영상 생성",
    tags: ["멀티 이미지"],
    iconType: "google"
  }
];

function ModelIcon({ type }: { readonly type: ModelOption["iconType"] }) {
  const iconMap: Record<ModelOption["iconType"], { symbol: string; color: string }> = {
    flux: { symbol: "▲", color: "#a855f7" },
    kling: { symbol: "⧉", color: "#ec4899" },
    google: { symbol: "G", color: "#4285f4" },
    higgsfield: { symbol: "✦", color: "#eab308" },
    wan: { symbol: "⌘", color: "#f97316" },
    seedance: { symbol: "📶", color: "#06b6d4" },
    grok: { symbol: "⊘", color: "#cbd5e1" },
    banana: { symbol: "🍌", color: "#eab308" },
    gpt: { symbol: "🧠", color: "#10b981" },
    minimax: { symbol: "M", color: "#10b981" }
  };
  const icon = iconMap[type] ?? { symbol: "❖", color: "#38bdf8" };

  return (
    <div
      style={{
        width: "44px",
        height: "44px",
        borderRadius: "10px",
        background: "rgba(255, 255, 255, 0.08)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "20px",
        color: icon.color,
        fontWeight: "bold",
        flexShrink: 0
      }}
    >
      {icon.symbol}
    </div>
  );
}

interface ModelSelectorModalProps {
  readonly title: string;
  readonly mode: "image" | "video";
  readonly selectedModelId: string;
  readonly onSelect: (modelId: string) => void;
  readonly onClose: () => void;
}

export function ModelSelectorModal({
  title,
  mode,
  selectedModelId,
  onSelect,
  onClose
}: ModelSelectorModalProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [tempSelectedId, setTempSelectedId] = useState<string>(selectedModelId);
  const models = mode === "image" ? IMAGE_MODELS : VIDEO_MODELS;

  const selectedModel = models.find((m) => m.id === tempSelectedId) ?? models[0];

  const filtered = models.filter((m) => {
    const q = searchTerm.toLowerCase();
    return (
      m.name.toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      m.provider.toLowerCase().includes(q) ||
      (m.badge && m.badge.toLowerCase().includes(q))
    );
  });

  function handleConfirm() {
    onSelect(tempSelectedId);
    onClose();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: "1rem"
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "480px",
          background: "#161b22",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "16px",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.6)",
          display: "flex",
          flexDirection: "column",
          maxHeight: "85vh",
          overflow: "hidden"
        }}
      >
        {/* 헤더 & 검색바 */}
        <div style={{ padding: "1.2rem 1.2rem 0.8rem", borderBottom: "1px solid rgba(255, 255, 255, 0.08)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.8rem" }}>
            <h3 style={{ margin: 0, fontSize: "1.1rem", color: "#f1f5f9" }}>{title}</h3>
            <button
              type="button"
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "#94a3b8",
                fontSize: "20px",
                cursor: "pointer",
                padding: "2px 8px"
              }}
            >
              ✕
            </button>
          </div>

          {/* 검색창 (첨부 이미지 스타일) */}
          <div
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              background: "#0d1117",
              borderRadius: "10px",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              padding: "0 0.75rem"
            }}
          >
            <span style={{ color: "#64748b", marginRight: "6px" }}>🔍</span>
            <input
              type="text"
              placeholder="검색..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                width: "100%",
                background: "transparent",
                border: "none",
                color: "#fff",
                padding: "0.6rem 0",
                fontSize: "0.95rem",
                outline: "none"
              }}
            />
          </div>
        </div>

        {/* 모델 리스트 (첨부 이미지 목록 디자인) */}
        <div style={{ flex: 1, overflowY: "auto", padding: "0.5rem 0" }}>
          {filtered.length === 0 ? (
            <div style={{ padding: "2rem", textAlign: "center", color: "#64748b" }}>
              일치하는 모델이 없습니다.
            </div>
          ) : (
            filtered.map((model) => {
              const isSelected = model.id === tempSelectedId;

              return (
                <div
                  key={model.id}
                  onClick={() => setTempSelectedId(model.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "1rem",
                    padding: "0.9rem 1.2rem",
                    cursor: "pointer",
                    background: isSelected ? "rgba(56, 189, 248, 0.12)" : "transparent",
                    borderLeft: isSelected ? "3px solid #38bdf8" : "3px solid transparent",
                    borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
                    transition: "all 0.15s ease"
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = "rgba(255, 255, 255, 0.04)";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = "transparent";
                    }
                  }}
                >
                  <ModelIcon type={model.iconType} />

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap", marginBottom: "3px" }}>
                      <strong style={{ color: isSelected ? "#38bdf8" : "#f8fafc", fontSize: "0.95rem" }}>
                        {model.name}
                      </strong>

                      {model.badge && (
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: "bold",
                            padding: "1px 6px",
                            borderRadius: "4px",
                            background:
                              model.badgeType === "free" || model.badgeType === "new"
                                ? "#eab308"
                                : model.badgeType === "recommended"
                                ? "#2563eb"
                                : model.badgeType === "value"
                                ? "#10b981"
                                : "#ec4899",
                            color: model.badgeType === "free" || model.badgeType === "new" ? "#000" : "#fff"
                          }}
                        >
                          {model.badge}
                        </span>
                      )}
                    </div>

                    <p style={{ margin: 0, fontSize: "12px", color: "#94a3b8", lineHeight: "1.3" }}>
                      {model.description}
                    </p>

                    {model.tags && (
                      <div style={{ display: "flex", gap: "0.3rem", marginTop: "4px" }}>
                        {model.tags.map((t, idx) => (
                          <span
                            key={idx}
                            style={{
                              fontSize: "10px",
                              background: "rgba(255, 255, 255, 0.06)",
                              color: "#cbd5e1",
                              padding: "1px 5px",
                              borderRadius: "3px"
                            }}
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div style={{ color: isSelected ? "#38bdf8" : "#475569", fontSize: "18px", fontWeight: "bold" }}>
                    {isSelected ? "✓" : "›"}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* 모달 하단: 선택된 모델 요약 & 반영완료 버튼 바 */}
        <div
          style={{
            padding: "1rem 1.2rem",
            background: "#0d1117",
            borderTop: "1px solid rgba(255, 255, 255, 0.1)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "0.75rem"
          }}
        >
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: "11px", color: "#64748b" }}>선택된 모델</div>
            <strong style={{ fontSize: "0.95rem", color: "#38bdf8", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "block" }}>
              {selectedModel ? selectedModel.name : "모델을 선택하세요"}
            </strong>
          </div>

          <div style={{ display: "flex", gap: "0.5rem", flexShrink: 0 }}>
            <button
              type="button"
              className="secondary-button"
              onClick={onClose}
              style={{ padding: "0.5rem 1rem", fontSize: "13px" }}
            >
              취소
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={handleConfirm}
              style={{
                padding: "0.5rem 1.2rem",
                fontSize: "13px",
                fontWeight: "bold",
                background: "#0284c7",
                borderColor: "#38bdf8",
                boxShadow: "0 2px 8px rgba(56, 189, 248, 0.3)"
              }}
            >
              반영 완료
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
