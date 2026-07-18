# Phase 20A acceptance notes

The death runtime has deterministic injectable operations and a durable result.
It emits the `death.*` lifecycle events from request through completion,
including claim, attribution, cleanup, cry, corpse, item, gold, loot,
extraction/pending-respawn, duplicate, and failure events. Trigger adapters may
suppress the default cry. Transport adapters render the death-room identity
message and anonymous adjacent-room message in their native browser/Telnet
format.

NPC extraction is intentionally the final disposition stage after corpse and
transfer commits. A player is never extracted. Restart/duplicate processing
reads the ledger result rather than rerolling outcomes. Remaining Phase 20B
work is rewards, penalties, kill credit consumers, and player respawn.
