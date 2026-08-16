"""Tools for common/ infrastructure files: script_values, on_actions, scripted_effects,
and a general-purpose write_localization tool used by all agents."""
import pathlib
import re
from typing import Optional


def _write_utf8(path: pathlib.Path, text: str) -> None:
    """Write plain UTF-8 (no BOM) — required for all .txt script files."""
    path.write_bytes(text.encode("utf-8"))


def _write_utf8_bom(path: pathlib.Path, text: str) -> None:
    """Write UTF-8 with BOM — required for all .yml localization files."""
    path.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))


def _append_utf8(path: pathlib.Path, text: str) -> None:
    """Append to a UTF-8 file, preserving existing content and encoding."""
    existing = path.read_bytes() if path.exists() else b""
    # Strip any trailing BOM that might have crept in
    content = existing.lstrip(b"\xef\xbb\xbf").decode("utf-8")
    combined = content.rstrip() + "\n\n" + text
    _write_utf8(path, combined)


def _indent_block(body: str, depth: int = 1) -> list[str]:
    prefix = "\t" * depth
    return [f"{prefix}{line.rstrip()}" for line in body.strip().splitlines()]


def register(mcp, repo_root: pathlib.Path):

    # ── Script Values ──────────────────────────────────────────────────────

    @mcp.tool()
    def write_script_value(
        value_id: str,
        formula: str,
        description: Optional[str] = None,
        file_name: Optional[str] = None,
        append_to_existing: bool = True,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create or append a CK3 script_value definition.

        Script values are computed formulas used as numeric values in triggers,
        effects, and GUI. They are always evaluated fresh — no storage needed.

        Args:
            value_id: Snake_case identifier (e.g. 'wizard_total_magic_power').
            formula: The value body WITHOUT outer braces. Use CK3 script_value
                     syntax: value = 0 / add = X / if = { limit = {} add = Y }.
            description: Short comment added above the definition.
            file_name: Target .txt file name inside common/script_values/.
                       Defaults to value_id.
            append_to_existing: If True and file exists, appends; else overwrites.
            mod_name: Mod folder name. Defaults to 'WizardMod'.
        Returns:
            Path to the written script_values file.
        """
        base = repo_root / (mod_name or "WizardMod")
        sv_dir = base / "common" / "script_values"
        sv_dir.mkdir(parents=True, exist_ok=True)

        fname = (file_name or value_id).removesuffix(".txt") + ".txt"
        path = sv_dir / fname

        comment = f"# {description}\n" if description else ""
        block_lines = [f"{comment}{value_id} = {{"] + _indent_block(formula) + ["}"]
        block = "\n".join(block_lines) + "\n"

        if append_to_existing and path.exists():
            _append_utf8(path, block)
        else:
            _write_utf8(path, block)

        return f"Script value '{value_id}' written to {path}"

    # ── On Actions ────────────────────────────────────────────────────────

    @mcp.tool()
    def write_on_action(
        on_action_id: str,
        effect_body: Optional[str] = None,
        chained_on_actions: Optional[list] = None,
        hook_into: Optional[str] = None,
        file_name: Optional[str] = None,
        append_to_existing: bool = True,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create or append a CK3 on_action definition using the append-safe pattern.

        To hook into a vanilla on_action without overriding it, set hook_into
        to the vanilla on_action name. This generates the correct two-block pattern:

            vanilla_on_action = { on_actions = { my_mod_action } }
            my_mod_action = { effect = { ... } }

        Args:
            on_action_id: Snake_case identifier for the new mod on_action.
            effect_body: CK3 effect body (without outer braces) for this on_action.
            chained_on_actions: List of on_action IDs to chain from this on_action.
            hook_into: Optional vanilla on_action to hook into. Generates the
                       append-safe two-block pattern automatically.
            file_name: Target .txt file name inside common/on_actions/.
                       Defaults to on_action_id.
            append_to_existing: Append to existing file if True (recommended).
            mod_name: Mod folder name. Defaults to 'WizardMod'.
        Returns:
            Path to the written on_actions file.
        """
        base = repo_root / (mod_name or "WizardMod")
        oa_dir = base / "common" / "on_actions"
        oa_dir.mkdir(parents=True, exist_ok=True)

        fname = (file_name or on_action_id).removesuffix(".txt") + ".txt"
        path = oa_dir / fname

        blocks: list[str] = []

        if hook_into:
            hook_block = (
                f"{hook_into} = {{\n"
                f"\ton_actions = {{ {on_action_id} }}\n"
                f"}}"
            )
            blocks.append(hook_block)

        action_lines = [f"{on_action_id} = {{"]
        if chained_on_actions:
            action_lines.append("\ton_actions = {")
            for oa in chained_on_actions:
                action_lines.append(f"\t\t{oa}")
            action_lines.append("\t}")
        if effect_body:
            action_lines.append("\teffect = {")
            action_lines.extend(_indent_block(effect_body, depth=2))
            action_lines.append("\t}")
        action_lines.append("}")
        blocks.append("\n".join(action_lines))

        content = "\n\n".join(blocks) + "\n"

        if append_to_existing and path.exists():
            _append_utf8(path, content)
        else:
            _write_utf8(path, content)

        return f"On_action '{on_action_id}' written to {path}"

    # ── Scripted Effects ──────────────────────────────────────────────────

    @mcp.tool()
    def write_scripted_effect(
        effect_id: str,
        body: str,
        description: Optional[str] = None,
        file_name: Optional[str] = None,
        append_to_existing: bool = True,
        mod_name: Optional[str] = None,
    ) -> str:
        """Create or append a CK3 scripted_effect definition.

        Scripted effects are reusable named effect blocks callable with
        'my_effect = yes' from events, decisions, or other effects.

        Args:
            effect_id: Snake_case identifier (e.g. 'wizard_award_study_xp').
            body: The effect body WITHOUT outer braces.
            description: Short comment above the definition.
            file_name: Target .txt file name inside common/scripted_effects/.
                       Defaults to effect_id.
            append_to_existing: Append to existing file if True (recommended).
            mod_name: Mod folder name. Defaults to 'WizardMod'.
        Returns:
            Path to the written scripted_effects file.
        """
        base = repo_root / (mod_name or "WizardMod")
        se_dir = base / "common" / "scripted_effects"
        se_dir.mkdir(parents=True, exist_ok=True)

        fname = (file_name or effect_id).removesuffix(".txt") + ".txt"
        path = se_dir / fname

        comment = f"# {description}\n" if description else ""
        block_lines = [f"{comment}{effect_id} = {{"] + _indent_block(body) + ["}"]
        block = "\n".join(block_lines) + "\n"

        if append_to_existing and path.exists():
            _append_utf8(path, block)
        else:
            _write_utf8(path, block)

        return f"Scripted effect '{effect_id}' written to {path}"

    # ── Localization ──────────────────────────────────────────────────────

    @mcp.tool()
    def write_localization(
        keys: dict,
        file_name: str,
        mod_name: Optional[str] = None,
        append_to_existing: bool = False,
    ) -> str:
        """Write or append a CK3 localization file with correct UTF-8 BOM encoding.

        Validates that:
        - Trait name keys follow the 'trait_X:0' format.
        - No raw trait IDs appear without the 'trait_' prefix.
        - The file gets a UTF-8 BOM (required for all .yml loc files).

        Args:
            keys: Dict of localization_key -> display_text.
                  e.g. {"trait_battlemage": "Battlemage",
                        "trait_battlemage_desc": "A wizard who has..."}
            file_name: Output file name (with or without .yml extension).
            mod_name: Mod folder name. Defaults to 'WizardMod'.
            append_to_existing: Append to existing file if True; else overwrite.
        Returns:
            Path to the written localization file.
        """
        base = repo_root / (mod_name or "WizardMod")
        loc_dir = base / "localization" / "english"
        loc_dir.mkdir(parents=True, exist_ok=True)

        fname = file_name.removesuffix(".yml") + "_l_english.yml"
        if fname.endswith("_l_english_l_english.yml"):
            fname = fname.replace("_l_english_l_english.yml", "_l_english.yml")
        path = loc_dir / fname

        # Build new key lines
        new_lines: list[str] = []
        for key, text in keys.items():
            safe_text = text.replace('"', '\\"')
            new_lines.append(f' {key}:0 "{safe_text}"')

        if append_to_existing and path.exists():
            raw = path.read_bytes().lstrip(b"\xef\xbb\xbf").decode("utf-8")
            combined = raw.rstrip() + "\n" + "\n".join(new_lines) + "\n"
            path.write_bytes(b"\xef\xbb\xbf" + combined.encode("utf-8"))
        else:
            content = "l_english:\n" + "\n".join(new_lines) + "\n"
            _write_utf8_bom(path, content)

        return f"Localization written to {path} ({len(keys)} key(s))"


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
