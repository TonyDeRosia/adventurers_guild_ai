# Phase 21B9: real-time prompt and command parity

## Implemented behavior

The resident `Actor` remains the only mutable resource authority.  `MudRuntime`
now owns a runtime-only, per-resident-character `prompt_revision`.  The revision
is advanced at the existing authoritative dirty/mutation boundary and is returned
with both command views and `GET /api/mud/async-messages`.  Polling is read-only:
an empty message list can contain the current complete prompt and an unchanged
revision.  The browser applies only strictly newer revisions, so an out-of-order
older async response cannot overwrite a later prompt.  Entering, leaving, logging
out, and changing character reset client revision state.

The asynchronous call path is: canonical resource/combat mutation -> projection
invalidation/dirtying -> `prompt_snapshot` -> `async_messages` -> `app.js`
`renderPrompt`.  The browser never calculates resources.  Telnet continues to
use the same `prompt_snapshot` projection at its textual response boundary; it
does not emit silent regeneration-only prompt spam.

## Ability and corpse behavior

Compact SKILLS now renders only display name and right-aligned proficiency;
registry command metadata is retained for help and routing.  CAST already uses
the registry-driven quoted-token parser and longest learned spell prefix.  The
canonical target resolver now accepts ordinal visible targets such as `1.fox`.
Missing offensive targets report `Cast Magic Missile at whom?`; non-present
targets report that they are not visible, before cost dispatch.

Corpse identities remain independent canonical entities.  `create_corpse` guards
by death ID, records creation and expiry UTC timestamps, and persists the entity.
The runtime decay pulse spills contained item instances to the surrounding room,
extracts the corpse once, and sends one room-visible decay message.  Therefore
two equal visible corpse descriptions are **D: insufficient evidence** without
their death/instance IDs; they must never be deduplicated by text.

## Reference audit limitation

The requested Adventurer's Lair repository could not be cloned in this execution
environment, so exact custom C function/constant claims are intentionally not
made here.  Smart MUD's selected policy is documented above and is not presented
as a copied TBA implementation.
