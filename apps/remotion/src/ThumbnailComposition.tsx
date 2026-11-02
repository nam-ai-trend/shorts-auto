import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

export interface ThumbnailProps {
  imageSrc?: string;
  title?: string;
}

const resolveMediaSrc = (src: string | undefined | null): string | undefined => {
  if (!src) return undefined;
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  const cleaned = src.replace(/^[./\\]+/, "");
  return staticFile(cleaned);
};

export const ThumbnailComposition: React.FC<ThumbnailProps> = ({
  imageSrc,
  title,
}) => {
  const resolvedImage = resolveMediaSrc(imageSrc);

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
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      {/* 1. 썸네일 배경 이미지 */}
      {resolvedImage ? (
        <Img
          src={resolvedImage}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      ) : (
        <AbsoluteFill
          style={{
            background: "linear-gradient(180deg, #1e1b4b 0%, #0f172a 100%)",
          }}
        />
      )}

      {/* 2. 텍스트 가독성을 위한 상하단 시네마틱 비네팅 */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.15) 40%, rgba(0,0,0,0.65) 100%)",
        }}
      />

      {/* 3. 유튜브 쇼츠 규격 초대형 볼드 썸네일 타이틀 (중앙 상단 27% 지점) */}
      {lines.length > 0 && (
        <div
          style={{
            position: "absolute",
            top: "27%",
            left: "50%",
            transform: "translate(-50%, -50%)",
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
          }}
        >
          {lines.map((line, index) => {
            const isSecondLine = index === 1;
            const textColor = isSecondLine ? "#ffe500" : "#ffffff";

            return (
              <div
                key={index}
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
      )}
    </AbsoluteFill>
  );
};

