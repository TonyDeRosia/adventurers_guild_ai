# PUBLISH PIPELINE

Publish creates a new immutable content generation in `builder/generations/generation-<timestamp>` and updates `builder/generations/active.json`. Runtime systems can atomically swap to the active generation pointer without editing live objects directly. Existing display-theme publish behavior remains available; BuilderService adds the canonical generation publish path for Phase 15B.14.
