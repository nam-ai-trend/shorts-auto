import { useState } from "react";
import type { FormEvent } from "react";

import type { ScriptCandidate, TtsValidationResult } from "../types";

interface FinalScriptPanelProps {
  readonly finalScript: string | null;
  readonly isBusy: boolean;
  readonly onFinalize: (feedback: string) => void;
  readonly onUpdateFinalScript?: (updatedScript: string) => Promise<void> | void;
  readonly selectedCandidate: ScriptCandidate | null;
  readonly ttsValidation: TtsValidationResult | null;
}

export function FinalScriptPanel({
  finalScript,
  isBusy,
  onFinalize,
  onUpdateFinalScript,
  selectedCandidate,
  ttsValidation
}: FinalScriptPanelProps) {
  const [feedback, setFeedback] = useState("");
  const [refineFeedback, setRefineFeedback] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [editedScript, setEditedScript] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isBusy && !isSaving && selectedCandidate) {
      onFinalize(feedback.trim());
    }
  }

  function handleRefineSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isBusy && !isSaving && selectedCandidate && refineFeedback.trim()) {
      onFinalize(refineFeedback.trim());
      setRefineFeedback("");
    }
  }

  function handleStartEditing() {
    setEditedScript(finalScript ?? "");
    setIsEditing(true);
  }

  function handleCancelEditing() {
    setIsEditing(false);
    setEditedScript("");
  }

  async function handleSaveEditing() {
    if (!onUpdateFinalScript || !editedScript.trim()) {
      return;
    }
    setIsSaving(true);
    try {
      await onUpdateFinalScript(editedScript.trim());
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="panel final-script-panel" aria-labelledby="final-script-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Script</p>
          <h2 id="final-script-title">Final TTS script</h2>
        </div>
      </div>

      {selectedCandidate ? (
        <div className="selected-script-summary">
          <p className="eyebrow">Selected candidate</p>
          <h3>{selectedCandidate.title}</h3>
          <p>{selectedCandidate.hook}</p>
        </div>
      ) : (
        <p className="empty-state">Select one candidate before finalizing a script.</p>
      )}

      <form className="final-script-form" onSubmit={handleSubmit}>
        <label>
          <span>Feedback (초기 확정 피드백)</span>
          <textarea
            name="feedback"
            onChange={(event) => setFeedback(event.target.value)}
            placeholder="선택 사항: 더 강하게, 더 짧게, 특정 주제/어조로 조정 등"
            value={feedback}
          />
        </label>
        <button className="primary-button" disabled={isBusy || isSaving || !selectedCandidate} type="submit">
          {isBusy ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span className="spinner-icon">⏳</span> {finalScript ? "AI 대본 다시 확정 진행 중..." : "6. 최종 대본 확정 진행 중..."}
            </span>
          ) : (
            finalScript ? "6. AI로 최종 대본 다시 확정하기 (Finalize Script with AI)" : "6. 최종 대본 확정 (Finalize Script)"
          )}
        </button>
      </form>

      {finalScript && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "0.5rem",
            padding: "8px 12px",
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: "6px",
          }}
        >
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span style={{ fontSize: "13px", fontWeight: "bold", color: "#10b981", display: "inline-flex", alignItems: "center", gap: "4px" }}>
              ✅ 최종 대본 확정 상태
            </span>
            {isEditing ? (
              <span style={{ fontSize: "12px", fontWeight: "bold", background: "#fef3c7", color: "#92400e", padding: "2px 8px", borderRadius: "4px" }}>
                ✏️ 직접 수정 모드
              </span>
            ) : (
              onUpdateFinalScript && (
                <button
                  type="button"
                  className="secondary-button"
                  onClick={handleStartEditing}
                  disabled={isBusy || isSaving}
                  style={{ fontSize: "12px", padding: "3px 10px", display: "inline-flex", alignItems: "center", gap: "4px" }}
                >
                  ✏️ 대본 직접 수정하기
                </button>
              )
            )}
          </div>
          <span style={{ fontSize: "12px", fontWeight: "bold", background: "#dbeafe", color: "#1e40af", padding: "3px 10px", borderRadius: "4px" }}>
            ⏱️ 글자 수: {(isEditing ? editedScript : finalScript).length}자 (예상 낭독 시간: 약 {Math.round((isEditing ? editedScript : finalScript).length / 9.5)}초)
          </span>
        </div>
      )}

      {isEditing ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "1rem" }}>
          <textarea
            aria-label="Direct Script Edit"
            value={editedScript}
            onChange={(e) => setEditedScript(e.target.value)}
            rows={12}
            style={{
              width: "100%",
              padding: "12px",
              borderRadius: "8px",
              background: "#090d16",
              border: "1.5px solid #38bdf8",
              color: "#f8fafc",
              fontSize: "14px",
              lineHeight: "1.6",
              fontFamily: "monospace",
              resize: "vertical",
              boxSizing: "border-box",
            }}
            placeholder="최종 대본 내용을 직접 수정하세요..."
          />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
            <button
              type="button"
              className="secondary-button"
              onClick={handleCancelEditing}
              disabled={isSaving}
              style={{ padding: "6px 14px", fontSize: "13px" }}
            >
              취소
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={handleSaveEditing}
              disabled={isSaving || !editedScript.trim()}
              style={{
                background: "linear-gradient(90deg, #10b981 0%, #059669 100%)",
                color: "#ffffff",
                fontWeight: "bold",
                padding: "6px 16px",
                fontSize: "13px",
              }}
            >
              {isSaving ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span className="spinner-icon">⏳</span> 수정한 대본 확정 저장 중...
                </span>
              ) : (
                "💾 수정한 대본 그대로 최종 확정"
              )}
            </button>
          </div>
        </div>
      ) : (
        <pre className="script-preview">{finalScript ?? "Final TTS-ready script will appear here."}</pre>
      )}

      {/* ✍️ 최종 대본 아래 실시간 피드백 입력란 & 재확정 컨트롤 */}
      {finalScript && (
        <form
          onSubmit={handleRefineSubmit}
          style={{
            marginTop: "1rem",
            padding: "1.1rem 1.25rem",
            background: "linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%)",
            border: "1.5px solid rgba(56, 189, 248, 0.35)",
            borderRadius: "10px",
            display: "flex",
            flexDirection: "column",
            gap: "10px",
          }}
        >
          <div>
            <strong style={{ fontSize: "14px", color: "#38bdf8", display: "flex", alignItems: "center", gap: "6px" }}>
              ✍️ 최종 대본 수정 피드백 (대본을 보며 직접 수정 요청)
            </strong>
            <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: "#94a3b8" }}>
              위 대본을 읽고 고치고 싶은 문장, 수치 정정, 팩트체크 수정 요청, 톤앤매너 등을 적어주세요.
            </p>
          </div>
          <textarea
            rows={3}
            value={refineFeedback}
            onChange={(e) => setRefineFeedback(e.target.value)}
            placeholder="예: 63빌딩 비유 빼고 실제 수치로 바꿔줘 / 마지막 문장을 질문형으로 도파민 터지게 바꿔줘"
            style={{
              width: "100%",
              padding: "10px",
              borderRadius: "6px",
              background: "#0f172a",
              border: "1px solid #334155",
              color: "#f8fafc",
              fontSize: "13px",
              resize: "vertical",
              boxSizing: "border-box",
            }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button
              className="primary-button"
              disabled={isBusy || !selectedCandidate || !refineFeedback.trim()}
              type="submit"
              style={{
                background: "linear-gradient(90deg, #0284c7 0%, #0369a1 100%)",
                fontWeight: "bold",
                padding: "8px 18px",
              }}
            >
              {isBusy ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                  <span className="spinner-icon">⏳</span> 대본 수정 및 재확정 진행 중...
                </span>
              ) : (
                "🔄 피드백 반영하여 최종 대본 다시 다듬기"
              )}
            </button>
          </div>
        </form>
      )}

      {ttsValidation ? (
        <div className={ttsValidation.is_valid ? "validation validation--ok" : "validation validation--warning"}>
          <strong>{ttsValidation.is_valid ? "TTS rules passed" : "TTS rules need review"}</strong>
          {ttsValidation.issues.length > 0 ? (
            <ul>
              {ttsValidation.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
