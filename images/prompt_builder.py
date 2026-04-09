"""Image prompt construction for visual generation pipeline.

Boundary notes:
- This module handles scene/state extraction + prompt composition only.
- Workflow token injection and node patching remain in images/workflow_manager.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from engine.entities import CampaignState


@dataclass
class SceneVisualContinuity:
    """Stable visual anchors reused across adjacent turns when still valid."""

    player_appearance: str = ""
    armor_clothing: str = ""
    primary_weapon: str = ""
    companions_present: list[str] = field(default_factory=list)
    active_enemy: str = ""
    location_identity: str = ""
    weather: str = ""
    lighting: str = ""
    persistent_magic_effects: list[str] = field(default_factory=list)


@dataclass
class SceneExtraction:
    """High-priority scene facts extracted before prompt assembly."""

    location_name: str
    location_description: str
    environment_type: str
    time_of_day: str
    weather: str
    lighting: str
    player_visible_appearance: str
    player_equipment: list[str]
    companions_present: list[str]
    enemies_present: list[str]
    enemy_count: int
    enemy_condition: str
    active_spell_effects: list[str]
    immediate_action: str
    action_target: str
    visible_outcome: str
    notable_props_or_landmarks: list[str]
    combat_posture_or_distance: str
    emotional_tone_visual: str
    scene_type: str
    event_summary: str
    continuity: SceneVisualContinuity


@dataclass
class ScenePromptPacket:
    """Final prompt payload consumed by the runtime image request path."""

    prompt: str
    negative_prompt: str
    extraction: SceneExtraction
    continuity_state: dict[str, Any]


class TurnImagePromptBuilder:
    """Builds compact, scene-accurate prompts for turn visuals."""

    _DEFAULT_AUTO_NEGATIVE_TERMS = [
        "extra unrelated characters",
        "wrong character count",
        "wrong creature type",
        "wrong weapons",
        "wrong armor",
        "wrong location style",
        "wrong time of day",
        "random hooded stranger",
        "unrelated cityscape",
        "futuristic technology",
        "sci-fi interface",
        "meme face",
        "cartoon exaggeration",
        "anime exaggeration",
        "deformed anatomy",
        "blurry",
        "low detail",
    ]

    def build(self, state: CampaignState, player_action: str, narrator_response: str = "") -> str:
        """Backward-compatible single-string builder used by existing call sites."""
        return self.build_packet(state, player_action=player_action, narrator_response=narrator_response).prompt

    def build_packet(
        self,
        state: CampaignState,
        *,
        player_action: str,
        narrator_response: str,
        stage: str = "after_narration",
        negative_prompt_additions: list[str] | None = None,
    ) -> ScenePromptPacket:
        """Extract scene facts and compose the final positive/negative prompts."""
        extraction, continuity_state = self._extract_scene(state, player_action=player_action, narrator_response=narrator_response)
        prompt = self._compose_positive_prompt(extraction=extraction, stage=stage)
        negative_prompt = self._compose_negative_prompt(extraction=extraction, additions=negative_prompt_additions or [])
        return ScenePromptPacket(
            prompt=prompt,
            negative_prompt=negative_prompt,
            extraction=extraction,
            continuity_state=continuity_state,
        )

    # -------- extraction layer --------
    def _extract_scene(self, state: CampaignState, *, player_action: str, narrator_response: str) -> tuple[SceneExtraction, dict[str, Any]]:
        scene_state = self._scene_state(state)
        continuity_prior = self._continuity_from_scene_state(scene_state.get("visual_continuity", {}))

        location = state.locations.get(state.current_location_id)
        location_name = self._clean(scene_state.get("location_name") or (location.name if location else "") or state.world_meta.starting_location_name)
        location_description = self._clean(scene_state.get("scene_summary") or (location.description if location else "") or state.current_location_id)
        scene_summary = self._clean(scene_state.get("scene_summary"))

        npc_names = self._collect_companions(state, scene_state)
        enemy_name = self._clean(state.active_enemy_id.replace("_", " ") if state.active_enemy_id else "")
        enemies_present = [enemy_name] if enemy_name else self._collect_enemy_mentions(scene_state)
        enemy_count = max(len(enemies_present), 1 if enemy_name else 0)
        enemy_condition = self._enemy_condition_label(state.active_enemy_hp)

        action_text = self._clean(player_action)
        action_target = self._extract_action_target(action_text, narrator_response)
        visible_outcome = self._derive_visible_outcome(narrator_response, scene_state)

        raw_visual_text = " ".join(
            part for part in [location_description, scene_summary, narrator_response, state.world_meta.premise, state.world_meta.tone] if self._clean(part)
        )
        environment_type = self._detect_environment_type(raw_visual_text)
        time_of_day = self._detect_time_of_day(raw_visual_text)
        weather = self._detect_weather(raw_visual_text)
        lighting = self._detect_lighting(raw_visual_text)

        equipment = self._collect_player_equipment(state)
        appearance = self._collect_player_appearance(state)
        active_effects = self._collect_active_effects(scene_state)
        props = self._collect_notable_props(scene_state, location_description, narrator_response)
        combat_posture = self._derive_combat_posture(action_text, narrator_response, enemy_count)
        emotional_tone = self._derive_visual_emotion(narrator_response)
        scene_type = self._classify_scene_type(action_text, narrator_response, enemy_count)

        continuity = SceneVisualContinuity(
            player_appearance=appearance or continuity_prior.player_appearance,
            armor_clothing=self._infer_armor_clothing(equipment) or continuity_prior.armor_clothing,
            primary_weapon=self._infer_primary_weapon(equipment) or continuity_prior.primary_weapon,
            companions_present=npc_names or continuity_prior.companions_present,
            active_enemy=(enemies_present[0] if enemies_present else "") or continuity_prior.active_enemy,
            location_identity=location_name or continuity_prior.location_identity,
            weather=weather or continuity_prior.weather,
            lighting=lighting or continuity_prior.lighting,
            persistent_magic_effects=active_effects or continuity_prior.persistent_magic_effects,
        )

        event_summary = self._build_event_summary(
            actor=state.player.name,
            action=action_text,
            target=action_target,
            location=location_name or location_description,
            outcome=visible_outcome,
            narrator_response=narrator_response,
        )

        extraction = SceneExtraction(
            location_name=location_name,
            location_description=location_description,
            environment_type=environment_type,
            time_of_day=time_of_day,
            weather=weather,
            lighting=lighting,
            player_visible_appearance=appearance,
            player_equipment=equipment,
            companions_present=npc_names,
            enemies_present=enemies_present,
            enemy_count=enemy_count,
            enemy_condition=enemy_condition,
            active_spell_effects=active_effects,
            immediate_action=action_text,
            action_target=action_target,
            visible_outcome=visible_outcome,
            notable_props_or_landmarks=props,
            combat_posture_or_distance=combat_posture,
            emotional_tone_visual=emotional_tone,
            scene_type=scene_type,
            event_summary=event_summary,
            continuity=continuity,
        )
        return extraction, self._serialize_continuity(continuity)

    # -------- composition layer --------
    def _compose_positive_prompt(self, *, extraction: SceneExtraction, stage: str) -> str:
        subject_and_action = extraction.event_summary or (
            f"{extraction.immediate_action} at {extraction.location_name or extraction.location_description}".strip()
        )

        participants = [
            f"protagonist {extraction.continuity.player_appearance or 'adventurer'}",
            f"companions: {', '.join(extraction.companions_present[:3])}" if extraction.companions_present else "",
            (
                f"enemies: {', '.join(extraction.enemies_present[:3])}"
                f" ({extraction.enemy_count} total, {extraction.enemy_condition})"
                if extraction.enemies_present
                else ""
            ),
        ]

        setting = ", ".join(
            part
            for part in [
                extraction.location_name,
                extraction.location_description,
                extraction.environment_type,
                extraction.time_of_day,
                extraction.weather,
                extraction.lighting,
            ]
            if part
        )

        continuity_bits = [
            extraction.continuity.armor_clothing,
            extraction.continuity.primary_weapon,
            ", ".join(extraction.continuity.persistent_magic_effects[:3]) if extraction.continuity.persistent_magic_effects else "",
        ]

        outcome_bits = [
            extraction.visible_outcome,
            extraction.combat_posture_or_distance if extraction.scene_type == "combat" else "",
            extraction.emotional_tone_visual,
        ]

        env_bits = [
            ", ".join(extraction.notable_props_or_landmarks[:3]) if extraction.notable_props_or_landmarks else "",
            f"world flavor: {self._clean(extraction.environment_type)}" if extraction.environment_type else "",
        ]

        if stage == "before_narration":
            fidelity_hint = "pre-outcome framing from current scene state"
        else:
            fidelity_hint = "turn outcome reflected"

        style_suffix = self._style_suffix_for_scene_type(extraction.scene_type)

        parts = [
            subject_and_action,
            *[part for part in participants if part],
            setting,
            *[part for part in continuity_bits if part],
            *[part for part in outcome_bits if part],
            *[part for part in env_bits if part],
            fidelity_hint,
            style_suffix,
        ]
        return self._join_prompt_parts(parts, max_parts=10)

    def _compose_negative_prompt(self, *, extraction: SceneExtraction, additions: list[str]) -> str:
        terms = list(self._DEFAULT_AUTO_NEGATIVE_TERMS)
        if extraction.scene_type == "dialogue":
            terms.extend(["battle pose", "combat blood spray", "explosion impact"])
        if extraction.scene_type == "combat":
            terms.extend(["peaceful tea party", "idle portrait only"])
        if extraction.enemy_count > 0:
            terms.append("incorrect enemy count")
        if extraction.time_of_day:
            terms.append(f"wrong {extraction.time_of_day}")
        for item in additions:
            clean = self._clean(item)
            if clean:
                terms.append(clean)
        deduped = self._dedupe_preserve_order([term.strip() for term in terms if term.strip()])
        return ", ".join(deduped)

    # -------- small helpers --------
    def _scene_state(self, state: CampaignState) -> dict[str, Any]:
        runtime_state = getattr(getattr(state, "structured_state", None), "runtime", None)
        scene_state = getattr(runtime_state, "scene_state", {}) if runtime_state else {}
        return scene_state if isinstance(scene_state, dict) else {}

    def _collect_companions(self, state: CampaignState, scene_state: dict[str, Any]) -> list[str]:
        names: list[str] = []
        for lite in scene_state.get("lightweight_npcs", []):
            if isinstance(lite, dict):
                name = self._clean(lite.get("display_name") or lite.get("name"))
                if name:
                    names.append(name)
        if not names:
            for actor in scene_state.get("scene_actors", []):
                if isinstance(actor, dict):
                    name = self._clean(actor.get("display_name") or actor.get("name"))
                    if name and name.lower() != self._clean(state.player.name).lower():
                        names.append(name)
        return self._dedupe_preserve_order(names)[:4]

    def _collect_enemy_mentions(self, scene_state: dict[str, Any]) -> list[str]:
        mentions: list[str] = []
        enemy_conditions = scene_state.get("enemy_conditions", {})
        if isinstance(enemy_conditions, dict):
            for enemy_id in enemy_conditions.keys():
                clean = self._clean(str(enemy_id).replace("_", " "))
                if clean:
                    mentions.append(clean)
        return self._dedupe_preserve_order(mentions)[:3]

    def _enemy_condition_label(self, hp: int | None) -> str:
        if hp is None:
            return "condition unknown"
        if hp >= 20:
            return "healthy"
        if hp >= 10:
            return "wounded"
        return "critical"

    def _collect_player_equipment(self, state: CampaignState) -> list[str]:
        runtime = getattr(state.structured_state, "runtime", None)
        values: list[str] = []
        if runtime and isinstance(runtime.equipment, dict):
            for item in runtime.equipment.values():
                if item:
                    values.append(self._clean(item))
        main_sheet = next((sheet for sheet in state.character_sheets if sheet.sheet_type == "main_character"), None)
        if main_sheet:
            values.extend(self._clean(item) for item in main_sheet.equipment if self._clean(item))
        return self._dedupe_preserve_order([v for v in values if v])[:5]

    def _collect_player_appearance(self, state: CampaignState) -> str:
        main_sheet = next((sheet for sheet in state.character_sheets if sheet.sheet_type == "main_character"), None)
        if main_sheet and self._clean(main_sheet.description):
            return self._truncate(self._clean(main_sheet.description), 120)
        role = self._clean(state.player.role)
        archetype = self._clean(state.player.archetype)
        tokens = [state.player.name, state.player.char_class, role, archetype]
        return self._truncate(", ".join(self._dedupe_preserve_order([self._clean(v) for v in tokens if self._clean(v)])), 120)

    def _collect_active_effects(self, scene_state: dict[str, Any]) -> list[str]:
        values = [self._clean(v) for v in scene_state.get("active_effects", []) if self._clean(v)]
        return self._dedupe_preserve_order(values)[:4]

    def _collect_notable_props(self, scene_state: dict[str, Any], location_description: str, narrator_response: str) -> list[str]:
        props: list[str] = []
        for key in ("damaged_objects", "altered_environment", "environment_consequences"):
            values = scene_state.get(key, [])
            if isinstance(values, list):
                props.extend(self._clean(v) for v in values if self._clean(v))
        if not props:
            text = f"{location_description}. {narrator_response}"
            props.extend(self._extract_phrases(text, ["gate", "altar", "bridge", "door", "torch", "throne", "statue", "pillar", "ruin"]))
        return self._dedupe_preserve_order([p for p in props if p])[:5]

    def _derive_combat_posture(self, action: str, narrator_response: str, enemy_count: int) -> str:
        text = f"{action} {narrator_response}".lower()
        if enemy_count <= 0 and not any(token in text for token in ["attack", "strike", "shoot", "slash", "cast"]):
            return ""
        if any(token in text for token in ["close", "melee", "point-blank", "grapple"]):
            return "close-quarters engagement"
        if any(token in text for token in ["distance", "across", "far", "ranged", "arrow", "bolt"]):
            return "mid-to-long range engagement"
        return "active combat stance"

    def _derive_visual_emotion(self, narration: str) -> str:
        lowered = narration.lower()
        if any(token in lowered for token in ["panic", "fear", "terrified"]):
            return "visible fear and urgency"
        if any(token in lowered for token in ["calm", "steady", "composed"]):
            return "measured, controlled tension"
        if any(token in lowered for token in ["furious", "rage", "snarl"]):
            return "aggressive hostility"
        return ""

    def _classify_scene_type(self, action: str, narration: str, enemy_count: int) -> str:
        text = f"{action} {narration}".lower()
        if enemy_count > 0 or any(token in text for token in ["attack", "strike", "parry", "slash", "cast"]):
            return "combat"
        if any(token in text for token in ["say", "ask", "reply", "talk", "negotiate", "bargain"]):
            return "dialogue"
        if any(token in text for token in ["travel", "ride", "march", "journey"]):
            return "travel"
        if any(token in text for token in ["investigate", "inspect", "search", "examine"]):
            return "investigation"
        if any(token in text for token in ["sneak", "hide", "stealth"]):
            return "stealth"
        if any(token in text for token in ["ritual", "chant", "sigil", "summon"]):
            return "ritual"
        return "exploration"

    def _build_event_summary(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        location: str,
        outcome: str,
        narrator_response: str,
    ) -> str:
        action_core = action or "holds position"
        target_core = f" targeting {target}" if target else ""
        outcome_core = outcome or self._truncate(self._clean(narrator_response), 120)
        base = f"{actor} {action_core}{target_core} in {location}".strip()
        if outcome_core:
            base = f"{base}, {outcome_core}"
        return self._truncate(base, 220)

    def _extract_action_target(self, action: str, narration: str) -> str:
        text = f"{action}. {narration}"
        target_patterns = [r"\b(?:at|toward|against|to)\s+([A-Za-z][A-Za-z '\-]{2,40})", r"\btarget(?:ing)?\s+([A-Za-z][A-Za-z '\-]{2,40})"]
        for pattern in target_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return self._clean(match.group(1))
        return ""

    def _derive_visible_outcome(self, narration: str, scene_state: dict[str, Any]) -> str:
        recent = scene_state.get("recent_consequences", [])
        if isinstance(recent, list):
            for item in recent:
                clean = self._clean(item)
                if clean:
                    return self._truncate(clean, 120)
        if scene_state.get("last_immediate_result"):
            return self._truncate(self._clean(scene_state.get("last_immediate_result")), 120)
        return self._truncate(self._clean(narration), 140)

    def _detect_environment_type(self, text: str) -> str:
        lowered = text.lower()
        mappings = {
            "chapel": "stone chapel interior",
            "temple": "temple interior",
            "forest": "forest wilderness",
            "dock": "harbor waterfront",
            "cavern": "underground cavern",
            "street": "urban street",
            "throne": "ceremonial hall",
            "ruin": "ancient ruins",
        }
        for token, label in mappings.items():
            if token in lowered:
                return label
        return "adventuring locale"

    def _detect_time_of_day(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ["dawn", "sunrise", "early morning"]):
            return "dawn"
        if any(token in lowered for token in ["noon", "midday", "afternoon"]):
            return "daytime"
        if any(token in lowered for token in ["dusk", "sunset", "twilight"]):
            return "dusk"
        if any(token in lowered for token in ["night", "moon", "midnight", "starlit"]):
            return "night"
        return ""

    def _detect_weather(self, text: str) -> str:
        lowered = text.lower()
        for token in ["rain", "storm", "fog", "snow", "wind", "mist", "clear skies"]:
            if token in lowered:
                return token
        return ""

    def _detect_lighting(self, text: str) -> str:
        lowered = text.lower()
        for token in ["torchlight", "moonlight", "sunlight", "candlelight", "witchlight", "dim light", "backlit"]:
            if token in lowered:
                return token
        return ""

    def _infer_armor_clothing(self, equipment: list[str]) -> str:
        for item in equipment:
            lowered = item.lower()
            if any(token in lowered for token in ["armor", "robe", "cloak", "mail", "plate", "leather"]):
                return item
        return ""

    def _infer_primary_weapon(self, equipment: list[str]) -> str:
        for item in equipment:
            lowered = item.lower()
            if any(token in lowered for token in ["sword", "bow", "staff", "dagger", "axe", "mace", "spear", "wand"]):
                return item
        return ""

    def _style_suffix_for_scene_type(self, scene_type: str) -> str:
        if scene_type == "combat":
            return "cinematic fantasy combat, coherent anatomy, clear attacker/defender silhouettes, impact detail, dramatic lighting"
        if scene_type == "dialogue":
            return "cinematic fantasy dialogue scene, expressive body language, coherent anatomy, detailed environment"
        if scene_type in {"ritual", "investigation", "stealth"}:
            return "cinematic fantasy scene, environmental storytelling, coherent anatomy, detailed props, moody lighting"
        return "cinematic fantasy scene, coherent anatomy, detailed environment, dramatic lighting"

    def _join_prompt_parts(self, parts: list[str], *, max_parts: int) -> str:
        clean_parts = [self._clean(part) for part in parts if self._clean(part)]
        return ", ".join(clean_parts[:max_parts])

    def _extract_phrases(self, text: str, anchors: list[str]) -> list[str]:
        lowered = text.lower()
        phrases: list[str] = []
        for anchor in anchors:
            if anchor not in lowered:
                continue
            match = re.search(rf"([^.\n]{{0,40}}\b{re.escape(anchor)}\b[^.\n]{{0,40}})", text, flags=re.IGNORECASE)
            if match:
                phrases.append(self._clean(match.group(1)))
        return phrases

    def _continuity_from_scene_state(self, raw: Any) -> SceneVisualContinuity:
        payload = raw if isinstance(raw, dict) else {}
        companions = payload.get("companions_present", [])
        effects = payload.get("persistent_magic_effects", [])
        return SceneVisualContinuity(
            player_appearance=self._clean(payload.get("player_appearance")),
            armor_clothing=self._clean(payload.get("armor_clothing")),
            primary_weapon=self._clean(payload.get("primary_weapon")),
            companions_present=[self._clean(v) for v in companions if self._clean(v)] if isinstance(companions, list) else [],
            active_enemy=self._clean(payload.get("active_enemy")),
            location_identity=self._clean(payload.get("location_identity")),
            weather=self._clean(payload.get("weather")),
            lighting=self._clean(payload.get("lighting")),
            persistent_magic_effects=[self._clean(v) for v in effects if self._clean(v)] if isinstance(effects, list) else [],
        )

    def _serialize_continuity(self, continuity: SceneVisualContinuity) -> dict[str, Any]:
        return {
            "player_appearance": continuity.player_appearance,
            "armor_clothing": continuity.armor_clothing,
            "primary_weapon": continuity.primary_weapon,
            "companions_present": continuity.companions_present,
            "active_enemy": continuity.active_enemy,
            "location_identity": continuity.location_identity,
            "weather": continuity.weather,
            "lighting": continuity.lighting,
            "persistent_magic_effects": continuity.persistent_magic_effects,
        }

    def _clean(self, value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    def _truncate(self, value: str, length: int) -> str:
        text = self._clean(value)
        if len(text) <= length:
            return text
        return text[: max(length - 3, 0)].rstrip() + "..."

    def _dedupe_preserve_order(self, values: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for item in values:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            output.append(item.strip())
        return output
