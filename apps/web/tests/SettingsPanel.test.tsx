import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SettingsPanel } from "../src/components/SettingsPanel";

describe("SettingsPanel", () => {
  it("shows API key presence without rendering raw secret values", () => {
    render(
      <SettingsPanel
        settings={{
          openai_api_key: true,
          youtube_api_key: false,
          higgsfield_api_key: true,
          qwen3_tts_base_url: "http://127.0.0.1:7860",
          reference_voice_path: "assets/reference_voice/reference_voice.mp3",
          reference_voice_text: true,
          bgm_path: "assets/bgm/default.mp3",
          bgm_volume: 0.18,
          output_dir: "outputs"
        }}
      />
    );

    expect(screen.getAllByText("Configured")).toHaveLength(3);
    expect(screen.getByText("Missing")).toBeInTheDocument();
    expect(screen.queryByText(/secret/i)).not.toBeInTheDocument();
    expect(screen.getByText("http://127.0.0.1:7860")).toBeInTheDocument();
    expect(screen.getByText("Reference text")).toBeInTheDocument();
  });
});
