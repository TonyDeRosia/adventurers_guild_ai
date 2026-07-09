# Smart MUD Command Registry

Smart MUD owns command metadata in `engine.command_registry.CommandRegistry`. The registry is the canonical source for command names, aliases, categories, access constraints, implementation status, help text, and transport safety.

## Philosophy

Smart MUD is not a tbaMUD or CircleMUD clone. It is a modern runtime with web and telnet-safe command handling. Classic MUD coverage is still tracked deliberately so players can try familiar commands without receiving accidental `Unknown command` responses for planned systems.

## Metadata

Each command records: `command`, `aliases`, `category`, `minimum_position`, `minimum_role`, `status`, `handler`, `short_help`, `long_help`, `implemented`, `placeholder`, `future_phase`, `transport_safe`, `admin_only`, and `builder_only`.

## Categories and statuses

Categories include movement, informational, interaction, object, equipment, communication, social, character, magic, combat, group, economy, quest, clan, toggle, builder, admin, and system.

Statuses include implemented, placeholder, planned, intentionally_omitted, future_builder, future_admin, future_combat, future_magic, future_economy, and future_quest.

## Placeholders

A placeholder command is intentionally recognized and returns useful text without activating a future system. For example, mount commands explain mounts are not implemented yet, while combat commands remain tracked as future combat rather than implemented behavior.

## Commands and help

`commands` groups visible commands by registry category and hides admin/builder/future commands from normal players. `commands all` and `commands planned` may expose planned registry entries that are still safe to display. `help <command>` falls back to registry metadata when no full helpfile exists.

## Future upgrades

Future systems should upgrade a placeholder by changing its registry status and wiring its handler, preserving aliases and help text wherever possible.

## Phase 3E examination and interaction polish

Registered player commands now route through runtime-owned command handling and must execute, show registry usage, return a clean placeholder, or explicitly describe unavailable future work. The examination layer supports room, self, object, entity, direction, and room-feature targets; `identify`, `read`, and `use` publish EventBus events and return semantic output. See `docs/EXAMINATION_AND_INTERACTION.md`.
