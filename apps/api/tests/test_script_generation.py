from pathlib import Path

import pytest

from app.scripts.files import (
    FINAL_SCRIPT_FILE,
    SCRIPT_CANDIDATES_FILE,
    read_script_state,
    write_final_script_state,
    write_script_candidates,
    write_selected_script_candidate,
)
from app.scripts.generation import (
    build_candidate_generation_prompt,
    build_final_script_prompt,
    validate_candidate_payload,
    validate_final_script,
)
from app.scripts.models import (
    CandidateKind,
    FinalScriptState,
    SelectScriptCandidateRequest,
    ScriptCandidate,
    TtsValidationResult,
)


def candidate(
    candidate_id: str = "same-topic-1",
    kind: CandidateKind = "same_topic",
) -> ScriptCandidate:
    return ScriptCandidate(
        candidate_id=candidate_id,
        candidate_type=kind,
        title="돈을 모으는 이상한 습관",
        hook="돈을 못 모으는 사람은 이것부터 틀립니다.",
        target_viewer="저축이 어려운 사회초년생",
        why_it_can_work="첫 문장이 자기 문제처럼 들리고, 중간 반전이 다음 문장을 보게 만듭니다.",
        main_curiosity_question="왜 열심히 아껴도 돈이 안 모일까?",
        structure_summary="상식 흔들기, 원인 좁히기, 반전, 실천 가능한 결론.",
        draft_script="돈을 못 모으는 사람은 대부분 의지가 약한 게 아닙니다. 처음부터 기준이 잘못돼 있습니다.",
        borrowed_reference_structure="레퍼런스의 상식 반박형 훅과 늦은 답변 구조를 빌립니다.",
    )


def candidate_payload():
    return {
        "candidates": [
            candidate("same-topic-1", "same_topic").model_dump(),
            candidate("different-topic-1", "different_topic").model_dump(),
            candidate("different-topic-2", "different_topic").model_dump(),
            candidate("different-topic-3", "different_topic").model_dump(),
        ]
    }


def test_script_candidate_rejects_empty_fields():
    with pytest.raises(ValueError):
        ScriptCandidate(
            candidate_id="same-topic-1",
            candidate_type="same_topic",
            title="",
            hook="훅",
            target_viewer="시청자",
            why_it_can_work="이유",
            main_curiosity_question="질문",
            structure_summary="구조",
            draft_script="대본",
            borrowed_reference_structure="구조 차용",
        )


def test_select_script_candidate_request_rejects_blank_id():
    with pytest.raises(ValueError):
        SelectScriptCandidateRequest(candidate_id="   ")


def test_tts_validation_rejects_empty_issue_text():
    with pytest.raises(ValueError):
        TtsValidationResult(is_valid=False, issues=[""])


@pytest.mark.parametrize(
    "payload",
    [
        {"is_valid": True, "issues": ["English letters remain"]},
        {"is_valid": False, "issues": []},
    ],
)
def test_tts_validation_rejects_inconsistent_validity(payload: dict):
    with pytest.raises(ValueError):
        TtsValidationResult(**payload)


def test_script_state_uses_final_state_as_canonical_source(tmp_path: Path):
    (tmp_path / FINAL_SCRIPT_FILE).write_text("orphan markdown\n", encoding="utf-8")

    state = read_script_state(tmp_path)

    assert state.final_script is None
    assert state.tts_validation is None


def test_write_and_read_script_state(tmp_path: Path):
    candidates = [
        candidate("same-topic-1", "same_topic"),
        candidate("different-topic-1", "different_topic"),
        candidate("different-topic-2", "different_topic"),
        candidate("different-topic-3", "different_topic"),
    ]
    write_script_candidates(tmp_path, candidates)
    write_selected_script_candidate(tmp_path, candidates[1])
    write_final_script_state(
        tmp_path,
        FinalScriptState(
            selected_candidate_id="different-topic-1",
            feedback="조금 더 강하게",
            final_script="돈을 못 모으는 이유는 의지가 아닙니다.",
            tts_validation=TtsValidationResult(is_valid=True, issues=[]),
        ),
    )

    state = read_script_state(tmp_path)

    assert (tmp_path / SCRIPT_CANDIDATES_FILE).exists()
    assert (
        (tmp_path / FINAL_SCRIPT_FILE).read_text(encoding="utf-8")
        == "돈을 못 모으는 이유는 의지가 아닙니다.\n"
    )
    assert len(state.candidates) == 4
    assert state.selected_candidate is not None
    assert state.selected_candidate.candidate_id == "different-topic-1"
    assert state.final_script == "돈을 못 모으는 이유는 의지가 아닙니다."
    assert state.tts_validation is not None
    assert state.tts_validation.is_valid is True


def test_candidate_prompt_requires_viral_drafts_and_reference_structure():
    prompt = build_candidate_generation_prompt(
        reference_script="레퍼런스 대본",
        reference_analysis={"primary_structure": "상식 반박"},
    )

    assert "exactly two" in prompt
    assert "Draft A" in prompt
    assert "Draft B" in prompt
    assert "레퍼런스 대본" in prompt
    assert "체감 단위 환산" in prompt


def test_validate_candidate_payload_requires_one_same_and_three_different():
    candidates = validate_candidate_payload(candidate_payload())

    assert len(candidates) == 4
    assert candidates[0].candidate_type == "same_topic"
    assert [item.candidate_type for item in candidates[1:]] == [
        "different_topic",
        "different_topic",
        "different_topic",
    ]


def test_validate_candidate_payload_rejects_wrong_mix():
    payload = candidate_payload()
    payload["candidates"][1]["candidate_type"] = "same_topic"

    with pytest.raises(ValueError, match="one same_topic and three different_topic"):
        validate_candidate_payload(payload)


def test_final_script_prompt_includes_feedback_and_strict_tts_rules():
    prompt = build_final_script_prompt(
        selected_candidate=candidate(),
        feedback="더 날카롭게",
    )

    assert "더 날카롭게" in prompt
    assert "all numbers are written in Korean pronunciation" in prompt
    assert "percent signs are written as 퍼센트" in prompt
    assert "parentheses and brackets are removed" in prompt
    assert "English words and acronyms are written by Korean pronunciation" in prompt


def test_validate_final_script_flags_obvious_tts_rule_violations():
    result = validate_final_script("AI가 24% 성장했습니다. (테스트)")

    assert result.is_valid is False
    assert "English letters remain" in result.issues
    assert "Arabic numerals remain" in result.issues
    assert "Percent symbol remains" in result.issues
    assert "Bracket characters remain" in result.issues


def test_validate_final_script_accepts_korean_tts_text():
    result = validate_final_script("에이아이가 이십사 퍼센트 성장했습니다.")

    assert result.is_valid is True
    assert result.issues == []


def test_validate_candidate_payload_accepts_two_drafts():
    payload = {
        "candidates": [
            candidate("draft_a", "draft_a").model_dump(),
            candidate("draft_b", "draft_b").model_dump(),
        ]
    }
    candidates = validate_candidate_payload(payload)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "draft_a"
    assert candidates[1].candidate_id == "draft_b"

