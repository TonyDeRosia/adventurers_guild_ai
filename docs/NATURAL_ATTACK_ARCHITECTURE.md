# Natural Attack Architecture (Phase 15B.12)

Resident NPC actors retain template/body-profile natural weapon data before combat-stat snapshot generation. The flow is:

entity template -> resident NPC actor (`template`, `template_id`, `body_profile_id`, `combat_profile.natural_weapons`) -> `CanonicalActorProjection` -> `ActorStatInput` -> `CombatStatSnapshot.natural_weapon_profiles` -> attack selection -> combat message family.

Starter creature policy:

- Ashback Bear: claws, with authored room for bite/maul profiles.
- Dire Forest Wolf / Forest Wolf: bite/fangs.
- Emberwood Fox: bite/nip.
- Giant Wood Spider: fangs/bite.
- Wild Boar: gore/tusks.
- Emberwood Stag: gore/antlers.
- Player unarmed: fist/punch.

Nonhumanoid combat-capable NPCs must not silently fall back to humanoid fist attacks. If authored profiles are absent, the content registry may apply an explicit body/name-appropriate starter fallback and validation should report missing authored data.
