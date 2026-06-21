"""
WAV Compressor
──────────────
Keeps files as .wav so all existing metadata (title, artist, album, comments,
etc.) is preserved natively without any re-encoding pipeline.

File size is reduced by stepping down audio parameters in quality order:
  1.  44100 Hz  stereo  16-bit   (CD quality — keep if already fits)
  2.  22050 Hz  stereo  16-bit
  3.  22050 Hz  mono    16-bit
  4.  16000 Hz  mono    16-bit
  5.  11025 Hz  mono    16-bit
  6.  11025 Hz  mono    8-bit
  7.   8000 Hz  mono    16-bit
  8.   8000 Hz  mono    8-bit
  9.   6000 Hz  mono    8-bit
  10.  4000 Hz  mono    8-bit

The first step whose output is under MAX_SIZE_BYTES wins.
Files already under the limit are left completely untouched.

Naming / renaming:
  • Finds track0.wav, track1.wav … first (zero-based), then any other .wav
    files, assigning them the next track numbers alphabetically.
  • Non-track .wav files are renamed to track<N>.wav before processing.
  • Originals are backed up to original_backup/ BEFORE any rename or change.

Requires: ffmpeg (auto-downloaded if missing), ffprobe (same bundle).
UI: Tkinter folder browser + rename-preview list + live log + progress bar.
"""

import os
import json
import math
import shutil
import subprocess
import threading
import platform
import urllib.request
import zipfile
import tarfile
import stat
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from pathlib import Path
import re

# ─── Constants ────────────────────────────────────────────────────────────────

MAX_SIZE_BYTES = 4 * 1024 * 1024          # 4 MB hard limit
BACKUP_FOLDER  = "original_backup"
TRACK_RE       = re.compile(r"^track(\d+)$", re.IGNORECASE)

# Reduction ladder: (sample_rate, channels, bit_depth)
# Ordered best → most-compressed.  We stop at the first that fits.
QUALITY_LADDER = [
    (44100, 2, 16),
    (22050, 2, 16),
    (22050, 1, 16),
    (16000, 1, 16),
    (11025, 1, 16),
    (11025, 1,  8),
    ( 8000, 1, 16),
    ( 8000, 1,  8),
    ( 6000, 1,  8),
    ( 4000, 1,  8),
]

FFMPEG_URLS = {
    "Windows": "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "Darwin":  "https://evermeet.cx/ffmpeg/getrelease/zip",
    "Linux":   "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
}


# ─── ffmpeg helpers ───────────────────────────────────────────────────────────

def _find_bin(name: str) -> "str | None":
    script_dir = Path(__file__).parent
    for candidate in (name, name + ".exe"):
        p = script_dir / candidate
        if p.exists():
            return str(p)
    return shutil.which(name)

def find_ffmpeg()  -> "str | None": return _find_bin("ffmpeg")
def find_ffprobe() -> "str | None": return _find_bin("ffprobe")


def download_ffmpeg(log) -> str:
    system     = platform.system()
    url        = FFMPEG_URLS.get(system)
    script_dir = Path(__file__).parent

    if not url:
        raise RuntimeError(f"Unsupported OS: {system}")

    is_zip       = url.endswith(".zip")
    archive_path = script_dir / ("ffmpeg_dl.zip" if is_zip else "ffmpeg_dl.tar.xz")

    log(f"Downloading ffmpeg for {system}…")
    log(f"  Source: {url}")

    def reporthook(count, block_size, total_size):
        if total_size > 0:
            pct = min(100, count * block_size * 100 // total_size)
            log(f"  Download progress: {pct}%", replace_last=True)

    urllib.request.urlretrieve(url, archive_path, reporthook)  # nosec B310 - url is from the hardcoded FFMPEG_URLS map, not user input
    log("  Download complete.")
    log("Extracting binaries…")

    targets   = {"ffmpeg", "ffmpeg.exe", "ffprobe", "ffprobe.exe"}
    extracted = []

    if is_zip:
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.namelist():
                if Path(member).name in targets and "/bin/" in member:
                    dest = script_dir / Path(member).name
                    with zf.open(member) as src, open(dest, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    extracted.append(str(dest))
    else:
        with tarfile.open(archive_path, "r:xz") as tf:
            for member in tf.getmembers():
                if Path(member.name).name in {"ffmpeg", "ffprobe"} \
                        and member.isfile():
                    member.name = Path(member.name).name
                    tf.extract(member, script_dir)
                    extracted.append(str(script_dir / member.name))

    archive_path.unlink(missing_ok=True)

    ffmpeg_bin = next((p for p in extracted if Path(p).stem == "ffmpeg"), None)
    if not ffmpeg_bin or not Path(ffmpeg_bin).exists():
        raise RuntimeError("Could not extract ffmpeg binary.")

    if system in ("Darwin", "Linux"):
        for p in extracted:
            st = os.stat(p)
            os.chmod(p, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    log(f"ffmpeg ready: {ffmpeg_bin}")
    return ffmpeg_bin


# ─── Audio properties ─────────────────────────────────────────────────────────

def get_audio_props(ffprobe: str, src: Path) -> dict:
    """Return sample_rate, channels, bits_per_sample, duration from ffprobe."""
    try:
        r = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_streams", "-show_format", str(src)],
            capture_output=True, text=True, timeout=15)
        d = json.loads(r.stdout)
        s = next((s for s in d.get("streams", [])
                  if s.get("codec_type") == "audio"), {})
        return {
            "sample_rate":    int(s.get("sample_rate", 44100)),
            "channels":       int(s.get("channels", 2)),
            "bits_per_sample": int(s.get("bits_per_sample", 16) or 16),
            "duration":       float(s.get("duration")
                                    or d.get("format", {}).get("duration", 0)),
        }
    except Exception:
        return {"sample_rate": 44100, "channels": 2,
                "bits_per_sample": 16, "duration": 0}


def predicted_wav_size(sample_rate: int, channels: int,
                        bit_depth: int, duration: float) -> int:
    """Estimate output .wav size in bytes (PCM data + 44-byte header)."""
    return int(sample_rate * channels * (bit_depth // 8) * duration) + 44


# ─── Compression ──────────────────────────────────────────────────────────────

def compress_wav(ffmpeg: str, src: Path, log) -> "tuple[bool, str]":
    """
    Rewrite src in-place at the best quality that fits under MAX_SIZE_BYTES.
    Returns (changed: bool, description: str).
    If already small enough, returns (False, reason) with no file changes.
    """
    current_size = src.stat().st_size
    if current_size <= MAX_SIZE_BYTES:
        mb = current_size / 1024 / 1024
        return False, f"already {mb:.2f} MB — no change needed"

    tmp = src.with_suffix(".tmp.wav")

    for sr, ch, bd in QUALITY_LADDER:
        predicted = predicted_wav_size(sr, ch, bd,
                        # We don't have duration yet cheaply, so try and check
                        9999)  # placeholder — we measure after encode below
        # Build ffmpeg command
        # ac = channels, ar = sample rate, sample_fmt = pcm encoding
        sample_fmt = f"pcm_u8" if bd == 8 else "pcm_s16le"
        cmd = [
            ffmpeg, "-y",
            "-i", str(src),
            "-ar", str(sr),
            "-ac", str(ch),
            "-c:a", sample_fmt,
            # Carry all metadata chunks through
            "-map_metadata", "0",
            "-write_bext", "1",   # preserve BWF/BEXT chunk if present
            str(tmp),
        ]
        log(f"    Trying {sr} Hz / {'stereo' if ch == 2 else 'mono'} / {bd}-bit…")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            log(f"    ffmpeg error: {r.stderr[-300:].strip()}")
            tmp.unlink(missing_ok=True)
            continue

        actual_size = tmp.stat().st_size
        mb = actual_size / 1024 / 1024
        log(f"    → {mb:.2f} MB")

        if actual_size <= MAX_SIZE_BYTES:
            # Replace original with compressed version
            tmp.replace(src)
            desc = (f"{sr} Hz / {'stereo' if ch==2 else 'mono'} / {bd}-bit "
                    f"({mb:.2f} MB)")
            return True, desc
        else:
            tmp.unlink(missing_ok=True)

    # Nothing worked — leave original intact
    return False, "could not fit under 4 MB at any quality step"


# ─── File discovery ───────────────────────────────────────────────────────────

def discover_files(folder: str):
    """
    Returns:
        ordered   – list[Path] already named track<N>.wav, sorted by N
        to_rename – list[(old_path, new_path)] for other .wav files
    """
    folder_path = Path(folder)
    backup_path = folder_path / BACKUP_FOLDER

    all_wav = sorted(
        [f for f in folder_path.iterdir()
         if f.is_file()
         and f.suffix.lower() == ".wav"
         and not f.resolve().is_relative_to(backup_path.resolve())],
        key=lambda f: f.name.lower(),
    )

    track_map: dict[int, Path] = {}
    other: list[Path] = []

    for f in all_wav:
        m = TRACK_RE.match(f.stem)
        if m:
            track_map[int(m.group(1))] = f
        else:
            other.append(f)

    ordered = [track_map[n] for n in sorted(track_map)]

    next_n = (max(track_map.keys()) + 1) if track_map else 0
    to_rename: list[tuple[Path, Path]] = []
    for f in other:
        new = folder_path / f"track{next_n}.wav"
        while new.exists() and new != f:
            next_n += 1
            new = folder_path / f"track{next_n}.wav"
        to_rename.append((f, new))
        next_n += 1

    return ordered, to_rename


# ─── GUI ──────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("WAV Compressor")
        self.resizable(True, True)
        self.minsize(700, 580)
        self.configure(bg="#1a1a2e")
        self._last_was_replace = False
        self._build_ui()

    def _build_ui(self):
        BG    = "#1a1a2e"
        PANEL = "#16213e"
        ACC   = "#e94560"
        TEXT  = "#eaeaea"
        MUTED = "#8892a4"
        ENTRY = "#0f3460"
        GREEN = "#a8d8a8"
        FH    = ("Consolas", 13, "bold")
        FN    = ("Consolas", 10)

        tk.Frame(self, bg=ACC, height=6).pack(fill="x")

        tf = tk.Frame(self, bg=BG, pady=16)
        tf.pack(fill="x", padx=24)
        tk.Label(tf, text="◈ WAV Compressor",
                 font=("Consolas", 20, "bold"), bg=BG, fg=ACC).pack(side="left")
        tk.Label(tf, text="stays .wav · metadata safe · under 4 MB",
                 font=FN, bg=BG, fg=MUTED).pack(side="left", padx=14)

        # Folder row
        ff = tk.Frame(self, bg=PANEL, pady=12, padx=16)
        ff.pack(fill="x", padx=24, pady=(0, 4))
        tk.Label(ff, text="Folder", font=FH, bg=PANEL, fg=TEXT,
                 width=8, anchor="w").pack(side="left")
        self.folder_var = tk.StringVar()
        self.folder_var.trace_add("write", lambda *_: self._on_folder_typed())
        tk.Entry(ff, textvariable=self.folder_var, font=FN,
                 bg=ENTRY, fg=TEXT, insertbackground=TEXT,
                 relief="flat", bd=0).pack(
            side="left", fill="x", expand=True, ipady=5, padx=(8, 8))
        tk.Button(ff, text="Browse…", font=FN,
                  bg=ACC, fg="#fff", relief="flat", cursor="hand2",
                  activebackground="#c73652",
                  command=self._browse, padx=10, pady=4).pack(side="left")

        # File list
        lf = tk.Frame(self, bg=BG, padx=24, pady=8)
        lf.pack(fill="x")
        hrow = tk.Frame(lf, bg=BG)
        hrow.pack(fill="x")
        tk.Label(hrow, text="  Filename",
                 font=("Consolas", 9, "bold"), bg=BG, fg=MUTED,
                 width=38, anchor="w").pack(side="left")
        tk.Label(hrow, text="Size",
                 font=("Consolas", 9, "bold"), bg=BG, fg=MUTED,
                 width=10, anchor="w").pack(side="left")
        tk.Label(hrow, text="Rename?",
                 font=("Consolas", 9, "bold"), bg=BG, fg=MUTED,
                 anchor="w").pack(side="left")

        self.file_listbox = tk.Listbox(
            lf, font=FN, bg=PANEL, fg=TEXT,
            selectbackground=ACC, relief="flat",
            height=6, bd=0, highlightthickness=1,
            highlightcolor=ACC, highlightbackground=MUTED)
        self.file_listbox.pack(fill="x", pady=(2, 0))

        # Progress
        pf = tk.Frame(self, bg=BG, padx=24, pady=8)
        pf.pack(fill="x")
        self.progress = ttk.Progressbar(pf, mode="determinate")
        sty = ttk.Style(self)
        sty.theme_use("default")
        sty.configure("TProgressbar", troughcolor=PANEL,
                       background=ACC, thickness=10)
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(pf, textvariable=self.status_var, font=FN,
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", pady=(4, 0))

        # Log
        logf = tk.Frame(self, bg=BG, padx=24)
        logf.pack(fill="both", expand=True, pady=(0, 6))
        tk.Label(logf, text="Log", font=FH, bg=BG, fg=TEXT).pack(anchor="w")
        self.log_text = tk.Text(
            logf, font=("Consolas", 9), bg=PANEL, fg=GREEN,
            insertbackground=TEXT, relief="flat", bd=0,
            state="disabled", wrap="word", height=10)
        sb = tk.Scrollbar(logf, command=self.log_text.yview,
                          bg=PANEL, troughcolor=BG, activebackground=ACC)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

        # Run button
        bf = tk.Frame(self, bg=BG, padx=24, pady=12)
        bf.pack(fill="x")
        self.run_btn = tk.Button(
            bf, text="▶  Process Files",
            font=("Consolas", 12, "bold"),
            bg=ACC, fg="#fff", relief="flat", cursor="hand2",
            activebackground="#c73652",
            command=self._start, pady=10)
        self.run_btn.pack(fill="x")

    # ── Events ───────────────────────────────────────────────────────────────

    def _browse(self):
        folder = filedialog.askdirectory(title="Select folder of .wav files")
        if folder:
            self.folder_var.set(folder)
            self._refresh_list(folder)

    def _on_folder_typed(self):
        folder = self.folder_var.get().strip()
        if os.path.isdir(folder):
            self._refresh_list(folder)

    def _refresh_list(self, folder):
        self.file_listbox.delete(0, "end")
        try:
            ordered, to_rename = discover_files(folder)
        except Exception as e:
            self.file_listbox.insert("end", f"  Error: {e}")
            return

        rename_map = {old: new for old, new in to_rename}
        all_files  = ordered + [old for old, _ in to_rename]

        if not all_files:
            self.file_listbox.insert("end", "  (no .wav files found)")
            return

        for f in all_files:
            try:
                mb = f.stat().st_size / 1024 / 1024
                size_str = f"{mb:.2f} MB"
                flag     = "⚠ over 4MB" if mb > 4 else "✓ ok"
            except OSError:
                size_str = "?"
                flag     = ""

            if f in rename_map:
                new      = rename_map[f]
                flag    += f"  →  {new.name}"

            line = f"  {f.name:<36}{size_str:<12}{flag}"
            self.file_listbox.insert("end", line)

    def _log(self, msg: str, replace_last=False):
        def _do():
            self.log_text.configure(state="normal")
            if replace_last and self._last_was_replace:
                self.log_text.delete("end-2l", "end-1c")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
            self._last_was_replace = replace_last
        self.after(0, _do)

    def _set_status(self, msg: str):
        self.after(0, lambda: self.status_var.set(msg))

    def _set_progress(self, val: float):
        self.after(0, lambda: self.progress.configure(value=val))

    def _start(self):
        folder = self.folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Please select a valid folder first.")
            return
        self.run_btn.configure(state="disabled")
        threading.Thread(target=self._pipeline, args=(folder,),
                         daemon=True).start()

    # ── Pipeline ─────────────────────────────────────────────────────────────

    def _pipeline(self, folder: str):
        log = self._log

        # 1. ffmpeg
        self._set_status("Locating ffmpeg…")
        log("─── Step 1: Locating ffmpeg ───")
        ffmpeg = find_ffmpeg()
        if ffmpeg:
            log(f"  ffmpeg : {ffmpeg}")
        else:
            log("  Not found — downloading…")
            try:
                ffmpeg = download_ffmpeg(log)
            except Exception as e:
                log(f"  ERROR: {e}")
                self._set_status("Failed.")
                self.after(0, lambda: self.run_btn.configure(state="normal"))
                return

        ffprobe = find_ffprobe()
        log(f"  ffprobe: {ffprobe or '(not found — size predictions skipped)'}")

        # 2. Discover
        log("\n─── Step 2: Scanning for .wav files ───")
        try:
            ordered, to_rename = discover_files(folder)
        except Exception as e:
            log(f"  ERROR: {e}")
            self._set_status("Failed.")
            self.after(0, lambda: self.run_btn.configure(state="normal"))
            return

        all_src = ordered + [old for old, _ in to_rename]
        if not all_src:
            log("  No .wav files found.")
            self._set_status("No files found.")
            self.after(0, lambda: self.run_btn.configure(state="normal"))
            return

        log(f"  {len(all_src)} file(s)"
            + (f", {len(to_rename)} will be renamed" if to_rename else ""))

        # 3. Backup FIRST — before rename or any modification
        log(f"\n─── Step 3: Backing up originals → {BACKUP_FOLDER}/ ───")
        backup_dir = Path(folder) / BACKUP_FOLDER
        backup_dir.mkdir(exist_ok=True)
        for f in all_src:
            dest = backup_dir / f.name
            if dest.exists():
                log(f"  Already backed up: {f.name}")
            else:
                shutil.copy2(f, dest)
                log(f"  Saved: {f.name}")

        # 4. Rename non-track files
        if to_rename:
            log(f"\n─── Step 4: Renaming to track<N>.wav ───")
        final_files: list[Path] = list(ordered)
        for old, new in to_rename:
            if old.exists():
                old.rename(new)
                log(f"  {old.name}  →  {new.name}")
                final_files.append(new)
            else:
                log(f"  WARN: {old.name} not found, skipping.")

        # 5. Compress oversized files
        log("\n─── Step 5: Compressing oversized files ───")
        total      = len(final_files)
        compressed = 0
        skipped    = 0
        failed     = []

        for idx, src in enumerate(final_files, 1):
            self._set_status(f"Processing {idx}/{total}: {src.name}")
            self._set_progress((idx - 1) / total * 100)

            size_mb = src.stat().st_size / 1024 / 1024
            log(f"\n[{idx}/{total}] {src.name}  ({size_mb:.2f} MB)")

            changed, desc = compress_wav(ffmpeg, src, log)
            if changed:
                log(f"  ✓ Compressed → {desc}")
                compressed += 1
            elif "already" in desc:
                log(f"  ✓ {desc}")
                skipped += 1
            else:
                log(f"  ✗ {desc}")
                failed.append(src.name)

        self._set_progress(100)

        # 6. Summary
        log("\n─── Summary ───")
        log(f"  Already OK  : {skipped}")
        log(f"  Compressed  : {compressed}")
        if to_rename:
            log(f"  Renamed     : {len(to_rename)}")
        if failed:
            log(f"  Failed      : {len(failed)}")
            for fn in failed:
                log(f"    • {fn}")
        log(f"  Backup      : {backup_dir}")
        log("All done!")

        status = f"Done! {compressed} compressed, {skipped} already OK."
        if failed:
            status += f"  {len(failed)} failed."
        self._set_status(status)
        self.after(0, lambda: self.run_btn.configure(state="normal"))
        self.after(0, lambda: messagebox.showinfo(
            "Complete",
            f"{compressed} file(s) compressed.\n"
            f"{skipped} already under 4 MB.\n"
            + (f"{len(to_rename)} file(s) renamed.\n" if to_rename else "")
            + (f"{len(failed)} failed.\n" if failed else "")
            + f"\nOriginals backed up to:\n{backup_dir}"
        ))


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()