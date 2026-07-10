# Organization System (Phase 8B)

Phase 8B adds one canonical `OrganizationService` for parties, groups, guilds, clans, NPC organizations, and future social structures. Organization runtime state is SQLite-authoritative and stores instances, memberships, invitations, applications, audit events, subgroups, messages, relationships, shared quest offers, and group combat participation. Party, guild, and clan behavior is metadata over one organization architecture rather than separate engines.

Organizations never directly mutate combat state, quest progress, rewards, currency, inventory, progression, movement, or world state. They provide context and must call canonical services such as CombatEngine, QuestService, RewardService, and WorldStateService.

## Manual acceptance commands

Party: `party create`, `party invite <second player>`, `party accept`, `party members`.

Combat: party members enter the same room and attack a configured rat; group combat participation should record damage/healing/support and preserve the membership snapshot.

Quest sharing: `quest share cellar_rat_problem`; the recipient accepts the shared offer, then both individual quest instances can receive same-room kill credit.

Guild: an Admin-created guild can run `guild invite <player>`, `guild accept`, `guild members`, and `guild promote <player> guild_officer`.

NPC organization: `orgstat town_guard` and `orgmembers town_guard` should show idempotent static organization membership.
