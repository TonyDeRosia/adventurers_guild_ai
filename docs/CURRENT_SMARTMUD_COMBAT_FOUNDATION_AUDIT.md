# Current Smart MUD combat foundation audit

## Findings

1. The historic zero-formula warmup came from `CombatWarmupService` reading
   only `<world>/rules/combat.json`; this repository did not author that file.
2. Formula content was therefore undiscovered **and absent**, not a valid
   optional-empty profile.
3. Startup continued and reported `ready` when the count was zero.  Phase 19A
   changes this to a canonical default and an `unavailable` state on validation
   failure.
4. `kill`/`attack` route through `MudCommandEngine` to
   `CombatRuntimeService.start_player_attack`, which creates/join participants,
   sets opponents, and executes one opening attack.
5. Existing runtime resolution updates resident `Actor.resources.health` and
   persists through `persist_actor`; Phase 19A additionally provides the
   explicit single-mutation `DamageService` contract for physical resolution.
6. Players and NPCs have different durable records but runtime actor adapters
   project both into `Actor`; player and entity IDs are distinct.
7. Resident actors are cached, so stale projections were a risk at the adapter
   boundary; the new service requires persistence of the same mutated actor,
   rather than a second combat HP store.
8. The repository has runtime resident actors plus compatibility encounter SQL
   records; Phase 19A does not add another actor store.
9. The warmup ready status was the material success-without-state placeholder.
