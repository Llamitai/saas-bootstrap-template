import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [operation, item, kind = "change"] = process.argv.slice(2);
if (!["status", "check"].includes(operation) || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(item ?? "") || !["change", "spec"].includes(kind)) {
  console.error("Usage: openspec.mjs status <change> | check <id> [change|spec]");
  process.exit(1);
}
const args = operation === "status"
  ? ["status", "--change", item, "--json"]
  : ["validate", item, "--type", kind, "--strict", "--no-interactive"];
const result = spawnSync(path.join(root, "node_modules/.bin/openspec"), args, { cwd: root, stdio: "inherit", env: { ...process.env, OPENSPEC_TELEMETRY: "0" } });
if (result.error) console.error("Install root tooling with pnpm install --frozen-lockfile:", result.error.message);
process.exit(result.status ?? 1);
