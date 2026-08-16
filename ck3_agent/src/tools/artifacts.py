import pathlib
from io import BytesIO
from typing import Optional

import replicate
from PIL import Image

from .icons import _save_dds

# Valid CK3 artifact rarities
_RARITIES = {"common", "masterwork", "famed", "illustrious", "legendary"}

# Common CK3 artifact inventory slot types
_SLOT_TYPES = {
    "trinket",
    "weapon",
    "armor",
    "regalia",
    "book",
    "banner",
    "court_artifact",
}


def register(mcp, output_dir: pathlib.Path):
    @mcp.tool()
    def generate_artifact(
        artifact_id: str,
        display_name: str,
        description: str,
        image_prompt: str,
        rarity: str = "legendary",
        slot_type: str = "trinket",
        modifiers: Optional[dict] = None,
        mod_name: Optional[str] = None,
        image_size: int = 240,
    ) -> str:
        """Create a complete CK3 artifact: script files, localization, and a 2D icon.

        Generates every piece needed for a working, spawnable artifact:
        - A 240x240 DDS artifact image (via Flux) at
          gfx/interface/icons/artifact/<artifact_id>.dds
        - A visuals entry (common/artifacts/visuals/) referencing the icon.
        - A template (common/artifacts/templates/) allowing equip/benefit.
        - A static modifier (common/modifiers/) applied to the wielder.
        - A creation scripted effect (common/scripted_effects/) so the artifact
          can be spawned in-game / via the debug console.
        - Localization (localization/english/) for the name and description.

        Args:
            artifact_id: Internal snake_case identifier (e.g. 'wizards_grimoire').
            display_name: Player-facing artifact name shown in game.
            description: Artifact tooltip/flavor description shown in game.
            image_prompt: Text prompt describing the artifact's appearance for the
                          2D icon (e.g. 'an ancient leather-bound spellbook with
                          glowing runes').
            rarity: Artifact rarity — common, masterwork, famed, illustrious, or
                    legendary.
            slot_type: Inventory slot type — trinket, weapon, armor, regalia,
                       book, banner, or court_artifact.
            modifiers: Dict of character modifier keys to values applied to the
                       wielder e.g. {"learning": 4, "monthly_prestige": 0.5}.
            mod_name: Mod folder name to write into. Defaults to 'mod'.
            image_size: Icon dimensions in pixels (CK3 artifact icons are 240).
        Returns:
            A report of all generated files and the console spawn command.
        """
        if rarity not in _RARITIES:
            return f"Error: rarity must be one of {sorted(_RARITIES)}"
        if slot_type not in _SLOT_TYPES:
            return f"Error: slot_type must be one of {sorted(_SLOT_TYPES)}"

        modifiers = modifiers or {}
        base = output_dir / (mod_name or "mod")

        visuals_dir = base / "common" / "artifacts" / "visuals"
        templates_dir = base / "common" / "artifacts" / "templates"
        modifiers_dir = base / "common" / "modifiers"
        effects_dir = base / "common" / "scripted_effects"
        loc_dir = base / "localization" / "english"
        icon_dir = base / "gfx" / "interface" / "icons" / "artifact"
        for d in (visuals_dir, templates_dir, modifiers_dir, effects_dir, loc_dir, icon_dir):
            d.mkdir(parents=True, exist_ok=True)

        icon_file = f"{artifact_id}.dds"

        # --- 2D artifact image (240x240 uncompressed A8R8G8B8 DDS with mipmaps) ---
        gen = max(256, (image_size // 8) * 8)
        prompt = (
            f"{image_prompt}, single medieval artifact object centered on a plain "
            "dark background, ornate detailed game item icon, painterly, no text, "
            "CK3 art style"
        )
        output = replicate.run(
            "black-forest-labs/flux-schnell",
            input={"prompt": prompt, "width": gen, "height": gen, "num_outputs": 1},
        )
        img_data = output[0].read()
        img = (
            Image.open(BytesIO(img_data))
            .convert("RGBA")
            .resize((image_size, image_size), Image.LANCZOS)
        )
        _save_dds(img, icon_dir / icon_file)

        # --- Visuals: link the 2D icon to the artifact ---
        visuals_script = (
            f"{artifact_id} = {{\n"
            f"\tdefault_type = {slot_type}\n"
            f'\ticon = "{icon_file}"\n'
            f"}}\n"
        )
        (visuals_dir / f"{artifact_id}.txt").write_text(visuals_script, encoding="utf-8")

        # --- Template: equip/benefit rules ---
        template_script = (
            f"{artifact_id}_template = {{\n"
            f"\tcan_equip = {{ always = yes }}\n"
            f"\tcan_benefit = {{ always = yes }}\n"
            f"\tcan_reforge = {{ always = yes }}\n"
            f"\tcan_repair = {{ always = yes }}\n"
            f"}}\n"
        )
        (templates_dir / f"{artifact_id}_template.txt").write_text(
            template_script, encoding="utf-8"
        )

        # --- Static modifier applied to the wielder (only if effects given) ---
        modifier_ref = ""
        if modifiers:
            mod_lines = [f"{artifact_id}_modifier = {{"]
            for key, val in modifiers.items():
                mod_lines.append(f"\t{key} = {val}")
            mod_lines.append("}")
            (modifiers_dir / f"{artifact_id}_modifier.txt").write_text(
                "\n".join(mod_lines) + "\n", encoding="utf-8"
            )
            modifier_ref = f"\t\tmodifier = {artifact_id}_modifier\n"

        # --- Creation scripted effect (spawns the artifact for the current char) ---
        effect_script = (
            f"create_{artifact_id}_effect = {{\n"
            f"\tcreate_artifact = {{\n"
            f"\t\tname = {artifact_id}_name\n"
            f"\t\tdescription = {artifact_id}_desc\n"
            f"\t\tvisuals = {artifact_id}\n"
            f"\t\ttemplate = {artifact_id}_template\n"
            f"{modifier_ref}"
            f"\t\trarity = {rarity}\n"
            f"\t\ttype = {slot_type}\n"
            f"\t\twealth = 100\n"
            f"\t\tquality = 100\n"
            f"\t}}\n"
            f"}}\n"
        )
        (effects_dir / f"create_{artifact_id}_effect.txt").write_text(
            effect_script, encoding="utf-8"
        )

        # --- Localization (name + description; UTF-8 BOM required by CK3) ---
        loc_content = (
            "\ufeffl_english:\n"
            f' {artifact_id}_name:0 "{display_name}"\n'
            f' {artifact_id}_desc:0 "{description}"\n'
        )
        (loc_dir / f"{artifact_id}_l_english.yml").write_text(
            loc_content, encoding="utf-8-sig"
        )

        return (
            f"Artifact '{artifact_id}' created:\n"
            f"  Icon:         {icon_dir / icon_file}\n"
            f"  Visuals:      {visuals_dir / (artifact_id + '.txt')}\n"
            f"  Template:     {templates_dir / (artifact_id + '_template.txt')}\n"
            + (
                f"  Modifier:     {modifiers_dir / (artifact_id + '_modifier.txt')}\n"
                if modifiers
                else ""
            )
            + f"  Effect:       {effects_dir / ('create_' + artifact_id + '_effect.txt')}\n"
            f"  Localization: {loc_dir / (artifact_id + '_l_english.yml')}\n"
            f"  Spawn (debug console): effect create_{artifact_id}_effect = yes"
        )
