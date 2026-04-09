Portable ComfyUI runtime location.

Release engineering must place a full portable ComfyUI runtime in this folder before producing end-user installers.
Expected minimum structure:
- main.py
- custom_nodes/
- models/
- run_cpu.bat (or run_nvidia_gpu.bat)

This repository intentionally excludes model checkpoint files.
