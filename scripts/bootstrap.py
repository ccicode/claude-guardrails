#!/usr/bin/env python3
"""
guardrails bootstrap: merges the guardrails template into a target project
non-destructively.

Usage:
    python bootstrap.py --source <path> [--target <path>] [--dry-run | --apply]
                        [--yes] [--no-scan]

Reads template files from --source (a fresh clone of guardrails) and merges
them into --target (the user's project). Existing files are never overwritten
blindly: they are parsed, merged, and a timestamped backup is placed in
<target>/.guardrails-backup/<YYYYMMDD-HHMMSS>/ before any write.

Requires Python 3.10+ and only uses the standard library.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME = "guardrails"
BACKUP_DIR_NAME = ".guardrails-backup"
GITIGNORE_MARKER = "# --- agregado por guardrails ---"
CLAUDE_MD_MARKER = "## Reglas de guardrails"

# Map of target-relative path -> source-relative path. The plugin stores
# templates under templates/ and plugin-specific folders at the top level
# (skills/, agents/, hooks/), while the target project uses conventional
# paths (.gitignore, .claude/skills/, etc.).
TEMPLATE_PATHS: dict[str, str] = {
    ".gitignore":               "templates/gitignore",
    ".env.example":             "templates/env.example",
    ".pre-commit-config.yaml":  "templates/pre-commit-config.yaml",
    ".gitleaks.toml":           "templates/gitleaks.toml",
    ".claude/CLAUDE.md":        "templates/.claude/CLAUDE.md",
    ".claude/settings.json":    "templates/.claude/settings.json",
}

# Directories copied additively. (source_rel, target_rel, excluded_names).
# Excluded names are plugin-only artifacts that don't belong in user projects:
# - guardrails-init is the plugin bootstrap entry point (makes no sense at project level)
# - hooks.json is the plugin hook manifest (target projects use settings.json instead)
ADDITIVE_DIRS: list[tuple[str, str, set[str]]] = [
    ("skills", ".claude/skills", {"guardrails-init"}),
    ("agents", ".claude/agents", set()),
    ("hooks",  ".claude/hooks",  {"hooks.json"}),
]


def src_path_for(source: Path, rel_target: str) -> Path:
    """Resolve the source path given a target-relative path."""
    rel_src = TEMPLATE_PATHS.get(rel_target, rel_target)
    return source / rel_src

SCAN_EXCLUDE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "dist", "build",
    "__pycache__", BACKUP_DIR_NAME, ".mypy_cache", ".pytest_cache",
    ".next", ".nuxt", ".cache",
}

SECRET_PATTERNS_REL = "hooks/secret-patterns.json"


def load_secret_patterns(source: Path) -> list[dict]:
    """Load the canonical secret pattern list from hooks/secret-patterns.json.

    Returns a list of dicts with keys: name, regex (compiled), severity.
    Returns an empty list if the file is missing or invalid.
    """
    path = source / SECRET_PATTERNS_REL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[dict] = []
    for entry in data.get("patterns", []):
        try:
            out.append({
                "name": entry["name"],
                "regex": re.compile(entry["regex"]),
                "severity": entry.get("severity", "MEDIO").upper(),
            })
        except (KeyError, re.error):
            continue
    return out


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlanEntry:
    action: str            # "CREATE" | "MERGE" | "SKIP"
    rel_path: str          # relative to target
    detail: str = ""       # short human-readable detail
    writer: Callable[[], None] | None = None  # called in apply mode
    needs_backup: bool = False
    source_for_backup: Path | None = None     # target path to back up


@dataclass
class SecretHit:
    severity: str
    rel_path: str
    line_no: int
    kind: str
    masked: str


@dataclass
class BootstrapContext:
    source: Path
    target: Path
    apply: bool
    yes: bool
    no_scan: bool
    personal: bool = False
    plan: list[PlanEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)
    backup_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.backup_dir = self.target / BACKUP_DIR_NAME / stamp


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def use_color() -> bool:
    """Return True only if stdout is a real TTY and not Windows cmd."""
    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        # Honor TERM or WT_SESSION (Windows Terminal). Plain cmd has no TERM.
        if not os.environ.get("TERM") and not os.environ.get("WT_SESSION"):
            return False
    return True


def banner(title: str) -> str:
    return f"===== {title} ====="


def section(title: str) -> str:
    return f"----- {title} -----"


def log_info(ctx: BootstrapContext, msg: str) -> None:
    ctx.infos.append(msg)


def log_warn(ctx: BootstrapContext, msg: str) -> None:
    ctx.warnings.append(msg)


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def detect_project(target: Path) -> list[str]:
    lines = []
    py_markers = [p for p in ("pyproject.toml", "requirements.txt", "setup.py")
                  if (target / p).exists()]
    node_markers = [p for p in ("package.json",) if (target / p).exists()]
    frontend_markers = [p for p in ("index.html",) if (target / p).exists()]

    lines.append(f"Python:   {'detectado (' + ', '.join(py_markers) + ')' if py_markers else 'no detectado'}")
    lines.append(f"Node:     {'detectado (' + ', '.join(node_markers) + ')' if node_markers else 'no detectado'}")
    lines.append(f"Frontend: {'detectado (' + ', '.join(frontend_markers) + ')' if frontend_markers else 'no detectado'}")

    git_dir = target / ".git"
    if git_dir.exists():
        branch = detect_git_branch(target)
        lines.append(f"Git:      inicializado (branch: {branch})")
    else:
        lines.append("Git:      no inicializado")

    claude_dir = target / ".claude"
    lines.append(f".claude/: {'existe' if claude_dir.exists() else 'no existe'}")

    return lines


def detect_git_branch(target: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip() or "?"
    except (OSError, subprocess.SubprocessError):
        pass
    return "?"


# ---------------------------------------------------------------------------
# Generic file ops
# ---------------------------------------------------------------------------

def read_text_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def backup_file(ctx: BootstrapContext, rel_path: str) -> None:
    src = ctx.target / rel_path
    if not src.exists():
        return
    dst = ctx.backup_dir / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# ---------------------------------------------------------------------------
# .gitignore merge
# ---------------------------------------------------------------------------

def plan_gitignore(ctx: BootstrapContext) -> None:
    rel = ".gitignore"
    src = src_path_for(ctx.source, rel)
    tgt = ctx.target / rel
    if not src.exists():
        return

    src_text = read_text_safe(src) or ""
    if not tgt.exists():
        ctx.plan.append(PlanEntry(
            action="CREATE", rel_path=rel,
            writer=lambda: write_text(tgt, src_text),
        ))
        return

    tgt_text = read_text_safe(tgt) or ""
    existing = {ln.strip() for ln in tgt_text.splitlines() if ln.strip() and not ln.strip().startswith("#")}
    to_add: list[str] = []
    for raw in src_text.splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s not in existing and s not in to_add:
            to_add.append(s)

    if not to_add:
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="ya contiene todas las reglas de guardrails"))
        return

    def writer() -> None:
        backup_file(ctx, rel)
        sep = "" if tgt_text.endswith("\n") else "\n"
        block = [GITIGNORE_MARKER] + to_add
        new = tgt_text + sep + "\n".join(block) + "\n"
        write_text(tgt, new)

    ctx.plan.append(PlanEntry(
        action="MERGE", rel_path=rel,
        detail=f"+{len(to_add)} lineas",
        writer=writer, needs_backup=True, source_for_backup=tgt,
    ))


# ---------------------------------------------------------------------------
# .env.example merge
# ---------------------------------------------------------------------------

_ENV_KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


def _parse_env_blocks(text: str) -> list[tuple[str | None, list[str], str]]:
    """Return list of (key_or_None, comment_lines, assignment_line)."""
    blocks: list[tuple[str | None, list[str], str]] = []
    pending_comments: list[str] = []
    for raw in text.splitlines():
        s = raw.rstrip("\r")
        stripped = s.strip()
        if not stripped:
            if pending_comments:
                blocks.append((None, pending_comments, ""))
                pending_comments = []
            blocks.append((None, [], ""))
            continue
        if stripped.startswith("#"):
            pending_comments.append(s)
            continue
        m = _ENV_KEY_RE.match(s)
        if m:
            blocks.append((m.group(1), pending_comments, s))
            pending_comments = []
        else:
            blocks.append((None, pending_comments, s))
            pending_comments = []
    if pending_comments:
        blocks.append((None, pending_comments, ""))
    return blocks


def _collect_env_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for raw in text.splitlines():
        m = _ENV_KEY_RE.match(raw)
        if m:
            keys.add(m.group(1))
    return keys


def plan_env_example(ctx: BootstrapContext) -> None:
    rel = ".env.example"
    src = src_path_for(ctx.source, rel)
    tgt = ctx.target / rel
    if not src.exists():
        return

    src_text = read_text_safe(src) or ""
    if not tgt.exists():
        ctx.plan.append(PlanEntry(
            action="CREATE", rel_path=rel,
            writer=lambda: write_text(tgt, src_text),
        ))
        return

    tgt_text = read_text_safe(tgt) or ""
    existing_keys = _collect_env_keys(tgt_text)
    src_blocks = _parse_env_blocks(src_text)

    new_lines: list[str] = []
    added_keys: list[str] = []
    for key, comments, line in src_blocks:
        if key and key not in existing_keys:
            new_lines.extend(comments)
            new_lines.append(line)
            added_keys.append(key)

    if not added_keys:
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="todas las variables ya existen"))
        return

    def writer() -> None:
        backup_file(ctx, rel)
        sep = "" if tgt_text.endswith("\n") else "\n"
        header = f"\n# --- agregado por guardrails ({dt.date.today().isoformat()}) ---\n"
        new = tgt_text + sep + header + "\n".join(new_lines) + "\n"
        write_text(tgt, new)

    ctx.plan.append(PlanEntry(
        action="MERGE", rel_path=rel,
        detail=f"+{len(added_keys)} variables ({', '.join(added_keys[:3])}{'...' if len(added_keys) > 3 else ''})",
        writer=writer, needs_backup=True,
    ))


# ---------------------------------------------------------------------------
# .pre-commit-config.yaml merge (textual)
# ---------------------------------------------------------------------------

_REPO_LINE_RE = re.compile(r"^(\s*)-\s*repo:\s*(\S+)\s*$")


def _split_repo_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split into (preamble_before_first_repo, [(url, block_text), ...]).

    Each block_text starts at its "- repo:" line and ends right before the next
    repo line (or EOF).
    """
    lines = text.splitlines(keepends=True)
    first_idx = None
    repo_lines: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = _REPO_LINE_RE.match(line)
        if m:
            if first_idx is None:
                first_idx = i
            repo_lines.append((i, m.group(2)))
    if first_idx is None:
        return text, []
    preamble = "".join(lines[:first_idx])
    blocks: list[tuple[str, str]] = []
    for idx, (line_idx, url) in enumerate(repo_lines):
        end = repo_lines[idx + 1][0] if idx + 1 < len(repo_lines) else len(lines)
        blocks.append((url, "".join(lines[line_idx:end])))
    return preamble, blocks


def plan_precommit(ctx: BootstrapContext) -> None:
    rel = ".pre-commit-config.yaml"
    src = src_path_for(ctx.source, rel)
    tgt = ctx.target / rel
    if not src.exists():
        return

    src_text = read_text_safe(src) or ""
    if not tgt.exists():
        ctx.plan.append(PlanEntry(
            action="CREATE", rel_path=rel,
            writer=lambda: write_text(tgt, src_text),
        ))
        return

    tgt_text = read_text_safe(tgt) or ""
    if "repos:" not in tgt_text:
        log_warn(ctx, f"{rel}: no se reconoce estructura 'repos:', se respeta el archivo")
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="target invalido o sin 'repos:'"))
        return

    _, src_blocks = _split_repo_blocks(src_text)
    _, tgt_blocks = _split_repo_blocks(tgt_text)
    tgt_urls = {url for url, _ in tgt_blocks}

    to_add = [(url, block) for url, block in src_blocks if url not in tgt_urls]
    if not to_add:
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="todos los repos ya presentes"))
        return

    def writer() -> None:
        backup_file(ctx, rel)
        sep = "" if tgt_text.endswith("\n") else "\n"
        marker = f"\n  # --- agregado por guardrails ({dt.date.today().isoformat()}) ---\n"
        appended = marker + "".join(b for _, b in to_add)
        new = tgt_text + sep + appended
        if not new.endswith("\n"):
            new += "\n"
        write_text(tgt, new)

    ctx.plan.append(PlanEntry(
        action="MERGE", rel_path=rel,
        detail=f"+{len(to_add)} repos",
        writer=writer, needs_backup=True,
    ))


# ---------------------------------------------------------------------------
# .gitleaks.toml: copy only if missing
# ---------------------------------------------------------------------------

def plan_gitleaks(ctx: BootstrapContext) -> None:
    rel = ".gitleaks.toml"
    src = src_path_for(ctx.source, rel)
    tgt = ctx.target / rel
    if not src.exists():
        return
    if tgt.exists():
        log_info(ctx, "el proyecto ya tiene .gitleaks.toml, se respeta")
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="ya existe"))
        return
    src_text = read_text_safe(src) or ""
    ctx.plan.append(PlanEntry(
        action="CREATE", rel_path=rel,
        writer=lambda: write_text(tgt, src_text),
    ))


# ---------------------------------------------------------------------------
# .claude/CLAUDE.md merge
# ---------------------------------------------------------------------------

def plan_claude_md(ctx: BootstrapContext) -> None:
    rel = ".claude/CLAUDE.md"
    src = src_path_for(ctx.source, rel)
    tgt = ctx.target / rel
    if not src.exists():
        return

    src_text = read_text_safe(src) or ""
    if not tgt.exists():
        ctx.plan.append(PlanEntry(
            action="CREATE", rel_path=rel,
            writer=lambda: write_text(tgt, src_text),
        ))
        return

    tgt_text = read_text_safe(tgt) or ""
    if CLAUDE_MD_MARKER in tgt_text:
        log_info(ctx, ".claude/CLAUDE.md ya tiene las reglas de guardrails, no se duplica")
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="ya contiene reglas guardrails"))
        return

    def writer() -> None:
        backup_file(ctx, rel)
        sep = "" if tgt_text.endswith("\n") else "\n"
        today = dt.date.today().isoformat()
        appended = (
            f"{sep}\n---\n\n## Reglas de guardrails (agregado por bootstrap {today})\n\n"
            f"{src_text}"
        )
        new = tgt_text + appended
        if not new.endswith("\n"):
            new += "\n"
        write_text(tgt, new)

    ctx.plan.append(PlanEntry(
        action="MERGE", rel_path=rel,
        detail="append seccion guardrails",
        writer=writer, needs_backup=True,
    ))


# ---------------------------------------------------------------------------
# .claude/settings.json merge (deep JSON)
# ---------------------------------------------------------------------------

def _merge_unique_list(target_list: list, source_list: list) -> tuple[list, int]:
    """Union preserving target order first, returning (merged, added_count)."""
    out = list(target_list)
    added = 0
    for item in source_list:
        if item not in out:
            out.append(item)
            added += 1
    return out, added


def _merge_hook_events(
    tgt_events: dict, src_events: dict,
) -> tuple[dict, int]:
    """Merge hooks.<Event> lists by matcher, preserving target content.

    Returns (merged_dict, added_hooks_count).
    """
    added_total = 0
    out: dict = {k: list(v) for k, v in tgt_events.items()}
    for event_name, src_entries in src_events.items():
        if not isinstance(src_entries, list):
            continue
        tgt_entries = out.setdefault(event_name, [])
        tgt_by_matcher: dict[str, dict] = {}
        for e in tgt_entries:
            if isinstance(e, dict) and "matcher" in e:
                tgt_by_matcher[e["matcher"]] = e
        for src_entry in src_entries:
            if not isinstance(src_entry, dict):
                continue
            matcher = src_entry.get("matcher")
            if matcher is None:
                continue
            if matcher not in tgt_by_matcher:
                tgt_entries.append(json.loads(json.dumps(src_entry)))  # deep copy
                tgt_by_matcher[matcher] = tgt_entries[-1]
                added_total += len(src_entry.get("hooks", []))
                continue
            tgt_hooks = tgt_by_matcher[matcher].setdefault("hooks", [])
            tgt_cmds = {h.get("command") for h in tgt_hooks if isinstance(h, dict)}
            for h in src_entry.get("hooks", []):
                if isinstance(h, dict) and h.get("command") not in tgt_cmds:
                    tgt_hooks.append(json.loads(json.dumps(h)))
                    tgt_cmds.add(h.get("command"))
                    added_total += 1
    return out, added_total


def _merge_settings(tgt: dict, src: dict) -> tuple[dict, dict]:
    """Return (merged, stats). stats has counts for reporting."""
    merged = json.loads(json.dumps(tgt))  # deep copy
    stats = {"perms_added": 0, "hooks_added": 0, "other_added": 0}

    # permissions
    src_perm = src.get("permissions", {})
    if isinstance(src_perm, dict):
        merged_perm = merged.setdefault("permissions", {})
        for bucket in ("deny", "ask", "allow"):
            src_list = src_perm.get(bucket, [])
            if not isinstance(src_list, list):
                continue
            tgt_list = merged_perm.get(bucket, []) or []
            new_list, added = _merge_unique_list(tgt_list, src_list)
            merged_perm[bucket] = new_list
            stats["perms_added"] += added

    # hooks
    src_hooks = src.get("hooks", {})
    if isinstance(src_hooks, dict):
        tgt_hooks = merged.get("hooks", {}) or {}
        new_hooks, added = _merge_hook_events(tgt_hooks, src_hooks)
        merged["hooks"] = new_hooks
        stats["hooks_added"] = added

    # other keys: add only if missing
    for k, v in src.items():
        if k in ("permissions", "hooks"):
            continue
        if k not in merged:
            merged[k] = json.loads(json.dumps(v))
            stats["other_added"] += 1

    return merged, stats


def _rewrite_hook_commands_absolute(settings: dict, hooks_dir: Path) -> None:
    """Replace relative `.claude/hooks/` paths with the absolute hooks_dir.

    Used only in personal mode: the relative form resolves against the CWD of
    the project that Claude Code opens, not against `~/.claude/`, so commands
    must be absolute to find the hook scripts.
    """
    prefix = hooks_dir.as_posix().rstrip("/") + "/"
    events = settings.get("hooks")
    if not isinstance(events, dict):
        return
    for entries in events.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for h in entry.get("hooks") or []:
                if not isinstance(h, dict):
                    continue
                cmd = h.get("command", "")
                if ".claude/hooks/" in cmd:
                    h["command"] = cmd.replace(".claude/hooks/", prefix)


def plan_settings_json(ctx: BootstrapContext) -> None:
    rel = ".claude/settings.json"
    src = src_path_for(ctx.source, rel)
    tgt = ctx.target / rel
    if not src.exists():
        return

    src_text = read_text_safe(src) or ""
    try:
        src_data = json.loads(src_text)
    except json.JSONDecodeError as e:
        log_warn(ctx, f"source {rel} invalido ({e}); se omite")
        return

    if not tgt.exists():
        final_data = src_data
        if ctx.personal:
            final_data = json.loads(json.dumps(src_data))  # deep copy
            _rewrite_hook_commands_absolute(final_data, ctx.target / ".claude" / "hooks")
        ctx.plan.append(PlanEntry(
            action="CREATE", rel_path=rel,
            writer=lambda data=final_data: write_text(tgt, json.dumps(data, indent=2) + "\n"),
        ))
        return

    tgt_text = read_text_safe(tgt) or ""
    try:
        tgt_data = json.loads(tgt_text)
    except json.JSONDecodeError:
        log_warn(ctx, f"{rel}: JSON inválido (posibles comentarios o trailing commas); reparar manualmente")
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="JSON inválido, reparar manualmente"))
        return

    if not isinstance(tgt_data, dict) or not isinstance(src_data, dict):
        log_warn(ctx, f"{rel}: raiz no es objeto JSON, se omite")
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="raiz no es objeto"))
        return

    merged, stats = _merge_settings(tgt_data, src_data)

    if ctx.personal:
        hooks_dir = ctx.target / ".claude" / "hooks"
        _rewrite_hook_commands_absolute(merged, hooks_dir)

    if merged == tgt_data:
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="ya contiene todo"))
        return

    def writer() -> None:
        backup_file(ctx, rel)
        write_text(tgt, json.dumps(merged, indent=2) + "\n")

    detail = (
        f"{stats['perms_added']} permisos nuevos, "
        f"{stats['hooks_added']} hooks nuevos, "
        f"{stats['other_added']} keys nuevas"
    )
    ctx.plan.append(PlanEntry(
        action="MERGE", rel_path=rel,
        detail=detail,
        writer=writer, needs_backup=True,
    ))


# ---------------------------------------------------------------------------
# Additive copies: skills, agents, hooks
# ---------------------------------------------------------------------------

def _copy_tree_additive(
    ctx: BootstrapContext, src_rel: str, tgt_rel: str, exclude: set[str],
) -> None:
    src_dir = ctx.source / src_rel
    if not src_dir.is_dir():
        return
    tgt_dir = ctx.target / tgt_rel
    for entry in sorted(src_dir.iterdir()):
        if entry.name in exclude:
            continue
        _plan_additive_entry(ctx, tgt_rel, entry, tgt_dir)


def _plan_additive_entry(
    ctx: BootstrapContext, tgt_rel_dir: str, src_entry: Path, tgt_dir: Path,
) -> None:
    rel = f"{tgt_rel_dir}/{src_entry.name}"
    tgt_entry = tgt_dir / src_entry.name

    if src_entry.is_dir():
        if tgt_entry.exists():
            log_info(ctx, f"ya existe {rel}, se respeta")
            ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                      detail="ya existe"))
            return

        def writer(s=src_entry, d=tgt_entry) -> None:
            shutil.copytree(s, d)

        ctx.plan.append(PlanEntry(
            action="CREATE", rel_path=rel + "/",
            detail="carpeta completa", writer=writer,
        ))
        return

    if tgt_entry.exists():
        log_info(ctx, f"ya existe {rel}, se respeta")
        ctx.plan.append(PlanEntry(action="SKIP", rel_path=rel,
                                  detail="ya existe"))
        return

    def writer(s=src_entry, d=tgt_entry) -> None:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)

    ctx.plan.append(PlanEntry(
        action="CREATE", rel_path=rel, writer=writer,
    ))


def plan_additive_dirs(ctx: BootstrapContext) -> None:
    for src_rel, tgt_rel, exclude in ADDITIVE_DIRS:
        _copy_tree_additive(ctx, src_rel, tgt_rel, exclude)


# ---------------------------------------------------------------------------
# Secret scan
# ---------------------------------------------------------------------------

def _should_scan_dir(dir_name: str) -> bool:
    return dir_name not in SCAN_EXCLUDE_DIRS


def _iter_scan_files(target: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(target):
        # Prune excluded dirs in-place.
        dirs[:] = [d for d in dirs if _should_scan_dir(d)]
        for fname in files:
            yield Path(root) / fname


def _mask(value: str) -> str:
    if len(value) <= 8:
        return value[:2] + "***"
    return value[:8] + "****"


def scan_secrets(target: Path, patterns: list[dict]) -> list[SecretHit]:
    hits: list[SecretHit] = []
    if not patterns:
        return hits
    for path in _iter_scan_files(target):
        try:
            if path.stat().st_size > 2_000_000:  # skip >2MB files
                continue
        except OSError:
            continue
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as fh:
                for line_no, line in enumerate(fh, start=1):
                    if len(line) > 4000:
                        continue
                    for entry in patterns:
                        m = entry["regex"].search(line)
                        if not m:
                            continue
                        rel = path.relative_to(target).as_posix()
                        hits.append(SecretHit(
                            severity=entry["severity"],
                            rel_path=rel,
                            line_no=line_no,
                            kind=entry["name"],
                            masked=_mask(m.group(0)),
                        ))
                        break  # one hit per line is enough
        except OSError:
            continue
    return hits


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_plan(ctx: BootstrapContext, hits: list[SecretHit] | None) -> None:
    print(banner(f"{APP_NAME} bootstrap"))
    print(f"target: {ctx.target}")
    print(f"source: {ctx.source}")
    print(f"mode:   {'apply' if ctx.apply else 'dry-run'}")
    print(f"date:   {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print(section("Deteccion del proyecto"))
    for line in detect_project(ctx.target):
        print(line)
    print()

    print(section("Plan de cambios"))
    if not ctx.plan:
        print("(sin cambios)")
    else:
        for e in ctx.plan:
            detail = f"  ({e.detail})" if e.detail else ""
            print(f"{e.action:<9} {e.rel_path}{detail}")
    print()

    if hits is not None:
        print(section("Escaneo de secretos"))
        if not hits:
            print("no se encontraron secretos")
        else:
            for h in hits:
                print(f"{h.severity:<6} {h.rel_path}:{h.line_no} {h.kind}  {h.masked}")
        print()

    print(section("Resumen"))
    creates = sum(1 for e in ctx.plan if e.action == "CREATE")
    merges = sum(1 for e in ctx.plan if e.action == "MERGE")
    skips = sum(1 for e in ctx.plan if e.action == "SKIP")
    print(f"{creates} archivos a crear")
    backup_hint = f" (backup en {ctx.backup_dir.as_posix()}/)" if merges else ""
    print(f"{merges} archivos a modificar{backup_hint}")
    print(f"{skips} archivos omitidos")

    if hits:
        alto = sum(1 for h in hits if h.severity == "ALTO")
        medio = sum(1 for h in hits if h.severity == "MEDIO")
        print(f"{len(hits)} secretos detectados (ALTO: {alto}, MEDIO: {medio})")

    if ctx.warnings:
        print()
        print(section("Advertencias"))
        for w in ctx.warnings:
            print(f"WARNING: {w}")

    if ctx.infos:
        print()
        print(section("Notas"))
        for i in ctx.infos:
            print(f"INFO: {i}")

    print()
    if not ctx.apply:
        print("[dry-run] No se escribió nada. Ejecuta con --apply para aplicar.")

    if hits:
        print()
        print("Invoca `/check-secrets` en Claude Code para el refactor asistido.")


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_plan(ctx: BootstrapContext) -> None:
    for entry in ctx.plan:
        if entry.writer is None:
            continue
        try:
            entry.writer()
        except Exception as e:  # noqa: BLE001 - report and continue
            log_warn(ctx, f"fallo al escribir {entry.rel_path}: {e}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="bootstrap.py",
        description="Integra la plantilla guardrails dentro de un proyecto existente.",
    )
    p.add_argument("--source", required=True, type=Path,
                   help="Directorio donde está clonado claude-guardrails.")
    p.add_argument("--target", type=Path, default=None,
                   help="Directorio destino. Por defecto: cwd (modo normal) "
                        "o ~ (modo --personal).")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True,
                      help="Solo reporta, no escribe (default).")
    mode.add_argument("--apply", action="store_true",
                      help="Aplica los cambios.")
    p.add_argument("--yes", action="store_true",
                   help="Salta la confirmación interactiva.")
    p.add_argument("--no-scan", action="store_true",
                   help="Salta el escaneo de secretos.")
    p.add_argument("--personal", action="store_true",
                   help="Instalación personal: escribe en ~/.claude/ en vez del "
                        "proyecto. No toca .gitignore, .env.example ni "
                        ".pre-commit-config.yaml. Los hooks quedan con ruta "
                        "absoluta para funcionar desde cualquier proyecto.")
    return p.parse_args(argv)


def validate_paths(source: Path, target: Path) -> str | None:
    if not source.exists() or not source.is_dir():
        return f"source no existe o no es directorio: {source}"
    if not target.exists():
        return f"target no existe: {target}"
    if not target.is_dir():
        return f"target no es un directorio: {target}"
    if not os.access(target, os.W_OK):
        return f"sin permisos de escritura en target: {target}"
    return None


def confirm_apply() -> bool:
    try:
        answer = input("Aplicar? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"y", "yes", "s", "si", "sí"}


def build_plan(ctx: BootstrapContext) -> None:
    if not ctx.personal:
        # Archivos de proyecto: solo en modo normal. En modo personal no
        # tocamos el repositorio del usuario.
        plan_gitignore(ctx)
        plan_env_example(ctx)
        plan_precommit(ctx)
        plan_gitleaks(ctx)
    plan_claude_md(ctx)
    plan_settings_json(ctx)
    plan_additive_dirs(ctx)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    source = args.source.resolve()
    if args.target is not None:
        target = args.target.resolve()
    elif args.personal:
        target = Path.home().resolve()
    else:
        target = Path.cwd().resolve()

    err = validate_paths(source, target)
    if err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    ctx = BootstrapContext(
        source=source,
        target=target,
        apply=bool(args.apply),
        yes=bool(args.yes),
        no_scan=bool(args.no_scan),
        personal=bool(args.personal),
    )

    try:
        build_plan(ctx)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR fatal construyendo el plan: {e}", file=sys.stderr)
        return 1

    hits: list[SecretHit] | None = None
    if not ctx.no_scan and not ctx.personal:
        try:
            patterns = load_secret_patterns(source)
            if not patterns:
                log_warn(ctx, f"no se pudo cargar {SECRET_PATTERNS_REL}; se omite el escaneo")
                hits = []
            else:
                hits = scan_secrets(target, patterns)
        except Exception as e:  # noqa: BLE001
            log_warn(ctx, f"escaneo de secretos falló: {e}")
            hits = []

    print_plan(ctx, hits)

    if not ctx.apply:
        return 0

    if not ctx.yes:
        print()
        if not confirm_apply():
            print("Operación cancelada.")
            return 2

    apply_plan(ctx)
    print()
    print("Listo. Cambios aplicados.")
    if any(e.action == "MERGE" for e in ctx.plan):
        print(f"Backup de archivos modificados: {ctx.backup_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
