"""Generate the Elder Magic character-window overrides from their upstream files.

The mods override `gui/window_character.gui` to show total magic power beside the
skill stats. Hand-maintaining a ~5,000 line fork of vanilla's (and AGOT's) window
silently loses upstream changes, so the override is rebuilt from the current
upstream file on every deploy instead.

If the anchor ever moves, generation raises `AnchorError` and the deploy fails
loudly rather than shipping a stale window.
"""

from __future__ import annotations

import pathlib

ANCHOR = "char_governor_efficiency_value"

HEADER = (
    "# GENERATED FILE — do not edit by hand.\n"
    "# Rebuilt from the upstream window_character.gui by"
    " multi_agent_ck3/tools/character_window.py.\n"
    "# Source: {source}\n"
)

MAGIC_POWER_BLOCK = """\
# Elder Magic: total magic power, styled to match the skill stats.
vbox = {
\tvisible = "[GreaterThan_CFixedPoint( Character.MakeScope.ScriptValue('wizard_total_magic_power'), '(CFixedPoint)0' )]"
\tmargin_right = 3
\tspacing = -3

\tusing = Animation_Character_Window_Refresh

\ticon = {
\t\tname = "wizard_magic_power_icon"
\t\tsize = { 32 32 }
\t\ttexture = "gfx/interface/icons/traits/mana_flame.dds"
\t\ttooltip = "WIZARD_MAGIC_POWER_BREAKDOWN_TT"
\t\tusing = tooltip_ne
\t}

\ttext_single = {
\t\tname = "wizard_magic_power_value"
\t\tdefault_format = "#color:{0.45,0.8,1.0,1.0}"
\t\traw_text = "[Character.MakeScope.ScriptValue('wizard_total_magic_power')]"
\t\talign = nobaseline
\t}
}
"""


class AnchorError(RuntimeError):
    """The upstream window no longer matches what the generator expects."""


def _insertion_point(lines: list[str]) -> int:
    """Index just past the governor-efficiency vbox, where our stat block goes."""
    hits = [i for i, line in enumerate(lines) if ANCHOR in line]
    if len(hits) != 1:
        raise AnchorError(
            f"expected exactly one line containing {ANCHOR!r}, found {len(hits)}"
        )

    # From inside the anchor's text_single, depth -1 closes it and -2 closes the vbox.
    depth = 0
    for i in range(hits[0], len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth <= -2:
            return i + 1
    raise AnchorError("could not find the end of the vbox enclosing the anchor")


def build(upstream_text: str, source_label: str) -> str:
    lines = upstream_text.splitlines()
    at = _insertion_point(lines)
    indent = lines[at - 1][: len(lines[at - 1]) - len(lines[at - 1].lstrip())]
    block = [indent + l if l.strip() else l for l in MAGIC_POWER_BLOCK.splitlines()]
    out = lines[:at] + [""] + block + lines[at:]
    return HEADER.format(source=source_label) + "\n".join(out) + "\n"


def generate(upstream: pathlib.Path, target: pathlib.Path, source_label: str) -> None:
    if not upstream.is_file():
        raise AnchorError(f"upstream window not found: {upstream}")
    text = upstream.read_text(encoding="utf-8-sig", errors="ignore")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build(text, source_label), encoding="utf-8")
