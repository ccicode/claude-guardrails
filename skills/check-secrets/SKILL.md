---
name: check-secrets
description: Audita el proyecto actual buscando secretos hardcodeados (API keys, tokens, passwords, connection strings, URLs de producción). Invocar cuando se sospecha que hay credenciales en el código, antes de publicar un repositorio o al heredar código de otra persona.
allowed-tools: Grep, Read, Bash(gitleaks *), Bash(ruff check *), Bash(python *), Bash(git diff *), Bash(git log *), Bash(git grep *)
---

# check-secrets — Auditoría de secretos hardcodeados

Identifica credenciales embebidas en el código: API keys, tokens, contraseñas,
connection strings, URLs internas. Cada hallazgo incluye **explicación breve**
y **acción concreta propuesta**.

## Principios

- Reportar falsos positivos con transparencia (por ejemplo, un ejemplo de
  README se marca como severidad BAJA).
- **Nunca** incluir el secreto completo en el reporte: mostrar los primeros
  4 caracteres y enmascarar el resto (`sk-Abcd****`).
- No modificar archivos en esta skill. Solo escanear y reportar. Los refactors
  se proponen y solo se aplican si el usuario lo solicita.

## Patrones

La fuente única de patrones vive en `.claude/hooks/secret-patterns.json` tras
la instalación (o en `hooks/secret-patterns.json` dentro del plugin). Usar
exactamente los mismos patrones para mantener coherencia con los hooks.

## Pasos

### Paso 1 — Barrido por expresiones regulares

Ejecutar `Grep` recursivo, excluyendo `node_modules/`, `.venv/`, `.git/`,
`dist/`, `build/`, `__pycache__/`. Aplicar los patrones definidos en
`secret-patterns.json`, agrupando los resultados por proveedor:

- **OpenAI / Anthropic** (`sk-[a-zA-Z0-9]{20,}`)
- **AWS Access Key** (`AKIA[0-9A-Z]{16}`)
- **GitHub PAT** (`ghp_...`)
- **Google API** (`AIza...`)
- **Slack** (`xox[baprs]-...`)
- **Private key PEM** (`-----BEGIN ... PRIVATE KEY-----`)
- **Connection strings**: MongoDB, PostgreSQL, MySQL, Redis.
- **Asignaciones genéricas**: `(api_key|secret|token|password)\s*[:=]\s*"..."`.

### Paso 2 — Herramientas externas (si están disponibles)

```bash
command -v gitleaks  >/dev/null && gitleaks detect --no-git --source . --report-format json --report-path /tmp/gitleaks.json
command -v ruff      >/dev/null && ruff check --select S105,S106,S107 .
command -v trufflehog >/dev/null && trufflehog filesystem . --no-verification
```

Si ninguna está disponible, mencionarlo al final como sugerencia (no es un
error).

### Paso 3 — Consolidar hallazgos

Tabla única ordenada por severidad:

| # | Severidad | Archivo:línea | Tipo | Valor (enmascarado) | Recomendación |
|---|---|---|---|---|---|
| 1 | CRÍTICO | `app.py:42` | OpenAI API key | `sk-Abcd****` | Rotar la key y moverla a `.env` como `OPENAI_API_KEY` |
| 2 | ALTO | `config.js:8` | Connection string | `postg****@prod-db...` | Mover a `.env`, rotar credencial |
| 3 | MEDIO | `docs/example.md:12` | Patrón genérico | `sk-exam****` | Verificación manual — probable ejemplo |

**Criterios de severidad:**

- **CRÍTICO:** coincidencia con proveedor conocido (OpenAI, AWS, GitHub) en
  código productivo.
- **ALTO:** connection string con credenciales embebidas, private keys,
  passwords genéricos en `.py` / `.js` / `.ts`.
- **MEDIO:** URL productiva, IP privada, patrón genérico en archivo de config.
- **BAJO:** coincidencia en `README.md`, `*.example`, `docs/` o tests con
  valores obviamente ficticios.

### Paso 4 — Proponer refactors

Para cada hallazgo CRÍTICO / ALTO, presentar un diff conceptual (sin aplicar):

**Python:**
```diff
- client = OpenAI(api_key="sk-Abcd1234...")
+ import os
+ client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
```

**Entrada correspondiente en `.env.example`:**
```
OPENAI_API_KEY=sk-...
```

**JavaScript:**
```diff
- const DB = "postgres://admin:s3cr3t@prod.db.com/app";
+ const DB = process.env.DATABASE_URL;
```

### Paso 5 — Preguntar y aplicar

Al final del reporte:

> **¿Aplico estos refactors automáticamente?**
>
> - Reemplazo los valores por lecturas de variables de entorno.
> - Actualizo `.env.example` con las nuevas variables.
> - **No** creo el `.env` con valores reales (es responsabilidad del usuario).
> - **No** roto las credenciales expuestas. Eso es urgente si el repositorio
>   es o fue público en algún momento; debe hacerse en el panel del proveedor.
>
> Respuestas aceptadas: `s` (aplicar todo), `n` (no aplicar), o una lista
> de números (`1,3,5`).

Si el usuario acepta, aplicar los cambios con `Edit` uno a uno. Al finalizar,
recordar expresamente: **"Las credenciales expuestas siguen siendo válidas
hasta que se roten en el panel del proveedor."**
