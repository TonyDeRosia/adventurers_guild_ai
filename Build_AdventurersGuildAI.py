#!/usr/bin/env python3
"""GUI build launcher for Adventurers Guild AI Windows packaging."""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog
import webbrowser


class BuildLauncherApp:
    EXE_PATH = Path("dist") / "AdventurerGuildAI" / "AdventurerGuildAI.exe"
    INSTALLER_PATH = Path("installer") / "Output" / "AdventurerGuildAI_Setup.exe"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Adventurers Guild AI Build Launcher")
        self.root.geometry("1020x760")
        self.root.minsize(860, 560)

        self.repo_root = Path(__file__).resolve().parent
        self.exe_script = self._resolve_script_path("Build_AdventurersGuildAI.bat", "tools/build_exe.bat")
        self.installer_script = self._resolve_script_path("tools/build_installer.bat")

        self.output_dir_var = tk.StringVar(value=str((self.repo_root / "release").resolve()))
        self.status_var = tk.StringVar(value="Ready.")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.prereq_status_vars: dict[str, tk.StringVar] = {}
        self.step_status_vars: dict[str, tk.StringVar] = {}
        self._needs_installer_assets_for_prereq = False

        logs_dir = self.repo_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.persistent_log_path = logs_dir / f"build_launcher_{ts}.log"

        self._build_ui()
        self._append_log(f"Adventurers Guild AI Build Launcher started at { _dt.datetime.now().isoformat(timespec='seconds') }")
        self._append_log(f"Repository root: {self.repo_root}")
        self._append_log(f"Persistent log: {self.persistent_log_path}")
        self._set_status("Ready.", "#1e3a8a")
        self._refresh_prerequisites(log_output=True)
        self._set_step_state("prereq", "ready")
        self.root.after(100, self._drain_log_queue)

    def _resolve_script_path(self, *relative_candidates: str) -> Path:
        for relative in relative_candidates:
            candidate = self.repo_root / relative
            if candidate.exists():
                return candidate
        return self.repo_root / relative_candidates[0]

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, padx=12, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Output folder:", anchor="w").grid(row=0, column=0, sticky="w")
        self.output_entry = tk.Entry(top, textvariable=self.output_dir_var, state="readonly", width=95)
        self.output_entry.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(4, 0))

        self.choose_button = tk.Button(top, text="Choose output folder", command=self.choose_output_folder, width=22)
        self.choose_button.grid(row=0, column=4, sticky="e")

        prereq_frame = tk.LabelFrame(self.root, text="Step 1: Prerequisite readiness", padx=10, pady=8)
        prereq_frame.pack(fill="x", padx=12)
        self._add_prereq_row(prereq_frame, "python", "Python 3.10+")
        self._add_prereq_row(prereq_frame, "pyinstaller", "PyInstaller")
        self._add_prereq_row(prereq_frame, "inno", "Inno Setup 6 (for installer builds)")
        self._add_prereq_row(prereq_frame, "packaging", "Required packaging files/folders")
        self.recheck_button = tk.Button(prereq_frame, text="Recheck prerequisites", command=lambda: self._refresh_prerequisites(log_output=True))
        self.recheck_button.grid(row=4, column=0, sticky="w", pady=(8, 0))

        flow_frame = tk.LabelFrame(self.root, text="Guided build flow", padx=10, pady=8)
        flow_frame.pack(fill="x", padx=12, pady=(10, 0))
        self._add_step_row(flow_frame, "prereq", "Step 1", "Prerequisite checks")
        self._add_step_row(flow_frame, "exe", "Step 2", "Build EXE")
        self._add_step_row(flow_frame, "installer", "Step 3", "Build installer")
        self._add_step_row(flow_frame, "copy", "Step 4", "Copy final artifact(s) to output folder")

        action_bar = tk.Frame(self.root, padx=12, pady=10)
        action_bar.pack(fill="x")

        self.build_exe_button = tk.Button(action_bar, text="Build EXE", width=17, command=lambda: self.start_build("exe"))
        self.build_exe_button.pack(side="left", padx=(0, 8))

        self.build_installer_button = tk.Button(
            action_bar,
            text="Build Installer",
            width=17,
            command=lambda: self.start_build("installer"),
        )
        self.build_installer_button.pack(side="left", padx=(0, 8))

        self.build_all_button = tk.Button(
            action_bar,
            text="Build Everything",
            width=17,
            command=lambda: self.start_build("all"),
        )
        self.build_all_button.pack(side="left", padx=(0, 8))

        self.open_output_button = tk.Button(
            action_bar,
            text="Open output folder",
            width=18,
            command=self.open_output_folder,
            state="disabled",
        )
        self.open_output_button.pack(side="left", padx=(0, 8))

        self.close_button = tk.Button(action_bar, text="Close", width=10, command=self.root.destroy)
        self.close_button.pack(side="right")

        status_frame = tk.LabelFrame(self.root, text="Status", padx=10, pady=8)
        status_frame.pack(fill="x", padx=12)
        self.status_label = tk.Label(status_frame, textvariable=self.status_var, anchor="w", fg="#1e3a8a")
        self.status_label.pack(fill="x")

        log_frame = tk.LabelFrame(self.root, text="Build Log", padx=8, pady=8)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(10, 12))

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap="word", state="disabled", height=24)
        self.log_text.pack(fill="both", expand=True)

    def _add_prereq_row(self, parent: tk.Misc, key: str, title: str) -> None:
        row = len(self.prereq_status_vars)
        tk.Label(parent, text=title, anchor="w").grid(row=row, column=0, sticky="w")
        self.prereq_status_vars[key] = tk.StringVar(value="Checking...")
        label = tk.Label(parent, textvariable=self.prereq_status_vars[key], anchor="w")
        label.grid(row=row, column=1, sticky="w", padx=(12, 0))

    def _add_step_row(self, parent: tk.Misc, key: str, step_label: str, title: str) -> None:
        row = len(self.step_status_vars)
        tk.Label(parent, text=f"{step_label}: {title}", anchor="w").grid(row=row, column=0, sticky="w")
        self.step_status_vars[key] = tk.StringVar(value="Pending")
        tk.Label(parent, textvariable=self.step_status_vars[key], anchor="w").grid(row=row, column=1, sticky="w", padx=(12, 0))

    def choose_output_folder(self) -> None:
        initial = self.output_dir_var.get() or str(self.repo_root)
        try:
            chosen = filedialog.askdirectory(title="Choose output folder", initialdir=initial, mustexist=False)
        except Exception as exc:  # pragma: no cover - platform dependent fallback
            self._append_log(f"Folder picker failed: {exc}")
            chosen = simpledialog.askstring("Output folder", "Folder picker failed. Enter output folder path:") or ""

        if chosen:
            target = Path(chosen).expanduser()
            self.output_dir_var.set(str(target))
            self._append_log(f"Output folder set to: {target}")

    def start_build(self, mode: str) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Build in progress", "A build is already running.")
            return

        output_dir = Path(self.output_dir_var.get()).expanduser()
        if not output_dir:
            messagebox.showerror("Missing output folder", "Please choose an output folder before building.")
            return

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._set_status(f"Error creating output folder: {exc}", "#991b1b")
            self._append_log(f"ERROR: Could not create output folder {output_dir}: {exc}")
            return

        if not self._ensure_prerequisites(mode):
            self._set_status("Build cancelled. Prerequisites are not ready.", "#991b1b")
            return

        for step in ("exe", "installer", "copy"):
            self._set_step_state(step, "pending")
        self._enable_build_controls(False)
        self.open_output_button.config(state="disabled")
        mode_label = {"exe": "EXE", "installer": "Installer", "all": "Everything"}[mode]
        self._set_status(f"Building {mode_label}...", "#92400e")
        self._append_log("=" * 72)
        self._append_log(f"Build requested: {mode_label}")
        self._append_log(f"Output folder: {output_dir}")

        self.worker = threading.Thread(target=self._run_build, args=(mode, output_dir), daemon=True)
        self.worker.start()

    def _run_build(self, mode: str, output_dir: Path) -> None:
        ok = True
        artifacts_to_copy: list[Path] = []

        try:
            self.log_queue.put("__STEP|exe|IN_PROGRESS")
            if mode in {"exe", "all"}:
                ok = self._run_script(self.exe_script)
                if ok and (self.repo_root / self.EXE_PATH).exists():
                    artifacts_to_copy.append(self.repo_root / self.EXE_PATH)
                elif ok:
                    self._append_log("WARNING: Expected executable not found after EXE build.")
            self.log_queue.put(f"__STEP|exe|{'DONE' if ok else 'ERROR'}")

            if mode == "exe":
                self.log_queue.put("__STEP|installer|SKIPPED")
            elif ok:
                self.log_queue.put("__STEP|installer|IN_PROGRESS")
            if ok and mode in {"installer", "all"}:
                ok = self._run_script(self.installer_script)
                installer_path = self.repo_root / self.INSTALLER_PATH
                if ok and installer_path.exists():
                    artifacts_to_copy.append(installer_path)
                elif ok:
                    self._append_log("WARNING: Installer script completed but expected installer was not found.")
            if mode in {"installer", "all"}:
                self.log_queue.put(f"__STEP|installer|{'DONE' if ok else 'ERROR'}")

            if ok:
                self.log_queue.put("__STEP|copy|IN_PROGRESS")
                copied_artifacts: list[Path] = []
                for artifact in artifacts_to_copy:
                    copied = self._copy_artifact(artifact, output_dir)
                    copied_artifacts.append(copied)
                self.log_queue.put("__STEP|copy|DONE")
                if copied_artifacts:
                    self._append_log("Copied final artifacts:")
                    for copied in copied_artifacts:
                        self._append_log(f"  - {copied}")
                summary = f"Build completed successfully. Artifacts copied to: {output_dir}"
                self.log_queue.put(f"__STATUS_OK__{summary}")
                self.log_queue.put("__ENABLE_OPEN__")
            else:
                self.log_queue.put("__STEP|copy|ERROR")
                self.log_queue.put("__STATUS_ERR__Build failed. Review log details above.")
        except Exception as exc:  # pragma: no cover - guard rail for GUI apps
            self._append_log(f"ERROR: Unexpected launcher exception: {exc}")
            self.log_queue.put("__STATUS_ERR__Build failed due to unexpected launcher error.")
        finally:
            self.log_queue.put("__BUILD_DONE__")

    def _run_script(self, script_path: Path) -> bool:
        if not script_path.exists():
            self._append_log(f"ERROR: Build script not found: {script_path}")
            return False

        self._append_log(f"Running script: {script_path.relative_to(self.repo_root)}")

        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        process = subprocess.Popen(
            ["cmd", "/c", str(script_path)],
            cwd=self.repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )

        assert process.stdout is not None
        for line in process.stdout:
            self._append_log(line.rstrip())

        rc = process.wait()
        if rc == 0:
            self._append_log(f"Script finished successfully: {script_path.name}")
            return True

        self._append_log(f"ERROR: Script failed ({rc}): {script_path.name}")
        return False

    def _copy_artifact(self, artifact: Path, output_dir: Path) -> Path:
        destination = output_dir / artifact.name
        shutil.copy2(artifact, destination)
        self._append_log(f"Copied artifact: {artifact} -> {destination}")
        return destination

    def _has_inno_setup(self) -> bool:
        candidates = [
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
        ]
        for candidate in candidates:
            if str(candidate) and candidate.exists():
                self._append_log(f"Detected Inno Setup at: {candidate}")
                return True

        discovered = shutil.which("iscc")
        if discovered:
            self._append_log(f"Detected Inno Setup in PATH: {discovered}")
            return True

        return False

    def _get_python_cmd(self) -> str | None:
        for candidate in ("py -3", "python"):
            try:
                completed = subprocess.run(
                    candidate.split(),
                    cwd=self.repo_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=8,
                )
            except (OSError, subprocess.SubprocessError):
                continue

            output = (completed.stdout or "").strip().lower()
            if completed.returncode == 0 and "python 3." in output:
                return candidate
        return None

    def _has_pyinstaller(self, python_cmd: str | None) -> bool:
        if not python_cmd:
            return False
        try:
            completed = subprocess.run(
                python_cmd.split() + ["-m", "PyInstaller", "--version"],
                cwd=self.repo_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    def _has_packaging_assets(self, *, include_installer_assets: bool = False) -> tuple[bool, list[str]]:
        required_paths = [
            Path("packaging/windows/AdventurerGuildAI.spec"),
            Path("packaging/windows/runtime_bundle/comfyui/README.txt"),
            Path("packaging/windows/runtime_bundle/workflows/scene_image.json"),
            Path("packaging/windows/runtime_bundle/THIRD_PARTY_NOTICES.txt"),
            Path("packaging/windows/runtime_bundle/licenses/ComfyUI-LICENSE-MIT.txt"),
        ]
        if include_installer_assets:
            required_paths.append(Path("installer/AdventurerGuildAI.iss"))
        missing = [str(path) for path in required_paths if not (self.repo_root / path).exists()]
        return not missing, missing

    def _refresh_prerequisites(self, log_output: bool = False, *, include_installer_assets: bool = False) -> dict[str, object]:
        python_cmd = self._get_python_cmd()
        pyinstaller_ok = self._has_pyinstaller(python_cmd)
        inno_ok = self._has_inno_setup()
        packaging_ok, missing_packaging = self._has_packaging_assets(
            include_installer_assets=include_installer_assets,
        )

        prereqs = {
            "python_ok": python_cmd is not None,
            "python_cmd": python_cmd,
            "pyinstaller_ok": pyinstaller_ok,
            "inno_ok": inno_ok,
            "packaging_ok": packaging_ok,
            "missing_packaging": missing_packaging,
        }

        self.prereq_status_vars["python"].set(f"✅ Ready ({python_cmd})" if python_cmd else "❌ Missing")
        self.prereq_status_vars["pyinstaller"].set("✅ Ready" if pyinstaller_ok else "❌ Missing")
        self.prereq_status_vars["inno"].set("✅ Ready" if inno_ok else "❌ Missing")
        self.prereq_status_vars["packaging"].set("✅ Ready" if packaging_ok else "❌ Missing files")

        if log_output:
            self._append_log("Prerequisite check complete:")
            self._append_log(f"  Python: {'ready' if prereqs['python_ok'] else 'missing'}")
            self._append_log(f"  PyInstaller: {'ready' if pyinstaller_ok else 'missing'}")
            self._append_log(f"  Inno Setup: {'ready' if inno_ok else 'missing'}")
            self._append_log(f"  Packaging files/folders: {'ready' if packaging_ok else 'missing'}")
            if missing_packaging:
                self._append_log("  Missing packaging paths:")
                for item in missing_packaging:
                    self._append_log(f"    - {item}")
        return prereqs

    def _ensure_prerequisites(self, mode: str) -> bool:
        self._set_step_state("prereq", "in_progress")
        needs_inno = mode in {"installer", "all"}
        self._needs_installer_assets_for_prereq = needs_inno
        prereqs = self._refresh_prerequisites(log_output=True, include_installer_assets=needs_inno)
        missing: list[tuple[str, str, str | None]] = []

        if not prereqs["python_ok"]:
            missing.append(("Python 3.10+", "https://www.python.org/downloads/windows/", None))
        if not prereqs["pyinstaller_ok"]:
            missing.append(("PyInstaller", "https://pyinstaller.org/en/stable/installation.html", None))
        if needs_inno and not prereqs["inno_ok"]:
            missing.append(("Inno Setup 6", "https://jrsoftware.org/isinfo.php", None))
        if not self.exe_script.exists():
            missing.append(("Build EXE script", "", str(self.exe_script.relative_to(self.repo_root))))
        if mode in {"installer", "all"} and not self.installer_script.exists():
            missing.append(("Build installer script", "", str(self.installer_script.relative_to(self.repo_root))))
        if not prereqs["packaging_ok"]:
            missing.append(("Required packaging files/folders", "", "\n".join(prereqs["missing_packaging"])))

        for name, url, details in missing:
            if not self._guide_missing_prerequisite(name, url, details):
                self._set_step_state("prereq", "error")
                return False

        self._set_step_state("prereq", "done")
        return True

    def _guide_missing_prerequisite(self, name: str, download_url: str, details: str | None) -> bool:
        while True:
            detail_message = f"\n\nMissing details:\n{details}" if details else ""
            action = messagebox.askyesnocancel(
                "Missing prerequisite",
                (
                    f"{name} is still missing.{detail_message}\n\n"
                    "Yes = Open setup/download page.\n"
                    "No = Recheck now.\n"
                    "Cancel = Stop build."
                ),
            )
            if action is None:
                self._append_log(f"Build cancelled by user while resolving prerequisite: {name}")
                return False
            if action:
                if download_url:
                    webbrowser.open(download_url)
                    self._append_log(f"Opened prerequisite page for {name}: {download_url}")
                else:
                    self._append_log(f"No download page for {name}. Recheck after restoring missing files.")
                continue

            prereqs = self._refresh_prerequisites(
                log_output=True,
                include_installer_assets=self._needs_installer_assets_for_prereq,
            )
            if name.startswith("Python") and prereqs["python_ok"]:
                return True
            if name == "PyInstaller" and prereqs["pyinstaller_ok"]:
                return True
            if name.startswith("Inno") and prereqs["inno_ok"]:
                return True
            if name.startswith("Build EXE script") and self.exe_script.exists():
                return True
            if name.startswith("Build installer script") and self.installer_script.exists():
                return True
            if name.startswith("Required packaging") and prereqs["packaging_ok"]:
                return True

    def open_output_folder(self) -> None:
        output_dir = Path(self.output_dir_var.get()).expanduser()
        if not output_dir.exists():
            messagebox.showerror("Missing folder", f"Output folder does not exist:\n{output_dir}")
            return

        try:
            if os.name == "nt":
                os.startfile(str(output_dir))  # type: ignore[attr-defined]
            elif os.name == "posix":
                subprocess.Popen(["xdg-open", str(output_dir)])
            else:
                subprocess.Popen(["open", str(output_dir)])
        except Exception as exc:
            messagebox.showerror("Open folder failed", f"Could not open output folder:\n{exc}")

    def _set_status(self, message: str, color: str) -> None:
        self.status_var.set(message)
        self.status_label.config(fg=color)

    def _append_log(self, message: str) -> None:
        line = message.rstrip("\n")
        self.log_queue.put(line)

    def _drain_log_queue(self) -> None:
        while True:
            try:
                item = self.log_queue.get_nowait()
            except queue.Empty:
                break

            if item.startswith("__STATUS_OK__"):
                self._set_status(item.replace("__STATUS_OK__", "", 1), "#166534")
                continue
            if item.startswith("__STATUS_ERR__"):
                self._set_status(item.replace("__STATUS_ERR__", "", 1), "#991b1b")
                continue
            if item == "__BUILD_DONE__":
                self._enable_build_controls(True)
                continue
            if item == "__ENABLE_OPEN__":
                self.open_output_button.config(state="normal")
                continue
            if item.startswith("__STEP|"):
                _, step, raw_state = item.split("|", 2)
                mapping = {
                    "IN_PROGRESS": "in_progress",
                    "DONE": "done",
                    "ERROR": "error",
                    "SKIPPED": "skipped",
                }
                self._set_step_state(step, mapping.get(raw_state, "pending"))
                continue

            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, item + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")
            with self.persistent_log_path.open("a", encoding="utf-8") as fh:
                fh.write(item + "\n")

        self.root.after(100, self._drain_log_queue)

    def _enable_build_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.build_exe_button.config(state=state)
        self.build_installer_button.config(state=state)
        self.build_all_button.config(state=state)
        self.choose_button.config(state=state)
        self.recheck_button.config(state=state)

    def _set_step_state(self, step: str, state: str) -> None:
        if step not in self.step_status_vars:
            return
        label = {
            "pending": "Pending",
            "ready": "Ready to run",
            "in_progress": "🟡 In progress",
            "done": "✅ Complete",
            "error": "❌ Blocked/failed",
            "skipped": "⏭️ Skipped",
        }.get(state, "Pending")
        self.step_status_vars[step].set(label)


def main() -> None:
    root = tk.Tk()
    BuildLauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
