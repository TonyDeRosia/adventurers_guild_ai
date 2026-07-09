# Smart MUD Semantic Rendering

Smart MUD web output is rendered with semantic roles instead of hardcoded colors. The backend emits HTML spans such as `<span role="room_name">Guildhall Crossing</span>` for web clients, while telnet/plain clients receive stripped plain text or ANSI text and never receive HTML spans.

## Canonical role list

`room_name`, `area_name`, `room_description`, `exit`, `npc`, `mob`, `player`, `object`, `item_common`, `item_uncommon`, `item_rare`, `item_epic`, `item_legendary`, `command_echo`, `system`, `error`, `warning`, `success`, `combat`, `damage`, `healing`, `spell`, `skill`, `quest`, `score_label`, `score_value`, `equipment_slot`, `equipment_item`, `gold`, `hp`, `mp`, `stamina`, `dialogue`, `prompt`, `input`, `prompt_marker`, `prompt_hp`, `prompt_mana`, `prompt_stamina`, `prompt_xp`, and `prompt_gold`.

The Python canonical source is `MudColorConfig` in `app/runtime_config_mud.py`. The frontend mirrors this list in `MUD_COLOR_ROLES` in `app/static/app.js`.

## Settings API shape

`GET /api/settings/global` returns:

```json
{
  "settings": {
    "mud_colors": {
      "selected_preset": "Dark Fantasy",
      "custom_roles": {"room_name": "#ff00ff"},
      "effective_roles": {"room_name": "#ff00ff", "exit": "#00ff00"}
    },
    "mud_color_presets": {
      "Dark Fantasy": {"room_name": "#ffff00"}
    },
    "smart_mud_settings": {
      "mud_colors": {},
      "mud_client": {}
    }
  }
}
```

`selected_preset` is the active preset. `custom_roles` contains only user overrides. `effective_roles` is the preset resolved with custom overrides. Blank, null, dash, and empty custom values mean “inherit from preset” and do not override preset colors.

## CSS variable contract

Each role maps to `--mud-color-<role-with-dashes>`, for example `--mud-color-room-name`, `--mud-color-score-label`, and `--mud-color-prompt-hp`. `app/static/app.js` applies these variables to the document and terminal roots from `mud_colors.effective_roles`. `app/static/styles.css` consumes them with role selectors such as `span[role="room_name"]` and compatible `.mud-room-name` classes.

## Web semantic span contract

Backend web HTML should wrap role-specific text with `<span role="role_name">...</span>`. The frontend preserves those spans when appending command output and adds compatibility classes for existing styling. Backend command strings should not hardcode final colors and should not contain ANSI escapes for web output.

## Telnet/plain boundary

Telnet and plain transports convert semantic HTML/tags to plain or ANSI output. HTML spans, CSS variables, and web-only classes must not leak into telnet output.

## Phase 2F classic MUD room layout

Smart MUD room rendering is presentation-only and is assembled by the shared MUD display pipeline before web or telnet transport conversion. The canonical room block is:

1. Room title, using `room_name`.
2. One blank line.
3. Room description paragraph(s), using `room_description`, preserving paragraph spacing.
4. One blank line.
5. Visible players, one per line, using `player`.
6. Visible NPCs, one per line, using `npc` or disposition-specific NPC roles where available.
7. Visible mobs, one per line, using `mob`.
8. Visible objects, one per line, using `object` or item rarity roles; optional object descriptions are indented on following lines.
9. One blank line.
10. A single final exits line: `[ Exits: north east south west ]`, with each exit direction using `exit`.

Normal player room renders must not expose internal room ids. The pinned web prompt remains outside the room output and continues to use prompt roles such as `prompt`, `prompt_hp`, `prompt_mana`, `prompt_stamina`, and `prompt_marker`.
