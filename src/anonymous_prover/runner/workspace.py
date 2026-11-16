"""Workspace management -- prepare isolated directories for each task."""

from __future__ import annotations

import logging
import os
import shutil
import threading
from pathlib import Path

from ..core.enums import AgentType, SkillsConfig

logger = logging.getLogger(__name__)

# ---- Native lake layout (non-Docker) --------------------------------------
#
# Parallel tasks can't share one ``.lake/`` on CPFS — every ``lake build``
# would contend on the same manifest / build-file locks and drag verify
# times into the 120s timeout. Per-task writable state lives on /tmp
# (ephemeral, fast SSD) while ``packages/`` (mathlib oleans) are symlinked
# from CPFS read-only — olean reads are mmap with no lock, so sharing them
# is safe across tasks.
_NATIVE_LAKE_ROOT = "/tmp/anonymous-prover-lake"  # per-workspace writable dirs


def _provision_native_lake(ws: str, workspace_id: str, project_lake: str) -> None:
    """Install a per-task ``.lake/`` that isolates lake's writes.

    Layout::

        /tmp/anonymous-prover-lake/<workspace_id>/
            packages → <project>/.lake/packages  (symlink, read-only share)
            build/                                (per-task, writable)

    and ``<ws>/.lake`` becomes a symlink into that /tmp tree. Everything
    lake writes — manifest, trace, build artefacts — stays on /tmp; only
    the mmap-friendly olean cache is shared, which doesn't take locks.
    """
    task_lake = os.path.join(_NATIVE_LAKE_ROOT, workspace_id)
    if os.path.exists(task_lake):
        shutil.rmtree(task_lake, ignore_errors=True)
    os.makedirs(task_lake)

    pkg_src = os.path.join(project_lake, "packages")
    if os.path.isdir(pkg_src):
        os.symlink(pkg_src, os.path.join(task_lake, "packages"))

    # Seed build/ from the project cache if present; else start empty.
    src_build = os.path.join(project_lake, "build")
    dst_build = os.path.join(task_lake, "build")
    if os.path.isdir(src_build):
        shutil.copytree(src_build, dst_build, symlinks=False)
    else:
        os.makedirs(dst_build)

    os.symlink(task_lake, os.path.join(ws, ".lake"))


def _cleanup_native_lake(workspace_id: str) -> None:
    """Remove the per-task /tmp writable tree."""
    task_lake = os.path.join(_NATIVE_LAKE_ROOT, workspace_id)
    if os.path.isdir(task_lake):
        shutil.rmtree(task_lake, ignore_errors=True)

# Maps SkillsConfig values to template directory names under workspaces/
WORKSPACE_TEMPLATES: dict[str, str] = {
    SkillsConfig.none: "baseline",
    SkillsConfig.standard: "standard",
    SkillsConfig.extended: "extended",
    SkillsConfig.co_derivation: "co-derivation",
    SkillsConfig.docs_only: "docs",
    SkillsConfig.tools_only: "tools",
}

# Maps SkillsConfig to the source skill directory name under
# ``agents/`` in the project root. This is the SINGLE SOURCE OF TRUTH
# for which skill body each config uses. The sources live outside
# ``.claude/`` on purpose: ``.claude/`` is reserved for the host
# developer's own Claude Code session state, while ``agents/`` is the
# versioned, deployable skill corpus that workspace.py copies into
# each per-task workspace.
SKILL_DIR_NAMES: dict[str, str] = {
    SkillsConfig.standard: "standard",
    SkillsConfig.extended: "extended",
    SkillsConfig.co_derivation: "co-derivation",
    SkillsConfig.docs_only: "standard",
    SkillsConfig.tools_only: "standard",
}

# Unified destination directory name installed into each workspace.
# Every variant (standard/extended/co-derivation) lands under
# ``.claude/skills/lean4-codeprover/`` so Claude Code loads a single,
# namespaced project skill. The per-mode slash commands it exposes
# (``/auto``, ``/proof``, ``/code``) are declared inside SKILL.md in the
# plugin-style ``/lean4-codeprover:<mode>`` table; the Python harness
# invokes them by the short form ``/auto <target>`` — see prompts.py.
INSTALLED_SKILL_NAME = "lean4-codeprover"


class WorkspaceManager:
    """Create and tear down per-task workspace directories."""

    def __init__(
        self,
        project_root: str,
        skills_config: str,
        *,
        docker_enabled: bool = False,
        agent_type: str = AgentType.claude_code,
        backend: str | None = None,
        model: str | None = None,
    ) -> None:
        self.project_root = project_root
        self.skills_config = skills_config
        self.docker_enabled = docker_enabled
        self.agent_type = str(agent_type)
        # Only "miromind" currently alters codex config.toml.
        self.backend = backend
        self.model = model
        self._template_name = WORKSPACE_TEMPLATES.get(skills_config, "standard")
        self._template_dir = os.path.join(
            project_root, "workspaces", self._template_name
        )
        self._skill_dir_name = SKILL_DIR_NAMES.get(skills_config)

    def create_workspace(self, task_file: str, tasks_mode: str = "file") -> tuple[str, str]:
        """Set up an isolated workspace for *task_file* and return its path.

        The workspace is placed under ``workspaces/active/{pid}_{tid}_{task}/``
        so that parallel runs do not collide.
        """
        task_name = os.path.splitext(os.path.basename(task_file))[0]
        unique = f"{os.getpid()}_{threading.get_ident()}_{task_name}"
        ws = os.path.join(self.project_root, "workspaces", "active", unique)
        os.makedirs(ws, exist_ok=True)

        # Optionally copy a workspace template (settings.local.json etc.).
        # Templates are now rarely present — per-agent instructions are
        # regenerated below from agents/<variant>/ — so a missing
        # template dir is expected and logged at debug level only.
        _is_codex = self.agent_type == AgentType.codex
        if os.path.isdir(self._template_dir):
            shutil.copytree(self._template_dir, ws, dirs_exist_ok=True)
            logger.debug("Copied template %s -> %s", self._template_dir, ws)
        else:
            logger.debug("No template dir at %s (expected)", self._template_dir)

        # No agent-specific instruction file exists in templates anymore
        # — the template dirs only carry things like settings.local.json.
        # Per-agent instructions are regenerated fresh from the canonical
        # skill source below: Claude Code gets a project skill under
        # ``.claude/skills/lean4-codeprover/``; Codex gets the same skill
        # body under ``.agents/skills/lean4-codeprover/`` plus a thin
        # workspace-root ``AGENTS.md`` pointer.

        # Install skills from canonical source (agents/<variant>/).
        # This is the single source of truth — no pre-copied skills in
        # templates. Codex gets .agents/skills/ inside the workspace,
        # Claude Code gets .claude/skills/ inside the workspace; both
        # destinations share the unified INSTALLED_SKILL_NAME.
        if self._skill_dir_name:
            skill_src = os.path.join(
                self.project_root, "agents", self._skill_dir_name
            )
            if os.path.isdir(skill_src):
                if _is_codex:
                    agents_dst = os.path.join(ws, ".agents", "skills", INSTALLED_SKILL_NAME)
                    os.makedirs(os.path.dirname(agents_dst), exist_ok=True)
                    shutil.copytree(skill_src, agents_dst, dirs_exist_ok=True,
                                    copy_function=_copy_resolve_symlinks)
                    # Drop a thin workspace-root AGENTS.md that points
                    # Codex at the full skill body. Codex auto-loads
                    # AGENTS.md from cwd, so this is all it needs to
                    # discover the protocol.
                    with open(os.path.join(ws, "AGENTS.md"), "w",
                              encoding="utf-8") as fh:
                        fh.write(_codex_agents_md_pointer(INSTALLED_SKILL_NAME))
                else:
                    claude_dst = os.path.join(ws, ".claude", "skills", INSTALLED_SKILL_NAME)
                    os.makedirs(os.path.dirname(claude_dst), exist_ok=True)
                    shutil.copytree(skill_src, claude_dst, dirs_exist_ok=True,
                                    copy_function=_copy_resolve_symlinks)
                logger.debug(
                    "Installed skill variant %s into workspace as %s",
                    self._skill_dir_name, INSTALLED_SKILL_NAME,
                )
            else:
                logger.warning("Skill source dir not found: %s", skill_src)

        # Copy task sources into workspace.
        # - flat: copy only current task as <name>_Generated.lean
        # - project: copy all sibling files from the task's parent directory
        #   so directory-targeted prompting sees the full subproject context.
        _IGNORE_DIRS = {".lake", ".git", "__pycache__", "build", "lake-packages"}
        if tasks_mode == "project":
            parent = Path(task_file).parent
            for p in parent.rglob("*"):
                if p.is_dir():
                    continue
                if any(part in _IGNORE_DIRS for part in p.relative_to(parent).parts):
                    continue
                rel = p.relative_to(parent)
                dest = Path(ws) / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
            work_file = os.path.join(ws, os.path.basename(task_file))
        else:
            work_file_name = f"{task_name}_Generated.lean"
            work_file = os.path.join(ws, work_file_name)
            shutil.copy2(task_file, work_file)

        # --- Lean project files & shared directories ---
        # Both Docker and local modes get lightweight project files so the
        # workspace is self-contained.  The only difference is .lake:
        #   - Local: symlinked (large, read-only)
        #   - Docker: omitted here; mounted from host at container start

        # In project mode the task ships its own lakefile.toml with the
        # correct module registrations (e.g. [[lean_lib]] name="Hashbrown").
        # We keep it as-is and only append the Tacs lean_lib so the shared
        # helper library resolves.  lean-toolchain and lake-manifest.json
        # are always taken from the project root.
        has_task_lakefile = (
            tasks_mode == "project"
            and os.path.exists(os.path.join(ws, "lakefile.toml"))
        )

        if has_task_lakefile:
            # Keep the task's own lakefile.toml.  Merge root's deps
            # into both the lakefile ([[require]]/[[lean_lib]]) and
            # the manifest (packages).  Same for lean-toolchain: keep
            # the task's if present, otherwise copy the root's.
            ws_toolchain = os.path.join(ws, "lean-toolchain")
            if not os.path.exists(ws_toolchain):
                root_toolchain = os.path.join(self.project_root, "lean-toolchain")
                if os.path.exists(root_toolchain):
                    shutil.copy2(root_toolchain, ws_toolchain)
            _merge_lake_manifest(
                os.path.join(ws, "lake-manifest.json"),
                os.path.join(self.project_root, "lake-manifest.json"),
            )
            # Merge [[require]] and [[lean_lib]] from the project-root
            # lakefile.  Task lakefiles typically declare lean_lib entries
            # but omit [[require]] (mathlib, quickcheck, etc.), so we
            # must pull those in from the root.
            root_lakefile = os.path.join(self.project_root, "lakefile.toml")
            if os.path.exists(root_lakefile):
                ws_lakefile = os.path.join(ws, "lakefile.toml")
                _merge_toml_sections(
                    ws_lakefile,
                    _extract_toml_sections(root_lakefile, "[[require]]"),
                    name_key="name",
                )
                _merge_toml_sections(
                    ws_lakefile,
                    _extract_toml_sections(root_lakefile, "[[lean_lib]]"),
                    name_key="name",
                )
        else:
            for item in ("lakefile.toml", "lean-toolchain", "lake-manifest.json"):
                src = os.path.join(self.project_root, item)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(ws, item))

        # Remove task-provided lakefile.lean if we use lakefile.toml,
        # otherwise Lake prefers .lean and ignores our .toml.
        if os.path.exists(os.path.join(ws, "lakefile.toml")):
            stale_lean = os.path.join(ws, "lakefile.lean")
            if os.path.exists(stale_lean):
                os.remove(stale_lean)

        # .lake handling:
        #   - Local: per-task /tmp-backed layout — mathlib packages shared
        #     read-only across tasks via _NATIVE_LAKE_CACHE, writable build/
        #     isolated per workspace so parallel ``lake build`` calls don't
        #     contend on CPFS locks. See _provision_native_lake.
        #   - Docker: .lake is mounted :ro by base.py, but lake build needs
        #     to write to .lake/build/. Copy build/ (~10 MB) into the
        #     workspace so base.py can overlay it as a rw sub-mount.
        lake_src = os.path.abspath(os.path.join(self.project_root, ".lake"))
        if not self.docker_enabled:
            if os.path.isdir(lake_src) and not os.path.exists(os.path.join(ws, ".lake")):
                _provision_native_lake(ws, unique, lake_src)
        else:
            lake_build_src = os.path.join(lake_src, "build")
            if os.path.isdir(lake_build_src):
                lake_build_dst = os.path.join(ws, ".lake-build")
                shutil.copytree(lake_build_src, lake_build_dst)

        # Tacs is copied (small) so we can selectively prune .lean files
        # for non-extended skills configs without affecting the source.
        # - extended: copy everything as-is.
        # - any other config: keep the Tacs/ folder skeleton but strip
        #   every .lean file inside it, and replace the root Tacs.lean
        #   entrypoint with a stub that only imports Mathlib (so the
        #   `Tacs` lean_lib in lakefile.toml still resolves cleanly).
        tacs_src = os.path.join(self.project_root, "Tacs")
        tacs_dst = os.path.join(ws, "Tacs")
        if os.path.isdir(tacs_src) and not os.path.exists(tacs_dst):
            shutil.copytree(tacs_src, tacs_dst)
        tacs_lean_src = os.path.join(self.project_root, "Tacs.lean")
        tacs_lean_dst = os.path.join(ws, "Tacs.lean")
        if self.skills_config == SkillsConfig.extended:
            if os.path.isfile(tacs_lean_src):
                shutil.copy2(tacs_lean_src, tacs_lean_dst)
        else:
            if os.path.isdir(tacs_dst):
                for p in Path(tacs_dst).rglob("*.lean"):
                    p.unlink()
            with open(tacs_lean_dst, "w", encoding="utf-8") as fh:
                fh.write("import Mathlib\n")

        # Copy .mcp.json for Claude MCP server configuration (lean-lsp etc.)
        mcp_src = os.path.join(self.project_root, ".mcp.json")
        if os.path.exists(mcp_src):
            mcp_dst = os.path.join(ws, ".mcp.json")
            if self.docker_enabled:
                # Rewrite paths for Docker container (workspace mounted at /task)
                import json
                with open(mcp_src) as f:
                    mcp_data = json.load(f)
                lean_server = mcp_data.get("mcpServers", {}).get("lean-lsp")
                if isinstance(lean_server, dict):
                    env = lean_server.setdefault("env", {})
                    env["LEAN_PROJECT_PATH"] = "/task"
                with open(mcp_dst, "w") as f:
                    json.dump(mcp_data, f, indent=2)
            else:
                shutil.copy2(mcp_src, mcp_dst)

        # Codex reads MCP config from config.toml (not .mcp.json), and the
        # file is mounted as *global* config in Docker because
        # project-scoped config requires explicit trust.
        if _is_codex:
            mcp_written = os.path.join(ws, ".mcp.json")
            want_miromind = self.backend == "miromind"
            if os.path.exists(mcp_written) or want_miromind:
                import json
                mcp_for_codex: dict = {}
                if os.path.exists(mcp_written):
                    with open(mcp_written) as f:
                        mcp_for_codex = json.load(f)
                codex_cfg_dir = os.path.join(ws, ".codex")
                os.makedirs(codex_cfg_dir, exist_ok=True)
                with open(os.path.join(codex_cfg_dir, "config.toml"), "w") as f:
                    f.write(_generate_codex_mcp_toml(
                        mcp_for_codex,
                        provider="miromind" if want_miromind else None,
                        model=self.model,
                    ))

        # Ensure all shell scripts are executable
        for sh in Path(ws).rglob("*.sh"):
            sh.chmod(sh.stat().st_mode | 0o755)

        # Initialise a git repo so agents that run `git log` / `git diff`
        # inside the workspace (or Docker /task) don't hit "not a git repository".
        import subprocess
        subprocess.run(
            ["git", "init", "-q", "-b", "main"],
            cwd=ws, capture_output=True,
        )
        subprocess.run(
            ["git", "add", "-A"],
            cwd=ws, capture_output=True,
        )
        subprocess.run(
            ["git", "-c", "user.name=solver", "-c", "user.email=solver@local",
             "commit", "-q", "-m", "initial", "--allow-empty"],
            cwd=ws, capture_output=True,
        )

        logger.info("Created workspace: %s", ws)
        return ws, work_file

    @staticmethod
    def cleanup(workspace_path: str) -> None:
        """Remove *workspace_path* and its per-task /tmp lake tree (if any).

        ``workspace_path`` looks like
        ``workspaces/active/<pid>_<tid>_<task>/``; the trailing segment is
        also the ``workspace_id`` we hand to :func:`_provision_native_lake`.
        """
        if os.path.isdir(workspace_path):
            workspace_id = os.path.basename(os.path.normpath(workspace_path))
            _cleanup_native_lake(workspace_id)
            shutil.rmtree(workspace_path, ignore_errors=True)
            logger.debug("Cleaned up workspace: %s", workspace_path)


def _copy_resolve_symlinks(src: str, dst: str) -> str:
    """Copy function that resolves symlinks before copying."""
    real_src = os.path.realpath(src)
    return shutil.copy2(real_src, dst)


def _codex_agents_md_pointer(skill_name: str) -> str:
    """Return a thin workspace-root ``AGENTS.md`` that points Codex at
    the installed skill body under ``.agents/skills/<skill_name>/``.

    Codex auto-loads ``AGENTS.md`` from the workspace cwd, so keeping the
    body inline in one canonical location (the skill SKILL.md) keeps the
    source of truth in one file while still letting Codex discover it.
    """
    skill_body = f".agents/skills/{skill_name}/SKILL.md"
    return (
        "# Task Instructions\n\n"
        f"Read `{skill_body}` for the full Lean 4 code-generation and "
        "verification workflow — it documents the core principles, sorry "
        "classification, the `code`/`proof`/`auto` modes, the tactic "
        "cascade, the quality gate, and all references.\n\n"
        "The harness will hand you a single instruction of the form\n"
        "`Run in \\`<mode>\\` mode on \\`<target_path>\\`.`\n"
        "where `<mode>` is one of `code`, `proof`, `auto` and "
        "`<target_path>` is a `.lean` file (or a directory in project "
        f"mode). Follow the matching section of `{skill_body}` on the "
        "target.\n\n"
        f"Reference material and helper scripts live under "
        f"`.agents/skills/{skill_name}/references/` and "
        f"`.agents/skills/{skill_name}/scripts/` respectively.\n"
    )


def _toml_value(v):
    """Format a Python value as a TOML literal."""
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(i) for i in v) + "]"
    return f'"{v}"'


# Known API gateways that speak the OpenAI Responses API. Keyed by the
# ``provider`` value set on ``AgentConfig``.
_CODEX_PROVIDERS: dict[str, dict[str, str]] = {
    "miromind": {
        "name": "MiroMind",
        "base_url": "https://api.miromind.site/v1",
        "wire_api": "responses",
        "env_key": "OPENAI_API_KEY",
    },
}


def _generate_codex_mcp_toml(
    mcp_data: dict,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """Convert ``.mcp.json`` data to Codex ``config.toml`` format.

    Translates the Claude-style ``mcpServers`` JSON into the
    ``[mcp_servers.<name>]`` TOML tables that Codex expects. When
    *provider* matches a known gateway, prepends ``model_provider`` and
    a ``[model_providers.<name>]`` block so Codex routes to that gateway
    instead of the official OpenAI endpoint.
    """
    lines: list[str] = []

    gateway = _CODEX_PROVIDERS.get((provider or "").lower()) if provider else None
    if gateway is not None:
        key = (provider or "").lower()
        if model:
            lines.append(f"model = {_toml_value(model)}")
        lines.append(f"model_provider = {_toml_value(key)}")
        lines.append("")
        lines.append(f"[model_providers.{key}]")
        for k in ("name", "base_url", "wire_api", "env_key"):
            if k in gateway:
                lines.append(f"{k} = {_toml_value(gateway[k])}")
        lines.append("")

    servers = mcp_data.get("mcpServers", {})
    for name, cfg in servers.items():
        lines.append(f"[mcp_servers.{name}]")
        for key in ("command", "args", "url"):
            if key in cfg:
                lines.append(f"{key} = {_toml_value(cfg[key])}")
        # Lean LSP tools (lean_verify, lean_build) can block for minutes
        # waiting for the Lean compiler; default Codex MCP tool timeout is
        # too short and causes "user cancelled MCP tool call" errors.
        timeout = cfg.get("tool_timeout_sec", 300)
        lines.append(f"tool_timeout_sec = {int(timeout)}")
        lines.append("")

        env = cfg.get("env", {})
        if env:
            lines.append(f"[mcp_servers.{name}.env]")
            for k, v in env.items():
                lines.append(f"{k} = {_toml_value(v)}")
            lines.append("")
    return "\n".join(lines) + "\n"


def _extract_toml_sections(lakefile_path: str, header: str) -> list[str]:
    """Return raw TOML sections matching *header* from *lakefile_path*.

    *header* is the exact table header line, e.g. ``[[lean_lib]]`` or
    ``[[require]]``.  Each returned element is the full text of one
    section (header included) and can be appended verbatim to another
    lakefile.
    """
    try:
        with open(lakefile_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError:
        return []

    import re
    # Split on any TOML table header ([[...]] or [...]).  Keep only
    # the sections whose header matches the requested one.
    blocks: list[str] = []
    parts = re.split(r"(?=^\[)", content, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if part.startswith(header):
            blocks.append(part)
    return blocks


def _merge_toml_sections(
    lakefile_path: str,
    extra_blocks: list[str],
    *,
    name_key: str = "name",
) -> None:
    """Append *extra_blocks* to *lakefile_path*, skipping duplicates.

    A block is considered duplicate if its *name_key* value already
    appears in the file.  For ``[[lean_lib]]`` blocks, entries whose
    ``srcDir`` points outside the workspace (contains ``..``) are
    also skipped.
    """
    import re

    try:
        with open(lakefile_path, "r", encoding="utf-8") as fh:
            existing = fh.read()
    except OSError:
        return

    # Collect values of name_key already present.
    existing_names: set[str] = set()
    for m in re.finditer(
        rf'{name_key}\s*=\s*"([^"]+)"',
        existing,
    ):
        existing_names.add(m.group(1))

    to_add: list[str] = []
    for block in extra_blocks:
        # Skip lean_libs whose srcDir points outside the workspace.
        src_match = re.search(r'srcDir\s*=\s*"([^"]+)"', block)
        if src_match and ".." in src_match.group(1):
            continue
        m = re.search(rf'{name_key}\s*=\s*"([^"]+)"', block)
        if m and m.group(1) not in existing_names:
            to_add.append(block)

    if not to_add:
        return

    with open(lakefile_path, "a", encoding="utf-8") as fh:
        fh.write("\n")
        for block in to_add:
            fh.write(f"\n{block}\n")
    logger.debug(
        "Merged %d TOML section(s) into %s", len(to_add), lakefile_path
    )


def _merge_lake_manifest(task_manifest: str, root_manifest: str) -> None:
    """Merge packages from *root_manifest* into *task_manifest*.

    Keeps the task manifest as the base and adds any packages from the
    root that are not already present (by name).  If the task manifest
    does not exist, the root manifest is copied as-is.
    """
    import json

    if not os.path.exists(root_manifest):
        return

    with open(root_manifest, "r", encoding="utf-8") as fh:
        root_data = json.load(fh)

    if not os.path.exists(task_manifest):
        with open(task_manifest, "w", encoding="utf-8") as fh:
            json.dump(root_data, fh, indent=1)
        return

    with open(task_manifest, "r", encoding="utf-8") as fh:
        task_data = json.load(fh)

    existing_names = {
        p.get("name") for p in task_data.get("packages", [])
    }

    added = 0
    for pkg in root_data.get("packages", []):
        if pkg.get("name") not in existing_names:
            task_data.setdefault("packages", []).append(pkg)
            added += 1

    if added:
        with open(task_manifest, "w", encoding="utf-8") as fh:
            json.dump(task_data, fh, indent=1)
        logger.debug(
            "Merged %d package(s) from root into %s", added, task_manifest
        )
