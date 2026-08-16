import pathlib
import re
from typing import Dict, List, Optional


_BLOCK_RE = re.compile(r"(?is)(window|container|button|textbox|icon)\s*=\s*\{(.*?)\}")
_POS_RE = re.compile(r"position\s*=\s*\{\s*(-?\d+)\s+(-?\d+)\s*\}", re.IGNORECASE)
_SIZE_RE = re.compile(r"size\s*=\s*\{\s*(\d+)\s+(\d+)\s*\}", re.IGNORECASE)
_NAME_RE = re.compile(r'name\s*=\s*"([^"]+)"', re.IGNORECASE)


SAFE_GUI_PROMPT_TEMPLATE = """You are generating CK3 .gui code.

== Layout container rules ==
- `vbox` / `hbox`: auto-flow children top-to-bottom or left-to-right. Children do NOT get
  explicit `position =`. Use `margin`, `spacing`, `layoutpolicy_*` to size them.
- `container`: children MUST have explicit `position = { x y }` and `size = { w h }`.
  Do NOT place `hbox` or `vbox` as a direct child of `container`.
- `widget`: same as container but also valid as a `types` base type and as a tooltipwidget root.
- Prefer `vbox`/`hbox` for flow layouts; use `container` only when pixel-exact positioning is required.

== Anchoring and positioning ==
- `parentanchor` and `widgetanchor` control how a widget is placed relative to its parent.
  `position = { x y }` is an OFFSET from the resolved anchor point — it is NOT an absolute coordinate.
- Bottom-edge HUD: `parentanchor = bottom|hcenter`  `widgetanchor = bottom|hcenter`  `position = { 0 -8 }`
- Modals: `parentanchor = center`  (no widgetanchor needed)
- Always add `allow_outside = yes` on any `window` whose anchor is bottom, right, or custom-offset,
  otherwise it will be clipped to the screen viewport.

== Window layers ==
Use `layer = top` for all mod HUD windows and modals so they render above vanilla UI.
Available layers (ascending z-order): bottom < middle < top < frontend.

== Tooltip / popup widgets ==
- `tooltipwidget = { my_type = {} }` renders adjacent to the element that owns it (hover element).
  It does NOT obey `parentanchor` of its enclosing `window`.
- The root type for a tooltipwidget MUST be `vbox` (NOT `widget` or `container`).
  Using `widget` or `container` as root causes CK3 to render the popup at the screen centre.
- Define each tooltip type EXACTLY ONCE across all loaded .gui files. Duplicate type definitions
  cause CK3 to silently pick one and discard the other — this is a common cause of wrong-position popups.

== Text elements ==
- `text_single`: single-line; use inside `hbox`/`vbox` with `layoutpolicy_horizontal = expanding`.
- `textbox`: multiline; requires explicit `size =`. Set `autoresize = no` unless intentional.
- Inside a `hbox`/`vbox` always set either `autoresize = yes` or a `minimumsize`; otherwise the
  widget may collapse to zero width.

== Hard constraints ==
- Keep all interactive/text elements inset by at least 8px from their parent edges.
- At most 3 decorative texture layers per panel.
- Every modal must have an explicit close button.
- Prefer stable `progressbar` or `text_single` meter rendering over decorative fill stacks.
- Do NOT duplicate `type` names that already exist in other loaded .gui files for this mod.

== Output requirements ==
- Return exactly one complete .gui snippet.
- Keep names unique and descriptive (prefix with mod namespace, e.g. `wizard_`).
- Call `lint_gui_layout` on the generated file immediately after writing it and fix all warnings.
- Call `get_gui_component_template` before generating any new component to reuse existing patterns.
"""


COMPONENT_TEMPLATES: Dict[str, str] = {
    # ── Two-column modal (left nav + right content) ───────────────────────────
    "modal_two_column": """window = {
\tname = \"my_modal\"
\tlayer = top
\tparentanchor = center
\tallow_outside = yes
\tsize = { 920 560 }
\tusing = Window_Background

\tcontainer = {
\t\tname = \"frame\"
\t\tposition = { 0 0 }
\t\tsize = { 920 560 }

\t\ttextbox = { name = \"title\" position = { 20 14 } size = { 420 30 } text = \"#bold Title#!\" }
\t\tbutton = { name = \"close\" position = { 882 10 } size = { 28 28 } text = \"#bold X#!\" }

\t\tcontainer = { name = \"left_pane\" position = { 20 54 } size = { 250 486 } }
\t\tcontainer = { name = \"right_pane\" position = { 286 54 } size = { 614 486 } }
\t}
}
""",
    # ── Single-column vbox modal with close button ────────────────────────────
    # Use this for simple dialogs. vbox auto-flows children; no manual position needed.
    "modal_standard": """window = {
\tname = \"my_modal\"
\tlayer = top
\tparentanchor = center
\tallow_outside = yes
\tsize = { 600 500 }
\tusing = Window_Background

\tvbox = {
\t\tparentanchor = top|left
\t\tmargin = { 16 12 }
\t\tspacing = 8
\t\tlayoutpolicy_horizontal = expanding

\t\thbox = {
\t\t\tlayoutpolicy_horizontal = expanding
\t\t\ttext_single = {
\t\t\t\ttext = \"TITLE_LOC_KEY\"
\t\t\t\tdefault_format = \"#bold #high\"
\t\t\t\tusing = Font_Size_Large
\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\tautoresize = no
\t\t\t}
\t\t\tbutton = { name = \"close\" size = { 28 28 } text = \"#bold X#!\" }
\t\t}
\t\tdivider = { size = { 0 1 } layoutpolicy_horizontal = expanding }
\t\t# Add content widgets here
\t}
}
""",
    # ── Tooltip/popup breakdown widget (MUST use vbox root) ───────────────────
    # IMPORTANT: root type must be `vbox` — NOT `widget` or `container`.
    # Using widget/container as root renders the popup at screen centre.
    # Reference: popup.gui (achievement_popup_window pattern).
    "popup_breakdown": """types MyNamespace
{
\ttype my_popup_tooltip = vbox
\t{
\t\tminimumsize = { 300 0 }

\t\thbox = {
\t\t\tmargin = { 5 5 }
\t\t\tusing = Window_Background_Subwindow

\t\t\ticon = {
\t\t\t\ttexture = \"gfx/interface/icons/traits/my_icon.dds\"
\t\t\t\tsize = { 56 56 }
\t\t\t}
\t\t\tspacer = { size = { 5 5 } }
\t\t\tvbox = {
\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\tlayoutpolicy_vertical = expanding
\t\t\t\ttext_single = {
\t\t\t\t\ttext = \"HEADER_LOC_KEY\"
\t\t\t\t\tdefault_format = \"#low\"
\t\t\t\t\tautoresize = no
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\tminimumsize = { 180 0 }
\t\t\t\t}
\t\t\t\ttext_single = {
\t\t\t\t\traw_text = \"+0/mo\"
\t\t\t\t\tdefault_format = \"#high\"
\t\t\t\t\tusing = Font_Size_Medium
\t\t\t\t\talign = nobaseline
\t\t\t\t}
\t\t\t}
\t\t}
\t\t# Optional conditional rows (use flowcontainer so hidden rows collapse)
\t\tflowcontainer = {
\t\t\tdirection = vertical
\t\t\tignoreinvisible = yes
\t\t\tmargin = { 8 4 }
\t\t\tspacing = 3
\t\t\twidget = {
\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\thbox = {
\t\t\t\t\tlayoutpolicy_horizontal = expanding
\t\t\t\t\ttext_single = { text = \"ROW_LABEL\" default_format = \"#high\" layoutpolicy_horizontal = expanding autoresize = no using = Font_Size_Small }
\t\t\t\t\ttext_single = { raw_text = \"+0\" default_format = \"#color:{0.45,0.8,1.0,1.0}\" using = Font_Size_Small margin_right = 3 }
\t\t\t\t}
\t\t\t}
\t\t}
\t}
}
# To attach: button = { ... tooltipwidget = { my_popup_tooltip = {} } }
""",
    # ── hbox label+value row for embedding in a vbox ─────────────────────────
    "resource_row": """hbox = {
\tlayoutpolicy_horizontal = expanding
\tspacing = 6
\ttext_single = {
\t\ttext = \"LABEL_LOC_KEY\"
\t\tdefault_format = \"#low\"
\t\tlayoutpolicy_horizontal = expanding
\t\tautoresize = no
\t\tusing = Font_Size_Small
\t}
\ttext_single = {
\t\traw_text = \"+0/mo\"
\t\tdefault_format = \"#color:{0.45,0.8,1.0,1.0}\"
\t\tautoresize = yes
\t\tusing = Font_Size_Small
\t\talign = nobaseline
\t}
}
""",
    # ── Bottom-centre persistent HUD overlay window ───────────────────────────
    # allow_outside = yes is REQUIRED — bottom-anchored windows are partially off-screen.
    "hud_overlay_widget": """window = {
\tname = \"my_hud_overlay\"
\tlayer = top
\tparentanchor = bottom|hcenter
\twidgetanchor = bottom|hcenter
\tallow_outside = yes
\tposition = { 0 -8 }
\tsize = { 200 50 }
\tmovable = no

\tstate = { name = _show  using = Animation_FadeIn_Quick }
\tstate = { name = _hide  using = Animation_FadeOut_Quick }

\tbackground = { using = Background_Area_Dark }

\t# content here
}
""",
    # ── Native progressbar (0.0–1.0 normalized value) ─────────────────────────
    "mana_progressbar": """window = {
\tname = \"wizard_mana_bar\"
\tlayer = top
\tparentanchor = bottom|left
\twidgetanchor = bottom|left
\tallow_outside = yes
\tposition = { 10 -10 }
\tsize = { 130 50 }
\tmovable = no

\tstate = { name = _show  using = Animation_FadeIn_Quick }
\tstate = { name = _hide  using = Animation_FadeOut_Quick }

\tbackground = { using = Background_Area_Dark }

\tvbox = {
\t\tparentanchor = center
\t\twidgetanchor = center
\t\tspacing = 4
\t\ttext_single = {
\t\t\tname = \"mana_label\"
\t\t\traw_text = \"[GetPlayer.MakeScope.Var('wizard_mana').GetValue|0] / 1000\"
\t\t\tdefault_format = \"#color:{0.45,0.8,1.0,1.0}\"
\t\t\tusing = Font_Size_Small
\t\t\tautoresize = yes
\t\t\talign = hcenter|nobaseline
\t\t}
\t\tprogressbar = {
\t\t\tname = \"mana_fill\"
\t\t\tsize = { 110 10 }
\t\t\tvalue = \"[GetPlayer.MakeScope.Var('wizard_mana').GetValue|0]\"
\t\t\tmin = 0
\t\t\tmax = 1000
\t\t\tdirection = right
\t\t\tusing = Progressbar_Standard
\t\t}
\t}

\tbutton = {
\t\tname = \"mana_tooltip_trigger\"
\t\tparentanchor = center
\t\twidgetanchor = center
\t\tsize = { 130 50 }
\t\talwaystransparent = yes
\t\ttooltipwidget = { my_popup_tooltip = {} }
\t}
}
""",
    # ── How to instantiate a wizard_spell_tile type ──────────────────────────
    # wizard_spell_tile is defined in wizard_spellbook_spell_tile.gui.
    # Use this pattern inside a spells_<lore> container. Increment position Y by 96 per tile.
    "spell_tile_instance": """wizard_spell_tile = {
\tposition = { 0 0 }  # increment by 96 for each subsequent tile
\tblock "tile_selected" {
\t\tbackground = { visible = "[GetScriptedGui('wizard_spell_X_selected').IsShown( GuiScope.SetRoot( GetPlayer.MakeScope ).End )]"  color = { 0.4 0.6 1.0 0.15 } }
\t}
\tblock "tile_button" {
\t\tbutton = { parentanchor = center  widgetanchor = center  size = { 556 90 }
\t\t  onclick = "[GetScriptedGui('wizard_spellbook_select_spell_X').Execute( GuiScope.SetRoot( GetPlayer.MakeScope ).End )]" }
\t}
\tblock "tile_name_text" { raw_text = "Spell Name (Tier 1)" }
\tblock "tile_status" {
\t\ttext_single = { name = "spell_X_known"     position = { 390 8 } size = { 156 22 } raw_text = "#bold #high Known#!"  visible = "..."   autoresize = no  align = right|nobaseline }
\t\ttext_single = { name = "spell_X_unlearned" position = { 390 8 } size = { 156 22 } raw_text = "#weak Unlearned#!"    visible = "..." autoresize = no  align = right|nobaseline }
\t}
\tblock "tile_desc_text" { text = "SPELL_DESC_LOC_KEY" }
\tblock "tile_cost_text" { raw_text = "25 Mana" }
}
""",
    # ── Old (kept for compat) ─────────────────────────────────────────────────
    "primary_action_button": """icon = {
\tname = \"action_bg\"
\tposition = { 0 0 }
\tsize = { 230 48 }
\tspriteType = \"GFX_wizard_tile_contract_2_flat\"
}
button = {
\tname = \"action_button\"
\tposition = { 4 3 }
\tsize = { 222 42 }
\ttext = \"#bold #high Action#!\"
}
""",
    "mana_thermometer": """window = {
\tname = \"wizard_mana_bar\"
\tlayer = top
\tparentanchor = bottom|left
\tallow_outside = yes
\tposition = { 24 -124 }
\tsize = { 170 360 }

\tcontainer = {
\t\tname = \"mana_thermometer\"
\t\tposition = { 0 0 }
\t\tsize = { 170 360 }
\t\t# Use simple segmented fill for robust rendering.
\t\tcontainer = { name = \"mana_fill_stack\" position = { 48 24 } size = { 24 220 } }
\t\ttextbox = { name = \"mana_label\" position = { 12 314 } size = { 150 36 } text = \"#bold #high Mana 0/1000#!\" }
\t}
}
""",
}


def _extract_size(block_text: str):
    match = _SIZE_RE.search(block_text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _extract_pos(block_text: str):
    match = _POS_RE.search(block_text)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _extract_name(block_text: str) -> str:
    match = _NAME_RE.search(block_text)
    return match.group(1) if match else "(unnamed)"


def lint_gui_text(gui_text: str, file_hint: str = "(inline)") -> List[str]:
    issues: List[str] = []

    # High-risk texture/overlay patterns that often render as dark blocks.
    if re.search(r"size\s*=\s*\{\s*[2-9]\d{3}\s+[2-9]\d{3}\s*\}", gui_text):
        issues.append(f"{file_hint}: very large UI blocks detected; verify no full-screen overlays are blocking other UI.")

    if gui_text.count("spriteType") > 24:
        issues.append(f"{file_hint}: many sprite layers detected (>24); reduce decorative stacking for render stability.")

    if "█" in gui_text:
        issues.append(f"{file_hint}: block glyph fill detected; prefer sprite/text templates for cleaner CK3 rendering.")

    # ── Duplicate `position` or `size` inside the same block ──────────────────
    # A textbox/icon/button block with two `position =` lines means the model
    # accidentally merged two separate blocks. CK3 uses the last value — the
    # earlier one is silently discarded, causing misaligned or invisible elements.
    for kind, body in _BLOCK_RE.findall(gui_text):
        bname = _extract_name(body)
        if len(re.findall(r'\bposition\s*=\s*\{', body, re.IGNORECASE)) > 1:
            issues.append(
                f"{file_hint}: {kind} '{bname}' has multiple 'position =' entries — "
                f"likely a merged block; split into separate elements."
            )
        if len(re.findall(r'\bsize\s*=\s*\{', body, re.IGNORECASE)) > 1:
            issues.append(
                f"{file_hint}: {kind} '{bname}' has multiple 'size =' entries — "
                f"likely a merged block; split into separate elements."
            )

    # ── CK3-specific: duplicate `type` names across the file ─────────────────
    # CK3 silently discards duplicates; this is the most common cause of
    # wrong-position popups when two .gui files both define the same type.
    type_names = re.findall(r'\btype\s+(\w+)\s*=', gui_text, re.IGNORECASE)
    seen: set = set()
    for t in type_names:
        if t in seen:
            issues.append(f"{file_hint}: duplicate type definition '{t}' — CK3 will silently drop one; causes wrong-position popups.")
        seen.add(t)

    # ── CK3-specific: tooltipwidget with non-vbox root type ──────────────────
    # If `tooltipwidget` references a type whose root is `widget` or `container`
    # CK3 renders the popup at screen centre instead of near the element.
    tooltip_types = re.findall(r'tooltipwidget\s*=\s*\{\s*(\w+)\s*=', gui_text, re.IGNORECASE)
    for tt in tooltip_types:
        # Find the type definition root: `type <name> = <root>`
        root_match = re.search(rf'\btype\s+{re.escape(tt)}\s*=\s*(\w+)', gui_text, re.IGNORECASE)
        if root_match:
            root = root_match.group(1).lower()
            if root in ("widget", "container"):
                issues.append(
                    f"{file_hint}: tooltipwidget type '{tt}' has root '{root}' — "
                    f"must be 'vbox' or the popup will render at screen centre, not near the element."
                )

    # ── CK3-specific: bottom/right-anchored window missing allow_outside ─────
    windows_iter = re.finditer(
        r'window\s*=\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}', gui_text, re.DOTALL | re.IGNORECASE
    )
    for w in windows_iter:
        body = w.group(1)
        anchor = re.search(r'parentanchor\s*=\s*([^\n]+)', body, re.IGNORECASE)
        if anchor:
            anchor_val = anchor.group(1).lower()
            if ("bottom" in anchor_val or "right" in anchor_val):
                if "allow_outside" not in body:
                    name_m = _NAME_RE.search(body)
                    name = name_m.group(1) if name_m else "(unnamed)"
                    issues.append(
                        f"{file_hint}: window '{name}' uses parentanchor '{anchor_val.strip()}' "
                        f"but is missing 'allow_outside = yes' — element may be clipped."
                    )

    # ── CK3-specific: window missing `layer =` ───────────────────────────────
    for w in re.finditer(r'^\s*window\s*=\s*\{', gui_text, re.MULTILINE | re.IGNORECASE):
        # Grab text from the opening brace to find a name; check for layer within ~20 lines
        snippet = gui_text[w.start():w.start() + 600]
        if "layer" not in snippet[:400]:
            name_m = _NAME_RE.search(snippet)
            name = name_m.group(1) if name_m else "(unnamed)"
            issues.append(
                f"{file_hint}: window '{name}' has no 'layer =' — may render below vanilla UI. Add 'layer = top'."
            )

    for kind, body in _BLOCK_RE.findall(gui_text):
        name = _extract_name(body)
        pos = _extract_pos(body)
        size = _extract_size(body)

        if kind in {"textbox", "button"} and pos is not None:
            x, y = pos
            if x < 8:
                issues.append(f"{file_hint}: {kind} '{name}' is close to left edge (x={x}); use at least 8px inset.")
            if y < 4:
                issues.append(f"{file_hint}: {kind} '{name}' is close to top edge (y={y}); consider more breathing room.")

        if kind == "textbox" and size is not None:
            w, _ = size
            if w < 80:
                issues.append(f"{file_hint}: textbox '{name}' width is very small ({w}); likely text clipping risk.")

    return issues


def lint_gui_file(gui_path: pathlib.Path) -> List[str]:
    try:
        content = gui_path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{gui_path}: failed to read file: {exc}"]
    return lint_gui_text(content, str(gui_path))


def lint_mod_gui(mod_path: pathlib.Path) -> Dict[str, List[str]]:
    findings: Dict[str, List[str]] = {}
    gui_dir = mod_path / "gui"
    if not gui_dir.is_dir():
        return findings

    # Per-file checks
    gui_files = list(gui_dir.rglob("*.gui"))
    for gui_file in gui_files:
        issues = lint_gui_file(gui_file)
        if issues:
            findings[str(gui_file)] = issues

    # Cross-file duplicate `type` name check
    type_to_file: Dict[str, str] = {}
    for gui_file in gui_files:
        try:
            content = gui_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for t in re.findall(r'\btype\s+(\w+)\s*=', content, re.IGNORECASE):
            if t in type_to_file:
                key = str(gui_file)
                msg = (
                    f"{key}: type '{t}' is also defined in '{type_to_file[t]}' — "
                    f"CK3 silently drops one; causes wrong-position popups."
                )
                findings.setdefault(key, []).append(msg)
            else:
                type_to_file[t] = str(gui_file)

    return findings


# ── Spellbook generator ───────────────────────────────────────────────────────

def _sg_show(name: str) -> str:
    return f"[GetScriptedGui('{name}').IsShown( GuiScope.SetRoot( GetPlayer.MakeScope ).End )]"


def _sg_exec(name: str) -> str:
    return f"[GetScriptedGui('{name}').Execute( GuiScope.SetRoot( GetPlayer.MakeScope ).End )]"


def _spell_tile(lore_id: str, spell: dict, y: int) -> str:
    sid = spell["id"]
    name = spell.get("name", sid)
    tier = spell.get("tier", 1)
    cost = spell.get("mana_cost", 25)
    desc = spell.get("desc_key", f"wizard_spell_{sid}_desc")
    T = "\t"
    return (
        f"{T*4}wizard_spell_tile = {{\n"
        f"{T*5}position = {{ 0 {y} }}\n"
        f"{T*5}block \"tile_selected\" {{\n"
        f'{T*6}background = {{ visible = "{_sg_show(f"wizard_spell_{sid}_selected")}"  color = {{ 0.4 0.6 1.0 0.15 }} }}\n'
        f"{T*5}}}\n"
        f"{T*5}block \"tile_button\" {{\n"
        f'{T*6}button = {{ parentanchor = center  widgetanchor = center  size = {{ 556 90 }}'
        f'  onclick = "{_sg_exec(f"wizard_spellbook_select_spell_{sid}")}" }}\n'
        f"{T*5}}}\n"
        f'{T*5}block "tile_name_text" {{ raw_text = "{name} (Tier {tier})" }}\n'
        f"{T*5}block \"tile_status\" {{\n"
        f'{T*6}text_single = {{ name = "spell_{sid}_known"     position = {{ 390 8 }} size = {{ 156 22 }} raw_text = "#bold #high Known#!"  visible = "{_sg_show(f"wizard_spell_{sid}_known")}"   autoresize = no  align = right|nobaseline }}\n'
        f'{T*6}text_single = {{ name = "spell_{sid}_unlearned" position = {{ 390 8 }} size = {{ 156 22 }} raw_text = "#weak Unlearned#!"    visible = "{_sg_show(f"wizard_spell_{sid}_unknown")}" autoresize = no  align = right|nobaseline }}\n'
        f"{T*5}}}\n"
        f'{T*5}block "tile_desc_text" {{ text = "{desc}" }}\n'
        f'{T*5}block "tile_cost_text" {{ raw_text = "{cost} Mana" }}\n'
        f"{T*4}}}\n"
    )


def generate_spellbook_gui(
    lores: List[dict],
    spells: List[dict],
    modal_width: int = 940,
    modal_height: int = 600,
) -> str:
    """Generate a complete wizard spellbook .gui file from a data specification.

    Args:
        lores:  List of dicts, each with keys:
                  id   – snake_case identifier matching scripted_gui names (e.g. 'fire')
                  name – display string (e.g. 'Lore of Fire')
        spells: List of dicts, each with keys:
                  lore_id   – matches a lore id above
                  id        – unique snake_case id (e.g. 'fire_1')
                  name      – display name (e.g. 'Ember Touch')
                  tier      – integer 1/2/3
                  mana_cost – integer
                  desc_key  – localization key (defaults to wizard_spell_{id}_desc)
        modal_width:  Modal window pixel width (default 940).
        modal_height: Modal window pixel height (default 600).

    Returns:
        Full .gui file contents as a string. Write this to WizardMod/gui/wizard_spellbook.gui.
        The matching wizard_spellbook_spell_tile.gui (types WizardSpellTiles) must also be present.
    """
    T = "\t"

    # ── Layout constants (derived from modal dimensions) ──────────────────────
    LORE_PANEL_X = 32
    LORE_PANEL_Y = 88
    LORE_PANEL_W = 270
    SPELL_PANEL_X = 322
    SPELL_PANEL_W = modal_width - SPELL_PANEL_X - 18
    PANEL_H = modal_height - LORE_PANEL_Y - 8

    LORE_BUTTON_X = 8
    LORE_BUTTON_W = LORE_PANEL_W - 16
    LORE_BUTTON_H = 36
    LORE_FIRST_Y = 40        # header occupies y=0..28, first button at y=40
    LORE_ROW_STRIDE = 42     # 36 button + 6 gap

    TILE_STRIDE = 96         # 90 tile + 6 gap
    SPELL_START_Y = 40       # below a header row

    CLOSE_BTN_X = modal_width - 38
    CLOSE_BTN_Y = 8

    # ── Section helpers ───────────────────────────────────────────────────────
    def lore_nav_block() -> str:
        lines = [
            f"{T*2}container = {{\n",
            f'{T*3}name = "lore_panel"\n',
            f"{T*3}position = {{ {LORE_PANEL_X} {LORE_PANEL_Y} }}\n",
            f"{T*3}size = {{ {LORE_PANEL_W} {PANEL_H} }}\n",
            f"\n",
            f'{T*3}textbox = {{ name = "lore_header" position = {{ 8 0 }} size = {{ {LORE_BUTTON_W} 28 }} text = "#bold #high Arcane Lores#!" }}\n',
            f"\n",
        ]
        for i, lore in enumerate(lores):
            lid = lore["id"]
            lname = lore["name"]
            y = LORE_FIRST_Y + i * LORE_ROW_STRIDE
            lines.append(
                f'{T*3}button = {{\n'
                f'{T*4}name = "lore_{lid}"\n'
                f"{T*4}position = {{ {LORE_BUTTON_X} {y} }}\n"
                f"{T*4}size = {{ {LORE_BUTTON_W} {LORE_BUTTON_H} }}\n"
                f'{T*4}text = "#high {lname}#!"\n'
                f'{T*4}visible = "{_sg_show(f"wizard_spellbook_lore_{lid}_available")}"\n'
                f'{T*4}onclick = "{_sg_exec(f"wizard_spellbook_select_lore_{lid}")}"\n'
                f"{T*3}}}\n"
                f'{T*3}textbox = {{\n'
                f'{T*4}name = "lore_{lid}_locked"\n'
                f"{T*4}position = {{ {LORE_BUTTON_X} {y} }}\n"
                f"{T*4}size = {{ {LORE_BUTTON_W} {LORE_BUTTON_H} }}\n"
                f'{T*4}text = "#weak {lname} (Locked)#!"\n'
                f'{T*4}visible = "{_sg_show(f"wizard_spellbook_lore_{lid}_unavailable")}"\n'
                f"{T*3}}}\n"
                f"\n"
            )
        lines.append(f"{T*2}}}\n")
        return "".join(lines)

    def spell_panel_block() -> str:
        lines = [
            f"{T*2}container = {{\n",
            f'{T*3}name = "spell_panel"\n',
            f"{T*3}position = {{ {SPELL_PANEL_X} {LORE_PANEL_Y} }}\n",
            f"{T*3}size = {{ {SPELL_PANEL_W} {PANEL_H} }}\n",
            f"\n",
            f'{T*3}textbox = {{ name = "spell_header" position = {{ 10 0 }} size = {{ {SPELL_PANEL_W - 20} 30 }} text = "#bold #high Spell Compendium#!" }}\n',
            f'{T*3}divider = {{ name = "spell_header_rule" position = {{ 10 30 }} size = {{ {SPELL_PANEL_W - 20} 8 }} using = HorizontalSeparator }}\n',
            f"\n",
        ]
        for lore in lores:
            lid = lore["id"]
            lore_spells = [s for s in spells if s["lore_id"] == lid]
            lines.append(
                f"{T*3}container = {{\n"
                f'{T*4}name = "spells_{lid}"\n'
                f"{T*4}position = {{ 10 {SPELL_START_Y} }}\n"
                f"{T*4}size = {{ {SPELL_PANEL_W - 20} {PANEL_H - SPELL_START_Y - 10} }}\n"
                f'{T*4}visible = "{_sg_show(f"wizard_spellbook_lore_{lid}_available")}"\n'
                f"\n"
            )
            for j, spell in enumerate(lore_spells):
                lines.append(_spell_tile(lid, spell, j * TILE_STRIDE))
            lines.append(f"{T*3}}}\n\n")

        # Action buttons at bottom of spell panel
        btn_y = PANEL_H - 58
        lines.append(
            f'{T*3}button = {{\n'
            f'{T*4}name = "spellbook_learn_selected"\n'
            f"{T*4}position = {{ 0 {btn_y} }}\n"
            f"{T*4}size = {{ 220 42 }}\n"
            f'{T*4}text = "#bold #high Learn Selected#!"\n'
            f'{T*4}visible = "{_sg_show("wizard_spellbook_can_learn_selected")}"\n'
            f'{T*4}onclick = "{_sg_exec("wizard_spellbook_learn_selected")}"\n'
            f"{T*3}}}\n"
        )
        lines.append(f"{T*2}}}\n")
        return "".join(lines)

    # ── Assemble file ─────────────────────────────────────────────────────────
    bg_icon_y = LORE_PANEL_Y - 14
    bg_w = modal_width - 16
    bg_h = modal_height - bg_icon_y - 8

    parts = [
        "# Generated by create_spellbook_gui — do not hand-edit repeating sections.\n",
        "# Re-run the tool to regenerate if lores or spells change.\n\n",

        # Toggle button
        f'window = {{\n'
        f'{T}name = "wizard_spellbook_toggle"\n'
        f'{T}layer = top\n'
        f'{T}parentanchor = bottom|hcenter\n'
        f'{T}widgetanchor = bottom|hcenter\n'
        f'{T}allow_outside = yes\n'
        f'{T}position = {{ 130 -58 }}\n'
        f'{T}size = {{ 210 48 }}\n'
        f'{T}using = Window_Background\n'
        f'{T}visible = "{_sg_show("wizard_spellbook_ui_allowed")}"\n'
        f"\n"
        f'{T}button = {{\n'
        f'{T*2}name = "open_spellbook_button"\n'
        f'{T*2}parentanchor = center\n'
        f'{T*2}widgetanchor = center\n'
        f'{T*2}size = {{ 200 40 }}\n'
        f'{T*2}text = "#bold Open Spellbook#!"\n'
        f'{T*2}onclick = "{_sg_exec("wizard_spellbook_toggle")}"\n'
        f'{T}}}\n'
        f"}}\n\n",

        # Veil (click-outside-to-close overlay)
        f'window = {{\n'
        f'{T}name = "wizard_spellbook_veil"\n'
        f'{T}layer = top\n'
        f'{T}parentanchor = center\n'
        f'{T}allow_outside = yes\n'
        f'{T}size = {{ 6000 3400 }}\n'
        f'{T}alwaystransparent = yes\n'
        f'{T}visible = "{_sg_show("wizard_spellbook_modal_visible")}"\n'
        f"\n"
        f'{T}button = {{\n'
        f'{T*2}name = "spellbook_veil_close"\n'
        f'{T*2}parentanchor = center\n'
        f'{T*2}widgetanchor = center\n'
        f'{T*2}size = {{ 6000 3400 }}\n'
        f'{T*2}text = ""\n'
        f'{T*2}onclick = "{_sg_exec("wizard_spellbook_close")}"\n'
        f'{T}}}\n'
        f"}}\n\n",

        # Modal
        f'window = {{\n'
        f'{T}name = "wizard_spellbook_modal"\n'
        f'{T}layer = top\n'
        f'{T}parentanchor = center\n'
        f'{T}allow_outside = yes\n'
        f'{T}size = {{ {modal_width} {modal_height} }}\n'
        f'{T}using = Window_Background\n'
        f'{T}visible = "{_sg_show("wizard_spellbook_modal_visible")}"\n'
        f"\n"
        f'{T}container = {{\n'
        f'{T*2}name = "spellbook_frame"\n'
        f'{T*2}position = {{ 0 0 }}\n'
        f'{T*2}size = {{ {modal_width} {modal_height} }}\n'
        f"\n"
        # Title
        f'{T*2}textbox = {{ name = "spellbook_title" position = {{ 24 12 }} size = {{ 480 36 }} text = "#bold #high Grand Spellbook - Arcane Codex#!" }}\n'
        # Close button
        f'{T*2}button = {{ name = "spellbook_close" position = {{ {CLOSE_BTN_X} {CLOSE_BTN_Y} }} size = {{ 30 30 }} text = "#bold X#!" onclick = "{_sg_exec("wizard_spellbook_close")}" }}\n'
        f"\n"
        # Background layers
        f'{T*2}icon = {{ name = "spellbook_main_bg"      position = {{ 8 {bg_icon_y} }} size = {{ {bg_w} {bg_h} }} spriteType = "GFX_wizard_tile_contract_3_flat" }}\n'
        f'{T*2}icon = {{ name = "spellbook_bg_texture"   position = {{ 16 {bg_icon_y + 8} }} size = {{ {bg_w - 16} {bg_h - 16} }} spriteType = "GFX_wizard_tile_contract_3_texture" }}\n'
        f'{T*2}icon = {{ name = "spellbook_column_divider" position = {{ {SPELL_PANEL_X - 16} {LORE_PANEL_Y} }} size = {{ 6 {PANEL_H} }} spriteType = "GFX_wizard_tile_contract_3_texture" }}\n'
        f"\n",

        lore_nav_block(),
        "\n",
        spell_panel_block(),

        f"{T}}}\n"  # close container
        f"}}\n",    # close window
    ]

    return "".join(parts)

