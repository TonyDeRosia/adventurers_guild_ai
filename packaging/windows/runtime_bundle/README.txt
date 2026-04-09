This folder is copied into the packaged Windows app as a managed runtime scaffold.

Suggested optional contents for release engineering:
- ComfyUI bootstrap files (if license/compliance allows)
- curated workflow templates
- helper scripts for first-run dependency setup

Large models/checkpoints are intentionally not bundled by default.

Legal-safe packaging policy:
- Keep third-party notices in THIRD_PARTY_NOTICES.txt.
- Keep third-party licenses in runtime_bundle/licenses/.
- Do not place checkpoint/model binaries in this folder.
