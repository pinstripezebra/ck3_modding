import pathlib
import zipfile
from typing import Optional


# Standard CK3 mod subdirectory layout
_MOD_SUBDIRS = [
    "common/traits",
    "common/modifiers",
    "common/decisions",
    "common/lifestyles",
    "common/lifestyle_perks",
    "common/religion/religions",
    "common/religion/holy_sites",
    "common/culture/cultures",
    "events",
    "localization/english",
    "gfx/interface/icons/traits",
    "gfx/interface/icons/faith",
]

_GITIGNORE = "*.dds\n*.png\n*.zip\n"


def register(mcp, output_dir: pathlib.Path, mods_dir: Optional[pathlib.Path] = None):
    @mcp.tool()
    def scaffold_mod(
        mod_name: str,
        mod_version: str = "1.0.0",
        supported_version: str = "1.12.*",
        output_path: Optional[str] = None,
    ) -> str:
        """Create a CK3 mod folder skeleton with descriptor.mod, required subdirs, and .gitignore.
        Args:
            mod_name: Name of the mod (e.g. 'MyMod'). Used as the folder name.
            mod_version: Mod version string (e.g. '1.0.0').
            supported_version: CK3 game version this mod supports (e.g. '1.12.*').
            output_path: Destination folder for the mod. Defaults to output_dir/<mod_name>.
        Returns:
            Absolute path to the created mod folder.
        """
        base = pathlib.Path(output_path) if output_path else (mods_dir or output_dir) / mod_name
        mod_dir = base

        for subdir in _MOD_SUBDIRS:
            (mod_dir / subdir).mkdir(parents=True, exist_ok=True)

        descriptor = (
            f'version="{mod_version}"\n'
            f'tags={{\n\t"Gameplay"\n}}\n'
            f'name="{mod_name}"\n'
            f'supported_version="{supported_version}"\n'
        )
        (mod_dir / "descriptor.mod").write_text(descriptor, encoding="utf-8")
        (mod_dir / ".gitignore").write_text(_GITIGNORE, encoding="utf-8")

        return str(mod_dir)

    @mcp.tool()
    def package_mod(
        mod_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """Zip a CK3 mod folder in the format expected by the Steam Workshop uploader.
        The zip contains descriptor.mod at the root and all mod files under <mod_name>/.
        Args:
            mod_path: Absolute path to the mod folder to package.
            output_path: Path for the output .zip file. Defaults to <mod_path>.zip.
        Returns:
            Absolute path to the generated zip file.
        """
        mod_dir = pathlib.Path(mod_path)
        if not mod_dir.is_dir():
            return f"Error: '{mod_path}' is not a directory."

        descriptor = mod_dir / "descriptor.mod"
        if not descriptor.is_file():
            return f"Error: '{mod_path}' has no descriptor.mod — run scaffold_mod first."

        zip_path = pathlib.Path(output_path) if output_path else mod_dir.parent / f"{mod_dir.name}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # descriptor.mod at zip root (required by Steam Workshop)
            zf.write(descriptor, "descriptor.mod")
            # All mod files under <mod_name>/
            for file in mod_dir.rglob("*"):
                if file.is_file():
                    zf.write(file, pathlib.Path(mod_dir.name) / file.relative_to(mod_dir))

        return str(zip_path)

    @mcp.tool()
    def deploy_mod(
        mod_name: str,
        ck3_data_dir: Optional[str] = None,
    ) -> str:
        """Copy a CK3 mod to the game's mod directory and ensure it is enabled.
        Copies files individually using shutil.copy2 to reliably overwrite OneDrive-cached files.
        Writes the .mod pointer file and updates dlc_load.json (both UTF-8, no BOM).
        Args:
            mod_name: Name of the mod folder to deploy (must exist under the repo root).
            ck3_data_dir: Absolute path to the CK3 user data directory.
                          Defaults to the OneDrive-redirected path on this machine:
                          C:/Users/seelc/OneDrive/Documents/Paradox Interactive/Crusader Kings III
        Returns:
            Summary of files copied and configuration written.
        """
        import shutil
        import json

        src_mod = (mods_dir or output_dir) / mod_name
        if not src_mod.is_dir():
            return f"Error: mod folder '{src_mod}' not found."

        ck3_dir = pathlib.Path(ck3_data_dir) if ck3_data_dir else pathlib.Path(
            r"C:\Users\seelc\OneDrive\Documents\Paradox Interactive\Crusader Kings III"
        )
        mod_install_dir = ck3_dir / "mod" / mod_name
        mod_file_path   = ck3_dir / "mod" / f"{mod_name}.mod"
        dlc_load_path   = ck3_dir / "dlc_load.json"

        # 1. Copy all mod files one-by-one (bypasses OneDrive file-lock issues)
        mod_install_dir.mkdir(parents=True, exist_ok=True)
        copied = 0
        for src_file in src_mod.rglob("*"):
            if not src_file.is_file():
                continue
            dst_file = mod_install_dir / src_file.relative_to(src_mod)
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_file), str(dst_file))
            copied += 1

        # 2. Write .mod pointer file — read descriptor for metadata, append path
        descriptor = src_mod / "descriptor.mod"
        desc_text = descriptor.read_text(encoding="utf-8").rstrip("\n") if descriptor.is_file() else ""
        mod_path_str = (ck3_dir / "mod" / mod_name).as_posix()
        mod_file_content = f'{desc_text}\npath="{mod_path_str}"\n'
        mod_file_path.write_text(mod_file_content, encoding="utf-8")  # utf-8, no BOM

        # 3. Update dlc_load.json — add mod entry if not already present
        mod_entry = f"mod/{mod_name}.mod"
        if dlc_load_path.is_file():
            try:
                dlc_data = json.loads(dlc_load_path.read_text(encoding="utf-8-sig"))
            except Exception:
                dlc_data = {}
        else:
            dlc_data = {}

        enabled = dlc_data.get("enabled_mods", [])
        if mod_entry not in enabled:
            enabled.append(mod_entry)
        dlc_data["enabled_mods"] = enabled
        dlc_data.setdefault("disabled_dlcs", [])
        dlc_load_path.write_text(json.dumps(dlc_data, indent=4), encoding="utf-8")

        return (
            f"Deployed '{mod_name}' to '{mod_install_dir}'.\n"
            f"  Files copied  : {copied}\n"
            f"  .mod file     : {mod_file_path}\n"
            f"  dlc_load.json : {dlc_load_path}\n"
            f"  enabled_mods  : {dlc_data['enabled_mods']}"
        )

    @mcp.tool()
    def check_modlist(
        ck3_data_dir: Optional[str] = None,
    ) -> str:
        """Return the list of all mods currently enabled in dlc_load.json, with
        name and path read from each .mod file.
        Args:
            ck3_data_dir: Absolute path to the CK3 user data directory.
                          Defaults to the OneDrive-redirected path on this machine.
        Returns:
            A human-readable table of enabled mods.
        """
        import json

        ck3_dir = pathlib.Path(ck3_data_dir) if ck3_data_dir else pathlib.Path(
            r"C:\Users\seelc\OneDrive\Documents\Paradox Interactive\Crusader Kings III"
        )
        dlc_load_path = ck3_dir / "dlc_load.json"

        if not dlc_load_path.is_file():
            return f"Error: dlc_load.json not found at '{dlc_load_path}'."

        try:
            dlc_data = json.loads(dlc_load_path.read_text(encoding="utf-8-sig"))
        except Exception as e:
            return f"Error reading dlc_load.json: {e}"

        enabled = dlc_data.get("enabled_mods", [])
        if not enabled:
            return "No mods are currently enabled in dlc_load.json."

        lines = [f"dlc_load.json: {dlc_load_path}", f"Enabled mods ({len(enabled)}):", ""]
        for entry in enabled:
            mod_file = ck3_dir / entry
            name = entry  # fallback
            path_val = ""
            if mod_file.is_file():
                for line in mod_file.read_text(encoding="utf-8-sig").splitlines():
                    line = line.strip()
                    if line.startswith("name="):
                        name = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("path="):
                        path_val = line.split("=", 1)[1].strip().strip('"')
            present = "✓" if (pathlib.Path(path_val).is_dir() if path_val else False) else "✗ (folder missing)"
            lines.append(f"  [{present}] {name}")
            lines.append(f"       file : {entry}")
            if path_val:
                lines.append(f"       path : {path_val}")
            lines.append("")

        return "\n".join(lines)
