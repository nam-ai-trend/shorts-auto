import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CandidateDraftsPanel } from "../src/components/CandidateDraftsPanel";
import type { ScriptCandidate } from "../src/types";

const candidate: ScriptCandidate = {
  candidate_id: "same-topic-1",
  candidate_type: "same_topic",
  title: "돈을 모으는 이상한 습관",
  hook: "돈을 못 모으는 사람은 이것부터 틀립니다.",
  target_viewer: "사회초년생",
  why_it_can_work: "자기 문제처럼 들리는 훅입니다.",
  main_curiosity_question: "왜 돈이 안 모일까?",
  structure_summary: "상식 반박, 원인, 반전, 결론.",
  draft_script: "돈을 못 모으는 사람은 의지가 약한 게 아닙니다.",
  borrowed_reference_structure: "레퍼런스의 상식 반박 구조를 빌립니다."
};

describe("CandidateDraftsPanel", () => {
  it("renders candidates and calls generate/select actions", async () => {
    const user = userEvent.setup();
    const onGenerate = vi.fn();
    const onSelect = vi.fn();

    render(
      <CandidateDraftsPanel
        candidates={[candidate]}
        isBusy={false}
        onGenerate={onGenerate}
        onSelect={onSelect}
        selectedCandidateId={null}
      />
    );

    expect(screen.getByText("돈을 모으는 이상한 습관")).toBeInTheDocument();
    expect(screen.getByText(/same topic/i)).toBeInTheDocument();
    expect(screen.getByText("돈을 못 모으는 사람은 이것부터 틀립니다.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Generate candidates/i }));
    await user.click(screen.getByRole("button", { name: /Select 돈을 모으는 이상한 습관/i }));

    expect(onGenerate).toHaveBeenCalled();
    expect(onSelect).toHaveBeenCalledWith("same-topic-1");
  });
});
