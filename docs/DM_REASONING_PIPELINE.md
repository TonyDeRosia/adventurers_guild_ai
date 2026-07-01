# DM Reasoning Pipeline V2

The V2 DM pipeline in `engine/dm_pipeline.py` is the authoritative entry point for live player input submitted to `POST /api/campaign/input`.

## Stages

1. **Normalize input** into `DMInput` with raw text, IC/OOC mode, campaign id, startup state, turn count, active character, and current location.
2. **Understand intent** with deterministic DM reasoning from `engine/dm_reasoning.py`, producing `DMUnderstanding` and `ExtractedFacts`.
3. **Assess state** before narration. The pipeline computes missing required bootstrap fields, ability setup needs, and whether a normal turn is allowed.
4. **Decide branch**. OOC, startup, reflection, dialogue, clarification, and normal turns each have explicit branches.
5. **Apply state first** through runtime helpers for character sheet updates, starter inventory, world metadata, and Campaign Event proposals.
6. **Respond** only after state is updated or a follow-up is chosen.
7. **Trace routing** to `/api/debug/last-turn-routing`.

## IC vs OOC routing

- OOC input never calls the normal turn engine, never advances the turn, and answers from current campaign state or OOC tools.
- IC reflection and dialogue are non-turn branches unless the player clearly performs a world-changing action.
- Unknown IC input asks a clarification question instead of fabricating a generic action.

## Bootstrap rules

Startup states are:

- `character_creation`
- `ability_setup_followup`
- `world_setup_followup`
- `ready`

The first opening scene cannot be generated until the campaign has at least a character name and a role/class/concept. Partial data merges into the main character sheet across startup messages.

## Event and proposal rules

Specific bootstrap abilities create pending `ability_suggested` Campaign Events. They are not silently added to accepted abilities or the spellbook. Broad ability claims such as pyromancer or fire spells trigger a follow-up asking for concrete starting abilities.

## Examples

- `im dork` saves name `Dork`, keeps `startup_state=character_creation`, and asks for role/concept.
- `a pyromancer with fire spells` merges with the existing character, sets role `Pyromancer`, and asks for fire spells.
- `Firebolt, Flame Shield, Ember Step` creates pending ability suggestions and then opens the scene.
- OOC `whats going on` returns campaign status without advancing the turn.
- IC `I think about my spells` answers from state without using the normal turn engine.

## Known limitations

This first pass is heuristic and deterministic. It does not replace the model-backed narrator or Campaign Intelligence; it gates access to them so state is ready before story is generated.
