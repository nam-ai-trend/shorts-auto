import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, staticFile } from "remotion";
import { Subtitles } from "./Subtitles";
import { TitleOverlay } from "./TitleOverlay";
import type { ShortsProps } from "./types";

const resolveMediaSrc = (src: string | undefined | null): string | undefined => {
  if (!src) return undefined;
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) {
    return src;
  }
  const cleaned = src.replace(/^[./\\]+/, "");
  return staticFile(cleaned);
};

export const ShortsComposition: React.FC<ShortsProps> = ({
  videoSrc,
  audioSrc,
  bgmSrc,
  bgmVolume = 0.15,
  subtitles,
  title,
}) => {
  const resolvedVideo = resolveMediaSrc(videoSrc);
  const resolvedAudio = resolveMediaSrc(audioSrc);
  const resolvedBgm = resolveMediaSrc(bgmSrc);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000000" }}>
      {/* 1. 비디오 배경 레이어 (9:16 Portrait - OffthreadVideo로 완벽한 프레임 연속성 보장) */}
      {resolvedVideo ? (
        <OffthreadVideo
          src={resolvedVideo}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      ) : null}

      {/* 2. 성우 나레이션 오디오 레이어 (1.2배속 음성 원본 볼륨 100%) */}
      {resolvedAudio ? <Audio src={resolvedAudio} volume={1.0} /> : null}

      {/* 3. 채널 BGM 레이어 (배경음악 볼륨 조절 및 루프) */}
      {resolvedBgm ? <Audio src={resolvedBgm} volume={bgmVolume} loop /> : null}

      {/* 4. 고화질 볼드 숏폼 자막 레이어 */}
      <Subtitles subtitles={subtitles} />

      {/* 5. 0~2초 오프닝 타이틀 오버레이 레이어 */}
      <TitleOverlay title={title} />
    </AbsoluteFill>
  );
};
