# BUILDER ORGANIZATION COMMANDS

See [Organization System](ORGANIZATION_SYSTEM.md). Phase 8B implements this area through the canonical `engine.organizations.OrganizationService`, data collections under `worlds/<world_id>/organization_*`, SQLite runtime tables, audit events, and data-driven roles/permissions. The implementation is intentionally foundational: faction warfare, guild perks, banks, loot rolling, alliances, elections, kingdoms, and autonomous AI organization control remain non-goals.
