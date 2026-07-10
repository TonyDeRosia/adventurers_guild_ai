# Shared Feature Library

Rooms may use `feature_refs` to reference global feature definitions while retaining local embedded `features`. Resolution loads shared refs first, includes local features, dedupes by stable ID, and never converts a feature into an item instance. Portable objects should be item templates plus item placements instead.
