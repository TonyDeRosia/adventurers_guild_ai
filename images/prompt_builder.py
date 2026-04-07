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
    narrator_visual_focus: str
    active_quest_titles: list[str]
    active_enemy: str
    mood_tags: list[str]


class TurnImagePromptBuilder:
    """Builds structured scene prompts for ComfyUI requests only."""

    def build(self, state: CampaignState, player_action: str, narrator_response: str = "") -> str:
        context = self._context_from_state(state, player_action, narrator_response)
        quest_line = ", ".join(context.active_quest_titles) if context.active_quest_titles else "none"
        mood_line = ", ".join(context.mood_tags) if context.mood_tags else "fantasy, adventure"
        enemy_line = context.active_enemy or "none"
        visual_focus_line = context.narrator_visual_focus or f"{context.player_name} reacting to the unfolding scene"
        return (
            f"fantasy RPG illustration, {context.world_theme}, {context.location_description}, "
            f"player {context.player_name} the {context.player_class}, action: {context.player_action}, "
            f"scene focus: {visual_focus_line}, "
            f"active quest focus: {quest_line}, threat: {enemy_line}, mood: {mood_line}, "
            "cinematic composition, dramatic lighting, high detail, concept art"
        )

    def _context_from_state(self, state: CampaignState, player_action: str, narrator_response: str) -> ImagePromptContext:
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
            narrator_visual_focus=self._summarize_visual_focus(narrator_response),
            active_quest_titles=active_quests,
            active_enemy=active_enemy,
            mood_tags=[tag for tag in mood_tags if tag],
        )

    def _summarize_visual_focus(self, narrator_response: str) -> str:
        text = " ".join(str(narrator_response or "").split()).strip()
        if not text:
            return ""
        first_sentence = text.split(".")[0]
        return first_sentence[:180].strip(" ,;")
