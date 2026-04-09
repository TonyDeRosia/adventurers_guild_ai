This folder is copied into the packaged Windows app as a managed runtime bundle.

Required release contents:
- comfyui/ portable ComfyUI runtime files
- workflows/ curated workflow templates shipped with the app

Large models/checkpoints are intentionally not bundled by default.

Legal-safe packaging policy:
- Keep third-party notices in THIRD_PARTY_NOTICES.txt.
- Keep third-party licenses in runtime_bundle/licenses/.
- Do not place checkpoint/model binaries in this folder.
