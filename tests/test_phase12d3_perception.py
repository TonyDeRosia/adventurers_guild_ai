from pathlib import Path

from engine.mud_displays import render_room
from engine.mud_runtime import MudRuntime


def test_phase12d3_numbered_entity_and_item_resolution(tmp_path):
    rt = MudRuntime(Path.cwd(), tmp_path)
    wolves = [
        {"entity_id":"w1","name":"Forest Wolf","keywords":["wolf","forest wolf","canine"]},
        {"entity_id":"w2","name":"Forest Wolf","keywords":["wolf","forest wolf","canine"]},
    ]
    assert rt.resolve_entity_keywords("wolf", wolves)["entity"]["entity_id"] == "w1"
    assert rt.resolve_entity_keywords("2.wolf", wolves)["entity"]["entity_id"] == "w2"
    assert rt.resolve_entity_keywords("can", wolves)["status"] == "ambiguous"
    assert rt.resolve_entity_keywords("3.wolf", wolves)["status"] == "missing_ordinal"
    items = [
        {"instance_id":"i1","name":"Iron Sword","keywords":["sword","iron sword"]},
        {"instance_id":"i2","name":"Iron Sword","keywords":["sword","iron sword"]},
    ]
    assert rt.resolve_item_keywords("2.sword", items)["item"]["instance_id"] == "i2"


def test_phase12d3_room_grouping_and_classic_exit_order():
    class Room:
        title = "Trail"
        description = "A quiet trail."
        players = [{"name":"Kraevok","entity_type":"player"}, {"name":"Mira","entity_type":"player"}]
        npcs = []
        mobs = [
            {"name":"Forest Wolf","entity_type":"mob","template_id":"wolf","keywords":["wolf"],"current_state":"standing","state":{"current_health":100,"maximum_health":100}},
            {"name":"Forest Wolf","entity_type":"mob","template_id":"wolf","keywords":["wolf"],"current_state":"standing","state":{"current_health":100,"maximum_health":100}},
            {"name":"Forest Wolf","entity_type":"mob","template_id":"wolf","keywords":["wolf"],"current_state":"standing","state":{"current_health":10,"maximum_health":100}},
        ]
        objects = []
        exits = [{"direction":"east"},{"direction":"north"},{"direction":"west","closed":True},{"direction":"south"}]
    html = render_room(Room(), character=type("C", (), {"name":"Kraevok"})())
    assert "(2) Forest Wolf" in html
    assert html.count("Mira") == 1
    assert "north" in html and "(west)" in html
    assert html.index("north") < html.index("(west)") < html.index("south") < html.index("east")
