# CK3 Local Mod Installation

Where a built mod's files must go for Crusader Kings III to load it, and how to
install one with [`publication.py`](src/publication.py).

---

## 1. Where the game reads mods from

CK3 loads local mods from the **user data directory**, not from the game install
folder. On Windows the user data directory is:

```
<Documents>\Paradox Interactive\Crusader Kings III\
```

### ⚠️ OneDrive redirection gotcha

`<Documents>` is **not always** `C:\Users\<user>\Documents`. If OneDrive is
enabled, the Documents folder is redirected, e.g.:

```
C:\Users\<user>\OneDrive\Documents\Paradox Interactive\Crusader Kings III\
```

The plain `C:\Users\<user>\Documents\...` copy is then **ignored by the game**.
Always resolve the real Documents path from the Windows registry:

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders → "Personal"
```

`publication.py` does this automatically via `winreg`.

---

## 2. Files that must be present

For a mod named `<ModName>`, three things must exist in the user data directory:

| File / Folder | Location | Purpose |
|---|---|---|
| `mod/<ModName>/` | `.../Crusader Kings III/mod/<ModName>/` | The mod content (all `common/`, `events/`, `gfx/`, `localization/` files + `descriptor.mod`) |
| `mod/<ModName>.mod` | `.../Crusader Kings III/mod/<ModName>.mod` | Launcher descriptor. Must contain an absolute `path=` pointing to the mod folder |
| `dlc_load.json` | `.../Crusader Kings III/dlc_load.json` | The list of enabled mods. Must include `"mod/<ModName>.mod"` in `enabled_mods` |

### `.mod` / `descriptor.mod` format

Both files share the same content. The `path=` line uses **forward slashes** and
an **absolute** path:

```
version="1.0.0"
tags={
	"Gameplay"
}
name="Elder Magic"
supported_version="1.19.*"
path="C:/Users/seelc/OneDrive/Documents/Paradox Interactive/Crusader Kings III/mod/ElderMagic"
```

### `dlc_load.json` format

```json
{"enabled_mods":["mod/ugc_2962333032.mod","mod/ElderMagic.mod"],"disabled_dlcs":[]}
```

Workshop mods appear as `ugc_<id>.mod`; your local mod is added alongside them.

---

## 3. Encoding rules

- Python's `Path.write_text(..., encoding="utf-8")` is correct (no BOM).
- PowerShell `Set-Content` writes UTF-16 and **breaks** these files. If you must
  use PowerShell, write with:
  `[System.IO.File]::WriteAllText(path, text, (New-Object System.Text.UTF8Encoding($false)))`
- Localization `.yml` files require a UTF-8 BOM (opposite rule) — that is handled
  when the mod is built, not during installation.

---

## 3a. Icon (DDS) format — important

Trait/perk icons that are the wrong DDS format render in game as a **"?"
placeholder** even though the trait itself works and the filename matches. CK3
requires (per the modding docs):

| Icon type | Dimensions | Format |
|---|---|---|
| Trait icons | 120×120 | `A8R8G8B8` (uncompressed 32-bit) **with mipmaps** |
| Lifestyle perks | 120×120 | `A8R8G8B8` **with mipmaps** |
| Faith icons | 100×100 | `A8R8G8B8`, no mipmaps |

- The `icon = <name>` field in a trait resolves to
  `gfx/interface/icons/traits/<name>.dds`. The `.dds` filename (minus extension)
  must match the `icon`/`icon_name` value exactly.
- `generate_icon_image` writes this correct format automatically (uncompressed
  A8R8G8B8 + mipmaps). Do **not** re-save icons as DXT1/DXT5 — that causes the
  "?" placeholder.

---

## 4. Launching & testing

Launch CK3 **directly** from the command line — do **not** go through Steam / the
Paradox Launcher, as it regenerates `dlc_load.json` from its own playset and drops
any manually-added local mod.

```powershell
& "C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings III\binaries\ck3.exe" -debug_mode
```

- Launch `...\binaries\ck3.exe -debug_mode` **directly**. Do **not** go through
  Steam / the Paradox Launcher — it regenerates `dlc_load.json` from its own
  playset and drops any manually-added local mod.
- `-debug_mode` also force-enables the in-game console (disabled in Ironman).
- Loading an existing save loads **that save's** baked-in mod set regardless of
  the current mod list — always **start a new game** to test a mod.
- Lifestyle-category traits do not appear in the ruler designer. Verify with the
  console instead, e.g. `add_trait wizard_novice_1`.

---

## 5. Installing with `publication.py`

The mod is built into the repo's **top-level directory** (e.g. `c:\dev\ai_dev\ElderMagic`).
`publication.py` copies that folder into the CK3 `mod/` sub-directory, writes the
`.mod` descriptor, and enables it in `dlc_load.json`.

```powershell
# From the repo root, with the venv active:
python ck3_agent/src/publication.py ElderMagic
```

Optional flags:

```
--source <dir>            Override the source mod folder (default: <repo>/<ModName>)
--dest <dir>              Override the CK3 mod directory (default: auto-detected)
--version <v>             Mod version for the descriptor (default: 1.0.0)
--supported-version <v>   CK3 version the mod targets (default: 1.19.*)
--no-enable               Copy files but do not touch dlc_load.json
```


## Testing
- Can give xp with: effect add_trait_xp = { trait = lore_of_fire value = 25 }
effect set_variable = { name = wizard_fire_xp_total value = 100 }