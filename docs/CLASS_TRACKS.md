# Class Tracks

Class tracks are assignable specialization foundations with requirements and grants. Phase 6E supports one active track by default and no talent trees or quests.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.
