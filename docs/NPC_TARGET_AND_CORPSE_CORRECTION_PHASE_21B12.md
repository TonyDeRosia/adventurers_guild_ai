# Phase 21B12: NPC target and corpse correction

## Canonical target identity

Living room occupants resolve through the resident entity contract: entity instance
ID, resident actor ID, template ID, authored display and short text, normalized
keywords/aliases, room, visibility, targetability, life state, and lifecycle ID.
The shared room resolver normalizes case, whitespace, punctuation, full names,
keywords, prefixes, and `N.keyword` ordinals in resident-presence order.

The Fox/Wolf discrepancy was metadata-path dependent: ability targeting examined
Actor names/IDs instead of the same authored keyword identity used by room
interactions.  Ability targeting now delegates to `MudRuntime.find_occupant`, so
Forest Wolf, Emberwood Fox, and templates with omitted keywords receive derived
name terms (for example `forest`, `wolf`, and `forest wolf`) consistently.

## Corpse ownership and expiry

`DeathRuntimeService` is the normal death authority; its corpse adapter calls
`MudRuntime.create_corpse`.  Creation is idempotent by death ID (or source entity
and lifecycle ID for legacy callers).  Room projections use durable entity
instance IDs, so identical corpse display text is not a deduplication key.

NPC corpse policy is `NPC_RANDOM_3_TO_5_MINUTES`.  Creation chooses one inclusive
180–300 second duration using injectable `corpse_decay_random_provider`, and
persists UTC `created_at_utc`, `decay_at_utc`, selected seconds, policy and bounds.
The scheduler compares absolute UTC expiry; its pulse cadence does not decrement
lifetime. `corpse_clock` is injectable for deterministic tests and expiry is not
rerolled on reload.

At expiry, contents move to the room once before extraction. Currency currently
uses the canonical reward/loot pipeline rather than a corpse field.

## Remaining work

Manual Browser/Telnet acceptance needs a running server observation; no manual
transcript is claimed by this code change. Combat physical severity/offhand work
remains outside this narrowly scoped phase.
