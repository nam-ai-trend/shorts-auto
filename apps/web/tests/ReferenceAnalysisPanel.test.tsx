import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ReferenceAnalysisPanel } from "../src/components/ReferenceAnalysisPanel";

describe("ReferenceAnalysisPanel", () => {
  it("shows markdown report and triggers analysis", async () => {
    const user = userEvent.setup();
    const onAnalyze = vi.fn();

    render(
      <ReferenceAnalysisPanel
        analysisMarkdown={"# Reference Analysis\n\n## Hook\n멈추게 합니다."}
        isBusy={false}
        onAnalyze={onAnalyze}
      />
    );

    expect(screen.getByText(/Reference Analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/멈추게 합니다/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Analyze reference/i }));
    expect(onAnalyze).toHaveBeenCalled();
  });
});
