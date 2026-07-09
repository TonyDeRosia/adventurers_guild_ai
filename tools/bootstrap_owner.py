#!/usr/bin/env python3
"""Safely grant a local Smart MUD role to one account or character."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.mud_runtime import MudStateStore, VALID_ROLES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant a persisted local development role.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--account", help="Account username or account_id to update.")
    group.add_argument("--character", help="Character name or character_id to update.")
    parser.add_argument("--role", required=True, choices=sorted(VALID_ROLES), help="Role to grant.")
    parser.add_argument("--db", type=Path, default=ROOT / "user_data" / "mud_state.db", help="SQLite DB path (default: user_data/mud_state.db).")
    args = parser.parse_args()

    store = MudStateStore(args.db)
    rec = store.grant_role(role=args.role, account=args.account or "", character=args.character or "", source="cli")
    print(f"Granted {rec['role']} via {rec['source']} at {rec['timestamp']}")
    print(f"account={rec.get('account_id') or ''} character={rec.get('character_name') or rec.get('character_id') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
