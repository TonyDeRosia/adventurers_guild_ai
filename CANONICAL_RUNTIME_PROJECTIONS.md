# Canonical Runtime Projections

## Ownership

`Actor` in `MudRuntime.actor_registry` is the only mutable live authority for a
connected player.  The same object is also installed in
`CombatRuntime.resident_actors` and `ActorRegistry` under the same character ID;
compatibility lookups are aliases, not a second actor.  Therefore
`RuntimeResourceService`, ability execution, combat, death, and regeneration
all mutate one `Actor.resources` object.

```
SQLite character + resource-version rows --load--> resident Actor.resources
                                              ├--> AbilityRuntimeService
                                              ├--> CombatRuntimeService
                                              └--> RuntimeResourceService
resident Actor --synchronize_character_projection--> MudCharacter facade
                                              ├--> prompt / Browser / Telnet
                                              ├--> SCORE snapshot
                                              └--> REPORT room message
```

`MudCharacter` is a persistence and presentation facade.  It is synchronized
from the resident actor before every projection and after every command,
including rejected validation.  SQLite resource-version rows are a persistence
mirror and hydrate a character only before actor materialization; they never
overlay live gameplay state while producing a response.

## Cache and invalidation

The projection cache stores rendered/snapshot values only.  Resource, position,
equipment, regeneration, death, and respawn changes invalidate character
projections.  Rendering first synchronizes the facade from the actor, so an
async heartbeat or a failed command cannot return cached pre-mutation resources.
Browser and Telnet transport adapters consume the same `handle_input` view;
they only differ in HTML/ANSI formatting.

## SCORE and REPORT

SCORE is built after facade synchronization.  REPORT reads `Actor.resources`
directly, formats a classic resource sentence, returns the actor perspective,
and delivers the observer perspective through the canonical room-output queue.
It never parses a prompt.

## Historical defect

The prior entry path constructed one Actor for `CombatRuntime` and another for
`ActorRegistry`/abilities.  Those independent resource bags could diverge,
allowing a prompt facade to retain 50 mana while ability validation consulted an
actor holding 0.  Entry now shares one object and the post-command projection
barrier covers both successful and failed commands.
