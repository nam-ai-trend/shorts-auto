import React from "react";
import { Composition } from "remotion";
import { ShortsComposition } from "./ShortsComposition";
import type { ShortsProps } from "./types";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ShortsVideo"
        component={ShortsComposition as any}
        durationInFrames={24 * 30} // 기본 30초 (24 FPS 기준)
        fps={24}
        width={1080}
        height={1920}
        defaultProps={{
          videoSrc: "",
          audioSrc: "",
          bgmSrc: undefined,
          bgmVolume: 0.15,
          subtitles: [],
          durationInFrames: 24 * 30,
          title: undefined,
        }}
        calculateMetadata={async ({ props }) => {
          const frames = typeof props.durationInFrames === "number" ? props.durationInFrames : 24 * 30;
          return {
            durationInFrames: Math.max(24, frames),
            props,
          };
        }}
      />
    </>
  );
};
