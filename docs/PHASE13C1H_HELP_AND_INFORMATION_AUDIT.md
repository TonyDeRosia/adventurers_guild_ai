# Phase 13C1H Help and Information Audit

| Feature | Current implementation | Canonical source | Defect | Planned/implemented change | Tests |
|---|---|---|---|---|---|
| HELP command | `MudCommandEngine._cmd_help` provided a short hard-coded command list and command-registry lookup. | Published world help entries plus command registry and ability definitions. | Topics such as race/alignment were unavailable; no search/categories/related support. | Added `engine.help_service.HelpService`, immutable `HelpEntry`, published/draft help JSON, and HELP subcommands. | `tests/test_phase13c1h_help_information.py` |
| Command registry/routing | `CommandRegistry` resolves exact, alias, and abbreviations; unknown commands fell to a generic message. | Registry for commands; HelpService for topics. | Known topics and typos gave no useful guidance; hidden Builder commands could intercept topic phrases. | Routing now checks exact visible help topics and close command/help suggestions before generic unknown output. | `tests/test_phase13c1h_help_information.py` |
| Builder drafts/publish | Builder workspace handled many JSON draft collections, but not help entries. | `worlds/<world>/builder/help_entries.json` drafts and `worlds/<world>/help/help_entries.json` published package. | Builders had to rely on raw/nonexistent help editing. | Added `helpedit` create/show/clone/edit keyword/alias/related/validate/preview/delete/publish workflow with validation and atomic publish. | Focused manual command checks; compile checks. |
| Help files | No canonical help package existed. | World-authored JSON package. | Runtime help was not authored world content. | Added starter help content for commands, movement, look, score, worth, inventory, equipment, skills, spells, abilities, cooldowns, affects, prompt, display, race/class/alignment/attributes, six attributes, title, set camp, and build campfire. | HelpService test. |
| Ability definitions | `engine.abilities.AbilityDefinition` is canonical; grants/progression store rank and maximum_rank. | Ability registry and actor ability progression/grants. | Skill/spell list displayed detail and often implied `/100`. | HelpService generates ability fallback entries from definitions; compact lists show only name and true rank wording. | Compact ability test. |
| SKILLS/SPELLS | `build_abilities_document` rendered status, category, costs, and descriptions in list views. | AbilityDisplaySnapshotService rows. | Too verbose for list commands. | Compact default SKILLS/SPELLS/ABILITIES list with one shared help guidance footer. | Compact ability test. |
| WORTH | Command built a worth document but returned SCORE intent; theme labels could still imply status. | CharacterDisplaySnapshot currency data. | Family identity mismatch. | Added WORTH display intent and worth command intent; title is CURRENCIES. | Worth test. |
| SCORE | Score builder showed Race/Class and carrying placeholders with em dashes. | CharacterDisplaySnapshotService and available canonical fields. | Unsupported fields appeared as placeholder punctuation. | Race/class/carrying rows are omitted when unavailable; prompt config is not included. | Score test. |
| Attributes | Snapshot service already supports attributes when present on character/snapshot. | CharacterDisplaySnapshot attributes. | No direct attributes command; must not fabricate values. | Added `attributes`/`stats` command that displays canonical attributes only when present, otherwise directs to HELP ATTRIBUTES. | Compile/manual checks. |
| Color preferences | Structured displays used resolved theme color_enabled; room and prompt wrappers ignored character no_color. | Per-character preferences dict and display renderer boundary. | DISPLAY COLOR OFF did not affect LOOK/prompt. | Room and prompt render through display HTML with `color_enabled` derived from character preferences; runtime re-renders display documents with preference. | No-color renderer test. |
| TITLE | `title` routed into achievement command family, which could expose diagnostic state. | Character title text plus help topic. | Player output could include raw achievement dictionaries. | Added natural `_cmd_title` show/set behavior and kept achievements under achievement/titles. | Title test. |

## Adventurer's Lair parity notes

The reference behavior informed keyword-based help, prefix matching, access filtering, Builder editing/publishing concepts, compact practice-style skill listings, WORTH/GOLD separation, unknown-command suggestions, and no-color-at-output-boundary behavior. Smart MUD uses original Python services, dataclasses, JSON package layout, and display documents rather than copying C structures or file formats.

## Attribute foundation audit

Canonical attributes can already enter `CharacterDisplaySnapshot.attributes` from character/runtime data. This phase does not create a second stat system and does not invent Strength/Dexterity/etc. values. SCORE and `attributes` display attributes only when canonical values are present.

## Proficiency source

Actor ability grants persist `rank` and `proficiency`; actor ability progression persists `rank` and `maximum_rank`. Existing display snapshots expose rank/maximum_rank. Because no universal percentage maximum is guaranteed, compact displays show `Rank N`, or `Rank N/M` only when an explicit maximum greater than one is present.
