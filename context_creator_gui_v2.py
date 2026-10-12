"""
Project Context Creator v2 — IBM Carbon-styled GUI
New file — original context_creator_gui.py is unchanged.

Features:
  - Individual files, Project folder, Paste/transcript, Video URL modes
  - Skip MP4 / skip large files / exclude folder patterns
  - Auto-consolidate toggle with config browse
  - Whisper model selector for video URL
  - Config persistence (config.json)
  - IBM Carbon g100 color palette throughout
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
from pathlib import Path
import logging
import json
import re
import subprocess
import sys
import threading
from datetime import datetime

# ── Logging ───────────────────────────────────────────────────────────────────
# Force UTF-8 on the Windows console so filenames with Unicode chars don't crash the log handler
import sys as _sys, io as _io
if hasattr(_sys.stdout, 'reconfigure'):
    try:
        _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(log_dir / f"gui_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
                            encoding='utf-8'),
        logging.StreamHandler(stream=_sys.stdout),
    ],
)

# ── Converters ────────────────────────────────────────────────────────────────
try:
    from converters import (
        convert_pdf_to_markdown,
        convert_docx_to_markdown,
        convert_pptx_to_markdown,
        convert_xlsx_to_markdown,
        convert_image_to_markdown,
        convert_boxnote_to_markdown,
        copy_markdown_file,
        convert_mp4_to_markdown,
        convert_video_url_to_markdown,
    )
    from converters.folder_processor import FolderProcessor
except ImportError as e:
    logging.error(f"Import error: {e}")


# ── Color palette — IBM Carbon g100 ──────────────────────────────────────────
BG       = "#161616"   # background           $background
LAYER1   = "#262626"   # layer-01             $layer-01
LAYER2   = "#393939"   # layer-02             $layer-02
BORDER   = "#525252"   # border-subtle        $border-subtle-01
FG       = "#f4f4f4"   # text-primary         $text-primary
FG2      = "#c6c6c6"   # text-secondary       $text-secondary
FG_DIS   = "#6f6f6f"   # text-disabled        $text-disabled
BLUE     = "#0f62fe"   # interactive          $button-primary / Blue-60
BLUE_H   = "#0353e9"   # interactive hover    $button-primary-hover / Blue-70
GREEN    = "#24a148"   # support-success      $support-success
RED      = "#da1e28"   # support-error        $support-error
HDR_BG   = "#161616"   # shell header bg      $background (UI Shell uses dark, not blue)
HDR_BDR  = "#0f62fe"   # header accent line   Blue-60 used as 3px left border on active tab
FONT     = "IBM Plex Sans"   # Carbon type: IBM Plex Sans (falls back to system sans-serif if not installed)


def _btn(parent, text, cmd, kind="primary", **kw):
    """Create a flat Carbon-style button."""
    if kind == "primary":
        bg, fg, abg = BLUE, "#ffffff", BLUE_H
    elif kind == "secondary":
        bg, fg, abg = LAYER2, FG, BORDER
    else:  # ghost
        bg, fg, abg = BG, FG2, LAYER1
    b = tk.Button(parent, text=text, command=cmd,
                  font=(FONT, 10), bg=bg, fg=fg,
                  activebackground=abg, activeforeground=fg,
                  relief=tk.FLAT, cursor="hand2",
                  padx=16, pady=7, **kw)
    return b


def _label(parent, text, size=9, color=FG2, **kw):
    return tk.Label(parent, text=text, font=(FONT, size),
                    bg=BG, fg=color, **kw)


def _text_box(parent, height=10):
    frame = tk.Frame(parent, bg=BG)
    sb = tk.Scrollbar(frame, bg=LAYER2, troughcolor=LAYER1)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    t = tk.Text(frame, font=("Consolas", 9),
                bg=LAYER1, fg=FG, insertbackground=FG,
                selectbackground=BLUE, relief=tk.FLAT, bd=0,
                height=height, wrap=tk.WORD,
                yscrollcommand=sb.set)
    t.pack(fill=tk.BOTH, expand=True)
    sb.config(command=t.yview)
    return frame, t


def _entry(parent, var, width=40, **kw):
    return tk.Entry(parent, textvariable=var,
                    font=(FONT, 10), bg=LAYER2, fg=FG,
                    insertbackground=FG, relief=tk.FLAT,
                    width=width, **kw)


def _check(parent, text, var, **kw):
    return tk.Checkbutton(parent, text=text, variable=var,
                          font=(FONT, 9), bg=LAYER1, fg=FG,
                          selectcolor=LAYER2, activebackground=LAYER1,
                          activeforeground=FG, cursor="hand2", **kw)


class AppV2:
    DEFAULT_CONFIG = {
        "skip_options": {
            "skip_mp4": False,
            "skip_large_files": False,
            "skip_large_threshold_mb": 500,
            "exclude_folder_patterns": ["Archive", "_archive", "OLD", "Do Not Use"],
        },
        "output": {"default_output_subfolder": "_markdown"},
        "consolidation": {"auto_consolidate": False},
        "video_url": {"whisper_model": "medium"},
        "version": "2.0",
    }

    SUPPORTED_FORMATS = {
        ".pdf", ".docx", ".pptx", ".xlsx",
        ".jpg", ".jpeg", ".png", ".mp4", ".boxnote", ".md",
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Project Context Creator")
        self.root.geometry("980x780")
        self.root.minsize(800, 600)
        self.root.configure(bg=BG)

        self.config_path = Path(__file__).parent / "config.json"
        self.config = self._load_config()

        # State
        self.selected_files = []
        self.selected_folder = None
        # Restore output folder from config so the auto-scan on source selection
        # uses the correct metadata path instead of defaulting to _markdown
        _saved_out = self.config.get("output", {}).get("last_output_folder", "")
        self.output_folder = Path(_saved_out) if _saved_out else None
        self.folder_info = None
        self.paste_output_folder = Path.home() / "Desktop"
        self.video_output_folder = Path.home() / "Desktop"
        self.video_queue = []
        self.conversion_results = []
        self.mode = "files"

        # Tk vars — seeded from config
        so = self.config.get("skip_options", {})
        self.skip_mp4_var    = tk.BooleanVar(value=so.get("skip_mp4", False))
        self.skip_large_var  = tk.BooleanVar(value=so.get("skip_large_files", False))
        self.skip_large_mb   = tk.StringVar(value=str(so.get("skip_large_threshold_mb", 500)))
        self.exclude_var     = tk.StringVar(value=", ".join(so.get("exclude_folder_patterns", [])))
        co = self.config.get("consolidation", {})
        self.auto_consol_var = tk.BooleanVar(value=co.get("auto_consolidate", False))
        self.consol_cfg_var  = tk.StringVar(value="")
        vo = self.config.get("video_url", {})
        self.whisper_var     = tk.StringVar(value=vo.get("whisper_model", "medium"))
        self.paste_filename  = tk.StringVar(value="meeting_transcript")

        self._build_ui()

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return dict(self.DEFAULT_CONFIG)

    def _save_config(self):
        try:
            self.config["skip_options"] = {
                "skip_mp4": self.skip_mp4_var.get(),
                "skip_large_files": self.skip_large_var.get(),
                "skip_large_threshold_mb": float(self.skip_large_mb.get() or 500),
                "exclude_folder_patterns": [p.strip() for p in self.exclude_var.get().split(",") if p.strip()],
            }
            self.config["consolidation"] = {"auto_consolidate": self.auto_consol_var.get()}
            self.config["video_url"]     = {"whisper_model": self.whisper_var.get()}
            self.config["output"] = {
                "last_output_folder": str(self.output_folder) if self.output_folder else "",
            }
            self.config_path.write_text(json.dumps(self.config, indent=2), encoding="utf-8")
        except Exception as e:
            logging.warning(f"Could not save config: {e}")

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header bar — Carbon UI Shell: dark background, IBM Plex Sans, Blue-60 left accent
        hdr = tk.Frame(self.root, bg=HDR_BG, height=48)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        # 3 px Blue-60 accent stripe on the left edge (mimics Carbon's header product name treatment)
        tk.Frame(hdr, bg=HDR_BDR, width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(hdr, text="Project Context Creator",
                 font=(FONT, 13, "bold"), bg=HDR_BG, fg=FG
                 ).pack(side=tk.LEFT, padx=14, pady=12)

        # Sub-header
        tk.Label(self.root,
                 text="Convert documents, project folders, and transcripts to AI-optimized markdown",
                 font=(FONT, 9), bg=BG, fg=FG2
                 ).pack(pady=(10, 0))

        # Mode tabs row
        tab_frame = tk.Frame(self.root, bg=LAYER1, height=40)
        tab_frame.pack(fill=tk.X, pady=(10, 0))
        tab_frame.pack_propagate(False)

        self.mode_var = tk.StringVar(value="files")
        self.tab_btns = {}
        modes = [
            ("files",     "Individual Files"),
            ("folder",    "Project Folder"),
            ("paste",     "Paste / Transcript"),
            ("video_url", "Video URL"),
        ]
        for value, label in modes:
            b = tk.Button(
                tab_frame, text=label,
                font=(FONT, 10), relief=tk.FLAT,
                cursor="hand2", padx=20, pady=8,
                command=lambda v=value: self._switch_mode(v),
            )
            b.pack(side=tk.LEFT)
            self.tab_btns[value] = b
        self._update_tabs("files")

        # Content area
        self.content = tk.Frame(self.root, bg=BG, padx=20, pady=16)
        self.content.pack(fill=tk.BOTH, expand=True)

        # Build all panels
        self.panels = {
            "files":     self._panel_files(),
            "folder":    self._panel_folder(),
            "paste":     self._panel_paste(),
            "video_url": self._panel_video(),
        }
        self._switch_mode("files")

        # Progress
        prog_frame = tk.Frame(self.root, bg=BG, padx=20)
        prog_frame.pack(fill=tk.X)
        self.progress_label = _label(prog_frame, "Ready", 9)
        self.progress_label.pack(anchor=tk.W)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("C.Horizontal.TProgressbar",
                        background=BLUE, troughcolor=LAYER2,
                        bordercolor=LAYER1, lightcolor=BLUE, darkcolor=BLUE)
        self.progress_bar = ttk.Progressbar(
            prog_frame, mode="determinate", style="C.Horizontal.TProgressbar")
        self.progress_bar.pack(fill=tk.X, pady=(4, 0))

        # Convert button
        self.convert_btn = _btn(self.content, "Convert to Markdown",
                                self.start_conversion, kind="primary")
        self.convert_btn.config(state=tk.DISABLED,
                                font=(FONT, 11, "bold"), padx=32, pady=12,
                                disabledforeground=FG_DIS)
        self.convert_btn.pack(pady=(12, 0))

        # Status bar
        sb = tk.Frame(self.root, bg=LAYER1, height=28)
        sb.pack(fill=tk.X, side=tk.BOTTOM)
        sb.pack_propagate(False)
        self.status_label = tk.Label(sb, text="Select a mode and input to begin",
                                     font=(FONT, 9), bg=LAYER1, fg=FG2, anchor=tk.W)
        self.status_label.pack(fill=tk.X, padx=12, pady=4)

    # ── Mode switching ────────────────────────────────────────────────────────

    def _update_tabs(self, active):
        for value, btn in self.tab_btns.items():
            if value == active:
                btn.config(bg=BG, fg=FG, activebackground=BG)
            else:
                btn.config(bg=LAYER1, fg=FG2, activebackground=LAYER2)

    def _switch_mode(self, mode):
        self.mode = mode
        self._update_tabs(mode)
        for key, panel in self.panels.items():
            if key == mode:
                panel.pack(fill=tk.BOTH, expand=True)
            else:
                panel.pack_forget()
        # Move convert button to bottom of content after panels
        if hasattr(self, "convert_btn"):
            self.convert_btn.pack_forget()
            self.convert_btn.pack(pady=(12, 0))

    # ── Panel: Individual Files ───────────────────────────────────────────────

    def _panel_files(self):
        f = tk.Frame(self.content, bg=BG)
        row = tk.Frame(f, bg=BG)
        row.pack(fill=tk.X, pady=(0, 10))
        _btn(row, "Select Files", self.select_files).pack(side=tk.LEFT, padx=(0, 8))
        _btn(row, "Clear", self.clear_selection, kind="secondary").pack(side=tk.LEFT)
        box_frame, self.files_text = _text_box(f, height=12)
        box_frame.pack(fill=tk.BOTH, expand=True)
        self.files_text.insert(tk.END, "No files selected\n\nClick 'Select Files' to choose documents.")
        return f

    # ── Panel: Project Folder ─────────────────────────────────────────────────

    def _panel_folder(self):
        f = tk.Frame(self.content, bg=BG)

        # Buttons
        row = tk.Frame(f, bg=BG)
        row.pack(fill=tk.X, pady=(0, 10))
        _btn(row, "Select Source Folder",   self.select_folder).pack(side=tk.LEFT, padx=(0, 8))
        _btn(row, "Select Output Location", self.select_output_folder, kind="secondary").pack(side=tk.LEFT, padx=(0, 8))
        _btn(row, "Clear",                  self.clear_selection, kind="secondary").pack(side=tk.LEFT)

        # Skip options
        skip = tk.LabelFrame(f, text="Skip Options", font=(FONT, 9, "bold"),
                             bg=LAYER1, fg=FG, padx=10, pady=8, relief=tk.FLAT, bd=1)
        skip.pack(fill=tk.X, pady=(0, 8))

        _check(skip, "Skip MP4 video files (avoids long Whisper transcription)",
               self.skip_mp4_var).pack(anchor=tk.W)

        large_row = tk.Frame(skip, bg=LAYER1)
        large_row.pack(anchor=tk.W, pady=(6, 0))
        _check(large_row, "Skip files over", self.skip_large_var).pack(side=tk.LEFT)
        _entry(large_row, self.skip_large_mb, width=6).pack(side=tk.LEFT, padx=(6, 4))
        tk.Label(large_row, text="MB", font=(FONT, 9), bg=LAYER1, fg=FG2).pack(side=tk.LEFT)

        excl_row = tk.Frame(skip, bg=LAYER1)
        excl_row.pack(fill=tk.X, pady=(8, 0))
        tk.Label(excl_row, text="Exclude folder names:", font=(FONT, 9), bg=LAYER1, fg=FG
                 ).pack(side=tk.LEFT)
        _entry(excl_row, self.exclude_var, width=45).pack(side=tk.LEFT, padx=(8, 0))
        tk.Label(excl_row, text="(comma-separated)", font=(FONT, 8), bg=LAYER1, fg=FG2
                 ).pack(side=tk.LEFT, padx=(6, 0))

        # Consolidation
        consol = tk.LabelFrame(f, text="Consolidation", font=(FONT, 9, "bold"),
                               bg=LAYER1, fg=FG, padx=10, pady=8, relief=tk.FLAT, bd=1)
        consol.pack(fill=tk.X, pady=(0, 8))

        _check(consol, "Auto-consolidate after conversion",
               self.auto_consol_var, command=self._save_config).pack(anchor=tk.W)

        cfg_row = tk.Frame(consol, bg=LAYER1)
        cfg_row.pack(fill=tk.X, pady=(6, 0))
        tk.Label(cfg_row, text="Groups config (.json):", font=(FONT, 9), bg=LAYER1, fg=FG
                 ).pack(side=tk.LEFT)
        _entry(cfg_row, self.consol_cfg_var, width=38).pack(side=tk.LEFT, padx=(8, 6))
        _btn(cfg_row, "Browse", self._browse_consol_config, kind="secondary"
             ).pack(side=tk.LEFT)

        # Info display
        box_frame, self.folder_text = _text_box(f, height=8)
        box_frame.pack(fill=tk.BOTH, expand=True)
        self.folder_text.insert(tk.END, "No folder selected\n\nClick 'Select Source Folder' to begin.")
        return f

    # ── Panel: Paste / Transcript ─────────────────────────────────────────────

    def _panel_paste(self):
        f = tk.Frame(self.content, bg=BG)
        _label(f, "Paste a Teams transcript or any text content below:", 10
               ).pack(anchor=tk.W, pady=(0, 6))

        box_frame, self.paste_text = _text_box(f, height=14)
        box_frame.pack(fill=tk.BOTH, expand=True)
        self.paste_text.bind("<<Modified>>", self._on_paste_change)

        row = tk.Frame(f, bg=BG)
        row.pack(fill=tk.X, pady=(10, 0))
        _btn(row, "Select Output Folder", self.select_paste_output, kind="secondary"
             ).pack(side=tk.LEFT, padx=(0, 8))
        _btn(row, "Clear", self.clear_paste, kind="secondary").pack(side=tk.LEFT)

        self.paste_out_label = _label(f, f"Output: {self.paste_output_folder}", 9)
        self.paste_out_label.pack(anchor=tk.W, pady=(6, 0))

        fn_row = tk.Frame(f, bg=BG)
        fn_row.pack(fill=tk.X, pady=(8, 0))
        _label(fn_row, "Filename:", 9, FG).pack(side=tk.LEFT)
        _entry(fn_row, self.paste_filename, width=30).pack(side=tk.LEFT, padx=(8, 4))
        _label(fn_row, ".md", 9).pack(side=tk.LEFT)
        return f

    # ── Panel: Video URL ──────────────────────────────────────────────────────

    def _panel_video(self):
        f = tk.Frame(self.content, bg=BG)
        _label(f, "Transcribe YouTube or any video URL using Whisper:", 10
               ).pack(anchor=tk.W, pady=(0, 6))

        # URL input row
        url_row = tk.Frame(f, bg=BG)
        url_row.pack(fill=tk.X, pady=(0, 8))
        self.url_var = tk.StringVar()
        url_entry = _entry(url_row, self.url_var, width=60)
        url_entry.pack(side=tk.LEFT, padx=(0, 8))
        url_entry.bind("<Return>", lambda e: self._add_url())
        _btn(url_row, "Add URL", self._add_url).pack(side=tk.LEFT)

        # Queue
        _label(f, "URL queue:", 9).pack(anchor=tk.W)
        q_frame = tk.Frame(f, bg=BG)
        q_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        sb = tk.Scrollbar(q_frame, bg=LAYER2, troughcolor=LAYER1)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.url_listbox = tk.Listbox(q_frame, font=("Consolas", 9),
                                      bg=LAYER1, fg=FG, selectbackground=BLUE,
                                      relief=tk.FLAT, bd=0, height=6,
                                      yscrollcommand=sb.set)
        self.url_listbox.pack(fill=tk.BOTH, expand=True)
        sb.config(command=self.url_listbox.yview)

        ctrl_row = tk.Frame(f, bg=BG)
        ctrl_row.pack(fill=tk.X, pady=(6, 0))
        _btn(ctrl_row, "Remove Selected", self._remove_url, kind="secondary").pack(side=tk.LEFT, padx=(0, 8))
        _btn(ctrl_row, "Clear Queue", self._clear_queue, kind="secondary").pack(side=tk.LEFT)

        # Model selector
        model_row = tk.Frame(f, bg=BG)
        model_row.pack(fill=tk.X, pady=(10, 0))
        _label(model_row, "Whisper model:", 10, FG).pack(side=tk.LEFT)
        MODELS = ["tiny", "small", "medium", "large"]
        DESCS  = {
            "tiny":   "Fastest · least accurate",
            "small":  "Fast · decent accuracy",
            "medium": "Recommended · best balance",
            "large":  "Most accurate · slowest",
        }
        self.model_desc_label = _label(model_row, DESCS.get(self.whisper_var.get(), ""), 9)
        om = tk.OptionMenu(model_row, self.whisper_var, *MODELS,
                           command=lambda m: (
                               self.model_desc_label.config(text=DESCS.get(m, "")),
                               self._save_config()
                           ))
        om.config(font=(FONT, 10), bg=LAYER2, fg=FG,
                  activebackground=LAYER1, activeforeground=FG, relief=tk.FLAT)
        om.pack(side=tk.LEFT, padx=(8, 12))
        self.model_desc_label.pack(side=tk.LEFT)

        # Output folder
        out_row = tk.Frame(f, bg=BG)
        out_row.pack(fill=tk.X, pady=(10, 0))
        _btn(out_row, "Select Output Folder", self._select_video_output, kind="secondary"
             ).pack(side=tk.LEFT, padx=(0, 12))
        self.video_out_label = _label(out_row, f"Output: {self.video_output_folder}", 9)
        self.video_out_label.pack(side=tk.LEFT)
        return f

    # ── File / folder pickers ─────────────────────────────────────────────────

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Select Documents to Convert",
            filetypes=[
                ("All Supported", "*.pdf *.docx *.pptx *.xlsx *.jpg *.jpeg *.png *.mp4 *.boxnote *.md"),
                ("All Files", "*.*"),
            ],
        )
        if files:
            self.selected_files = [f for f in files if Path(f).suffix.lower() in self.SUPPORTED_FORMATS]
            self._update_files_display()
            self._update_status()

    def select_folder(self):
        folder = filedialog.askdirectory(title="Select Source Project Folder")
        if not folder:
            return
        self.selected_folder = Path(folder)
        if not self.output_folder:
            self.output_folder = self.selected_folder / "_markdown"
        self._save_config()
        # Only auto-scan when the output folder is the default (_markdown inside source).
        # If the user has a custom output folder already set from a previous session,
        # the scan will use it correctly.  Either way, selecting the output folder
        # explicitly also triggers a fresh scan, so the user always sees accurate counts.
        self._scan_folder()

    def select_output_folder(self):
        folder = filedialog.askdirectory(title="Select Output Location")
        if folder:
            self.output_folder = Path(folder)
            self._save_config()   # persist so next startup auto-scan uses correct path
            if self.selected_folder:
                self._scan_folder()

    def select_paste_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.paste_output_folder = Path(folder)
            self.paste_out_label.config(text=f"Output: {self.paste_output_folder}")

    def _select_video_output(self):
        folder = filedialog.askdirectory(title="Select Output Folder")
        if folder:
            self.video_output_folder = Path(folder)
            self.video_out_label.config(text=f"Output: {self.video_output_folder}")

    def _browse_consol_config(self):
        path = filedialog.askopenfilename(
            title="Select Consolidation Config",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self.consol_cfg_var.set(path)

    # ── Video queue ───────────────────────────────────────────────────────────

    def _add_url(self):
        url = self.url_var.get().strip()
        if not url or url in self.video_queue:
            return
        self.video_queue.append(url)
        self.url_listbox.insert(tk.END, url)
        self.url_var.set("")
        self._update_status()

    def _remove_url(self):
        sel = self.url_listbox.curselection()
        if sel:
            idx = sel[0]
            self.url_listbox.delete(idx)
            self.video_queue.pop(idx)
            self._update_status()

    def _clear_queue(self):
        self.video_queue.clear()
        self.url_listbox.delete(0, tk.END)
        self._update_status()

    # ── Folder scan ───────────────────────────────────────────────────────────

    def _scan_folder(self):
        exclude = [p.strip() for p in self.exclude_var.get().split(",") if p.strip()]
        processor = FolderProcessor(self.selected_folder, self.output_folder,
                                    exclude_folder_patterns=exclude)
        processor.clean_orphans()
        files_to_convert, total_files, total_size = processor.scan_folder()

        if self.skip_mp4_var.get():
            files_to_convert = [f for f in files_to_convert if f.suffix.lower() != ".mp4"]
        if self.skip_large_var.get():
            try:
                threshold = float(self.skip_large_mb.get()) * 1024 * 1024
                files_to_convert = [f for f in files_to_convert if f.stat().st_size <= threshold]
            except ValueError:
                pass

        self.folder_info = {
            "files_to_convert": files_to_convert,
            "total_files": total_files,
            "total_size": total_size,
            "processor": processor,
        }
        self._update_folder_display()
        self._update_status()

    # ── Paste helpers ─────────────────────────────────────────────────────────

    def _on_paste_change(self, event=None):
        self.paste_text.edit_modified(False)
        self._update_status()

    def clear_paste(self):
        self.paste_text.delete("1.0", tk.END)
        self._update_status()

    def clear_selection(self):
        self.selected_files = []
        self.selected_folder = None
        self.output_folder = None
        self.folder_info = None
        if self.mode == "files":
            self._update_files_display()
        elif self.mode == "folder":
            self._update_folder_display()
        elif self.mode == "paste":
            self.paste_text.delete("1.0", tk.END)
        self._update_status()

    # ── Display updates ───────────────────────────────────────────────────────

    def _update_files_display(self):
        self.files_text.delete("1.0", tk.END)
        if self.selected_files:
            self.files_text.insert(tk.END, f"{len(self.selected_files)} file(s) selected:\n\n")
            for fp in self.selected_files:
                p = Path(fp)
                kb = p.stat().st_size / 1024
                self.files_text.insert(tk.END, f"  • {p.name}  ({kb:.1f} KB)\n")
        else:
            self.files_text.insert(tk.END, "No files selected\n\nClick 'Select Files' to choose documents.")

    def _update_folder_display(self):
        self.folder_text.delete("1.0", tk.END)
        if self.selected_folder and self.folder_info:
            info = self.folder_info
            mb = info["total_size"] / (1024 * 1024)
            self.folder_text.insert(tk.END, f"Source:  {self.selected_folder}\n")
            self.folder_text.insert(tk.END, f"Output:  {self.output_folder}\n\n")
            self.folder_text.insert(tk.END, f"Total files:     {info['total_files']}\n")
            self.folder_text.insert(tk.END, f"To convert:      {len(info['files_to_convert'])}\n")
            already = info["total_files"] - len(info["files_to_convert"])
            if already:
                self.folder_text.insert(tk.END, f"Already done:    {already} (skipped)\n")
            self.folder_text.insert(tk.END, f"Total size:      {mb:.1f} MB\n")
        else:
            self.folder_text.insert(tk.END, "No folder selected\n\nClick 'Select Source Folder' to begin.")

    def _update_status(self):
        mode = self.mode
        has = False
        if mode == "files" and self.selected_files:
            has = True
            self.status_label.config(text=f"Ready — {len(self.selected_files)} file(s) selected")
        elif mode == "folder" and self.selected_folder and self.folder_info:
            has = True
            n = len(self.folder_info["files_to_convert"])
            self.status_label.config(text=f"Ready — {self.selected_folder.name}  ({n} files to convert)")
        elif mode == "paste":
            content = self.paste_text.get("1.0", tk.END).strip()
            if content:
                has = True
                self.status_label.config(text=f"Ready — {len(content.split())} words")
        elif mode == "video_url" and self.video_queue:
            has = True
            self.status_label.config(text=f"Ready — {len(self.video_queue)} URL(s) queued")
        if not has:
            self.status_label.config(text="Select a mode and input to begin")
        self.convert_btn.config(state=tk.NORMAL if has else tk.DISABLED)

    # ── Conversion ────────────────────────────────────────────────────────────

    def start_conversion(self):
        self.convert_btn.config(state=tk.DISABLED)
        self.progress_bar["value"] = 0
        self.progress_label.config(text="Starting…")
        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _run_conversion(self):
        try:
            if self.mode == "files":
                self._convert_files()
            elif self.mode == "folder":
                self._convert_folder()
            elif self.mode == "paste":
                self._convert_paste()
            elif self.mode == "video_url":
                self._convert_video()
        except Exception as e:
            logging.error(f"Conversion error: {e}")
        self.root.after(0, self._show_results)

    def _progress(self, i, total, name):
        pct = round(i / total * 100) if total else 100
        self.progress_bar["value"] = pct
        self.progress_label.config(text=f"Converting {i}/{total}: {name}")
        self.status_label.config(text=f"Converting  {i} / {total}  ({pct}%)  —  {name}")
        self.root.update_idletasks()

    def _convert_files(self):
        self.conversion_results = []
        total = len(self.selected_files)
        for i, fp in enumerate(self.selected_files, 1):
            path = Path(fp)
            self._progress(i, total, path.name)
            out = path.with_suffix(".md")
            try:
                ext = path.suffix.lower()
                if ext == ".pdf":    convert_pdf_to_markdown(fp, out)
                elif ext == ".docx": convert_docx_to_markdown(fp, out)
                elif ext == ".pptx": convert_pptx_to_markdown(fp, out)
                elif ext == ".xlsx": convert_xlsx_to_markdown(fp, out)
                elif ext in (".jpg", ".jpeg", ".png"): convert_image_to_markdown(fp, out)
                elif ext == ".boxnote": convert_boxnote_to_markdown(path, out)
                elif ext == ".md":   copy_markdown_file(path, out)
                elif ext == ".mp4":  convert_mp4_to_markdown(path, out)
                self.conversion_results.append({"file": path.name, "status": "success", "output": str(out)})
            except Exception as e:
                self.conversion_results.append({"file": path.name, "status": "error", "error": str(e)})

    def _convert_folder(self):
        self.conversion_results = []
        processor = self.folder_info["processor"]
        files = self.folder_info["files_to_convert"]
        total = len(files)
        converted = []
        for i, src in enumerate(files, 1):
            rel = str(src.relative_to(self.selected_folder))
            self._progress(i, total, rel)
            out = processor.get_output_path(src)
            try:
                ext = src.suffix.lower()
                if ext == ".pdf":    convert_pdf_to_markdown(str(src), out)
                elif ext == ".docx": convert_docx_to_markdown(str(src), out)
                elif ext == ".pptx": convert_pptx_to_markdown(str(src), out)
                elif ext == ".xlsx": convert_xlsx_to_markdown(str(src), out)
                elif ext in (".jpg", ".jpeg", ".png"): convert_image_to_markdown(str(src), out)
                elif ext == ".boxnote": convert_boxnote_to_markdown(src, out)
                elif ext == ".md":   copy_markdown_file(src, out)
                elif ext == ".mp4":  convert_mp4_to_markdown(src, out)
                processor.update_file_metadata(src, out, True)
                converted.append((src, out, True))
                self.conversion_results.append({"file": rel, "status": "success", "output": str(out)})
            except Exception as e:
                processor.update_file_metadata(src, None, False, str(e))
                converted.append((src, None, False))
                self.conversion_results.append({"file": rel, "status": "error", "error": str(e)})
        try:
            processor.create_index(converted)
        except Exception as e:
            logging.error(f"Index creation failed: {e}")
        processor.finalize()

        if self.auto_consol_var.get():
            self._run_consolidator(self.output_folder)

    def _convert_paste(self):
        self.conversion_results = []
        content = self.paste_text.get("1.0", tk.END).strip()
        filename = (self.paste_filename.get().strip() or "meeting_transcript").removesuffix(".md")
        out_dir = self.paste_output_folder
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{filename}.md"
        try:
            patterns = [
                r"\d{1,2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}\.\d{3}",
                r"<v\s+[^>]+>", r"\[.*?\]:\s*\d{1,2}:\d{2}",
            ]
            is_teams = any(re.search(p, content) for p in patterns)
            if is_teams:
                lines_out = ["# Meeting Transcript", "", f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
                             "**Source:** Microsoft Teams", "", "---", ""]
                speaker = None
                for line in content.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    m = re.match(r"\[([^\]]+)\]:\s*\d{1,2}:\d{2}", line) or re.match(r"<v\s+([^>]+)>", line)
                    if m:
                        s = m.group(1).strip()
                        if s != speaker:
                            speaker = s
                            lines_out += ["", f"## {speaker}", ""]
                        line = re.sub(r"\[([^\]]+)\]:\s*\d{1,2}:\d{2}\s*", "", line)
                        line = re.sub(r"<v\s+([^>]+)>", "", line)
                    if line:
                        lines_out.append(line)
                md = "\n".join(lines_out)
            else:
                md = f"# {filename.replace('_', ' ').title()}\n\n**Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n---\n\n{content}\n"
            out.write_text(md, encoding="utf-8")
            self.conversion_results.append({"file": filename, "status": "success", "output": str(out)})
        except Exception as e:
            self.conversion_results.append({"file": filename, "status": "error", "error": str(e)})

    def _convert_video(self):
        self.conversion_results = []
        total = len(self.video_queue)
        for i, url in enumerate(self.video_queue, 1):
            self._progress(i, total, url[:60])
            try:
                result = convert_video_url_to_markdown(
                    url, self.video_output_folder,
                    whisper_model=self.whisper_var.get(),
                )
                self.conversion_results.append({"file": url, "status": "success", "output": str(result)})
            except Exception as e:
                self.conversion_results.append({"file": url, "status": "error", "error": str(e)})

    def _run_consolidator(self, output_folder):
        script = Path(__file__).parent / "consolidate_by_initiative.py"
        if not script.exists():
            return
        cfg = self.consol_cfg_var.get().strip()
        if not cfg:
            candidates = [f for f in output_folder.glob("*.json")
                          if not f.name.startswith(".")]
            if candidates:
                cfg = str(candidates[0])
        cmd = [sys.executable, str(script), str(output_folder), str(output_folder / "_CONSOLIDATED")]
        if cfg:
            cmd += ["--config", cfg]
        subprocess.run(cmd, capture_output=True, timeout=300)

    # ── Results ───────────────────────────────────────────────────────────────

    def _show_results(self):
        self.progress_label.config(text="Conversion complete!")
        self.convert_btn.config(state=tk.NORMAL)

        ok  = [r for r in self.conversion_results if r["status"] == "success"]
        err = [r for r in self.conversion_results if r["status"] == "error"]

        msg = f"Conversion Complete!\n\n✓ Successful: {len(ok)}\n"
        if err:
            msg += f"✗ Failed:     {len(err)}\n\nFailed files:\n"
            for r in err:
                e = r["error"]
                if len(e) > 60:
                    e = e[:57] + "..."
                msg += f"  • {Path(r['file']).name}: {e}\n"

        if self.mode == "folder":
            out = self.output_folder or (self.selected_folder / "_markdown")
            msg += f"\nOutput: {out}\nSee _INDEX.md for navigation."
        elif ok:
            msg += f"\nOutput: {ok[0]['output']}"

        messagebox.showinfo("Results", msg)
        self.clear_selection()

    @staticmethod
    def _fmt_size(b):
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024:
                return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} TB"


def main():
    root = tk.Tk()
    AppV2(root)
    root.mainloop()


if __name__ == "__main__":
    main()
