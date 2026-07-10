# Trainer Definitions

Phase 9A introduces `engine.training.TrainingService` as the canonical advancement-service pipeline. Trainers, offers, requirements, costs, results, availability, conversions, respec foundations, refunds, cooldowns, and messages are authored as world-package/Builder collections. Runtime mutations flow through immutable quotes, `EconomyService` for currency costs, `ProgressionService` for advancement currencies and ability/class/profession state, SQLite training tables for audit/history, and EventBus events for presentation and diagnostics.

Manual acceptance commands:

```text
trainerlist
trainerstat training_master_borik
trainingofferlist training_master_borik
trainingofferpreview learn_basic_attack_improvement self
train list
train preview learn_basic_attack_improvement
train learn_basic_attack_improvement
train confirm
practice basic_attack
training history
respec preview respec_starter_ability_rank
```

The implementation is intentionally conservative: no talent trees, unrestricted class switching, autonomous teaching, remort/prestige execution, or final balance are included.
