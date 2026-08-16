"""Men-at-arms unit creation tool."""
import pathlib
from typing import Optional


_VALID_UNIT_TYPES = {
    "heavy_infantry", "light_cavalry", "heavy_cavalry", "archers",
    "skirmishers", "pikemen", "siege_weapons", "special",
}

_VALID_TERRAINS = {
    "plains", "farmlands", "hills", "mountains", "forest", "taiga",
    "drylands", "desert", "floodplains", "oasis", "wetlands",
    "steppe", "jungle", "coastal_deserts", "arctic",
}


def _write_utf8(path: pathlib.Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def _write_utf8_bom(path: pathlib.Path, text: str) -> None:
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))


def register(mcp, repo_root: pathlib.Path):
    @mcp.tool()
    def create_men_at_arms(
        unit_id: str,
        display_name: str,
        description: str,
        unit_type: str = "heavy_infantry",
        damage: int = 50,
        toughness: int = 25,
        pursuit: int = 0,
        screen: int = 0,
        stack: int = 25,
        buy_cost_gold: float = 150.0,
        low_maintenance_gold: float = 0.5,
        high_maintenance_gold: float = 1.0,
        can_recruit_trigger: Optional[str] = None,
        siege_tier: Optional[int] = None,
        siege_value: Optional[float] = None,
        terrain_bonuses: Optional[dict] = None,
        ai_quality: int = 100,
        file_name: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 men-at-arms unit type definition and localization.

        Args:
            unit_id: Internal snake_case identifier (e.g. 'wandering_mages').
            display_name: Player-facing unit name shown in the UI.
            description: Tooltip/description for the unit.
            unit_type: Unit class. One of heavy_infantry, light_cavalry, heavy_cavalry,
                       archers, skirmishers, pikemen, siege_weapons, special.
            damage: Base damage value.
            toughness: Base toughness value.
            pursuit: Pursuit stat (pursuit damage when routing enemies).
            screen: Screen stat (reduces damage taken from cavalry).
            stack: Stack size (soldiers per unit).
            buy_cost_gold: Gold cost to recruit one stack.
            low_maintenance_gold: Monthly gold cost (peacetime).
            high_maintenance_gold: Monthly gold cost (wartime).
            can_recruit_trigger: CK3 trigger block body (without outer braces)
                                  that gates recruitment. Defaults to always = yes.
            siege_tier: Optional siege tier (1-3). Omit for non-siege units.
            siege_value: Optional daily siege progress added per stack (e.g. 0.2).
            terrain_bonuses: Dict mapping terrain names to dicts of stat bonuses.
                             e.g. {"plains": {"damage": 10}, "hills": {"toughness": 5}}
            ai_quality: AI weight for recruiting this unit (higher = preferred).
            file_name: Output .txt file name (defaults to unit_id).
            mod_name: Mod folder name. Defaults to 'WizardMod'.
        Returns:
            Paths to the generated unit type and localization files.
        """
        if unit_type not in _VALID_UNIT_TYPES:
            return f"Error: invalid unit_type '{unit_type}'. Valid: {sorted(_VALID_UNIT_TYPES)}"

        if terrain_bonuses:
            bad = [t for t in terrain_bonuses if t not in _VALID_TERRAINS]
            if bad:
                return f"Error: invalid terrain(s) {bad}. Valid: {sorted(_VALID_TERRAINS)}"

        base = repo_root / (mod_name or "WizardMod")
        maa_dir = base / "common" / "men_at_arms_types"
        loc_dir = base / "localization" / "english"
        maa_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        lines = [f"{unit_id} = {{"]
        lines.append(f"\ttype = {unit_type}")
        lines.append(f"\ticon = {unit_id}")
        lines.append("")
        lines.append(f"\tdamage = {damage}")
        lines.append(f"\ttoughness = {toughness}")
        lines.append(f"\tpursuit = {pursuit}")
        lines.append(f"\tscreen = {screen}")

        if siege_tier is not None:
            lines.append("")
            lines.append(f"\tsiege_tier = {siege_tier}")
        if siege_value is not None:
            lines.append(f"\tsiege_value = {siege_value}")

        lines.append("")
        lines.append(f"\tstack = {stack}")

        if terrain_bonuses:
            lines.append("")
            lines.append("\tterrain_bonus = {")
            for terrain, bonuses in terrain_bonuses.items():
                bonus_parts = "  ".join(f"{k} = {v}" for k, v in bonuses.items())
                lines.append(f"\t\t{terrain} = {{ {bonus_parts} }}")
            lines.append("\t}")

        lines.append("")
        lines.append(f"\tbuy_cost = {{ gold = {buy_cost_gold} }}")
        lines.append(f"\tlow_maintenance_cost = {{ gold = {low_maintenance_gold} }}")
        lines.append(f"\thigh_maintenance_cost = {{ gold = {high_maintenance_gold} }}")

        lines.append("")
        lines.append("\tcan_recruit = {")
        if can_recruit_trigger:
            for trig_line in can_recruit_trigger.strip().splitlines():
                lines.append(f"\t\t{trig_line.rstrip()}")
        else:
            lines.append("\t\talways = yes")
        lines.append("\t}")

        lines.append("")
        lines.append(f"\tai_quality = {{ value = {ai_quality} }}")
        lines.append("}")

        fname = (file_name or unit_id).rstrip(".txt") + ".txt"
        unit_path = maa_dir / fname
        _write_utf8(unit_path, "\n".join(lines) + "\n")

        loc_lines = (
            "l_english:\n"
            f' men_at_arms_type_{unit_id}:0 "{display_name}"\n'
            f' men_at_arms_type_{unit_id}_desc:0 "{description}"\n'
        )
        loc_path = loc_dir / f"{unit_id}_maa_l_english.yml"
        _write_utf8_bom(loc_path, loc_lines)

        return (
            f"Created men-at-arms unit '{unit_id}':\n"
            f"  Unit file : {unit_path}\n"
            f"  Loc file  : {loc_path}\n"
        )


class _ToolCollector:
    def __init__(self):
        self._fns: list = []
    def tool(self, **_):
        def _wrap(fn):
            self._fns.append(fn)
            return fn
        return _wrap


def get_tools(repo_root: pathlib.Path) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, repo_root)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
