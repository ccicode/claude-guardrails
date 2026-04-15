<!--
  Este archivo contiene instrucciones para Claude Code, no para personas.
  Cuando un usuario solicite "aprovisionar este proyecto con claude-guardrails"
  apuntando a este URL, Claude debe seguir el procedimiento al pie de la letra.
-->

# Instrucciones para Claude Code — Aprovisionar con `claude-guardrails`

Si estás leyendo esto, el usuario solicitó aplicar `claude-guardrails`. Ejecuta
el instalador **sin improvisar** y sin escribir código a mano.

## Paso 0 — Elegir el modo

Preguntar al usuario una sola vez:

> **¿Modo de instalación?**
>
> - **Proyecto** (recomendado): los guardarraíles viven dentro del repositorio
>   actual (`.claude/`, `.gitignore`, `.pre-commit-config.yaml`, etc.). Se
>   commitean y se aplican también al resto del equipo.
> - **Personal**: los guardarraíles viven en tu `~/.claude/` y se aplican a
>   todos los proyectos que abras en tu máquina. No tocan el repositorio ni al
>   equipo.

Si el usuario elige **personal**, usar `--personal` en el comando del paso 4 y
omitir los pasos 5 (pre-commit) y la verificación de `git init`.

## Procedimiento

### 1. Obtener el repositorio

Clona el repositorio a una carpeta temporal:

```bash
git clone --depth=1 https://github.com/ccicode/claude-guardrails.git /tmp/claude-guardrails-src
```

Si ya está disponible localmente en otra ruta, usa esa ruta como `--source` en
lugar de clonar.

### 2. Identificar el proyecto objetivo

El objetivo es el `cwd` — el proyecto que el usuario tiene abierto. Confirma con
`pwd`. Si el `cwd` resulta ser la carpeta del propio plugin clonado, detente y
pregunta cuál es el proyecto real.

Si el objetivo no tiene directorio `.git/`, pregunta una sola vez:
**"El proyecto no está inicializado con Git. ¿Ejecuto `git init`?"**. Si la
respuesta es afirmativa, ejecútalo; si no, continúa (se omitirá la instalación
de `pre-commit`).

### 3. Dry-run

**Modo proyecto:**

```bash
python /tmp/claude-guardrails-src/scripts/bootstrap.py \
  --source /tmp/claude-guardrails-src \
  --target "$(pwd)"
```

**Modo personal:**

```bash
python /tmp/claude-guardrails-src/scripts/bootstrap.py \
  --source /tmp/claude-guardrails-src \
  --personal
```

Muestra al usuario el output completo y pregunta: **"¿Aplico estos cambios?"**.

### 4. Apply

Con aprobación explícita, agregar `--apply --yes` al comando anterior.

**Modo proyecto** respalda en `.guardrails-backup/<YYYYMMDD-HHMMSS>/` los
archivos que modifica.

**Modo personal** escribe en `~/.claude/` y deja los comandos de hook con
ruta absoluta (necesario para que funcionen desde cualquier proyecto).

### 5. Instalar pre-commit

Solo en **modo proyecto**. En modo personal omitir este paso.

```bash
python -m pip install --user pre-commit
pre-commit install
```

Si alguno de los dos pasos falla, emite un `WARN` no fatal; el usuario puede
reintentar después.

### 6. Limpieza

```bash
rm -rf /tmp/claude-guardrails-src
```

### 7. Reporte final

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
- **Nunca** ejecutes `--apply` sin mostrar primero el dry-run y recibir
  confirmación explícita.
- **Nunca** elimines archivos del proyecto objetivo. El bootstrap solo crea o
  fusiona.
- **Nunca** modifiques código productivo (`*.py`, `*.js`, `pyproject.toml`,
  `package.json`, etc.). Los secretos detectados solo se reportan.

## Errores comunes

| Síntoma | Causa probable | Acción |
|---|---|---|
| `python no encontrado` | Python no está en `PATH`. | Solicita instalar Python 3.10+ y reintentar. En Windows, probar `py -3`. |
| `git clone falló` | Credenciales o URL errada. | Verificar acceso a la red o la URL del repositorio. |
| `JSON inválido` en `bootstrap.py` | El proyecto ya tenía `.claude/settings.json` con JSON roto. | Abrirlo, reparar la sintaxis y reintentar. |
| Usuario quiere revertir | — | Copiar los archivos de `.guardrails-backup/<timestamp>/` sobre su ubicación original. Los archivos creados desde cero se eliminan manualmente. |
