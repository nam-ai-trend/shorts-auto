from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.scripts.models import (
    FINAL_SCRIPT_MAX_LENGTH,
    FinalScriptState,
    ScriptCandidate,
    TtsValidationResult,
    clean_text,
)


class CandidateGenerationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ScriptCandidate] = Field(min_length=2, max_length=4)


class FinalScriptPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_script: str = Field(max_length=FINAL_SCRIPT_MAX_LENGTH)

    @field_validator("final_script")
    @classmethod
    def clean_final_script(cls, value: str) -> str:
        return clean_text(value, "final_script", FINAL_SCRIPT_MAX_LENGTH)


def _json_for_prompt(payload: Any) -> str:
    if isinstance(payload, BaseModel):
        payload = payload.model_dump()
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_candidate_generation_prompt(
    reference_script: str,
    reference_analysis: dict,
    user_feedback: str = "",
) -> str:
    user_feedback = user_feedback.strip()

    # 원본 재구성/리메이크 요청 여부 판별
    remake_keywords = ["원본", "원작", "리메이크", "동일 주제", "재구성", "원복", "스크립트 참고", "대본 참고"]
    is_remake_request = any(kw in user_feedback for kw in remake_keywords)

    recommended_topics = reference_analysis.get("recommended_topics", []) if isinstance(reference_analysis, dict) else []
    matched_topic = None
    if user_feedback and recommended_topics:
        match = re.search(r"(?:#?\s*([1-5])\s*번?|([1-5])\s*번)", user_feedback)
        if match:
            num = int(match.group(1) or match.group(2))
            matched_topic = next((t for t in recommended_topics if t.get("topic_number") == num), None)
            if num == 1:
                # 1번은 본래 '동일 주제/원본 재구성' 목적이므로 리메이크 요청으로 판별
                is_remake_request = True

    if is_remake_request:
        reference_script_note = "💡 필수 참고: 아래 원본 레퍼런스 대본의 소재와 핵심 사건/팩트를 바탕으로, 사용자 피드백 요구사항에 맞춰 고밀도 팩트체크 쇼츠로 재구성하세요."
        feedback_section = f"""### 🚨 [최우선 필수: 원본 대본 팩트체크 & 바이럴 쇼츠 재구성 (Draft A & Draft B 둘 다 100% 공통 적용)]
사용자가 원본 레퍼런스 대본의 핵심 소재와 주제를 바탕으로 한 **'원본 재구성(리메이크)'**을 요청했습니다.
원본 대본의 핵심 주제와 팩트를 충실히 계승하되, 사용자가 제시한 구체적인 기획 피드백을 100% 반영하여 고밀도 팩트 쇼츠 대본 2종(Draft A, Draft B)을 작성하세요.

[사용자 필수 기획 피드백]:
{user_feedback}

[⚠️ 원본 재구성 절대 반영 규칙]:
1. 🎯 소재 일치: 원본 레퍼런스 대본의 핵심 소재와 과학적/역사적/지식적 팩트를 바탕으로 작성하세요.
2. 🗣️ 사용자 지정 멘트 및 구성 100% 구현:
   - 사용자가 시작 멘트나 특정 대사를 지정했다면 도입부에 반드시 그대로 구현하세요.
   - 사용자가 전개 방식, 팩트체크 순서, 특정 관점을 지정했다면 본문에 빠짐없이 충실하게 반영하세요.
3. 🔥 수치 폭탄 & 체감 환산:
   - 원본 대본의 팩트를 더 생생하게 전달할 수 있는 구체적인 수치(숫자, 단위)와 일상 체감 환산 비유(올림픽 수영장 N개, 63빌딩 N채, N만 잔 등)를 결합하여 압도적인 몰입감을 부여하세요.
4. 🎭 2가지 버전 모두 위 원본 재구성 내용을 다루되,
   - Draft A: [도파민 폭발 / 상식 충돌 & 충격 수치형 (텐션형)]
   - Draft B: [호기심 뇌절 / 미스터리 & 단계적 반전형 (스토리텔링형)]
   으로 연출 톤만 다르게 작성하세요."""
    elif matched_topic:
        reference_script_note = "⚠️ 중요 주의: 아래 레퍼런스 대본은 오직 '문장 리듬과 텐션 전개 구조'를 참고하기 위한 템플릿일 뿐입니다. 아래 레퍼런스 대본의 고유 소재/내용은 절대 새 대본에 섞지 마세요! 당신이 작성할 Draft A와 Draft B의 소재는 오직 위 [선택된 확정 주제]여야 합니다."
        feedback_section = f"""### 🚨 [최우선 필수: 사용자가 선택한 확정 주제 (Draft A & Draft B 둘 다 100% 공통 적용)]
- 주제 번호: #{matched_topic.get('topic_number')}
- 주제 제목: {matched_topic.get('title')}
- 카테고리: {matched_topic.get('category')}
- 핵심 후킹: {matched_topic.get('hook')}
- 핵심 질문: {matched_topic.get('core_question')}
- 제작 전략: {matched_topic.get('production_strategy')}
- 추가 요청사항: {user_feedback}

[⚠️ 엄격한 단일 주제 강제 규칙 (Single-Topic Enforcement)]:
1. Draft A와 Draft B는 **둘 다 반드시 위 확정 주제("#{matched_topic.get('topic_number')}. {matched_topic.get('title')}")만을 주인공이자 소재로 작성**해야 합니다!
2. Draft A는 원본 레퍼런스 소재를 쓰고 Draft B만 새 주제를 쓰는 식의 역할 분리는 **절대로 금지**합니다!
3. 원본 레퍼런스 대본은 오직 '문장 호흡/텐션 전개 구조'만 참고할 뿐, 원본 레퍼런스의 고유 소재는 Draft A와 Draft B 모두에서 **100% 완전히 배제**해야 합니다."""
    elif user_feedback:
        reference_script_note = "💡 참고: 아래 레퍼런스 대본의 호흡과 구조를 참고하여, 사용자의 기획 피드백을 대본에 충실히 반영하세요."
        feedback_section = f"""### [사용자 기획 피드백 및 선택 주제]
{user_feedback}

[⚠️ 엄격한 단일 주제 강제 규칙]:
1. Draft A와 Draft B는 **둘 다 사용자가 지정한 위 피드백/주제만을 100% 동일한 소재로 작성**해야 합니다.
2. 사용자가 요구한 시작 대사, 전개 방식, 팩트 수치를 대본에 빠짐없이 정확히 반영하세요!"""
    else:
        reference_script_note = "💡 참고: 분석 리포트의 추천 주제 1개를 선택하여 Draft A와 Draft B를 작성하세요."
        feedback_section = """### [사용자 기획 피드백]
별도 피드백 없음 (분석 리포트의 '추천 재구성 주제 5선' 중 가장 파급력이 크고 상식 충돌이 강렬한 주제 1개를 선택하여, Draft A와 Draft B 둘 다 100% 동일한 그 주제로 제작하세요)."""

    return f"""
# System Instruction: Generate exactly two viral-ready Korean YouTube Shorts script candidates (Draft A and Draft B).

당신은 대한민국 최고의 유튜브 쇼츠 바이럴 전문 기획자이자 과학/지식 팩트체커입니다.
제공된 레퍼런스 분석 리포트의 흥행 공식과 5대 기획 원칙(ref/analysis.md)을 바탕으로, 완전히 새로운 **한국어 유튜브 쇼츠 대본 초안 2가지 버전(Draft A, Draft B)**을 작성하세요.

{feedback_section}

### 🔥 [가장 중요한 핵심 목표: 빈약함 탈피 & 고밀도 팩트/수치 폭탄]
기존의 쇼츠 대본이 밋밋하고 빈약했던 이유는 구체적인 사실(Fact)과 체감 수치(Figure) 없이 추상적인 설명만 늘어놓았기 때문입니다.
이번 대본은 레퍼런스 쇼츠(예: "모기 주둥이 안 6개 바늘, 초당 30번 진동 톱날, 물 한 방울의 25분의 1인 2마이크로리터, 전 세계 1000조 마리 모기가 빨아먹는 피 160억 리터, 올림픽 수영장 6,400개")처럼,
**시청자가 1초도 눈을 뗄 수 없는 정밀한 팩트와 충격적인 체감 환산 수치**를 반드시 담아야 합니다.

### [대본 작성 4대 절대 규칙]
1. 🎯 정밀한 마이크로 팩트 & 구조적 디테일 (Micro Facts & Detail):
   - "엄청 빠릅니다", "놀랍습니다", "대단합니다" 같은 추상적이고 뻔한 수식어는 절대 금지!
   - 해당 주제의 미세한 과학적/생물학적/물리적 메커니즘과 정밀한 수치를 최소 2개 이상 구체적으로 포함하세요.
   - 예시: "초당 30번 진동하는 톱날침", "물 한 방울의 25분의 1인 2마이크로리터", "약산성 비가 바위를 녹여 나트륨을 배출", "뇌가 하루에 내리는 35,000번의 결정" 등.

2. 🔥 압도적인 매크로 스케일 & 체감 단위 환산 (Macro Scale & Everyday Comparison):
   - 전체 총량(억/조 단위 등)이나 거대한 규모를 말할 때는, 시청자가 머릿속에 즉시 그릴 수 있는 일상적 시각 단위로 반드시 환산하세요.
   - 환산 단위 예시: "올림픽 규격 수영장 6,400개", "50층 아파트 높이 150미터", "63빌딩 120채", "서울 면적의 3배", "종이컵 500만 잔" 등.
   - 숫자가 귀로 들었을 때 꽂히고 머릿속에 시각적 충격을 주어야 합니다.

3. 🎢 쇼츠 떡상 4단계 텐션 빌드업 (Pacing & Hooking):
   - [0~3초: 상식 충돌 후킹] 시청자가 당연하게 생각하는 상식을 단 한 문장으로 부수며 스크롤 정지.
     (예: "기껏해야 수영장 하나 정도겠지 생각하겠지만, 이거 완전 아닙니다!", "왜 아무도 이 사실을 모를까요?")
   - [3~15초: 의문 심화 & 관찰 포인트] 시청자가 예측하지 못한 의외의 질문과 낯선 관찰 포인트를 던져 "대체 왜?" 호기심 갭 극대화.
   - [15~35초: 상태 변화 & 팩트 폭탄] 설명조로 늘어지지 않고, "더 소름 돋는 건...", "그런데 여기서 반전이 일어납니다"처럼 국면이 바뀌는 전환점과 함께 미세 팩트와 작동 원리를 쉴 틈 없이 전개.
   - [35~50초: 결말 인지 보상 & 펀치라인] 압도적 총량과 체감 환산 수치로 지적 카타르시스를 주고, 댓글을 달고 공유할 수밖에 없는 여운 넘치는 마지막 한마디(클리프행어/펀치라인)로 마무리.

4. ⏱️ 대본 분량 및 구어체 어조 (엄수!):
   - 분량: 각 draft_script는 **45~55초 분량 (공백 포함 420자 ~ 520자 내외, 8~10개 문장)**으로 꽉 찬 밀도로 작성하세요. (250~350자는 너무 짧아 내용이 빈약해지니 절대 금지!)
   - 어조: 시청자에게 직접 속삭이듯 말하는 찰진 구어체 낭독 톤 ("~거든요!", "~다니까요!", "~죠?"). 딱딱한 백과사전식 문장 절대 금지.

### [2가지 버전의 뚜렷한 연출 차별화 - 단, 소재는 둘 다 위 [선택된 확정 주제] 100% 동일 적용!]
- Draft A (candidate_id: "draft_a", candidate_type: "draft_a"):
  * 소재: 위 [선택된 확정 주제] 100% 적용 (절대 원본 레퍼런스 소재로 쓰지 말 것!)
  * 컨셉: [도파민 폭발 / 상식 충돌 & 충격 수치형 (텐션형)]
  * 연출: 빠른 템포와 쉴 틈 없는 수치 폭격! 시청각적 상상력을 자극하는 거대한 스케일 비교 중심. 위 선택된 주제와 관련된 일반인의 당연한 상식을 단숨에 부수고 구체적인 과학적 팩트와 충격 환산 수치를 쏟아부으세요.
- Draft B (candidate_id: "draft_b", candidate_type: "draft_b"):
  * 소재: 위 [선택된 확정 주제] 100% 적용
  * 컨셉: [호기심 뇌절 / 미스터리 & 단계적 반전형 (스토리텔링형)]
  * 연출: "우리가 매일 보면서도 몰랐던 소름 돋는 비밀" 식의 서서히 조여오는 스토리텔링. 미세한 관찰 디테일과 실험에서 출발해 거대한 진실과 반전으로 확장되는 몰입형.

### [유튜브 업로드용 필수 메타데이터 작성 규칙]
1. title_options (후킹형 제목 3선):
   - 시청자가 클릭하지 않고는 못 배기는 각기 다른 스타일의 3가지 제목 리스트:
     * 1) 호기심/궁금증 유발형 (예: "전 세계 개미가 하루에 옮기는 무게는?")
     * 2) 충격 팩트/숫자 환산형 (예: "개미들이 하루에 옮기는 무게가 63빌딩 150채라고?")
     * 3) 상식 파괴/도파민형 (예: "기껏해야 차 한 대? 개미 힘에 숨겨진 충격 진실")
2. title:
   - 위 3가지 옵션 중 가장 어그로와 후킹이 강력한 대표 제목 1개.
3. description (설명란 문구):
   - 영상 내용을 간략히 2~3줄로 요약한 유튜브 설명란 텍스트.
   - [중요!] 마크다운 별표(**)나 큰따옴표("), 작은따옴표(')는 절대 사용하지 말고 순수 평문으로만 작성하세요.
4. tags (해시태그):
   - #키워드1 #키워드2 #키워드3 #쇼츠 형태로 띄어쓰기로 구분된 해시태그 목록.
5. keywords (검색 키워드):
   - 키워드1, 키워드2, 키워드3, 키워드4 형태로 쉼표로 구분된 검색 키워드 목록.

### [출력 형식 (반드시 JSON만 출력)]
{{
  "candidates": [
    {{
      "candidate_id": "draft_a",
      "candidate_type": "draft_a",
      "title": "대표 대본 제목 A",
      "title_options": [
        "호기심 유발형 제목 A1",
        "충격 팩트/숫자형 제목 A2",
        "상식 파괴형 제목 A3"
      ],
      "description": "설명란에 넣을 간략한 문구 (별표나 따옴표 없이 평문 작성)",
      "tags": "#태그1 #태그2 #태그3 #쇼츠",
      "keywords": "키워드1, 키워드2, 키워드3, 키워드4",
      "hook": "첫 3초 후킹 대사",
      "target_viewer": "타겟 시청자층",
      "why_it_can_work": "알고리즘에서 터질 수밖에 없는 이유",
      "main_curiosity_question": "끝까지 보게 만드는 핵심 호기심 질문",
      "structure_summary": "전체 구성 요약 (소재 이해 -> 후킹 -> 상태변화 -> 결말 보상)",
      "draft_script": "실제 나레이션 대본 전체 (공백 포함 420~520자 내외, 팩트와 숫자가 꽉 찬 구어체)",
      "borrowed_reference_structure": "레퍼런스에서 차용한 공식 및 구조 설명"
    }},
    {{
      "candidate_id": "draft_b",
      "candidate_type": "draft_b",
      "title": "대표 대본 제목 B",
      "title_options": [
        "호기심 유발형 제목 B1",
        "충격 팩트/숫자형 제목 B2",
        "상식 파괴형 제목 B3"
      ],
      "description": "설명란에 넣을 간략한 문구 (별표나 따옴표 없이 평문 작성)",
      "tags": "#태그1 #태그2 #태그3 #쇼츠",
      "keywords": "키워드1, 키워드2, 키워드3, 키워드4",
      "hook": "첫 3초 후킹 대사",
      "target_viewer": "타겟 시청자층",
      "why_it_can_work": "알고리즘에서 터질 수밖에 없는 이유",
      "main_curiosity_question": "끝까지 보게 만드는 핵심 호기심 질문",
      "structure_summary": "전체 구성 요약 (소재 이해 -> 후킹 -> 상태변화 -> 결말 보상)",
      "draft_script": "실제 나레이션 대본 전체 (공백 포함 420~520자 내외, 팩트와 숫자가 꽉 찬 구어체)",
      "borrowed_reference_structure": "레퍼런스에서 차용한 공식 및 구조 설명"
    }}
  ]
}}

Reference analysis:
{_json_for_prompt(reference_analysis)}

Reference script ({reference_script_note}):
{reference_script}
""".strip()


def build_final_script_prompt(
    selected_candidate: ScriptCandidate,
    feedback: str = "",
) -> str:
    feedback = feedback.strip()
    feedback_section = feedback if feedback else "No additional feedback."
    return f"""
Rewrite the selected candidate into one final high-tension, viral Korean narration script ready for TTS.

선택된 대본 초안의 탄탄한 팩트, 구체적인 수치(숫자/단위), 체감 비유 환산, 4단계 텐션 구조(후킹-호기심-상태변화-결말보상)를 절대 축소하거나 누락하지 말고 완벽하게 살리면서, 음성 합성(TTS)이 가장 정확하고 감칠맛 나게 읽을 수 있는 최종 낭독 대본으로 다듬으세요.

Return JSON only with this exact shape:
{{
  "final_script": "..."
}}

핵심 원칙:
1. 분량 유지: 공백 포함 400~520자 내외. 핵심 팩트와 수치, 예시를 절대 생략하지 마세요.
2. 구어체 리듬감: 말하듯이 자연스럽고 호흡이 살아있는 구어체 문장으로 다듬되, 쉼표(,)와 마침표(.)를 적절히 배치하여 낭독 시 적절한 호흡과 강세를 살리세요.

Strict TTS rules (절대 엄수):
- all numbers are written in Korean pronunciation (e.g. 160억 -> 백육십억, 6,400개 -> 육천사백 개, 6개 -> 여섯 개, 30번 -> 서른 번, 1/25 -> 이십오분의 일, 35kg -> 삼십오 킬로그램, 150m -> 백오십 미터).
- percent signs are written as 퍼센트 (e.g. 99% -> 구십구 퍼센트).
- parentheses and brackets are removed.
- English words and acronyms are written by Korean pronunciation (e.g. AI -> 에이아이, DNA -> 디엔에이).
- Do not leave percent symbols, Arabic numerals, or English letters in the final_script.
- Keep the narration natural, punchy, and ready to read aloud.

Selected candidate:
{_json_for_prompt(selected_candidate)}

Feedback:
{feedback_section}
""".strip()


def validate_candidate_payload(payload: dict) -> list[ScriptCandidate]:
    try:
        candidates = CandidateGenerationPayload.model_validate(payload).candidates
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    if len(candidates) == 2:
        return candidates

    draft_candidates = [c for c in candidates if str(c.candidate_type).startswith("draft_")]
    if len(draft_candidates) >= 2:
        return draft_candidates[:2]

    if len(candidates) == 4:
        same_topic_count = sum(
            1 for candidate in candidates if candidate.candidate_type == "same_topic"
        )
        different_topic_count = sum(
            1 for candidate in candidates if candidate.candidate_type == "different_topic"
        )
        if (
            same_topic_count != 1
            or different_topic_count != 3
            or candidates[0].candidate_type != "same_topic"
        ):
            raise ValueError(
                "candidate payload must include one same_topic and three different_topic "
                "candidates, with the same_topic candidate first"
            )
        return candidates

    if len(candidates) > 2:
        return candidates[:2]

    raise ValueError("candidate payload must include either 2 draft candidates or 4 candidates")


def extract_final_script(payload: dict) -> str:
    try:
        return FinalScriptPayload.model_validate(payload).final_script.strip()
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def validate_final_script(script: str) -> TtsValidationResult:
    issues: list[str] = []
    if re.search(r"[A-Za-z]", script):
        issues.append("English letters remain")
    if re.search(r"\d", script):
        issues.append("Arabic numerals remain")
    if "%" in script:
        issues.append("Percent symbol remains")
    if re.search(r"[\(\)\[\]\{\}]", script):
        issues.append("Bracket characters remain")

    return TtsValidationResult(is_valid=not issues, issues=issues)


def build_final_script_state(
    selected_candidate_id: str,
    feedback: str,
    final_script: str,
) -> FinalScriptState:
    final_script = final_script.strip()
    return FinalScriptState(
        selected_candidate_id=selected_candidate_id,
        feedback=feedback.strip(),
        final_script=final_script,
        tts_validation=validate_final_script(final_script),
    )
