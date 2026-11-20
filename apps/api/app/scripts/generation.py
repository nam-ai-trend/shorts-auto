from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.scripts.models import (
    FINAL_SCRIPT_MAX_LENGTH,
    FinalScriptState,
    LoopDesign,
    LoopValidationResult,
    ScriptCandidate,
    TtsValidationResult,
    clean_text,
)


class CandidateGenerationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[ScriptCandidate] = Field(min_length=2, max_length=4)


class FinalScriptPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    final_script: str = Field(max_length=FINAL_SCRIPT_MAX_LENGTH)
    display_script: str = Field(default="", max_length=FINAL_SCRIPT_MAX_LENGTH)
    loop_tail_bridge: str = Field(default="", max_length=500)
    connected_preview: str = Field(default="", max_length=1200)

    @field_validator("final_script")
    @classmethod
    def clean_final_script(cls, value: str) -> str:
        return clean_text(value, "final_script", FINAL_SCRIPT_MAX_LENGTH)


class CandidateRefinementItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidate_id: str
    tail_bridge: str = Field(default="", max_length=500)
    connected_preview: str = Field(default="", max_length=1200)
    loop_type: str = Field(default="원인/결론 브릿지형 (완결 순환 ⭐)", max_length=100)
    refined_draft_script: str = Field(default="", max_length=FINAL_SCRIPT_MAX_LENGTH)
    refined_display_script: str = Field(default="", max_length=FINAL_SCRIPT_MAX_LENGTH)


class CandidatesLoopRefinementPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    refinements: list[CandidateRefinementItem] = Field(default_factory=list)


class FinalScriptLoopRefinementPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tail_bridge: str = Field(default="", max_length=500)
    connected_preview: str = Field(default="", max_length=1200)
    loop_type: str = Field(default="원인/결론 브릿지형 (완결 순환 ⭐)", max_length=100)
    refined_final_script: str = Field(default="", max_length=FINAL_SCRIPT_MAX_LENGTH)
    refined_display_script: str = Field(default="", max_length=FINAL_SCRIPT_MAX_LENGTH)


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
3. 🔥 팩트 기반 수치 & 주제 맞춤형 체감 환산:
   - 원본 대본의 팩트를 생생하게 전달할 수 있는 구체적인 수치(숫자, 단위)와 주제의 물리적 크기/스케일에 딱 맞는 직관적인 일상 사물 비교를 결합하세요.
   - 특정 건물이나 장소를 기계적으로 쓰지 말고, 해당 주제의 과학적 원리와 스케일에 가장 자연스럽게 어울리는 사물(무게, 길이, 부피, 시간, 전압 등)을 모델이 직접 판단하여 환산하세요.
   - 모든 수치와 비교는 실제 과학적 사실과 수학적 단위 환산(곱셈/나눗셈)에 기반해야 하며, 근거 없는 임의의 과장이나 날조는 절대 금지합니다.
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

### 🔥 [가장 중요한 핵심 목표: 빈약함 탈피 & 팩트 기반 수치 비교]
기존의 쇼츠 대본이 밋밋하고 빈약했던 이유는 구체적인 사실(Fact)과 체감 수치(Figure) 없이 추상적인 설명만 늘어놓았기 때문입니다.
이번 대본은 시청자가 1초도 눈을 뗄 수 없는 **정밀한 과학적 팩트와 철저히 계산된 체감 환산 수치**를 반드시 담아야 합니다.

### [🚨 최우선 필수 출력 조건: 2개 버전(TTS 낭독용 vs 화면 렌더링 자막용) 동시 생성 엄수!]
모든 대본 후보는 반드시 아래 2가지 버전(draft_script 와 display_script)을 1:1 완벽히 일치하는 문장 구조로 동시에 작성해야 합니다:
- [버전 1: draft_script (TTS 성우 낭독용)]: 보이스 엔진이 읽을 대본이므로, 모든 숫자와 영어를 100% '말하듯이 한글 발음'으로 표기하세요 (예: 이천이십삼년, 디엔에이, 일밀리미터, 영쩜일마이크로미터, 수백만원짜리).
- [버전 2: display_script (화면 렌더링 자막용)]: 시청자 화면 하단에 띄울 실제 자막이므로, 시각적 직관성과 가독성을 위해 '실제 아라비아 숫자와 영문 약어'로 표기하세요 (예: 2023년, DNA, 1mm, 0.1마이크로미터, 수백만 원).

[티티에스(TTS) 최적화 포맷 세부 규칙 (draft_script 및 hook 전용)]:
1. 🔢 한국어 맥락 맞춤 숫자 한글화 (한자어 수사 vs 고유어 수사 구분 엄수!):
   - 한국어는 뒤에 붙는 '단위'의 성격에 따라 읽는 방식이 완전히 달라지므로 문맥에 맞게 정확히 구별하세요:
     * [그룹 1: 계측/과학/날짜/시간(분, 초)/화폐 ➔ 반드시 한자어 수사(일, 이, 삼, ..., 십, 백, 천...)]
       - 과학/길이/무게/부피 단위: 마이크로미터, 밀리미터, 센티미터, 미터, 킬로미터, 그램, 킬로그램, 리터, 나노미터 등
         (예: 10마이크로미터 -> 십마이크로미터 [절대 '열마이크로미터' 금지!], 10킬로미터 -> 십킬로미터, 10그램 -> 십그램)
       - 시간(분, 초), 날짜, 화폐, 비율: 초, 분, 년, 월, 일, 원, 퍼센트, 배(배수)
         (예: 10초 -> 십초 [열초 금지!], 10분 -> 십분 [열분 금지!], 10퍼센트 -> 십퍼센트 [열퍼센트 금지!], 10배 -> 십배, 2023년 -> 이천이십삼년, 6천만원 -> 육천만원)
     * [그룹 2: 시(時), 나이 ➔ 반드시 고유어 수사(한, 두, 세, 네, ..., 열, 스물...)]
       - 시간의 '시': 10시 10분 -> 열시 십분 [앞의 '시'는 고유어 '열시', 뒤의 '분'은 한자어 '십분'으로 구분! 절대 '열시열분'이나 '십시십분' 금지!]
       - 나이: 10살 -> 열살
     * [그룹 3: 일상 개수/수량 단위 (개, 마리, 명, 번, 겹, 알, 장 등)]
       - 1~10의 작은 수량: 문맥에 맞게 자연스러운 구어체 적용 (예: 3개 -> 세개, 10개 -> 열개, 10마리 -> 열마리, 10번 -> 열번)
       - 20 이상의 큰 수량: 쇼츠 나레이션 전달력을 위해 한자어 발음 우선 (예: 20개 -> 이십개, 30개 -> 삼십개, 50겹 -> 오십겹, 50알 -> 오십알)
   - [🚨 단위 붙여쓰기 규칙 (숫자와 단위 사이만 붙여쓰기)]:
     * 오직 '숫자(한자어, 고유어 불문)'와 '뒤따르는 단위 명사' 사이만 무조건 붙여 쓰세요!
     * ❌ 단위 띄어쓰기 금지 예시: '한 겹씩', '한 조각씩', '한 마리', '수십 알', '오십 겹', '일 밀리미터', '삼십 개', '육천만 원'
     * ⭕ 올바른 단위 붙여쓰기: '한겹씩', '한조각씩', '한마리', '수십알', '오십겹', '일밀리미터', '삼십개', '육천만원'
     * [⚠️ 중요! 단어 간 일반 띄어쓰기 철저 보존]: 위 규칙은 '숫자+단위'에만 적용됩니다! 문장 내 명사, 조사, 동사, 형용사 등 일반 단어 사이의 띄어쓰기(예: "수백만원짜리 천연 진주를 반으로 쪼개면")는 반드시 지켜야 합니다. 문장 전체의 띄어쓰기를 없애고 다닥다닥 붙여 쓰는 것은 절대 금지합니다!
   - [소수점 '쩜' 표기]: 소수점은 '점'이 아니라 반드시 '쩜'으로 표기하세요! (예: 0.1 -> 영쩜일, 0.03 -> 영쩜영삼, 0.5밀리미터 -> 영쩜오밀리미터, 2.5초 -> 이쩜오초)
   - [분수 및 범위]: 1/150 -> 백오십분의 일, 30~50개 -> 삼십에서 오십개
2. 🔣 기호 변환:
   - 퍼센트 기호(%)는 반드시 '퍼센트'로 풀어서 기재하세요. (예: 99% -> 구십구퍼센트)
   - 물결표(~), 슬래시(/), 대시(-) 등 특수기호는 기호 그대로 두지 말고 말하듯이 한글로 풀어서 작성하세요.
3. 🚫 괄호 및 특수문자 제거:
   - 소괄호(), 대괄호[], 중괄호{{}} 등 모든 괄호 기호는 대본 읽기에 방해되므로 대본에서 완전히 제거하세요.
4. 🔤 영어 한글화:
   - 모든 영어 단어와 약어는 철자 대신 '읽히는 발음 그대로' 한글로 적으세요.
     (예: DNA -> 디엔에이, AI -> 에이아이, TDD -> 티디디, G-Stack -> 쥐스택, CLAUDE.md -> 클로드 쩜 엠디, mm -> 밀리미터, km -> 킬로미터, mg -> 밀리그램)
5. ❌ 아라비아 숫자(0~9)와 영문 알파벳(A~Z, a~z), 기호(%, () 등)가 대본 본문에 단 하나라도 남아있으면 안 됩니다!

### [대본 작성 5대 절대 규칙]
1. 🎯 정밀한 마이크로 팩트 & 구조적 디테일 (Micro Facts & Detail):
   - "엄청 빠릅니다", "놀랍습니다", "대단합니다" 같은 추상적이고 뻔한 수식어는 절대 금지!
   - 해당 주제의 미세한 과학적/생물학적/물리적 메커니즘과 정밀한 수치를 최소 2개 이상 구체적으로 포함하세요.
   - 예시: "초당 30번 진동하는 톱날침", "물 한 방울의 25분의 1인 2마이크로리터", "약산성 비가 바위를 녹여 나트륨을 배출", "뇌가 하루에 내리는 35,000번의 결정" 등.

2. 🔥 압도적인 매크로 스케일 & 주제 맞춤형 체감 단위 환산 (Contextual Fact-checked Comparison):
   - 전체 총량(억/조 단위 등)이나 거대한 규모를 말할 때는, 시청자가 머릿속에 즉시 그릴 수 있는 일상적 시각 단위로 반드시 환산하세요.
   - [엄격한 환산 원칙]:
     * 특정 랜드마크(63빌딩 등)나 고정된 장소(수영장 등)를 습관적으로 반복 사용하지 마세요!
     * 주제의 물리량(미세 질량, 거대 부피, 전압, 시간, 속도 등)에 가장 잘 어울리는 일상 사물을 AI가 직접 선정하여 정확한 수학적 단위 환산(곱셈/나눗셈)을 거친 뒤 비교하세요.
       (예: 미세 질량/크기 -> 머리카락 두께, 물 한 방울, 스마트폰 무게 / 거대 질량/에너지 -> 아프리카 코끼리, 여객기, 벼락 전압 등)
     * 모든 수치와 비교는 실제 과학 데이터와 사실에 부합해야 합니다. 그럴듯하다고 숫자를 지어내거나(할루시네이션) 과장하지 마세요.

3. 🎢 쇼츠 떡상 4단계 텐션 빌드업 (Pacing & Hooking):
   - [0~3초: 🚀 직진형 다이렉트 후킹 (🚨 엄수!)]:
     * ❌ 시간 끄는 늘어지는 서두 절대 금지: "만약 여러분이...", "만약 여러분은...", "혹시 여러분...", "여러분, ...", "혹시 아시나요?" 등 지루한 시청자 호출 및 전제 깔기 절대 금지!
     * ⭕ 0초 재생 즉시 핵심 대상, 구체적 명사/수치/동작으로 곧바로 직격할 것!
       - ❌ 금지: "만약 여러분이 수백만 원짜리 천연 진주를 반으로 쪼갠다면!"
       - ⭕ 올바른 직진형 후킹: "수백만 원짜리 천연 진주를 반으로 쪼갠다면, 그 속에서 모래알 대신 끔찍한 벌레 사체를 보게 됩니다!"
     * 시청자가 당연하게 생각하는 상식을 첫 문장부터 단숨에 부수며 스크롤을 멈추게 만드세요.
   - [3~15초: 의문 심화 & 관찰 포인트] 시청자가 예측하지 못한 의외의 질문과 낯선 관찰 포인트를 던져 "대체 왜?" 호기심 갭 극대화.
   - [15~35초: 상태 변화 & 팩트 폭탄] 설명조로 늘어지지 않고, "더 소름 돋는 건...", "그런데 여기서 반전이 일어납니다"처럼 국면이 바뀌는 전환점과 함께 미세 팩트와 작동 원리를 쉴 틈 없이 전개.
   - [35~50초: 결말 인지 보상 & 브릿지] 압도적 총량과 체감 환산 수치로 지적 카타르시스를 주고, 아래 5번의 무한 루프 꼬리 브릿지로 연결.

4. ⏱️ 대본 분량 및 구어체 어조 (엄수!):
   - 분량: 각 draft_script는 **45~55초 분량 (공백 포함 420자 ~ 520자 내외, 8~10개 문장)**으로 꽉 찬 밀도로 작성하세요. (250~350자는 너무 짧아 내용이 빈약해지니 절대 금지!)
   - 어조: 시청자에게 직접 속삭이듯 말하는 찰진 구어체 낭독 톤 ("~거든요!", "~다니까요!", "~죠?", "~해요!", "~아니에요!"). 딱딱한 백과사전/보고서식 서술형 문장(~다, ~했다, ~이다, ~것이다) 절대 금지.

5. 🎬 강렬하고 완성도 높은 결말(Impactful Outro) & 🛡️ 팩트체크 QA 절대 규칙:
   - [🚨 규칙 1: 대본 시작 문장 = hook 완벽 일치 & 직진형 다이렉트 후킹]:
     * 각 draft_script의 맨 첫 문장은 반드시 메타데이터의 `hook` 대사와 토시 하나 틀리지 않고 100% 동일하게 시작해야 합니다.
     * [🚨 후킹 시작어 절대 금지]: `hook`의 시작에 "만약 여러분이", "혹시 여러분", "여러분은", "여러분" 같은 군더더기 말은 절대 포함하지 마세요! 첫 단어부터 핵심 명사/소재로 시작하세요.
   - [🚨 규칙 2: 자연스럽고 완성도 높은 완결형 결말(Impactful Outro)]:
     * 쇼츠 본문의 핵심 결론이나 충격적 교훈을 담아, 듣는 사람이 깊은 인상을 받도록 깔끔한 완결형 문장으로 당당하게 끝맺으세요.
     * [❌ 절대 금지]:
       - 첫 문장(hook)을 대본 끝에 억지로 다시 복사해 붙이는 행위 절대 금지!
       - 쉼표(,)나 미완성 문장(~하는,, ~된,, ~위해,)으로 어색하게 끝내는 행위 절대 금지! 온전한 마침표나 느낌표, 물음표로 완결성 있게 끝맺으세요.
   - [🚨 규칙 3: 팩트체크 & 물리/수학 단위 환산 엄수]:
     * 충격파 속도, 중력 변화, 질량, 면적 등 모든 수치는 실제 물리 법칙과 과학적 사실에 부합해야 합니다.
     * 암석 충격파 속도가 초당 1,200km라거나(실제 암석 내 지진파 속도는 초당 5~8km 내외), 중력 가속도와 힘/무게 환산이 엉터리인 황당한 날조(할루시네이션)는 절대 금지합니다.
     * 실제 학술 데이터와 정확한 산수(곱셈/나눗셈)로 검산된 수치만 사용하고, 그 근거를 `fact_check_qa`에 명시하세요.

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
     * 1) 호기심/궁금증 유발형 (예: "전 세계 개미의 총 무게를 달아봤더니?")
     * 2) 충격 팩트/숫자 환산형 (예: "전 세계 개미의 무게가 인류 전체 무게와 같다고?")
     * 3) 상식 파괴/도파민형 (예: "기껏해야 작은 벌레? 개미 떼의 충격적인 진실")
2. title:
   - 위 3가지 옵션 중 가장 어그로와 후킹이 강력한 대표 제목 1개.
3. description (설명란 문구):
   - 영상 내용을 간략히 2~3줄로 요약한 유튜브 설명란 텍스트.
   - [중요!] 마크다운 별표(**)나 큰따옴표("), 작은따옴표(')는 절대 사용하지 말고 순수 평문으로만 작성하세요.
4. tags (해시태그):
   - #키워드1 #키워드2 #키워드3 형태로 띄어쓰기로 구분된 핵심 해시태그 목록. [주의] #쇼츠 또는 #shorts 해시태그는 절대 포함하지 마세요.
5. keywords (검색 키워드):
   - 키워드1, 키워드2, 키워드3, 키워드4 형태로 쉼표로 구분된 핵심 검색 키워드 4개를 먼저 작성하고, 맨 뒤에 과학쇼츠, 쇼츠, 과학지식 3개를 필수로 추가하세요 (해시태그 # 없이 순수 키워드로 작성). (예: 키워드1, 키워드2, 키워드3, 키워드4, 과학쇼츠, 쇼츠, 과학지식)

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
      "tags": "#태그1 #태그2 #태그3",
      "keywords": "키워드1, 키워드2, 키워드3, 키워드4, 과학쇼츠, 쇼츠, 과학지식",
      "hook": "첫 0~3초 직진형 후킹 대사 (반드시 시청자에게 직접 말하는 생생한 구어체로 작성할 것! 예: '~아니에요!', '~알고 계셨나요?', '~보게 됩니다!')",
      "target_viewer": "타겟 시청자층",
      "why_it_can_work": "알고리즘에서 터질 수밖에 없는 이유",
      "main_curiosity_question": "끝까지 보게 만드는 핵심 호기심 질문",
      "structure_summary": "전체 구성 요약 (소재 이해 -> 후킹 -> 상태변화 -> 결말 보상)",
      "draft_script": "실제 나레이션 대본 전체 (공백 포함 420~520자. 위 티티에스 최적화 포맷을 엄수하여 숫자/영문 없이 100% 한글 구어체로 작성. 반드시 위 hook으로 시작하고 0초 첫 문장으로 자연스럽게 순환되도록 끝맺을 것)",
      "display_script": "화면 렌더링 자막용 대본 (시청자 화면 자막용: 아라비아 숫자 2023년, DNA, 1mm 표기)",
      "borrowed_reference_structure": "레퍼런스에서 차용한 공식 및 구조 설명",
      "fact_check_qa": [
        {{
          "claim": "대본에 포함된 첫 번째 핵심 과학/수치 주장",
          "status": "verified",
          "evidence": "수학적 계산 및 실제 학술/과학 사실에 기반한 명확한 검증 근거"
        }},
        {{
          "claim": "대본에 포함된 두 번째 핵심 과학/수치 주장",
          "status": "verified",
          "evidence": "수학적 계산 및 실제 학술/과학 사실에 기반한 명확한 검증 근거"
        }}
      ],
      "loop_design": {{
        "loop_type": "원인/결론 브릿지형 또는 질문 순환형",
        "tail_bridge": "대본 맨 마지막 문장 (0초 첫 문장으로 이어지는 완전한 문장. 예: '이것이 바로 우리 뇌가 번쩍 깨달음을 얻는 진짜 이유입니다.' 또는 '도대체 우리 뇌는 왜 이런 신호를 보내는 걸까요?')",
        "head_hook": "대본 첫 문장 후킹 대사",
        "connected_preview": "[tail_bridge] + [head_hook]이 합쳐져 비문 없이 매끄럽게 하나로 이어지는 완전한 1개 문장"
      }}
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
      "tags": "#태그1 #태그2 #태그3",
      "keywords": "키워드1, 키워드2, 키워드3, 키워드4, 과학쇼츠, 쇼츠, 과학지식",
      "hook": "첫 0~3초 직진형 후킹 대사 (반드시 시청자에게 직접 말하는 생생한 구어체로 작성할 것! 예: '~아니에요!', '~알고 계셨나요?', '~보게 됩니다!')",
      "target_viewer": "타겟 시청자층",
      "why_it_can_work": "알고리즘에서 터질 수밖에 없는 이유",
      "main_curiosity_question": "끝까지 보게 만드는 핵심 호기심 질문",
      "structure_summary": "전체 구성 요약 (소재 이해 -> 후킹 -> 상태변화 -> 결말 보상)",
      "draft_script": "실제 나레이션 대본 전체 (공백 포함 420~520자. 위 티티에스 최적화 포맷을 엄수하여 숫자/영문 없이 100% 한글 구어체로 작성. 반드시 위 hook으로 시작하고 0초 첫 문장으로 자연스럽게 순환되도록 끝맺을 것)",
      "display_script": "화면 렌더링 자막용 대본 (시청자 화면 자막용: 아라비아 숫자 2023년, DNA, 1mm 표기)",
      "borrowed_reference_structure": "레퍼런스에서 차용한 공식 및 구조 설명",
      "fact_check_qa": [
        {{
          "claim": "대본에 포함된 첫 번째 핵심 과학/수치 주장",
          "status": "verified",
          "evidence": "수학적 계산 및 실제 학술/과학 사실에 기반한 명확한 검증 근거"
        }},
        {{
          "claim": "대본에 포함된 두 번째 핵심 과학/수치 주장",
          "status": "verified",
          "evidence": "수학적 계산 및 실제 학술/과학 사실에 기반한 명확한 검증 근거"
        }}
      ],
      "loop_design": {{
        "loop_type": "원인/결론 브릿지형 또는 질문 순환형",
        "tail_bridge": "대본 맨 마지막 문장 (0초 첫 문장으로 이어지는 완전한 문장. 예: '이것이 바로 우리 뇌가 번쩍 깨달음을 얻는 진짜 이유입니다.' 또는 '도대체 우리 뇌는 왜 이런 신호를 보내는 걸까요?')",
        "head_hook": "대본 첫 문장 후킹 대사",
        "connected_preview": "[tail_bridge] + [head_hook]이 합쳐져 비문 없이 매끄럽게 하나로 이어지는 완전한 1개 문장"
      }}
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
    current_final_script: str | None = None,
) -> str:
    feedback = feedback.strip()
    candidate_hook = strip_unnecessary_hook_intro(selected_candidate.hook)
    candidate_tail = (
        selected_candidate.loop_design.tail_bridge.strip()
        if selected_candidate.loop_design and selected_candidate.loop_design.tail_bridge
        else ""
    )

    # 사용자가 첫 문장(후킹/오프닝) 수정을 요청했는지 판단
    hook_change_keywords = (
        "시작", "후킹", "첫 문장", "첫문장", "처음", "바꿔", "바꾸", "도입", "오프닝",
        "아시나요", "알고", "믿어지", "어떨까요", "연기", "질문", "먼저"
    )
    is_hook_change_requested = any(kw in feedback for kw in hook_change_keywords) if feedback else False

    if is_hook_change_requested:
        hook_instruction = f"""1. 🚀 [0초 직진형 다이렉트 후킹 (사용자 피드백 최우선 적용 🚨)]:
   - [🚨 최우선 필수 반영 원칙]: 사용자가 첫 문장(후킹/오프닝)을 다음과 같이 시작하거나 변경하라고 명확히 요구했습니다:
     👉 "{feedback}"
   - 따라서 기존 초안의 첫 문장("{candidate_hook}")을 절대 그대로 유지하지 마세요! 사용자가 요구한 후킹 아이디어를 100% 반영하여 시청자의 귀를 단번에 사로잡는 강력한 0초 직진형 첫 문장으로 전면 교체하여 시작하세요!
   - (참고: "만약 여러분이", "혹시 여러분", "여러분" 같은 군더더기 시작어 절대 금지!)"""
    else:
        hook_instruction = f"""1. 🚀 [0초 직진형 다이렉트 후킹 엄수 (시작 문장 고정)]:
   - 대본의 첫 문장은 반드시 아래 확정된 후킹 멘트로 시작해야 합니다:
     👉 "{candidate_hook}"
   - (사용자 피드백에서 첫 문장을 바꾸라고 요구한 경우가 아니라면, 첫 문장을 임의로 변경하지 마세요! "만약 여러분이", "혹시 여러분", "여러분" 같은 군더더기 시작어 절대 금지!)"""
    
    if feedback:
        feedback_directive = f"""### 🚨 [최우선 필수 반영 지시사항: 사용자 대본 수정 피드백 (Strict Priority #1)]
사용자가 대본에 대해 다음과 같은 구체적인 수정을 강력히 요구했습니다:
👉 "{feedback}"

[절대 준수 피드백 반영 규칙]:
1. 위 사용자의 피드백을 최우선(Priority #1)으로 100% 반영하여 대본의 해당 내용, 단어, 수치, 비유, 흐름을 반드시 뜯어고치세요!
2. 사용자가 특정 비유(예: 63빌딩 등)를 빼거나 실제 팩트 수치로 바꾸라고 했다면, 즉시 실제 과학적 사실과 수학적 계산에 맞는 자연스러운 비유/수치로 전면 수정하세요.
3. 사용자의 지시사항을 무시하고 기존 내용을 그대로 복사하는 것은 엄격히 금지됩니다.
4. [완전 일치 지시사항]: 사용자가 피드백에 '똑같이', '완전똑같이', '그대로', '수정 없이' 등을 요구하며 특정 대본이나 문장을 제공한 경우, AI가 임의로 단어나 숫자 표기(예: '이밀리미터', '영쩜영삼기압' 같은 한글 발음 표기 등)를 바꾸지 말고 사용자가 적어준 문장을 100% 동일하게 final_script로 확정하세요."""
    else:
        feedback_directive = """### 💡 [사용자 피드백 없음: 초안 원문의 찰진 구어체 100% 보존 지침]
사용자가 별도의 수정 피드백을 입력하지 않았습니다.
따라서 선택된 초안(Selected candidate의 draft_script)의 문장 구성, 흥미진진한 흐름, 그리고 **맛깔나는 구어체 종결어미(~해요, ~하죠, ~답니다, ~거든요 등)를 절대 임의로 딱딱한 문어체(~다, ~했다, ~이다, ~것이다)로 바꾸지 마세요!**
초안의 자연스럽고 찰진 나레이션 톤을 온전히 살리면서 오직:
1) TTS 성우 발음 최적화(숫자 및 영어를 한국어 맥락 맞춤 한글 발음으로 변환)
2) 문맥에 맞는 자연스러운 띄어쓰기 및 특수문자/괄호 제거
3) 온전한 문장 부호로 끝나는 완성도 높은 마무리
만 정밀하게 다듬어 최종 대본을 완성하세요."""

    current_script_section = ""
    if current_final_script and current_final_script.strip():
        current_script_section = f"""### [현재 생성되어 있는 대본 (Current Script Before Feedback)]:
{current_final_script.strip()}
"""

    return f"""
Rewrite or refine the script into one final high-tension, viral Korean narration script ready for TTS.

{feedback_directive}

{current_script_section}

선택된 대본 초안의 탄탄한 팩트, 구체적인 수치(숫자/단위), 체감 비유 환산, 4단계 텐션 구조(후킹-호기심-상태변화-결말보상)를 절대 축소하거나 누락하지 말고 완벽하게 살리면서, 음성 합성(TTS)이 가장 정확하고 감칠맛 나게 읽을 수 있는 최종 낭독 대본으로 다듬으세요.

### 🎯 [핵심 3대 원칙: 0초 후킹 + 무한 루프 엔딩 + 정밀 띄어쓰기]

{hook_instruction}

2. 🎬 [자연스럽고 완성도 높은 결말(Impactful Outro)]:
   - 쇼츠의 본론을 관통하는 핵심 메시지나 충격적 교훈을 담아, 듣는 사람이 깊은 인상을 받도록 깔끔한 완결형 문장으로 당당하게 끝맺으세요.
   - [❌ 절대 금지]:
     * 첫 문장(hook)을 대본 끝에 억지로 다시 복사해 붙이는 행위 절대 금지!
     * 쉼표(,)나 미완성 문장(~하는,, ~된,, ~위해,)으로 어색하게 끝내는 행위 절대 금지! 온전한 마침표(.)나 느낌표(!), 물음표(?)로 완결성 있게 끝맺으세요.
     * 0초 첫 문장과 호응되지 않는 뜬금없는 독백형 질문이나 낚시성 호객 멘트 금지!

3. ✍️ [단어 간 일반 띄어쓰기 철저 보존 (문장 다닥다닥 붙이기 절대 금지!)]:
   - 단위 명사(개, 겹, 원, 밀리미터 등)만 숫자와 붙여 쓸 뿐, 일반 단어 사이의 띄어쓰기(명사, 동사, 조사 등)는 반드시 한국어 맞춤법에 맞게 정상적으로 띄어 쓰세요! 문장 전체의 공백을 없애는 것은 엄격히 금지됩니다.

4. 🗣️ [🚨 구어체 어조 절대 엄수: 찰진 유튜브 쇼츠 낭독 구어체 (~해요체 / ~하죠체) 필수 & 책/신문 문어체 절대 금지 🚨]:
   - [❌ 책/신문/백과사전식 딱딱한 서술형 문어체 절대 금지]:
     * "~다.", "~했다.", "~이다.", "~시켰다.", "~버티고 있다.", "~건널 수 있는 것이다.", "~할 수 있다." 처럼 딱딱하고 무미건조한 책/보고서/신문 기사 서술형 어미를 절대 쓰지 마세요! 쇼츠 영상은 책을 읽는 게 아니라 시청자의 귓가에 흥미진진하게 속삭여주는 콘텐츠입니다.
   - [⭕ 생동감 넘치는 100% 유튜브 쇼츠 구어체 종결어미 사용]:
     * 선택된 초안(Selected candidate의 draft_script)에 사용된 생생하고 친근한 낭독 어조를 100% 그대로 유지하고 계승하세요!
     * 시청자에게 직접 재미있게 이야기해 주듯 귀에 쏙쏙 박히는 구어체 톤 사용:
       - "~아니에요!", "~잡고 있어요", "~전해주죠", "~지탱한답니다", "~강해요", "~분산시켰죠!", "~통행하는 거죠", "~할 수 있어요", "~거든요!", "~다니까요!"
   - 초안의 맛깔나는 어투와 종결어미를 기계적인 문어체(~다)로 망가뜨리지 말고, 듣기 편안하고 몰입감 넘치는 유튜브 나레이션 구어체로 다듬으세요.

Return JSON only with this exact shape:
{{
  "final_script": "TTS 성우 낭독용 최종 대본 (한글 발음: 이천이십삼년, 디엔에이, 일밀리미터)",
  "display_script": "화면 자막 렌더링용 최종 대본 (시각 자막: 2023년, DNA, 1mm)",
  "loop_tail_bridge": "대본 맨 마지막 완결 문장",
  "connected_preview": "대본 맨 마지막 문장 미리보기"
}}

Strict TTS rules (티티에스 최적화 포맷 절대 엄수):
- all numbers are written in Korean pronunciation (한국어 맥락 맞춤 숫자 한글화 & 단위 붙여쓰기):
  * 과학/계측/초/분/비율: 10마이크로미터 -> 십마이크로미터 ('열마이크로미터' 절대 금지!), 10초 -> 십초 ('열초' 금지!), 10분 -> 십분 ('열분' 금지!), 10퍼센트 -> 십퍼센트, 10배 -> 십배, 2023년 -> 이천이십삼년.
  * 시간/나이: 10시 10분 -> 열시 십분 ('열시열분', '십시십분' 금지!), 10살 -> 열살.
  * 수량/개수: 10개 -> 열개, 10마리 -> 열마리, 10번 -> 열번, 30개 -> 삼십개, 50겹 -> 오십겹.
  * [🚨 단위 붙여쓰기]: 숫자/수사와 단위 명사는 붙여 쓰되 (예: 한겹씩, 한조각씩, 한마리, 수십알, 십마이크로미터, 일밀리미터, 삼십개, 오십겹, 육천만원), 일반 단어 간 띄어쓰기는 반드시 유지하세요!
- 소수점 표기: 소수점은 '점'이 아니라 반드시 '쩜'으로 표기하세요 (예: 0.1 -> 영쩜일, 0.03 -> 영쩜영삼, 0.5밀리미터 -> 영쩜오밀리미터).
- percent signs are written as 퍼센트 (퍼센트 기호(%)는 '퍼센트'로 풀어서 기재하고 붙여 쓰세요. 예: 99% -> 구십구퍼센트).
- parentheses and brackets are removed (소괄호(), 대괄호[] 등 모든 괄호 기호는 최종 대본에서 완전히 제거하세요).
- English words and acronyms are written by Korean pronunciation (모든 영어 단어와 약어는 철자 대신 '읽히는 발음 그대로' 한글로 적으세요. 예: DNA -> 디엔에이, AI -> 에이아이, TDD -> 티디디, G-Stack -> 쥐스택, CLAUDE.md -> 클로드 쩜 엠디).
- Do not leave percent symbols, Arabic numerals, or English letters in the final_script.

Selected candidate:
{_json_for_prompt(selected_candidate)}

Feedback:
{feedback if feedback else "No additional feedback."}
""".strip()


def convert_number_to_korean(n: int) -> str:
    if n == 0:
        return "영"
    units = ["", "십", "백", "천"]
    big_units = ["", "만", "억", "조"]
    digits = ["", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구"]

    s = str(n)
    groups = []
    while s:
        groups.append(s[-4:])
        s = s[:-4]

    result = []
    for g_idx, grp in enumerate(groups):
        grp_int = int(grp)
        if grp_int == 0:
            continue
        grp_str = ""
        for i, ch in enumerate(reversed(grp)):
            d = int(ch)
            if d != 0:
                digit_word = digits[d]
                unit_word = units[i]
                if d == 1 and i > 0 and len(grp) <= 2:
                    digit_word = ""
                grp_str = digit_word + unit_word + grp_str
        result.append(grp_str + big_units[g_idx])

    res = "".join(reversed(result))
    return res if res else "영"


def normalize_to_korean_tts(text: str) -> str:
    # 1. 괄호 제거
    text = re.sub(r"[\(\)\[\]\{\}]", "", text)
    # 2. 퍼센트 기호 변환
    text = re.sub(r"%", "퍼센트", text)

    # 3. 영단어 및 단위 치환 (앞뒤에 영문자가 없는 경계: 한글 조사가 붙어도 치환되도록 처리)
    text = re.sub(r"(?i)(?<![a-zA-Z])DNA(?![a-zA-Z])", "디엔에이", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])AI(?![a-zA-Z])", "에이아이", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])TDD(?![a-zA-Z])", "티디디", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])CLAUDE\.md(?![a-zA-Z])", "클로드 쩜 엠디", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])mm(?![a-zA-Z])", "밀리미터", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])cm(?![a-zA-Z])", "센티미터", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])km(?![a-zA-Z])", "킬로미터", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])mg(?![a-zA-Z])", "밀리그램", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])kg(?![a-zA-Z])", "킬로그램", text)
    text = re.sub(r"(?i)(?<![a-zA-Z])ms(?![a-zA-Z])", "밀리초", text)

    # 4. 숫자 범위 물결표: 30~50 -> 삼십에서 오십
    def repl_range(m):
        n1 = convert_number_to_korean(int(m.group(1)))
        n2 = convert_number_to_korean(int(m.group(2)))
        return f"{n1}에서 {n2}"
    text = re.sub(r"(\d+)\s*~\s*(\d+)", repl_range, text)

    # 5. 소수점 처리: 예 0.1 -> 영쩜일, 0.03 -> 영쩜영삼
    digits_kor = {"0": "영", "1": "일", "2": "이", "3": "삼", "4": "사", "5": "오", "6": "육", "7": "칠", "8": "팔", "9": "구"}
    def repl_float(m):
        int_part = m.group(1)
        dec_part = m.group(2)
        int_kor = convert_number_to_korean(int(int_part))
        dec_kor = "".join(digits_kor.get(d, d) for d in dec_part)
        return f"{int_kor}쩜{dec_kor}"
    text = re.sub(r"(\d+)\.(\d+)", repl_float, text)

    # 6. 정수 숫자 치환
    def repl_int(m):
        val = int(m.group(0))
        return convert_number_to_korean(val)
    text = re.sub(r"\d+", repl_int, text)

    # 7. 점 -> 쩜 보정 (숫자 한글화 이후 '영점' -> '영쩜', '일점' -> '일쩜' 등)
    text = re.sub(r"(영|일|이|삼|사|오|육|칠|팔|구)점(영|일|이|삼|사|오|육|칠|팔|구)", r"\1쩜\2", text)

    # 8. 숫자와 단위 사이 공백 정밀 제거 (끔찍한 벌레 등 일반 형용사 오작동 방지 및 단위 100% 붙여쓰기)
    num_words = (
        r"일|이|삼|사|오|육|칠|팔|구|십|백|천|만|억|조|영|쩜|"
        r"한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스물|서른|마흔|쉰|예순|일흔|여든|아흔|"
        r"수십|수백|수천|수만|수억|수천만|수백만|수십만|두세|서너|너덧|대여섯|몇"
    )
    units = (
        r"밀리미터|센티미터|미터|킬로미터|마이크로미터|마이크로리터|나노미터|그램|킬로그램|밀리그램|"
        r"초|분|시간|일|년|개|겹|번|알|장|원|퍼센트|마리|조각|배|가지|단계|통|채|그루|권|병|잔|판|포기|줄"
    )
    particles = r"(?:씩|들|마다|정도|내외|짜리)?(?:은|는|이|가|을|를|에|의|로|으로|과|와)?(?![가-힣])"
    unit_contract_pattern = rf"(?<![가-힣])({num_words})\s+({units}{particles})"
    for _ in range(4):
        text = re.sub(unit_contract_pattern, r"\1\2", text)

    # 9. 디엔에이, 에이아이 등 뒤에 조사나 한글이 붙을 때 띄어쓰기 정돈
    text = re.sub(r"(디엔에이|에이아이|티디디)([가-힣]{2,})", r"\1 \2", text)

    return text


def strip_unnecessary_hook_intro(text: str) -> str:
    cleaned = text.strip()
    # '만약 여러분이', '만약 여러분은', '혹시 여러분이', '여러분,', '여러분 ' 등 군더더기 제거
    pattern = r"^(만약에?\s+)?(혹시\s+)?(여러분이|여러분은|여러분도|여러분)\s*[,]?\s*"
    cleaned = re.sub(pattern, "", cleaned).strip()
    return cleaned


    # 이미 온전한 종결부호(. ? !) 또는 완결된 서술어인 경우 보존
    if re.search(r"[.?!]$", s) or re.search(r"(니다|세요|어요|아요|해요|되죠|하죠|까요|가요|답니다|거든요|있죠|있습니다|때문이죠|이유입니다|말이죠)$", s):
        return s
    # 쉼표로 끝나는 의도적 연결절(~위해, 등)은 보존
    if s.endswith(","):
        return s

    broken_endings = [
        ("말똥말똥한", "이유일지도 모릅니다."),
        ("피곤한", "까닭이죠."),
        ("하는", "이유입니다."),
        ("있는", "이유입니다."),
        ("한", "이유입니다."),
        ("던", "비밀입니다."),
        ("되는", "원리입니다."),
    ]
    for target, suffix in broken_endings:
        if s.endswith(target):
            return f"{s} {suffix}"
    return s




def clean_trailing_hook_duplicate(script: str, hook: str) -> str:
    """대본 끝에 0초 첫 문장의 질문(예: '하루아침에 태양이 사라진다면 어떤 일이 일어날까요')이 중복으로 덧붙은 경우 도려내기"""
    s = script.strip()
    if not hook or not hook.strip():
        return s

    # 0초 첫 문장의 핵심 질문 종결어미 추출 (예: '일어날까요', '벌어질까요', '있을까요', '톤일까요')
    hook_clean = re.sub(r"[?!.,\s]+$", "", hook).strip()
    m_end = re.search(r"([가-힣]{2,6})$", hook_clean)
    if not m_end:
        return s
    end_word = m_end.group(1)

    # 대본 끝부분(마지막 150자 이내)이 이 end_word로 끝나는지 확인
    s_clean_tail = s.rstrip(".,?! ")
    if s_clean_tail.endswith(end_word):
        # 1) 앞 문장 종결(다/죠/요/네/까/바) 뒤에 쉼표 찍고 붙은 중복 찌꺼기 도려내기
        m = re.search(r"(?<=[다죠요네까바])[,\s]+[^,\.!?]{2,50}[,\s]+[^,\.!?]{2,60}" + re.escape(end_word) + r"[\s?!.]*$", s)
        if m:
            s = s[:m.start()].strip()
            if not s.endswith((".", "!", "?")):
                s += "."
            return s

        # 2) 쉼표 없이 바로 첫 문장 복붙 질문이 붙은 경우
        m2 = re.search(r"(?<=[다죠요네까바\.!?])\s*[^,\.!?]{5,60}" + re.escape(end_word) + r"[\s?!.]*$", s)
        if m2:
            s = s[:m2.start()].strip()
            if not s.endswith((".", "!", "?")):
                s += "."
            return s

    return s


def clean_dangling_modifier_tail(text: str, hook: str = "") -> str:
    """대본 끝에 ', 그 ~를 매번 체험하는'처럼 앞 문장이 완결된 뒤 쉼표 찍고 hook 단어가 중복된 꼬리표 찌꺼기만 안전하게 정리"""
    s = text.strip()
    # 앞 문장이 이미 서술어(~예요, ~입니다, ~겁니다)로 끝났는데 뒤에 쉼표 찍고 꼬리표가 덧붙은 극단적 비문 케이스만 감지
    pattern = r"(?<=[다죠요네까바])[,\s]+(?:그\s*)?[^,\.!\?]{2,30}(?:체험하는|말똥말똥한)$"
    m = re.search(pattern, s)
    if m:
        s = s[:m.start()].strip()
        if not s.endswith((".", "!", "?")):
            s += "."
    return s


def _clean_loop_trailing_conjunctions(text: str) -> str:
    # hook 대사가 잘려나가고 끝에 홀로 남은 불완전한 접속사 찌꺼기(예: '...셈이죠. 그래서') 정리
    cleaned = text.strip()
    pattern = r"[\s,]+(그래서|그러니|결국|바로|그렇다면)$"
    cleaned = re.sub(pattern, "", cleaned).strip()
    return cleaned


def sanitize_script_loop_candidate(candidate: ScriptCandidate) -> ScriptCandidate:
    # 0. 0초 직진형 후킹을 위해 '만약 여러분이', '여러분' 등 불필요한 군더더기 서두 제거
    old_hook = candidate.hook.strip()
    new_hook = strip_unnecessary_hook_intro(old_hook)
    candidate.hook = new_hook
    hook = new_hook

    def _sanitize_single_text(text: str, is_tts: bool) -> str:
        s = text.strip()
        if s.startswith(old_hook):
            s = new_hook + s[len(old_hook):]
        else:
            s = strip_unnecessary_hook_intro(s)

        # 1. 스크립트 끝에 hook 대사가 중복으로 붙어있는 경우 잘라내기
        hook_clean = re.sub(r"[?!.,\s]+$", "", hook)
        if hook_clean:
            pattern = re.compile(re.escape(hook_clean) + r"[\s?!.]*$", re.IGNORECASE)
            s = pattern.sub("", s).strip()

        # 2. loop_design의 tail_bridge가 첫 문장과 단순 복붙인 경우만 hook 제거 처리
        # (문장 중간 단어 일치로 대본 뒤를 싹둑 자르는 위험한 prefix 절단은 비문 방지를 위해 배제)
        if candidate.loop_design and candidate.loop_design.tail_bridge:
            tb = candidate.loop_design.tail_bridge.strip()
            tb_clean = re.sub(r"[?!.,\s]+$", "", tb)
            is_tb_repeat = (
                tb_clean == hook_clean
                or (len(hook_clean) >= 10 and (tb_clean in hook_clean or hook_clean in tb_clean))
            )
            if not is_tb_repeat and tb_clean and tb_clean in s:
                idx = s.rfind(tb_clean)
                if len(s) - idx < 100:
                    s = s[: idx + len(tb_clean)].strip()

        # 3. hook 절단 후 홀로 남은 접속사 찌꺼기 제거
        s = _clean_loop_trailing_conjunctions(s)
        s = clean_dangling_modifier_tail(s)
        s = clean_trailing_hook_duplicate(s, hook)

        # 4. 완결형 문장 종결 보장: 끝의 불필요한 쉼표 제거 및 온전한 마침표/종결부호 보장
        s = re.sub(r"[,]+$", "", s).strip()
        if s and not s.endswith((".", "?", "!")):
            s = s + "."

        # 5. TTS 전용인 경우 정규화 적용
        if is_tts:
            s = normalize_to_korean_tts(s)
        return s

    candidate.hook = normalize_to_korean_tts(candidate.hook)
    candidate.draft_script = _sanitize_single_text(candidate.draft_script, is_tts=True)

    # 5. 화면 렌더링 자막용 display_script 보정
    if not candidate.display_script or not candidate.display_script.strip():
        candidate.display_script = candidate.draft_script
    else:
        candidate.display_script = _sanitize_single_text(candidate.display_script, is_tts=False)

    # 6. loop_design 메타데이터 보정 (호환성 유지)
    if candidate.loop_design:
        h_clean = re.sub(r"[?!.,\s]+$", "", candidate.hook).strip()
        clean_draft = candidate.draft_script.strip()
        if h_clean and clean_draft.endswith(h_clean):
            clean_draft = clean_draft[:-len(h_clean)].strip()

        sentences = [s.strip() for s in re.split(r"(?<=[.?!,])\s+", clean_draft) if s.strip()]
        actual_last = sentences[-1] if sentences else ""
        candidate.loop_design.head_hook = candidate.hook
        candidate.loop_design.tail_bridge = actual_last
        candidate.loop_design.loop_type = "완결형 엔딩"
        candidate.loop_design.connected_preview = actual_last

    return candidate


def validate_candidate_payload(payload: dict) -> list[ScriptCandidate]:
    try:
        candidates = CandidateGenerationPayload.model_validate(payload).candidates
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    # 모든 대본 후보에 대해 무한 루프 엔딩 정돈(sanitize) 적용
    candidates = [sanitize_script_loop_candidate(c) for c in candidates]

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


def sanitize_final_script_loop(final_script: str, hook: str = "", tail_bridge: str = "", is_tts: bool = True) -> str:
    script = strip_unnecessary_hook_intro(final_script.strip())
    hook = strip_unnecessary_hook_intro(hook.strip())

    hook_clean = re.sub(r"[?!.,\s]+$", "", hook)
    tb_clean = re.sub(r"[?!.,\s]+$", "", tail_bridge.strip())

    # 1. hook 대사 또는 hook의 핵심 문구가 스크립트 끝에 중복으로 붙어있는 경우 잘라내기
    if hook_clean:
        pattern = re.compile(re.escape(hook_clean) + r"[\s?!.]*$", re.IGNORECASE)
        script = pattern.sub("", script).strip()

    # 2. tail_bridge가 첫 문장과 복붙이 아닌 유효한 브릿지이고 대본 끝부분(100자 이내)에 위치할 때만 뒤에 붙은 군더더기/중복 제거
    is_verbatim_repeat = (
        not tb_clean
        or tb_clean == hook_clean
        or (len(hook_clean) >= 10 and (tb_clean in hook_clean or hook_clean in tb_clean))
    )
    if not is_verbatim_repeat and tb_clean in script:
        idx = script.rfind(tb_clean)
        if len(script) - idx < 100:
            script = script[: idx + len(tb_clean)].strip()

    # 3. hook 절단 후 홀로 남은 접속사 찌꺼기 정리
    script = _clean_loop_trailing_conjunctions(script)
    script = clean_dangling_modifier_tail(script)
    script = clean_trailing_hook_duplicate(script, hook)

    # 4. 완결형 문장 종결 보장: 끝의 불필요한 쉼표 제거 및 온전한 마침표/종결부호 보장
    script = re.sub(r"[,]+$", "", script).strip()
    if script and not script.endswith((".", "?", "!")):
        script = script + "."

    # 5. 티티에스(TTS) 최적화 포맷 정규화
    if is_tts:
        script = normalize_to_korean_tts(script)
    return script


def extract_final_scripts(payload: dict, hook: str = "", tail_bridge: str = "") -> tuple[str, str, str]:
    try:
        validated = FinalScriptPayload.model_validate(payload)
        raw_script = validated.final_script.strip()
        raw_display = validated.display_script.strip() if validated.display_script else raw_script
        
        # 모델이 loop_tail_bridge를 명시적으로 반환한 경우 복붙 여부 검증 후 활용
        cand_tb = validated.loop_tail_bridge.strip() if validated.loop_tail_bridge else ""
        h_clean = re.sub(r"[?!.,\s]+$", "", hook).strip()
        tb_clean = re.sub(r"[?!.,\s]+$", "", cand_tb).strip()
        
        is_repeat = (
            tb_clean == h_clean
            or (len(h_clean) >= 10 and (tb_clean in h_clean or h_clean in tb_clean))
        )
        effective_tail_bridge = tail_bridge if (is_repeat or not cand_tb) else cand_tb
        
        final_script = sanitize_final_script_loop(raw_script, hook, effective_tail_bridge, is_tts=True)
        display_script = sanitize_final_script_loop(raw_display, hook, effective_tail_bridge, is_tts=False)

        # 만약 effective_tail_bridge가 비어있거나 여전히 복붙이면, sanitize된 final_script의 마지막 절 추출
        eff_clean = re.sub(r"[?!.,\s]+$", "", effective_tail_bridge).strip()
        if not eff_clean or eff_clean == h_clean:
            sentences = [s.strip() for s in re.split(r"(?<=[.?!,])\s+", final_script) if s.strip()]
            effective_tail_bridge = sentences[-1] if sentences else ""

        return final_script, display_script, effective_tail_bridge
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def extract_final_script(payload: dict, hook: str = "", tail_bridge: str = "") -> str:
    final_s, _, _ = extract_final_scripts(payload, hook, tail_bridge)
    return final_s


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


def validate_script_loop(
    script: str,
    hook: str = "",
    tail_bridge: str = "",
) -> LoopValidationResult:
    issues: list[str] = []
    clean_s = script.strip()

    # 1. 0초 첫 문장 (head_hook) 결정
    if hook and hook.strip():
        head_hook = strip_unnecessary_hook_intro(hook.strip())
    else:
        # 스크립트의 첫 문장 추출 (마침표/물음표/느낌표 또는 쉼표 기준)
        first_match = re.split(r"[.?!]\s*", clean_s)
        head_hook = first_match[0].strip() if first_match else ""

    hook_clean = re.sub(r"[?!.,\s]+$", "", head_hook).strip()

    # 2. 마지막 꼬리 문장 (tail_bridge) 결정
    tb_clean = re.sub(r"[?!.,\s]+$", "", tail_bridge.strip()).strip()
    is_verbatim_tb = (
        not tb_clean
        or tb_clean == hook_clean
        or (len(hook_clean) >= 10 and (tb_clean in hook_clean or hook_clean in tb_clean))
    )

    if not is_verbatim_tb and tail_bridge.strip() in clean_s:
        actual_tail = tail_bridge.strip()
    else:
        # 스크립트의 마지막 문장/절 추출 (마침표, 물음표, 느낌표, 쉼표 기준 분할)
        sentences = [s.strip() for s in re.split(r"(?<=[.?!,])\s+", clean_s) if s.strip()]
        actual_tail = sentences[-1] if sentences else ""

    actual_tail_clean = re.sub(r"[?!.,\s]+$", "", actual_tail).strip()

    # 3. 중복 복붙 검사 (대본 끝부분에 0초 첫 문장(후킹)이 다시 복붙되었거나 2회 이상 반복되었는지 확인)
    if hook_clean and (
        actual_tail_clean == hook_clean
        or (len(hook_clean) >= 10 and (actual_tail_clean in hook_clean or hook_clean in actual_tail_clean))
    ):
        issues.append("대본 끝에 0초 첫 문장(후킹)이 그대로 중복 복붙되어 있습니다.")
    elif hook_clean and len(hook_clean) >= 10:
        tail_slice = clean_s[max(0, len(clean_s) - len(hook_clean) - 30):]
        if clean_s.count(hook_clean) >= 2 or hook_clean in tail_slice:
            issues.append("대본 끝에 0초 첫 문장(후킹)이 그대로 중복 복붙되어 있습니다.")

    # 4. 무성의한 닫힌 평서문 종결 검사 (브릿지 키워드나 질문형 호응 없이 단순 설명으로 꽉 닫힌 경우)
    bridge_keywords = ("이유", "비밀", "까닭", "원리", "진실", "때문", "말이죠", "당신처럼", "위해", "선택", "결과")
    is_flat_ending = any(actual_tail_clean.endswith(k) for k in ("니다", "어요", "아요", "해요", "거든요", "답니다", "되죠", "하죠"))
    has_bridge = any(kw in actual_tail_clean for kw in bridge_keywords) or actual_tail_clean.endswith(("?", "까요", "가요", "말이죠"))
    if is_flat_ending and not has_bridge:
        issues.append("대본 끝이 평서문 종결형(~합니다/습니다)으로 닫혀 있어 0초 첫 문장으로 이어지지 않고 흐름이 끊깁니다. 질문형이나 원인/결론 브릿지형으로 이어주세요.")

    # 4-1. 서술어 없는 뚝 끊긴 비문 검사 (예: ~한, ~는, ~던 등으로 끝나 뒤에 서술어가 없는 경우)
    bare_tail = actual_tail_clean.rstrip(".,?! ")
    if any(bare_tail.endswith(k) for k in ("말똥말똥한", "피곤한", "하는", "했던", "있는", "되는", "던")) and not any(bare_tail.endswith(k) for k in ("쉬는", "숨만 쉬는")):
        issues.append("대본 끝이 서술어 없이 미완성 수식어(~한, ~는)로 뚝 끊겨 흉측한 비문이 되었습니다. 완전한 문장으로 마무리해주세요.")

    # 5. 불완전 접속사 단독 잔재 검사
    if re.search(r"[\s,]+(그래서|그러니|결국|바로|그렇다면)$", clean_s):
        issues.append("대본 끝이 단독 접속사(그래서/그러니/바로 등)로 부자연스럽게 끊겨 있습니다.")

    # 6. 이중 조건문(~면 ... ~면) 비문 검사
    tail_is_condition = any(actual_tail.endswith(k) for k in ["싶다면,", "싶다면", "면,", "다면,", "라면,"])
    hook_has_condition = any(head_hook.split()[0].endswith(k) or (len(head_hook.split()) > 1 and head_hook.split()[1].endswith(k)) for k in ["면,", "면", "다면,", "라면,"])
    if tail_is_condition and ("쪼개면" in head_hook or hook_has_condition):
        issues.append("끝 문장의 조건 어미(~싶다면)와 첫 문장(~쪼개면)이 겹쳐 이중 조건문 비문이 됩니다. '~하기 위해' 같은 목적절로 이어주세요.")

    # 7. 낚시성 호객 클리셰 검사
    cliche_patterns = [
        r"궁금하다면\s*지금\s*확인",
        r"결과는\s*바로",
        r"비밀은\s*대체\s*뭘까요\s*바로",
        r"소름\s*돋는\s*결과",
    ]
    for pat in cliche_patterns:
        if re.search(pat, actual_tail):
            issues.append(f"낚시성 호객 클리셰 문구('{pat}')가 포함되어 몰입을 해칩니다.")
            break

    # 8. 호응되지 않는 뜬금없는 독백형 질문 검사
    unrelated_questions = [
        r"과연\s*무엇을\s*의미하는\s*걸까요\?",
        r"어떻게\s*된\s*일일까요\?",
        r"과연\s*진짜일까요\?",
    ]
    for q_pat in unrelated_questions:
        if re.search(q_pat, actual_tail):
            issues.append("0초 첫 문장과 호응되지 않는 독백형 질문으로 끝나 루프 흐름이 끊깁니다.")
            break

    # 9. 루프 유형 판별 (loop_type)
    actual_tail_bare = actual_tail_clean.rstrip(".,?! ")
    if any(actual_tail_bare.endswith(k) for k in ["하는", "하고 있는", "있는", "된", "한", "던", "지금도", "순간에도", "숨만 쉬는", "쉬는"]):
        loop_type = "관형절 주어 수식형 (완벽한 순환 ⭐)"
    elif any(k in actual_tail for k in ["풀기 위해", "밝히기 위해", "확인하기 위해", "알아보기 위해", "위해,", "위해"]):
        loop_type = "목적-결과 연결형 (자연스러운 순환 ⭐)"
    elif actual_tail_clean.endswith("?") or actual_tail_bare.endswith(("까요", "가요", "걸까요")):
        loop_type = "질문 순환형 (호기심 극대화 ⭐)"
    elif any(actual_tail_bare.endswith(k) for k in ["이유입니다", "정체입니다", "비밀입니다", "까닭입니다", "때문이죠", "말이죠"]):
        loop_type = "원인/결론 브릿지형 (완결 순환 ⭐)"
    elif any(k in actual_tail for k in ["싶다면", "보고 싶다면", "확인해보고 싶다면", "궁금하다면"]):
        loop_type = "상황 유발 / 행동 촉구형"
    elif any(actual_tail.endswith(k) for k in ["바로,", "바로"]):
        loop_type = "문장 완성형"
    elif any(k in actual_tail for k in ["그래서,", "따라서,"]):
        loop_type = "인과 접속형"
    else:
        loop_type = "일반 서사형"

    # 10. 연결 프리뷰 생성
    connected_preview = f"...{actual_tail} ➔ [{head_hook}]"

    # 11. 종합 판정
    is_valid = len(issues) == 0
    score = 100 if is_valid else max(0, 100 - len(issues) * 35)

    if is_valid:
        evaluation = f"[{loop_type}] 0초 첫 문장과 마지막 문장이 귀에 착 감기며 완벽하게 한 문장으로 이어지는 자연스러운 루프입니다."
    else:
        evaluation = f"[{loop_type}] 연결이 다소 어색합니다: {', '.join(issues)}"

    return LoopValidationResult(
        is_valid=is_valid,
        score=score,
        loop_type=loop_type,
        tail_bridge=actual_tail,
        head_hook=head_hook,
        connected_preview=connected_preview,
        evaluation=evaluation,
        issues=issues,
    )


def build_final_script_state(
    selected_candidate_id: str,
    feedback: str,
    final_script: str,
    display_script: str = "",
    hook: str = "",
    tail_bridge: str = "",
) -> FinalScriptState:
    final_script = final_script.strip()
    display_script = display_script.strip() if display_script else final_script
    effective_hook = hook
    if not effective_hook or not final_script.startswith(effective_hook):
        first_sentence = re.split(r"(?<=[.?!])\s+", final_script)[0].strip()
        if first_sentence:
            effective_hook = first_sentence

    return FinalScriptState(
        selected_candidate_id=selected_candidate_id,
        feedback=feedback.strip(),
        final_script=final_script,
        display_script=display_script,
        tts_validation=validate_final_script(final_script),
        loop_validation=validate_script_loop(final_script, hook=effective_hook, tail_bridge=tail_bridge),
    )


def extract_verbatim_script_from_feedback(feedback: str) -> str | None:
    lines = [line.strip() for line in feedback.strip().splitlines() if line.strip()]
    if not lines:
        return None
    first_line = lines[0].lower()
    trigger_words = ["똑같이", "완전똑같이", "그대로", "아래와 같이", "아래 대본", "직접 작성", "수정 없이"]
    if any(tw in first_line for tw in trigger_words) and len(lines) > 1:
        body = "\n".join(lines[1:]).strip()
        if len(body) >= 50:
            return body
    return None


def build_candidates_loop_refinement_prompt(candidates: list[ScriptCandidate]) -> str:
    cands_summary = []
    for c in candidates:
        cands_summary.append({
            "candidate_id": c.candidate_id,
            "title": c.title,
            "hook": c.hook,
            "draft_script": c.draft_script,
            "display_script": c.display_script,
        })
    cands_json = json.dumps(cands_summary, ensure_ascii=False, indent=2)

    return f"""당신은 대한민국 최고의 유튜브 쇼츠 바이럴 기획자이자 무한 루프(Seamless Loop) 엔딩 전문 오디오/텍스트 에디터입니다.
아래 1차로 작성된 쇼츠 대본 2종(Draft A, Draft B)의 전체 문맥과 각 대본의 '0초 첫 문장(hook)'을 분석하여, **대본의 맨 마지막 문장(꼬리)을 0초 첫 문장과 소름 돋게 하나로 이어지는 완벽한 1개의 문장**으로 정밀 수정하는 [2차 무한 루프 정밀 결합] 작업을 수행하세요.

### 🏆 [무한 루프(Seamless Loop) 엔딩 골든 스탠다드 레퍼런스 - 0초 첫 문장과 완벽히 이어지는 수미상관 설계]:
아래 1차 대본의 마지막 문장을 0초 첫 문장과 소름 돋게 하나로 이어지는 완벽한 1개의 문장으로 정밀 다듬기하세요!

⭕ [소재에 맞게 선택할 핵심 결합 공식 2가지]:
1. [공식 A: 관형절 주어/목적어 수식형 (수미상관형 ⭐⭐⭐)]:
   대본 끝을 0초 첫 문장의 첫 단어/주어를 수식하는 형태(~하는, ~한, ~돋는 등)로 끝맺으세요!
   🚨 [동어반복 절대 금지]: 0초 첫 문장의 첫 단어(예: '‘아하!’ 순간')를 꼬리 브릿지에서 그대로 반복하지 마세요!
   * ❌ 나쁜 예: `...미스터리한 기적이에요, 그 ‘아하’ 순간을 매번 체험하는 [0초] ‘아하!’ 순간, 뇌에서 무슨 일이 벌어질까요?` (동어반복 비문 탈락!)
   * ⭕ 완벽한 예 1: `...결국 수십억 개의 신경세포가 일제히 연결되며 온몸에 전율이 돋는, [0초] ‘아하!’ 순간, 뇌에서 무슨 일이 벌어질까요?`
   * ⭕ 완벽한 예 2 (레퍼런스): `...대왕고래 3마리보다 더 무겁다는 사실! 하루 종일 숨만 쉬는 [0초] 내가 평생 들이마시는 공기를 모두 모으면 몇 톤일까요?`
2. [공식 B: 목적/이유 연결 브릿지형 (시청 지속형 ⭐⭐⭐)]:
   0초 첫 문장이 의문/질문형일 때, 대본 끝을 목적절이나 조건절(~알고 싶다면,, ~비밀을 풀기 위해, 등)로 끝맺으세요!
   * ⭕ 완벽한 예: `...이 찰나의 폭발이 어떻게 천재적인 번뜩임을 만들어내는지 알고 싶다면, [0초] ‘아하!’ 순간, 뇌에서 무슨 일이 벌어질까요?`

### ❌ [절대 금지 5대 규칙 - 위반 시 0점 탈락]:
1. 🚨 [문장 완결 강박 및 명사 덧붙이기 절대 금지 ('이야기', '사실', '비밀', '것', '이유' 등)]:
   대본 끝을 '...보여주는 이야기', '...증명하는 사실', '...알 수 있는 이유' 처럼 뜬금없는 명사나 마침표로 닫아버리지 마세요!
   명사로 닫아버리면 0초 첫 문장으로 이어질 때 '...이야기. 만약 태양이 사라진다면...' 처럼 무한 루프가 완전히 끊겨버립니다!
   반드시 0초 첫 문장으로 곧바로 이어지는 열린 관형사형(~하는,) 또는 목적절(~위해,)로 열어둔 채 끝나야 합니다!
2. 🚨 [독립 평서문 종결 금지]:
   '...진짜 비밀입니다.', '...사실이죠.', '...어떨까요?' 처럼 독립된 문장으로 끝내지 마세요! 0초 첫 문장과 한 문장으로 결합해야 합니다.
3. 🚨 [첫 문장 키워드 동어반복 절대 금지]: 대본 끝 문장에 첫 문장의 핵심 단어를 그대로 넣거나 똑같은 말을 무성의하게 반복하지 마세요!
4. 🚨 [꼬리표 덧붙이기 금지]: 앞 문장을 다 끝내놓고 뒤에 쉼표(,) 찍고 억지로 수식어만 매달지 마세요! 대본 본문의 마지막 문장 자체가 0초 첫 문장을 향해 유기적으로 이어져야 합니다.
5. 🚨 [본문 보존 원칙]: 1차로 공들여 쓴 본문의 팩트, 수치, 설명은 그대로 보존하고, **오직 맨 마지막 1개 문장(꼬리)만** 위 결합 공식에 맞게 자연스럽게 마무리하세요!
6. [TTS vs 자막 포맷 일치]: refined_draft_script(한글 발음 숫자/영어 표기)와 refined_display_script(아라비아 숫자 2023년, DNA 표기) 둘 다 마지막 문장을 1:1 완벽히 일치하게 교체하세요.

[1차 생성된 대본 목록]:
{cands_json}

Return JSON only with this exact shape:
{{
  "refinements": [
    {{
      "candidate_id": "draft_a",
      "tail_bridge": "0초 첫 문장으로 매끄럽게 이어지는 마지막 문장 (예: '...수십억 개 신경망이 순식간에 불을 켜며 온몸에 전율이 돋는,' 또는 '...이 경이로운 현상의 비밀을 밝히기 위해,')",
      "connected_preview": "...[tail_bridge] ➔ [0초 첫 문장]",
      "loop_type": "관형절 주어 수식형 (완벽한 순환 ⭐)",
      "refined_draft_script": "마지막 문장이 tail_bridge로 매끄럽게 교체된 전체 TTS 대본",
      "refined_display_script": "마지막 문장이 tail_bridge로 매끄럽게 교체된 전체 화면 자막 대본"
    }},
    {{
      "candidate_id": "draft_b",
      "tail_bridge": "0초 첫 문장으로 매끄럽게 이어지는 마지막 문장 (예: '...수십억 개 신경망이 순식간에 불을 켜며 온몸에 전율이 돋는,' 또는 '...이 경이로운 현상의 비밀을 밝히기 위해,')",
      "connected_preview": "...[tail_bridge] ➔ [0초 첫 문장]",
      "loop_type": "관형절 주어 수식형 (완벽한 순환 ⭐)",
      "refined_draft_script": "마지막 문장이 tail_bridge로 매끄럽게 교체된 전체 TTS 대본",
      "refined_display_script": "마지막 문장이 tail_bridge로 매끄럽게 교체된 전체 화면 자막 대본"
    }}
  ]
}}""".strip()


def refine_candidates_loop(
    client: Any,
    candidates: list[ScriptCandidate],
) -> list[ScriptCandidate]:
    if not candidates:
        return candidates
    try:
        prompt = build_candidates_loop_refinement_prompt(candidates)
        raw_res = client.analyze(prompt)
        payload = CandidatesLoopRefinementPayload.model_validate(raw_res)
        ref_map = {item.candidate_id: item for item in payload.refinements}

        for cand in candidates:
            ref = ref_map.get(cand.candidate_id)
            if not ref:
                continue
            if ref.refined_draft_script and ref.refined_draft_script.strip():
                cand.draft_script = ref.refined_draft_script.strip()
            if ref.refined_display_script and ref.refined_display_script.strip():
                cand.display_script = ref.refined_display_script.strip()
            if cand.loop_design is None:
                cand.loop_design = LoopDesign(
                    tail_bridge=ref.tail_bridge,
                    head_hook=cand.hook,
                    connected_preview=ref.connected_preview or f"...{ref.tail_bridge} ➔ [{cand.hook}]",
                    loop_type=ref.loop_type or "관형절 주어 수식형 (완벽한 순환 ⭐)",
                )
            else:
                if ref.tail_bridge:
                    cand.loop_design.tail_bridge = ref.tail_bridge
                if ref.loop_type:
                    cand.loop_design.loop_type = ref.loop_type
                cand.loop_design.connected_preview = ref.connected_preview or f"...{cand.loop_design.tail_bridge} ➔ [{cand.hook}]"

            # 2차 수정 후 최종 안전망 통과
            cand = sanitize_script_loop_candidate(cand)
    except Exception:
        # 2차 호출 실패 시 1차 candidate 유지 및 fallback sanitize
        candidates = [sanitize_script_loop_candidate(c) for c in candidates]

    return candidates


def build_final_script_loop_refinement_prompt(
    hook: str,
    final_script: str,
    display_script: str,
) -> str:
    return f"""당신은 대한민국 최고의 유튜브 쇼츠 바이럴 기획자이자 무한 루프(Seamless Loop) 엔딩 전문 오디오/텍스트 에디터입니다.
아래 1차로 완성된 최종 쇼츠 대본 전체 문맥과 확정된 '0초 첫 문장(hook)'을 분석하여, **대본의 맨 마지막 문장(꼬리)을 0초 첫 문장과 소름 돋게 하나로 이어지는 완벽한 1개의 문장**으로 정밀 수정하는 [2차 무한 루프 정밀 결합] 작업을 수행하세요.

### 0초 첫 문장 (hook - 고정):
👉 "{hook}"

### 🏆 [무한 루프(Seamless Loop) 엔딩 골든 스탠다드 레퍼런스 - 0초 첫 문장과 완벽히 이어지는 수미상관 설계]:
아래 최종 대본의 마지막 문장을 0초 첫 문장("{hook}")과 소름 돋게 하나로 이어지는 완벽한 1개의 문장으로 정밀 다듬기하세요!

⭕ [소재에 맞게 선택할 핵심 결합 공식 2가지]:
1. [공식 A: 관형절 주어/목적어 수식형 (수미상관형 ⭐⭐⭐)]:
   대본 끝을 0초 첫 문장의 첫 단어/주어를 수식하는 형태(~하는, ~한, ~돋는 등)로 끝맺으세요!
   🚨 [동어반복 절대 금지]: 0초 첫 문장("{hook}")의 핵심 단어를 꼬리 브릿지에서 그대로 반복하지 마세요!
   * ❌ 나쁜 예: 꼬리에 첫 문장의 단어를 그대로 반복해 읽을 때 두 번 겹치는 비문
   * ⭕ 좋은 예: 첫 문장의 주어/상황을 생생하게 수식하여, 0초 첫 문장과 합쳐졌을 때 물 흐르듯 이어지는 완전한 1개 문장 완성!
2. [공식 B: 목적/이유 연결 브릿지형 (시청 지속형 ⭐⭐⭐)]:
   0초 첫 문장이 의문/질문형일 때, 대본 끝을 목적절이나 조건절(~알고 싶다면,, ~비밀을 풀기 위해, 등)로 끝맺으세요!

### ❌ [절대 금지 5대 규칙 - 위반 시 0점 탈락]:
1. 🚨 [문장 완결 강박 및 명사 덧붙이기 절대 금지 ('이야기', '사실', '비밀', '것', '이유' 등)]:
   대본 끝을 '...보여주는 이야기', '...증명하는 사실', '...알 수 있는 이유' 처럼 뜬금없는 명사나 마침표로 닫아버리지 마세요!
   명사로 닫아버리면 0초 첫 문장으로 이어질 때 '...이야기. 만약 태양이 사라진다면...' 처럼 무한 루프가 완전히 끊겨버립니다!
   반드시 0초 첫 문장으로 곧바로 이어지는 열린 관형사형(~하는,) 또는 목적절(~위해,)로 열어둔 채 끝나야 합니다!
2. 🚨 [독립 평서문 종결 금지]:
   '...진짜 비밀입니다.', '...사실이죠.', '...어떨까요?' 처럼 독립된 문장으로 끝내지 마세요! 0초 첫 문장과 한 문장으로 결합해야 합니다.
3. 🚨 [첫 문장 키워드 동어반복 절대 금지]: 대본 끝 문장에 첫 문장의 핵심 단어를 그대로 넣거나 똑같은 말을 무성의하게 반복하지 마세요!
4. 🚨 [꼬리표 덧붙이기 금지]: 앞 문장을 다 끝내놓고 뒤에 쉼표(,) 찍고 억지로 수식어만 매달지 마세요! 대본 본문의 마지막 문장 자체가 0초 첫 문장을 향해 유기적으로 이어져야 합니다.
5. 🚨 [본문 보존 원칙]: 1차 본문의 탄탄한 과학 팩트와 수치, 설명은 그대로 보존하고, **오직 맨 마지막 1개 문장(꼬리)만** 위 결합 공식에 맞게 자연스럽게 마무리하세요!
6. [TTS vs 자막 포맷 일치]: refined_final_script(한글 발음)와 refined_display_script(숫자/영문) 둘 다 마지막 문장을 1:1 완벽히 일치하게 교체하세요.

[1차 완성된 TTS 낭독 대본]:
{final_script}

[1차 완성된 화면 자막 대본]:
{display_script}

Return JSON only with this exact shape:
{{
  "tail_bridge": "0초 첫 문장으로 매끄럽게 이어지는 마지막 문장 (예: '...수십억 개 신경망이 순식간에 불을 켜며 온몸에 전율이 돋는,' 또는 '...이 경이로운 현상의 비밀을 밝히기 위해,')",
  "connected_preview": "...[tail_bridge] ➔ [{hook}]",
  "loop_type": "관형절 주어 수식형 (완벽한 순환 ⭐)",
  "refined_final_script": "마지막 문장이 tail_bridge로 매끄럽게 교체된 전체 TTS 대본",
  "refined_display_script": "마지막 문장이 tail_bridge로 매끄럽게 교체된 전체 화면 자막 대본"
}}""".strip()


def refine_final_script_loop(
    client: Any,
    hook: str,
    final_script: str,
    display_script: str,
    tail_bridge: str = "",
) -> tuple[str, str, str]:
    refined_final = final_script
    refined_display = display_script
    effective_tb = tail_bridge

    try:
        prompt = build_final_script_loop_refinement_prompt(hook, final_script, display_script)
        raw_res = client.analyze(prompt)
        payload = FinalScriptLoopRefinementPayload.model_validate(raw_res)

        if payload.refined_final_script and payload.refined_final_script.strip():
            refined_final = payload.refined_final_script.strip()
        if payload.refined_display_script and payload.refined_display_script.strip():
            refined_display = payload.refined_display_script.strip()
        if payload.tail_bridge and payload.tail_bridge.strip():
            effective_tb = payload.tail_bridge.strip()
    except Exception:
        pass

    # 안전망 살균기 적용
    refined_final = sanitize_final_script_loop(refined_final, hook, effective_tb, is_tts=True)
    refined_display = sanitize_final_script_loop(refined_display, hook, effective_tb, is_tts=False)

    return refined_final, refined_display, effective_tb

