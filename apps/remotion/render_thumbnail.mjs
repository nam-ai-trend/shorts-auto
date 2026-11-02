import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
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
    console.error("Usage: node render_thumbnail.mjs --props=<props.json> --output=<output.png>");
    process.exit(1);
  }

  const rawProps = JSON.parse(fs.readFileSync(propsPath, "utf-8"));
  console.log(`[Remotion Thumbnail] Loaded props from ${propsPath}`);
  console.log(`[Remotion Thumbnail] Target output: ${outputPath}`);

  const entryPoint = path.resolve(__dirname, "src/index.ts");
  const projectRoot = path.resolve(__dirname, "../../");

  const bundleLocation = await bundle({
    entryPoint,
    publicDir: projectRoot,
  });

  const composition = await selectComposition({
    serveUrl: bundleLocation,
    id: "ShortsThumbnail",
    inputProps: rawProps,
  });

  await renderStill({
    composition,
    serveUrl: bundleLocation,
    output: path.resolve(outputPath),
    inputProps: rawProps,
    imageFormat: "png",
  });

  console.log(`[Remotion Thumbnail] ✅ Successfully rendered thumbnail to ${outputPath}`);
}

main().catch((err) => {
  console.error("[Remotion Thumbnail] Render failed:", err);
  process.exit(1);
});
