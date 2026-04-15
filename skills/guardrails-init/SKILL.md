---
name: guardrails-init
description: Instala claude-guardrails en el proyecto actual y ejecuta auditoría de seguridad. Invocar cuando el usuario pida configurar guardrails, seguridad, o apunte al repo ccicode/claude-guardrails.
allowed-tools: Bash(git *), Bash(python *), Bash(py *), Bash(rm *), Read, Glob
context: fork
---

# guardrails-init

Instalar guardrails y lanzar auditoría. Sin preguntas.

## Detección de modo

- Usuario dijo "personal" → `--personal`
- Cualquier otro caso → proyecto

## Estado actual del proyecto

```!
pwd
ls .claude/hooks/pre_write_guard.py 2>/dev/null && echo "GUARDRAILS_INSTALLED=true" || echo "GUARDRAILS_INSTALLED=false"
```

## Ejecución

Si `GUARDRAILS_INSTALLED=true`: informar "guardrails ya instalado" y saltar
a la auditoría (paso 3 abajo).

Si `GUARDRAILS_INSTALLED=false`:

### Paso 1 — Instalar

```bash
rm -rf /tmp/claude-guardrails-src 2>/dev/null
git clone --depth=1 https://github.com/ccicode/claude-guardrails.git /tmp/claude-guardrails-src
```

**Proyecto:**
```bash
python /tmp/claude-guardrails-src/scripts/bootstrap.py \
  --source /tmp/claude-guardrails-src --target "$(pwd)" --apply --yes
```

**Personal:**
```bash
python /tmp/claude-guardrails-src/scripts/bootstrap.py \
  --source /tmp/claude-guardrails-src --personal --apply --yes
```

### Paso 2 — Limpiar

```bash
rm -rf /tmp/claude-guardrails-src
```

### Paso 3 — Auditar y remediar

Lanzar el agente `security-auditor` con el prompt:

> Audita y remedia el proyecto en `<cwd>`. Lee TODOS los archivos de código
> del proyecto. Busca secretos con tu inteligencia, no solo con regex.
> Remedia cada secreto moviéndolo a variables de entorno. Crea .env con los
> valores REALES. La app debe funcionar igual después. Reporta al final.

Mostrar el reporte al usuario.
