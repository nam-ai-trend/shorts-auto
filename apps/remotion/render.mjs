import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const args = process.argv.slice(2);
  let propsPath = null;
  let outputPath = null;

  for (const arg of args) {
    if (arg.startsWith("--props=")) {
      propsPath = arg.replace("--props=", "");
    } else if (arg.startsWith("--output=")) {
      outputPath = arg.replace("--output=", "");
    }
  }

  if (!propsPath || !outputPath) {
    console.error("Usage: node render.mjs --props=<props.json> --output=<output.mp4>");
    process.exit(1);
  }

  const rawProps = JSON.parse(fs.readFileSync(propsPath, "utf-8"));
  console.log(`[Remotion] Loaded props from ${propsPath}`);
  console.log(`[Remotion] Target output: ${outputPath}`);
  console.log(`[Remotion] Video frames: ${rawProps.durationInFrames}, Subtitles count: ${rawProps.subtitles?.length || 0}`);

  console.log("[Remotion] Bundling React composition...");
  const entryPoint = path.resolve(__dirname, "src/index.ts");
  const projectRoot = path.resolve(__dirname, "../../");
  const bundleLocation = await bundle({
    entryPoint,
    publicDir: projectRoot,
  });

  console.log("[Remotion] Selecting composition 'ShortsVideo'...");
  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "ShortsVideo",
    inputProps: rawProps,
  });

  console.log(`[Remotion] Rendering ${composition.durationInFrames} frames (${(composition.durationInFrames / 30).toFixed(1)}s)...`);
  const startTime = Date.now();

  await renderMedia({
    composition,
    serveUrl: bundleLocation,
    codec: "h264",
    outputLocation: path.resolve(outputPath),
    inputProps: rawProps,
    concurrency: null, // CPU 코어 자동 최적화
    onProgress: ({ progress }) => {
      const pct = Math.round(progress * 100);
      if (pct % 10 === 0) {
        process.stdout.write(`\r[Remotion] Progress: ${pct}%`);
      }
    },
  });

  const durationSec = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`\n[Remotion] ✅ Successfully rendered to ${outputPath} in ${durationSec}s`);
}

main().catch((err) => {
  console.error("[Remotion] Render failed:", err);
  process.exit(1);
});
