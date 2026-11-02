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

  // 줄바꿈(\\n 문자열 포함) 정규화 및 분할
  const normalizedTitle = (title || "").replace(/\\n/g, "\n").trim();
  let rawLines = normalizedTitle
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  // 줄바꿈이 없는데 12자 이상이면 공백 기준으로 2줄 분할
  if (rawLines.length === 1 && rawLines[0].length >= 12) {
    const words = rawLines[0].split(/\s+/);
    if (words.length >= 2) {
      const mid = Math.ceil(words.length / 2);
      rawLines = [words.slice(0, mid).join(" "), words.slice(mid).join(" ")];
    }
  }

  const lines = rawLines.slice(0, 2);
  const maxLineLength = lines.length > 0 ? Math.max(...lines.map((l) => l.length)) : 0;
  let calculatedFontSize = 130;
  if (maxLineLength >= 17) {
    calculatedFontSize = 80;
  } else if (maxLineLength >= 15) {
    calculatedFontSize = 90;
  } else if (maxLineLength >= 13) {
    calculatedFontSize = 100;
  } else if (maxLineLength >= 11) {
    calculatedFontSize = 112;
  } else if (maxLineLength >= 9) {
    calculatedFontSize = 120;
  }

  return (
    <div
      style={{
        position: "absolute",
        top: "27%",
        left: "50%",
        transform: `translate(-50%, -50%) scale(${currentScale})`,
        opacity: currentOpacity,
        width: "100%",
        maxWidth: "1050px",
        padding: "0 24px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "12px",
        textAlign: "center",
        boxSizing: "border-box",
        pointerEvents: "none",
        zIndex: 60, // 하단 자막(zIndex: 50)보다 상위
      }}
    >
      {lines.map((line, idx) => {
        const isSecondLine = idx === 1;
        const textColor = isSecondLine ? "#ffe500" : "#ffffff";

        return (
          <div
            key={idx}
            style={{
              fontFamily:
                'Pretendard, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Segoe UI", Roboto, sans-serif',
              fontSize: `${calculatedFontSize}px`,
              fontWeight: 900,
              lineHeight: 1.15,
              color: textColor,
              letterSpacing: "-3px",
              whiteSpace: "nowrap",
              wordBreak: "keep-all",
              WebkitTextStroke: "14px #000000",
              paintOrder: "stroke fill",
              textShadow:
                "0 4px 12px rgba(0, 0, 0, 0.95), 0 8px 30px rgba(0, 0, 0, 0.95), 0 0 45px rgba(0, 0, 0, 0.85)",
            }}
          >
            {line}
          </div>
        );
      })}
    </div>
  );
};

