"""Packaging compliance audit for commercial-safe desktop distribution.

Checks performed:
1) Confirms required license/notice files exist.
2) Fails if likely model checkpoint artifacts are present in packaged paths.
3) Warns about unexpectedly large files that may indicate accidental bundling.
"""

from __future__ import annotations

import argparse
import fnmatch
from pathlib import Path
from typing import Iterable


FORBIDDEN_MODEL_PATTERNS = (
    "*.safetensors",
    "*.ckpt",
    "*.pt",
    "*.pth",
    "*.bin",
    "*.onnx",
    "*.gguf",
    "*.ggml",
)

FORBIDDEN_MODEL_DIR_NAMES = {
    "checkpoints",
    "loras",
    "controlnet",
    "vae",
    "embeddings",
    "unet",
}


def iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (path for path in root.rglob("*") if path.is_file())


def is_forbidden_model_file(path: Path) -> bool:
    lower_name = path.name.lower()
    if any(fnmatch.fnmatch(lower_name, pattern) for pattern in FORBIDDEN_MODEL_PATTERNS):
        return True
    parts = [part.lower() for part in path.parts]
    for banned_dir in FORBIDDEN_MODEL_DIR_NAMES:
        if banned_dir in parts:
            return True
    return False


def run_audit(paths: list[Path], required_files: list[Path], max_file_size_mb: int) -> int:
    errors: list[str] = []
    warnings: list[str] = []
    scanned_files = 0

    for required in required_files:
        if not required.exists():
            errors.append(f"Missing required file: {required}")

    max_bytes = max_file_size_mb * 1024 * 1024
    for root in paths:
        if not root.exists():
            errors.append(f"Audit path does not exist: {root}")
            continue
        for file_path in iter_files(root):
            scanned_files += 1
            if is_forbidden_model_file(file_path):
                errors.append(f"Forbidden model artifact detected: {file_path}")
            try:
                size = file_path.stat().st_size
            except OSError:
                continue
            if size > max_bytes:
                warnings.append(
                    f"Large file flagged ({size / (1024 * 1024):.1f} MB): {file_path}"
                )

    print(f"[distribution-audit] scanned_files={scanned_files}")
    for warning in warnings:
        print(f"[distribution-audit][warning] {warning}")
    for error in errors:
        print(f"[distribution-audit][error] {error}")

    if errors:
        print("[distribution-audit] FAILED")
        return 1
    print("[distribution-audit] PASSED")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit packaged output for legal-safe distribution.")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="Path to audit (repeatable).",
    )
    parser.add_argument(
        "--require-file",
        action="append",
        default=[],
        help="Required file path that must exist (repeatable).",
    )
    parser.add_argument(
        "--max-file-size-mb",
        type=int,
        default=200,
        help="Warn threshold for oversized files (MB).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.path:
        print("[distribution-audit][error] no --path values provided")
        return 1
    paths = [Path(item).resolve() for item in args.path]
    required_files = [Path(item).resolve() for item in args.require_file]
    return run_audit(paths=paths, required_files=required_files, max_file_size_mb=args.max_file_size_mb)


if __name__ == "__main__":
    raise SystemExit(main())
