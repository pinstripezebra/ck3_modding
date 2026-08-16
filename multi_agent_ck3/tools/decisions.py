import pathlib
from typing import Optional


def register(mcp, output_dir: pathlib.Path):
    @mcp.tool()
    def create_decision(
        decision_id: str,
        display_name: str,
        description: str,
        is_shown: str,
        effect: str,
        is_valid: Optional[str] = None,
        cooldown_years: Optional[int] = None,
        ai_check_interval_months: Optional[int] = 12,
        selection_tooltip: Optional[str] = None,
        confirm_text: Optional[str] = None,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create a CK3 decision definition and localization entries.

        Args:
            decision_id: Internal snake_case identifier for the decision.
            display_name: Player-facing decision title.
            description: Decision description/tooltip.
            is_shown: CK3 trigger block body (without outer braces) controlling
                      whether the decision appears.
            effect: CK3 effect block body (without outer braces) executed on take.
            is_valid: Optional CK3 trigger block body for taking the decision.
            cooldown_years: Optional cooldown duration in years.
            ai_check_interval_months: Optional AI recheck interval in months.
            selection_tooltip: Optional custom tooltip localization text. Defaults
                              to the description if omitted.
            confirm_text: Optional confirm button text. Defaults to "Take decision".
            mod_name: Mod folder name. Defaults to 'mod'.
        Returns:
            Paths to the generated decision and localization files.
        """
        base = output_dir / (mod_name or "mod")
        decisions_dir = base / "common" / "decisions"
        loc_dir = base / "localization" / "english"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        loc_dir.mkdir(parents=True, exist_ok=True)

        lines = [f"{decision_id} = {{"]
        lines.append(f"\ttitle = {decision_id}")
        lines.append(f"\tdesc = {decision_id}_desc")
        lines.append(f"\tselection_tooltip = {decision_id}_tooltip")
        lines.append(f"\tconfirm_text = {decision_id}_confirm")
        if ai_check_interval_months is not None:
            lines.append(f"\tai_check_interval = {ai_check_interval_months}")
        if cooldown_years is not None:
            lines.append(f"\tcooldown = {{ years = {cooldown_years} }}")
        lines.append("\tis_shown = {")
        for trigger_line in is_shown.strip().splitlines():
            lines.append(f"\t\t{trigger_line.rstrip()}")
        lines.append("\t}")
        if is_valid:
            lines.append("\tis_valid = {")
            for trigger_line in is_valid.strip().splitlines():
                lines.append(f"\t\t{trigger_line.rstrip()}")
            lines.append("\t}")
        lines.append("\teffect = {")
        for effect_line in effect.strip().splitlines():
            lines.append(f"\t\t{effect_line.rstrip()}")
        lines.append("\t}")
        lines.append("}")

        decision_path = decisions_dir / f"{decision_id}.txt"
        decision_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        tooltip_text = selection_tooltip or description
        confirm_label = confirm_text or "Take decision"
        loc_content = (
            "l_english:\n"
            f' {decision_id}:0 "{display_name}"\n'
            f' {decision_id}_desc:0 "{description}"\n'
            f' {decision_id}_tooltip:0 "{tooltip_text}"\n'
            f' {decision_id}_confirm:0 "{confirm_label}"\n'
        )
        loc_path = loc_dir / f"{decision_id}_l_english.yml"
        loc_path.write_text(loc_content, encoding="utf-8-sig")

        return f"Decision:     {decision_path}\nLocalization: {loc_path}"
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
