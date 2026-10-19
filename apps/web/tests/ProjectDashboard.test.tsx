import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { ProjectDashboard } from "../src/components/ProjectDashboard";

const project = {
  project_id: "261011_2130",
  project_title: "테스트 쇼츠",
  display_name: "261011_테스트 쇼츠",
  created_at: "2026-10-11T21:30:00Z",
  updated_at: "2026-10-11T21:40:00Z",
  current_step: "Analysis",
  step_statuses: [
    { name: "Reference", state: "succeeded", message: "Reference selected" },
    { name: "STT", state: "succeeded", message: "Transcript ready" },
    { name: "Analysis", state: "running", message: "Finding hooks" },
    { name: "Candidates", state: "waiting", message: "" },
    { name: "Script", state: "waiting", message: "" },
    { name: "Production", state: "waiting", message: "" },
    { name: "Render", state: "waiting", message: "" }
  ],
  selected_reference_path: "inputs/reference.mp4",
  selected_candidate_id: null,
  settings_snapshot: {
    default_shorts_duration_seconds: 45,
    bgm_volume: 0.18
  },
  job_history: [
    {
      job_id: "job-1",
      job_type: "analysis",
      label: "Analyze reference",
      provider: "openai",
      command: "analyze reference",
      state: "running",
      created_at: "2026-10-11T21:31:00Z",
      updated_at: "2026-10-11T21:39:00Z",
      started_at: "2026-10-11T21:31:00Z",
      ended_at: null,
      error_message: null,
      input_paths: ["inputs/reference.mp4"],
      output_paths: [],
      logs: [{ timestamp: "2026-10-11T21:39:00Z", message: "Finding hooks" }]
    }
  ],
  generated_files: {
    transcript: "outputs/261011_2130/transcript.json"
  }
} as const;

describe("ProjectDashboard", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders project display names and exposes the new project action", async () => {
    const user = userEvent.setup();
    const events: string[] = [];

    render(
      <ProjectDashboard
        onCreateProject={() => events.push("create")}
        onSelectProject={(selectedProject) => events.push(selectedProject.project_id)}
        projects={[project]}
        selectedProjectId={project.project_id}
      />
    );

    expect(screen.getByRole("heading", { name: "Projects" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /New Project/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /261011_테스트 쇼츠/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /New Project/i }));
    await user.click(screen.getByRole("button", { name: /261011_테스트 쇼츠/i }));

    expect(events).toEqual(["create", "261011_2130"]);
  });

  it("marks the selected project as the current page", () => {
    const selectedProject = {
      ...project,
      project_id: "261011_2200",
      display_name: "261011_선택한 쇼츠"
    };

    render(
      <ProjectDashboard
        onCreateProject={() => undefined}
        onSelectProject={() => undefined}
        projects={[project, selectedProject]}
        selectedProjectId={selectedProject.project_id}
      />
    );

    expect(screen.getByRole("button", { name: /261011_선택한 쇼츠/i })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: /261011_테스트 쇼츠/i })).not.toHaveAttribute("aria-current");
  });
});
