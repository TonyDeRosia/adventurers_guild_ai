"""Every shipped living NPC template remains targetable through resident occupancy."""
from pathlib import Path
from engine.mud_runtime import MudRuntime


def test_targetable_npc_templates_have_resolvable_terms(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path); rt.load_world("shattered_realms")
    cid = rt.create_character(world_id="shattered_realms", name="Catalog Mage")["character_id"]; rt.enter_world(cid)
    ch = rt.active_characters[cid]
    for template_id, template in rt.entity_templates.items():
        if template.get("entity_type", template.get("type")) not in {"npc", "mob"}: continue
        flags = set(template.get("flags") or []) | set(template.get("tags") or [])
        if flags & {"untargetable", "nonliving", "scenery", "system_only", "hidden"}: continue
        ent = rt.spawn_entity(template_id, room_id=ch.room_id)
        terms = [str(x).strip().lower() for x in ent.get("keywords", []) if str(x).strip()]
        diag = f"template={template_id} name={ent.get('name')} authored={template.get('keywords')} derived={terms}"
        assert terms, diag
        matches = rt.find_occupant(ch.room_id, terms[0], {"living": True, "visible_to": ch})["matches"]
        # The resident order is authoritative, so select this newly materialized
        # instance with its ordinal rather than relying on dictionary order.
        ordinal = next(i for i, match in enumerate(matches, 1) if match["entity_id"] == ent["entity_id"])
        assert rt.find_occupant(ch.room_id, f"{ordinal}.{terms[0]}", {"living": True, "visible_to": ch})["entity"]["entity_id"] == ent["entity_id"], diag
