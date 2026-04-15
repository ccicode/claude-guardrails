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
- Si el objetivo no tiene `.git/`, continuar sin instalar `pre-commit`. Anotar
  un `WARN` en el reporte final. **No preguntar si ejecutar `git init`.**

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

### 4. Instalar pre-commit

Solo en **modo proyecto** y solo si el proyecto tiene `.git/`.

```bash
python -m pip install --user pre-commit 2>&1 || true
pre-commit install 2>&1 || true
```

Si falla, anotar un `WARN` no fatal en el reporte. **No detenerse.**

### 5. Limpieza

```bash
rm -rf /tmp/claude-guardrails-src
```

Omitir si se usó el repo local como source.

### 6. Reporte final

Mostrar el output del bootstrap.py y complementar con:

**Modo proyecto:**

```
claude-guardrails aplicado en <ruta>

  Archivos creados:     N
  Archivos modificados: M   (respaldo en .guardrails-backup/YYYYMMDD-HHMMSS/)
  Secretos detectados:  X

Próximos pasos:
  1. Crear el archivo .env real a partir de .env.example (no incluirlo en git).
  2. (si hubo secretos) invocar /check-secrets para un refactor asistido.
  3. Reiniciar Claude Code para cargar las skills:
     /guardrails-init, /secure-init, /check-secrets, /refactor-monolith.
```

**Modo personal:**

```
claude-guardrails (personal) aplicado en ~/.claude/

  Archivos creados:     N
  Archivos modificados: M   (respaldo en ~/.guardrails-backup/YYYYMMDD-HHMMSS/)

Próximos pasos:
  1. Reiniciar Claude Code para cargar las skills y los hooks globales.
  2. Abrir cualquier proyecto: los guardarraíles ya están activos en todos.
  3. Para agregar las reglas a un proyecto específico (compartirlas con el
     equipo), ejecutar /guardrails-init dentro de ese proyecto.
```

## Reglas duras

- **Nunca** escribas los templates a mano en el proyecto objetivo. Siempre vía
  `bootstrap.py`.
- **Nunca** elimines archivos del proyecto objetivo. El bootstrap solo crea o
  fusiona.
- **Nunca** modifiques código productivo (`*.py`, `*.js`, `pyproject.toml`,
  `package.json`, etc.). Los secretos detectados solo se reportan.
- **Nunca** preguntes por confirmación. La solicitud del usuario es la
  confirmación. Los backups automáticos en `.guardrails-backup/` garantizan
  reversibilidad.
- La **única pregunta permitida** es cuando el `cwd` es el propio repo
  clonado de `claude-guardrails` y no queda claro cuál es el proyecto destino.

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
