# Elder Magic — Patch Notes
**v1.3.4 — since September 18, 2026**

## Fixes
- Wardship magic-lore inheritance: fixed the actual root cause — six on_action files (including wardship) were sitting in a wrongly-named `on_actions` folder that CK3 never loads. Wards and children of a lore-holding guardian now reliably learn Lore of Magic traits over time, with a guaranteed grant of every missing lore at age 16.
- Fixed the Battle-Wary trait / Defensive Casting perk being available to characters with no Lore of Magic trait. Added a proper eligibility gate plus a self-correcting yearly check, so any character who still slips through (e.g. via world/history generation) loses the trait and perk point within a year.
- Fixed a localization bug where the Elemental Magic and Dark Magic doctrine tooltips displayed raw loc keys instead of descriptive text.
- Fixed the "Teach Lore of Magic" interaction icon showing its flame on a solid black square instead of a transparent background.
- Fixed Wandering Mages / Mage Squadron / Mage Regiment flavor text using the wrong loc key suffix (showed blank flavor text).

## Buildings
- Deleted the Wizard Tower building entirely.
- Added the Necromancer Sanctum building chain (5 levels, Ossuary Sanctum → Apex Ziggurat of the Black Sun), unlocked by the Necrotic Reanimators tradition.
- Added the Elemental Tower building chain (5 levels, Elemental Haven → Grand Citadel of the Prime Elements), unlocked by the Sorcerous Heritage tradition.
- The Sorcerous Heritage and Necrotic Reanimators traditions now explicitly state which building they unlock in their tooltip.

## New: Criminal Doctrines
- Added two new faith doctrines: **Elemental Magic** and **Dark Magic**, each with Crime / Shunned / Accepted / Virtuous tiers, mirroring the base game's Witchcraft doctrine.
- Elemental Magic starts at whatever stance a faith already holds toward Witchcraft; Dark Magic always starts as a Crime.
- New flame and skull doctrine icons.
