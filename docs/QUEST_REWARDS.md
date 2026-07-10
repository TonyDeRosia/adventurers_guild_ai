# Quest Rewards

Phase 8A adds the canonical authored quest and narrative-state foundation. QuestService owns quest runtime state, stage state, objective state, event consumption, timers, history, and RewardService handoff. Definitions remain Builder/world-package data; runtime mutation is SQLite-authoritative.

## Boundaries

- Quests, conversations, objectives, branches, and world-state definitions are data, not scripts.
- Objective progress consumes stable canonical events idempotently.
- Rewards are requested from RewardService with `source_type=quest`; quests never mutate XP, currency, items, abilities, Actor stats, or progression directly.
- World state changes go through WorldStateService and append history.
- Conversations can call QuestService actions but never edit quest tables directly.
- Unsupported custom actions fail safely; unrestricted Python and command execution are forbidden so authored content cannot bypass canonical service ownership.

## Manual acceptance commands

Builder: `builder on`, `questlist`, `queststat cellar_rat_problem`, `stagelist cellar_rat_problem`, `objectivelist cellar_rat_problem_kill`, `conversationlist`, `questvalidate cellar_rat_problem`, `questpreview cellar_rat_problem self`.

Player: `talk tavern_keeper_jory`, `reply 1`, `accept cellar_rat_problem`, `quests`, `quest cellar_rat_problem`, kill configured rats, `turnin cellar_rat_problem`. Crafting: `accept first_craft`, `craft training_sword`, advance crafting time, `quests`. World state: `worldstateset world shattered_realms tutorial_complete true`.
