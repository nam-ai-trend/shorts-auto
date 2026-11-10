import React from "react";

interface TitleOverlayProps {
  title?: string;
}

export const TitleOverlay: React.FC<TitleOverlayProps> = ({ title }) => {

  // 제목이 없거나 공백이면 렌더링하지 않음
  if (!title || !title.trim()) {
    return null;
  }

  // 노출 시간: 영상의 완전 처음부터 끝까지 (Always-On 상시 고정 노출)
  // 시청자가 쇼츠를 언제 보든 주제와 핵심 후킹을 놓치지 않도록 상시 유지
  const currentScale = 1.0;
  const currentOpacity = 1.0;

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

