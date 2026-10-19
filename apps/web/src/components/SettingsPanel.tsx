import type { SettingsStatus } from "../types";

interface SettingsPanelProps {
  readonly settings: SettingsStatus | null;
}

function keyStatus(isConfigured: boolean): string {
  return isConfigured ? "Configured" : "Missing";
}

export function SettingsPanel({ settings }: SettingsPanelProps) {
  return (
    <section className="panel settings-panel" aria-labelledby="settings-title">
      <div className="section-header">
        <div>
          <p className="eyebrow">Settings</p>
          <h2 id="settings-title">Project defaults</h2>
        </div>
      </div>

      {settings === null ? (
        <p className="empty-state">Loading settings...</p>
      ) : (
        <dl className="settings-grid">
          <div>
            <dt>OpenAI API key</dt>
            <dd>{keyStatus(settings.openai_api_key)}</dd>
          </div>
          <div>
            <dt>YouTube API key</dt>
            <dd>{keyStatus(settings.youtube_api_key)}</dd>
          </div>
          <div>
            <dt>Higgsfield API key</dt>
            <dd>{keyStatus(settings.higgsfield_api_key)}</dd>
          </div>
          <div>
            <dt>Qwen3-TTS</dt>
            <dd>{settings.qwen3_tts_base_url}</dd>
          </div>
          <div>
            <dt>Reference voice</dt>
            <dd>{settings.reference_voice_path}</dd>
          </div>
          <div>
            <dt>Reference text</dt>
            <dd>{keyStatus(settings.reference_voice_text)}</dd>
          </div>
          <div>
            <dt>BGM path</dt>
            <dd>{settings.bgm_path}</dd>
          </div>
          <div>
            <dt>BGM volume</dt>
            <dd>{Math.round(settings.bgm_volume * 100)}%</dd>
          </div>
          <div>
            <dt>Output directory</dt>
            <dd>{settings.output_dir}</dd>
          </div>
        </dl>
      )}
    </section>
  );
}
