import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import ts from "typescript";

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

function imports(source, file) {
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  const found = [];
  function visit(node) {
    if (
      (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) &&
      node.moduleSpecifier &&
      ts.isStringLiteralLike(node.moduleSpecifier)
    ) {
      found.push(node.moduleSpecifier.text);
    }
    if (
      ts.isCallExpression(node) &&
      (node.expression.kind === ts.SyntaxKind.ImportKeyword ||
        (ts.isIdentifier(node.expression) &&
          node.expression.text === "require"))
    ) {
      const first = node.arguments[0];
      if (first && ts.isStringLiteralLike(first)) found.push(first.text);
    }
    if (
      ts.isImportTypeNode(node) &&
      ts.isLiteralTypeNode(node.argument) &&
      ts.isStringLiteralLike(node.argument.literal)
    ) {
      found.push(node.argument.literal.text);
    }
    ts.forEachChild(node, visit);
  }
  visit(ast);
  return found;
}

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

const clientModuleCache = new Map();
function isClientModule(source) {
  if (clientModuleCache.has(source)) return clientModuleCache.get(source);
  const ast = ts.createSourceFile(
    "module.tsx",
    source,
    ts.ScriptTarget.Latest,
    true
  );
  let client = false;
  for (const statement of ast.statements) {
    if (
      !ts.isExpressionStatement(statement) ||
      !ts.isStringLiteral(statement.expression)
    )
      break;
    if (statement.expression.text === "use client") client = true;
  }
  clientModuleCache.set(source, client);
  return client;
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
  if (
    isBrowserFacing(relativePath, source) &&
    (["next/headers", "server-only"].includes(specifier) ||
      /^src\/shared\/(config\/server|http\/(server|bff|session-cookies))(?:\.[cm]?[jt]sx?)?$/.test(
        resolved ?? ""
      ))
  ) {
    addViolation(
      file,
      `browser-facing code must not import server-only module ${specifier}`
    );
  }
  if (!resolved) return;
  resolved = resolved.replace(/\.[cm]?[jt]sx?$/, "");

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

  if (
    featureName(relativePath) &&
    importedEntity &&
    !new RegExp(`^src/entities/${importedEntity}(?:/index)?/?$`).test(resolved)
  ) {
    addViolation(
      file,
      `feature imports must use the entity public API, not ${specifier}`
    );
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

  for (const specifier of imports(source, file)) {
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
