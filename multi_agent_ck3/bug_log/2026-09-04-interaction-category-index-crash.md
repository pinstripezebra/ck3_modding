# Character interaction menu crash — `interaction_category_wizard_magic` index

**Date:** 2026-09-04
**Severity:** Hard crash (`EXCEPTION_ACCESS_VIOLATION`)
**Cost:** ~7 failed fixes across 3 days, 6+ crash cycles

## Symptom

Open a character sheet, right-click the character to open the **character
interaction menu** → instant CTD. Only for characters holding a Lore of Magic
trait. Other characters opened fine.

## Root cause

`ElderMagic/common/character_interaction_categories/wizard_magic_categories.txt`
declared:

```
interaction_category_wizard_magic = {
    index = 15
    ...
}
```

Vanilla's own `common/character_interaction_categories/00_character_interaction_categories.txt`
opens with:

```
#########################################################
#  DO NOT LEAVE GAPS IN "index" OR THE GAME WILL CRASH  #
#########################################################
```

Two rules follow from that, and the mod broke both in turn:

1. **Indices must be unique.** Vanilla occupies `0..14`. AGOT's
   `interaction_category_agot_debug` takes `15`. Elder Magic also used `15` →
   collision.
2. **Indices must be contiguous.** The first fix attempt moved it to `20`,
   which removed the collision but left holes at `16..19` → still crashed.

Correct value in an AGOT playset: **`16`**.

The category is only rendered when it contains a *shown* interaction. Every
Elder Magic interaction is gated on a lore trait, which is why only mages
crashed — the category never materialised for anyone else.

A second, genuine bug was found on the way: `study_lore_interaction` declared
`category = interaction_category_personal`, which is defined nowhere in vanilla,
AGOT, any loaded mod, or Elder Magic. That is an unresolved pointer and would
crash independently.

## Why it took seven attempts

**The log line before the crash was misleading.** Every crash report ended with:

```
[hh:mm:ss][I][character_window.cpp:1010]: Open character 'X of Y'
```

That is the *previous* user action. The right-click that actually crashed logs
nothing. This was read as "the crash is in the character window", and four fixes
were spent inside `gui/window_character.gui`:

1. `tooltipwidget` → `tooltip` in the base mod — never ran, the patch mod's copy
   shadows it in an AGOT playset.
2. Same change in the patch mod — still crashed.
3. Moved the tooltip from the `vbox` onto the inner `icon` — still crashed.
4. Deleted `window_character.gui` from both mods entirely — still crashed.

Attempt 4 was the decisive datum: with the override *gone*, the crash persisted.
That proved the GUI was innocent, but it was only reached after the user
volunteered that the trigger was the **right-click menu**, not the sheet.

Then, having correctly localised the bug to `common/character_interactions/`,
two more attempts were lost by checking category *existence* and *uniqueness*
without reading the vanilla file that documents the *contiguity* requirement.

### Also ruled out (all clean, all wasted cycles)

- Trait icon `.dds` files — all present.
- Recursion in `wizard_total_magic_power` script value — none.
- `customizable_localization` entries missing a fallback — all had one.
- `glow_alpha` animation warning at the crash timestamp — 2,417 occurrences per
  session, routine noise.
- `wizard_char_win_open` variable — set by the window, read by nothing.

## Collateral damage

Two changes were made on false suspicion and later reversed/reworked:

- `gui/window_character.gui` was deleted from both mods. It is now **generated**
  from upstream at deploy time by `tools/character_window.py` instead of being a
  hand-maintained ~5,000-line fork — a net improvement, but not what the bug
  called for.
- The magic power readout was moved to the floating badge, then to the Arcane
  Codex title bar, then back to the character sheet.

## Prevention

Automated preflight checks now run before every `playtest.ps1` deploy and abort
on failure (`multi_agent_ck3/tools/playtest.py`):

- `check_interaction_category_indices` — indices unique **and** contiguous from
  `0`, computed across vanilla + every mod in the active playset.
- `check_interaction_categories_exist` — every `category =` referenced by our
  interactions resolves to a real definition.

## Lessons

1. **The last log line is the previous action, not the crash site.** CK3 logs
   window opens but not menu opens. Treat the final log entry as an upper bound
   on when the crash happened, not as a location.
2. **Bisect before theorising.** Deleting the suspect file outright would have
   exonerated the GUI on attempt 1 instead of attempt 4. When a component is
   suspected, remove it entirely first; narrow only after the binary answer.
3. **Read the vanilla file's comments.** The answer was in a comment box at the
   top of the file being overridden. `check_ck3_file` exists precisely for this
   and was not used.
4. **A "fix" that changes the symptom's cause but not the symptom is a signal.**
   Index `15 → 20` swapped one violation for another; the unchanged symptom
   should have prompted re-reading the spec rather than moving on.
5. **Ask what the user actually clicked.** "Character menu" meant two different
   UI surfaces to the user and to the investigation. Confirming the exact
   interaction earlier would have saved four attempts.
