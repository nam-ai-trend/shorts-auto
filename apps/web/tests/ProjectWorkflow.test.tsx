import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ProjectWorkflow } from "../src/components/ProjectWorkflow";
import type { StepStatus } from "../src/types";

const stepStatuses: readonly StepStatus[] = [
  { name: "Reference", state: "succeeded", message: "Reference selected" },
  { name: "STT", state: "succeeded", message: "Transcript ready" },
  { name: "Analysis", state: "running", message: "Finding hooks" },
  { name: "Candidates", state: "waiting", message: "" },
  { name: "Script", state: "waiting", message: "" },
  { name: "Production", state: "waiting", message: "" },
  { name: "Render", state: "waiting", message: "" }
];

describe("ProjectWorkflow", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders all seven workflow steps and marks the current step", () => {
    render(<ProjectWorkflow currentStep="Analysis" stepStatuses={stepStatuses} />);

    for (const step of [
      "Reference",
      "Extract Audio",
      "STT",
      "Analysis",
      "Candidates",
      "Script",
      "Production",
      "Render"
    ]) {
      expect(screen.getByText(step)).toBeInTheDocument();
    }

    expect(screen.getByText("Analysis")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("Analysis")).toHaveClass("active");
  });

  it("renders persisted state and message for each workflow step", () => {
    render(<ProjectWorkflow currentStep="Analysis" stepStatuses={stepStatuses} />);

    expect(screen.getAllByText("Succeeded")).toHaveLength(2);
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("Reference selected")).toBeInTheDocument();
    expect(screen.getByText("Finding hooks")).toBeInTheDocument();
  });
});
