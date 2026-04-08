"""
Roblox Audio Converter
======================
Downloads audio from Roblox asset links (authenticated via .ROBLOSECURITY),
adjusts playback speed, and exports to .ogg via ffmpeg.

Dependencies (auto-managed):
  - ffmpeg   : downloaded from https://github.com/yt-dlp/FFmpeg-Builds
  - requests : pip install requests

HOW TO GET YOUR .ROBLOSECURITY COOKIE
--------------------------------------
1. Log into roblox.com in your browser.
2. Open DevTools (F12) → Application tab → Cookies → https://www.roblox.com
3. Find ".ROBLOSECURITY" and copy its Value.
   (Tip: use an alt account to avoid risk.)
"""

import os
import sys
import stat
import shutil
import zipfile
import tarfile
import platform
import threading
import subprocess
import urllib.request
import tkinter as tk
from tkinter import filedialog, messagebox

import requests


# ── ffmpeg bootstrap ──────────────────────────────────────────────────────────

FFMPEG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg_bin")

FFMPEG_URLS = {
    "Windows": "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    "Linux":   "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz",
    "Darwin":  "https://github.com/yt-dlp/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-macos64-gpl.zip",
}

def ffmpeg_exe():
    name = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    local = os.path.join(FFMPEG_DIR, name)
    if os.path.isfile(local):
        return local
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    return None

def download_ffmpeg(progress_cb=None):
    system = platform.system()
    url = FFMPEG_URLS.get(system)
    if not url:
        raise RuntimeError(f"No ffmpeg build available for {system}.")
    os.makedirs(FFMPEG_DIR, exist_ok=True)
    archive = os.path.join(FFMPEG_DIR, url.split("/")[-1])
    if progress_cb:
        progress_cb("Downloading ffmpeg ...")
    with urllib.request.urlopen(url) as resp, open(archive, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if progress_cb and total:
                progress_cb(f"Downloading ffmpeg ... {downloaded * 100 // total}%")
    if progress_cb:
        progress_cb("Extracting ffmpeg ...")
    if archive.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(FFMPEG_DIR)
    else:
        with tarfile.open(archive) as t:
            t.extractall(FFMPEG_DIR)
    exe_name = "ffmpeg.exe" if system == "Windows" else "ffmpeg"
    found = None
    for root, _, files in os.walk(FFMPEG_DIR):
        if exe_name in files:
            found = os.path.join(root, exe_name)
            break
    if not found:
        raise RuntimeError("ffmpeg binary not found after extraction.")
    dest = os.path.join(FFMPEG_DIR, exe_name)
    shutil.copy2(found, dest)
    os.chmod(dest, os.stat(dest).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    os.remove(archive)
    if progress_cb:
        progress_cb("ffmpeg ready")
    return dest


# ── Roblox helpers ────────────────────────────────────────────────────────────

def extract_asset_id(url: str) -> str:
    url = url.strip()
    if "id=" in url:
        return url.split("id=")[-1].split("&")[0].strip()
    if url.isdigit():
        return url
    raise ValueError(f"Cannot parse asset ID from: {url!r}")


def resolve_roblox_audio(asset_id: str, cookie: str,
                         place_id: str = "", progress_cb=None) -> bytes:
    """
    Download raw audio bytes for a Roblox asset.
    Requires a valid .ROBLOSECURITY session cookie.
    """
    if not cookie.strip():
        raise ValueError(
            "No .ROBLOSECURITY cookie provided.\n"
            "Audio assets require authentication -- paste your cookie in the field above."
        )

    session = requests.Session()
    session.cookies.set(".ROBLOSECURITY", cookie.strip(),
                        domain=".roblox.com", path="/")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Referer": "https://www.roblox.com/",
    }
    if place_id.strip():
        headers["Roblox-Place-Id"] = place_id.strip()

    url = f"https://assetdelivery.roblox.com/v1/asset/?id={asset_id}"
    if progress_cb:
        progress_cb(f"Fetching asset {asset_id} ...")

    resp = session.get(url, headers=headers, allow_redirects=True, timeout=30)

    # Some responses return a JSON envelope with a CDN location instead of raw bytes
    if "application/json" in resp.headers.get("Content-Type", ""):
        try:
            data = resp.json()
        except Exception:
            data = {}
        location = data.get("location") or data.get("Location")
        if location:
            if progress_cb:
                progress_cb("Following CDN redirect ...")
            resp = session.get(location, headers=headers, timeout=30)
        else:
            errors = data.get("errors", [{}])
            msg = errors[0].get("message", str(data)) if errors else str(data)
            raise RuntimeError(f"Roblox API error: {msg}")

    if resp.status_code == 401:
        raise RuntimeError(
            "401 Unauthorized -- your .ROBLOSECURITY cookie is invalid or expired.\n"
            "Re-copy it from your browser and try again."
        )
    if resp.status_code == 403:
        raise RuntimeError(
            "403 Forbidden -- you don't have permission to access this asset.\n"
            "Make sure your account owns or has access to this audio."
        )
    resp.raise_for_status()

    if len(resp.content) < 16:
        raise RuntimeError("Response too small -- asset may not be audio or is unavailable.")

    if progress_cb:
        progress_cb(f"Downloaded {len(resp.content):,} bytes")
    return resp.content


# ── ffmpeg conversion ─────────────────────────────────────────────────────────

def _build_atempo_chain(speed: float) -> list:
    """Chain atempo stages; each must be in the range 0.5-2.0."""
    filters = []
    remaining = speed
    while remaining > 2.0:
        filters.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        filters.append(0.5)
        remaining /= 0.5
    filters.append(round(remaining, 6))
    return filters


def convert_audio(raw_bytes: bytes, speed: float, out_path: str,
                  progress_cb=None):
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg not found. Use the Download button first.")

    af_str = ",".join(f"atempo={v}" for v in _build_atempo_chain(speed))
    cmd = [exe, "-y", "-i", "pipe:0", "-vn",
           "-af", af_str, "-c:a", "libvorbis", "-q:a", "5", out_path]

    if progress_cb:
        progress_cb(f"Converting (speed x{speed:.2f}) ...")

    proc = subprocess.run(cmd, input=raw_bytes, capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="replace")
        raise RuntimeError(f"ffmpeg error:\n{err[-800:]}")

    if progress_cb:
        progress_cb(f"Saved -> {os.path.basename(out_path)}")


# ── GUI ───────────────────────────────────────────────────────────────────────

DARK_BG  = "#12111A"
PANEL_BG = "#1C1B28"
ACCENT   = "#7C6AF7"
ACCENT2  = "#C084FC"
TEXT     = "#E8E6F0"
SUBTEXT  = "#8B89A0"
SUCCESS  = "#4ADE80"
ERROR    = "#F87171"
WARN     = "#FBBF24"
BORDER   = "#2E2C42"

IS_WIN    = platform.system() == "Windows"
FONT_MONO = ("Consolas", 10) if IS_WIN else ("Menlo", 10)
FONT_UI   = ("Segoe UI", 10) if IS_WIN else ("Helvetica Neue", 10)
FONT_HEAD = ("Segoe UI Semibold", 11) if IS_WIN else ("Helvetica Neue", 11, "bold")
FONT_BIG  = ("Segoe UI Semibold", 14) if IS_WIN else ("Helvetica Neue", 14, "bold")


def _btn(parent, text, command, bg=None, fg="white", **kw):
    return tk.Button(parent, text=text, command=command,
                     bg=bg or ACCENT, fg=fg,
                     activebackground=ACCENT2, activeforeground="white",
                     relief="flat", cursor="hand2",
                     font=FONT_UI, padx=10, pady=3, **kw)


def _label(parent, text, fg=None, font=None, **kw):
    return tk.Label(parent, text=text, bg=DARK_BG,
                    fg=fg or TEXT, font=font or FONT_UI, **kw)


def _entry(parent, textvariable=None, width=42, show=""):
    return tk.Entry(parent, textvariable=textvariable,
                    bg=PANEL_BG, fg=TEXT, insertbackground=ACCENT,
                    relief="flat", font=FONT_MONO,
                    bd=0, highlightthickness=1,
                    highlightbackground=BORDER, highlightcolor=ACCENT,
                    width=width, show=show)


def _sep(parent):
    return tk.Frame(parent, bg=BORDER, height=1)


class CookieHelpDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("How to get your .ROBLOSECURITY cookie")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self.grab_set()

        tk.Label(self, text="Getting your .ROBLOSECURITY cookie",
                 bg=DARK_BG, fg=TEXT, font=FONT_BIG,
                 pady=12, padx=20).pack(anchor="w")
        tk.Label(self,
                 text="  Warning: never share this with anyone. Use an alt account for safety.",
                 bg="#2A1F10", fg=WARN, font=FONT_UI,
                 padx=16, pady=6).pack(fill="x")

        steps = [
            ("1", "Log into", "roblox.com", "in your browser."),
            ("2", "Press", "F12", "to open Developer Tools."),
            ("3", "Go to the", "Application", "tab (Chrome/Edge) or Storage (Firefox)."),
            ("4", "Open", "Cookies > https://www.roblox.com", "."),
            ("5", "Find", ".ROBLOSECURITY", "and copy its full Value."),
            ("6", "Paste it into the Cookie field in the main window.", "", ""),
        ]

        body = tk.Frame(self, bg=DARK_BG, padx=20, pady=14)
        body.pack()
        for num, pre, hl, post in steps:
            row = tk.Frame(body, bg=DARK_BG)
            row.pack(anchor="w", pady=2)
            tk.Label(row, text=f"  {num}. ", bg=DARK_BG, fg=ACCENT,
                     font=FONT_UI).pack(side="left")
            tk.Label(row, text=pre + " ", bg=DARK_BG, fg=TEXT,
                     font=FONT_UI).pack(side="left")
            if hl:
                tk.Label(row, text=hl + " ", bg=PANEL_BG, fg=ACCENT2,
                         font=FONT_MONO, padx=4).pack(side="left")
            if post:
                tk.Label(row, text=post, bg=DARK_BG, fg=TEXT,
                         font=FONT_UI).pack(side="left")

        _btn(self, "Close", self.destroy, bg=PANEL_BG, fg=TEXT,
             pady=6).pack(pady=(4, 16))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Roblox Audio Converter")
        self.configure(bg=DARK_BG)
        self.resizable(False, False)
        self._build_ui()
        self._check_ffmpeg()

    def _build_ui(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=PANEL_BG, pady=10)
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="Roblox Audio Converter",
                 bg=PANEL_BG, fg=TEXT, font=FONT_BIG).pack(padx=20)
        tk.Label(hdr, text="Download  *  Retime  *  Export to .ogg",
                 bg=PANEL_BG, fg=SUBTEXT, font=FONT_UI).pack()

        # ── ffmpeg row ────────────────────────────────────────────────────────
        _sep(self).grid(row=1, column=0, sticky="ew")
        ffrow = tk.Frame(self, bg=DARK_BG)
        ffrow.grid(row=2, column=0, sticky="ew", padx=16, pady=(10, 2))
        _label(ffrow, "ffmpeg:", fg=SUBTEXT).pack(side="left")
        self.ff_label = _label(ffrow, "checking ...", fg=SUBTEXT)
        self.ff_label.pack(side="left", padx=6)
        self.ff_btn = _btn(ffrow, "Download ffmpeg", self._download_ffmpeg_thread)
        self.ff_btn.pack(side="right")
        _sep(self).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        body = tk.Frame(self, bg=DARK_BG, padx=16, pady=10)
        body.grid(row=4, column=0, sticky="nsew")

        # ── Cookie ────────────────────────────────────────────────────────────
        ck_hdr = tk.Frame(body, bg=DARK_BG)
        ck_hdr.grid(row=0, column=0, sticky="ew")
        _label(ck_hdr, ".ROBLOSECURITY Cookie  (required)", font=FONT_HEAD).pack(side="left")
        _btn(ck_hdr, "How to get it?",
             lambda: CookieHelpDialog(self),
             bg=PANEL_BG, fg=SUBTEXT).pack(side="right")

        _label(body, "Roblox requires auth for all audio. Consider using an alt account.",
               fg=WARN).grid(row=1, column=0, sticky="w")

        self.cookie_var = tk.StringVar()
        self.cookie_entry = _entry(body, textvariable=self.cookie_var,
                                   width=68, show="*")
        self.cookie_entry.grid(row=2, column=0, sticky="ew", pady=(4, 0))

        ck_tog = tk.Frame(body, bg=DARK_BG)
        ck_tog.grid(row=3, column=0, sticky="w", pady=(2, 0))
        self._show_cookie = tk.BooleanVar(value=False)
        tk.Checkbutton(ck_tog, text="Show cookie", variable=self._show_cookie,
                       bg=DARK_BG, fg=SUBTEXT,
                       activebackground=DARK_BG, activeforeground=TEXT,
                       selectcolor=PANEL_BG, font=FONT_UI,
                       command=self._toggle_cookie_vis).pack(side="left")

        _sep(body).grid(row=4, column=0, sticky="ew", pady=(10, 6))

        # ── Place ID ──────────────────────────────────────────────────────────
        _label(body, "Place ID  (optional)", font=FONT_HEAD).grid(row=5, column=0, sticky="w")
        _label(body, "Helps with game-owned audio. Found in roblox.com/games/XXXXXXX/...",
               fg=SUBTEXT).grid(row=6, column=0, sticky="w")
        self.place_var = tk.StringVar()
        _entry(body, textvariable=self.place_var, width=28).grid(
            row=7, column=0, sticky="w", pady=(4, 0))

        _sep(body).grid(row=8, column=0, sticky="ew", pady=(10, 6))

        # ── URL list ──────────────────────────────────────────────────────────
        _label(body, "Asset URLs  (one per line)", font=FONT_HEAD).grid(
            row=9, column=0, sticky="w")
        _label(body, "e.g.  http://www.roblox.com/asset/?id=160608684  or just the ID",
               fg=SUBTEXT).grid(row=10, column=0, sticky="w")
        self.url_box = tk.Text(body, width=68, height=5,
                               bg=PANEL_BG, fg=TEXT, insertbackground=ACCENT,
                               relief="flat", font=FONT_MONO,
                               bd=0, highlightthickness=1,
                               highlightbackground=BORDER, highlightcolor=ACCENT,
                               pady=6, padx=6)
        self.url_box.grid(row=11, column=0, sticky="ew", pady=(4, 0))

        _sep(body).grid(row=12, column=0, sticky="ew", pady=(10, 6))

        # ── Speed ─────────────────────────────────────────────────────────────
        spd_row = tk.Frame(body, bg=DARK_BG)
        spd_row.grid(row=13, column=0, sticky="ew")
        _label(spd_row, "Speed multiplier:").pack(side="left")
        self.speed_var = tk.DoubleVar(value=1.0)
        self.speed_label = tk.Label(spd_row, text="1.00x",
                                    bg=DARK_BG, fg=ACCENT,
                                    font=("Consolas", 11, "bold") if IS_WIN
                                         else ("Menlo", 11, "bold"),
                                    width=6, anchor="e")
        self.speed_label.pack(side="right")
        tk.Scale(spd_row, from_=0.25, to=3.0, resolution=0.05,
                 orient="horizontal", variable=self.speed_var,
                 bg=DARK_BG, fg=TEXT, troughcolor=PANEL_BG,
                 activebackground=ACCENT, highlightthickness=0,
                 showvalue=False, length=350,
                 command=self._update_speed_label).pack(side="left", padx=10)

        presets = tk.Frame(body, bg=DARK_BG)
        presets.grid(row=14, column=0, sticky="w", pady=(4, 0))
        _label(presets, "Presets:", fg=SUBTEXT).pack(side="left", padx=(0, 6))
        for lbl, val in [("0.5x", 0.5), ("0.75x", 0.75), ("1x", 1.0),
                          ("1.25x", 1.25), ("1.5x", 1.5), ("2x", 2.0)]:
            _btn(presets, lbl, lambda v=val: self._set_speed(v),
                 bg=PANEL_BG, fg=TEXT).pack(side="left", padx=2)

        _sep(body).grid(row=15, column=0, sticky="ew", pady=(10, 6))

        # ── Output folder ─────────────────────────────────────────────────────
        out_row = tk.Frame(body, bg=DARK_BG)
        out_row.grid(row=16, column=0, sticky="ew")
        _label(out_row, "Output folder:").pack(side="left")
        self.out_var = tk.StringVar(value=os.path.expanduser("~"))
        _entry(out_row, textvariable=self.out_var, width=46).pack(side="left", padx=8)
        _btn(out_row, "Browse ...", self._browse_out,
             bg=PANEL_BG, fg=TEXT).pack(side="left")

        # ── Convert button ────────────────────────────────────────────────────
        self.convert_btn = tk.Button(
            body, text="Convert  ->  .ogg",
            bg=ACCENT, fg="white",
            activebackground=ACCENT2, activeforeground="white",
            relief="flat", cursor="hand2",
            font=("Segoe UI Semibold", 11) if IS_WIN
                 else ("Helvetica Neue", 11, "bold"),
            padx=20, pady=9,
            command=self._start_convert,
        )
        self.convert_btn.grid(row=17, column=0, sticky="ew", pady=(14, 0))

        # ── Log ───────────────────────────────────────────────────────────────
        _sep(self).grid(row=5, column=0, sticky="ew", pady=(4, 0))
        log_frame = tk.Frame(self, bg=DARK_BG, padx=16)
        log_frame.grid(row=6, column=0, sticky="nsew", pady=(8, 12))
        _label(log_frame, "Log", fg=SUBTEXT).pack(anchor="w")
        self.log_box = tk.Text(
            log_frame, width=68, height=7,
            bg=PANEL_BG, fg=TEXT,
            relief="flat", font=FONT_MONO,
            bd=0, highlightthickness=1,
            highlightbackground=BORDER,
            state="disabled", pady=6, padx=6,
        )
        self.log_box.pack(fill="both", expand=True, pady=(4, 0))
        self.log_box.tag_config("ok",   foreground=SUCCESS)
        self.log_box.tag_config("err",  foreground=ERROR)
        self.log_box.tag_config("dim",  foreground=SUBTEXT)
        self.log_box.tag_config("warn", foreground=WARN)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _log(self, msg, tag=None):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", msg + "\n", tag or "")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _toggle_cookie_vis(self):
        self.cookie_entry.config(show="" if self._show_cookie.get() else "*")

    def _update_speed_label(self, _=None):
        self.speed_label.config(text=f"{self.speed_var.get():.2f}x")

    def _set_speed(self, val):
        self.speed_var.set(val)
        self._update_speed_label()

    def _browse_out(self):
        d = filedialog.askdirectory(initialdir=self.out_var.get())
        if d:
            self.out_var.set(d)

    def _set_ff_status(self, ok: bool):
        if ok:
            self.ff_label.config(text="found", fg=SUCCESS)
            self.ff_btn.config(state="disabled", bg=BORDER)
        else:
            self.ff_label.config(text="not found", fg=ERROR)
            self.ff_btn.config(state="normal", bg=ACCENT)

    def _check_ffmpeg(self):
        self._set_ff_status(bool(ffmpeg_exe()))

    # ── ffmpeg download ───────────────────────────────────────────────────────

    def _download_ffmpeg_thread(self):
        self.ff_btn.config(state="disabled", text="Downloading ...")
        threading.Thread(target=self._do_download_ffmpeg, daemon=True).start()

    def _do_download_ffmpeg(self):
        try:
            download_ffmpeg(progress_cb=lambda m: self.after(0, self._log, m, "dim"))
            self.after(0, self._set_ff_status, True)
            self.after(0, self.ff_btn.config, {"text": "Download ffmpeg"})
        except Exception as e:
            self.after(0, self._log, f"ffmpeg download failed: {e}", "err")
            self.after(0, self.ff_btn.config, {"state": "normal", "text": "Retry Download"})

    # ── conversion pipeline ───────────────────────────────────────────────────

    def _start_convert(self):
        urls = [u.strip() for u in self.url_box.get("1.0", "end").splitlines()
                if u.strip()]
        if not urls:
            messagebox.showwarning("No URLs", "Paste at least one Roblox asset URL.")
            return
        if not ffmpeg_exe():
            messagebox.showerror("ffmpeg missing",
                                 "Download ffmpeg first using the button above.")
            return
        if not self.cookie_var.get().strip():
            messagebox.showerror(
                "Cookie required",
                "A .ROBLOSECURITY cookie is required.\n\n"
                "Roblox now requires authentication for all audio downloads.\n"
                "Click 'How to get it?' for step-by-step instructions."
            )
            return
        out_dir = self.out_var.get()
        if not os.path.isdir(out_dir):
            messagebox.showerror("Bad output folder", f"Directory not found:\n{out_dir}")
            return

        self.convert_btn.config(state="disabled", text="Working ...")
        threading.Thread(
            target=self._do_convert,
            args=(urls, self.cookie_var.get(), self.place_var.get(),
                  self.speed_var.get(), out_dir),
            daemon=True,
        ).start()

    def _do_convert(self, urls, cookie, place_id, speed, out_dir):
        ok_count = 0
        for url in urls:
            try:
                asset_id = extract_asset_id(url)
                self.after(0, self._log, f"-- Asset {asset_id}", "dim")

                raw = resolve_roblox_audio(
                    asset_id, cookie, place_id,
                    progress_cb=lambda m: self.after(0, self._log, f"  {m}", "dim"),
                )

                out_name = f"roblox_{asset_id}_x{speed:.2f}.ogg"
                out_path = os.path.join(out_dir, out_name)

                convert_audio(
                    raw, speed, out_path,
                    progress_cb=lambda m: self.after(0, self._log, f"  {m}", "dim"),
                )
                self.after(0, self._log, f"  OK  {out_name}", "ok")
                ok_count += 1

            except Exception as e:
                self.after(0, self._log, f"  FAIL  {e}", "err")

        n = len(urls)
        tag = "ok" if ok_count == n else ("err" if ok_count == 0 else "warn")
        self.after(0, self._log, f"\nDone -- {ok_count}/{n} succeeded.", tag)
        self.after(0, self.convert_btn.config,
                   {"state": "normal", "text": "Convert  ->  .ogg"})


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        import requests
    except ImportError:
        print("Installing requests ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        import requests  # noqa: F811

    app = App()
    app.mainloop()