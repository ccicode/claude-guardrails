---
name: refactor-monolith
description: Refactoriza un archivo monolítico (HTML con CSS y JS inline, Python mayor a 300 líneas, etc.) en una estructura modular. Invocar cuando el usuario tenga un único archivo grande que desee organizar.
allowed-tools: Read, Write, Edit, Glob, Bash(git status), Bash(git add *), Bash(git stash *), Bash(wc *), Bash(ls *)
---

# refactor-monolith — De un archivo único a estructura modular

Toma un archivo extenso (HTML con todo inline, script Python de 800 líneas,
JS que acumula responsabilidades) y lo divide en archivos separados con
responsabilidades claras. Es una operación **con alto riesgo de regresión**;
por eso exige aprobación explícita antes de modificar el código.

## Principios

- **Proponer antes de actuar.** Mostrar el árbol destino y esperar confirmación
  literal antes de escribir.
- **Preservar comportamiento.** El refactor es estructural, no funcional. Si
  se detecta un bug durante el proceso, anotarlo en el reporte pero **no
  corregirlo** en esta ejecución.
- **Mantener las referencias.** Si se extrae CSS, el HTML debe enlazarlo. Si
  se extrae un módulo Python, los `import` deben cuadrar.
- **Snapshot de Git** antes de empezar, cuando exista repositorio.

## Pasos

### Paso 1 — Identificar el archivo candidato

Si el usuario no lo indica:

```bash
find . -type f \( -name "*.html" -o -name "*.py" -o -name "*.js" -o -name "*.ts" \) \
  -not -path "*/node_modules/*" -not -path "*/.venv/*" -not -path "*/.git/*" \
  -exec wc -l {} + | sort -rn | head -10
```

- Un único archivo con más de 500 líneas: proponerlo.
- Varios candidatos: listar los 3-5 más grandes y solicitar que elija.
- Ninguno > 500 líneas: preguntar directamente cuál refactorizar.

### Paso 2 — Analizar el archivo

Leerlo completo. Identificar **secciones lógicas** según el tipo:

**HTML monolítico:**
- `<style>` inline → `css/styles.css` (dividir si excede 500 líneas).
- `<script>` inline → separar por responsabilidad:
  - Llamadas HTTP / fetch → `js/api.js`.
  - Lógica de UI (eventos, DOM) → `js/app.js` o `js/ui.js`.
  - Configuración (endpoints, constantes) → `js/config.js`.
- Templates Handlebars / Mustache → `templates/`.
- Assets inline (SVG, base64) → evaluar si corresponde extraer.

**Python monolítico:**
- Clases por dominio → un archivo por dominio (`models.py`, `services.py`,
  `utils.py`).
- Funciones de entrada / CLI → `cli.py` o `main.py`.
- Constantes y configuración → `config.py` (que lee `os.environ`).
- Tests embebidos → `tests/test_*.py`.

**JS / TS monolítico:**
- Componentes → `src/components/`.
- Llamadas HTTP → `src/api/`.
- Estado / stores → `src/state/`.
- Utilidades puras → `src/utils/`.

### Paso 3 — Proponer el árbol destino (sin escribir)

Ejemplo:

```
Actual:
  index.html                   (1247 líneas, todo inline)

Propuesto:
  index.html                   (solo estructura HTML, ~120 líneas)
  css/styles.css               (~380 líneas extraídas de <style>)
  js/config.js                 (~25 líneas, lee window.__CONFIG__)
  js/api.js                    (~180 líneas, fetch / XHR)
  js/app.js                    (~440 líneas, lógica UI)
  assets/icons.svg             (SVGs agrupados)
```

Preguntar:

> **¿Procedo con esta estructura?**
>
> - `sí` — aplicar tal cual.
> - `modificar: ...` — ajustes (por ejemplo, "no separes api.js").
> - `no` — cancelar.

**No continuar sin respuesta afirmativa.**

### Paso 4 — Snapshot de seguridad

```bash
git status 2>&1 | head -1
```

- Repositorio con cambios sin commit: preguntar
  **"¿Hago commit de los cambios actuales antes de refactorizar?"**. Con
  respuesta afirmativa: `git add -A && git commit -m "snapshot before refactor-monolith"`.
- No es repositorio Git: advertir que no podrá revertirse con facilidad y
  ofrecer `git init` + commit inicial.

### Paso 5 — Ejecutar el refactor

Para cada archivo destino:

1. Leer la sección original del archivo monolito (rango de líneas exacto).
2. Crear el nuevo archivo con `Write`.
3. Verificar que el contenido extraído sea sintácticamente válido (indentación,
   llaves balanceadas).

Luego modificar el archivo original con `Edit`:

- **HTML:** reemplazar `<style>…</style>` por
  `<link rel="stylesheet" href="css/styles.css">`; reemplazar `<script>…</script>`
  por `<script src="js/app.js"></script>` respetando el orden de dependencias.
- **Python:** reemplazar el bloque extraído por `from .modulo import Cosa`.
- **JS / TS:** reemplazar por `import { ... } from './modulo.js'`.

### Paso 6 — Validar

Según el stack:

- **HTML:** revisar que no queden `<style>` / `<script>` inline huérfanos.
- **Python:** `python -c "import ast; ast.parse(open('archivo.py').read())"`.
- **JS / TS:** si hay `package.json` con script `build` o `lint`, ejecutarlo.
  En su defecto, al menos `node --check archivo.js`.

### Paso 7 — Ejecutar check-secrets

Invocar `/check-secrets` sobre el directorio refactorizado. Durante la
extracción es frecuente que queden constantes con API keys o URLs que deben
viajar por `.env`.

### Paso 8 — Reporte final

| Métrica | Antes | Después |
|---|---|---|
| Archivos | 1 | N |
| Líneas totales | 1247 | 1265 (+18 por imports) |
| Archivo más grande | 1247 | 440 (app.js) |

**Archivos creados:**
- `css/styles.css` — 380 líneas.
- `js/config.js` — 25 líneas.
- `js/api.js` — 180 líneas.
- `js/app.js` — 440 líneas.

**Observaciones detectadas (sin corregir en esta corrida):**
- Variable `userData` se define en `api.js` y se usa en `app.js` vía scope
  global. Debería pasar como parámetro.
- Se encontró un `console.log` con un token (reportado por `check-secrets`
  como CRÍTICO).

**Próximos pasos:**
1. Verificar el funcionamiento completo antes de seguir.
2. En caso de fallo, revertir con `git reset --hard HEAD~1`.
3. Considerar agregar tests antes del próximo refactor.
