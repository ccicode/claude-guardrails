---
name: guardrails-init
description: Aprovisiona claude-guardrails en modo proyecto (dentro del repositorio actual, compartido con el equipo) o personal (en ~/.claude/, solo para el desarrollador). Fusiona sin sobrescribir .gitignore, .env.example, .pre-commit-config.yaml, .claude/CLAUDE.md y .claude/settings.json; escanea secretos hardcodeados; instala pre-commit (solo en modo proyecto).
allowed-tools: Bash(python *), Bash(python3 *), Bash(py *), Bash(pip install *), Bash(python -m pip install *), Bash(pre-commit install), Bash(pre-commit run *), Bash(git init), Bash(git status), Bash(ls *), Bash(pwd), Read, Write, Glob
---

# guardrails-init — Aprovisionar guardarraíles

Fusiona los guardarraíles de `claude-guardrails` sin sobrescribir configuración
existente. Todo archivo modificado se respalda previamente en
`.guardrails-backup/`.

## 0. Elegir el modo

Preguntar una sola vez:

> **¿Modo de instalación?**
>
> - **Proyecto** (default): los guardarraíles viven dentro del repositorio
>   actual, se commitean y aplican al resto del equipo.
> - **Personal**: viven en `~/.claude/` y se aplican a todos los proyectos
>   abiertos en esta máquina. No tocan el repositorio.

Si el usuario pasa `--personal` como argumento o elige "personal", agregar el
flag `--personal` al comando del paso 4 y omitir el paso 5 (pre-commit).

## Procedimiento

### 1. Resolver la raíz del plugin

El plugin reside en `$CLAUDE_PLUGIN_ROOT`. El motor de instalación está en
`$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py` y las plantillas en
`$CLAUDE_PLUGIN_ROOT/templates/`.

Si la variable no está disponible, busca hacia arriba desde el directorio
actual un directorio con `.claude-plugin/plugin.json`; esa es la raíz.

### 2. Verificar el proyecto objetivo

El objetivo es el `cwd`. Confirma con `pwd` que es el proyecto correcto. En
caso de duda, pregunta una sola vez.

Si no existe `.git/`, pregunta: **"El proyecto no está inicializado con Git.
¿Ejecuto `git init`?"**. Con respuesta afirmativa, ejecuta `git init`; en caso
contrario, continúa (el paso de `pre-commit` se omitirá).

### 3. Dry-run

**Modo proyecto:**

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" \
  --source "$CLAUDE_PLUGIN_ROOT" \
  --target "$(pwd)"
```

**Modo personal:**

```bash
python "$CLAUDE_PLUGIN_ROOT/scripts/bootstrap.py" \
  --source "$CLAUDE_PLUGIN_ROOT" \
  --personal
```

Sin `--apply` el script solo reporta el plan. Mostrar el output completo y
preguntar: **"¿Aplico estos cambios?"**.

### 4. Apply

Con aprobación explícita, agregar `--apply --yes` al comando anterior.

El bootstrap respalda los archivos que modifica:
- Modo proyecto: `./.guardrails-backup/<timestamp>/`.
- Modo personal: `~/.guardrails-backup/<timestamp>/`.

### 5. Instalar pre-commit (solo modo proyecto)

```bash
python -m pip install --user pre-commit
pre-commit install
```

En modo personal este paso se omite: pre-commit es una herramienta por
repositorio, no por usuario.

Cualquier fallo es `WARN`, no fatal. El usuario puede reintentar.

### 6. Reporte final

Presenta el resumen estándar:

```
claude-guardrails aplicado en <ruta>

  Archivos creados:     N
  Archivos modificados: M   (respaldo en .guardrails-backup/YYYYMMDD-HHMMSS/)
  Secretos detectados:  X

Próximos pasos:
  1. Crear .env real a partir de .env.example (nunca incluirlo en git).
  2. (si hubo secretos) ejecutar /check-secrets para refactor asistido.
  3. Skills disponibles: /secure-init, /check-secrets, /refactor-monolith.
```

## Reglas duras

- **Nunca** escribas plantillas manualmente en el proyecto. Siempre vía
  `bootstrap.py`.
- **Nunca** ejecutes `--apply` sin mostrar antes el dry-run y obtener
  confirmación.
- **Nunca** elimines archivos del proyecto. El bootstrap solo crea o fusiona.
- **Nunca** modifiques código productivo ni archivos de dependencias
  (`pyproject.toml`, `package.json`, etc.). Los secretos solo se reportan.

## Errores comunes

- `python no encontrado` → solicitar instalar Python 3.10+ y reintentar.
- `JSON inválido` en el reporte → el proyecto tiene `.claude/settings.json`
  con sintaxis rota; repararlo antes de reintentar.
- `El usuario quiere revertir` → restaurar desde
  `.guardrails-backup/<timestamp>/`. Los archivos creados desde cero se borran
  manualmente.
