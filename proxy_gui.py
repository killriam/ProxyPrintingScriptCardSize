#!/usr/bin/env python3
"""
proxy_gui.py — Graphical Front-End for MaMo Proxy & Slip-in Marker Printing.

Allows selecting one or multiple proxy/marker XML files, auto-detecting recent
exports from Downloads, previewing format/card info, and generating print PDFs.

Launch:
    python proxy_gui.py
    or double-click gui.bat
"""

import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import xml.etree.ElementTree as ET
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

SCRIPT_DIR = Path(__file__).resolve().parent

# Import helper from proxy_print
try:
    sys.path.insert(0, str(SCRIPT_DIR))
    from proxy_print import find_scribus, sanitize_xml  # type: ignore[import]
except Exception:
    find_scribus = lambda: None  # noqa: E731

    def sanitize_xml(p: Path) -> str:  # type: ignore[misc]
        t = p.read_text(encoding="utf-8", errors="replace")
        return re.sub(r"(<!--.*?)--(?=.*?-->)", r"\1-", t, flags=re.DOTALL)


class FileItem:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name
        self.deck_name = ""
        self.detected_format = "cardstock"
        self.card_count = 0
        self.parse_info()

    def parse_info(self) -> None:
        raw_stem = self.path.stem
        if raw_stem.startswith("cards_"):
            raw_stem = raw_stem[6:]
        clean_stem = re.sub(
            r"_\d{4}-\d{2}-\d{2}_(missing|all|owned)_(proxy|markers|stickers)$",
            "",
            raw_stem,
        )
        self.deck_name = clean_stem

        try:
            try:
                tree = ET.parse(str(self.path))
            except ET.ParseError:
                import io

                tree = ET.parse(io.StringIO(sanitize_xml(self.path)))
            root = tree.getroot()
            po = root.find(".//printoptions")
            if po is not None and "format" in po.attrib:
                fmt = po.attrib["format"].strip().lower()
                self.detected_format = "markers" if fmt == "stickers" else fmt
            fronts = root.find(".//fronts")
            if fronts is not None:
                self.card_count = len(fronts.findall("card"))
        except Exception:
            pass

    @property
    def format_label(self) -> str:
        if self.detected_format == "a4":
            return "🖨️ DIN A4 PDF (9/page)"
        if self.detected_format == "markers":
            return "🏷️ Slip-in Markers (3.6mm)"
        return "📄 Card stock (Scribus SLA)"


class ProxyPrintGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("MaMo Proxy & Marker Print Studio")
        root.resizable(True, True)
        root.minsize(720, 640)

        self.files: list[FileItem] = []
        self._output_dir: Path | None = None
        self._log_queue: queue.Queue[str] = queue.Queue()

        self._build_ui()
        self._auto_detect_scribus()
        self._poll_log()

        # Check for local XMLs on startup
        self._auto_load_startup_files()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        PAD = {"padx": 10, "pady": 4}

        # ── Step 1: File Selection ────────────────────────────────────────────
        frame_files = ttk.LabelFrame(
            self.root, text="1. Select XML File(s) to Print"
        )
        frame_files.pack(fill="x", **PAD)

        btn_bar = ttk.Frame(frame_files)
        btn_bar.pack(fill="x", padx=8, pady=(6, 4))

        ttk.Button(
            btn_bar, text="➕ Add XML File(s)…", command=self._browse_files
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            btn_bar,
            text="⚡ Auto-Detect Recent Exports",
            command=self._auto_detect_recent,
        ).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="🗑️ Clear List", command=self._clear_files).pack(
            side="right"
        )

        # Treeview list of files
        tree_frame = ttk.Frame(frame_files)
        tree_frame.pack(fill="x", padx=8, pady=(0, 8))

        columns = ("#", "filename", "type", "cards", "deck")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=4, selectmode="extended"
        )
        self.tree.heading("#", text="#")
        self.tree.heading("filename", text="XML File Name")
        self.tree.heading("type", text="Detected Format")
        self.tree.heading("cards", text="Copies")
        self.tree.heading("deck", text="Deck Name")

        self.tree.column("#", width=35, anchor="center")
        self.tree.column("filename", width=250, anchor="w")
        self.tree.column("type", width=180, anchor="w")
        self.tree.column("cards", width=60, anchor="center")
        self.tree.column("deck", width=120, anchor="w")

        tree_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="x", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # ── Step 2: Format & Options ──────────────────────────────────────────
        frame_options = ttk.LabelFrame(
            self.root, text="2. Print Format & Options"
        )
        frame_options.pack(fill="x", **PAD)

        fmt_row = ttk.Frame(frame_options)
        fmt_row.pack(fill="x", padx=8, pady=4)

        ttk.Label(fmt_row, text="Output format:").pack(side="left")
        self.format_mode_var = tk.StringVar(value="auto")

        ttk.Radiobutton(
            fmt_row,
            text="Auto (from XML file) ★",
            variable=self.format_mode_var,
            value="auto",
            command=self._on_format_change,
        ).pack(side="left", padx=(10, 8))
        ttk.Radiobutton(
            fmt_row,
            text="DIN A4 PDF",
            variable=self.format_mode_var,
            value="a4",
            command=self._on_format_change,
        ).pack(side="left", padx=8)
        ttk.Radiobutton(
            fmt_row,
            text="Slip-in Markers",
            variable=self.format_mode_var,
            value="markers",
            command=self._on_format_change,
        ).pack(side="left", padx=8)
        ttk.Radiobutton(
            fmt_row,
            text="Card stock SLA",
            variable=self.format_mode_var,
            value="cardstock",
            command=self._on_format_change,
        ).pack(side="left", padx=8)

        # Options drawer
        self.opt_container = ttk.Frame(frame_options)
        self.opt_container.pack(fill="x", padx=8, pady=(2, 6))

        # A4 options
        self.frame_a4 = ttk.Frame(self.opt_container)
        gap_row = ttk.Frame(self.frame_a4)
        gap_row.pack(fill="x", pady=2)
        ttk.Label(gap_row, text="A4 Gap (mm):").pack(side="left")
        self.gap_var = tk.StringVar(value="0.2")
        ttk.Combobox(
            gap_row,
            textvariable=self.gap_var,
            values=["0", "0.2", "3"],
            state="readonly",
            width=5,
        ).pack(side="left", padx=6)
        self.cut_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.frame_a4, text="Cut marks", variable=self.cut_var
        ).pack(side="left", padx=8)
        self.watermark_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.frame_a4, text="Watermark", variable=self.watermark_var
        ).pack(side="left", padx=8)
        self.skip_lands_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.frame_a4, text="Skip basic lands", variable=self.skip_lands_var
        ).pack(side="left", padx=8)

        # Markers options
        self.frame_markers = ttk.Frame(self.opt_container)
        self.compact_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.frame_markers,
            text="Compact mode (dense 8mm barcodes only, omit orientation names)",
            variable=self.compact_var,
        ).pack(side="left", padx=4)

        # Cardstock options
        self.frame_cs = ttk.Frame(self.opt_container)
        scribus_row = ttk.Frame(self.frame_cs)
        scribus_row.pack(fill="x", pady=2)
        ttk.Label(scribus_row, text="Scribus:").pack(side="left")
        self.scribus_var = tk.StringVar()
        ttk.Entry(scribus_row, textvariable=self.scribus_var).pack(
            side="left", fill="x", expand=True, padx=4
        )
        ttk.Button(
            scribus_row, text="Browse…", command=self._browse_scribus
        ).pack(side="left")
        self.scribus_status_lbl = ttk.Label(
            scribus_row, text="detecting…", foreground="gray"
        )
        self.scribus_status_lbl.pack(side="left", padx=(6, 0))

        self._on_format_change()

        # ── Step 3: Action Controls ───────────────────────────────────────────
        frame_run = ttk.Frame(self.root)
        frame_run.pack(fill="x", padx=10, pady=(6, 4))

        self.run_btn = ttk.Button(
            frame_run,
            text="▶  Run Print Pipeline",
            command=self._run,
            state="disabled",
        )
        self.run_btn.pack(side="left")

        self.open_btn = ttk.Button(
            frame_run,
            text="📂 Open output folder",
            command=self._open_output,
            state="disabled",
        )
        self.open_btn.pack(side="left", padx=10)

        self.status_lbl = ttk.Label(frame_run, text="", foreground="gray")
        self.status_lbl.pack(side="left")

        # ── Log Output ────────────────────────────────────────────────────────
        frame_log = ttk.LabelFrame(self.root, text="Pipeline Output")
        frame_log.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.log_text = scrolledtext.ScrolledText(
            frame_log,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            height=12,
            background="#0f172a",
            foreground="#38bdf8",
            insertbackground="#ffffff",
        )
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ── File List Handling ────────────────────────────────────────────────────

    def _browse_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select proxy or slip-in marker XML file(s)",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if not paths:
            return
        for p in paths:
            self._add_file_item(Path(p))
        self._refresh_tree()

    def _auto_detect_recent(self) -> None:
        added = 0
        now = time.time()

        # 1. Check current directory
        for p in sorted(
            Path.cwd().glob("*.xml"), key=lambda x: x.stat().st_mtime, reverse=True
        ):
            if p.name != "pom.xml" and not p.name.endswith(".sla.xml"):
                if self._add_file_item(p):
                    added += 1

        # 2. Check Downloads folder for recent exports (last 3 hours)
        downloads_dir = Path.home() / "Downloads"
        if downloads_dir.exists():
            for p in sorted(
                downloads_dir.glob("*.xml"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            ):
                if now - p.stat().st_mtime < 10800:
                    try:
                        head = p.read_text(encoding="utf-8", errors="ignore")[
                            :400
                        ]
                        if (
                            "<cards" in head
                            or "<fronts" in head
                            or "<printoptions" in head
                            or "proxy" in p.name.lower()
                            or "markers" in p.name.lower()
                        ):
                            # Copy to current dir
                            dest = Path.cwd() / p.name
                            if not dest.exists():
                                shutil.copy2(p, dest)
                            if self._add_file_item(dest):
                                added += 1
                    except Exception:
                        pass

        self._refresh_tree()
        if added > 0:
            self._set_status(f"Found and added {added} XML file(s).", "#166534")
        else:
            self._set_status("No new recent XML files found.", "gray")

    def _auto_load_startup_files(self) -> None:
        for p in sorted(
            Path.cwd().glob("*.xml"), key=lambda x: x.stat().st_mtime, reverse=True
        ):
            if p.name != "pom.xml" and not p.name.endswith(".sla.xml"):
                self._add_file_item(p)
        self._refresh_tree()

    def _add_file_item(self, path: Path) -> bool:
        norm = str(path.resolve())
        for existing in self.files:
            if str(existing.path.resolve()) == norm:
                return False
        self.files.append(FileItem(path))
        return True

    def _clear_files(self) -> None:
        self.files.clear()
        self._refresh_tree()
        self._set_status("File list cleared.", "gray")

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, item in enumerate(self.files, 1):
            self.tree.insert(
                "",
                "end",
                values=(
                    str(i),
                    item.name,
                    item.format_label,
                    str(item.card_count),
                    item.deck_name,
                ),
            )
        count = len(self.files)
        if count > 0:
            self.run_btn.config(
                state="normal",
                text=f"▶  Run Print Pipeline ({count} file{'s' if count > 1 else ''})",
            )
        else:
            self.run_btn.config(state="disabled", text="▶  Run Print Pipeline")

    # ── Options Visibility ────────────────────────────────────────────────────

    def _on_format_change(self) -> None:
        mode = self.format_mode_var.get()
        self.frame_a4.pack_forget()
        self.frame_markers.pack_forget()
        self.frame_cs.pack_forget()

        if mode == "a4":
            self.frame_a4.pack(fill="x")
        elif mode == "markers":
            self.frame_markers.pack(fill="x")
        elif mode == "cardstock":
            self.frame_cs.pack(fill="x")
        else:
            # Auto mode shows A4 and markers options compactly
            self.frame_a4.pack(fill="x")
            self.frame_markers.pack(fill="x", pady=(2, 0))

    def _browse_scribus(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Scribus executable",
            filetypes=[("Executables", "*.exe *.app"), ("All files", "*.*")],
        )
        if path:
            self.scribus_var.set(path)
            self.scribus_status_lbl.config(text="", foreground="gray")

    def _auto_detect_scribus(self) -> None:
        def _detect() -> None:
            found = find_scribus()
            self.root.after(0, self._apply_scribus_result, found)

        threading.Thread(target=_detect, daemon=True).start()

    def _apply_scribus_result(self, path: str | None) -> None:
        if path:
            self.scribus_var.set(path)
            self.scribus_status_lbl.config(
                text="auto-detected", foreground="green"
            )
        else:
            self.scribus_status_lbl.config(
                text="not found", foreground="orange"
            )

    # ── Pipeline Execution ────────────────────────────────────────────────────

    def _run(self) -> None:
        if not self.files:
            self._set_status("Please add at least one XML file.", "red")
            return

        self.run_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self._set_status("Processing files…", "gray")

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        targets = [str(f.path) for f in self.files]
        threading.Thread(
            target=self._run_pipeline, args=(targets,), daemon=True
        ).start()

    def _run_pipeline(self, target_paths: list[str]) -> None:
        cmd = [sys.executable, "-u", str(SCRIPT_DIR / "proxy_print.py")]

        mode = self.format_mode_var.get()
        if mode != "auto":
            cmd += ["--format", mode]

        # Options
        if mode in ("auto", "a4"):
            cmd += ["--gap", self.gap_var.get()]
            if self.cut_var.get():
                cmd.append("--cut-marks")
            if self.watermark_var.get():
                cmd.append("--watermark")
            if self.skip_lands_var.get():
                cmd.append("--skip-basic-lands")

        if mode in ("auto", "markers") and self.compact_var.get():
            cmd.append("--compact")

        if mode == "cardstock":
            sc = self.scribus_var.get().strip()
            if sc:
                cmd += ["--scribus", sc]

        cmd.extend(target_paths)

        display_cmd = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        self._append_log(f"$ {display_cmd}\n\n")

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self._append_log(line)
            proc.wait()
            rc = proc.returncode
        except Exception as exc:
            self._append_log(f"\nFailed to launch pipeline: {exc}\n")
            rc = -1

        # Derive first deck output folder for quick opening
        if self.files:
            deck = self.files[0].deck_name or "deck"
            self._output_dir = SCRIPT_DIR / "ready2Print" / deck
            if not self._output_dir.exists():
                self._output_dir = SCRIPT_DIR / "ready2Print"

        self.root.after(0, self._on_done, rc == 0)

    def _on_done(self, success: bool) -> None:
        count = len(self.files)
        self.run_btn.config(
            state="normal",
            text=f"▶  Run Print Pipeline ({count} file{'s' if count > 1 else ''})",
        )
        if success:
            self._set_status("All files printed successfully!", "#166534")
            self.open_btn.config(state="normal")
        else:
            self._set_status("Pipeline completed with errors (see log).", "red")

    def _open_output(self) -> None:
        target = self._output_dir or (SCRIPT_DIR / "ready2Print")
        if not target.exists():
            target = SCRIPT_DIR
        if sys.platform == "win32":
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target)], check=False)
        else:
            subprocess.run(["xdg-open", str(target)], check=False)

    def _set_status(self, text: str, color: str) -> None:
        self.status_lbl.config(text=text, foreground=color)

    def _poll_log(self) -> None:
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert("end", msg)
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(50, self._poll_log)

    def _append_log(self, text: str) -> None:
        self._log_queue.put(text)


def main() -> None:
    root = tk.Tk()
    ProxyPrintGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
