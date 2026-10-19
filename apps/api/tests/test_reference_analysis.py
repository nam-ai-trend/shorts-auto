from pathlib import Path

import pytest

from app.references.analysis import (
    build_analysis_prompt,
    render_analysis_markdown,
    validate_reference_analysis,
    write_reference_analysis,
)


def analysis_payload():
    return {
        "primary_structure": "common-sense conflict",
        "supporting_structures": ["question"],
        "hook_analysis": "첫 문장이 상식을 흔듭니다.",
        "curiosity_gap": "왜 그런지 궁금하게 만듭니다.",
        "retention_analysis": "중간에 반전을 넣습니다.",
        "payoff_analysis": "끝에서 답을 줍니다.",
        "risk_notes": ["근거가 약하면 과장처럼 보입니다."],
        "reusable_structure_notes": "상식 제시, 의문, 반전, 결론 순서.",
        "section_breakdown": [
            {
                "section": "Hook",
                "script_excerpt": "이걸 모르면 손해입니다.",
                "viewer_reaction": "멈춥니다.",
                "purpose": "궁금증",
            }
        ],
    }


def test_build_analysis_prompt_requires_reusable_production_analysis():
    prompt = build_analysis_prompt("이걸 모르면 손해입니다.")

    assert "why viewers stop" in prompt
    assert "keep watching" in prompt
    assert "feel payoff" in prompt
    assert "section_breakdown" in prompt
    assert "이걸 모르면 손해입니다." in prompt


def test_render_analysis_markdown_contains_core_sections():
    markdown = render_analysis_markdown(analysis_payload())

    assert "# Reference Analysis" in markdown
    assert "common-sense conflict" in markdown
    assert "첫 문장이 상식을 흔듭니다." in markdown
    assert "근거가 약하면 과장처럼 보입니다." in markdown


def test_write_reference_analysis_saves_json_and_markdown(tmp_path: Path):
    markdown = write_reference_analysis(tmp_path, analysis_payload())

    assert "# Reference Analysis" in markdown
    assert (tmp_path / "reference_analysis.json").exists()
    assert (tmp_path / "reference_analysis.md").exists()


@pytest.mark.parametrize(
    "bad_payload",
    [
        {"primary_structure": "missing fields"},
        {**analysis_payload(), "supporting_structures": 12345},
        {**analysis_payload(), "section_breakdown": [{"section": "Hook"}]},
    ],
)
def test_validate_reference_analysis_rejects_malformed_payloads(bad_payload: dict):
    with pytest.raises(ValueError):
        validate_reference_analysis(bad_payload)


def test_validate_reference_analysis_coerces_string_to_list():
    payload = analysis_payload()
    payload["risk_notes"] = "하나의 위험 요소 문자열"
    payload["supporting_structures"] = "단일 지원 구조"

    validated = validate_reference_analysis(payload)

    assert validated["risk_notes"] == ["하나의 위험 요소 문자열"]
    assert validated["supporting_structures"] == ["단일 지원 구조"]

