import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const extensions = new Set([".js", ".jsx", ".mjs", ".mts", ".ts", ".tsx"]);
const violations = [];
const baselinePath = path.join(root, "scripts/import-boundary-baseline.txt");
const ignoredDirs = new Set([
  "node_modules",
  ".next",
  "out",
  "build",
  "dist",
  "coverage",
  "test-results",
]);
const ignoredFiles = new Set(["next-env.d.ts"]);

const importPattern =
  /(?:import|export)\s+(?:type\s+)?(?:[^'"()]*?\s+from\s+)?["']([^"']+)["']|import\s*\(\s*["']([^"']+)["']\s*\)|import\s*\(\s*`([^`]+)`\s*\)/g;

function toPosix(value) {
  return value.split(path.sep).join("/");
}

function relativeToRoot(filePath) {
  return toPosix(path.relative(root, filePath));
}

function resolveSpecifier(importer, specifier) {
  if (specifier.startsWith("@/features/")) {
    return `src/features/${specifier.slice("@/features/".length)}`;
  }
  if (specifier.startsWith("@/entities/")) {
    return `src/entities/${specifier.slice("@/entities/".length)}`;
  }
  if (specifier.startsWith("@/shared/")) {
    return `src/shared/${specifier.slice("@/shared/".length)}`;
  }
  if (specifier === "@/features") return "src/features";
  if (specifier === "@/entities") return "src/entities";
  if (specifier === "@/shared") return "src/shared";
  if (specifier.startsWith("@/src/"))
    return `src/${specifier.slice("@/src/".length)}`;
  if (specifier.startsWith("@/")) return specifier.slice("@/".length);
  if (specifier.startsWith(".")) {
    const importerDir = path.dirname(importer);
    return toPosix(path.relative(root, path.resolve(importerDir, specifier)));
  }
  return null;
}

function addViolation(file, message) {
  violations.push(`${relativeToRoot(file)}: ${message}`);
}

async function readBaseline() {
  try {
    const content = await readFile(baselinePath, "utf8");
    return new Set(
      content
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line && !line.startsWith("#"))
    );
  } catch (error) {
    if (error?.code === "ENOENT") return new Set();
    throw error;
  }
}

function featureName(relativePath) {
  const match = relativePath.match(/^src\/features\/([^/]+)/);
  return match?.[1] ?? null;
}

function entityName(relativePath) {
  const match = relativePath.match(/^src\/entities\/([^/]+)/);
  return match?.[1] ?? null;
}

function isClientModule(source) {
  const prelude = source.slice(0, 512);
  return /^(?:\s|;|\/\/.*|\/\*[\s\S]*?\*\/)*["']use client["']/.test(prelude);
}

function isFeatureUi(relativePath) {
  return /^src\/features\/[^/]+\/ui\//.test(relativePath);
}

function isSharedUi(relativePath) {
  return /^src\/shared\/ui\//.test(relativePath);
}

function isApiRoute(relativePath) {
  return /^src\/app\/api\//.test(relativePath);
}

const retiredTopLevelRoots = [
  "src/application",
  "src/infrastructure",
  "src/domain",
  "src/presentation",
];

function isRetiredTopLevelPath(relativePath) {
  return retiredTopLevelRoots.some(
    (root) => relativePath === root || relativePath.startsWith(`${root}/`)
  );
}

function isBrowserFacing(relativePath, source) {
  return (
    isClientModule(source) ||
    isFeatureUi(relativePath) ||
    isSharedUi(relativePath)
  );
}

function checkImport({ file, relativePath, source, specifier, resolved }) {
  if (!resolved) return;

  if (isRetiredTopLevelPath(resolved)) {
    addViolation(
      file,
      `imports must use feature/shared slices instead of retired root ${specifier}`
    );
  }

  if (relativePath.startsWith("src/shared/")) {
    if (
      resolved.startsWith("src/entities/") ||
      resolved.startsWith("src/features/") ||
      resolved.startsWith("src/app/")
    ) {
      addViolation(file, `shared code must not import ${specifier}`);
    }
  }

  const importerEntity = entityName(relativePath);
  const importedEntity = entityName(resolved);
  if (importerEntity) {
    if (
      resolved.startsWith("src/features/") ||
      resolved.startsWith("src/app/")
    ) {
      addViolation(file, `entity code must not import ${specifier}`);
    }
    if (importedEntity && importedEntity !== importerEntity) {
      const publicEntry = new RegExp(`^src/entities/${importedEntity}/?$`);
      const publicIndex = new RegExp(`^src/entities/${importedEntity}/index$`);
      if (!publicEntry.test(resolved) && !publicIndex.test(resolved)) {
        addViolation(
          file,
          `cross-entity imports must use the public API, not ${specifier}`
        );
      }
    }
  }

  const importerFeature = featureName(relativePath);
  const importedFeature = featureName(resolved);
  if (importerFeature) {
    if (resolved.startsWith("src/app/")) {
      addViolation(
        file,
        `feature code must not import app code via ${specifier}`
      );
    }
    if (importedFeature && importedFeature !== importerFeature) {
      const publicEntry = new RegExp(`^src/features/${importedFeature}/?$`);
      const publicIndex = new RegExp(`^src/features/${importedFeature}/index$`);
      if (!publicEntry.test(resolved) && !publicIndex.test(resolved)) {
        addViolation(
          file,
          `cross-feature imports must use the public API, not ${specifier}`
        );
      }
    }
  }

  if (relativePath.startsWith("src/app/") && !isApiRoute(relativePath)) {
    const privateSlicePath =
      /^src\/(features|entities)\/[^/]+\/(api|model|ui)\//;
    if (privateSlicePath.test(resolved)) {
      addViolation(
        file,
        `app route code must not import feature/entity internals via ${specifier}`
      );
    }
  }

  if (!isBrowserFacing(relativePath, source)) return;

  if (resolved === "src/settings" || resolved.startsWith("src/settings/")) {
    addViolation(
      file,
      `browser-facing code must not import backend settings via ${specifier}`
    );
  }
  if (resolved.startsWith("src/shared/api/repositories/")) {
    addViolation(
      file,
      `browser-facing code must not import raw repositories via ${specifier}`
    );
  }
  if (resolved === "src/shared/http/requests") {
    addViolation(
      file,
      `browser-facing code must use shared HTTP headers instead of ${specifier}`
    );
  }
}

async function* walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (ignoredDirs.has(entry.name)) continue;
    if (ignoredFiles.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walk(fullPath);
      continue;
    }
    if (extensions.has(path.extname(entry.name))) yield fullPath;
  }
}

for await (const file of walk(root)) {
  const relativePath = relativeToRoot(file);
  const source = await readFile(file, "utf8");

  if (isRetiredTopLevelPath(relativePath)) {
    addViolation(
      file,
      "code must live under src/features/<feature> or src/shared, not retired top-level layers"
    );
  }

  for (const match of source.matchAll(importPattern)) {
    const specifier = match[1] ?? match[2] ?? match[3];
    if (specifier.startsWith(".")) {
      addViolation(
        file,
        `imports must use aliases instead of relative specifier ${specifier}`
      );
    }
    checkImport({
      file,
      relativePath,
      source,
      specifier,
      resolved: resolveSpecifier(file, specifier),
    });
  }

  if (isBrowserFacing(relativePath, source)) {
    if (source.includes("NEXT_PUBLIC_BACKEND_API_HOST")) {
      addViolation(
        file,
        "browser-facing code must not read NEXT_PUBLIC_BACKEND_API_HOST"
      );
    }
    if (source.includes("Settings.apiBaseUrl")) {
      addViolation(
        file,
        "browser-facing code must not read Settings.apiBaseUrl"
      );
    }
  }
}

const baseline = await readBaseline();
const uniqueViolations = [...new Set(violations)].sort();
const newViolations = uniqueViolations.filter(
  (violation) => !baseline.has(violation)
);
const staleBaseline = [...baseline]
  .filter((violation) => !uniqueViolations.includes(violation))
  .sort();

if (newViolations.length > 0 || staleBaseline.length > 0) {
  if (newViolations.length > 0) {
    console.error("Import boundary violations found:\n");
    for (const violation of newViolations) console.error(`- ${violation}`);
  }
  if (staleBaseline.length > 0) {
    console.error("\nImport boundary baseline entries are stale:\n");
    for (const violation of staleBaseline) console.error(`- ${violation}`);
  }
  process.exit(1);
}

const baselineNote =
  baseline.size > 0 ? ` (${baseline.size} legacy violations baselined)` : "";
process.stdout.write(`Import boundary checks passed${baselineNote}.\n`);
