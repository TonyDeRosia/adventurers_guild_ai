from pathlib import Path

from engine.mud_runtime import MudRuntime


def test_empty_async_poll_carries_new_authoritative_prompt_revision(tmp_path):
    runtime = MudRuntime(Path('.'), tmp_path)
    runtime.load_world('shattered_realms')
    character_id = runtime.create_character(
        world_id='shattered_realms', name='Prompt Mage', race_id='human', class_id='mage'
    )['character_id']
    character = runtime.state_store.load_character(character_id)
    runtime.register_live_character(character)

    initial = runtime.async_messages(character_id, after=0)
    revision = initial['prompt_revision']
    actor = runtime.abilities.actor_registry.get(character_id)
    actor.resources.mana = max(0, actor.resources.mana - 1)
    runtime.runtime_resources._sync_runtime_character(actor, reason='resource_current')

    changed = runtime.async_messages(character_id, after=initial['cursor'])
    assert changed['messages'] == []
    assert changed['prompt_revision'] > revision
    assert changed['prompt_html']

    stable = runtime.async_messages(character_id, after=changed['cursor'])
    assert stable['messages'] == []
    assert stable['prompt_revision'] == changed['prompt_revision']
