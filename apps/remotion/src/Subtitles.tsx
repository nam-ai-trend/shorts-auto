import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { SubtitleItem } from "./types";

interface SubtitlesProps {
  subtitles: SubtitleItem[];
}

export const Subtitles: React.FC<SubtitlesProps> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // 현재 재생 시간에 해당하는 자막 블록 탐색
  const currentSub = subtitles.find(
    (s) => currentTime >= s.start && currentTime <= s.end
  );

  if (!currentSub || !currentSub.text.trim()) {
    return null;
  }

  // 자막 시작 시점에서의 프레임 오프셋 (스프링 팝업 효과)
  const startFrame = Math.round(currentSub.start * fps);
  const relativeFrame = Math.max(0, frame - startFrame);

  const scale = spring({
    frame: relativeFrame,
    fps,
    config: {
      damping: 14,
      stiffness: 220,
      mass: 0.8,
    },
  });

  const opacity = interpolate(relativeFrame, [0, 4], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 390, // 원래 하단 안전지대 자막 위치로 복구
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 40px",
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          opacity,
          background: "rgba(10, 15, 29, 0.85)",
          backdropFilter: "blur(12px)",
          border: "2px solid rgba(56, 189, 248, 0.45)",
          borderRadius: "24px",
          padding: "16px 36px",
          boxShadow: "0 12px 36px rgba(0, 0, 0, 0.8), 0 0 24px rgba(56, 189, 248, 0.3)",
          maxWidth: "1000px",
          textAlign: "center",
          whiteSpace: "nowrap",
        }}
      >
        <span
          style={{
            fontFamily:
              'Pretendard, -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Segoe UI", Roboto, sans-serif',
            fontSize: currentSub.text.length > 14 ? "60px" : "65px", // 기존 46~50px에서 1.3배 확대
            fontWeight: 800,
            lineHeight: 1.2,
            color: "#ffffff",
            letterSpacing: "-0.5px",
            textShadow:
              "0 3px 6px rgba(0,0,0,0.95), -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000",
            whiteSpace: "nowrap",
            display: "inline-block",
          }}
        >
          {currentSub.text}
        </span>
      </div>
    </div>
  );
};
