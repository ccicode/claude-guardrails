#!/usr/bin/env python3
"""PreToolUse hook para Bash.

Bloquea:
  1. Uso de `--no-verify` en cualquier subcomando git (salta pre-commit).
  2. `git commit` o `git push` con secretos presentes en el diff staged.

Protocolo idéntico a pre_write_guard.py: exit 0 siempre; la decisión `deny`
viaja como JSON en stdout.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PATTERNS_FILE = Path(__file__).parent / "secret-patterns.json"

GIT_COMMIT_OR_PUSH = re.compile(r"\bgit\s+(commit|push)\b")
NO_VERIFY = re.compile(r"--no-verify\b")


def deny(reason: str) -> None:
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(out))
    sys.exit(0)


def load_config() -> dict:
    try:
        return json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def staged_diff() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    cmd = (payload.get("tool_input") or {}).get("command", "") or ""
    if not cmd:
        return 0

    # Regla 1: prohibido --no-verify.
    if NO_VERIFY.search(cmd):
        deny(
            "El flag `--no-verify` salta los hooks de seguridad y no está "
            "permitido. Si un hook está fallando, resuelve la causa en lugar "
            "de saltarlo."
        )

    # Regla 2: escanear el diff staged cuando se trata de commit / push.
    if not GIT_COMMIT_OR_PUSH.search(cmd):
        return 0

    diff = staged_diff()
    if not diff:
        return 0

    cfg = load_config()
    placeholder_raw = cfg.get("placeholder_regex")
    placeholder_re = re.compile(placeholder_raw) if placeholder_raw else None

    added_lines = [ln for ln in diff.splitlines() if ln.startswith("+") and not ln.startswith("+++")]

    for entry in cfg.get("patterns", []):
        try:
            regex = re.compile(entry["regex"])
        except (KeyError, re.error):
            continue
        for line in added_lines:
            if not regex.search(line):
                continue
            if placeholder_re and placeholder_re.search(line):
                continue
            preview = line[:120]
            deny(
                f"Se detectó un posible secreto en el diff staged "
                f"(tipo: {entry['name']}). Línea: `{preview}`. "
                "Quítalo del commit con `git reset HEAD <archivo>`, mueve el "
                "valor a `.env` (que debe estar en `.gitignore`) y deja solo "
                "un placeholder en `.env.example`."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
