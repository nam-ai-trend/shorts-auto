# 🎬 Shorts Auto

> **떡상한 유튜브 쇼츠를 벤치마킹하여, 나만의 고품질 9:16 쇼츠 영상을 원클릭으로 제작하는 Local-First 올인원 자동화 스튜디오**

[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![pnpm](https://img.shields.io/badge/pnpm-9+-F69220?logo=pnpm&logoColor=white)](https://pnpm.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=white)](https://react.dev/)
[![Remotion](https://img.shields.io/badge/Remotion-Video_Rendering-0B84F3?logo=remotion&logoColor=white)](https://remotion.dev/)

---

## 📌 목차
- [1. 프로젝트 소개](#1-프로젝트-소개)
- [2. 핵심 기능](#2-핵심-기능)
- [3. 사전 필수 요구사항 (Prerequisites)](#3-사전-필수-요구사항-prerequisites)
- [4. 빠른 시작 가이드 (Quick Start)](#4-빠른-시작-가이드-quick-start)
  - [Step 1. 저장소 클론 및 패키지 설치](#step-1-저장소-클론-및-패키지-설치)
  - [Step 2. 환경 변수 설정 (.env)](#step-2-환경-변수-설정-env)
  - [Step 3. 로컬 에셋 파일 배치](#step-3-로컬-에셋-파일-배치)
  - [Step 4. (선택) Higgsfield MCP 연동](#step-4-선택-higgsfield-mcp-연동)
- [5. 프로젝트 실행 (Running)](#5-프로젝트-실행-running)
- [6. 상세 사용 매뉴얼](#6-상세-사용-매뉴얼)
- [7. 프로젝트 폴더 구조](#7-프로젝트-폴더-구조)
- [8. 테스트 및 빌드](#8-테스트-및-빌드)
- [9. 트러블슈팅 & FAQ](#9-트러블슈팅--faq)

---

## 1. 프로젝트 소개

**Shorts Auto**는 유튜브 쇼츠의 흥행 공식을 데이터 기반으로 분석하고, 기획/대본 작성/음성 합성/AI 비디오 생성/자막 및 타이틀 렌더링까지 전 과정을 로컬 웹 대시보드에서 유기적으로 수행할 수 있는 자동화 플랫폼입니다.

- **FastAPI 백엔드:** 비동기 작업 큐, 유튜브 오디오 추출, Whisper STT, GPT 대본 생성, Remotion 및 FFmpeg 렌더링 파이프라인 제어
- **Vite React 프론트엔드:** 단계별 진행 상황 실시간 모니터링, 초안 선택, 씬별 프롬프트 수정 및 미리보기를 지원하는 직관적인 대시보드
- **Remotion 비디오 렌더러:** 타임스탬프 기반 자막 싱크, 동적 스프링 애니메이션 타이틀 카드, 오디오/비디오 자동 믹싱

---

## 2. 핵심 기능

| 단계 | 기능 | 설명 |
| :--- | :--- | :--- |
| **01. 레퍼런스 탐색** | 유튜브 검색 & 직링크 | 키워드/채널 검색 또는 쇼츠 직링크(`https://youtube.com/shorts/...`) 입력 |
| **02. 오디오 & STT** | 음성 추출 및 자막화 | `yt-dlp` 고음질 음원 추출 + OpenAI Whisper 자동 전사 |
| **03. AI 심층 분석** | 떡상 공식 구조화 | 첫 3초 후킹 공식, 텐션 곡선, 리메이크 추천 주제 5선 도출 |
| **04. 대본 초안 생성** | 2종 맞춤형 초안 | 상식파괴형(Draft A) vs 스토리텔링형(Draft B) + 후킹 제목 3선 |
| **05. 음성 & 씬 분할** | 1.2배속 TTS & 문장 쪼개기 | 참조 보이스 클로닝 + 단어 단위 타임스탬프 기반 4~8개 씬 자동 분할 |
| **06. AI 영상 생성** | 키프레임 & 모션 | Higgsfield, Kling 3.0, Veo 등 최신 모델로 연속성(Continuity) 있는 씬 제작 |
| **07. 원클릭 렌더링** | 9:16 쇼츠 완성본 | 0~2초 오프닝 타이틀 오버레이 + 자막 + BGM + 씬 클립을 `final.mp4`로 합성 |

---

## 3. 사전 필수 요구사항 (Prerequisites)

이 프로젝트를 구동하기 위해 아래 시스템 도구들이 컴퓨터에 설치되어 있어야 합니다.

### 1) 미디어 처리 도구 (필수)
- **ffmpeg**: 오디오 변환, 영상 인코딩 및 Remotion 합성
- **yt-dlp**: 유튜브 쇼츠 음원 다운로드

#### OS별 설치 방법:
- **macOS (Homebrew):**
  ```bash
  brew install ffmpeg yt-dlp
  ```
- **Ubuntu / Debian Linux:**
  ```bash
  sudo apt update && sudo apt install -y ffmpeg
  pip install -U yt-dlp
  ```
- **Windows (Scoop / Chocolatey):**
  ```powershell
  scoop install ffmpeg yt-dlp
  # 또는
  choco install ffmpeg yt-dlp
  ```

### 2) 개발 런타임
- **Node.js**: `v18.0.0` 이상 ([다운로드](https://nodejs.org/))
- **pnpm**: `v9.0.0` 이상 (`npm i -g pnpm`)
- **Python**: `3.11` 이상 ([다운로드](https://python.org/))
- **uv** (권장, 초고속 파이썬 패키지 관리자):
  ```bash
  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Windows
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

---

## 4. 빠른 시작 가이드 (Quick Start)

### Step 1. 저장소 클론 및 패키지 설치
```bash
# 1. 저장소 클론
git clone https://github.com/<your-username>/shorts-auto.git
cd shorts-auto

# 2. Node.js 의존성 설치 (모노레포 루트)
pnpm install
```

### Step 2. 환경 변수 설정 (`.env`)
프로젝트 루트의 `.env.example`을 복사하여 `.env` 파일을 생성합니다:
```bash
cp .env.example .env
```

`.env` 파일을 열고 사용할 API 키를 입력합니다:
```env
# [필수] OpenAI API 키 (GPT-4o 대본 분석/생성 및 Whisper STT에 사용)
OPENAI_API_KEY=sk-proj-...

# [선택] YouTube Data API 키 (키워드/채널 검색 시 필요, 직링크 사용 시 생략 가능)
YOUTUBE_API_KEY=AIzaSy...

# [선택] Higgsfield API 키 (AI 이미지/비디오 생성 파이프라인용)
HIGGSFIELD_API_KEY=...

# [선택] 로컬 또는 원격 Qwen3-TTS 서버 엔드포인트
QWEN3_TTS_BASE_URL=http://127.0.0.1:7860

# 기본 경로 설정
REFERENCE_VOICE_PATH=assets/reference_voice/reference_voice.mp3
BGM_PATH=assets/bgm/channel_bgm.mp3
BGM_VOLUME=0.18
OUTPUT_DIR=outputs
```

> ⚠️ **보안 주의**: `.env` 파일과 실제 API 키는 `.gitignore`에 등록되어 있어 GitHub에 절대 커밋되지 않습니다.

### Step 3. 로컬 에셋 파일 배치
음성 클로닝과 배경음악으로 사용할 오디오 파일을 아래 폴더에 넣어줍니다:
1. **나레이션 기준 목소리:** `assets/reference_voice/reference_voice.mp3` (잡음이 없는 10~20초 분량 음원)
2. **배경음악(BGM):** `assets/bgm/channel_bgm.mp3` (영상 분위기에 어울리는 BGM)

> 💡 파일명이 다른 경우 `.env`의 `REFERENCE_VOICE_PATH` 및 `BGM_PATH`를 원하는 파일명으로 수정하면 됩니다.

### Step 4. (선택) Higgsfield MCP 연동
AI 에이전트(Codex, Antigravity 등)에서 Higgsfield 도구를 직접 호출하려면 MCP 래퍼를 1회 등록합니다:
```bash
# Higgsfield CLI 설치 및 로그인
npm i -g @higgsfield/cli
higgsfield auth login
higgsfield workspace set <workspace_id>

# MCP 설정 파일 등록
pnpm setup:higgsfield-mcp
```

---

## 5. 프로젝트 실행 (Running)

터미널에서 아래 단 한 줄의 명령어로 FastAPI 백엔드와 Vite 프론트엔드를 동시에 실행합니다:

```bash
pnpm dev
```

터미널에 다음 로그가 출력되면 정상 기동된 것입니다:
```text
[api] INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
[web]   VITE v5.x.x  ready in 250 ms
[web]   ➜  Local:   http://localhost:5173/
```

웹 브라우저를 열고 **`http://localhost:5173`** 에 접속하면 대시보드가 열립니다.

> 💡 **서비스 개별 실행이 필요한 경우:**
> - 백엔드만 실행: `pnpm dev:api`
> - 프론트엔드만 실행: `pnpm dev:web`

---

## 6. 상세 사용 매뉴얼

대시보드 화면 구성 및 Step 0(프로젝트 생성)부터 Step 10(최종 9:16 쇼츠 렌더링)까지의 모든 실전 제작 가이드는 **[manual.md](manual.md)** 에 상세히 설명되어 있습니다.

👉 **[📖 Shorts Auto 상세 매뉴얼(manual.md) 바로가기](manual.md)**

---

## 7. 프로젝트 폴더 구조

```text
shorts-auto/
├── apps/
│   ├── api/                   # FastAPI 백엔드 (Python 3.11+, uv)
│   │   ├── app/               # API 라우터, 비즈니스 로직, 렌더러 파이프라인
│   │   └── tests/             # 백엔드 pytest 테스트 스위트
│   ├── remotion/              # Remotion 비디오 렌더러 (React + Webpack)
│   │   ├── src/               # 쇼츠 씬 컴포지션, 자막, 타이틀 오버레이
│   │   └── render.mjs         # Remotion 렌더 실행 CLI 스크립트
│   └── web/                   # 대시보드 프론트엔드 (Vite, React, TypeScript)
│       ├── src/               # 대시보드 컴포넌트 및 API 클라이언트
│       └── tests/             # 프론트엔드 Vitest 테스트 스위트
├── assets/                    # 기본 미디어 에셋 (.gitkeep으로 디렉토리 유지)
│   ├── bgm/                   # 배경음악 (channel_bgm.mp3 등)
│   └── reference_voice/       # 보이스 클로닝 참조 음원
├── config/                    # 설정 템플릿
│   └── local.settings.example.json
├── outputs/                   # 프로젝트별 생성 결과물 (.gitignore로 파일 커밋 차단)
├── tools/                     # 개발 및 MCP 도구 스크립트
│   ├── dev/start-dev.mjs      # 백엔드/프론트엔드 동시 실행 런처
│   └── higgsfield-mcp/        # Higgsfield Model Context Protocol 래퍼
├── manual.md                  # 대시보드 상세 사용 가이드
└── README.md                  # 프로젝트 개요 및 셋업 가이드
```

---

## 8. 테스트 및 빌드

```bash
# 1. 전체 테스트 실행 (FastAPI + Vite)
pnpm test

# 2. 백엔드 테스트 단독 실행
pnpm test:api

# 3. 프론트엔드 테스트 단독 실행
pnpm test:web

# 4. 프론트엔드 프로덕션 빌드
pnpm --filter @shorts-auto/web build
```

---

## 9. 트러블슈팅 & FAQ

#### Q1. `ECONNREFUSED 127.0.0.1:8000` 오류가 화면에 나타납니다.
- **원인:** 백엔드 FastAPI 서버가 켜져 있지 않은 상태입니다.
- **해결:** `pnpm dev:web` 대신 **`pnpm dev`** 명령어로 백엔드와 프론트엔드를 동시에 실행해 주세요.

#### Q2. `yt-dlp: command not found` 또는 오디오 추출 실패
- **해결:** 터미널에 `brew install yt-dlp` (macOS) 또는 최신 버전으로 업데이트(`brew upgrade yt-dlp`)를 진행해 주세요.

#### Q3. outputs 폴더에 파일이 많은데 깃허브에 올라가나요?
- **답변:** 아니오. `outputs/` 디렉토리는 깃허브에 빈 디렉토리(`.gitkeep`)로만 생성되며, 내부의 모든 프로젝트 생성 파일(`outputs/*`)은 `.gitignore`에 의해 자동으로 배제됩니다.
