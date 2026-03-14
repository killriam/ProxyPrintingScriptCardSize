#!/usr/bin/env python3
"""
proxy_gui.py — Tkinter GUI front-end for the MaMo proxy print pipeline.

Wraps proxy_print.py with a graphical interface — no command-line required.
Run: python proxy_gui.py
"""

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

SCRIPT_DIR = Path(__file__).resolve().parent


class ProxyPrintGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("MaMo Proxy Print")
        root.resizable(True, True)
        root.minsize(660, 600)

        # Import find_scribus from sibling module (optional — belt-and-suspenders)
        try:
            sys.path.insert(0, str(SCRIPT_DIR))
            from proxy_print import find_scribus  # type: ignore[import]
            self._find_scribus = find_scribus
        except Exception:
            self._find_scribus = lambda: None

        self._output_dir: Path | None = None
        self._log_queue: queue.Queue[str] = queue.Queue()

        self._build_ui()
        self._auto_detect_scribus()
        self._poll_log()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        PAD = {"padx": 8, "pady": 4}

        # XML file picker
        frame_xml = ttk.LabelFrame(self.root, text="Proxy XML file")
        frame_xml.pack(fill="x", **PAD)
        self.xml_var = tk.StringVar()
        ttk.Entry(frame_xml, textvariable=self.xml_var).pack(
            side="left", fill="x", expand=True, padx=(6, 4), pady=6
        )
        ttk.Button(frame_xml, text="Browse…", command=self._browse_xml).pack(
            side="right", padx=(0, 6), pady=6
        )

        # Deck name override
        frame_deck = ttk.LabelFrame(self.root, text="Deck name override (optional)")
        frame_deck.pack(fill="x", **PAD)
        self.deck_var = tk.StringVar()
        ttk.Entry(frame_deck, textvariable=self.deck_var).pack(
            side="left", fill="x", expand=True, padx=6, pady=6
        )
        ttk.Label(
            frame_deck, text="  leave blank = auto-derive from filename", foreground="gray"
        ).pack(side="left", padx=(0, 6))

        # Format radio
        frame_fmt = ttk.LabelFrame(self.root, text="Output format")
        frame_fmt.pack(fill="x", **PAD)
        self.format_var = tk.StringVar(value="cardstock")
        ttk.Radiobutton(
            frame_fmt,
            text="Card stock  (1 card / page · Scribus SLA)",
            variable=self.format_var,
            value="cardstock",
            command=self._on_format_change,
        ).pack(anchor="w", padx=8, pady=2)
        ttk.Radiobutton(
            frame_fmt,
            text="DIN A4  (9 cards / page · PDF · no Scribus needed)",
            variable=self.format_var,
            value="a4",
            command=self._on_format_change,
        ).pack(anchor="w", padx=8, pady=(2, 4))

        # Container that holds EITHER card-stock or A4 options
        self._options_container = ttk.Frame(self.root)
        self._options_container.pack(fill="x", padx=8)

        # ── Card stock options ─────────────────────────────────────────────
        self.frame_cs = ttk.LabelFrame(self._options_container, text="Card stock options")

        scribus_row = ttk.Frame(self.frame_cs)
        scribus_row.pack(fill="x", padx=6, pady=4)
        ttk.Label(scribus_row, text="Scribus:").pack(side="left")
        self.scribus_var = tk.StringVar()
        ttk.Entry(scribus_row, textvariable=self.scribus_var).pack(
            side="left", fill="x", expand=True, padx=4
        )
        ttk.Button(scribus_row, text="Browse…", command=self._browse_scribus).pack(side="left")
        self.scribus_status_lbl = ttk.Label(scribus_row, text="detecting…", foreground="gray")
        self.scribus_status_lbl.pack(side="left", padx=(6, 0))

        bg_row = ttk.Frame(self.frame_cs)
        bg_row.pack(fill="x", padx=6, pady=2)
        ttk.Label(bg_row, text="Background / cardback image  (optional):").pack(side="left")
        self.bg_var = tk.StringVar()
        ttk.Entry(bg_row, textvariable=self.bg_var).pack(
            side="left", fill="x", expand=True, padx=4
        )
        ttk.Button(bg_row, text="Browse…", command=self._browse_bg).pack(side="left")



        # ── A4 options ─────────────────────────────────────────────────────
        self.frame_a4 = ttk.LabelFrame(self._options_container, text="A4 options")

        gap_row = ttk.Frame(self.frame_a4)
        gap_row.pack(fill="x", padx=6, pady=4)
        ttk.Label(gap_row, text="Gap between cards (mm):").pack(side="left")
        self.gap_var = tk.StringVar(value="0.2")
        ttk.Combobox(
            gap_row, textvariable=self.gap_var, values=["0", "0.2", "3"],
            state="readonly", width=6,
        ).pack(side="left", padx=8)

        self.cut_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.frame_a4, text="Draw cut marks at card corners",
            variable=self.cut_var,
        ).pack(anchor="w", padx=8, pady=2)

        self.watermark_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.frame_a4, text='Diagonal "Playtest Card" watermark on each card',
            variable=self.watermark_var,
        ).pack(anchor="w", padx=8, pady=2)

        self.skip_lands_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.frame_a4, text="Skip basic lands",
            variable=self.skip_lands_var,
        ).pack(anchor="w", padx=8, pady=(2, 6))

        # Show the default format options
        self._on_format_change()

        # ── Run controls ───────────────────────────────────────────────────
        frame_run = ttk.Frame(self.root)
        frame_run.pack(fill="x", padx=8, pady=6)

        self.run_btn = ttk.Button(frame_run, text="▶  Run Pipeline", command=self._run)
        self.run_btn.pack(side="left")

        self.open_btn = ttk.Button(
            frame_run, text="Open output folder",
            command=self._open_output, state="disabled",
        )
        self.open_btn.pack(side="left", padx=8)

        self.status_lbl = ttk.Label(frame_run, text="", foreground="gray")
        self.status_lbl.pack(side="left")

        # ── Log output ─────────────────────────────────────────────────────
        frame_log = ttk.LabelFrame(self.root, text="Pipeline output")
        frame_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.log_text = scrolledtext.ScrolledText(
            frame_log,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
            height=14,
            background="#1e1e1e",
            foreground="#d4d4d4",
            insertbackground="#d4d4d4",
        )
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ── Format toggle ─────────────────────────────────────────────────────────

    def _on_format_change(self) -> None:
        if self.format_var.get() == "cardstock":
            self.frame_a4.pack_forget()
            self.frame_cs.pack(fill="x")
        else:
            self.frame_cs.pack_forget()
            self.frame_a4.pack(fill="x")

    # ── File dialogs ──────────────────────────────────────────────────────────

    def _browse_xml(self) -> None:
        path = filedialog.askopenfilename(
            title="Select proxy XML file",
            filetypes=[("XML files", "*.xml"), ("All files", "*.*")],
        )
        if not path:
            return
        self.xml_var.set(path)
        # Auto-fill deck name if empty
        if not self.deck_var.get():
            stem = Path(path).stem
            if stem.startswith("cards_"):
                stem = stem[6:]
            # Strip MaMo date+scope suffix and optional OS copy suffix like " (1)"
            clean = re.sub(r"_\d{4}-\d{2}-\d{2}_(missing|all)_proxy( \(\d+\))?$", "", stem)
            self.deck_var.set(clean)

    def _browse_scribus(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Scribus executable",
            filetypes=[("Executables", "*.exe *.app"), ("All files", "*.*")],
        )
        if path:
            self.scribus_var.set(path)
            self.scribus_status_lbl.config(text="", foreground="gray")

    def _browse_bg(self) -> None:
        path = filedialog.askopenfilename(
            title="Select background / cardback image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.bg_var.set(path)

    # ── Scribus auto-detect (runs in background thread) ───────────────────────

    def _auto_detect_scribus(self) -> None:
        def _detect() -> None:
            found = self._find_scribus()
            self.root.after(0, self._apply_scribus_result, found)

        threading.Thread(target=_detect, daemon=True).start()

    def _apply_scribus_result(self, path: str | None) -> None:
        if path:
            self.scribus_var.set(path)
            self.scribus_status_lbl.config(text="auto-detected", foreground="green")
        else:
            self.scribus_status_lbl.config(text="not found — browse to set", foreground="orange")

    # ── Log (thread-safe, polled via after()) ────────────────────────────────

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

    # ── Pipeline execution ────────────────────────────────────────────────────

    def _preflight(self) -> bool:
        """Validate prerequisites and show a user-facing error if something is missing."""
        from tkinter import messagebox
        fmt = self.format_var.get()
        if fmt == "a4":
            try:
                import importlib
                if importlib.util.find_spec("fpdf") is None:
                    raise ImportError
            except ImportError:
                messagebox.showerror(
                    "Missing dependency",
                    "The fpdf2 package is required for DIN A4 PDF output but is not installed "
                    "for the current Python interpreter.\n\n"
                    f"Install it with:\n  {sys.executable} -m pip install fpdf2>=2.7.0"
                )
                return False
        elif fmt == "cardstock":
            if not self.scribus_var.get().strip():
                messagebox.showerror(
                    "Scribus not found",
                    "Scribus executable is required for card stock output but was not found.\n\n"
                    "Install Scribus from https://www.scribus.net/downloads/ "
                    "or browse to the executable above."
                )
                return False
        return True

    def _run(self) -> None:
        xml_path = self.xml_var.get().strip()
        if not xml_path:
            self._set_status("Please select a proxy XML file.", "red")
            return
        if not Path(xml_path).exists():
            self._set_status("XML file not found.", "red")
            return
        if not self._preflight():
            return

        self.run_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self._set_status("Running…", "gray")

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        threading.Thread(target=self._run_pipeline, args=(xml_path,), daemon=True).start()

    def _run_pipeline(self, xml_path: str) -> None:
        cmd = [sys.executable, str(SCRIPT_DIR / "proxy_print.py"), xml_path]

        deck_name = self.deck_var.get().strip()
        if deck_name:
            cmd += ["--deck-name", deck_name]

        fmt = self.format_var.get()
        cmd += ["--format", fmt]

        if fmt == "cardstock":
            scribus = self.scribus_var.get().strip()
            if scribus:
                cmd += ["--scribus", scribus]
            bg = self.bg_var.get().strip()
            if bg:
                cmd += ["--background", bg]
        else:  # a4
            cmd += ["--gap", self.gap_var.get()]
            if self.cut_var.get():
                cmd.append("--cut-marks")
            if self.watermark_var.get():
                cmd.append("--watermark")
            if self.skip_lands_var.get():
                cmd.append("--skip-basic-lands")

        # Show the full command in the log
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

        # Derive expected output directory for the "Open folder" button
        xml_p = Path(xml_path)
        dn = deck_name
        if not dn:
            stem = xml_p.stem
            if stem.startswith("cards_"):
                stem = stem[6:]
            dn = re.sub(r"_\d{4}-\d{2}-\d{2}_(missing|all)_proxy( \(\d+\))?$", "", stem)
        self._output_dir = xml_p.parent / "ready2Print" / dn

        self.root.after(0, self._on_done, rc == 0)

    def _on_done(self, success: bool) -> None:
        self.run_btn.config(state="normal")
        if success:
            self._set_status("Done!", "green")
            if self._output_dir and self._output_dir.exists():
                self.open_btn.config(state="normal")
        else:
            self._set_status("Pipeline failed — see log above.", "red")

    def _open_output(self) -> None:
        if not self._output_dir or not self._output_dir.exists():
            return
        if sys.platform == "win32":
            os.startfile(str(self._output_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(self._output_dir)], check=False)
        else:
            subprocess.run(["xdg-open", str(self._output_dir)], check=False)

    def _set_status(self, text: str, color: str) -> None:
        self.status_lbl.config(text=text, foreground=color)


def main() -> None:
    root = tk.Tk()
    ProxyPrintGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
