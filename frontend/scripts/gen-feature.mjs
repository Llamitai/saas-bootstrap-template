import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const [, , featureName] = process.argv;

if (!featureName || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(featureName)) {
  process.stderr.write("Usage: pnpm gen:feature <kebab-case-feature>\n");
  process.exit(1);
}

const featureRoot = path.join(process.cwd(), "src", "features", featureName);

await mkdir(path.join(featureRoot, "api"), { recursive: true });
await mkdir(path.join(featureRoot, "model"), { recursive: true });
await mkdir(path.join(featureRoot, "ui"), { recursive: true });
await writeFile(
  path.join(featureRoot, "index.ts"),
  `// Public facade for ${featureName}. Export feature API deliberately.\n`
);

process.stdout.write(`Created src/features/${featureName}\n`);
