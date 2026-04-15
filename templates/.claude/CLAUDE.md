# Instrucciones del proyecto para Claude Code

Este archivo define reglas **obligatorias** que Claude Code debe aplicar a todo
código que genere, edite o proponga dentro de este proyecto. El archivo fue
instalado por `claude-guardrails`; puede ampliarse con reglas específicas del
proyecto pero no deben eliminarse las secciones base.

## 1. Arquitectura modular obligatoria

Estructura mínima esperada:

```
proyecto/
├── src/ o app/               Código fuente.
├── tests/                    Pruebas automatizadas.
├── config/                   Configuración no sensible.
├── .env.example              Placeholders de variables.
├── README.md
└── requirements.txt | package.json | pyproject.toml
```

Reglas duras:

- **Ningún archivo puede superar 300 líneas.** Al acercarse al límite,
  dividirlo por responsabilidad.
- **Prohibido "todo en un único HTML".** HTML, CSS y JavaScript se mantienen
  en archivos separados (`index.html`, `styles/*.css`, `js/*.js` o su
  equivalente con bundler).
- **Prohibido código Python repartido en varios archivos sin
  `requirements.txt` o `pyproject.toml`.** Las dependencias deben declararse.
- **Prohibido frontend con dependencias sin `package.json`.**
- Ante una solicitud de monolito explícita (por ejemplo, "hazme todo en un
  solo archivo"), **no ejecutarla**. Primero explicar brevemente los riesgos
  (mantenibilidad, seguridad, ausencia de tests) y proponer la estructura
  modular mínima. Implementar únicamente tras confirmación.

## 2. Separación de secretos

Está **prohibido** hardcodear cualquiera de los siguientes valores en el
código fuente:

- API keys, tokens, contraseñas.
- Connection strings (MongoDB, PostgreSQL, Redis, etc.).
- URLs de producción, subdominios privados, IPs internas.
- Nombres de buckets S3 / GCS.
- Certificados o claves privadas.

Reglas:

- Leer secretos **siempre** desde el entorno: `os.environ["X"]` (Python),
  `process.env.X` (Node), `import.meta.env.VITE_X` (Vite).
- Si el proyecto aún no tiene `.env.example`, **crearlo antes** de escribir
  código que consuma configuración.
- En `.env.example` solo deben existir placeholders
  (`API_KEY=your-api-key-here`, `DB_URL=postgres://user:password@host:5432/db`);
  nunca valores reales.
- El `.env` real **nunca** lo genera Claude Code. Lo produce manualmente el
  usuario y debe figurar en `.gitignore`.

## 3. Manejo de Git

Antes de sugerir `git commit` o `git push`:

1. Verificar que `.gitignore` contenga `.env`, `.env.local`, `.env.*.local`.
2. Ejecutar `git diff --cached` y revisar que no existan strings sospechosos
   (keys largas, tokens, URLs con credenciales).

Reglas absolutas:

- **Nunca** usar `git commit --no-verify` ni `git push --no-verify`. Saltan
  los hooks de seguridad.
- Ante una solicitud explícita de `--no-verify`, preguntar el motivo y
  advertir del riesgo. No ejecutarlo sin justificación documentada.
- Nunca `git push --force` sobre `main` / `master` sin confirmación explícita.

## 4. Estilo de código y claridad

- Nombres de variables **descriptivos en inglés**: `user_email`,
  `connection_pool`; evitar `x1`, `var2`, identificadores mixtos español-inglés.
- Comentarios y mensajes de error pueden estar en español; los identificadores
  no.
- Docstrings y comentarios **solo cuando el _por qué_ no sea evidente**. No
  duplicar lo que ya expresa el código.
- Antes de considerar un proyecto "entregado" debe existir: `README.md` con
  pasos de instalación, `.env.example` y el archivo de dependencias
  correspondiente.

## 5. Antes de responder

- Ante una solicitud de panel, aplicación o feature nueva: **mostrar primero
  el árbol de archivos propuesto** y esperar confirmación antes de escribir
  código.
- Si al explorar se detecta código con secretos hardcodeados, ofrecer
  `/check-secrets` o proponer `/refactor-monolith` antes de continuar sobre
  código que viola las reglas.
- Ante una solicitud que contradice estas reglas, explicar brevemente el
  motivo del rechazo y proponer la alternativa segura.

## Skills disponibles

- `/guardrails-init` — aplica estos guardarraíles sobre el proyecto actual.
- `/secure-init` — inicializa la estructura segura de un proyecto nuevo.
- `/check-secrets` — audita el proyecto buscando secretos hardcodeados.
- `/refactor-monolith` — divide archivos monolíticos en módulos respetando la
  estructura obligatoria.
