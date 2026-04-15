"""Pruebas funcionales del bootstrap.

Cubren los casos críticos:

1. Dry-run en un proyecto vacío: no escribe nada.
2. Apply en proyecto vacío: crea los archivos esperados.
3. Apply idempotente: una segunda corrida no rompe ni duplica reglas.
4. Detección de un secreto conocido en el target.
5. Hook de Write rechaza escritura a `.env` y a contenido con secretos.

Se ejecutan solo con la stdlib. Deben pasar en Python 3.10+ y en Windows.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.py"
PRE_WRITE_GUARD = ROOT / "hooks" / "pre_write_guard.py"
PRE_BASH_GUARD = ROOT / "hooks" / "pre_bash_guard.py"


def run_bootstrap(target: Path, *extra: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(BOOTSTRAP), "--source", str(ROOT), "--target", str(target), *extra]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def run_hook(script: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload),
        capture_output=True, text=True, timeout=15,
    )


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="guardrails-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dry_run_does_not_write(self) -> None:
        result = run_bootstrap(self.tmp)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[dry-run]", result.stdout)
        self.assertFalse((self.tmp / ".gitignore").exists())
        self.assertFalse((self.tmp / ".claude").exists())

    def test_apply_creates_expected_files(self) -> None:
        result = run_bootstrap(self.tmp, "--apply", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        for rel in (
            ".gitignore",
            ".env.example",
            ".pre-commit-config.yaml",
            ".gitleaks.toml",
            ".claude/CLAUDE.md",
            ".claude/settings.json",
            ".claude/hooks/pre_write_guard.py",
            ".claude/hooks/pre_bash_guard.py",
            ".claude/hooks/secret-patterns.json",
        ):
            self.assertTrue((self.tmp / rel).exists(), f"falta {rel}")

    def test_apply_is_idempotent(self) -> None:
        run_bootstrap(self.tmp, "--apply", "--yes")
        before = (self.tmp / ".gitignore").read_text(encoding="utf-8")
        second = run_bootstrap(self.tmp, "--apply", "--yes")
        self.assertEqual(second.returncode, 0, second.stderr)
        after = (self.tmp / ".gitignore").read_text(encoding="utf-8")
        self.assertEqual(before, after, "el bootstrap no debe modificar archivos ya aplicados")

    def test_detects_known_secret(self) -> None:
        src_dir = self.tmp / "src"
        src_dir.mkdir()
        (src_dir / "leak.py").write_text(
            'OPENAI_API_KEY = "sk-proj-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"\n',
            encoding="utf-8",
        )
        result = run_bootstrap(self.tmp)
        self.assertIn("secretos detectados", result.stdout.lower())

    def test_personal_mode_skips_project_files(self) -> None:
        """En modo personal no se escriben archivos del repositorio."""
        result = run_bootstrap(self.tmp, "--personal", "--target", str(self.tmp), "--apply", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        for rel in (".gitignore", ".env.example", ".pre-commit-config.yaml", ".gitleaks.toml"):
            self.assertFalse((self.tmp / rel).exists(), f"{rel} no debería crearse en --personal")
        for rel in (
            ".claude/CLAUDE.md",
            ".claude/settings.json",
            ".claude/hooks/pre_write_guard.py",
            ".claude/hooks/secret-patterns.json",
        ):
            self.assertTrue((self.tmp / rel).exists(), f"falta {rel}")

    def test_personal_mode_uses_absolute_hook_paths(self) -> None:
        """Los hooks de settings.json deben apuntar a rutas absolutas en --personal."""
        run_bootstrap(self.tmp, "--personal", "--target", str(self.tmp), "--apply", "--yes")
        settings = json.loads((self.tmp / ".claude" / "settings.json").read_text(encoding="utf-8"))
        commands = [
            h["command"]
            for entries in settings.get("hooks", {}).values()
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        self.assertTrue(commands, "no hay hooks en settings.json")
        tmp_posix = str(self.tmp).replace("\\", "/")
        for cmd in commands:
            self.assertIn(tmp_posix, cmd,
                          f"el comando no contiene la ruta absoluta esperada: {cmd}")


class HookTests(unittest.TestCase):
    def _parse_decision(self, stdout: str) -> str | None:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return None
        return data.get("hookSpecificOutput", {}).get("permissionDecision")

    def test_write_hook_blocks_dotenv(self) -> None:
        payload = {"tool_input": {"file_path": ".env", "content": "FOO=bar"}}
        res = run_hook(PRE_WRITE_GUARD, payload)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(self._parse_decision(res.stdout), "deny")

    def test_write_hook_blocks_secret_content(self) -> None:
        payload = {
            "tool_input": {
                "file_path": "src/app.py",
                "content": 'API_KEY = "sk-proj-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"\n',
            }
        }
        res = run_hook(PRE_WRITE_GUARD, payload)
        self.assertEqual(self._parse_decision(res.stdout), "deny")

    def test_write_hook_allows_placeholder(self) -> None:
        payload = {
            "tool_input": {
                "file_path": ".env.example",
                "content": "OPENAI_API_KEY=your-api-key-here\n",
            }
        }
        res = run_hook(PRE_WRITE_GUARD, payload)
        self.assertNotEqual(self._parse_decision(res.stdout), "deny")

    def test_bash_hook_blocks_no_verify(self) -> None:
        payload = {"tool_input": {"command": "git commit --no-verify -m test"}}
        res = run_hook(PRE_BASH_GUARD, payload)
        self.assertEqual(self._parse_decision(res.stdout), "deny")


if __name__ == "__main__":
    unittest.main()
