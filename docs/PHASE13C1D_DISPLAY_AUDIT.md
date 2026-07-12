# Phase 13C1D Character Display Audit

Adventurer's Lair reference behavior was reviewed at a functionality level: classic character displays use framed panels, dense aligned rows, explicit currency panels, distinct skill/spell listings, and tokenized prompts. Smart MUD now routes SCORE, WORTH, SKILLS, SPELLS, ABILITIES, COOLDOWNS, inventory/equipment prompt rendering through the structured `DisplayDocument` family where practical.

Active command aliases: `score/sc`, `worth`, `inventory/inv/i`, `equipment/eq`, `affects/aff/saff`, `skills/sk`, `spells/sp`, `abilities`, `cooldowns`. Legacy compatibility remains in `ActorScoreRenderer` for deep admin score subsections and old equipment/resistance sections.

Builder display themes are data contracts: labels, roles, safe color markup, prompt presets, section ordering, and display templates validate against whitelisted fields. Python, SQL, raw HTML, raw ANSI, method calls, attribute traversal, and arbitrary expressions are rejected.

Theme precedence: engine safety, player accessibility, player display/prompt preference, world theme, area override, authored markup, canonical default. Accessibility can neutralize colors after theme selection.
