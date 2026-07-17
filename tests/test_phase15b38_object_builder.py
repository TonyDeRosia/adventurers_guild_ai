from types import SimpleNamespace
from engine.mud_commands import MudCommandEngine


def actor():
    return SimpleNamespace(id="builder", account_id="acct", role="builder", account_role="builder", world_id="shattered_realms", room_id="guildhall_crossing_square", edit_room_id="guildhall_crossing_square", current_area_id="starter_guildlands", current_zone_id="guildhall_crossing", name="Builder")


def engine(isolated_builder_world):
    e = MudCommandEngine(); e.builder = isolated_builder_world.workspace; e.builder_service.workspace = e.builder; return e


def text(e, a, cmd):
    return e.handle_command(a, cmd).narrative


def test_object_builder_grouped_menu_validation_preview_dependencies_search_and_clone(isolated_builder_world):
    e=engine(isolated_builder_world); a=actor()
    out=text(e,a,"ocreate iron_sword")
    assert "Draft items iron_sword updated" in out
    menu=text(e,a,"oedit iron_sword")
    assert "-- Item number" in menu and "1) Keywords" in menu and "C) Values" in menu and "W) Copy object" in menu
    assert "Editor closed" in text(e,a,"quit")
    assert "cannot be negative" in text(e,a,"oset iron_sword weight -1")
    assert "updated" in text(e,a,"oset iron_sword item_type weapon")
    val=text(e,a,"ovalidate iron_sword")
    assert "warning: damage_dice Weapon has no damage dice" in val
    assert "updated" in text(e,a,"oset iron_sword damage_dice 1d8")
    preview=text(e,a,"opreview iron_sword")
    assert "LOOK OBJECT" in preview and "INVENTORY" in preview and "SHOP DISPLAY" in preview and "GROUND DISPLAY" in preview
    drafts=e.builder.load("shattered_realms")
    drafts.setdefault("rooms", {})["armory"]={"id":"armory","name":"Armory","features":{"rack":{"item_template_id":"iron_sword"}}}
    e.builder.save_drafts("shattered_realms", drafts)
    deps=text(e,a,"owhere iron_sword")
    assert "room armory" in deps
    search=text(e,a,"ofind sword")
    assert "item iron_sword" in search
    clone=text(e,a,"oclone iron_sword steel_sword")
    assert "steel_sword" in clone
    assert e.builder.load("shattered_realms")["items"]["steel_sword"]["id"] == "steel_sword"


def test_container_and_keyword_warnings(isolated_builder_world):
    e=engine(isolated_builder_world); a=actor()
    text(e,a,"ocreate oak_chest")
    text(e,a,"oset oak_chest item_type container")
    text(e,a,"oset oak_chest keywords oak,oak,chest")
    val=text(e,a,"ovalidate oak_chest")
    assert "Duplicate keywords" in val
    assert "Container has no capacity" in val
