"""CK3 duchy capital building generator.

Lessons learned (hard-won from debugging):
- Building .txt MUST be UTF-8 WITH BOM — CK3 gives a parse error without it.
- type_icon = "icon_building_<name>.dds"  (full filename, quoted, with .dds)
- Icon lives at gfx/interface/icons/building_types/icon_building_<name>.dds
  (NOT gfx/interface/icons/buildings/ — that folder is ignored for this purpose).
- Icon dimensions: 150×130 px, A8R8G8B8, no mipmaps.
- No .gfx sprite registration needed — the game reads building_types/ directly.
- Loc keys are PER LEVEL: building_type_<building_id>_01:0 "Name"
  and building_type_<building_id>_01_desc:0 "Desc"  (not a shared key).
- Each level REPLACES the previous level's modifiers (they do not stack).
"""

import pathlib
from typing import Optional

from tools.icons import _apply_building_frame, _normalize_output_name, _run_replicate_flux, _save_dds
from PIL import Image


_ICON_W = 150
_ICON_H = 130
_GEN_W = 256
_GEN_H = 256


def _build_level_block(
    building_id: str,
    level: int,
    num_levels: int,
    base_id: str,
    cost_gold: int,
    construction_time: int,
    modifiers: dict,
    holding_modifiers: dict,
    duchy_modifiers: dict,
) -> list[str]:
    """Return lines for one building level block."""
    lines = [f"{building_id} = {{"]
    lines.append(f"\ttype = duchy_capital")
    lines.append(f'\ttype_icon = "icon_building_{base_id}.dds"')
    lines.append("")
    lines.append(f"\tcost = {{ gold = {cost_gold} }}")
    lines.append(f"\tconstruction_time = {construction_time}")
    lines.append("")
    lines.append("\tcan_construct_potential = {")
    lines.append("\t\talways = yes")
    lines.append("\t}")
    lines.append("")
    lines.append("\tcan_construct_showing_failures_only = {")
    lines.append("\t\tbuilding_requirement_tribal = no")
    lines.append("\t}")

    if modifiers:
        lines.append("")
        lines.append("\tcounty_modifier = {")
        for k, v in modifiers.items():
            lines.append(f"\t\t{k} = {v}")
        lines.append("\t}")

    if holding_modifiers:
        lines.append("")
        lines.append("\tcounty_holding_modifier = {")
        lines.append("\t\tholding = castle_holding")
        for k, v in holding_modifiers.items():
            lines.append(f"\t\t{k} = {v}")
        lines.append("\t}")

    if duchy_modifiers:
        lines.append("")
        lines.append("\tduchy_capital_county_modifier = {")
        for k, v in duchy_modifiers.items():
            lines.append(f"\t\t{k} = {v}")
        lines.append("\t}")

    if level < num_levels:
        next_id = f"{base_id}_{level + 1:02d}"
        lines.append("")
        lines.append(f"\tnext_building = {next_id}")

    lines.append("")
    lines.append("\tai_value = {")
    lines.append("\t\tbase = 10")
    lines.append("\t\tai_general_building_modifier = yes")
    lines.append("\t}")
    lines.append("}")
    return lines


def register(mcp, repo_root: pathlib.Path):

    @mcp.tool()
    def create_building(
        building_id: str,
        display_name: str,
        image_prompt: str,
        level_descriptions: list[str],
        costs_gold: list[int],
        income_mult_per_level: list[float],
        dev_growth_per_level: list[float],
        duchy_dev_per_level: Optional[list[float]] = None,
        construction_time: int = 730,
        mod_name: str = "ElderMagic",
    ) -> str:
        """Create a complete CK3 duchy capital building: script, localization, and icon.

        Embeds all hard-won lessons from building modding:
        - Writes building .txt with UTF-8 BOM (required by CK3).
        - Sets type_icon = "icon_building_<building_id>.dds" (full filename, quoted).
        - Generates icon at gfx/interface/icons/building_types/ at 150x130 px.
        - Writes per-level localization keys: building_type_<id>_01 ... _0N.

        Args:
            building_id: Snake_case base id (e.g. 'wizard_tower'). Levels get
                         _01 … _0N suffixes automatically.
            display_name: Player-facing name shown in game (same for all levels).
            image_prompt: Text prompt for the building icon image generation.
            level_descriptions: List of per-level description strings. Length
                                 determines the number of building levels.
            costs_gold: Gold cost per level (must match length of level_descriptions).
            income_mult_per_level: Castle holding income multiplier per level
                                   (e.g. [0.05, 0.10, 0.15]).
            dev_growth_per_level: county_modifier development_growth_factor per
                                   level (e.g. [0.05, 0.10, 0.15]).
            duchy_dev_per_level: Optional duchy_capital_county_modifier
                                  development_growth_factor per level.
            construction_time: Days to construct each level (default 730 = 2 yrs).
            mod_name: Mod folder name under repo root (default 'ElderMagic').
        Returns:
            Summary of generated files.
        """
        num_levels = len(level_descriptions)
        if not (len(costs_gold) == len(income_mult_per_level) == len(dev_growth_per_level) == num_levels):
            raise ValueError(
                "costs_gold, income_mult_per_level, dev_growth_per_level, and "
                "level_descriptions must all have the same length."
            )
        if duchy_dev_per_level and len(duchy_dev_per_level) != num_levels:
            raise ValueError("duchy_dev_per_level must have the same length as level_descriptions.")

        base = repo_root / mod_name
        buildings_dir = base / "common" / "buildings"
        loc_dir = base / "localization" / "english"
        icon_dir = base / "gfx" / "interface" / "icons" / "building_types"
        buildings_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)
        icon_dir.mkdir(parents=True, exist_ok=True)

        # --- Building definition file ---
        all_lines: list[str] = [
            f"# {display_name} - Duchy Capital Building",
            f"# Generated by create_building. {num_levels} upgrade levels.",
            "",
        ]
        for i in range(1, num_levels + 1):
            lvl_id = f"{building_id}_{i:02d}"
            modifiers = {"development_growth_factor": dev_growth_per_level[i - 1]}
            holding_modifiers = {"income_mult": income_mult_per_level[i - 1]}
            duchy_modifiers = {}
            if duchy_dev_per_level:
                duchy_modifiers["development_growth_factor"] = duchy_dev_per_level[i - 1]

            block = _build_level_block(
                building_id=lvl_id,
                level=i,
                num_levels=num_levels,
                base_id=building_id,
                cost_gold=costs_gold[i - 1],
                construction_time=construction_time,
                modifiers=modifiers,
                holding_modifiers=holding_modifiers,
                duchy_modifiers=duchy_modifiers,
            )
            all_lines.extend(block)
            all_lines.append("")

        building_path = buildings_dir / f"{building_id}.txt"
        building_path.write_bytes(
            ("\n".join(all_lines) + "\n").encode("utf-8-sig")
        )

        # --- Localization file ---
        loc_lines = ["l_english:"]
        for i in range(1, num_levels + 1):
            lvl_id = f"{building_id}_{i:02d}"
            desc = level_descriptions[i - 1].replace('"', '\\"')
            loc_lines.append(f' building_type_{lvl_id}:0 "{display_name}"')
            loc_lines.append(f' building_type_{lvl_id}_desc:0 "{desc}"')
        loc_content = "\n".join(loc_lines) + "\n"

        loc_path = loc_dir / f"{building_id}_buildings_l_english.yml"
        loc_path.write_bytes(loc_content.encode("utf-8-sig"))

        # --- Icon ---
        icon_path = icon_dir / f"icon_building_{building_id}.dds"
        model_prompt = (
            "medieval fantasy building icon, flat 2D illustration, single centered "
            "structure, bold silhouette, high contrast, muted stone and amber palette, "
            "no text, CK3 UI art style; subject: " + image_prompt.strip()
        )
        img = _run_replicate_flux(model_prompt, _GEN_W, _GEN_H).resize(
            (_ICON_W, _ICON_H), Image.LANCZOS
        )
        img = _apply_building_frame(img)
        _save_dds(img, icon_path)

        return (
            f"Building:     {building_path}\n"
            f"Localization: {loc_path}\n"
            f"Icon:         {icon_path}\n"
            f"Levels:       {num_levels}\n"
            f"Deploy with:  deploy_mod(mod_name='{mod_name}')"
        )
