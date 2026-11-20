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
    extract_verbatim_script_from_feedback,
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


def test_extract_verbatim_script_from_feedback():
    feedback = """아래와 똑같이 해줘. 완전똑같이

주유소에서 기름이 딸깍 멈출 때, 왜 그런지 궁금했죠? 사실 주유기 끝에 아주 작은 구멍이 하나 있어요. 기름 넣는 동안 이 구멍은 탱크 내 공기를 끌어들이는 역할을 합니다."""
    result = extract_verbatim_script_from_feedback(feedback)
    assert result is not None
    assert "주유소에서 기름이 딸깍 멈출 때" in result
    assert "아래와 똑같이" not in result

    # Should return None if no verbatim trigger
    assert extract_verbatim_script_from_feedback("더 짧고 강하게 해줘") is None


def test_script_candidate_tags_and_keywords_normalization():
    cand = ScriptCandidate(
        candidate_id="draft_a",
        candidate_type="draft_a",
        title="테스트 제목",
        tags="#교통카드 #배터리 #쇼츠 #shorts",
        keywords="교통카드, 스마트폰 배터리, #쇼츠",
        hook="훅 대사",
        target_viewer="시청자",
        why_it_can_work="알고리즘 이유",
        main_curiosity_question="호기심 질문",
        structure_summary="구조 요약",
        draft_script="대본 본문",
        borrowed_reference_structure="공식 차용",
    )
    # tags에서 #쇼츠, #shorts 제거 확인
    assert "#쇼츠" not in cand.tags
    assert "#shorts" not in cand.tags
    assert cand.tags == "#교통카드 #배터리"

    # keywords에서 # 없이 과학쇼츠, 쇼츠, 과학지식이 맨 뒤에 붙는지 확인
    assert cand.keywords.endswith("과학쇼츠, 쇼츠, 과학지식")
    assert "#과학쇼츠" not in cand.keywords
    assert "#쇼츠" not in cand.keywords
    assert cand.keywords == "교통카드, 스마트폰 배터리, 과학쇼츠, 쇼츠, 과학지식"


def test_strip_unnecessary_hook_intro():
    from app.scripts.generation import strip_unnecessary_hook_intro, sanitize_script_loop_candidate

    assert strip_unnecessary_hook_intro("만약 여러분이 수백만 원짜리 진주를 쪼갠다면!") == "수백만 원짜리 진주를 쪼갠다면!"
    assert strip_unnecessary_hook_intro("만약 여러분은 이걸 알고 계셨나요?") == "이걸 알고 계셨나요?"
    assert strip_unnecessary_hook_intro("여러분, 진짜 놀라운 사실이 있습니다.") == "진짜 놀라운 사실이 있습니다."
    assert strip_unnecessary_hook_intro("혹시 여러분이 생각하는 그게 맞을까요?") == "생각하는 그게 맞을까요?"
    assert strip_unnecessary_hook_intro("수백만 원짜리 천연 진주를 반으로 쪼갠다면") == "수백만 원짜리 천연 진주를 반으로 쪼갠다면"

    # candidate sanitizer 검증
    cand = candidate()
    cand.hook = "만약 여러분이 돈을 못 모은다면 이것부터 틀렸습니다."
    cand.draft_script = "만약 여러분이 돈을 못 모은다면 이것부터 틀렸습니다. 본문 내용입니다."
    sanitized = sanitize_script_loop_candidate(cand)
    assert sanitized.hook == "돈을 못 모은다면 이것부터 틀렸습니다."
    assert sanitized.draft_script.startswith("돈을 못 모은다면 이것부터 틀렸습니다.")


def test_sanitize_final_script_loop_removes_duplicate_hook_and_trailing_conjunction():
    from app.scripts.generation import sanitize_final_script_loop

    hook = "수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다."
    raw = (
        "진주는 조개가 만든 방어막입니다. 결국 그 보석의 정체인 셈이죠. "
        "그래서 수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다."
    )
    cleaned = sanitize_final_script_loop(raw, hook=hook)
    assert "그래서" not in cleaned
    assert "벌레가 나옵니다" not in cleaned
    assert cleaned.rstrip(".").endswith("정체인 셈이죠")


def test_extract_final_scripts_syncs_loop_structure_between_tts_and_display():
    from app.scripts.generation import extract_final_scripts

    hook = "수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다."
    payload = {
        "final_script": "이천이십삼년에 조개가 방어막을 쳤습니다. 직접 확인해보고 싶다면.",
        "display_script": "2023년에 조개가 방어막을 쳤습니다. 직접 확인해보고 싶다면.",
        "loop_tail_bridge": "직접 확인해보고 싶다면",
        "connected_preview": "직접 확인해보고 싶다면 수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다.",
    }
    final_s, display_s, returned_tb = extract_final_scripts(payload, hook=hook)
    assert final_s.rstrip(".").endswith("직접 확인해보고 싶다면")
    assert display_s.rstrip(".").endswith("직접 확인해보고 싶다면")
    assert returned_tb == "직접 확인해보고 싶다면"
    assert "이천이십삼년" in final_s
    assert "2023년" in display_s


def test_validate_script_loop_golden_standard_air_intake_example():
    """사용자가 제공한 실제 골든 스탠다드 레퍼런스(공기 흡입 예시) 검증"""
    from app.scripts.generation import validate_script_loop

    hook = "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요?"
    script = (
        "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요? "
        "풍선 수천다발 정도 될 거라 생각하겠지만 이거 아닙니다. "
        "어른 뱃속엔 포도알 같은 공기주머니인 허파꽈리가 약 4억8천만개나 있고, "
        "평생 모으면 약 530톤으로 지구에서 가장 큰 동물 대왕고래 3마리보다 더 무겁다는 사실! "
        "하루 종일 숨만 쉬는"
    )
    result = validate_script_loop(script, hook=hook)
    assert result.is_valid is True
    assert result.score == 100
    assert "관형절 주어 수식형" in result.loop_type
    assert result.tail_bridge == "하루 종일 숨만 쉬는"
    assert result.head_hook == "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요?"
    assert result.connected_preview == "...하루 종일 숨만 쉬는 ➔ [내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요?]"
    assert not result.issues


def test_validate_script_loop_detects_verbatim_repeat_and_period_ending():
    """사용자가 겪었던 복붙 버그 및 평서문 종결 감지 검증"""
    from app.scripts.generation import validate_script_loop

    hook = "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다!"
    # 1. 복붙 케이스
    bad_script = (
        "스마트폰을 계속 보면 뇌의 전두엽이 손상됩니다. "
        "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다!"
    )
    res1 = validate_script_loop(bad_script, hook=hook, tail_bridge=hook)
    assert res1.is_valid is False
    assert any("중복 복붙" in iss for iss in res1.issues)

    # 2. 평서문 종결 케이스
    flat_script = (
        "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다! "
        "도파민 과부하를 막으려면 스마트폰을 멀리해야 합니다."
    )
    res2 = validate_script_loop(flat_script, hook=hook)
    assert res2.is_valid is False
    assert any("평서문 종결형" in iss for iss in res2.issues)


def test_sanitize_script_loop_candidate_fixes_verbatim_repeat():
    """초안 생성 시 LLM이 tail_bridge를 hook과 똑같이 반환했을 때 안전하게 보정하는지 검증"""
    from app.scripts.generation import sanitize_script_loop_candidate
    from app.scripts.models import LoopDesign

    cand = candidate()
    cand.hook = "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다!"
    cand.draft_script = (
        "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다! "
        "도파민 과부하로 인해 뇌가 쉽게 피로해집니다."
    )
    cand.loop_design = LoopDesign(
        loop_type="단계적 인과형 무한 루프",
        tail_bridge=cand.hook,  # 모델이 첫 문장을 그대로 복붙함
        head_hook=cand.hook,
        connected_preview=f"...{cand.hook} ➔ [{cand.hook}]",
    )

    sanitized = sanitize_script_loop_candidate(cand)
    assert sanitized.loop_design is not None
    # 복붙이 해제되고, 실제 마지막 문장으로 깔끔하게 보정되었는지 확인
    assert sanitized.loop_design.tail_bridge != cand.hook
    assert sanitized.loop_design.head_hook == cand.hook


def test_final_script_prompt_enforces_hook_and_loop_rules():
    from app.scripts.generation import build_final_script_prompt

    cand = candidate()
    cand.hook = "돈을 못 모으는 사람은 이것부터 틀립니다."
    prompt = build_final_script_prompt(cand)

    assert cand.hook in prompt
    assert "완성도 높은 결말(Impactful Outro)" in prompt
    assert "connected_preview" in prompt


def test_validate_script_loop_passes_high_quality_loop():
    from app.scripts.generation import validate_script_loop

    hook = "수백만 원짜리 천연 진주를 반으로 쪼개면, 그 속에서 모래알 대신 끔찍한 벌레 사체를 보게 됩니다."
    script = (
        "수백만 원짜리 천연 진주를 반으로 쪼개면, 그 속에서 모래알 대신 끔찍한 벌레 사체를 보게 됩니다. "
        "진주는 조개가 만든 방어막입니다. "
        "조개가 평생에 걸쳐 치러낸 이 처절한 사투의 비밀을 풀기 위해,"
    )
    result = validate_script_loop(script, hook=hook)
    assert result.is_valid is True
    assert result.score == 100
    assert "목적-결과 연결형" in result.loop_type
    assert "풀기 위해" in result.connected_preview
    assert not result.issues


def test_validate_script_loop_catches_double_condition_awkwardness():
    from app.scripts.generation import validate_script_loop

    hook = "수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다."
    awkward_script = (
        "진주는 조개가 만든 방어막입니다. "
        "조개의 사투를 두 눈으로 직접 확인해보고 싶다면,"
    )
    result = validate_script_loop(awkward_script, hook=hook)
    assert result.is_valid is False
    assert any("이중 조건문" in iss for iss in result.issues)


def test_validate_script_loop_catches_duplicate_hook_and_conjunction_residue():
    from app.scripts.generation import validate_script_loop

    hook = "수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다."
    bad_script = (
        "진주는 모래가 아닙니다. "
        "그래서 수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다."
    )
    result = validate_script_loop(bad_script, hook=hook)
    assert result.is_valid is False
    assert any("중복 복붙" in iss for iss in result.issues)


def test_validate_script_loop_catches_unrelated_monologue_question():
    from app.scripts.generation import validate_script_loop

    hook = "수백만 원짜리 천연 진주를 반으로 쪼개면 벌레가 나옵니다."
    bad_script = (
        "진주는 조개가 만든 방어막입니다. "
        "그렇다면 조개 한 마리 몸속에 심어진 수십 주머니가 쏟아내는 그 반짝임은 과연 무엇을 의미하는 걸까요?"
    )
    result = validate_script_loop(bad_script, hook=hook)
    assert any("독백형 질문" in iss for iss in result.issues)
    assert result.score < 80


def test_candidates_two_pass_loop_refinement():
    """1차 본문 생성 후 2차 정밀 루프 폴리싱(시퀀스) 검증"""
    from app.scripts.generation import (
        build_candidates_loop_refinement_prompt,
        refine_candidates_loop,
    )

    c1 = candidate("draft_a", "draft_a")
    c1.hook = "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요?"
    # 1차로 생성된 본문이 평서문으로 끝난 상태
    c1.draft_script = (
        "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요? "
        "어른 뱃속엔 허파꽈리가 사억팔천만개나 있고, "
        "평생 모으면 약 오백삼십톤으로 대왕고래 세 마리보다 더 무겁습니다."
    )
    c1.display_script = (
        "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요? "
        "어른 뱃속엔 허파꽈리가 4억8천만개나 있고, "
        "평생 모으면 약 530톤으로 대왕고래 3마리보다 더 무겁습니다."
    )

    # 1. 프롬프트 생성 검증
    prompt = build_candidates_loop_refinement_prompt([c1])
    assert "2차 무한 루프 정밀 결합" in prompt
    assert c1.hook in prompt
    assert "골든 스탠다드 레퍼런스" in prompt
    assert "관형절 주어/목적어 수식형" in prompt

    # 2. 2차 시퀀스 실행 검증 (Mock Client)
    class MockClient:
        def analyze(self, p: str):
            return {
                "refinements": [
                    {
                        "candidate_id": "draft_a",
                        "tail_bridge": "하루 종일 숨만 쉬는",
                        "connected_preview": "...하루 종일 숨만 쉬는 ➔ [내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요?]",
                        "loop_type": "관형절 주어 수식형 (완벽한 순환 ⭐)",
                        "refined_draft_script": (
                            "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요? "
                            "어른 뱃속엔 허파꽈리가 사억팔천만개나 있고, "
                            "평생 모으면 약 오백삼십톤으로 대왕고래 세 마리보다 더 무겁다는 사실! 하루 종일 숨만 쉬는"
                        ),
                        "refined_display_script": (
                            "내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요? "
                            "어른 뱃속엔 허파꽈리가 4억8천만개나 있고, "
                            "평생 모으면 약 530톤으로 대왕고래 3마리보다 더 무겁다는 사실! 하루 종일 숨만 쉬는"
                        ),
                    }
                ]
            }

    refined = refine_candidates_loop(MockClient(), [c1])
    assert len(refined) == 1
    target = refined[0]
    # 2차 시퀀스를 거쳐 끝 문장이 관형절 수식형으로 결합되었는지 확인
    assert target.draft_script.rstrip(".").endswith("하루 종일 숨만 쉬는")
    assert target.display_script.rstrip(".").endswith("하루 종일 숨만 쉬는")
    assert target.loop_design is not None
    assert target.loop_design.tail_bridge.rstrip(".") == "하루 종일 숨만 쉬는"
    assert target.loop_design.loop_type in ("완결형 엔딩", "관형절 주어 수식형 (완벽한 순환 ⭐)")


def test_final_script_two_pass_loop_refinement():
    """최종 대본(Step 6) 1차 확정 후 2차 루프 폴리싱(시퀀스) 검증"""
    from app.scripts.generation import (
        build_final_script_loop_refinement_prompt,
        refine_final_script_loop,
    )

    hook = "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다!"
    # 1차로 작성된 최종 대본 (평서문 종결)
    raw_final = (
        "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다! "
        "스마트폰 화면을 보면 도파민이 폭발하지만 이십분 뒤 전두엽 활동이 급감합니다. "
        "결국 뇌가 쉽게 피로해집니다."
    )
    raw_display = (
        "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다! "
        "스마트폰 화면을 보면 도파민이 폭발하지만 20분 뒤 전두엽 활동이 급감합니다. "
        "결국 뇌가 쉽게 피로해집니다."
    )

    prompt = build_final_script_loop_refinement_prompt(hook, raw_final, raw_display)
    assert hook in prompt
    assert "2차 무한 루프 정밀 결합" in prompt

    class MockFinalClient:
        def analyze(self, p: str):
            return {
                "tail_bridge": "여전히 스마트폰에서 손을 떼지 못하는",
                "connected_preview": "...여전히 스마트폰에서 손을 떼지 못하는 ➔ [스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다!]",
                "loop_type": "관형절 주어 수식형 (완벽한 순환 ⭐)",
                "refined_final_script": (
                    "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다! "
                    "스마트폰 화면을 보면 도파민이 폭발하지만 이십분 뒤 전두엽 활동이 급감합니다. "
                    "여전히 스마트폰에서 손을 떼지 못하는"
                ),
                "refined_display_script": (
                    "스마트폰만 보면 집중력이 확 떨어지는 당신, 이유가 있습니다! "
                    "스마트폰 화면을 보면 도파민이 폭발하지만 20분 뒤 전두엽 활동이 급감합니다. "
                    "여전히 스마트폰에서 손을 떼지 못하는"
                ),
            }

    refined_s, refined_d, tb = refine_final_script_loop(
        MockFinalClient(),
        hook=hook,
        final_script=raw_final,
        display_script=raw_display,
    )

    assert refined_s.rstrip(".").endswith("여전히 스마트폰에서 손을 떼지 못하는")
    assert refined_d.rstrip(".").endswith("여전히 스마트폰에서 손을 떼지 못하는")
    assert tb == "여전히 스마트폰에서 손을 떼지 못하는"


def test_build_final_script_prompt_with_hook_change_feedback():
    from app.scripts.generation import build_final_script_prompt
    from app.scripts.models import ScriptCandidate

    candidate = ScriptCandidate(
        candidate_id="draft_b",
        candidate_type="draft_b",
        title="굵은 통나무를 통째로 넣으면 불이 꺼진다는 사실, 믿어지나요?",
        hook="굵은 통나무를 통째로 넣으면 불이 꺼진다는 사실, 믿어지나요?",
        target_viewer="일반인",
        why_it_can_work="호기심",
        main_curiosity_question="왜 꺼질까?",
        structure_summary="구조",
        draft_script="초안 대본 본문입니다.",
        borrowed_reference_structure="구조",
    )

    feedback = "통나무를 통째로 넣으면 매운연기만 나온다는식으로 먼저 시작해줘. 후킹이 너무 부족해서."
    prompt = build_final_script_prompt(candidate, feedback=feedback)

    assert "사용자 피드백 최우선 적용" in prompt
    assert "기존 초안의 첫 문장" in prompt
    assert "절대 그대로 유지하지 마세요" in prompt
    assert feedback in prompt

