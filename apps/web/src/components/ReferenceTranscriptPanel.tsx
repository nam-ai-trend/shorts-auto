interface ReferenceTranscriptPanelProps {
  readonly referenceScript: string | null;
  readonly hasSelectedReference: boolean;
  readonly hasAudio: boolean;
  readonly isAudioBusy: boolean;
  readonly isSttBusy: boolean;
  readonly onExtractAudio: () => void;
  readonly onRunStt: () => void;
}

export function ReferenceTranscriptPanel({
  referenceScript,
  hasSelectedReference,
  hasAudio,
  isAudioBusy,
  isSttBusy,
  onExtractAudio,
  onRunStt
}: ReferenceTranscriptPanelProps) {
  return (
    <section className="panel" aria-labelledby="transcript-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Audio & STT</p>
          <h2 id="transcript-title">Reference script</h2>
        </div>
        {hasAudio ? (
          <span className="state-pill state-pill--succeeded">✓ Audio ready</span>
        ) : (
          <span className="state-pill state-pill--waiting">Audio required</span>
        )}
      </div>

      <div className="transcript-actions">
        <button
          className={hasAudio ? "secondary-button" : "primary-button"}
          disabled={isAudioBusy || isSttBusy || !hasSelectedReference}
          onClick={onExtractAudio}
          type="button"
        >
          {isAudioBusy ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span className="spinner-icon">⏳</span> 2. 음성 추출 진행 중...
            </span>
          ) : (
            "2. Extract Audio"
          )}
        </button>
        <button
          className={hasAudio ? "primary-button" : "secondary-button"}
          disabled={isAudioBusy || isSttBusy || !hasAudio}
          onClick={onRunStt}
          title={!hasAudio ? "2. Extract audio를 먼저 실행해주세요" : undefined}
          type="button"
        >
          {isSttBusy ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
              <span className="spinner-icon">⏳</span> 3. STT 변환 진행 중...
            </span>
          ) : (
            "3. Run STT"
          )}
        </button>
      </div>
      <pre className="script-preview">{referenceScript ?? "Reference script will appear here after STT."}</pre>
    </section>
  );
}
