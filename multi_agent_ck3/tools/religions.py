import pathlib
from typing import Optional

# Vanilla religion family IDs
_RELIGION_FAMILIES = {"rf_abrahamic", "rf_eastern", "rf_pagan"}

# Vanilla graphical faith options
_GRAPHICAL_FAITHS = {
    "christian_gfx", "muslim_gfx", "jewish_gfx", "pagan_gfx",
    "hindu_gfx", "buddhist_gfx", "jain_gfx", "zoroastrian_gfx",
}


def register(mcp, output_dir: pathlib.Path):
    @mcp.tool()
    def create_religion(
        religion_id: str,
        display_name: str,
        description: str,
        adjective: str,
        adherent: str,
        adherent_plural: str,
        family: str = "rf_pagan",
        graphical_faith: str = "pagan_gfx",
        doctrines: Optional[list] = None,
        pagan_roots: bool = False,
        faiths: Optional[list] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 religion definition and localization files.
        Writes to common/religion/religions/ in the target mod folder.
        Args:
            religion_id: Internal snake_case identifier (e.g. 'sea_cults').
            display_name: Player-facing religion name.
            description: Religion tooltip description.
            adjective: Adjectival form of the name (e.g. 'Sea Cult').
            adherent: Singular adherent noun (e.g. 'Sea Cultist').
            adherent_plural: Plural adherent noun (e.g. 'Sea Cultists').
            family: Religion family — rf_abrahamic, rf_eastern, or rf_pagan.
            graphical_faith: Visual style — e.g. pagan_gfx, christian_gfx,
                             muslim_gfx, hindu_gfx.
            doctrines: List of doctrine IDs applied to all faiths
                       e.g. ["doctrine_gender_male_dominated",
                              "doctrine_pluralism_fundamentalist"].
            pagan_roots: If True, faiths without unreformed doctrine are
                         treated as reformed by the UI.
            faiths: List of faith dicts. Each dict may contain:
                    - id (str, required)
                    - display_name (str)
                    - description (str)
                    - color (list of 3 floats, e.g. [0.2, 0.2, 0.9])
                    - icon (str, filename without extension)
                    - holy_sites (list of str)
                    - tenets (list of str doctrine/tenet IDs)
            mod_name: Mod folder name. Defaults to 'mod'.
        Returns:
            Paths to the generated religion and localization files.
        """
        if family not in _RELIGION_FAMILIES:
            return f"Error: family must be one of {sorted(_RELIGION_FAMILIES)}"

        doctrines = doctrines or []
        faiths = faiths or []
        base = output_dir / (mod_name or "mod")

        religion_dir = base / "common" / "religion" / "religions"
        loc_dir = base / "localization" / "english"
        religion_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        # --- Religion script ---
        lines = [f"{religion_id} = {{"]
        lines.append(f"\tfamily = {family}")
        lines.append(f"\tgraphical_faith = {graphical_faith}")
        if pagan_roots:
            lines.append("\tpagan_roots = yes")
        lines.append("")
        for doc in doctrines:
            lines.append(f"\tdoctrine = {doc}")
        if faiths:
            lines.append("")
            lines.append("\tfaiths = {")
            for faith in faiths:
                faith_id = faith.get("id", f"{religion_id}_faith")
                color = faith.get("color", [0.5, 0.5, 0.5])
                icon = faith.get("icon", faith_id)
                holy_sites = faith.get("holy_sites", [])
                tenets = faith.get("tenets", [])

                lines.append(f"\t\t{faith_id} = {{")
                lines.append(f"\t\t\tcolor = {{ {' '.join(str(c) for c in color)} }}")
                lines.append(f"\t\t\ticon = {icon}")
                lines.append(f"\t\t\treformed_icon = {icon}_reformed")
                for site in holy_sites:
                    lines.append(f"\t\t\tholy_site = {site}")
                for tenet in tenets:
                    lines.append(f"\t\t\tdoctrine = {tenet}")
                lines.append("\t\t}")
            lines.append("\t}")
        lines.append("}")
        religion_script = "\n".join(lines) + "\n"

        # --- Localization ---
        loc_lines = ["l_english:"]
        loc_lines.append(f" {religion_id}:0 \"{display_name}\"")
        loc_lines.append(f" {religion_id}_adj:0 \"{adjective}\"")
        loc_lines.append(f" {religion_id}_adherent:0 \"{adherent}\"")
        loc_lines.append(f" {religion_id}_adherent_plural:0 \"{adherent_plural}\"")
        loc_lines.append(f" {religion_id}_desc:0 \"{description}\"")
        # Faith localization
        for faith in faiths:
            fid = faith.get("id", f"{religion_id}_faith")
            fname = faith.get("display_name", fid.replace("_", " ").title())
            fdesc = faith.get("description", "")
            loc_lines.append(f" {fid}:0 \"{fname}\"")
            loc_lines.append(f" {fid}_adj:0 \"{fname}\"")
            loc_lines.append(f" {fid}_adherent:0 \"{fname} Adherent\"")
            loc_lines.append(f" {fid}_adherent_plural:0 \"{fname} Adherents\"")
            loc_lines.append(f" {fid}_desc:0 \"{fdesc}\"")
        loc_content = "\n".join(loc_lines) + "\n"

        religion_path = religion_dir / f"{religion_id}.txt"
        loc_path = loc_dir / f"{religion_id}_l_english.yml"

        religion_path.write_text(religion_script, encoding="utf-8")
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        return f"Religion:     {religion_path}\nLocalization: {loc_path}"

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
