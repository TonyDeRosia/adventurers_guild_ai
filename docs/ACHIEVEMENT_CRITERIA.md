# Smart MUD Phase 9B Achievement Foundation

Phase 9B introduces one canonical `engine.achievements.AchievementService` for achievements, milestones, titles, accolades, collections, criteria progress, reward handoff, and diagnostics.

Definitions are Builder/world-package JSON collections under `worlds/<world_id>/achievement_*`, `title_definitions`, `accolade_definitions`, and `collection_*`. Runtime state is SQLite-authoritative through `actor_achievement_state`, `actor_achievement_criteria_state`, `achievement_event_consumption`, `achievement_completion_history`, `achievement_progress_history`, `actor_titles`, `actor_accolades`, `actor_collection_state`, and `achievement_reward_claims`.

Canonical EventBus events are consumed idempotently by `AchievementEventRouter`; read-only commands do not publish progress events. Achievement rewards use `RewardService` with `source_type=achievement`. Titles and accolades are cosmetic, source-traceable, and never mutate Actor statistics.

Manual acceptance commands: `achievementlist`, `achievementstat first_blood`, `achievementpreview first_blood self`, `achievementtrace self first_blood`, `achievements`, `achievement first_blood`, `titles`, `title select rat_hunter`, `score achievements`, `score titles`, and `collections`.
