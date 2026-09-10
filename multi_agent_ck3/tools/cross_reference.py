"""Cross-file / cross-mod reference validation.

The existing validators (`validation.py`, `gui_quality.py`) only look *inside* a
single file: brace balance, BOM, trait categories. Every expensive bug in
`bug_log/` has instead been a **reference that does not resolve against the rest
of the load order** — an interaction pointing at a category that does not exist,
an index that collides with another mod, a modifier name the engine never
registered.

This module checks a mod against vanilla plus the other mods actually installed,
which is the only place those bugs are visible.
"""

from __future__ import annotations

import pathlib
import re
from typing import Optional

# CK3 registers men-at-arms modifiers per archetype only. Per-unit-key variants
# such as `mage_regiment_max_size_add` parse as "Unexpected token".
MAA_ARCHETYPES = {
    "archers",
    "archer_cavalry",
    "camel_cavalry",
    "elephant_cavalry",
    "gunpowder",
    "heavy_cavalry",
    "heavy_infantry",
    "light_cavalry",
    "nomadic_horde",
    "peasant_militia",
    "pikemen",
    "siege_weapon",
    "skirmishers",
}
MAA_MODIFIER_SUFFIXES = (
    "_max_size_add",
    "_max_size_mult",
    "_maintenance_mult",
    "_recruitment_cost_mult",
    "_damage_add",
    "_damage_mult",
    "_toughness_add",
    "_toughness_mult",
    "_pursuit_add",
    "_pursuit_mult",
    "_screen_add",
    "_screen_mult",
    "_siege_value_add",
    "_siege_value_mult",
)

_CATEGORY_RE = re.compile(r"(\w+)\s*=\s*\{[^}]*?\bindex\s*=\s*(\d+)", re.S)


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def interaction_categories(root: pathlib.Path) -> dict[str, int]:
    """category key -> index, for one game or mod folder."""
    found: dict[str, int] = {}
    folder = root / "common" / "character_interaction_categories"
    if folder.is_dir():
        for path in folder.rglob("*.txt"):
            for key, index in _CATEGORY_RE.findall(_read(path)):
                found[key] = int(index)
    return found


def check_interaction_categories(
    mod_root: pathlib.Path, other_roots: list[pathlib.Path]
) -> list[str]:
    """Categories must be unique AND contiguous from 0, and every reference must resolve.

    Vanilla's 00_character_interaction_categories.txt: "DO NOT LEAVE GAPS IN
    index OR THE GAME WILL CRASH". A duplicate index crashes the same way.
    """
    issues: list[str] = []
    ours = interaction_categories(mod_root)
    theirs: dict[str, dict[str, int]] = {
        root.name: interaction_categories(root) for root in other_roots
    }

    taken: dict[int, str] = {}
    for source, cats in theirs.items():
        for key, index in cats.items():
            taken[index] = f"{key} ({source})"

    for key, index in sorted(ours.items(), key=lambda kv: kv[1]):
        if index in taken:
            issues.append(f"category '{key}' index {index} collides with {taken[index]}")

    all_indices = set(taken) | set(ours.values())
    if all_indices:
        gaps = sorted(set(range(max(all_indices) + 1)) - all_indices)
        if gaps:
            issues.append(
                f"category index gap(s) at {gaps}: indices must run "
                f"0..{max(all_indices)} with no holes or the game crashes"
            )

    defined = set(ours) | {k for cats in theirs.values() for k in cats}
    folder = mod_root / "common" / "character_interactions"
    if folder.is_dir():
        for path in folder.rglob("*.txt"):
            for category in sorted(set(re.findall(r"^\s*category\s*=\s*(\w+)", _read(path), re.M))):
                if category not in defined:
                    issues.append(f"{path.name}: category '{category}' is not defined anywhere")
    return issues


def check_maa_modifiers(mod_root: pathlib.Path) -> list[str]:
    """Flag men-at-arms modifiers written against a unit key instead of an archetype."""
    issues: list[str] = []
    unit_keys: set[str] = set()
    maa_folder = mod_root / "common" / "men_at_arms_types"
    if maa_folder.is_dir():
        for path in maa_folder.rglob("*.txt"):
            unit_keys.update(re.findall(r"^(\w+)\s*=\s*\{", _read(path), re.M))
    if not unit_keys:
        return issues

    pattern = re.compile(
        r"\b(\w+)(" + "|".join(re.escape(s) for s in MAA_MODIFIER_SUFFIXES) + r")\s*="
    )
    for path in (mod_root / "common").rglob("*.txt"):
        for stem, suffix in pattern.findall(_read(path)):
            if stem in unit_keys and stem not in MAA_ARCHETYPES:
                issues.append(
                    f"{path.name}: '{stem}{suffix}' targets a unit key; CK3 only registers "
                    f"these per archetype ({', '.join(sorted(MAA_ARCHETYPES))})"
                )
    return sorted(set(issues))


def check_referenced_traits(mod_root: pathlib.Path, other_roots: list[pathlib.Path]) -> list[str]:
    """Every `has_trait = X` / `add_trait = X` must resolve to a defined trait."""
    defined: set[str] = set()
    for root in [mod_root, *other_roots]:
        folder = root / "common" / "traits"
        if folder.is_dir():
            for path in folder.rglob("*.txt"):
                defined.update(re.findall(r"^(\w+)\s*=\s*\{", _read(path), re.M))
    if not defined:
        return []

    issues: list[str] = []
    for path in (mod_root / "common").rglob("*.txt"):
        text = _read(path)
        for trait in set(re.findall(r"\b(?:has_trait|add_trait|remove_trait)\s*=\s*(\w+)", text)):
            if trait not in defined:
                issues.append(f"{path.name}: trait '{trait}' is not defined anywhere")
    return sorted(set(issues))


def audit(
    mod_root: pathlib.Path, game_dir: pathlib.Path, other_mod_roots: list[pathlib.Path]
) -> dict[str, list[str]]:
    others = [game_dir, *other_mod_roots]
    return {
        "interaction_categories": check_interaction_categories(mod_root, others),
        "maa_modifiers": check_maa_modifiers(mod_root),
        "traits": check_referenced_traits(mod_root, others),
    }


def register(mcp, repo_root: pathlib.Path, game_dir: pathlib.Path):
    @mcp.tool()
    def validate_mod_references(
        mod_name: str,
        other_mods: Optional[list] = None,
    ) -> str:
        """Check a mod's cross-file and cross-mod references for crash-causing errors.

        Unlike validate_script (which only inspects one file in isolation), this
        resolves references against vanilla CK3 and any other mods you name, which
        is where load-order bugs actually live. Run it before every playtest.

        Checks:
          - character interaction category indices are unique AND contiguous from 0
            (a duplicate or a gap hard-crashes the interaction menu)
          - every `category =` used by an interaction resolves to a real definition
          - men-at-arms modifiers target an archetype, not a unit key
            (per-unit variants throw "Unexpected token")
          - every has_trait/add_trait/remove_trait target is defined somewhere

        Args:
            mod_name: Mod folder name inside the repo root (e.g. 'ElderMagic').
            other_mods: Optional list of absolute paths to other mod folders that
                will be loaded alongside it (e.g. an AGOT workshop folder).
        Returns:
            A grouped report of issues, or 'No reference issues found.'
        """
        mod_root = repo_root / mod_name
        if not mod_root.is_dir():
            return f"Mod folder not found: {mod_root}"

        other_roots = [pathlib.Path(p) for p in (other_mods or [])]
        missing = [str(p) for p in other_roots if not p.is_dir()]
        results = audit(mod_root, game_dir, [p for p in other_roots if p.is_dir()])

        lines = []
        for group, issues in results.items():
            if issues:
                lines.append(f"[{group}]")
                lines.extend(f"  - {i}" for i in issues)
        if missing:
            lines.append("[warnings]")
            lines.extend(f"  - other mod folder not found, skipped: {p}" for p in missing)

        return "\n".join(lines) if lines else "No reference issues found."


class _ToolCollector:
    """Mimics FastMCP so register() populates tools without a real server."""

    def __init__(self):
        self._fns: list = []

    def tool(self, **_):
        def _wrap(fn):
            self._fns.append(fn)
            return fn

        return _wrap


def get_tools(repo_root: pathlib.Path, game_dir: pathlib.Path) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool

    collector = _ToolCollector()
    register(collector, repo_root, game_dir)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
