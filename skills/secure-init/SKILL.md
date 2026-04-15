---
name: secure-init
description: Configura la seguridad inicial de un proyecto. Crea .env.example, valida .gitignore, instala pre-commit y verifica que el proyecto esté versionado. Invocar al empezar un proyecto nuevo o al heredar uno sin separación de secretos.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(python *), Bash(pip install *), Bash(pre-commit *), Bash(git init), Bash(git status), Bash(ls *), Bash(pwd), Bash(cp *)
---

# secure-init — Inicialización segura de proyectos

Prepara un proyecto (nuevo o existente) con los mínimos de seguridad
obligatorios. Cada paso destructivo o que instale software requiere
**confirmación explícita** del usuario antes de ejecutarse.

## Contexto

- **Plataforma objetivo:** Windows con `bash` (git-bash o WSL). Utilizar
  siempre rutas con barras normales y comandos POSIX.
- **Origen de las plantillas:** raíz del plugin `claude-guardrails`
  (detectable buscando hacia arriba un directorio con
  `.claude/skills/secure-init/`).
- **Regla:** nunca sobrescribir un archivo existente sin preguntar. Si el
  proyecto ya tiene `.gitignore`, agregar las líneas faltantes; no reemplazar.

## Pasos

Ejecutar **en orden** y presentar al final una tabla resumen.

### Paso 1 — Detectar el stack

Inspeccionar el directorio actual y clasificar:

| Señal | Stack |
|---|---|
| `package.json`, `*.js`, `*.ts`, `*.jsx`, `*.tsx` | Node / JS / TS |
| `requirements.txt`, `pyproject.toml`, `*.py` | Python |
| `*.html` con `<script>` inline | Frontend estático |
| `Gemfile` | Ruby |
| ninguna de las anteriores | "desconocido" — preguntar |

Reportar: "Se detectó que este proyecto es **X**. ¿Es correcto?".

### Paso 2 — Validar `.gitignore`

```bash
test -f .gitignore && echo "existe" || echo "falta"
```

- Si falta: copiar desde la raíz del plugin con `cp`. Si no se encuentra la
  raíz, crear uno mínimo inline (`.env`, `.env.*`, `!.env.example`, `*.key`,
  `*.pem`, `secrets/`, `node_modules/`, `__pycache__/`, `.venv/`, `dist/`,
  `build/`).
- Si existe: leerlo y verificar que contenga, como mínimo:
  ```
  .env
  .env.*
  !.env.example
  *.key
  *.pem
  secrets/
  ```
  Si falta alguna, **agregarla** al final (no reemplazar el archivo).

### Paso 3 — Crear `.env.example`

Si ya existe, no modificar. Si no existe, crear con placeholders adecuados al
stack:

- **Python:** `DATABASE_URL`, `SECRET_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`.
- **Node:** `DATABASE_URL`, `NODE_ENV`, `PORT`, `JWT_SECRET` y las keys
  correspondientes.
- **Frontend:** `VITE_API_BASE_URL` (o equivalente del framework).

Encabezar con:

```
# Copiar este archivo a .env y completar con valores reales.
# NUNCA incluir .env en el repositorio.
```

### Paso 4 — Validar `.pre-commit-config.yaml`

Si no existe, copiar desde la raíz del plugin. Si la plantilla tampoco está
disponible, omitir el paso y reportarlo (no inventar una configuración).

### Paso 5 — Verificar Git

```bash
git status 2>&1 | head -1
```

- Si responde "not a git repository": preguntar
  **"¿Inicializo Git aquí?"**. Con respuesta afirmativa: `git init && git branch -M main`.
- Si ya es un repositorio: continuar.

### Paso 6 — Instalar pre-commit (con confirmación)

Preguntar: **"Voy a instalar `pre-commit` con pip. ¿Procedo?"**.

Con respuesta afirmativa:

```bash
pip install pre-commit
pre-commit install
```

Si la respuesta es negativa, dejar constancia en el reporte y continuar.

### Paso 7 — Validación inicial

```bash
pre-commit run --all-files
```

Capturar la salida. Si falla, **no intentar corregirlo automáticamente**:
reportar qué hook falló y sobre qué archivo, y preguntar si se desea la
corrección asistida.

### Paso 8 — Reporte final

Presentar la tabla:

| Paso | Estado | Detalle |
|---|---|---|
| Stack detectado | ✓ | Python / Node / … |
| `.gitignore` | ✓ / ✗ | creado / actualizado / ya existía |
| `.env.example` | ✓ / ✗ | creado con N variables |
| `.pre-commit-config.yaml` | ✓ / ✗ | copiado / ya existía / plantilla no disponible |
| Git inicializado | ✓ / ✗ | |
| pre-commit instalado | ✓ / ✗ | |
| Validación inicial | ✓ / ✗ | N hooks OK, M con fallo |

## Checklist final para el usuario

- [ ] ¿Se copió `.env.example` a `.env` con credenciales reales?
- [ ] ¿`git status` confirma que `.env` NO aparece como archivo rastreado?
- [ ] ¿`git log --all --full-history -- .env` confirma que no se commiteó en
      el pasado?
- [ ] Si el repositorio será público, ¿se ejecutó `/check-secrets`?

Ante cualquier ítem sin marcar, ofrecer invocar `/check-secrets` de inmediato.
