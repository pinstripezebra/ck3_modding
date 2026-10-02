import pathlib
from typing import Optional

# Maps user-friendly type names (and common aliases) to paths relative to the
# CK3 game "game/" directory.  Keys are lowercased at lookup time.
FILE_TYPE_MAP: dict[str, str] = {
    # --- common/ ---
    "decisions":              "common/decisions",
    "decision":               "common/decisions",
    "traits":                 "common/traits",
    "trait":                  "common/traits",
    "character_interactions": "common/character_interactions",
    "interactions":           "common/character_interactions",
    "interaction":            "common/character_interactions",
    "scripted_effects":       "common/scripted_effects",
    "scripted_effect":        "common/scripted_effects",
    "scripted_triggers":      "common/scripted_triggers",
    "scripted_trigger":       "common/scripted_triggers",
    "on_actions":             "common/on_actions",
    "on_action":              "common/on_actions",
    "lifestyle_perks":        "common/lifestyle_perks",
    "perks":                  "common/lifestyle_perks",
    "perk":                   "common/lifestyle_perks",
    "buildings":              "common/buildings",
    "building":               "common/buildings",
    "modifiers":              "common/modifiers",
    "modifier":               "common/modifiers",
    "cultures":               "common/culture/cultures",
    "culture":                "common/culture/cultures",
    "religions":              "common/religion/religions",
    "religion":               "common/religion/religions",
    "schemes":                "common/schemes/scheme_types",
    "scheme":                 "common/schemes/scheme_types",
    "artifacts":              "common/artifacts/templates",
    "artifact":               "common/artifacts/templates",
    "script_values":          "common/script_values",
    "script_value":           "common/script_values",
    "scripted_guis":          "common/scripted_guis",
    "scripted_gui":           "common/scripted_guis",
    "character_interaction_categories": "common/character_interaction_categories",
    "lifestyles":             "common/lifestyles",
    "lifestyle":              "common/lifestyles",
    "holdings":               "common/holdings",
    "holding":                "common/holdings",
    # --- events/ ---
    "events":                 "events",
    "event":                  "events",
    # --- gui/ ---
    "gui":                    "gui",
    # --- localization/ ---
    "localization":           "localization/english",
    "loc":                    "localization/english",
}

# Extensions to scan per directory type
_TXT_EXTS  = {".txt"}
_GUI_EXTS  = {".gui"}
_LOC_EXTS  = {".yml", ".yaml"}
_DEFAULT_EXTS = _TXT_EXTS

_EXT_MAP: dict[str, set[str]] = {
    "gui":                    _GUI_EXTS,
    "localization/english":   _LOC_EXTS,
    "localization":           _LOC_EXTS,
}

_SAMPLE_FILES   = 2    # how many files to return when no specific file requested
_MAX_LINES_EACH = 150  # line cap per file in sample mode
_MAX_LINES_FULL = 300  # line cap when a specific file is requested


def _extensions_for(rel_path: str) -> set[str]:
    for key, exts in _EXT_MAP.items():
        if rel_path.endswith(key):
            return exts
    return _DEFAULT_EXTS


def _read_capped(path: pathlib.Path, max_lines: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as exc:
        return f"[Error reading file: {exc}]"
    truncated = len(lines) > max_lines
    out = "\n".join(lines[:max_lines])
    if truncated:
        out += f"\n\n[... truncated — file has {len(lines)} lines total ...]"
    return out


def register(mcp, ck3_game_dir: pathlib.Path, repo_root: Optional[pathlib.Path] = None):
    @mcp.tool()
    def check_ck3_file(
        file_type: str,
        file_name: Optional[str] = None,
        max_lines: Optional[int] = None,
    ) -> str:
        """Read vanilla CK3 game files so you can copy their exact format.

        Call this BEFORE creating any new mod file of a type that exists in
        vanilla (decisions, events, traits, interactions, schemes, perks, etc.).
        It returns real on-disk examples so generated content matches the actual
        CK3 format rather than an approximation from memory.

        Args:
            file_type: Content category to inspect.  Accepted values (case-
                insensitive): decisions, events, traits, character_interactions,
                interactions, scripted_effects, scripted_triggers, on_actions,
                lifestyle_perks, perks, buildings, modifiers, cultures,
                religions, schemes, artifacts, script_values, scripted_guis,
                lifestyles, holdings, gui, localization.
            file_name: Optional specific file name (e.g. "00_decisions.txt").
                When omitted the tool returns a sample of the first
                1-2 files alphabetically from the folder.
            max_lines: Override the per-file line cap (default 150 for samples,
                300 for a named file).

        Returns:
            Formatted file content with clear section headers, or an error
            message if the type is unrecognised or the game folder is missing.
        """
        key = file_type.strip().lower()
        rel = FILE_TYPE_MAP.get(key)
        if rel is None:
            known = ", ".join(sorted({k for k in FILE_TYPE_MAP if not k.endswith("s") or k + "s" not in FILE_TYPE_MAP}))
            return (
                f"Unknown file_type '{file_type}'. "
                f"Known types include: {', '.join(sorted(set(FILE_TYPE_MAP.keys())))}."
            )

        folder = ck3_game_dir / rel
        if not folder.exists():
            return f"Game folder not found: {folder}\nVerify the CK3 install path."

        extensions = _extensions_for(rel)

        if file_name:
            target = folder / file_name
            # An absolute file_name makes pathlib's `/` discard `folder` entirely,
            # so guard against paths outside ck3_game_dir before reading anything.
            try:
                target.resolve().relative_to(ck3_game_dir.resolve())
            except ValueError:
                return (
                    f"'{file_name}' is not a vanilla CK3 game file (outside {ck3_game_dir}). "
                    "check_ck3_file only reads vanilla files for format reference — "
                    "pass a bare file name (e.g. '00_traits.txt'), not an absolute path "
                    "to a mod file."
                )
            if not target.exists():
                # Try a recursive search one level deep (some types have sub-folders)
                matches = list(folder.rglob(file_name))
                if matches:
                    target = matches[0]
                else:
                    available = [
                        f.name for f in sorted(folder.rglob("*"))
                        if f.suffix in extensions
                    ][:20]
                    return (
                        f"File '{file_name}' not found in {folder}.\n"
                        f"Available files (first 20): {available}"
                    )
            cap = max_lines or _MAX_LINES_FULL
            content = _read_capped(target, cap)
            return f"=== {target.relative_to(ck3_game_dir)} ===\n\n{content}"

        # Collect candidate files (top-level first, then recurse)
        candidates = sorted(
            f for f in folder.iterdir()
            if f.is_file() and f.suffix in extensions
        )
        if not candidates:
            # Fall back to recursive if top-level has sub-folders only
            candidates = sorted(
                f for f in folder.rglob("*")
                if f.is_file() and f.suffix in extensions
            )

        if not candidates:
            return f"No {extensions} files found in {folder}."

        cap = max_lines or _MAX_LINES_EACH
        parts: list[str] = []
        for f in candidates[:_SAMPLE_FILES]:
            header = f"=== {f.relative_to(ck3_game_dir)} ==="
            parts.append(f"{header}\n\n{_read_capped(f, cap)}")

        total = len(candidates)
        footer = (
            f"\n\n[Showing {min(_SAMPLE_FILES, total)} of {total} files in "
            f"{folder.relative_to(ck3_game_dir)}.  "
            f"Pass file_name=<name> to read a specific file.]"
        )
        return "\n\n---\n\n".join(parts) + footer

    if repo_root is not None:
        @mcp.tool()
        def read_mod_file(
            mod_name: str,
            relative_path: str,
            max_lines: Optional[int] = None,
        ) -> str:
            """Read a file from one of this repo's OWN mod folders (e.g. ElderMagic),
            as opposed to check_ck3_file which only reads vanilla game files.

            Args:
                mod_name: Mod folder name under the repo root (e.g. 'ElderMagic').
                relative_path: Path to the file relative to the mod folder
                    (e.g. 'common/traits/ascendant_lore_traits.txt').
                max_lines: Override the line cap (default 300).
            Returns:
                File contents, or an error message if the mod/file isn't found
                or relative_path escapes the mod folder.
            """
            mod_dir = repo_root / mod_name
            if not mod_dir.is_dir():
                return f"Mod folder not found: {mod_dir}"

            target = (mod_dir / relative_path).resolve()
            try:
                target.relative_to(mod_dir.resolve())
            except ValueError:
                return f"'{relative_path}' escapes the mod folder '{mod_dir}'."

            if not target.is_file():
                return f"File not found: {target}"

            cap = max_lines or _MAX_LINES_FULL
            content = _read_capped(target, cap)
            return f"=== {mod_name}/{relative_path} ===\n\n{content}"

        @mcp.tool()
        def edit_mod_file(
            mod_name: str,
            relative_path: str,
            old_text: str,
            new_text: str,
        ) -> str:
            """Make an exact find-and-replace edit to an EXISTING file in one of our
            OWN mods — use this to modify existing content (e.g. add a field to an
            existing trait block). The create_* tools only generate brand-new
            content and cannot edit a file that already exists.

            old_text must match the file's current content EXACTLY ONCE, including
            whitespace/indentation — call read_mod_file first to get the exact
            current text. Prefer a SHORT, uniquely-identifying anchor line (e.g. a
            filename/icon reference, or one distinctive field) over a multi-line
            snippet: multi-line old_text is much more likely to mismatch on
            indentation/newlines and waste repeated failed attempts. If applying
            the same change across several near-identical blocks (e.g. one field
            added to N trait definitions), make one call per block using that
            block's own unique anchor (its icon/filename line is usually perfect).

            Args:
                mod_name: Mod folder name under the repo root (e.g. 'ElderMagic').
                relative_path: Path to the file relative to the mod folder.
                old_text: Exact text to replace. Must appear exactly once.
                new_text: Text to replace it with.
            Returns:
                A confirmation of the edit, or an error message if the mod/file
                isn't found, relative_path escapes the mod folder, or old_text
                doesn't match exactly once.
            """
            mod_dir = repo_root / mod_name
            if not mod_dir.is_dir():
                return f"Mod folder not found: {mod_dir}"

            target = (mod_dir / relative_path).resolve()
            try:
                target.relative_to(mod_dir.resolve())
            except ValueError:
                return f"'{relative_path}' escapes the mod folder '{mod_dir}'."

            if not target.is_file():
                return f"File not found: {target}"

            raw = target.read_bytes()
            has_bom = raw[:3] == b"\xef\xbb\xbf"
            text = (raw[3:] if has_bom else raw).decode("utf-8", errors="replace")

            # Idempotency guard: if every occurrence of old_text is already part of
            # an inserted new_text (the common case: new_text = old_text + appended
            # content), this edit was already applied -- skip the redundant write
            # instead of re-inserting a duplicate. Mask out existing new_text
            # instances first so a leftover old_text INSIDE new_text (e.g. as its
            # own prefix) isn't mistaken for a genuine still-unedited occurrence.
            count_new = text.count(new_text)
            if count_new > 0:
                remaining = text.replace(new_text, "", count_new)
                if old_text not in remaining:
                    return (
                        f"No-op: new_text already present in {mod_name}/{relative_path} "
                        "(this edit looks like it was already applied). Nothing changed."
                    )

            count = text.count(old_text)
            if count == 0:
                return (
                    f"old_text not found in {mod_name}/{relative_path}. Call read_mod_file "
                    "again to get the exact current content -- do not guess whitespace/line "
                    "endings. Prefer a SHORT, uniquely-identifying line as old_text (e.g. a "
                    "filename/icon reference, or a single distinctive field) over a multi-line "
                    "snippet, which is far more likely to mismatch on indentation/newlines."
                )
            if count > 1:
                return (
                    f"old_text matches {count} locations in {mod_name}/{relative_path} — "
                    "it's too generic. Include more surrounding context, or better, switch to "
                    "a short line that's unique to just this one block (e.g. that block's own "
                    "icon/filename reference) so it matches exactly once."
                )

            new_file_text = text.replace(old_text, new_text, 1)
            encoded = new_file_text.encode("utf-8")
            target.write_bytes((b"\xef\xbb\xbf" + encoded) if has_bom else encoded)

            return (
                f"Edited {mod_name}/{relative_path}: replaced 1 occurrence "
                f"({len(old_text)} chars -> {len(new_text)} chars)."
            )

# -- LangChain tool factory -------------------------------------------------

class _ToolCollector:
    """Mimics FastMCP so register() populates tools without a real server."""
    def __init__(self):
        self._fns: list = []
    def tool(self, **_):
        def _wrap(fn):
            self._fns.append(fn)
            return fn
        return _wrap


def get_tools(ck3_game_dir, repo_root=None) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, ck3_game_dir, repo_root=repo_root)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
