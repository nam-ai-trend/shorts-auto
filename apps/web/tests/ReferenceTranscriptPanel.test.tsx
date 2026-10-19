import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReferenceTranscriptPanel } from "../src/components/ReferenceTranscriptPanel";

describe("ReferenceTranscriptPanel", () => {
  it("renders audio status and triggers extract audio and STT", async () => {
    const user = userEvent.setup();
    const onExtractAudio = vi.fn();
    const onRunStt = vi.fn();

    const { rerender } = render(
      <ReferenceTranscriptPanel
        hasAudio={false}
        hasSelectedReference={true}
        isAudioBusy={false}
        isSttBusy={false}
        onExtractAudio={onExtractAudio}
        onRunStt={onRunStt}
        referenceScript={null}
      />
    );

    expect(screen.getByText("Audio required")).toBeInTheDocument();
    const sttButton = screen.getByRole("button", { name: /Run STT/i });
    expect(sttButton).toBeDisabled();

    const extractButton = screen.getByRole("button", { name: /Extract audio/i });
    await user.click(extractButton);
    expect(onExtractAudio).toHaveBeenCalled();

    // Rerender after audio is ready
    rerender(
      <ReferenceTranscriptPanel
        hasAudio={true}
        hasSelectedReference={true}
        isAudioBusy={false}
        isSttBusy={false}
        onExtractAudio={onExtractAudio}
        onRunStt={onRunStt}
        referenceScript="첫 문장입니다."
      />
    );

    expect(screen.getByText("✓ Audio ready")).toBeInTheDocument();
    expect(screen.getByText("첫 문장입니다.")).toBeInTheDocument();
    expect(sttButton).not.toBeDisabled();

    await user.click(sttButton);
    expect(onRunStt).toHaveBeenCalled();
  });
});
