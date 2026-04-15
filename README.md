# claude-guardrails

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](#requisitos)

Guardarraíles de seguridad y buenas prácticas para desarrollar con **Claude Code**.

`claude-guardrails` aplica sobre cualquier proyecto —nuevo o existente— un conjunto
coherente de controles que impiden que el asistente introduzca secretos en el
código, salte los hooks de commit o genere monolitos difíciles de mantener.
La instalación es **no destructiva**: cualquier archivo que se modifique se
respalda primero en `.guardrails-backup/<timestamp>/`.

## Qué controla

| Capa | Control |
|---|---|
| **Hooks de Claude Code** | `PreToolUse` sobre `Write` y `Edit` rechaza contenido con patrones de secretos. `PreToolUse` sobre `Bash` rechaza `git commit --no-verify` y commits con secretos en el diff staged. |
| **Permisos del CLI** | `deny` sobre `Write(**/.env)`, `--no-verify`, `rm -rf /*`. `ask` sobre `git push`, `git commit`, `npm publish`, `pip install`. |
| **Pre-commit** | [gitleaks](https://github.com/gitleaks/gitleaks) + [detect-private-key](https://github.com/pre-commit/pre-commit-hooks) + ruff `S105/S106/S107` se ejecutan en cada commit. |
| **Instrucciones del asistente** | `CLAUDE.md` impone estructura modular (sin archivos > 300 líneas, prohibido HTML monolítico, separación de secretos). |
| **Skills y subagente** | `/guardrails-init`, `/secure-init`, `/check-secrets`, `/refactor-monolith` y el agente `security-auditor`. |

## Instalación

Tres modos, todos parten del mismo prompt. Elige el que encaje con tu caso.

### Modo A — Proyecto (compartido con el equipo)

Abre tu proyecto en Claude Code y envía:

```
Aprovisiona este proyecto con claude-guardrails siguiendo las instrucciones de
https://raw.githubusercontent.com/ccicode/claude-guardrails/main/BOOTSTRAP.md
```

Claude clona el repositorio a una carpeta temporal, ejecuta `bootstrap.py` en
dry-run, solicita confirmación, aplica los cambios, instala `pre-commit` y
elimina la copia temporal. Los guardarraíles quedan **dentro del repositorio**
(se commitean, se aplican al equipo entero).

### Modo B — Personal (solo en tu máquina)

Mismo prompt pero indicando modo personal:

```
Aprovisiona mi Claude Code con claude-guardrails en modo personal siguiendo
https://raw.githubusercontent.com/ccicode/claude-guardrails/main/BOOTSTRAP.md
```

Los guardarraíles viven en `~/.claude/` y se aplican **a todos los proyectos**
que abras en tu máquina. No tocan ningún repositorio ni a tu equipo. Ideal
cuando solo quieres protección personal o cuando no tienes permiso para
modificar el repositorio compartido.

### Modo C — Plugin (uso continuado)

```
/plugin marketplace add ccicode/claude-guardrails
/plugin install guardrails@claude-guardrails
```

Después, en el proyecto donde quieras aplicar los guardarraíles:

```
/guardrails-init            # modo proyecto
/guardrails-init --personal # modo personal
```

## Comparativa

| | Modo proyecto | Modo personal |
|---|---|---|
| Dónde vive | `./.claude/`, `./.gitignore`, etc. | `~/.claude/` |
| Alcance | Solo este proyecto, compartido con el equipo | Todos los proyectos, solo tu máquina |
| Toca el repositorio | Sí (no destructivo) | No |
| Instala `pre-commit` | Sí | No |
| Ideal para | Equipos y repositorios con política común | Desarrolladores individuales, clones efímeros |

## Qué instala en el proyecto objetivo

| Ruta | Contenido |
|---|---|
| `.claude/CLAUDE.md` | Reglas permanentes que Claude aplica en cada sesión. |
| `.claude/settings.json` | `permissions` y `hooks` (fusión no destructiva con los existentes). |
| `.claude/skills/` | Skills: `secure-init`, `check-secrets`, `refactor-monolith`. |
| `.claude/agents/security-auditor.md` | Subagente de auditoría de seguridad. |
| `.claude/hooks/` | Hooks Python (`pre_write_guard.py`, `pre_bash_guard.py`) y `secret-patterns.json`. |
| `.gitignore` | Se añaden entradas para `.env`, claves privadas, lockfiles sensibles, etc. |
| `.env.example` | Placeholders documentados. |
| `.pre-commit-config.yaml` | Configuración pinneada a las últimas versiones estables. |
| `.gitleaks.toml` | Allowlist de falsos positivos habituales. |

## Requisitos

- Claude Code.
- Python ≥ 3.10.
- Git.
- `pre-commit` (se instala automáticamente al aplicar; requiere `pip`).

En Windows los hooks funcionan con Python nativo; ya **no** es necesario `bash`
ni `jq` (los hooks en shell fueron reemplazados por equivalentes en Python en
la versión 0.2.0).

## Arquitectura

```
claude-guardrails/
├── BOOTSTRAP.md               Procedimiento que Claude sigue al ser invocado.
├── README.md                  Este archivo.
├── CHANGELOG.md
├── LICENSE                    MIT.
├── .claude-plugin/            Manifiestos del plugin (plugin.json, marketplace.json).
├── .github/workflows/ci.yml   CI: validación de JSON, sintaxis Python, tests.
├── agents/
│   └── security-auditor.md    Subagente con herramientas de solo lectura.
├── hooks/
│   ├── hooks.json             Declaración de PreToolUse para el plugin.
│   ├── pre_write_guard.py     Bloquea Write/Edit con secretos o sobre .env.
│   ├── pre_bash_guard.py      Bloquea git commit/push con secretos o --no-verify.
│   └── secret-patterns.json   Fuente única de patrones de detección.
├── scripts/
│   └── bootstrap.py           Motor de fusión idempotente sin dependencias.
├── skills/
│   ├── guardrails-init/       Orquesta el bootstrap dentro del plugin.
│   ├── secure-init/           Inicialización segura de un proyecto.
│   ├── check-secrets/         Auditoría de secretos hardcodeados.
│   └── refactor-monolith/     División de archivos monolíticos en módulos.
├── templates/                 Archivos que bootstrap.py integra en el proyecto.
│   ├── .claude/{CLAUDE.md,settings.json}
│   ├── env.example
│   ├── gitignore
│   ├── gitleaks.toml
│   └── pre-commit-config.yaml
└── tests/
    └── test_bootstrap.py      Cobertura de merges idempotentes y hooks.
```

## Fuente única de patrones

Todos los consumidores de detección de secretos leen
[`hooks/secret-patterns.json`](hooks/secret-patterns.json). Para ampliar la
cobertura basta con añadir una entrada:

```json
{
  "name": "NUEVO_PROVEEDOR",
  "regex": "...",
  "severity": "ALTO",
  "description": "..."
}
```

Los tests en `tests/test_bootstrap.py` validan automáticamente que el escáner
y los hooks detectan el mismo conjunto.

## Reversión

Cada corrida con `--apply` respalda los archivos modificados en
`.guardrails-backup/<timestamp>/`. Para revertir basta con copiarlos de vuelta
sobre sus rutas originales. Los archivos creados desde cero (donde no había
original) se eliminan manualmente.

## Desarrollo

```bash
# Validar manifiestos y sintaxis
python -c "import json; [json.load(open(p)) for p in ['.claude-plugin/plugin.json', '.claude-plugin/marketplace.json', 'hooks/hooks.json', 'hooks/secret-patterns.json']]"
python -c "import ast; [ast.parse(open(p).read()) for p in ['scripts/bootstrap.py', 'hooks/pre_write_guard.py', 'hooks/pre_bash_guard.py']]"

# Suite de pruebas
python -m unittest discover -s tests -v
```

CI replica estos pasos en Linux y Windows sobre Python 3.10 y 3.12.

## Licencia

MIT — ver [LICENSE](LICENSE).
