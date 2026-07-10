# Smart MUD Phase 7B Economy Foundation

Phase 7B introduces `engine.economy.EconomyService` as the canonical authority for carried currency balances, immutable ledger rows, price quotes, transactions, shop runtime state, buyback records, service payments, repair foundations, bank accounts, and currency conversion. Currency values are stored as integer minor units in SQLite; world data defines immutable profiles and runtime rows record all mutation history.

## Canonical Flow

Buyer actor/account → shop or service provider → offer definition → eligibility/availability checks → immutable quote → funds and inventory validation → SQLite transaction boundary → item/currency/service delivery → ledger entries → EventBus events → player, Builder, and Admin presentation.

Commands and future gameplay systems must call EconomyService APIs instead of directly editing character currency dictionaries, item ownership, shop stock, bank balances, service records, progression state, or Actor resources.

## World Data Collections

Implemented Builder/world collections are `currency_profiles`, `shop_definitions`, `shop_stock_profiles`, `shop_buy_policies`, `shop_sell_policies`, `pricing_profiles`, `service_definitions`, `repair_profiles`, `bank_profiles`, `shop_restock_profiles`, `economy_message_profiles`, and `economy_eligibility_profiles`. Old bundles remain valid because omitted collections load as empty.

## SQLite Runtime Tables

`actor_currency_balances`, `economy_ledger_entries`, `economy_transactions`, `economy_price_quotes`, `shop_runtime_state`, `shop_stock_entries`, `shop_buyback_entries`, `bank_accounts`, `bank_account_balances`, and `bank_transactions` are created idempotently by `init_economy_schema`.

## Atomicity and Idempotency

Transaction IDs, balance IDs, stock IDs, bank account IDs, and ledger IDs are stable hashes where practical. Completed transactions are persisted and ledger rows are append-only with idempotency indexes. Retries must reuse the canonical quote/transaction APIs so debit, credit, delivery, and stock release can be traced.

## Manual Acceptance Smoke

Currency: `currency`, `score currencies`, `currencybalance self`, `ledger self`.

Shop: go to Blacksmith Harl and run `list`, `shop info`, `value iron sword`, `buy iron sword`, `inventory`, `transactions`.

Insufficient funds: attempt a purchase without enough currency; expected no debit, no item, a clear failure, and released reservation.

Sale and buyback: `sell training sword`, `buyback`, `buyback 1`; expected sale quote, item transfer to shop, one currency credit, and buyback preserving the same item instance.

Repair: damage fixture item condition with an Admin test fixture and run `repair iron sword`; expected quote by missing condition, payment, condition restoration, ledger, and service event.

Bank: `balance`, `deposit 10 gold`, `balance`, `withdraw 5 gold`, `bank history`; expected carried and banked balances adjust without duplicated funds.

Restart: expected stock, balances, bank state, buybacks, transactions, and ledger rows persist without replaying completed delivery.

## Deferred Systems

Crafting, trainers, quest shops, auctions, player trading, mail, autonomous AI economics, dynamic supply/demand, interest, loans, taxes, gambling, premium currencies, and final balance are intentionally separate future systems.

## Phase 9A training integration

Canonical trainer and advancement interactions now route through `engine.training.TrainingService`. Builder/world-package collections include `trainer_definitions`, `training_offer_definitions`, `training_requirement_profiles`, `training_cost_profiles`, `training_result_profiles`, `trainer_availability_profiles`, `class_track_training_profiles`, `advancement_conversion_profiles`, `respec_profiles`, `training_refund_profiles`, `training_cooldown_profiles`, and `training_message_profiles`. Training uses immutable SQLite quotes and transactions, delegates money to `EconomyService`, delegates ability and advancement-currency state to `ProgressionService`, records restart-safe history, and publishes training EventBus events.
