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


class BuildLauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Adventurers Guild AI Build Launcher")
        self.root.geometry("980x680")
        self.root.minsize(860, 560)

        self.repo_root = Path(__file__).resolve().parent
        self.exe_script = self.repo_root / "tools" / "build_exe.bat"
        self.installer_script = self.repo_root / "tools" / "build_installer.bat"

        self.output_dir_var = tk.StringVar(value=str((self.repo_root / "release").resolve()))
        self.status_var = tk.StringVar(value="Ready.")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None

        logs_dir = self.repo_root / "logs"
        logs_dir.mkdir(exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.persistent_log_path = logs_dir / f"build_launcher_{ts}.log"

        self._build_ui()
        self._append_log(f"Adventurers Guild AI Build Launcher started at { _dt.datetime.now().isoformat(timespec='seconds') }")
        self._append_log(f"Repository root: {self.repo_root}")
        self._append_log(f"Persistent log: {self.persistent_log_path}")
        self._set_status("Ready.", "#1e3a8a")
        self.root.after(100, self._drain_log_queue)

    def _build_ui(self) -> None:
        top = tk.Frame(self.root, padx=12, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Output folder:", anchor="w").grid(row=0, column=0, sticky="w")
        self.output_entry = tk.Entry(top, textvariable=self.output_dir_var, state="readonly", width=95)
        self.output_entry.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(4, 0))

        self.choose_button = tk.Button(top, text="Choose output folder", command=self.choose_output_folder, width=22)
        self.choose_button.grid(row=0, column=4, sticky="e")

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

        if mode in {"installer", "all"} and not self._has_inno_setup():
            msg = (
                "Inno Setup 6 (ISCC.exe) was not found.\n"
                "Installer and Build Everything modes require Inno Setup.\n"
                "Install from https://jrsoftware.org/isinfo.php"
            )
            self._set_status("Missing prerequisite: Inno Setup 6 not found.", "#991b1b")
            self._append_log("ERROR: Inno Setup prerequisite missing for installer build.")
            messagebox.showerror("Missing prerequisite", msg)
            return

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
        artifacts: list[Path] = []

        try:
            if mode in {"exe", "all"}:
                ok = self._run_script(self.exe_script)
                if ok:
                    exe_path = self.repo_root / "dist" / "AdventurerGuildAI" / "AdventurerGuildAI.exe"
                    if exe_path.exists():
                        copied = self._copy_artifact(exe_path, output_dir)
                        artifacts.append(copied)
                    else:
                        self._append_log("WARNING: Expected executable not found after EXE build.")

            if ok and mode in {"installer", "all"}:
                ok = self._run_script(self.installer_script)
                installer_path = self.repo_root / "installer" / "Output" / "AdventurerGuildAI_Setup.exe"
                if ok and installer_path.exists():
                    copied = self._copy_artifact(installer_path, output_dir)
                    artifacts.append(copied)
                    self._append_log(f"FINAL INSTALLER PATH: {copied}")
                elif ok:
                    self._append_log("WARNING: Installer script completed but expected installer was not found.")

            if ok:
                summary = f"Build completed successfully. Artifacts copied to: {output_dir}"
                self.log_queue.put(f"__STATUS_OK__{summary}")
                self.log_queue.put("__ENABLE_OPEN__")
            else:
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


def main() -> None:
    root = tk.Tk()
    BuildLauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
