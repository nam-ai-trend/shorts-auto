import { useState } from "react";
import type { ScriptCandidate } from "../types";

interface CandidateDraftsPanelProps {
  readonly candidates: readonly ScriptCandidate[];
  readonly isBusy: boolean;
  readonly onGenerate: (feedback: string) => void;
  readonly onSelect: (candidateId: string) => void;
  readonly selectedCandidateId: string | null;
  readonly videoTitle?: string;
  readonly onTitleChange?: (title: string) => void;
}

function formatCandidateType(value: ScriptCandidate["candidate_type"]): string {
  switch (value) {
    case "draft_a":
      return "Draft A (상식 충돌 / 텐션형)";
    case "draft_b":
      return "Draft B (스토리텔링 / 몰입형)";
    case "same_topic":
      return "Same Topic (동일 주제 리메이크)";
    case "different_topic":
      return "Different Topic (새로운 주제 변주)";
    default:
      return value;
  }
}

export function CandidateDraftsPanel({
  candidates,
  isBusy,
  onGenerate,
  onSelect,
  selectedCandidateId,
  videoTitle,
  onTitleChange,
}: CandidateDraftsPanelProps) {
  const [feedback, setFeedback] = useState("");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  function copyText(key: string, text: string) {
    if (!text) return;
    void navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => {
      setCopiedKey((curr) => (curr === key ? null : curr));
    }, 1500);
  }

  return (
    <section className="panel candidate-panel" aria-labelledby="candidates-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Candidates & Drafts</p>
          <h2 id="candidates-title">Script drafts</h2>
        </div>
        <button
          className="secondary-button"
          disabled={isBusy}
          onClick={() => onGenerate(feedback)}
          type="button"
          aria-label="Generate candidates"
        >
          {isBusy ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span className="spinner-icon">⏳</span> 5. 대본 초안 생성 진행 중...
            </span>
          ) : (
            "5. 대본 초안 2개 생성"
          )}
        </button>
      </div>

      <div className="feedback-block">
        <label className="field-label" htmlFor="draft-generation-feedback">
          <strong>기획 방향 및 피드백 (선택 또는 자유 입력)</strong>
        </label>
        <p className="muted" style={{ margin: "0.25rem 0 0.5rem" }}>
          💡 분석 리포트의 5가지 추천 주제 중 원하는 번호를 고르거나, <strong>팩트체크할 주제, 강조할 구체적 숫자, 체감 비유(올림픽 수영장 N개 등)</strong>를 자유롭게 적어주세요.
        </p>
        <textarea
          id="draft-generation-feedback"
          className="feedback-input"
          disabled={isBusy}
          onChange={(event) => setFeedback(event.target.value)}
          placeholder="예: 1번 추천 주제(개미가 하루 동안 옮기는 무게)로 해줘. 실제 과학 팩트와 충격적인 환산 수치(63빌딩 무게 등)를 넣어서 도파민 터지게 써줘."
          rows={3}
          value={feedback}
          style={{ width: "100%", minHeight: "92px", boxSizing: "border-box" }}
        />
      </div>

      {/* 🎬 쇼츠 오프닝 제목 입력란 (피드백 바로 아래 배치) */}
      <div className="feedback-block" style={{ marginTop: "1rem" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <label className="field-label" htmlFor="draft-video-title">
            <strong>🎬 쇼츠 오프닝 제목 (0~2초 화면 상단 타이틀로 자동 렌더링)</strong>
          </label>
          <span style={{ fontSize: "11px", color: "#0284c7", background: "rgba(56, 189, 248, 0.15)", padding: "2px 8px", borderRadius: "4px", fontWeight: "600" }}>
            줄바꿈(Enter) 지원
          </span>
        </div>
        <p className="muted" style={{ margin: "0.25rem 0 0.5rem" }}>
          💡 여기서 정한 제목은 <strong>[전체 씬 영상 일괄 생성 & 렌더링]</strong> 및 최종 렌더링 시 영상 시작 <strong>0~2초 동안 화면 상단에 큼직하게 노출되는 오프닝 타이틀</strong>로 자동 반영됩니다.
        </p>
        <textarea
          id="draft-video-title"
          className="feedback-input"
          disabled={isBusy}
          onChange={(event) => onTitleChange?.(event.target.value)}
          placeholder={`예:\n빨대는 10m가 한계인데,\n나무는 어떻게 100m까지?`}
          rows={2}
          value={videoTitle ?? ""}
          style={{
            width: "100%",
            minHeight: "68px",
            boxSizing: "border-box",
            fontWeight: "bold",
            fontSize: "14px",
            lineHeight: "1.4",
            border: "1.5px solid #38bdf8",
            background: "rgba(240, 249, 255, 0.6)"
          }}
        />
      </div>

      {candidates.length === 0 ? (
        <p className="empty-state">
          분석 리포트의 5가지 추천 주제를 확인한 뒤, 위 피드백란을 작성하고 [대본 초안 2개 생성] 버튼을 눌러주세요.
        </p>
      ) : (
        <div className="candidate-list">
          {candidates.map((candidate) => {
            const isSelected = selectedCandidateId === candidate.candidate_id;
            return (
              <article
                className={`candidate-card ${isSelected ? "candidate-card--selected" : ""}`}
                key={candidate.candidate_id}
              >
                <div className="candidate-card-header">
                  <span className="state-pill">{formatCandidateType(candidate.candidate_type)}</span>
                  <button
                    className="table-action"
                    disabled={isBusy || isSelected}
                    onClick={() => onSelect(candidate.candidate_id)}
                    type="button"
                    aria-label={`Select ${candidate.title}`}
                  >
                    {isSelected ? "✓ 선택됨" : `이 초안 선택하기 (${candidate.candidate_id.toUpperCase()})`}
                  </button>
                </div>
                <h3>{candidate.title}</h3>
                {/* 🎯 후킹 제목 추천 3선 */}
                {candidate.title_options && candidate.title_options.length > 0 && (
                  <div style={{ margin: "0.6rem 0", padding: "10px 12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <strong style={{ fontSize: "13px", color: "#1e293b" }}>🎯 후킹형 제목 3선:</strong>
                      <span style={{ fontSize: "11px", color: "#64748b" }}>상황에 맞게 골라보세요</span>
                    </div>
                    <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", color: "#334155", display: "flex", flexDirection: "column", gap: "6px" }}>
                      {candidate.title_options.map((titleOpt, idx) => (
                        <li key={idx} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontWeight: idx === 0 ? 600 : 400 }}>{titleOpt}</span>
                          <button
                            type="button"
                            onClick={() => copyText(`${candidate.candidate_id}-title-${idx}`, titleOpt)}
                            style={{ fontSize: "11px", padding: "2px 8px", cursor: "pointer", borderRadius: "4px", border: "1px solid #cbd5e1", background: "#ffffff" }}
                          >
                            {copiedKey === `${candidate.candidate_id}-title-${idx}` ? "✓ 복사됨" : "복사"}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                <p className="candidate-hook">
                  <strong>🎣 후킹:</strong> {candidate.hook}
                </p>
                <dl className="candidate-meta">
                  <div>
                    <dt>타겟 시청자</dt>
                    <dd>{candidate.target_viewer}</dd>
                  </div>
                  <div>
                    <dt>핵심 호기심 질문</dt>
                    <dd>{candidate.main_curiosity_question}</dd>
                  </div>
                </dl>
                <div style={{ margin: "0.5rem 0" }}>
                  <p><strong>💡 왜 터질 수밖에 없는가:</strong> {candidate.why_it_can_work}</p>
                  <p><strong>🔄 구성 흐름:</strong> {candidate.structure_summary}</p>
                  <p><strong>📐 차용한 공식/구조:</strong> {candidate.borrowed_reference_structure}</p>
                </div>
                <div style={{ marginTop: "0.75rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem" }}>
                    <p style={{ fontWeight: 600, margin: 0 }}>📜 대본 초안 (Draft Script):</p>
                    <span style={{ fontSize: "11px", fontWeight: "bold", background: "#e2e8f0", color: "#334155", padding: "2px 8px", borderRadius: "4px" }}>
                      📊 {candidate.draft_script.length}자 (약 {Math.round(candidate.draft_script.length / 9.5)}초 분량)
                    </span>
                  </div>
                  <pre className="script-preview">{candidate.draft_script}</pre>
                </div>

                {/* 📝 유튜브 설명란 문구, 해시태그, 키워드 */}
                {(candidate.description || candidate.tags || candidate.keywords) && (
                  <div style={{ marginTop: "0.75rem", padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #cbd5e1", display: "flex", flexDirection: "column", gap: "10px" }}>
                    {candidate.description && (
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                          <span style={{ fontSize: "12px", fontWeight: "bold", color: "#1e293b" }}>📝 설명란 문구:</span>
                          <button
                            type="button"
                            onClick={() => copyText(`${candidate.candidate_id}-desc`, candidate.description!)}
                            style={{ fontSize: "11px", padding: "2px 8px", cursor: "pointer", borderRadius: "4px", border: "1px solid #cbd5e1", background: "#ffffff" }}
                          >
                            {copiedKey === `${candidate.candidate_id}-desc` ? "✓ 복사됨" : "📋 설명란 복사"}
                          </button>
                        </div>
                        <p style={{ margin: 0, fontSize: "12px", color: "#334155", lineHeight: 1.45, whiteSpace: "pre-wrap", background: "#ffffff", padding: "8px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                          {candidate.description}
                        </p>
                      </div>
                    )}

                    {candidate.tags && (
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                          <span style={{ fontSize: "12px", fontWeight: "bold", color: "#1e293b" }}>🏷️ 해시태그:</span>
                          <button
                            type="button"
                            onClick={() => copyText(`${candidate.candidate_id}-tags`, candidate.tags!)}
                            style={{ fontSize: "11px", padding: "2px 8px", cursor: "pointer", borderRadius: "4px", border: "1px solid #cbd5e1", background: "#ffffff" }}
                          >
                            {copiedKey === `${candidate.candidate_id}-tags` ? "✓ 복사됨" : "📋 태그 복사"}
                          </button>
                        </div>
                        <p style={{ margin: 0, fontSize: "12px", color: "#0284c7", fontWeight: 600, background: "#ffffff", padding: "6px 8px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                          {candidate.tags}
                        </p>
                      </div>
                    )}

                    {candidate.keywords && (
                      <div>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                          <span style={{ fontSize: "12px", fontWeight: "bold", color: "#1e293b" }}>🔑 키워드:</span>
                          <button
                            type="button"
                            onClick={() => copyText(`${candidate.candidate_id}-keywords`, candidate.keywords!)}
                            style={{ fontSize: "11px", padding: "2px 8px", cursor: "pointer", borderRadius: "4px", border: "1px solid #cbd5e1", background: "#ffffff" }}
                          >
                            {copiedKey === `${candidate.candidate_id}-keywords` ? "✓ 복사됨" : "📋 키워드 복사"}
                          </button>
                        </div>
                        <p style={{ margin: 0, fontSize: "12px", color: "#475569", background: "#ffffff", padding: "6px 8px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                          {candidate.keywords}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
