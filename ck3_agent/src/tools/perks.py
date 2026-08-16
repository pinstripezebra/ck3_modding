import pathlib
from typing import Optional

# Valid CK3 lifestyle identifiers
_LIFESTYLES = {
    "martial",
    "diplomacy",
    "stewardship",
    "intrigue",
    "learning",
}


def register(mcp, output_dir: pathlib.Path):
    @mcp.tool()
    def create_perk(
        perk_id: str,
        display_name: str,
        description: str,
        lifestyle: str,
        tree: str,
        position_x: int = 0,
        position_y: int = 0,
        parent: Optional[str] = None,
        modifiers: Optional[dict] = None,
        can_be_picked: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 lifestyle perk definition and localization entry.
        Perks are written to common/lifestyle_perks/ in the target mod folder.
        Args:
            perk_id: Internal snake_case identifier (e.g. 'herculean_might').
            display_name: Player-facing perk name shown in the perk tree UI.
            description: Tooltip text shown when hovering the perk.
            lifestyle: Lifestyle this perk belongs to — martial, diplomacy,
                       stewardship, intrigue, or learning.
            tree: Track/tree name within the lifestyle (e.g. 'combat', 'strategy').
            position_x: Horizontal grid position in the perk tree UI.
            position_y: Vertical grid position in the perk tree UI.
            parent: ID of the parent perk this perk requires, if any.
            modifiers: Dict of character modifier keys to values
                       e.g. {"prowess": 3, "monthly_prestige": 0.25}.
            can_be_picked: Optional CK3 trigger block body (without outer braces)
                           e.g. "prowess >= 12".
            mod_name: Mod folder name to write into. Defaults to 'mod' subfolder.
        Returns:
            Paths to the generated perk and localization files.
        """
        if lifestyle not in _LIFESTYLES:
            return f"Error: lifestyle must be one of {sorted(_LIFESTYLES)}"

        modifiers = modifiers or {}
        base = output_dir / (mod_name or "mod")
        lifestyle_dir = base / "common" / "lifestyle_perks"
        loc_dir = base / "localization" / "english"
        lifestyle_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        # Build perk script block
        lines = [f"{perk_id} = {{"]
        lines.append(f"\tlifestyle = {lifestyle}_lifestyle")
        lines.append(f"\ttree = {tree}")
        lines.append(f"\tposition = {{ {position_x} {position_y} }}")
        lines.append("\ticon = node_learning")
        lines.append("")

        if can_be_picked:
            lines.append("\tcan_be_picked = {")
            for trigger_line in can_be_picked.strip().splitlines():
                lines.append(f"\t\t{trigger_line.strip()}")
            lines.append("\t}")
            lines.append("")

        if parent:
            lines.append(f"\tparent = {parent}")
            lines.append("")

        if modifiers:
            lines.append("\tcharacter_modifier = {")
            for key, val in modifiers.items():
                lines.append(f"\t\t{key} = {val}")
            lines.append("\t}")
            lines.append("")

        lines.append("\tauto_selection_weight = {")
        lines.append("\t\tvalue = 100")
        lines.append("\t}")
        lines.append("}")

        perk_script = "\n".join(lines) + "\n"

        # Localization (UTF-8 BOM required by CK3)
        loc_content = (
            "l_english:\n"
            f" {perk_id}:0 \"{display_name}\"\n"
            f" {perk_id}_desc:0 \"{description}\"\n"
        )

        perk_path = lifestyle_dir / f"{perk_id}.txt"
        loc_path = loc_dir / f"{perk_id}_l_english.yml"

        perk_path.write_text(perk_script, encoding="utf-8-sig")
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        return f"Perk:         {perk_path}\nLocalization: {loc_path}"
