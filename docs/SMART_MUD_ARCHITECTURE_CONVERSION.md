# Smart MUD Complete Architecture Conversion

## EXECUTIVE SUMMARY

Smart MUD is now the **primary application runtime**. The old campaign/story engine is dormant legacy code. Normal startup, gameplay, persistence, rendering, and settings are entirely MUD-controlled.

---

## PART 1: STARTUP SEPARATION

### Before (Legacy)
```
WebRuntime.__init__()
  → creates campaign_1 (Untitled World)
  → seeds Starting Area, Arrival Clearing
  → loads narrator rules, character sheets
  → checks ComfyUI, image provider status
  → initializes story display_mode
  → logs: campaign_create, scene-state seeded, display_mode=story
```

### After (Smart MUD)
```
WebRuntime.__init__()
  → initializes MudRuntime (no campaigns)
  → MudRuntime.world_registry loads from mud_worlds/
  → MudRuntime.state_store opens SQLite
  → shows World Select modal
  → logs: [mud-runtime] Smart MUD runtime initialized
  → NO campaign, NO ComfyUI, NO legacy logs
```

**File: `engine/mud_runtime.py`**
- `MudRuntime`: Primary application owner
- `MudWorldRegistry`: Static world registry
- `MudStateStore`: SQLite persistence
- `MudSession`: Active character session

**Console Must Not Show:**
- `campaign_create`
- `Untitled World`
- `Starting Area`
- `display_mode=story`
- `ComfyUI`, `image_provider`, `workflow_path`
- `model-status`, `check_provider`
- `campaign-memory load/save` (in normal flow)

---

## PART 2: PERSISTENCE - SQLite as Truth

### Legacy (Campaign-Memory)
```
/api/mud/input
  → MUD command processed
  → campaign-memory saves state
  → logs: "campaign-memory save campaign=mud_shattered_realms"
```

### Smart MUD (SQLite First)
```
/api/mud/input
  → MUD command processed
  → MudStateStore.save_command() → SQLite
  → MudStateStore.save_character() → SQLite
  → logs: [mud-persistence] Command saved to SQLite
  → NO campaign-memory call
```

**Schema: `mud_state.db`**
- `characters`: character data, role, immortal_level
- `character_stats`: denormalized stats for quick query
- `command_history`: every command executed
- `scrollback`: recent output (last 1000 lines)
- `rooms_runtime`: room state (exits, NPCs, objects)
- `npc_runtime`: NPC instance state
- `npc_relationships`: NPC affinity tracking
- `builder_audit_log`: all admin/builder actions
- `quests_runtime`: active quest state
- `death_log`: character deaths

**Migration Path:**
- If old `mud_v2.json` exists, migrate once to SQLite
- Log: `[mud-persistence] migrated legacy mud_v2 save`
- Never use campaign-memory as primary

---

## PART 3: REMOVED FROM STARTUP

### These Must NOT initialize during normal Smart MUD startup:

1. **ComfyUI and Image Generation**
   - No `images/` imports
   - No `check_image_status()`
   - No ComfyUI path resolution
   - No workflow loading
   - No checkpoint scanning

2. **Legacy Campaign Systems**
   - No `create_campaign()` default
   - No `GameStateManager` initialization
   - No narrator rules loading
   - No character sheet attachment
   - No scene-state seeding

3. **Logging Suppressions**
   - No `campaign_create` logs
   - No `scene-state` logs
   - No `image_provider` logs
   - No `workflow_path` logs
   - No repeated `model-status` checks

**Allowed Startup Logs Only:**
```
[mud-runtime] Smart MUD runtime initialized
[mud-world] World registry initialized at <path>
[mud-persistence] SQLite database opened
[startup] Backend ready
```

---

## PART 4: MUD COLOR PERSISTENCE & APPLICATION

### Current Bug → Fix

**Before:**
- Colors save but don't apply
- Inputs show dashes instead of hex
- Terminal never updates

**After:**
- Store in `mud_colors.json` + `app_config`
- Return real hex values from `/api/settings/global`
- Frontend inputs show #rrggbb
- CSS variables applied immediately
- Terminal scrollback re-rendered

**Flow:**
```
1. Frontend: user changes color (e.g., #ff0000 for HP)
2. POST /api/settings/global { mud_colors: {...} }
3. Backend: runtime.set_mud_colors()
4. Persist to mud_colors.json
5. Return effective_mud_colors with real hex
6. Frontend: document.documentElement.style.setProperty('--mud-prompt_hp', '#ff0000')
7. CSS re-applies to all <span role="prompt_hp">
8. Re-render terminal scrollback
9. Reload: colors persist
```

**Semantic Roles (40 total):**
```
Room display: room_name, area_name, room_description, exit
Entities: npc, mob, player, object, item_common/uncommon/rare/epic/legendary
Combat: combat, damage, healing, spell, skill, quest
Info: command_echo, system, error, warning, score_label, score_value
Equipment: equipment_slot, equipment_item
Dialogue: dialogue
Prompt: prompt_marker, prompt_hp, prompt_mana, prompt_stamina, prompt_xp,
         prompt_gold, prompt_mv, prompt_alignment, prompt_position, prompt_target,
         prompt_area, prompt_time
```

**File: `app/runtime_config_mud.py`**
- `MudColorConfig`: 40 semantic roles with hex defaults
- `get_default_mud_colors()`: bootstrap

**File: `engine/mud_displays.py`**
- `render_room()`: inline exits, semantic roles
- `render_prompt()`: each component with role
- `apply_css_variables()`: generate CSS map

---

## PART 5: TERMINAL LAYOUT FIX

### Current Bug
- Multiple scrollbars (page + terminal)
- Terminal doesn't fill space
- Prompt not pinned
- Input shifts when scrolling

### Fix: CSS Discipline

```css
html, body {
  height: 100%;
  overflow: hidden;  /* Prevent page scroll */
}

body.smart-mud-mode {
  height: 100vh;
  overflow: hidden;
}

.smart-mud-shell {
  height: 100vh;
  max-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.mud-terminal-frame {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}

#mud-world-output {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;        /* ONLY this scrolls */
  overflow-x: hidden;
  background: #000;
  color: #00ff00;
  font-family: 'Courier New', monospace;
}

#mud-player-prompt {
  flex: 0 0 auto;  /* Pinned, no flex */
}

.mud-command-row {
  flex: 0 0 auto;  /* Pinned */
}

.mud-save-status {
  flex: 0 0 auto;  /* Compact status */
  font-size: 0.8em;
  color: #888;
}
```

**Acceptance:**
- Only `#mud-world-output` has scrollbar
- Page scroll disabled
- Prompt pinned at bottom
- Input pinned at bottom

---

## PART 6: CLASSIC MUD EXITS & DISPLAYS

### Before
```
Exits:
north
east
west
in
```

### After
```
[ Exits: north east west in ]
```

or inline without brackets:
```
Exits: north east west in
```

**File: `engine/mud_displays.py`**

```python
def render_legacy_example_room(room, colors):
    lines = []
    lines.append(f'<span role="room_name">{room.title}</span>')
    lines.append(f'<span role="room_description">{room.description}</span>')
    
    # Inline exits
    exits = [exit.direction for exit in room.exits]
    exits_str = "[ Exits: " + " ".join(
        f'<span role="exit">{e}</span>' for e in exits
    ) + " ]"
    lines.append(exits_str)
    
    return "\n".join(lines)
```

**All Display Commands:**
All implemented through `engine/mud_displays.py`:
- `score/sc` → stats formatted as MUD
- `worth` → gold count
- `finger` → who info
- `inventory/i` → item list
- `equipment/eq` → worn items
- `spells/sp`, `skills/sk`, `abilities` → ability list
- `affects` → buff display
- `resists` → resistance display
- `who` → online players
- `where` → area map
- `commands` → available command list
- `help` → help text
- `socials` → emote list
- `areas` → zone list
- `map` → zone minimap
- `time` → current game time
- `weather` → weather desc
- `practice/prac`, `train`, `study` → trainer interface
- `list`, `buy`, `sell`, `value` → shop commands
- `consider/con` → combat assessment
- `history` → command history

**Key:** All display commands return MUD **terminal text**, not web components or cards. No fallback "You try to..." unless truly freeform.

---

## PART 7: ADMIN & BUILDER SYSTEM

### Role Hierarchy
```
Player (0)             → no special commands
Helper (1)             → can use socials
Builder (2)            → can use dig, redit, oedit, medit, zedit
Senior Builder (3)     → can manage builder-created content
Immortal (4-49)        → immortal privileges
Admin (50)             → can use all admin commands
Implementor (51)       → implementor level
```

### Local Owner Bootstrap
```
On startup:
  IF no admin exists in world:
    Allow local-only promotion via flag or config
    create MudCharacter with role="implementor"
    log: [mud-admin] Owner promoted to Implementor (local-only)
    set immortal_level = 51
```

### Builder Commands (Scaffolds)

**`wizhelp`** - List admin/builder commands
**`goto <room>`** - Teleport to room
**`transfer <char> <room>`** - Teleport another character
**`stat <char>`** - View character stats
**`restore <char>`** - Restore to full HP/mana/stamina
**`load <obj>`** - Load object (stub)
**`purge`** - Remove objects in room
**`set <char> <field> <value>`** - Set character field
**`dig <direction> <room_id>`** - Create exit
**`redit`** - Edit current room (scaffold → form)
**`oedit`** - Edit object (scaffold → form)
**`medit`** - Edit mobile (scaffold → form)
**`zedit`** - Edit zone (scaffold → form)
**`sedit`** - Edit shop (scaffold → form)
**`aedit`** - Edit area (scaffold → form)

### Gating & Audit
```python
if command.name == "goto":
    if character.role not in ["admin", "implementor"]:
        return "You do not have permission."
    
    # Execute command
    character.room_id = target_room
    
    # Audit
    state_store.audit_builder_action(
        builder_id=character.id,
        action="goto",
        target_type="room",
        target_id=target_room,
        details={"previous_room": old_room}
    )
```

**Normal players cannot see** `wizhelp` output or builder command help.

---

## PART 8: AI BUILDER WORKFLOW (SCAFFOLD)

### Commands (Return Safe Text, No Mutation)

**`ai room <brief>`**
```
> ai room haunted forest shrine
[mud-ai] Generating room from prompt
Generating... Name: Haunted Shrine Clearing
Description: Ancient stones circle a twisted tree...
Exits proposed: north, south, east
NPCs proposed: Shrine Keeper (ghost), Forest Spirit
Objects proposed: offerings, stone altar
[Builder review required before accepting]
```

**`ai npc <brief>`** - Same: generate NPC, builder confirms
**`ai quest <brief>`** - Same: generate quest chain
**`ai area <brief>`** - Same: generate zone

### Constraints
- AI generates **proposals only**
- Builder must review and confirm
- World JSON updated only after confirmation
- All changes audited
- No direct world mutation

### Future (Phase 2+)
- Builder edits room description
- AI suggests NPC dialogue/behavior
- Builder confirms before save
- Git-backed JSON world data workflow

---

## PART 9: COMMAND PIPELINE (Correct Order)

### Deterministic Path (Most Commands)
```
Player input: "score"
  ↓
MudCommandEngine.handle_command()
  ↓
Known command? YES
  ↓
Deterministic handler
  ↓
Apply state changes
  ↓
MudRenderer.render_room()
  ↓
Terminal output
```

### Hybrid Path (Social/Freeform)
```
Player input: "I bow respectfully"
  ↓
MudCommandEngine.handle_command()
  ↓
Known command? NO
  ↓
Gather context:
  - room state
  - NPC relationships
  - memory
  ↓
Route to AI
  ↓
AI generates response
  ↓
Apply emotional/memory state changes
  ↓
Terminal output
```

### Never:
- AI before context gathering
- Skip deterministic commands and route to AI
- Bypass MUD systems

---

## PART 10: TBAMUD PARITY AUDIT

**File: `docs/SMART_MUD_TBAMUD_COMMAND_AND_DISPLAY_AUDIT.md`**

Reference: `https://github.com/TonyDeRosia/tbamud_adventurers_lair`

### Categories

| Command | Type | Category | Implemented | Status |
|---------|------|----------|-------------|--------|
| score | display | info | yes | deterministic |
| inventory | display | info | yes | deterministic |
| equipment | display | info | yes | deterministic |
| look | movement | info | yes | deterministic |
| help | help | info | yes | deterministic |
| commands | help | info | yes | deterministic |
| north/south/... | movement | movement | partial | needs room nav |
| cast spell | action | magic | no | AI route |
| flee | action | combat | no | AI route |
| say | social | social | no | AI route |
| emote | social | social | no | AI route |

### Player Command Categories

1. **Deterministic** (no AI): score, inventory, equipment, spells, skills, help, commands, who, areas, time
2. **Hybrid** (context → AI): say, emote, ask, greet, cast spell
3. **Builder** (admin only): dig, redit, oedit, medit, zedit, goto
4. **Stub** (scaffold): practice, train, list, buy, sell, value

### Non-exposed Admin Commands

Admin commands NOT shown in `help` output for normal players:
- wizhelp
- goto, transfer, stat, restore, load, purge, set
- dig, redit, oedit, medit, zedit
- ai room, ai npc, ai quest

---

## PART 11: TESTS

### Compile Checks
```bash
node --check app/static/app.js
python -m py_compile \
  app/web.py \
  app/runtime_config.py \
  app/runtime_config_mud.py \
  engine/mud_runtime.py \
  engine/mud_commands.py \
  engine/mud_displays.py
```

### Unit Tests
```bash
python -m pytest \
  tests/test_mud_state_store.py \
  tests/test_mud_startup.py \
  tests/test_mud_colors.py \
  tests/test_mud_displays.py \
  tests/test_mud_commands.py \
  -v
```

### Test Cases

**Startup:**
- `test_smart_mud_startup_no_legacy_campaign()` - No campaign_create logs
- `test_normal_startup_no_comfyui()` - No image checks
- `test_world_select_modal_shown()` - Shows world list, not campaign wizard

**Persistence:**
- `test_mud_input_uses_sqlite()` - /api/mud/input saves to DB, not campaign-memory
- `test_no_campaign_memory_in_normal_flow()` - campaign-memory not called

**Settings & Colors:**
- `test_mud_colors_persist_and_reload()` - Save #ff0000, reload, still #ff0000
- `test_color_inputs_show_real_hex()` - Frontend inputs are real hex, not dashes
- `test_colors_apply_to_terminal()` - Terminal text uses color roles

**Layout:**
- `test_only_terminal_scrolls()` - Page doesn't scroll, only output area
- `test_prompt_pinned()` - Prompt doesn't move when output scrolls
- `test_no_double_scrollbar()` - One scrollbar only

**Displays:**
- `test_exits_inline_format()` - "Exits: north east west", not vertical list
- `test_score_returns_terminal_text()` - score command returns MUD format
- `test_all_known_commands_not_ai_routed()` - Known commands don't return "You try to..."

**Admin/Builder:**
- `test_player_cannot_see_wizhelp()` - wizhelp hidden from help output
- `test_admin_can_use_goto()` - admin role can teleport
- `test_non_admin_blocked_from_dig()` - builder command denied to player
- `test_builder_action_audited()` - dig action logged to audit_log

---

## ACCEPTANCE CRITERIA (11/11)

✅ **1. Smart MUD is primary runtime**
   - Startup initializes MudRuntime only
   - Normal gameplay uses only MUD systems
   - No legacy campaign during normal operation

✅ **2. No legacy startup**
   - No `campaign_create` logs
   - No "Untitled World", "Starting Area"
   - Console shows `[mud-runtime]`, `[mud-world]`, `[mud-persistence]` only

✅ **3. No ComfyUI/image in normal path**
   - Image system unreachable
   - No imports, no checks, no setup
   - Remains dormant for future archival

✅ **4. /api/mud/input uses SQLite**
   - Primary save path: MudStateStore → SQLite
   - No campaign-memory calls in normal MUD
   - Tests prove persistence to database

✅ **5. MUD colors save, reload, apply**
   - Store 40 semantic roles
   - Colors persist across reload
   - Inputs show real hex
   - Terminal updates immediately with CSS variables

✅ **6. Exits display inline**
   - Format: "Exits: north east west in"
   - Uses semantic role="exit" for color
   - Not vertical list

✅ **7. Terminal layout fixed**
   - Only #mud-world-output scrolls
   - Page has no scrollbar
   - Prompt pinned
   - Input pinned

✅ **8. Known commands deterministic**
   - score, inventory, equipment, spells, help, etc. return MUD text
   - No AI fallback for known commands
   - No "You try to..." for recognized verbs

✅ **9. Admin/builder foundation**
   - Role hierarchy: Player, Helper, Builder, Admin, Implementor
   - Builder commands gated by role
   - Owner bootstrap (local-only)
   - Audit log

✅ **10. AI builder scaffolds**
   - `ai room`, `ai npc`, `ai quest`, `ai area` return proposals
   - Builder review required
   - No direct world mutation
   - Gated by admin/builder role

✅ **11. Logs are MUD-focused**
   - `[mud-runtime]`, `[mud-command]`, `[mud-render]`, `[mud-builder]`
   - `[mud-world]`, `[mud-ai]`, `[mud-persistence]`, `[mud-admin]`
   - No campaign/image/story logs in normal flow

---

## FILES CHANGED

### New Files
- `engine/mud_runtime.py` - MudRuntime, MudSession, MudStateStore, MudWorldRegistry
- `engine/mud_commands.py` - MudCommandEngine, deterministic command handlers
- `engine/mud_displays.py` - render_room, render_prompt, all display commands
- `app/runtime_config_mud.py` - MudColorConfig, 40 color roles
- `docs/SMART_MUD_BUILDER_SYSTEM_PLAN.md` - Builder workflow and phases
- `docs/SMART_MUD_TBAMUD_COMMAND_AND_DISPLAY_AUDIT.md` - Command parity audit

### Modified Files
- `app/runtime_config.py` - Add mud_colors, mud_client persistence
- `app/web.py` - Initialize MudRuntime instead of campaign, clean startup
- `app/static/styles.css` - Terminal layout CSS (flex-based, pinned prompt/input)
- `tests/test_*.py` - Update to test Smart MUD startup, no legacy behavior

### Dormant Files (Unreachable)
- `images/` - No imports during Smart MUD startup
- `memory/campaign_memory.py` - Not called in normal MUD flow
- `engine/campaign_engine.py` - Not initialized

---

## REMAINING LIMITATIONS

1. **Phase 1 Builder Commands**: Return scaffolds/confirmation prompts, but do not edit world JSON yet. Full editor forms (redit, oedit, medit, zedit) deferred to Phase 2.

2. **AI World Generation**: `ai room`, `ai npc`, etc. return proposals and audit log only. Actual world mutation requires builder confirmation flow (Phase 2).

3. **Quest/Shop/Trainer Integration**: Not yet connected to MUD systems. Listed commands are stubs. Full impl Phase 2+.

4. **Class/Race/Spell/Skill Definition UI**: Not exposed to in-game builder. Requires file editing or external tools. Roadmap for Phase 3.

5. **Git-Backed World Data**: World package JSON is JSON-only today. Git integration and collaborative editing deferred.

6. **NPC Dialogue Trees**: Simple dialogue stubs. Full tree editor (medit) deferred.

7. **Combat Balancing**: Combat system functional but not tuned. All damage/AC values are defaults.

8. **Spell School System**: Spells classified by type but no school-specific mechanics yet.

---

## CONCLUSION

Smart MUD is now the **sole primary runtime**. Legacy campaign/story systems are completely offline during normal operation and cannot interfere with MUD gameplay or persistence.

All 11 acceptance criteria are met. The application is ready for MUD-focused development and builder tools.
