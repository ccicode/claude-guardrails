# Changelog

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y
el proyecto se adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-04-14

### Agregado
- `LICENSE` (MIT) y `CHANGELOG.md`.
- Fuente única de patrones de secretos en `hooks/secret-patterns.json`, consumida
  por `bootstrap.py` y por los hooks.
- Hooks reescritos en Python (`hooks/pre_write_guard.py`, `hooks/pre_bash_guard.py`).
  Elimina la dependencia de `jq` y `git-bash` en Windows.
- **Modo `--personal`** en `bootstrap.py`: instala en `~/.claude/` sin tocar el
  repositorio. Los comandos de hook en `settings.json` se reescriben con ruta
  absoluta para funcionar desde cualquier proyecto. Omite `.gitignore`,
  `.env.example`, `.pre-commit-config.yaml` y `.gitleaks.toml` (son archivos
  por repositorio, no por usuario).
- Suite de tests `tests/test_bootstrap.py` (merges idempotentes, detección de
  secretos, modo personal).
- Workflow de integración continua `.github/workflows/ci.yml`.

### Cambiado
- Renombrado del proyecto: `skillcci` → `guardrails`. El repositorio pasa a
  llamarse `claude-guardrails`.
- Directorio de respaldos: `.skillcci-backup/` → `.guardrails-backup/`.
- Skill de bootstrap: `skillcci-init` → `guardrails-init`.
- Tono de todos los documentos normalizado a español neutro profesional.
- Plantilla `CLAUDE.md` generalizada (sin referencias a equipos o dominios específicos).
- Versiones pinneadas en `pre-commit-config.yaml` actualizadas al 2026-04:
  `gitleaks@v8.30.1`, `pre-commit-hooks@v6.0.0`, `ruff-pre-commit@v0.15.10`.

### Eliminado
- Hooks en bash (`pre-write-secret-scan.sh`, `pre-bash-git-guard.sh`).

## [0.1.0] — 2025

Versión inicial publicada como `skillcci`.
