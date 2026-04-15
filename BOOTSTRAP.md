<!--
  Este archivo contiene instrucciones para Claude Code, no para personas.
  Cuando un usuario solicite "aprovisionar este proyecto con claude-guardrails"
  apuntando a este URL, Claude debe seguir el procedimiento al pie de la letra.
-->

# Instrucciones para Claude Code — Aprovisionar con `claude-guardrails`

Si estás leyendo esto, el usuario solicitó aplicar `claude-guardrails`. Ejecuta
el instalador **sin improvisar**, sin escribir código a mano, y **sin hacer
preguntas innecesarias**. La solicitud del usuario ya es la confirmación. Tu
trabajo es detectar el modo correcto, ejecutar y reportar.

## Detección automática de modo

**No preguntar.** Determinar el modo con esta lógica:

1. Si el usuario escribió explícitamente "personal" o `--personal` → modo
   **personal**.
2. Si el `cwd` es `$HOME` o `~` → modo **personal**.
3. En cualquier otro caso → modo **proyecto**.

## Procedimiento

Ejecutar los pasos en orden. **No detenerse a pedir confirmación entre pasos.**

### 1. Obtener el repositorio

Si el `cwd` ya es el propio repo `claude-guardrails`, usarlo como `--source`
directamente y saltar el clone.

De lo contrario, clonar a una carpeta temporal:

```bash
git clone --depth=1 https://github.com/ccicode/claude-guardrails.git /tmp/claude-guardrails-src
```

### 2. Identificar el proyecto objetivo

El objetivo es el `cwd` del usuario. Verificar con `pwd`.

- Si el `cwd` es la carpeta del propio plugin clonado **y** el usuario no
  indicó otro proyecto, detenerse y preguntar cuál es el proyecto real. Esta es
  la **única pregunta permitida** en todo el flujo.
- Si el objetivo no tiene `.git/`, continuar normalmente. Anotar un `WARN` en
  el reporte final. **No preguntar si ejecutar `git init`.**

### 3. Ejecutar bootstrap (apply directo)

Ejecutar `bootstrap.py` con `--apply --yes` directamente. El script genera
backups automáticos en `.guardrails-backup/<YYYYMMDD-HHMMSS>/` antes de
modificar cualquier archivo, por lo que no se necesita un dry-run previo.

**Modo proyecto:**

```bash
python /tmp/claude-guardrails-src/scripts/bootstrap.py \
  --source /tmp/claude-guardrails-src \
  --target "$(pwd)" \
  --apply --yes
```

**Modo personal:**

```bash
python /tmp/claude-guardrails-src/scripts/bootstrap.py \
  --source /tmp/claude-guardrails-src \
  --personal \
  --apply --yes
```

> En Windows, si `python` no está en PATH, probar `py -3`.

### 4. Limpieza

```bash
rm -rf /tmp/claude-guardrails-src
```

Omitir si se usó el repo local como source.

### 5. Post-instalación automática (modo proyecto)

**No detenerse. No preguntar. Ejecutar todo inmediatamente después del apply.**

#### 5a. Auditoría de secretos en código existente

Escanear todos los archivos del proyecto (excluyendo `.git/`, `node_modules/`,
`venv/`, `__pycache__/`, `.guardrails-backup/`) buscando:

- API keys, tokens, passwords hardcodeados
- Connection strings (MongoDB, PostgreSQL, Redis, SMTP, etc.)
- URLs con credenciales embebidas
- IPs internas, nombres de buckets, rutas absolutas con usuario

Usar los patrones de `hooks/secret-patterns.json` como base, pero también
buscar patrones específicos del stack detectado (Python: `os.environ.get` sin
usar, strings con `sk-`, `AKIA`, `ghp_`, `AIza`, `BEGIN.*PRIVATE KEY`).

#### 5b. Remediación automática de secretos

Si se detectan secretos hardcodeados:

1. **Mover cada valor a variable de entorno**: reemplazar el valor literal en el
   código por `os.environ["NOMBRE_VARIABLE"]` (Python) o `process.env.NOMBRE`
   (Node.js) según el stack.
2. **Agregar la variable a `.env.example`** con un placeholder descriptivo
   (e.g., `MONGO_URI=mongodb://usuario:contraseña@host:puerto/db`).
3. **Crear `.env`** copiando `.env.example` si no existe. Los valores reales se
   dejan como placeholders — el usuario los completa después.

No pedir permiso para modificar código. Esto es remediación de seguridad, no
una feature. Hacer backup del archivo antes de editarlo (copiar a
`.guardrails-backup/<timestamp>/`).

#### 5c. Detección de archivos monolíticos

Buscar archivos `>300 líneas` (regla del CLAUDE.md). Si se encuentran:

- Listarlos en el reporte con su conteo de líneas.
- **No refactorizar automáticamente** — eso requiere contexto del dominio.
  Solo reportar y sugerir usar `/refactor-monolith` después.

#### 5d. Validación de .gitignore

Verificar que `.gitignore` incluye al menos: `.env`, `.env.local`,
`.env.*.local`. Si faltan, agregarlas.

### 6. Reporte final

Mostrar un reporte único consolidado:

```
claude-guardrails aplicado en <ruta>

  Archivos guardrails creados:  N
  Archivos guardrails merged:   M  (backup en .guardrails-backup/YYYYMMDD-HHMMSS/)
  Secretos detectados:          X
  Secretos remediados:          Y  (movidos a variables de entorno)
  Archivos >300 líneas:         Z  (usar /refactor-monolith)

  Acción requerida del usuario:
  - Completar los valores reales en .env (no subirlo a git).
  - Reiniciar Claude Code para cargar skills y hooks.
```

**Modo personal** — mostrar solo la parte de guardrails (no hay auditoría de
proyecto):

```
claude-guardrails (personal) aplicado en ~/.claude/

  Archivos creados:     N
  Archivos modificados: M  (backup en ~/.guardrails-backup/YYYYMMDD-HHMMSS/)

  Reiniciar Claude Code para activar skills y hooks en todos los proyectos.
```

## Idempotencia

Si el bootstrap detecta que las guardrails ya están instaladas (`.claude/hooks/`
existe con los archivos de guardrails), **no reinstalar**. En su lugar:

1. Informar: "guardrails ya instalado, ejecutando auditoría."
2. Saltar directamente al paso 5 (post-instalación).
3. Re-escanear secretos y monolitos por si el código cambió desde la última vez.

## Reglas duras

- **Nunca** escribas los templates a mano en el proyecto objetivo. Siempre vía
  `bootstrap.py`.
- **Nunca** elimines archivos del proyecto objetivo. El bootstrap solo crea o
  fusiona.
- **Nunca** preguntes por confirmación. La solicitud del usuario es la
  confirmación. Los backups automáticos en `.guardrails-backup/` garantizan
  reversibilidad.
- La **única pregunta permitida** es cuando el `cwd` es el propio repo
  clonado de `claude-guardrails` y no queda claro cuál es el proyecto destino.
- **Sí** modificar código productivo cuando se trata de remediación de
  secretos (mover valores hardcodeados a variables de entorno). Siempre hacer
  backup antes de editar. Nunca modificar lógica de negocio, solo la fuente
  del valor secreto.

## Override interactivo

Si el usuario dice explícitamente "paso a paso", "preguntando", o
"con confirmación", entonces sí detenerse antes de aplicar y mostrar el
dry-run (ejecutar sin `--apply`). Este es el único caso donde se permite
el flujo interactivo.

## Errores comunes

| Síntoma | Causa probable | Acción |
|---|---|---|
| `python no encontrado` | Python no está en `PATH`. | Intentar `py -3`. Si tampoco funciona, informar al usuario que necesita Python 3.10+. |
| `git clone falló` | Credenciales o URL errada. | Verificar acceso a la red o la URL del repositorio. |
| `JSON inválido` en `bootstrap.py` | El proyecto ya tenía `.claude/settings.json` con JSON roto. | Abrirlo, reparar la sintaxis y reintentar. |
| Usuario quiere revertir | — | Copiar los archivos de `.guardrails-backup/<timestamp>/` sobre su ubicación original. Los archivos creados desde cero se eliminan manualmente. |
