"""Image prompt construction for visual generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from engine.entities import CampaignState


@dataclass
class ImagePromptContext:
    campaign_name: str
    world_name: str
    world_theme: str
    location_id: str
    location_description: str
    player_name: str
    player_class: str
    player_action: str
    active_quest_titles: list[str]
    active_enemy: str
    mood_tags: list[str]


class TurnImagePromptBuilder:
    """Builds structured scene prompts for ComfyUI requests only."""

    def build(self, state: CampaignState, player_action: str) -> str:
        context = self._context_from_state(state, player_action)
        quest_line = ", ".join(context.active_quest_titles) if context.active_quest_titles else "none"
        mood_line = ", ".join(context.mood_tags) if context.mood_tags else "fantasy, adventure"
        enemy_line = context.active_enemy or "none"
        return (
            f"fantasy RPG illustration, {context.world_theme}, {context.location_description}, "
            f"player {context.player_name} the {context.player_class}, action: {context.player_action}, "
            f"active quest focus: {quest_line}, threat: {enemy_line}, mood: {mood_line}, "
            "cinematic composition, dramatic lighting, high detail, concept art"
        )

    def _context_from_state(self, state: CampaignState, player_action: str) -> ImagePromptContext:
        location = state.locations.get(state.current_location_id)
        active_quests = [quest.title for quest in state.quests.values() if quest.status == "active"]
        active_enemy = ""
        if state.active_enemy_id:
            enemy = state.active_enemy_id.replace("_", " ")
            if state.active_enemy_hp is not None:
                enemy = f"{enemy} (hp {state.active_enemy_hp})"
            active_enemy = enemy
        mood_tags = [state.settings.narration_tone, state.world_meta.tone, "adventure"]
        return ImagePromptContext(
            campaign_name=state.campaign_name,
            world_name=state.world_meta.world_name,
            world_theme=state.world_meta.world_theme,
            location_id=state.current_location_id,
            location_description=(location.description if location else state.current_location_id),
            player_name=state.player.name,
            player_class=state.player.char_class,
            player_action=player_action.strip(),
            active_quest_titles=active_quests,
            active_enemy=active_enemy,
            mood_tags=[tag for tag in mood_tags if tag],
        )
