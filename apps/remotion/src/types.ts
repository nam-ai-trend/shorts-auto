export interface SubtitleItem {
  start: number;
  end: number;
  text: string;
}

export interface ShortsProps {
  videoSrc: string;
  audioSrc: string;
  bgmSrc?: string;
  bgmVolume?: number;
  subtitles: SubtitleItem[];
  durationInFrames: number;
  title?: string;
}
