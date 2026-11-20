import { useState } from "react";

export interface ModelOption {
  readonly id: string;
  readonly name: string;
  readonly provider: string;
  readonly platform: "higgsfield" | "flow";
  readonly description: string;
  readonly badge?: string;
  readonly badgeType?: "new" | "free" | "popular" | "recommended" | "value";
  readonly tags?: readonly string[];
  readonly iconType: "flux" | "kling" | "google" | "higgsfield" | "wan" | "seedance" | "grok" | "banana" | "gpt" | "minimax";
}

export const IMAGE_MODELS: readonly ModelOption[] = [
  // === 힉스필드 (Higgsfield) 이미지 모델 ===
  {
    id: "nano_banana_pro",
    name: "Nano Banana Pro",
    provider: "Higgsfield",
    platform: "higgsfield",
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
    platform: "higgsfield",
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
    platform: "higgsfield",
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
    platform: "higgsfield",
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
    platform: "higgsfield",
    description: "OpenAI API 직접 연결을 통한 창의적 스타일 일러스트레이션",
    tags: ["클래식"],
    iconType: "gpt"
  },

  // === Google Flow CLI 이미지 모델 ===
  {
    id: "flow_nano_pro",
    name: "Nano Banana Pro (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "Google Flow 공식 Nano Banana Pro. 3D 입체 질감과 사물 배치 최적화 모델",
    badge: "Flow 대표",
    badgeType: "recommended",
    tags: ["Google Flow", "9:16 특화", "고화질"],
    iconType: "google"
  },
  {
    id: "flow_imagen_4",
    name: "Imagen 4 / 3.5 (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "Google Flow 공식 최신 Imagen. 극사실주의 디테일과 감성적 라이팅 연출",
    badge: "Flow 신규",
    badgeType: "new",
    tags: ["Google Flow", "포토리얼", "최신세대"],
    iconType: "google"
  },
  {
    id: "flow_nano_2_1",
    name: "Nano Banana 2.1 (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "빠른 렌더링 속도와 균형 잡힌 비주얼을 제공하는 Google Flow 표준 모델",
    badge: "Flow 인기",
    badgeType: "popular",
    tags: ["Google Flow", "빠른 속도"],
    iconType: "google"
  },
  {
    id: "flow_nano_2_lite",
    name: "Nano Banana 2 Lite (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "크레딧 소모가 적고 초고속으로 이미지를 뽑아내는 실속형 모델",
    badge: "Flow 가성비",
    badgeType: "value",
    tags: ["Google Flow", "초고속", "실속형"],
    iconType: "google"
  }
];

export const VIDEO_MODELS: readonly ModelOption[] = [
  // === 힉스필드 (Higgsfield) 비디오 모델 ===
  {
    id: "wan3_0",
    name: "Wan 3.0 Video",
    provider: "Wan (Alibaba)",
    platform: "higgsfield",
    description: "Free 플랜 완벽 지원! 시작+종료 2장 프레임 보간 및 720p/1080p 고화질 원테이크 지원",
    badge: "Free 플랜 추천",
    badgeType: "recommended",
    tags: ["Free 플랜 지원", "시작+종료 2장 보간", "8.75 크레딧", "고화질"],
    iconType: "wan"
  },
  {
    id: "kling_o3_flf",
    name: "Kling 3.0 Omni (Frames)",
    provider: "Kuaishou",
    platform: "higgsfield",
    description: "시작+종료 이미지 2장 보간 (주의: 힉스필드 Basic 이상 유료 플랜 필요)",
    badge: "Basic 플랜 전용",
    badgeType: "popular",
    tags: ["Basic 플랜 이상 필요", "시작+종료 2장 보간", "멀티샷 지원"],
    iconType: "kling"
  },
  {
    id: "minimax_h3",
    name: "Minimax H3",
    provider: "MiniMax",
    platform: "higgsfield",
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
    platform: "higgsfield",
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
    platform: "higgsfield",
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
    platform: "higgsfield",
    description: "시네마틱 멀티샷 영상 제작 및 시작/종료 프레임 키프레임 보간",
    badge: "시댄스 대표",
    badgeType: "popular",
    tags: ["시작+종료 프레임", "720p/1080p"],
    iconType: "seedance"
  },
  {
    id: "flux_3_video",
    name: "FLUX.3 Video",
    provider: "Black Forest Labs",
    platform: "higgsfield",
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
    platform: "higgsfield",
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
    platform: "higgsfield",
    description: "Google의 멀티 이미지 영상 생성",
    tags: ["멀티 이미지"],
    iconType: "google"
  },

  // === Google Flow CLI 비디오 모델 ===
  {
    id: "flow_veo_fast",
    name: "Google Veo 3.1 Fast (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "Google Flow 공식 Veo 3.1. 고속 물리 시뮬레이션 및 역동적인 카메라 모션 영상",
    badge: "Flow 추천",
    badgeType: "recommended",
    tags: ["Google Flow", "Veo 3.1", "최대 8초"],
    iconType: "google"
  },
  {
    id: "flow_veo_quality",
    name: "Google Veo 3.1 Quality (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "영화 같은 극적인 시네마틱 화질과 정교한 디테일 보존을 제공하는 프리미엄 Veo 모델",
    badge: "Flow 시네마틱",
    badgeType: "new",
    tags: ["Google Flow", "Veo Quality", "8초"],
    iconType: "google"
  },
  {
    id: "flow_veo_lite",
    name: "Google Veo 3.1 Lite (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "가장 저렴한 크레딧 소모로 부담 없이 빠르게 클립을 뽑아낼 수 있는 실속형 Veo 모델",
    badge: "Flow 최고가성비",
    badgeType: "value",
    tags: ["Google Flow", "Veo Lite", "빠른 생성"],
    iconType: "google"
  },
  {
    id: "flow_omni_flash",
    name: "Gemini Omni Flash (Flow)",
    provider: "Google Flow",
    platform: "flow",
    description: "Google Flow 공식 Omni 모델. 고속 영상 생성 및 최대 10초까지 생성 가능한 롱 클립 모델",
    badge: "Flow 롱클립",
    badgeType: "recommended",
    tags: ["Google Flow", "단일 샷", "최대 10초"],
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
  const models = mode === "image" ? IMAGE_MODELS : VIDEO_MODELS;

  // 현재 선택된 모델에 맞게 힉스필드 vs Flow CLI 탭 자동 설정
  const initialProvider: "higgsfield" | "flow" = (() => {
    const cur = models.find((m) => m.id === selectedModelId);
    if (cur) return cur.platform;
    return selectedModelId.startsWith("flow_") || selectedModelId.endsWith("_flow") ? "flow" : "higgsfield";
  })();

  const [providerFilter, setProviderFilter] = useState<"higgsfield" | "flow">(initialProvider);
  const [tempSelectedId, setTempSelectedId] = useState<string>(selectedModelId);

  const selectedModel = models.find((m) => m.id === tempSelectedId) ?? models[0];

  const higgsfieldCount = models.filter((m) => m.platform === "higgsfield").length;
  const flowCount = models.filter((m) => m.platform === "flow").length;

  const filtered = models.filter((m) => {
    // 1. 플랫폼 필터 (전체 제거, 오직 힉스필드 또는 Flow CLI)
    if (m.platform !== providerFilter) {
      return false;
    }

    // 2. 검색어 필터
    if (!searchTerm.trim()) {
      return true;
    }
    const q = searchTerm.toLowerCase();
    return (
      m.name.toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      m.provider.toLowerCase().includes(q) ||
      Boolean(m.badge && m.badge.toLowerCase().includes(q))
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

          {/* 검색창 */}
          <div
            style={{
              position: "relative",
              display: "flex",
              alignItems: "center",
              background: "#0d1117",
              borderRadius: "10px",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              padding: "0 0.75rem",
              marginBottom: "0.6rem"
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

          {/* 공급자 필터 탭 (전체 제거 ➔ 힉스필드 vs Flow CLI 2개 항목으로 명확 분리) */}
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button
              type="button"
              onClick={() => setProviderFilter("higgsfield")}
              style={{
                flex: 1,
                padding: "0.45rem 0.75rem",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: providerFilter === "higgsfield" ? "bold" : "normal",
                background: providerFilter === "higgsfield"
                  ? "linear-gradient(135deg, rgba(234, 179, 8, 0.25) 0%, rgba(168, 85, 247, 0.2) 100%)"
                  : "rgba(255, 255, 255, 0.05)",
                color: providerFilter === "higgsfield" ? "#facc15" : "#94a3b8",
                border: providerFilter === "higgsfield" ? "1.5px solid #eab308" : "1px solid rgba(255, 255, 255, 0.1)",
                cursor: "pointer",
                transition: "all 0.15s ease",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px"
              }}
            >
              <span>✨</span>
              <span>힉스필드 ({higgsfieldCount})</span>
            </button>
            <button
              type="button"
              onClick={() => setProviderFilter("flow")}
              style={{
                flex: 1,
                padding: "0.45rem 0.75rem",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: providerFilter === "flow" ? "bold" : "normal",
                background: providerFilter === "flow"
                  ? "linear-gradient(135deg, rgba(59, 130, 246, 0.3) 0%, rgba(56, 189, 248, 0.2) 100%)"
                  : "rgba(255, 255, 255, 0.05)",
                color: providerFilter === "flow" ? "#38bdf8" : "#94a3b8",
                border: providerFilter === "flow" ? "1.5px solid #38bdf8" : "1px solid rgba(255, 255, 255, 0.1)",
                cursor: "pointer",
                transition: "all 0.15s ease",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "6px"
              }}
            >
              <span>🌐</span>
              <span>Flow CLI ({flowCount})</span>
            </button>
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
