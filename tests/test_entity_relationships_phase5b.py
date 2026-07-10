from pathlib import Path
from engine.mud_runtime import MudRuntime

def test_relationship_table_exists(tmp_path):
    import sqlite3
    rt=MudRuntime(Path('.'), tmp_path); rt.load_world('shattered_realms')
    with sqlite3.connect(rt.state_store.db_path) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entity_relationships'").fetchone()
