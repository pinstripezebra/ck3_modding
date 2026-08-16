import pathlib
import re
import shutil
from typing import Optional


_TRAIT_ID_RE = re.compile(r"^[a-z0-9_]+$")
_ICON_BASE_RE = re.compile(r"^[A-Za-z0-9_]+$")
_TRAILING_LEVEL_RE = re.compile(r"^(?P<base>[a-z0-9_]+)_(?P<level>[1-5])$")

_LEVEL_WORD = {
    1: "novice",
    2: "adept",
    3: "skilled",
    4: "expert",
    5: "master",
}


def _modifier_cost_weight(value: object) -> float:
    """Approximate ruler designer impact for a single modifier value."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        magnitude = abs(float(value))
        if magnitude <= 0.25:
            return magnitude * 6.0
        if magnitude <= 1.0:
            return magnitude * 10.0
        return 10.0 + (magnitude - 1.0) * 3.0
    return 0.0


def _estimate_ruler_designer_cost(
    category: str, modifiers: dict, progression: list[dict]
) -> int:
    """Estimate a nonzero ruler_designer_cost from strongest modifier tier."""
    snapshots = [modifiers or {}]
    snapshots.extend(step.get("modifiers", {}) for step in progression)

    max_by_key: dict[str, float] = {}
    for snap in snapshots:
        for key, value in (snap or {}).items():
            try:
                val = float(value)
            except (TypeError, ValueError):
                continue
            if key not in max_by_key or abs(val) > abs(max_by_key[key]):
                max_by_key[key] = val

    score = sum(_modifier_cost_weight(v) for v in max_by_key.values())
    base = 5
    if category == "education":
        base = 8
    elif category == "lifestyle":
        base = 10
    elif category == "genetic":
        base = 14

    estimated = int(round(base + score * 1.75))
    return max(5, min(120, estimated))


def _normalize_icon_base(icon_name: str) -> str:
    base = icon_name.strip()
    if base.lower().endswith(".dds"):
        base = base[:-4]
    if not _ICON_BASE_RE.fullmatch(base):
        raise ValueError(
            f"icon_name must be a simple file token (letters, numbers, underscore), got: {icon_name!r}"
        )
    return base


def _humanize_token(token: str) -> str:
    return token.replace("_", " ").strip()


def _escape_loc_text(text: str) -> str:
    return text.replace('"', "\\\"")


def _auto_description(trait_id: str, display_name: str) -> str:
    match = _TRAILING_LEVEL_RE.fullmatch(trait_id)
    title = display_name.strip() or _humanize_token(trait_id).title()

    if match:
        base = _humanize_token(match.group("base"))
        level = int(match.group("level"))
        level_word = _LEVEL_WORD[level]
        return (
            f"{title} marks {level_word} proficiency in {base}. "
            "This character applies that discipline with confidence in daily life."
        )

    domain = _humanize_token(trait_id)
    return (
        f"{title} reflects notable talent in {domain}. "
        "This character regularly turns that aptitude into practical advantage."
    )


def _render_modifiers(modifiers: dict, indent: str = "\t") -> list[str]:
    lines: list[str] = []
    for key, val in modifiers.items():
        lines.append(f"{indent}{key} = {val}")
    return lines


def _coerce_progression(progression: Optional[list]) -> list[dict]:
    if not progression:
        return []

    normalized: list[dict] = []
    for i, entry in enumerate(progression, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"progression_levels[{i}] must be an object")
        if "xp" not in entry:
            raise ValueError(f"progression_levels[{i}] missing required key 'xp'")

        xp = int(entry["xp"])
        if xp <= 0 or xp > 100:
            raise ValueError(f"progression_levels[{i}].xp must be 1..100, got {xp}")

        mods = entry.get("modifiers", {})
        if mods is None:
            mods = {}
        if not isinstance(mods, dict):
            raise ValueError(f"progression_levels[{i}].modifiers must be an object")

        name = entry.get("name")
        if name is not None and not isinstance(name, str):
            raise ValueError(f"progression_levels[{i}].name must be a string")

        normalized.append({"xp": xp, "modifiers": mods, "name": name})

    normalized.sort(key=lambda x: x["xp"])
    return normalized


def register(mcp, output_dir: pathlib.Path):
    @mcp.tool()
    def create_trait(
        trait_id: str,
        display_name: str,
        description: Optional[str] = None,
        category: str = "personality",
        modifiers: Optional[dict] = None,
        opposites: Optional[list] = None,
        icon_name: Optional[str] = None,
        progression_levels: Optional[list] = None,
        dynamic_level_names: bool = False,
        ruler_designer_cost: Optional[int] = None,
        genetic: bool = False,
        group: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create CK3 trait definition and localization files.
        Args:
            trait_id: Internal snake_case identifier (e.g. 'herculean_strength').
            display_name: Player-facing name shown in game (e.g. 'Herculean').
            description: Trait tooltip description shown in game.
                         If omitted or blank, a short description is generated.
            category: personality, physical, health, genetic, education,
                      lifestyle, commander, fame, court, or childhood.
            modifiers: Dict of modifier keys to values e.g. {"prowess": 4, "health": 1.0}.
            opposites: List of trait IDs this trait opposes e.g. ["weak"].
            icon_name: DDS icon filename without extension (defaults to trait_id).
            progression_levels: Optional XP progression config for lifestyle traits.
                                Example:
                                [
                                    {"xp": 25, "name": "Elementalist Initiate", "modifiers": {"learning": 1}},
                                    {"xp": 50, "name": "Elementalist Adept", "modifiers": {"learning": 2}},
                                    {"xp": 75, "name": "Elementalist Expert", "modifiers": {"learning": 3}},
                                    {"xp": 100, "name": "Elementalist Master", "modifiers": {"learning": 4}}
                                ]
                                If category is lifestyle and this is omitted, default
                                thresholds 25/50/75/100 are generated using base modifiers.
            dynamic_level_names: If True, lifestyle progression names change by
                                XP tier (e.g., Novice/Adept/Master). Defaults to
                                False so trait labels stay fixed (e.g., "Necromancer").
            ruler_designer_cost: Optional explicit ruler designer cost. If omitted,
                                a nonzero cost is estimated from trait strength.
            genetic: If True, adds 'genetic = yes' to the trait definition. Children
                     can inherit the trait; active parents pass at 100%, inactive at 50%.
                     Both parents passing the trait makes it active in the child.
                     Pair with group for the tier-reinforce mechanic.
            group: Optional group name (e.g. 'wizard_potential'). Traits in the same
                   group reinforce each other at birth — if both parents carry traits
                   from this group, the child may inherit a higher-ranked trait.
                   Only meaningful when genetic=True.
            mod_name: Mod folder name. Defaults to 'mod'.
        Returns:
            Paths to the generated trait and localization files.
        """
        modifiers = modifiers or {}
        opposites = opposites or []
        if not _TRAIT_ID_RE.fullmatch(trait_id):
            raise ValueError(
                f"trait_id must be snake_case using lowercase letters, numbers, and underscores, got: {trait_id!r}"
            )

        if not display_name or not display_name.strip():
            raise ValueError("display_name cannot be empty")

        icon_base = _normalize_icon_base(icon_name or trait_id)
        icon_token = f"{icon_base}.dds"
        progression = _coerce_progression(progression_levels)
        final_description = (
            description.strip()
            if isinstance(description, str) and description.strip()
            else _auto_description(trait_id, display_name)
        )

        if category == "lifestyle" and not progression:
            # Default lifestyle progression so trait XP has gameplay effect.
            progression = [
                {"xp": 25, "modifiers": dict(modifiers), "name": f"{display_name} Initiate"},
                {"xp": 50, "modifiers": dict(modifiers), "name": f"{display_name} Adept"},
                {"xp": 75, "modifiers": dict(modifiers), "name": f"{display_name} Expert"},
                {"xp": 100, "modifiers": dict(modifiers), "name": f"{display_name} Master"},
            ]

        final_cost = (
            int(ruler_designer_cost)
            if ruler_designer_cost is not None
            else _estimate_ruler_designer_cost(category, modifiers, progression)
        )

        lines = [f"{trait_id} = {{"]
        lines.append(f"\tcategory = {category}")
        if genetic:
            lines.append("\tgenetic = yes")
        if group:
            lines.append(f"\tgroup = {group}")
        lines.append(f"\ticon = {icon_token}")
        if modifiers:
            lines.append("")
            lines.extend(_render_modifiers(modifiers))

        if progression:
            lines.append("")
            lines.append("\ttrack = {")
            for step in progression:
                lines.append(f"\t\t{step['xp']} = {{")
                lines.extend(_render_modifiers(step["modifiers"], indent="\t\t\t"))
                lines.append("\t\t}")
            lines.append("\t}")

            if dynamic_level_names:
                # Optional dynamic names by XP tier for leveled lifestyle traits.
                lines.append("")
                lines.append("\tname = {")
                lines.append("\t\tfirst_valid = {")
                for idx, step in enumerate(
                    sorted(progression, key=lambda x: x["xp"], reverse=True), start=1
                ):
                    lines.append("\t\t\ttriggered_desc = {")
                    lines.append("\t\t\t\ttrigger = {")
                    lines.append("\t\t\t\t\texists = this")
                    lines.append("\t\t\t\t\thas_trait_xp = {")
                    lines.append(f"\t\t\t\t\t\ttrait = {trait_id}")
                    lines.append(f"\t\t\t\t\t\tvalue >= {step['xp']}")
                    lines.append("\t\t\t\t\t}")
                    lines.append("\t\t\t\t}")
                    lines.append(f"\t\t\t\tdesc = trait_{trait_id}_{idx}")
                    lines.append("\t\t\t}")
                lines.append(f"\t\t\tdesc = trait_{trait_id}")
                lines.append("\t\t}")
                lines.append("\t}")

        lines.append("")
        lines.append(f"\truler_designer_cost = {final_cost}")

        if opposites:
            lines.append("")
            lines.append(f"\topposites = {{ {' '.join(opposites)} }}")
        lines.append("}")
        trait_script = "\n".join(lines) + "\n"

        # CK3 localization requires UTF-8 BOM
        loc_content = (
            "l_english:\n"
            f" trait_{trait_id}:0 \"{_escape_loc_text(display_name)}\"\n"
            f" trait_{trait_id}_desc:0 \"{_escape_loc_text(final_description)}\"\n"
        )

        if progression and dynamic_level_names:
            progression_loc_lines: list[str] = []
            for idx, step in enumerate(sorted(progression, key=lambda x: x["xp"], reverse=True), start=1):
                level_name = step.get("name") or f"{display_name} {_LEVEL_WORD.get(idx, idx)}"
                progression_loc_lines.append(
                    f" trait_{trait_id}_{idx}:0 \"{_escape_loc_text(level_name)}\""
                )
            loc_content += "\n".join(progression_loc_lines) + "\n"

        base = output_dir / (mod_name or "mod")
        trait_dir = base / "common" / "traits"
        loc_dir = base / "localization" / "english"
        trait_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        trait_path = trait_dir / f"{trait_id}.txt"
        loc_path = loc_dir / f"{trait_id}_l_english.yml"

        trait_path.write_text(trait_script, encoding="utf-8-sig")
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        # Allow callers to share one generated image across many traits while
        # still keeping the trait script's icon reference one-to-one with the
        # trait id that CK3 resolves.
        icon_dir = base / "gfx" / "interface" / "icons" / "traits"
        source_icon = icon_dir / f"{icon_base}.dds"
        fallback_icon = icon_dir / f"{trait_id}.dds"
        if source_icon.is_file() and source_icon != fallback_icon:
            shutil.copyfile(source_icon, fallback_icon)

        missing_icon_note = ""
        if not source_icon.is_file() and not fallback_icon.is_file():
            missing_icon_note = (
                "\nWarning: no matching icon file found in gfx/interface/icons/traits. "
                f"Expected {icon_token}."
            )

        return f"Trait:        {trait_path}\nLocalization: {loc_path}{missing_icon_note}"

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


def get_tools(output_dir) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, output_dir)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
