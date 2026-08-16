"""Publish a locally-built CK3 mod into the game's mod directory.

Mods are built into the repo's top-level directory (e.g. ``<repo>/ElderMagic``).
This script copies that folder into the Crusader Kings III user ``mod/``
sub-directory, writes the launcher ``.mod`` descriptor, and enables the mod in
``dlc_load.json``.

See ``ck3_agent/mod_installation.md`` for the full layout and conventions.

Usage:
    python ck3_agent/src/publication.py <ModName> [options]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sys

from dotenv import dotenv_values

import gui_quality

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
ENV_PATH = REPO_ROOT / ".env"
CK3_USER_SUBPATH = pathlib.Path("Paradox Interactive") / "Crusader Kings III"


def configured_output_location() -> pathlib.Path | None:
    """Return OUTPUT_LOCATION from the repo .env when configured."""
    if not ENV_PATH.is_file():
        return None

    raw = dotenv_values(ENV_PATH).get("OUTPUT_LOCATION")
    if not raw:
        return None

    return pathlib.Path(os.path.expandvars(str(raw))).expanduser()


def documents_dir() -> pathlib.Path:
    """Return the user's Documents folder, honoring OneDrive redirection.

    On Windows the Documents folder can be redirected (e.g. to OneDrive). The
    real location is recorded in the registry; using it avoids installing the
    mod into a folder the game ignores.
    """
    if sys.platform.startswith("win"):
        try:
            import winreg

            key = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
                raw, _ = winreg.QueryValueEx(handle, "Personal")
            return pathlib.Path(os.path.expandvars(raw))
        except OSError:
            pass
    return pathlib.Path.home() / "Documents"


def ck3_mod_dir() -> pathlib.Path:
    """Return the CK3 user ``mod/`` directory."""
    configured = configured_output_location()
    if configured is not None:
        return configured
    return documents_dir() / CK3_USER_SUBPATH / "mod"


def build_descriptor(
    mod_name: str,
    mod_folder: pathlib.Path,
    version: str,
    supported_version: str,
) -> str:
    """Build the ``.mod`` / ``descriptor.mod`` contents with an absolute path."""
    return (
        f'version="{version}"\n'
        f"tags={{\n\t\"Gameplay\"\n}}\n"
        f'name="{mod_name}"\n'
        f'supported_version="{supported_version}"\n'
        f'path="{mod_folder.as_posix()}"\n'
    )


def enable_in_dlc_load(ck3_dir: pathlib.Path, mod_name: str) -> None:
    """Add ``mod/<mod_name>.mod`` to all ``dlc_load*.json`` variants.

    The launcher can use profile-specific files such as ``dlc_load-<profile>.json``.
    Keeping all variants in sync avoids publishing to a file the game is not reading.
    """
    entry = f"mod/{mod_name}.mod"
    dlc_paths = list(ck3_dir.glob("dlc_load*.json"))
    if not dlc_paths:
        dlc_paths = [ck3_dir / "dlc_load.json"]

    for dlc_path in dlc_paths:
        data = {"enabled_mods": [], "disabled_dlcs": []}
        if dlc_path.is_file():
            try:
                data = json.loads(dlc_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        mods = data.setdefault("enabled_mods", [])
        if entry not in mods:
            mods.append(entry)

        # UTF-8 without BOM; compact form matches what the launcher writes.
        dlc_path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def strip_script_boms(mod_folder: pathlib.Path) -> int:
    """Remove UTF-8 BOM from CK3 script (.txt) files.

    CK3 script files must be UTF-8 **without** BOM.  VS Code (and some other
    editors) silently add a BOM on save, which causes the game to misread the
    first token (e.g. ``namespace`` becomes ``﻿namespace``), breaking every
    event in the file.  Localization ``.yml`` files are the *one* exception —
    they are required to have a BOM and are left untouched here.
    """
    BOM = b"\xef\xbb\xbf"
    count = 0
    for path in mod_folder.rglob("*.txt"):
        raw = path.read_bytes()
        if raw.startswith(BOM):
            path.write_bytes(raw[3:])
            count += 1
    return count


def publish_mod(
    mod_name: str,
    source: pathlib.Path | None = None,
    dest_root: pathlib.Path | None = None,
    version: str = "1.0.0",
    supported_version: str = "1.19.*",
    enable: bool = True,
) -> pathlib.Path:
    """Copy a mod folder into the CK3 mod directory and register it.

    Args:
        mod_name: Name of the mod / folder (e.g. ``"ElderMagic"``).
        source: Source mod folder. Defaults to ``<repo>/<mod_name>``.
        dest_root: CK3 ``mod/`` directory. Defaults to OUTPUT_LOCATION from
               ``.env`` when set, otherwise the auto-detected location.
        version: Mod version for the descriptor.
        supported_version: CK3 game version the mod targets.
        enable: When True, add the mod to ``dlc_load.json``.

    Returns:
        The absolute path to the installed mod folder.
    """
    source = pathlib.Path(source) if source else REPO_ROOT / mod_name
    if not source.is_dir():
        raise FileNotFoundError(f"Source mod folder not found: {source}")

    mod_root = pathlib.Path(dest_root) if dest_root else ck3_mod_dir()
    mod_root.mkdir(parents=True, exist_ok=True)

    target = mod_root / mod_name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    stripped = strip_script_boms(target)
    if stripped:
        print(f"Stripped UTF-8 BOM from {stripped} script file(s).")

    descriptor = build_descriptor(mod_name, target, version, supported_version)
    (target / "descriptor.mod").write_text(descriptor, encoding="utf-8")
    (mod_root / f"{mod_name}.mod").write_text(descriptor, encoding="utf-8")

    if enable:
        enable_in_dlc_load(mod_root.parent, mod_name)

    findings = gui_quality.lint_mod_gui(target)
    if findings:
        print("GUI lint warnings:")
        shown = 0
        max_lines = 30
        for file_name, issues in findings.items():
            print(f"- {file_name}")
            for issue in issues:
                print(f"  * {issue}")
                shown += 1
                if shown >= max_lines:
                    print("  * ...additional warnings omitted...")
                    return target

    return target


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a locally-built CK3 mod into the game's mod directory."
    )
    parser.add_argument("mod_name", help="Name of the mod folder to publish.")
    parser.add_argument(
        "--source",
        help="Override the source mod folder (default: <repo>/<mod_name>).",
    )
    parser.add_argument(
        "--dest",
        help="Override the CK3 mod directory (default: OUTPUT_LOCATION from .env, else auto-detected).",
    )
    parser.add_argument("--version", default="1.0.0", help="Mod version.")
    parser.add_argument(
        "--supported-version",
        default="1.19.*",
        help="CK3 game version the mod targets.",
    )
    parser.add_argument(
        "--no-enable",
        action="store_true",
        help="Copy files but do not modify dlc_load.json.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        target = publish_mod(
            mod_name=args.mod_name,
            source=pathlib.Path(args.source) if args.source else None,
            dest_root=pathlib.Path(args.dest) if args.dest else None,
            version=args.version,
            supported_version=args.supported_version,
            enable=not args.no_enable,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Installed '{args.mod_name}' -> {target}")
    if not args.no_enable:
        print(f"Enabled in {target.parent.parent / 'dlc_load.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
