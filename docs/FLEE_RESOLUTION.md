# Flee Resolution (Phase 15B.12)

Flee is now a contested resident-runtime operation, not guaranteed movement.

Formula:

`chance_percent = 50 + (fleeing_dexterity - opponent_dexterity) * 4.0 + (fleeing_level - opponent_level) * 1.5 + situational_modifiers`

The ordinary chance is clamped to 5%-95%. Equal level and Dexterity is a 50% threshold. Dexterity is the primary stat; level is secondary.

When multiple active hostile opponents are present, Smart MUD evaluates every valid opponent in the same room and uses the opponent that yields the lowest success chance. Dead, fled, defeated, non-hostile, and out-of-room participants are ignored.

On success, flee calls `MudRuntime.move_resident_actor()` so `MudCharacter.room_id`, resident `Actor.identity.current_location`, and `resident_occupants_by_room` move atomically. On failure, no movement event is published, no destination room is rendered, and all location authorities remain unchanged.

Situational modifiers are represented in the flee trace and are bounded; rooted/no-exit cases resolve to 0% with a specific failure reason.
