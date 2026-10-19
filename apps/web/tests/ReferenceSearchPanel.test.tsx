import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReferenceSearchPanel } from "../src/components/ReferenceSearchPanel";
import type { ReferenceCandidate } from "../src/types";

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

describe("ReferenceSearchPanel", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-13T12:00:00+09:00"));
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  it("submits search filters and selects a reference", async () => {
    const onSearch = vi.fn();
    const onSelect = vi.fn();

    render(
      <ReferenceSearchPanel
        candidates={[candidate]}
        isBusy={false}
        onAddDirect={vi.fn()}
        onSearch={onSearch}
        onSelect={onSelect}
        selectedReference={null}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /최근 1개월/i }));
    expect(screen.getByLabelText(/Uploaded after/i)).toHaveValue("2026-09-13");
    expect(screen.getByLabelText(/Uploaded before/i)).toHaveValue("2026-10-13");
    expect(screen.getByRole("combobox", { name: /Video length/i })).toHaveValue("under_180");
    expect(screen.getByRole("img", { name: /테스트 쇼츠 thumbnail/i })).toHaveAttribute(
      "src",
      "https://example.com/thumb.jpg"
    );
    expect(screen.getByRole("link", { name: /Open 테스트 쇼츠 on YouTube/i })).toHaveAttribute(
      "href",
      "https://www.youtube.com/watch?v=abc123DEF45"
    );

    fireEvent.change(screen.getByRole("textbox", { name: /Keyword/i }), { target: { value: "돈" } });
    fireEvent.change(screen.getByRole("combobox", { name: /Video length/i }), { target: { value: "under_120" } });
    fireEvent.click(screen.getByRole("button", { name: /Search references/i }));
    fireEvent.click(screen.getByRole("button", { name: /Select 테스트 쇼츠/i }));

    expect(onSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        keyword: "돈",
        duration_filter: "under_120",
        max_duration_seconds: 120,
        published_after: "2026-09-13",
        published_before: "2026-10-13"
      })
    );
    expect(onSelect).toHaveBeenCalledWith("abc123DEF45");
    expect(screen.getByRole("button", { name: /Select 테스트 쇼츠/i })).toHaveTextContent("Select");
  });

  it("keeps max results inside the YouTube API request limit", () => {
    const onSearch = vi.fn();

    render(
      <ReferenceSearchPanel
        candidates={[]}
        isBusy={false}
        onAddDirect={vi.fn()}
        onSearch={onSearch}
        onSelect={vi.fn()}
        selectedReference={null}
      />
    );

    expect(screen.getByLabelText(/Max results/i)).toHaveAttribute("max", "50");

    fireEvent.change(screen.getByRole("textbox", { name: /Keyword/i }), { target: { value: "과학" } });
    fireEvent.change(screen.getByLabelText(/Max results/i), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: /Search references/i }));

    expect(onSearch).toHaveBeenCalledWith(expect.objectContaining({ max_results: 50 }));
  });

  it("adds a direct link and renders selected reference", async () => {
    const onAddDirect = vi.fn();

    render(
      <ReferenceSearchPanel
        candidates={[]}
        isBusy={false}
        onAddDirect={onAddDirect}
        onSearch={vi.fn()}
        onSelect={vi.fn()}
        selectedReference={candidate}
      />
    );

    fireEvent.change(screen.getByRole("textbox", { name: /Direct YouTube URL/i }), {
      target: { value: "https://www.youtube.com/shorts/abc123DEF45" }
    });
    fireEvent.click(screen.getByRole("button", { name: /Add direct link/i }));

    expect(onAddDirect).toHaveBeenCalledWith("https://www.youtube.com/shorts/abc123DEF45");
    expect(screen.getByText("테스트 쇼츠")).toBeInTheDocument();
  });
});
