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
   - [0~3초: 상식 충돌 후킹] 시청자가 당연하게 생각하는 상식을 단 한 문장으로 부수며 스크롤 정지.
     (예: "기껏해야 얼마 안 되겠지 생각하겠지만, 이거 완전 아닙니다!", "왜 아무도 이 사실을 모를까요?")
   - [3~15초: 의문 심화 & 관찰 포인트] 시청자가 예측하지 못한 의외의 질문과 낯선 관찰 포인트를 던져 "대체 왜?" 호기심 갭 극대화.
   - [15~35초: 상태 변화 & 팩트 폭탄] 설명조로 늘어지지 않고, "더 소름 돋는 건...", "그런데 여기서 반전이 일어납니다"처럼 국면이 바뀌는 전환점과 함께 미세 팩트와 작동 원리를 쉴 틈 없이 전개.
   - [35~50초: 결말 인지 보상 & 브릿지] 압도적 총량과 체감 환산 수치로 지적 카타르시스를 주고, 아래 5번의 무한 루프 꼬리 브릿지로 연결.

4. ⏱️ 대본 분량 및 구어체 어조 (엄수!):
   - 분량: 각 draft_script는 **45~55초 분량 (공백 포함 420자 ~ 520자 내외, 8~10개 문장)**으로 꽉 찬 밀도로 작성하세요. (250~350자는 너무 짧아 내용이 빈약해지니 절대 금지!)
   - 어조: 시청자에게 직접 속삭이듯 말하는 찰진 구어체 낭독 톤 ("~거든요!", "~다니까요!", "~죠?"). 딱딱한 백과사전식 문장 절대 금지.

5. 🔄 수미상관 무한 루프(Seamless Loop) 엔딩 & 🛡️ 팩트체크 QA (Fact-Check QA) 절대 규칙 [위반 시 엄격히 재생성 대상]:
   - [🚨 규칙 1: 대본 시작 문장 = hook 완벽 일치]:
     * 각 draft_script의 맨 첫 문장은 반드시 메타데이터의 `hook` 대사와 토시 하나 틀리지 않고 100% 동일하게 시작해야 합니다.
   - [🚨 규칙 2: 대본 맨 끝은 반드시 tail_bridge로 끝나야 하며, 첫 문장(hook)을 대본 끝에 다시 붙이지 말 것!]:
     * 유튜브 쇼츠는 영상이 끝나면 플레이어가 자동으로 처음(0초)으로 되돌아가 재생됩니다.
     * 따라서 대본 맨 끝에 첫 문장(hook)을 다시 한 번 낭독하거나 덧붙이면 절대 안 됩니다! (그렇게 하면 첫 문장이 두 번 연속 낭독되는 치명적인 오류가 발생합니다!)
     * 대본의 맨 마지막 단어는 반드시 첫 문장(`hook`)의 첫 주어/명사를 수식하는 불완전한 **관형사형 꼬리 어미(`tail_bridge`: 예: "~해버린", "~했던", "~라는 사실 바로")**로 끝나야 합니다. (마침표나 물음표 없이 끝낼 것!)
     * ❌ 치명적 오류 1: 대본 맨 뒤에 첫 문장을 또 붙이는 행위 (예: "...지구상에서 싹 사라져버린 공룡을 멸종시킨 소행성이 서울에 떨어지면 구덩이는 어디까지 생길까요?") -> 절대 금지!
     * ❌ 치명적 오류 2: 질문이나 마침표로 끝내기 (예: "...구멍만 있을까요?", "...사실입니다.") -> 절대 금지!
     * ⭕ 완벽한 draft_script 끝부분 예시:
       "...그렇게 완성된 구덩이는 지름 약 180km로 서울시청은 물론 춘천과 천안시청까지 집어삼킨다는 사실, 지구상에서 싹 사라져버린" (여기서 대본 끝! 마침표 없음!)
     * 🚫 기계적 클리셰("~의 장본인", "~의 시초")는 금지하며, 해당 주제의 고유 동작(파괴, 폭발, 회전, 분열, 냉각 등)을 담은 동사/형용사로 브릿지를 창작하세요.
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
      "hook": "첫 3초 후킹 대사",
      "target_viewer": "타겟 시청자층",
      "why_it_can_work": "알고리즘에서 터질 수밖에 없는 이유",
      "main_curiosity_question": "끝까지 보게 만드는 핵심 호기심 질문",
      "structure_summary": "전체 구성 요약 (소재 이해 -> 후킹 -> 상태변화 -> 결말 보상)",
      "draft_script": "실제 나레이션 대본 전체 (공백 포함 420~520자. 반드시 위 hook으로 첫 문장을 시작하고, 맨 마지막은 마침표/물음표 없이 hook을 자석처럼 수식하는 불완전한 tail_bridge로 끝내야 함)",
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
        "loop_type": "수식형 / 인과형 / 동작묘사형 등 창작한 루프 유형",
        "tail_bridge": "대본 맨 마지막 꼬리 브릿지 문구 (예: 지구상에서 싹 사라져버린)",
        "head_hook": "대본 첫 문장 후킹 대사",
        "connected_preview": "[꼬리 브릿지] [첫 문장 후킹]이 자석처럼 자연스럽게 하나로 이어지는 프리뷰"
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
      "hook": "첫 3초 후킹 대사",
      "target_viewer": "타겟 시청자층",
      "why_it_can_work": "알고리즘에서 터질 수밖에 없는 이유",
      "main_curiosity_question": "끝까지 보게 만드는 핵심 호기심 질문",
      "structure_summary": "전체 구성 요약 (소재 이해 -> 후킹 -> 상태변화 -> 결말 보상)",
      "draft_script": "실제 나레이션 대본 전체 (공백 포함 420~520자. 반드시 위 hook으로 첫 문장을 시작하고, 맨 마지막은 마침표/물음표 없이 hook을 자석처럼 수식하는 불완전한 tail_bridge로 끝내야 함)",
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
        "loop_type": "수식형 / 인과형 / 동작묘사형 등 창작한 루프 유형",
        "tail_bridge": "대본 맨 마지막 꼬리 브릿지 문구 (예: 단 몇 초 만에 모든 것을 삼켜버린)",
        "head_hook": "대본 첫 문장 후킹 대사",
        "connected_preview": "[꼬리 브릿지] [첫 문장 후킹]이 자석처럼 자연스럽게 하나로 이어지는 프리뷰"
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
        feedback_directive = "No additional feedback."

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

Return JSON only with this exact shape:
{{
  "final_script": "..."
}}

핵심 원칙:
1. 분량 유지: 공백 포함 400~520자 내외. 핵심 팩트와 수치, 예시를 절대 생략하지 마세요.
2. 구어체 리듬감: 말하듯이 자연스럽고 호흡이 살아있는 구어체 문장으로 다듬되, 쉼표(,)와 마침표(.)를 적절히 배치하여 낭독 시 적절한 호흡과 강세를 살리세요.
3. 팩트 정합성 및 수치 검산: 모든 수치와 비교는 실제 과학적 데이터와 수학적 단위 환산(곱셈/나눗셈)에 철저히 부합해야 하며, 랜드마크 억지 비유는 금지합니다.
4. 🔄 수미상관 무한 루프(Seamless Loop) 엔딩 절대 규칙:
   - [🚨 치명적 절대 금지]: 대본 맨 끝에 첫 문장(hook)을 다시 한 번 낭독하거나 덧붙이지 마세요!
     유튜브 쇼츠 플레이어가 자동으로 0초(처음)로 되감기 때문에, 대본 끝에 첫 문장을 또 쓰면 첫 문장이 두 번 연속 낭독되는 치명적인 오류가 발생합니다!
   - [올바른 결말]: 대본의 맨 마지막 단어는 반드시 첫 문장(hook)을 자석처럼 수식하는 불완전한 꼬리 브릿지(Tail Bridge, 예: '단 몇 초 만에 내부를 뒤흔들어버린', '지구상에서 싹 사라져버린')로 마침표나 물음표 없이 끝내야 합니다.
   - ❌ 절대 금지: "...단 몇 초 만에 내부를 뒤흔들어버린 달에 만약 구멍을 뚫는다면, 대체 어떻게 될까요?" (첫 문장을 또 붙이는 행위 절대 금지!)
   - ⭕ 올바른 예: "...단 몇 초 만에 내부를 뒤흔들어버린" (여기서 대본 종료! 마침표 없음!)

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
{feedback if feedback else "No additional feedback."}
""".strip()


def sanitize_script_loop_candidate(candidate: ScriptCandidate) -> ScriptCandidate:
    script = candidate.draft_script.strip()
    hook = candidate.hook.strip()

    # 1. 스크립트 끝에 hook 대사가 중복으로 붙어있는 경우 잘라내기
    hook_clean = re.sub(r"[?!.,\s]+$", "", hook)
    if hook_clean:
        pattern = re.compile(re.escape(hook_clean) + r"[\s?!.]*$", re.IGNORECASE)
        script = pattern.sub("", script).strip()

    # hook의 앞부분(15자 이상)이 대본 후반부에 다시 복붙된 경우 제거
    if len(hook_clean) >= 15:
        prefix = hook_clean[:18]
        if prefix in script[len(script) // 2 :]:
            idx = script.rfind(prefix)
            if len(script) - idx < 120:
                script = script[:idx].strip()

    # 2. loop_design의 tail_bridge가 대본 맨 마지막에 오도록 보정
    if candidate.loop_design and candidate.loop_design.tail_bridge:
        tb = candidate.loop_design.tail_bridge.strip()
        tb_clean = re.sub(r"[?!.,\s]+$", "", tb)
        if tb_clean:
            if tb_clean in script:
                idx = script.rfind(tb_clean)
                script = script[: idx + len(tb_clean)].strip()
            else:
                script = re.sub(r"[?!.,\s]+$", "", script).strip()
                script = f"{script}, {tb_clean}"

    # 3. 무한 루프(다음 영상 첫 문장으로 연결)를 위해 맨 끝의 마침표/물음표 종결 부호 제거
    script = re.sub(r"[?!.]+$", "", script).strip()
    candidate.draft_script = script
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


def sanitize_final_script_loop(final_script: str, hook: str = "", tail_bridge: str = "") -> str:
    script = final_script.strip()
    hook = hook.strip()

    # 1. hook 대사 또는 hook의 핵심 문구가 스크립트 끝에 중복으로 붙어있는 경우 잘라내기
    hook_clean = re.sub(r"[?!.,\s]+$", "", hook)
    if hook_clean:
        pattern = re.compile(re.escape(hook_clean) + r"[\s?!.]*$", re.IGNORECASE)
        script = pattern.sub("", script).strip()

    # 혹시 hook의 앞 12자 이상이 스크립트 후반부(마지막 150자 이내)에 또 나타나면 잘라내기
    if len(hook_clean) >= 12:
        prefix = hook_clean[:15]
        if prefix in script[len(script) // 2 :]:
            idx = script.rfind(prefix)
            if len(script) - idx < 150:
                script = script[:idx].strip()

    # 2. tail_bridge가 있다면 tail_bridge 뒤에 붙은 군더더기/중복 제거
    tb_clean = re.sub(r"[?!.,\s]+$", "", tail_bridge.strip())
    if tb_clean and tb_clean in script:
        idx = script.rfind(tb_clean)
        script = script[: idx + len(tb_clean)].strip()

    # 3. 무한 루프(0초 첫 문장으로의 부드러운 연결)를 위해 맨 끝의 마침표/물음표/느낌표 제거
    script = re.sub(r"[?!.]+$", "", script).strip()
    return script


def extract_final_script(payload: dict, hook: str = "", tail_bridge: str = "") -> str:
    try:
        raw_script = FinalScriptPayload.model_validate(payload).final_script.strip()
        return sanitize_final_script_loop(raw_script, hook, tail_bridge)
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

