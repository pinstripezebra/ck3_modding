import pathlib
from typing import List

from tools import gui_quality


def _build_popup_row(row: dict) -> str:
    """Build one conditional widget>hbox row for a popup_breakdown tooltip.
    flowcontainer forbids hbox/vbox as direct children — each row is wrapped in a widget.
    """
    label = row.get("label_key", "LABEL_KEY")
    value = row.get("value_raw", "+0")
    visible = row.get("visible", "")
    color = "#color:{0.45,0.8,1.0,1.0}"
    T = "\t"
    lines = [f"{T*5}widget = {{"]
    if visible:
        lines.append(f'{T*6}visible = "{visible}"')
    lines.append(f"{T*6}layoutpolicy_horizontal = expanding")
    lines.append(f"{T*6}hbox = {{")
    lines.append(f"{T*7}layoutpolicy_horizontal = expanding")
    lines.append(
        f'{T*7}text_single = {{ text = "{label}"  layoutpolicy_horizontal = expanding  '
        f'default_format = "#high"  autoresize = no  using = Font_Size_Small }}'
    )
    lines.append(
        f'{T*7}text_single = {{ raw_text = "{value}"  default_format = "{color}"  '
        f'using = Font_Size_Small  margin_right = 3 }}'
    )
    lines.append(f"{T*6}}}")
    lines.append(f"{T*5}}}")
    return "\n".join(lines)


def register(mcp, repo_root: pathlib.Path):
    @mcp.tool()
    def lint_gui_layout(gui_path: str) -> str:
        """Lint a CK3 .gui file for common layout and rendering risks.
        Args:
            gui_path: Absolute path to a .gui file.
        Returns:
            A newline-separated list of warnings, or 'No issues found.'
        """
        path = pathlib.Path(gui_path)
        if not path.is_file():
            return f"Error: file not found: {gui_path}"
        if path.suffix.lower() != ".gui":
            return f"Error: expected a .gui file, got: {path.name}"

        issues = gui_quality.lint_gui_file(path)
        return "\n".join(issues) if issues else "No issues found."

    @mcp.tool()
    def lint_mod_gui_layout(mod_path: str) -> str:
        """Lint all GUI files in a CK3 mod folder.
        Args:
            mod_path: Absolute path to the mod root.
        Returns:
            A report of warnings grouped by file, or 'No issues found.'
        """
        path = pathlib.Path(mod_path)
        if not path.is_dir():
            return f"Error: directory not found: {mod_path}"

        findings = gui_quality.lint_mod_gui(path)
        if not findings:
            return "No issues found."

        lines: list[str] = []
        for file_name, issues in findings.items():
            lines.append(file_name)
            lines.extend(f"  - {issue}" for issue in issues)
        return "\n".join(lines)

    @mcp.tool()
    def get_gui_prompt_template() -> str:
        """Return a constrained CK3 GUI generation prompt template."""
        return gui_quality.SAFE_GUI_PROMPT_TEMPLATE

    @mcp.tool()
    def get_gui_component_template(component_name: str) -> str:
        """Return a reusable CK3 GUI component snippet using correct CK3 layout patterns.
        Supported component names:
          modal_standard        - single-column vbox modal with close button
          modal_two_column      - two-pane container modal (left nav + right content)
          popup_breakdown       - vbox-root tooltipwidget (achievement popup.gui pattern)
                                  NOTE: root MUST be vbox — widget/container roots render at screen centre
          resource_row          - hbox label+value row for embedding in a vbox
          hud_overlay_widget    - bottom-centre persistent HUD overlay with allow_outside
          mana_progressbar      - bottom-left window with native progressbar element
          mana_thermometer      - legacy thermometer fill stack (use mana_progressbar instead)
          primary_action_button - styled action button pair
        """
        token = component_name.strip().lower()
        template = gui_quality.COMPONENT_TEMPLATES.get(token)
        if template is None:
            names = ", ".join(sorted(gui_quality.COMPONENT_TEMPLATES.keys()))
            return f"Error: unknown component '{component_name}'. Available: {names}"
        return template

    @mcp.tool()
    def create_popup_gui(
        type_name: str,
        namespace: str,
        header_loc_key: str,
        icon_texture: str,
        rows: list,
        total_loc_key: str,
        total_value_raw: str,
        icon_size: int = 56,
    ) -> str:
        """Generate a CK3 popup breakdown GUI types block following the popup.gui pattern.

        The output is a complete `types` block. Paste it at the end of a .gui file and
        reference the type in any hover-able element:
            button = { ... tooltipwidget = { <type_name> = {} } }

        Key rules encoded from popup.gui:
          - Base type is vbox (NOT container — container cannot have hbox/vbox children).
          - hbox uses Window_Background_Subwindow for the dark frame.
          - Icon left at icon_size x icon_size, spacer { 5 5 }, then text vbox.
          - Header: default_format = "#low", autoresize = no.
          - Rows: flowcontainer direction=vertical ignoreinvisible=yes so hidden rows collapse.
          - Row labels: #high Font_Size_Small. Row values: arcane blue color Font_Size_Small.
          - Total label: #low. Total value: #high Font_Size_Medium align=nobaseline.

        Args:
            type_name:        Snake_case type identifier (e.g. 'mana_breakdown_tooltip').
            namespace:        types block namespace identifier (e.g. 'WizardManaBar').
            header_loc_key:   Localization key for the dim subtitle header.
            icon_texture:     GFX path to the icon DDS (e.g. 'gfx/interface/icons/traits/mana_flame.dds').
            rows:             List of row dicts, each with:
                                'label_key' - localization key for the label
                                'value_raw' - raw inline text (e.g. '+1/mo')
                                'visible'   - optional CK3 visible expression
            total_loc_key:    Localization key for the summary/total label.
            total_value_raw:  Raw text or CK3 expression for the total value.
            icon_size:        Icon pixel size (default 56).
        Returns:
            Complete .gui types block snippet.
        """
        T = "\t"
        rows_text = "\n".join(_build_popup_row(r) for r in rows) if rows else ""

        return (
            f"types {namespace}\n"
            f"{{\n"
            f"{T}type {type_name} = vbox\n"
            f"{T}{{\n"
            f"{T*2}minimumsize = {{ 300 0 }}\n"
            f"\n"
            f"{T*2}hbox = {{\n"
            f"{T*3}margin = {{ 5 5 }}\n"
            f"{T*3}using = Window_Background_Subwindow\n"
            f"\n"
            f"{T*3}icon = {{\n"
            f"{T*4}size = {{ {icon_size} {icon_size} }}\n"
            f'{T*4}texture = "{icon_texture}"\n'
            f"{T*3}}}\n"
            f"\n"
            f"{T*3}spacer = {{ size = {{ 5 5 }} }}\n"
            f"\n"
            f"{T*3}vbox = {{\n"
            f"{T*4}margin = {{ 0 3 }}\n"
            f"{T*4}layoutpolicy_horizontal = expanding\n"
            f"{T*4}layoutpolicy_vertical = expanding\n"
            f"{T*4}spacing = 2\n"
            f"\n"
            f"{T*4}text_single = {{\n"
            f'{T*5}text = "{header_loc_key}"\n'
            f'{T*5}default_format = "#low"\n'
            f"{T*5}layoutpolicy_horizontal = expanding\n"
            f"{T*5}autoresize = no\n"
            f"{T*5}minimumsize = {{ -1 10 }}\n"
            f"{T*4}}}\n"
            f"\n"
            f"{T*4}flowcontainer = {{\n"
            f"{T*5}direction = vertical\n"
            f"{T*5}ignoreinvisible = yes\n"
            f"{T*5}layoutpolicy_horizontal = expanding\n"
            f"{T*5}spacing = 1\n"
            f"\n"
            f"{rows_text}\n"
            f"{T*4}}}\n"
            f"\n"
            f"{T*4}divider = {{ layoutpolicy_horizontal = expanding }}\n"
            f"\n"
            f"{T*4}hbox = {{\n"
            f"{T*5}layoutpolicy_horizontal = expanding\n"
            f"{T*5}text_single = {{\n"
            f'{T*6}text = "{total_loc_key}"\n'
            f'{T*6}default_format = "#low"\n'
            f"{T*6}layoutpolicy_horizontal = expanding\n"
            f"{T*6}autoresize = no\n"
            f"{T*6}align = nobaseline\n"
            f"{T*5}}}\n"
            f"{T*5}text_single = {{\n"
            f'{T*6}raw_text = "{total_value_raw}"\n'
            f'{T*6}default_format = "#high"\n'
            f"{T*6}using = Font_Size_Medium\n"
            f"{T*6}align = nobaseline\n"
            f"{T*6}margin_right = 3\n"
            f"{T*5}}}\n"
            f"{T*4}}}\n"
            f"{T*3}}}\n"
            f"{T*2}}}\n"
            f"{T}}}\n"
            f"}}"
        )

    @mcp.tool()
    def create_spellbook_gui(
        lores: list,
        spells: list,
        output_path: str,
        modal_width: int = 940,
        modal_height: int = 600,
    ) -> str:
        """Generate and write the complete wizard spellbook .gui file from a data spec.

        Use this instead of hand-writing wizard_spellbook.gui — it generates all
        lore nav buttons, spell tile instances, and scripted_gui wiring automatically,
        eliminating positional math errors and repetition bugs.

        Args:
            lores: List of dicts, each with:
                     id   – snake_case lore identifier (e.g. 'fire')
                     name – display string (e.g. 'Lore of Fire')
            spells: List of dicts, each with:
                     lore_id   – matches a lore id above
                     id        – unique snake_case spell id (e.g. 'fire_1')
                     name      – display name
                     tier      – integer 1/2/3
                     mana_cost – integer
                     desc_key  – localization key (optional, defaults to wizard_spell_{id}_desc)
            output_path: Absolute path to write the file (e.g. the WizardMod/gui/ folder).
                         Pass the .gui file path directly.
            modal_width:  Modal pixel width (default 940).
            modal_height: Modal pixel height (default 600).

        Returns:
            Summary of what was written, or an error message.

        NOTE: wizard_spellbook_spell_tile.gui (types WizardSpellTiles) must remain
        present alongside this file — it is NOT regenerated by this tool.
        """
        content = gui_quality.generate_spellbook_gui(
            lores=lores,
            spells=spells,
            modal_width=modal_width,
            modal_height=modal_height,
        )
        out = pathlib.Path(output_path)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")
        except OSError as exc:
            return f"Error writing '{output_path}': {exc}"

        lore_count = len(lores)
        spell_count = len(spells)
        issues = gui_quality.lint_gui_text(content, str(out))
        lint_summary = "No lint issues." if not issues else "\n".join(issues)
        return (
            f"Wrote {out.name} ({len(content)} bytes).\n"
            f"  {lore_count} lores, {spell_count} spells ({spell_count // lore_count if lore_count else 0} avg per lore).\n"
            f"Lint: {lint_summary}"
        )

    @mcp.tool()
    def get_ck3_layout_guide() -> str:
        """Return a concise CK3 GUI layout reference card.
        Covers: vbox/hbox vs container, layoutpolicy, text_single/textbox,
        progressbar, tooltipwidget anchoring rules, layer values,
        allow_outside requirements, and common anti-patterns to avoid.
        """
        return gui_quality.SAFE_GUI_PROMPT_TEMPLATE

    @mcp.tool()
    def get_reference_gui(filename: str) -> str:
        """Return the full contents of a vanilla CK3 .gui reference file from the assets library.
        Use this BEFORE generating any new GUI component to see a working real-world pattern.

        Available reference files (pass filename only, no path):
          popup.gui                    - achievement popup; tooltipwidget/vbox pattern
          window_character.gui         - sidebar window; portrait + vbox layout
          window_character_lifestyle.gui - lifestyle/perk tree window
          window_council.gui           - council grid; hbox/vbox flow layout
          window_county_view.gui       - county detail window
          window_artifact_details.gui  - artifact viewer; icon + text layout

        Args:
            filename: Exact filename (e.g. 'popup.gui').
        Returns:
            Full file contents, or an error message with the list of available files.
        """
        assets_gui = repo_root / "ck3_agent" / "assets" / "gui"
        target = assets_gui / pathlib.Path(filename).name  # strip any path prefix
        if not target.is_file():
            available = sorted(p.name for p in assets_gui.glob("*.gui"))
            return (
                f"Error: '{filename}' not found in assets/gui.\n"
                f"Available files:\n" + "\n".join(f"  {n}" for n in available)
            )
        try:
            return target.read_text(encoding="utf-8")
        except OSError as exc:
            return f"Error reading '{filename}': {exc}"

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


def get_tools(repo_root) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, repo_root)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
