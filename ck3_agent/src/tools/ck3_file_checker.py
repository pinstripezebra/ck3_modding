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


def register(mcp, ck3_game_dir: pathlib.Path):
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
