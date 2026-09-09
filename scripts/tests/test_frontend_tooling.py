import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class FrontendToolingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def node(self, script, *args):
        return subprocess.run(["node", str(ROOT / "frontend/scripts" / script), *args], cwd=self.root, capture_output=True, text=True)

    def source(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_generator_refuses_overwrite_and_path_escape(self):
        self.assertEqual(self.node("gen-feature.mjs", "member-tools").returncode, 0)
        facade = self.root / "src/features/member-tools/index.ts"
        facade.write_text("keep this user code")
        self.assertNotEqual(self.node("gen-feature.mjs", "member-tools").returncode, 0)
        self.assertEqual(facade.read_text(), "keep this user code")
        self.assertNotEqual(self.node("gen-feature.mjs", "../escape").returncode, 0)

    def test_facades_comments_and_type_exports_are_valid(self):
        self.source("src/features/members/api/list.ts", 'export type { Tenant } from "@/entities/tenant";\n// import x from "@/app/private"\n')
        result = self.node("check-import-boundaries.mjs")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_private_entity_dynamic_server_and_reverse_imports_fail(self):
        cases = [
            ("src/features/members/api/list.ts", 'import { x } from "@/entities/tenant/model/private";', "public API"),
            ("src/shared/lib/a.ts", 'export { x } from "@/features/members";', "shared code"),
            ("src/features/members/ui/a.tsx", '"use client"; const x = import("@/shared/config/server");', "server-only"),
            ("src/features/members/ui/a.tsx", '"use client"; const x = require("@/shared/http/server");', "server-only"),
            ("src/features/members/ui/a.tsx", '/*' + 'header ' * 100 + '*/\n"use client"; const x = import("@/shared/config/server");', "server-only"),
            ("src/features/members/api/list.ts", 'type T = import("@/entities/tenant/model/private").Tenant;', "public API"),
        ]
        for name, content, message in cases:
            with self.subTest(name=name, content=content):
                shutil.rmtree(self.root / "src", ignore_errors=True)
                self.source(name, content)
                result = self.node("check-import-boundaries.mjs")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_e2e_empty_selection_fails(self):
        env = {**os.environ, "E2E_PORT": "3199"}
        result = subprocess.run(["pnpm", "-C", str(ROOT / "frontend"), "test:e2e", "--list", "nonexistent-contract-test"], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No tests found", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
