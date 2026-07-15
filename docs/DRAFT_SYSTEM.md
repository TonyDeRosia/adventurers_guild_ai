# DRAFT SYSTEM

Smart MUD Builder edits drafts only. BuilderService mutates collections under `worlds/<world>/builder`, records audit entries, and pushes per-builder undo/redo snapshots before every mutation. Draft save/export remains JSON-compatible with previous BuilderWorkspace files. Draft load is generation-independent and can recover from persisted draft files after process restart.
