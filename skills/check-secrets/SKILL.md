---
name: check-secrets
description: Audita y remedia secretos hardcodeados en el proyecto actual. Invocar cuando se sospeche de credenciales en el código, antes de publicar un repo, o al heredar código de otra persona.
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git *)
context: fork
---

# check-secrets — Auditoría y remediación de secretos

## Instrucción

Lanzar el agente `security-auditor` con el prompt:

> Audita y remedia el proyecto en `<cwd>`. Lee TODOS los archivos de código
> (excluyendo .git/, node_modules/, venv/, __pycache__/, .claude/,
> .guardrails-backup/). Para cada archivo, busca con tu inteligencia:
> passwords, API keys, tokens, connection strings, emails/hosts operativos,
> credenciales en constructores/funciones/dicts, fallbacks inseguros en
> os.environ.get(). Remedia cada secreto moviéndolo a variables de entorno.
> Crea .env con los valores REALES que estaban hardcodeados. La app debe
> funcionar igual después. Reporta al final.
