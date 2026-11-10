# 🎬 쇼츠 자동 생성 시스템 작업 정리 및 인수인계 보고서

**작업 일시:** 2026-11-10  
**프로젝트 경로:** `/Users/gwn/antigravity/16_shorts_auto`  
**최신 산출물:** `outputs/261108_1514/final.mp4`

---

## 1. 주요 해결 과제 및 구현 내역

### ① 씬 내부 비디오 안정성 개선 (앵커 락 & 3D 패럴랙스 카메라 모션)
* **문제점:**
  * 한 씬(클립) 안에서 피사체(달 등)와 배경이 제각각 변형되거나 화면이 따로 놀아 매끄럽지 않은 현상 발생.
* **해결 원칙:**
  * 배속 조절 대신 **'앵커 락(Anchor-Lock) & 3D 패럴랙스'** 카메라 기법 도입.
  * **원형 유지(No Morphing):** 피사체 형태는 100% 원형을 유지하며 형태 붕괴나 무작위 모핑을 엄격히 금지.
  * **단일 궤도 모션(Single Arc Motion):** 카메라는 Slow Orbit / Smooth Arc / Subtle Push-in 등 하나의 부드러운 궤적만 따르도록 프롬프트 가이드라인 개편.
* **반영 사항:**
  * 비디오 생성 프롬프트 및 파이프라인 전면 개편 (`apps/api/app/production/camera_movements.py` 등).
  * 1~13씬 비디오 클립 전량 재생성 완료 (`scene_01_video.mp4` ~ `scene_13_video.mp4`).

### ② 쇼츠 상단 타이틀 상시 고정 (Always-On Title Overlay)
* **문제점:**
  * 기존에는 오프닝 2.1초에만 제목이 노출되었다가 사라져, 영상 중간 유입 시청자의 이탈 방지 효과가 떨어짐.
* **해결 원칙:**
  * 쇼츠 시작부터 끝까지(전체 프레임) 화면 상단 안전지대에 제목이 100% 고정 노출(Always-On)되도록 변경.
* **반영 사항:**
  * **지침 문서:** `manual.md`, `README.md`에 Always-On 타이틀 명세 반영.
  * **Remotion 컴포넌트:** `apps/remotion/src/TitleOverlay.tsx`에서 2초 후 렌더링 중단 조건(`frame > endFrame`) 및 페이드아웃 제거, `scale = 1.0`, `opacity = 1.0` 상시 고정.
  * **웹 UI:** `apps/web/src/components/ProductionPanel.tsx` 입력 라벨을 "쇼츠 상단 고정 타이틀 (처음부터 끝까지 노출)"로 갱신.
  * **최종 렌더링 및 검증:** `outputs/261108_1514/final.mp4` 재렌더링 후 1초, 10초, 30초, 50초 프레임에서 상단 고정 타이틀 정상 노출 확인 완료.

---

## 2. 변경된 파일 목록 및 역할

| 구분 | 파일 경로 | 설명 |
|---|---|---|
| **지침 문서** | [`manual.md`](./manual.md) | 상단 고정 타이틀 및 카메라 모션 원칙 표준 지침 갱신 |
| | [`README.md`](./README.md) | Always-On 타이틀 및 전체 파이프라인 아키텍처 반영 |
| **비디오 렌더러** | [`apps/remotion/src/TitleOverlay.tsx`](./apps/remotion/src/TitleOverlay.tsx) | 타이틀 상시 노출(시간제한/페이드아웃 제거) |
| | [`apps/remotion/src/ShortsComposition.tsx`](./apps/remotion/src/ShortsComposition.tsx) | Always-On 타이틀 레이어 및 컴포지션 구성 |
| **웹 프론트엔드** | [`apps/web/src/components/ProductionPanel.tsx`](./apps/web/src/components/ProductionPanel.tsx) | 상시 고정 타이틀 UI 라벨 반영 |
| | [`apps/web/src/components/CandidateDraftsPanel.tsx`](./apps/web/src/components/CandidateDraftsPanel.tsx) | 드래프트 관리 컴포넌트 |
| | [`apps/web/src/components/ModelSelectorModal.tsx`](./apps/web/src/components/ModelSelectorModal.tsx) | 모델 선택 모달 |
| **백엔드 API** | [`apps/api/app/production/camera_movements.py`](./apps/api/app/production/camera_movements.py) | 앵커 락 & 3D 패럴랙스 카메라 규칙 정의 |
| | [`apps/api/app/production/service.py`](./apps/api/app/production/service.py) | 비디오 생성 및 렌더러 서비스 연동 |

---

## 3. 최신 결과물 상태

* **최종 영상:** [`outputs/261108_1514/final.mp4`](./outputs/261108_1514/final.mp4)
  * 해상도: 1080x1920 (9:16 세로형 쇼츠)
  * 재생 시간: 약 52초 (24fps, 1,247 프레임)
  * 비디오: 1~13씬 앵커 락 모션 클립 적용
  * 텍스트: 상단 고정 타이틀("달에 구멍 뚫으니 달이 이렇게 변했어요") + 하단 나레이션 싱크 자막
  * 오디오: ElevenLabs 한국어 TTS + 배경음악 믹싱

---

## 4. 새 세션에서 바로 이어갈 수 있는 다음 작업 제안

1. **새 프로젝트 일괄 생성 테스트:** 새로 정립된 앵커 락 규칙과 Always-On 타이틀이 새 주제 생성 시에도 완전 자동으로 일관되게 동작하는지 확인.
2. **소셜 플랫폼 배포 파이프라인 구축:** 렌더링된 `final.mp4`를 유튜브 쇼츠, 인스타그램 릴스, 틱톡 등에 원클릭 업로드하는 자동화 연동.
3. **Git 변경사항 정리:** 현재 작업된 파일들을 깔끔하게 커밋(`git commit`)하여 버전 히스토리 보존.

