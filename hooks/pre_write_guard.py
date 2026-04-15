#!/usr/bin/env python3
"""PreToolUse hook para Write / Edit.

Bloquea:
  1. Escritura directa sobre archivos .env reales (permite .env.example y variantes).
  2. Contenido con patrones de secretos definidos en secret-patterns.json.

Protocolo Claude Code: lee un payload JSON por stdin y, para denegar, emite
un JSON con hookSpecificOutput.permissionDecision == "deny". Siempre sale con
código 0 (la decisión viaja en el JSON, no en el exit code).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PATTERNS_FILE = Path(__file__).parent / "secret-patterns.json"


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


def is_placeholder(line: str, placeholder_re: re.Pattern[str] | None) -> bool:
    if placeholder_re is None:
        return False
    return bool(placeholder_re.search(line))


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""
    content = tool_input.get("content") or tool_input.get("new_string") or ""

    cfg = load_config()
    protected = set(cfg.get("protected_filenames", []))

    # Regla 1: archivos .env reales están prohibidos (permitir .env.example, etc.)
    if file_path:
        basename = Path(file_path).name
        if basename in protected:
            deny(
                f"Está prohibido escribir `{basename}` desde Claude Code. "
                "Usa `.env.example` con placeholders; los valores reales los "
                "coloca el usuario manualmente y el archivo debe estar en `.gitignore`."
            )

    if not content:
        return 0

    # Regla 2: escaneo de patrones en el contenido.
    placeholder_raw = cfg.get("placeholder_regex")
    placeholder_re = re.compile(placeholder_raw) if placeholder_raw else None

    for entry in cfg.get("patterns", []):
        try:
            regex = re.compile(entry["regex"])
        except (KeyError, re.error):
            continue
        for line_no, line in enumerate(content.splitlines(), start=1):
            if len(line) > 4000:
                continue
            if not regex.search(line):
                continue
            if is_placeholder(line, placeholder_re):
                break
            preview = line.strip()[:120]
            deny(
                f"Se detectó un posible secreto hardcodeado "
                f"(tipo: {entry['name']}) en la línea {line_no}: `{preview}`. "
                "Mueve el valor a una variable de entorno y deja un placeholder "
                "en `.env.example`. Si es un falso positivo, renómbralo o usa un "
                "valor de ejemplo tipo `your-api-key-here`."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
