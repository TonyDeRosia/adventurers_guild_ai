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

## 21B12 verification completion

The Phase 18K fixture now verifies the compact `SKILLS` contract (display name
and proficiency only) while keeping Build Campfire routing as a separate gateway
assertion.  Focused production-runtime coverage exercises Forest Wolf with short,
full, single-quoted, and double-quoted Magic Missile forms.  It also verifies
case/whitespace/full-name/token/ordinal normalization, and that a missing Bear
returns before payment, rolls, damage, wait state, or cooldown mutation.

The catalog test materializes every shipped living targetable NPC template and
uses its canonical resident term (and stable ordinal where necessary) to resolve
the exact instance.  Bare duplicate keywords retain the existing first stable
visible resident policy; ordinal counting excludes dead candidates.

Deterministic clock/random tests record the inclusive 180, 240, and 300 second
policy boundaries, prove five/30/120 second pulses do not expire a corpse, and
prove legacy tick values are clamped once to 180--300 seconds.  Absolute expired
rows are extracted rather than revived.  SQLite restart coverage verifies a
240-second expiry remains unchanged with 180 seconds remaining after a
60-second restart interval.  Duplicate death callbacks return the same corpse,
while two different death IDs retain two distinct room projection IDs.

Currency remains outside container item movement: current canonical currency is
handled by the reward/loot pipeline. Browser and Telnet semantic boundary proof
remains covered by the existing Phase 21B.5--21B.7 transport acceptance modules;
manual server transcripts are not claimed.
