import pathlib
from typing import Optional

# Vanilla ethos pillar IDs
_ETHOS_VALUES = {
    "ethos_bellicose", "ethos_communal", "ethos_courtly",
    "ethos_egalitarian", "ethos_spiritual", "ethos_stoic",
}


def register(mcp, output_dir: pathlib.Path):
    @mcp.tool()
    def create_culture(
        culture_id: str,
        display_name: str,
        group_id: str,
        ethos: str,
        heritage: str,
        color: Optional[list] = None,
        traditions: Optional[list] = None,
        character_modifier: Optional[dict] = None,
        language: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 culture definition and localization files.
        Writes to common/culture/cultures/ in the target mod folder.
        Args:
            culture_id: Internal snake_case identifier (e.g. 'herculean').
            display_name: Player-facing culture name.
            group_id: Culture group this culture belongs to
                      (e.g. 'mediterranean_group'). The culture will be
                      written inside this group block.
            ethos: Ethos pillar ID — ethos_bellicose, ethos_communal,
                   ethos_courtly, ethos_egalitarian, ethos_spiritual,
                   or ethos_stoic.
            heritage: Heritage key grouping related cultures
                      (e.g. 'heritage_latin').
            color: RGB float list for the map color e.g. [1.0, 0.5, 0.2].
                   Defaults to [0.5, 0.5, 0.5].
            traditions: List of tradition IDs
                        e.g. ["tradition_martial_admiration",
                               "tradition_practiced_pirates"].
            character_modifier: Dict of modifier keys to values applied to
                                 all characters of this culture
                                 e.g. {"diplomacy": 1, "monthly_prestige": 0.1}.
            language: Optional language key (e.g. 'language_latin').
            mod_name: Mod folder name. Defaults to 'mod'.
        Returns:
            Paths to the generated culture and localization files.
        """
        if ethos not in _ETHOS_VALUES:
            return f"Error: ethos must be one of {sorted(_ETHOS_VALUES)}"

        color = color or [0.5, 0.5, 0.5]
        traditions = traditions or []
        character_modifier = character_modifier or {}
        base = output_dir / (mod_name or "mod")

        culture_dir = base / "common" / "culture" / "cultures"
        loc_dir = base / "localization" / "english"
        culture_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        # --- Culture script (wrapped in its group block) ---
        culture_lines = [f"{culture_id} = {{"]
        culture_lines.append(f"\tcolor = {{ {' '.join(str(c) for c in color)} }}")
        culture_lines.append(f"\theritage = {heritage}")
        culture_lines.append(f"\tethos = {ethos}")
        if language:
            culture_lines.append(f"\tlanguage = {language}")
        if traditions:
            culture_lines.append("")
            culture_lines.append("\ttraditions = {")
            for t in traditions:
                culture_lines.append(f"\t\t{t}")
            culture_lines.append("\t}")
        if character_modifier:
            culture_lines.append("")
            culture_lines.append("\tcharacter_modifier = {")
            for key, val in character_modifier.items():
                culture_lines.append(f"\t\t{key} = {val}")
            culture_lines.append("\t}")
        culture_lines.append("}")

        group_lines = [f"{group_id} = {{"]
        for cl in culture_lines:
            group_lines.append(f"\t{cl}")
        group_lines.append("}")
        culture_script = "\n".join(group_lines) + "\n"

        # --- Localization (CK3 requires UTF-8 BOM) ---
        loc_lines = [
            "l_english:",
            f" {culture_id}:0 \"{display_name}\"",
            f" {culture_id}_collective_noun:0 \"The {display_name}\"",
            f" {culture_id}_prefix:0 \"{display_name}\"",
        ]
        loc_content = "\n".join(loc_lines) + "\n"

        culture_path = culture_dir / f"{culture_id}.txt"
        loc_path = loc_dir / f"{culture_id}_l_english.yml"

        culture_path.write_text(culture_script, encoding="utf-8")
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        return f"Culture:      {culture_path}\nLocalization: {loc_path}"

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
