from engine.mud_runtime import MudCharacter
from engine.mud_commands import MudCommandEngine
from engine.progression import ProgressionService
import sqlite3

class Store:
    world_id = "shattered_realms"
    campaign_id = "phase12a3"
    def __init__(self, path): self.db_path = path
    def connect(self):
        con = sqlite3.connect(self.db_path); con.row_factory = sqlite3.Row; return con
    def initialize(self):
        with self.connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS actor_progression_state(progression_state_id TEXT PRIMARY KEY,world_id TEXT,actor_type TEXT,actor_id TEXT,species_id TEXT,race_id TEXT,primary_class_id TEXT,primary_class_track_id TEXT,profession_ids_json TEXT,level INTEGER,experience INTEGER,experience_to_next INTEGER,total_experience INTEGER,practice_sessions INTEGER,training_sessions INTEGER,skill_points INTEGER,attribute_points INTEGER,talent_points_placeholder INTEGER,remort_count INTEGER,prestige_rank INTEGER,advancement_flags_json TEXT,last_level_at TEXT,created_at TEXT,updated_at,metadata_json TEXT,UNIQUE(actor_type,actor_id))""")
    def load_character(self, actor_id):
        return MudCharacter(id=actor_id, name="Kraevok", role="player", level=4, xp=12, room_id="training_yard")

def test_progression_accepts_mud_character_and_mapping(tmp_path):
    svc = ProgressionService(Store(tmp_path / "prog.sqlite3"))
    char_state = svc.initialize_actor_progression(MudCharacter(id="hero", name="Kraevok", role="player", level=3, xp=7))
    assert char_state["actor_id"] == "hero"
    assert char_state["level"] == 3
    mapping_state = svc.initialize_actor_progression("mapper", defaults={"level": 2, "experience": 5})
    assert mapping_state["level"] == 2

def test_session_and_social_commands_are_player_safe():
    engine = MudCommandEngine(event_bus=None)
    char = MudCharacter(id="hero", name="Kraevok", role="player", room_id="training_yard")
    assert "already connected" in engine.handle_command(char, "reconnect").narrative.lower()
    assert "cannot restart" in engine.handle_command(char, "restart").narrative.lower()
    hug = engine.handle_command(char, "hug")
    assert "Kraevok hugs" in hug.narrative
    assert '"' not in hug.narrative
    assert "Unknown command" not in engine.handle_command(char, "dance").narrative
