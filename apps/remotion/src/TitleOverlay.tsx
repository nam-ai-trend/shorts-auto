import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

interface TitleOverlayProps {
  title?: string;
}

export const TitleOverlay: React.FC<TitleOverlayProps> = ({ title }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // 제목이 없거나 공백이면 렌더링하지 않음
  if (!title || !title.trim()) {
    return null;
  }

  // 노출 시간: 0초 ~ 2.0초 (정확히 2초 = 48 프레임 at 24fps)
  const endFrame = Math.round(2.0 * fps);
  if (frame > endFrame) {
    return null;
  }

  // 1. 완전 처음(0초 0프레임)부터 100% 크기와 불투명도로 즉시 표시
  // (스프링 팝업으로 인한 0초 시점 미노출 현상 제거)

  // 2. 퇴장 페이드아웃 및 축소 효과 (1.5초 ~ 2.0초 = 36 ~ 48 프레임)
  const fadeStartFrame = Math.round(1.5 * fps);
  const exitOpacity = interpolate(
    frame,
    [fadeStartFrame, endFrame],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  const exitScale = interpolate(
    frame,
    [fadeStartFrame, endFrame],
    [1, 0.94],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  const currentScale = exitScale;
  const currentOpacity = exitOpacity;

  // 줄바꿈(\n) 처리
  const lines = title.trim().split("\n");

  // 글자 크기: 사용자의 요청에 따라 1.1배 축소하여 양옆 잘림 방지
  // 1080px 화면 폭에서 꽉 차면서도 안전하게 여백 확보
  const maxLineLength = Math.max(...lines.map((l) => l.length));
  let calculatedFontSize = 136; // 150 / 1.1
  if (maxLineLength >= 17) {
    calculatedFontSize = 80; // 88 / 1.1
  } else if (maxLineLength >= 15) {
    calculatedFontSize = 90; // 100 / 1.1
  } else if (maxLineLength >= 13) {
    calculatedFontSize = 102; // 112 / 1.1
  } else if (maxLineLength >= 11) {
    calculatedFontSize = 116; // 11~12자 (130 / 1.1 = 118에서 안전 마진 고려 116px)
  } else if (maxLineLength >= 9) {
    calculatedFontSize = 124;
  }

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: 0,
        bottom: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center", // 중앙 기준
        padding: "0 16px 200px 16px", // 중앙보다 조금 더 위쪽으로 올리며 좌우 가용 폭(1048px) 최대 확보
        pointerEvents: "none",
        zIndex: 60, // 하단 자막(zIndex: 50)보다 상위
      }}
    >
      <div
        style={{
          transform: `scale(${currentScale})`,
          opacity: currentOpacity,
          width: "100%",
          maxWidth: "1050px",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "12px",
        }}
      >
        {/* 네모박스 없이 글자만 1.2배 더 키워 큼직하게 렌더링 */}
        {lines.map((line, idx) => (
          <div
            key={idx}
            style={{
              fontFamily:
                'Pretendard, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Segoe UI", Roboto, sans-serif',
              fontSize: `${calculatedFontSize}px`,
              fontWeight: 800, // 자막과 동일한 800(ExtraBold)로 통일
              lineHeight: 1.15,
              color: idx === 0 ? "#ffffff" : "#fef08a", // 1줄은 화이트, 2줄은 강조 옐로우
              letterSpacing: "-3px", // 큼직한 폰트에서 양끝 잘림을 방지하고 탄탄한 헤드라인을 만드는 자간
              whiteSpace: "nowrap",
              wordBreak: "keep-all",
              // 커진 폰트에 맞춰 9px 볼드 블랙 외곽선 & 입체 그림자
              WebkitTextStroke: "9px #000000",
              paintOrder: "stroke fill",
              textShadow:
                "0 4px 8px rgba(0, 0, 0, 0.9), 0 8px 24px rgba(0, 0, 0, 0.95), 0 0 35px rgba(0, 0, 0, 0.8)",
            }}
          >
            {line}
          </div>
        ))}
      </div>
    </div>
  );
};
