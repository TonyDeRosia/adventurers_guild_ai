"""Compatibility reexports for the canonical Smart MUD world registry.

New runtime code should import from :mod:`smart_mud.world_registry`. This module
exists so legacy campaign-era imports exercise the same validation logic instead
of carrying a second implementation.
"""
from smart_mud.world_registry import (  # noqa: F401
    REQUIRED_BUILDER_DIRS,
    REQUIRED_RUNTIME_DIRS,
    REQUIRED_WORLD_DIRS,
    WORLDS_DIR,
    WorldPackage,
    WorldRegistry,
    WorldRegistryError,
    WorldValidationError,
    by_id,
)
