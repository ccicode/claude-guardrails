<!--
  Instrucciones para Claude Code. NO para personas.
  Claude: ejecuta esto al pie de la letra, sin improvisar, sin preguntar.
-->

# claude-guardrails — Bootstrap automático

**CONTEXTO**: el usuario pidió configurar guardrails. Tu trabajo: ejecutar todo
y entregar un reporte. Sin preguntas. Sin confirmaciones. La solicitud ya es
la autorización.

**IMPORTANTE — Eficiencia:**
- **No verificar** archivos creados por `bootstrap.py`. Su output ya lo reporta.
  No hacer `cat .gitignore`, `ls .claude/`, ni leer archivos recién instalados.
- **No escribir memoria** durante este proceso. Cero tool calls a Write sobre
  directorios de memoria. El foco es: instalar → auditar → remediar → reportar.
- **No hacer greps exploratorios** innecesarios. Ir directo a los patrones de
  secretos definidos abajo.

## Modo

Detectar automáticamente:

- Usuario dijo "personal" o `--personal` → **personal**
- `cwd` es `$HOME` → **personal**
- Cualquier otro caso → **proyecto**

## Ejecución

Ejecutar estos comandos en orden, **sin detenerse entre pasos**.

### Paso 1 — Clonar y ejecutar bootstrap

```bash
rm -rf /tmp/claude-guardrails-src 2>/dev/null
git clone --depth=1 https://github.com/ccicode/claude-guardrails.git /tmp/claude-guardrails-src
```

> **Nota Windows**: si `git clone` falla por SSL, agregar `-c http.sslVerify=false`.

Si el `cwd` ya es el repo `claude-guardrails`, usarlo como `--source` y saltar
el clone. Si el `cwd` es el propio clone, preguntar cuál es el proyecto
(única pregunta permitida).

Luego ejecutar:

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

> Si `python` no está en PATH: probar `py -3`.

### Paso 2 — Limpieza

```bash
rm -rf /tmp/claude-guardrails-src
```

### Paso 3 — Auditoría y remediación (solo modo proyecto)

**No detenerse. No preguntar. Ejecutar inmediatamente.**

Usar la herramienta **Agent** (subagente) para paralelizar la auditoría:

Ejecutar estas **3 búsquedas en paralelo** (usar Grep, no Bash):

**Grep 1 — Tokens y keys:**
```
pattern: (sk-[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}|AIza[0-9A-Za-z_-]{35}|BEGIN [A-Z ]*PRIVATE KEY|xox[baprs]-[0-9a-zA-Z-]+)
```

**Grep 2 — Connection strings con credenciales:**
```
pattern: (mongodb(\+srv)?://[^\s'"]+:[^\s'"@]+@|postgres(ql)?://[^\s'"]+:[^\s'"@]+@|redis://[^\s'"]*:[^\s'"@]+@|smtp://[^\s'"]+:[^\s'"@]+@)
```

**Grep 3 — Passwords/secrets hardcodeados en asignaciones:**
```
pattern: (password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['"][^'"\s${}]{6,}['"]
```

Excluir: `.git/`, `node_modules/`, `venv/`, `__pycache__/`,
`.guardrails-backup/`, `.env.example`, `.gitleaks.toml`.

**En paralelo**, buscar archivos >300 líneas:
```bash
find . -type f \( -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.html" \) \
  -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.venv/*" \
  -not -path "./__pycache__/*" -not -path "./.guardrails-backup/*" \
  -exec wc -l {} + 2>/dev/null | awk '$1 > 300 && $2 != "total" {print $1, $2}' | sort -rn
```

Y verificar `.gitignore`:
```bash
grep -c "^\.env$" .gitignore && grep -c "^\.env\.local$" .gitignore
```

Con los resultados, pasar al paso 4 **sin detenerse**.

### Paso 4 — Remediación automática

Con los resultados de la auditoría:

**Secretos encontrados:**
1. Reemplazar cada valor hardcodeado por `os.environ["NOMBRE"]` (Python) o
   `process.env.NOMBRE` (Node.js).
2. Agregar la variable a `.env.example` con placeholder descriptivo.
3. Crear `.env` copiando `.env.example` si no existe.
4. Hacer backup del archivo antes de editarlo.

**`.gitignore` incompleto:** agregar las entradas faltantes.

**Archivos monolíticos:** solo listar en el reporte. No refactorizar (requiere
contexto de dominio). Sugerir `/refactor-monolith`.

### Paso 5 — Reporte

```
claude-guardrails aplicado en <ruta>

  Archivos guardrails creados:  N
  Archivos guardrails merged:   M
  Secretos detectados:          X
  Secretos remediados:          Y  (movidos a variables de entorno)
  Archivos >300 líneas:         Z  (usar /refactor-monolith)

  Acción del usuario:
  - Completar valores reales en .env (no subirlo a git).
  - Reiniciar Claude Code para cargar skills y hooks.
```

## Idempotencia

Si `.claude/hooks/pre_write_guard.py` ya existe → guardrails ya instalado.
Informar "guardrails ya instalado, ejecutando auditoría" y saltar al paso 3.

## Reglas

- Nunca escribir templates a mano. Siempre vía `bootstrap.py`.
- Nunca eliminar archivos del proyecto.
- Nunca preguntar por confirmación (backups garantizan reversibilidad).
- Sí modificar código para mover secretos a variables de entorno (con backup).
- Nunca modificar lógica de negocio.

## Override

Si el usuario dice "paso a paso" o "con confirmación" → dry-run primero
(omitir `--apply`), mostrar plan, esperar OK.
