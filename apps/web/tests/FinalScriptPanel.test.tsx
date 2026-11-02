import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FinalScriptPanel } from "../src/components/FinalScriptPanel";
import type { ScriptCandidate, TtsValidationResult } from "../src/types";

const selectedCandidate: ScriptCandidate = {
  candidate_id: "different-topic-1",
  candidate_type: "different_topic",
  title: "잠을 망치는 습관",
  hook: "잠을 못 자는 사람은 밤이 아니라 아침을 망칩니다.",
  target_viewer: "수면이 부족한 직장인",
  why_it_can_work: "예상과 다른 원인이 궁금증을 만듭니다.",
  main_curiosity_question: "왜 아침 습관이 잠을 망칠까?",
  structure_summary: "오해 제시, 원인 이동, 반전, 해결.",
  draft_script: "잠을 못 자는 사람은 밤에만 문제가 있는 게 아닙니다.",
  borrowed_reference_structure: "원인 이동 구조를 빌립니다."
};

const validation: TtsValidationResult = {
  is_valid: false,
  issues: ["English letters remain"]
};

describe("FinalScriptPanel", () => {
  it("submits feedback and shows validation issues", async () => {
    const user = userEvent.setup();
    const onFinalize = vi.fn();

    render(
      <FinalScriptPanel
        finalScript="AI가 성장했습니다."
        isBusy={false}
        onFinalize={onFinalize}
        selectedCandidate={selectedCandidate}
        ttsValidation={validation}
      />
    );

    expect(screen.getByText("잠을 망치는 습관")).toBeInTheDocument();
    expect(screen.getByText("AI가 성장했습니다.")).toBeInTheDocument();
    expect(screen.getByText("English letters remain")).toBeInTheDocument();

    await user.type(screen.getByLabelText(/Feedback/i), "더 짧게");
    await user.click(screen.getByRole("button", { name: /Finalize script/i }));

    expect(onFinalize).toHaveBeenCalledWith("더 짧게");
  });

  it("allows direct script editing and saves modified script", async () => {
    const user = userEvent.setup();
    const onFinalize = vi.fn();
    const onUpdateFinalScript = vi.fn();

    render(
      <FinalScriptPanel
        finalScript="기존 대본입니다."
        isBusy={false}
        onFinalize={onFinalize}
        onUpdateFinalScript={onUpdateFinalScript}
        selectedCandidate={selectedCandidate}
        ttsValidation={null}
      />
    );

    const editButton = screen.getByRole("button", { name: /대본 직접 수정하기/i });
    expect(editButton).toBeInTheDocument();

    await user.click(editButton);

    const textarea = screen.getByRole("textbox", { name: /Direct Script Edit/i });
    expect(textarea).toHaveValue("기존 대본입니다.");

    await user.clear(textarea);
    await user.type(textarea, "직접 수정한 대본입니다.");

    const saveButton = screen.getByRole("button", { name: /수정한 대본 그대로 최종 확정/i });
    await user.click(saveButton);

    expect(onUpdateFinalScript).toHaveBeenCalledWith("직접 수정한 대본입니다.");
  });
});

