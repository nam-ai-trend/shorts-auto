import { FormEvent, useState } from "react";

import type { DurationFilter, ReferenceCandidate, ReferenceSearchPayload } from "../types";

interface ReferenceSearchPanelProps {
  readonly candidates: readonly ReferenceCandidate[];
  readonly selectedReference: ReferenceCandidate | null;
  readonly isBusy: boolean;
  readonly onSearch: (payload: ReferenceSearchPayload) => void;
  readonly onAddDirect: (url: string) => void;
  readonly onSelect: (videoId: string) => void;
}

const DURATION_OPTIONS: readonly {
  value: DurationFilter;
  label: string;
  maxDurationSeconds: number;
}[] = [
  { value: "under_60", label: "60초 이하", maxDurationSeconds: 60 },
  { value: "under_120", label: "2분 이하", maxDurationSeconds: 120 },
  { value: "under_180", label: "3분 이하", maxDurationSeconds: 180 },
  { value: "under_300", label: "5분 이하", maxDurationSeconds: 300 },
  { value: "over_300", label: "5분 초과", maxDurationSeconds: 300 },
  { value: "all", label: "ALL", maxDurationSeconds: 600 }
];

function formatDateInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addMonthsClamped(date: Date, months: number): Date {
  const target = new Date(date);
  const originalDay = target.getDate();
  target.setDate(1);
  target.setMonth(target.getMonth() + months);
  const lastDayOfTargetMonth = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  target.setDate(Math.min(originalDay, lastDayOfTargetMonth));
  return target;
}

function getDefaultDateRange() {
  const today = new Date();
  return {
    publishedAfter: formatDateInput(addMonthsClamped(today, -1)),
    publishedBefore: formatDateInput(today)
  };
}

function formatInteger(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return new Intl.NumberFormat("ko-KR").format(value);
}

function formatRatio(value: number | null): string {
  if (value === null) {
    return "-";
  }
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function clampInteger(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, Math.trunc(value)));
}

export function ReferenceSearchPanel({
  candidates,
  isBusy,
  onAddDirect,
  onSearch,
  onSelect,
  selectedReference
}: ReferenceSearchPanelProps) {
  const [defaultDateRange] = useState(getDefaultDateRange);
  const [channelQuery, setChannelQuery] = useState("");
  const [keyword, setKeyword] = useState("");
  const [directUrl, setDirectUrl] = useState("");
  const [isAllTime, setIsAllTime] = useState(true);
  const [publishedAfter, setPublishedAfter] = useState(defaultDateRange.publishedAfter);
  const [publishedBefore, setPublishedBefore] = useState(defaultDateRange.publishedBefore);
  const [durationFilter, setDurationFilter] = useState<DurationFilter>("under_180");
  const [minimumViews, setMinimumViews] = useState(0);
  const [maximumSubscribers, setMaximumSubscribers] = useState("");
  const [maxResults, setMaxResults] = useState(25);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedKeyword = keyword.trim();
    const trimmedChannelQuery = channelQuery.trim();
    if ((!trimmedKeyword && !trimmedChannelQuery) || isBusy) {
      return;
    }
    const selectedDuration = DURATION_OPTIONS.find((option) => option.value === durationFilter) ?? DURATION_OPTIONS[0];
    onSearch({
      keyword: trimmedKeyword || undefined,
      channel_query: trimmedChannelQuery || undefined,
      published_after: isAllTime ? undefined : (publishedAfter || undefined),
      published_before: isAllTime ? undefined : (publishedBefore || undefined),
      duration_filter: durationFilter,
      max_duration_seconds: selectedDuration.maxDurationSeconds,
      minimum_views: Math.max(0, Math.trunc(minimumViews || 0)),
      maximum_subscribers: maximumSubscribers ? Number(maximumSubscribers) : undefined,
      max_results: clampInteger(maxResults || 25, 1, 50)
    });
  }

  function submitDirect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedUrl = directUrl.trim();
    if (!trimmedUrl || isBusy) {
      return;
    }
    onAddDirect(trimmedUrl);
    setDirectUrl("");
  }

  return (
    <section className="panel reference-panel" aria-labelledby="reference-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Reference</p>
          <h2 id="reference-title">Search and link</h2>
        </div>
      </div>

      <form className="reference-form" onSubmit={submitSearch}>
        <div style={{ gridColumn: "1 / -1", display: "flex", gap: "8px", alignItems: "center", marginBottom: "6px" }}>
          <span style={{ fontSize: "12px", fontWeight: "bold", color: "#1e293b" }}>📅 검색 기간:</span>
          <button
            type="button"
            className={isAllTime ? "primary-button" : "secondary-button"}
            onClick={() => setIsAllTime(true)}
            style={{ width: "auto", padding: "4px 12px", fontSize: "12px" }}
          >
            🌐 전체 기간 (추천: 채널 전체 영상 검색)
          </button>
          <button
            type="button"
            className={!isAllTime ? "primary-button" : "secondary-button"}
            onClick={() => setIsAllTime(false)}
            style={{ width: "auto", padding: "4px 12px", fontSize: "12px" }}
          >
            🗓️ 최근 1개월/직접 지정
          </button>
        </div>

        <label>
          <span>Channel</span>
          <input
            name="channelQuery"
            onChange={(event) => setChannelQuery(event.target.value)}
            placeholder="예: @채널핸들 또는 채널명/URL (선택)"
            type="text"
            value={channelQuery}
          />
        </label>
        <label>
          <span>Keyword</span>
          <input
            name="keyword"
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="예: 돈 버는 습관 (선택)"
            type="text"
            value={keyword}
          />
        </label>
        {!isAllTime && (
          <>
            <label>
              <span>Uploaded after</span>
              <input
                name="uploadedAfter"
                onChange={(event) => setPublishedAfter(event.target.value)}
                type="date"
                value={publishedAfter}
              />
            </label>
            <label>
              <span>Uploaded before</span>
              <input
                name="uploadedBefore"
                onChange={(event) => setPublishedBefore(event.target.value)}
                type="date"
                value={publishedBefore}
              />
            </label>
          </>
        )}
        <label>
          <span>Video length</span>
          <select
            name="durationFilter"
            onChange={(event) => setDurationFilter(event.target.value as DurationFilter)}
            value={durationFilter}
          >
            {DURATION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Minimum views</span>
          <input
            min="0"
            name="minimumViews"
            onChange={(event) => setMinimumViews(Number(event.target.value))}
            type="number"
            value={minimumViews}
          />
        </label>
        <label>
          <span>Maximum subscribers</span>
          <input
            min="0"
            name="maximumSubscribers"
            onChange={(event) => setMaximumSubscribers(event.target.value)}
            placeholder="optional"
            type="number"
            value={maximumSubscribers}
          />
        </label>
        <label>
          <span>Max results</span>
          <input
            max="50"
            min="1"
            name="maxResults"
            onChange={(event) => setMaxResults(clampInteger(Number(event.target.value), 1, 50))}
            type="number"
            value={maxResults}
          />
        </label>
        <button
          className="primary-button"
          disabled={isBusy || (keyword.trim().length === 0 && channelQuery.trim().length === 0)}
          type="submit"
        >
          Search references
        </button>
      </form>

      <form className="direct-form" onSubmit={submitDirect}>
        <label>
          <span>Direct YouTube URL</span>
          <input
            name="youtubeUrl"
            onChange={(event) => setDirectUrl(event.target.value)}
            placeholder="https://www.youtube.com/shorts/..."
            type="url"
            value={directUrl}
          />
        </label>
        <button className="secondary-button" disabled={isBusy || directUrl.trim().length === 0} type="submit">
          {isBusy ? "⏳ 분석 및 선택 중..." : "🔗 Add direct link & Select"}
        </button>
      </form>

      <div className="reference-status-grid">
        <section className="reference-selected" aria-labelledby="selected-reference-title">
          <p className="eyebrow" id="selected-reference-title">
            Selected reference
          </p>
          {selectedReference ? (
            <div
              className="selected-reference-card"
              style={{
                display: "flex",
                gap: "16px",
                alignItems: "flex-start",
                padding: "14px",
                background: "#f8fafc",
                borderRadius: "10px",
                border: "1px solid #cbd5e1"
              }}
            >
              {selectedReference.thumbnail_url && (
                <div style={{ position: "relative", width: "110px", flexShrink: 0, borderRadius: "6px", overflow: "hidden" }}>
                  <img
                    alt={selectedReference.title}
                    src={selectedReference.thumbnail_url}
                    style={{ width: "100%", height: "auto", display: "block" }}
                  />
                  <span className="duration-badge" style={{ position: "absolute", bottom: "4px", right: "4px" }}>
                    {formatDuration(selectedReference.duration_seconds)}
                  </span>
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: "6px", minWidth: 0, flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "11px", fontWeight: "bold", background: "#dcfce7", color: "#166534", padding: "2px 8px", borderRadius: "4px" }}>
                    ✅ 선택 완료
                  </span>
                  {selectedReference.source_type === "direct" && (
                    <span style={{ fontSize: "11px", fontWeight: "bold", background: "#fef3c7", color: "#92400e", padding: "2px 8px", borderRadius: "4px" }}>
                      🔗 Direct Link
                    </span>
                  )}
                </div>
                <strong style={{ fontSize: "14px", lineHeight: 1.35, color: "#0f172a", wordBreak: "keep-all" }}>
                  {selectedReference.title}
                </strong>
                <div style={{ fontSize: "12px", color: "#64748b", display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  <span>📺 <strong>{selectedReference.channel_name}</strong></span>
                  <span>👀 조회수 <strong>{formatInteger(selectedReference.view_count)}회</strong></span>
                  <span>👥 구독자 <strong>{formatInteger(selectedReference.subscriber_count)}명</strong></span>
                  {selectedReference.vs_ratio !== null && (
                    <span style={{ color: "#2563eb", fontWeight: "bold" }}>
                      🔥 VS: {formatRatio(selectedReference.vs_ratio)}배
                    </span>
                  )}
                </div>
                <div>
                  <a
                    href={selectedReference.url}
                    rel="noreferrer"
                    target="_blank"
                    style={{ fontSize: "12px", color: "#2563eb", textDecoration: "underline" }}
                  >
                    YouTube에서 영상 보기 ↗
                  </a>
                </div>
              </div>
            </div>
          ) : (
            <p className="empty-state">No reference selected yet.</p>
          )}
        </section>

        <table className="reference-table" aria-label="Reference candidates">
          <thead>
            <tr>
              <th>Video</th>
              <th>Views</th>
              <th>Subscribers</th>
              <th>Ratio</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {candidates.length > 0 ? (
              candidates.map((candidate) => (
                <tr key={candidate.video_id}>
                  <td>
                    <div className="reference-video-cell">
                      <a
                        aria-label={`Open ${candidate.title} on YouTube`}
                        className="reference-thumbnail"
                        href={candidate.url}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <img alt={`${candidate.title} thumbnail`} src={candidate.thumbnail_url} />
                        <span className="duration-badge">{formatDuration(candidate.duration_seconds)}</span>
                      </a>
                      <div className="reference-video-copy">
                        <a className="reference-title-link" href={candidate.url} rel="noreferrer" target="_blank">
                          {candidate.title}
                        </a>
                        <small>{candidate.channel_name}</small>
                      </div>
                    </div>
                  </td>
                  <td>{formatInteger(candidate.view_count)}</td>
                  <td>{formatInteger(candidate.subscriber_count)}</td>
                  <td>{formatRatio(candidate.vs_ratio)}</td>
                  <td>
                    <button
                      className="table-action"
                      disabled={isBusy || selectedReference?.video_id === candidate.video_id}
                      onClick={() => onSelect(candidate.video_id)}
                      type="button"
                      aria-label={`Select ${candidate.title}`}
                    >
                      Select
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5}>Search results will appear here.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
