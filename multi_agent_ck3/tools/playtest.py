"""Local playtest workflow for the Elder Magic mods.

Deploys the repo mods into CK3 under separate *playtest* identities (no
``remote_file_id``), so they never collide with the Steam-published copies of the
same mods, enables them on top of the launcher's active playset, and starts the
game with the launcher skipped.

Usage:
    python -m tools.playtest                 # deploy + launch + verify
    python -m tools.playtest --no-launch     # deploy only
    python -m tools.playtest --restore       # undo: restore dlc_load.json, drop playtest copies
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from tools import publication  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CK3_EXE = pathlib.Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\binaries\ck3.exe"
)
PLAYTEST_SUFFIX = "Playtest"
BACKUP_NAME = "dlc_load.playtest_backup.json"

# Source folder -> launcher display name, in load order.
MODS: list[tuple[str, str]] = [
    ("ElderMagic", "Elder Magic"),
    ("ElderMagicAgotCompPatch", "Elder Magic - AGOT Compatibility Patch"),
]


def ck3_user_dir() -> pathlib.Path:
    return publication.ck3_mod_dir().parent


def active_playset_mods(ck3_dir: pathlib.Path) -> list[str]:
    """Ordered ``mod/*.mod`` entries of the launcher's active playset.

    Falls back to the current dlc_load.json when the launcher DB is unreadable.
    """
    db = ck3_dir / "launcher-v2.sqlite"
    if db.is_file():
        tmp = pathlib.Path(os.environ.get("TEMP", ".")) / "ck3_launcher_ro.sqlite"
        try:
            shutil.copy(db, tmp)
            conn = sqlite3.connect(tmp)
            rows = conn.execute(
                """
                SELECT m.gameRegistryId
                FROM playsets_mods pm
                JOIN mods m ON m.id = pm.modId
                JOIN playsets p ON p.id = pm.playsetId
                WHERE p.isActive = 1 AND pm.enabled = 1
                ORDER BY pm.position
                """
            ).fetchall()
            conn.close()
            entries = [r[0] for r in rows if r[0]]
            if entries:
                return entries
        except sqlite3.Error:
            pass

    dlc_load = ck3_dir / "dlc_load.json"
    if dlc_load.is_file():
        return json.loads(dlc_load.read_text(encoding="utf-8")).get("enabled_mods", [])
    return []


def steam_ids_for(ck3_dir: pathlib.Path, display_names: set[str]) -> set[str]:
    """gameRegistryIds of Steam mods whose display name matches one under test.

    These must be dropped from the load order or the workshop copy shadows the
    local build.
    """
    db = ck3_dir / "launcher-v2.sqlite"
    if not db.is_file():
        return set()
    tmp = pathlib.Path(os.environ.get("TEMP", ".")) / "ck3_launcher_ro.sqlite"
    try:
        shutil.copy(db, tmp)
        conn = sqlite3.connect(tmp)
        rows = conn.execute("SELECT displayName, gameRegistryId FROM mods").fetchall()
        conn.close()
    except sqlite3.Error:
        return set()
    return {reg for name, reg in rows if reg and name in display_names}


def deploy(mod_name: str, display_name: str, version: str) -> pathlib.Path:
    playtest_name = f"{mod_name}{PLAYTEST_SUFFIX}"
    return publication.publish_mod(
        mod_name=playtest_name,
        display_name=f"{display_name} (Playtest)",
        source=REPO_ROOT / mod_name,
        version=version,
        enable=False,
    )


def source_version(mod_name: str) -> str:
    descriptor = REPO_ROOT / mod_name / "descriptor.mod"
    if descriptor.is_file():
        for line in descriptor.read_text(encoding="utf-8").splitlines():
            if line.startswith("version="):
                return line.split('"')[1]
    return "1.0.0"


def write_load_order(ck3_dir: pathlib.Path, entries: list[str]) -> None:
    dlc_load = ck3_dir / "dlc_load.json"
    backup = ck3_dir / BACKUP_NAME
    if dlc_load.is_file() and not backup.is_file():
        shutil.copy(dlc_load, backup)
        print(f"Backed up load order -> {backup.name}")

    data = {"enabled_mods": [], "disabled_dlcs": []}
    if dlc_load.is_file():
        data = json.loads(dlc_load.read_text(encoding="utf-8"))
    data["enabled_mods"] = entries
    dlc_load.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def verify_mounted(ck3_dir: pathlib.Path, folders: list[str], timeout: int = 120) -> bool:
    """Poll debug.log until every playtest folder reports as mounted."""
    debug_log = ck3_dir / "logs" / "debug.log"
    deadline = time.time() + timeout
    pending = set(folders)
    while time.time() < deadline and pending:
        time.sleep(3)
        if not debug_log.is_file():
            continue
        text = debug_log.read_text(encoding="utf-8", errors="ignore")
        for folder in list(pending):
            if f"Mounted Data: {(ck3_dir / 'mod' / folder).as_posix()}" in text:
                print(f"  mounted: {folder}")
                pending.discard(folder)
    for folder in pending:
        print(f"  NOT MOUNTED: {folder}")
    return not pending


def restore(ck3_dir: pathlib.Path) -> None:
    backup = ck3_dir / BACKUP_NAME
    dlc_load = ck3_dir / "dlc_load.json"
    if backup.is_file():
        shutil.copy(backup, dlc_load)
        backup.unlink()
        print("Restored original dlc_load.json")
    else:
        print("No playtest backup found; dlc_load.json left untouched")

    for mod_name, _ in MODS:
        playtest_name = f"{mod_name}{PLAYTEST_SUFFIX}"
        folder = ck3_dir / "mod" / playtest_name
        pointer = ck3_dir / "mod" / f"{playtest_name}.mod"
        if folder.is_dir():
            shutil.rmtree(folder)
            print(f"Removed {folder.name}")
        if pointer.is_file():
            pointer.unlink()
            print(f"Removed {pointer.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-launch", action="store_true", help="Deploy without starting CK3.")
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Restore the original load order and delete the playtest copies.",
    )
    args = parser.parse_args(argv)

    ck3_dir = ck3_user_dir()
    if args.restore:
        restore(ck3_dir)
        return 0

    display_names = {display for _, display in MODS}
    shadowing = steam_ids_for(ck3_dir, display_names)

    base = [e for e in active_playset_mods(ck3_dir) if e not in shadowing]
    playtest_entries = [f"mod/{name}{PLAYTEST_SUFFIX}.mod" for name, _ in MODS]
    base = [e for e in base if e not in playtest_entries]

    for mod_name, display_name in MODS:
        target = deploy(mod_name, display_name, source_version(mod_name))
        print(f"Deployed {mod_name} -> {target}")

    write_load_order(ck3_dir, base + playtest_entries)
    print("\nLoad order:")
    for i, entry in enumerate(base + playtest_entries):
        print(f"  {i}. {entry}")

    if args.no_launch:
        return 0

    if not CK3_EXE.is_file():
        print(f"Error: CK3 not found at {CK3_EXE}", file=sys.stderr)
        return 1

    print("\nLaunching CK3 ...")
    subprocess.Popen([str(CK3_EXE), "-skiplauncher"])
    print("Verifying mods mount (this takes a moment) ...")
    ok = verify_mounted(ck3_dir, [f"{name}{PLAYTEST_SUFFIX}" for name, _ in MODS])
    print("\nAll playtest mods mounted." if ok else "\nSome mods failed to mount, see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
