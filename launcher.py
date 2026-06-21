import ctypes
import hashlib
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, W, Text, Tk, messagebox, ttk
from typing import Any, Callable

import requests

try:
    import sv_ttk  # type: ignore[import-not-found]
except Exception:
    sv_ttk = None

try:
    import darkdetect  # type: ignore[import-not-found]
except Exception:
    darkdetect = None


OWNER = "soli-dstate"
REPO = "DOOM-Tools"
DEFAULT_BRANCH = "master"
GITHUB_API_RELEASE = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
GITHUB_API_RELEASES = f"https://api.github.com/repos/{OWNER}/{REPO}/releases"
GITHUB_API_BRANCHES = f"https://api.github.com/repos/{OWNER}/{REPO}/branches?per_page=100"
GITHUB_API_BRANCH = f"https://api.github.com/repos/{OWNER}/{REPO}/branches/{{branch}}"
GITHUB_BRANCH_ZIP = f"https://api.github.com/repos/{OWNER}/{REPO}/zipball/{{ref}}"
# Ref-aware raw file URL. `current_resource_links` moved from main.py into
# app/foundation.py during the package overhaul, so resource resolution reads
# foundation first and falls back to main.py for older refs.
GITHUB_RAW_FILE = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{{ref}}/{{path}}"
GITHUB_RAW_MAIN = GITHUB_RAW_FILE.format(ref=DEFAULT_BRANCH, path="main.py")
RESOURCE_LINK_FILES = ("app/foundation.py", "main.py")

APP_NAME = "DOOM-Tools Launcher"
EXE_NAME = "DOOM-Tools.exe"
SOURCE_DIR_NAME = "source"
VENV_DIR_NAME = "venv"
RUNTIME_DIR_NAME = "runtime"
BUILD_DIR_NAME = "build"
DIST_DIR_NAME = "dist"
STATE_FILE_NAME = "state.json"
LAUNCH_SETTINGS_FILE_NAME = "launcher_settings.json"
BUILDER_DIR_NAME = "builder_toolchain"
BUILDER_ASSET_NAME = "DOOM-Tools-python-builder-windows.zip"

DEFAULT_LAUNCH_SETTINGS = {
    "devmode": False,
    "debug": False,
    "dmmode": False,
    "keep_console_open": False,
    "use_prerelease": False,
    # Empty string = stable release channel. A branch name (e.g. "overhaul")
    # runs that branch's source directly and requires a local Python install.
    "branch": "",
    # When True, the "build from source?" prompt is skipped and the prebuilt
    # binary is used. Set by ticking "Don't ask again" after declining a build.
    "suppress_source_prompt": False,
}

SOURCE_COPY_DIRS = ("tables", "themes", "fonts")
RESOURCE_DIRS = ("sounds", "images")
FONT_SUFFIXES = (".ttf", ".otf")
FONT_INSTALL_VERSION = 2

INSTALL_STEPS = [
    "Checking release",
    "Downloading source",
    "Preparing environment",
    "Building executable",
    "Checking fonts",
    "Checking resources",
    "Ready to launch",
]

MUTEX_NAME = "DOOMToolsLauncherSingleton"
ERROR_ALREADY_EXISTS = 183
HTTP_RETRY_ATTEMPTS = 4
HTTP_RETRY_SLEEP_SECONDS = 1.4
HTTP_RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
HTTP_DEFAULT_HEADERS = {
    "Accept": "*/*",
    "Connection": "close",
    "User-Agent": "DOOM-Tools-Launcher/1.0",
}
REQUIRED_PYTHON_VERSION = (3, 13, 11)


class LauncherError(RuntimeError):
    pass


def _enable_windows_vt_mode() -> bool:
    if os.name != "nt":
        return False
    try:
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        if handle in (0, -1):
            return False
        mode = ctypes.c_uint()
        if ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)) == 0:
            return False
        return ctypes.windll.kernel32.SetConsoleMode(handle, mode.value | 0x0004) != 0
    except Exception:
        return False


def _console_supports_color() -> bool:
    stream = getattr(sys, "stderr", None)
    if stream is None or not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if os.name != "nt":
        return True
    if os.environ.get("WT_SESSION") or os.environ.get("ANSICON"):
        return True
    return _enable_windows_vt_mode()


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        orig_level = record.levelname
        color = self.COLORS.get(orig_level, "")
        formatted = super().format(record)

        if orig_level in ("WARNING", "ERROR", "CRITICAL", "DEBUG") and color:
            return f"{color}{formatted}{self.RESET}"

        if orig_level == "INFO" and color:
            try:
                return formatted.replace(orig_level, f"{color}{orig_level}{self.RESET}", 1)
            except Exception:
                return formatted
        return formatted


class StripAnsiFormatter(logging.Formatter):
    ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return self.ANSI_RE.sub("", formatted)


class UILogHandler(logging.Handler):
    def __init__(self, ui_queue: queue.Queue[tuple[str, Any]]) -> None:
        super().__init__()
        self.ui_queue = ui_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.ui_queue.put(("log", (record.levelname, self.format(record))))
        except Exception:
            self.handleError(record)


def send_desktop_notification(title: str, message: str, logger: logging.Logger | None = None) -> bool:
    try:
        if os.name == "nt":
            try:
                from winotify import Notification, audio

                toast = Notification(app_id=APP_NAME, title=title, msg=message, duration="short")
                toast.set_audio(audio.Default, loop=False)
                toast.show()
                return True
            except Exception:
                escaped_title = title.replace("'", "''")
                escaped_message = message.replace("'", "''")
                script = (
                    "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                    "$template = [Windows.UI.Notifications.ToastTemplateType, Windows.UI.Notifications, ContentType=WindowsRuntime]::ToastText02; "
                    "$xml = [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]::GetTemplateContent($template); "
                    "$nodes = $xml.GetElementsByTagName('text'); "
                    f"$nodes.Item(0).AppendChild($xml.CreateTextNode('{escaped_title}')) > $null; "
                    f"$nodes.Item(1).AppendChild($xml.CreateTextNode('{escaped_message}')) > $null; "
                    "$toast = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType=WindowsRuntime]::new($xml); "
                    f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]::CreateToastNotifier('{escaped_title}').Show($toast)"
                )
                completed = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=10,
                )
                return completed.returncode == 0

        if sys.platform == "darwin":
            escaped_title = title.replace('"', '\\"')
            escaped_message = message.replace('"', '\\"')
            completed = subprocess.run(
                ["osascript", "-e", f'display notification "{escaped_message}" with title "{escaped_title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            return completed.returncode == 0

        notify_send = shutil.which("notify-send")
        if notify_send:
            completed = subprocess.run(
                [notify_send, title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            return completed.returncode == 0
    except Exception as exc:
        if logger:
            logger.debug("Desktop notification failed: %s", exc)
        return False

    if logger:
        logger.debug("Desktop notifications are unavailable on this platform")
    return False


def configure_launcher_logger(
    ui_queue: queue.Queue[tuple[str, Any]],
    cache_dir: Path,
) -> tuple[logging.Logger, Path]:
    logs_dir = cache_dir / "logs"
    archive_dir = logs_dir / "archive"
    logs_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)

    log_files = sorted(logs_dir.glob("log_*.log"))
    if len(log_files) >= 50:
        archive_name = archive_dir / f"logs_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        with zipfile.ZipFile(archive_name, "w", zipfile.ZIP_DEFLATED) as archive_zip:
            for log_file in log_files:
                archive_zip.write(log_file, arcname=log_file.name)
                log_file.unlink(missing_ok=True)
        log_files = []

    log_number = len(log_files) + 1
    log_path = logs_dir / f"log_{log_number}_{datetime.now().strftime('%A_%B_%d_%Y_%H_%M_%S_%f')[:-3]}.log"
    message_format = "%(asctime)s | %(levelname)s | %(message)s"

    logger = logging.getLogger("doom_tools.launcher")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            logging.exception("Suppressed exception")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(StripAnsiFormatter(message_format))

    console_handler = logging.StreamHandler()
    if _console_supports_color():
        console_handler.setFormatter(ColoredFormatter(message_format))
    else:
        console_handler.setFormatter(StripAnsiFormatter(message_format))

    ui_handler = UILogHandler(ui_queue)
    ui_handler.setFormatter(StripAnsiFormatter(message_format))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(ui_handler)
    return logger, log_path


def hide_console_window() -> None:
    if os.name != "nt":
        return
    if os.environ.get("DOOM_TOOLS_LAUNCHER_SHOW_CONSOLE", "").strip() == "1":
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        logging.exception("Suppressed exception")


def acquire_single_instance_lock() -> int | None:
    if os.name != "nt":
        return None

    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not mutex:
        return None

    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        ctypes.windll.kernel32.CloseHandle(mutex)
        return 0

    return int(mutex)


def release_single_instance_lock(mutex_handle: int | None) -> None:
    if os.name != "nt" or not mutex_handle:
        return
    ctypes.windll.kernel32.CloseHandle(mutex_handle)


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir = dest_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            target = (dest_dir / member.filename).resolve()
            if not str(target).startswith(str(dest_dir)):
                raise LauncherError(f"Zip slip blocked: {member.filename}")
            zf.extract(member, dest_dir)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _retry_delay(attempt: int) -> float:
    return min(6.0, HTTP_RETRY_SLEEP_SECONDS * attempt)


def _request_with_retry(
    url: str,
    *,
    timeout: int,
    stream: bool = False,
    headers: dict[str, str] | None = None,
    attempts: int = HTTP_RETRY_ATTEMPTS,
):
    merged_headers = dict(HTTP_DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, timeout=timeout, stream=stream, headers=merged_headers)
            if response.status_code in HTTP_RETRY_STATUS and attempt < attempts:
                response.close()
                raise requests.HTTPError(f"Transient HTTP status {response.status_code}")
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt >= attempts:
                break
            time.sleep(_retry_delay(attempt))

    raise LauncherError(f"Failed to fetch URL after retries: {url} | {last_error}")


def fetch_latest_release(include_prerelease: bool = False) -> dict:
    if include_prerelease:
        with _request_with_retry(
            GITHUB_API_RELEASES,
            timeout=20,
            headers={"Accept": "application/vnd.github+json"},
        ) as response:
            releases = response.json()
        if not isinstance(releases, list):
            raise LauncherError("Releases list response was not a list")
        # The API returns releases newest-first; pick the most recent published
        # (non-draft) release, which may be a prerelease.
        data = next(
            (r for r in releases if isinstance(r, dict) and not r.get("draft")),
            None,
        )
        if data is None:
            raise LauncherError("No published releases found")
    else:
        with _request_with_retry(
            GITHUB_API_RELEASE,
            timeout=20,
            headers={"Accept": "application/vnd.github+json"},
        ) as response:
            data = response.json()
    tag = str(data.get("tag_name", "")).strip()
    zipball_url = str(data.get("zipball_url", "")).strip()
    assets = data.get("assets", [])
    if not isinstance(assets, list):
        assets = []
    if not tag or not zipball_url:
        raise LauncherError("Latest release response missing tag_name or zipball_url")
    return {"tag": tag, "zipball_url": zipball_url, "assets": assets}


def _parse_resource_links(text: str) -> list[str]:
    list_match = re.search(r"current_resource_links\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if list_match:
        urls = re.findall(r"[\"']([^\"']+)[\"']", list_match.group(1))
        return [u.strip() for u in urls if u.strip()]
    single = re.search(r"^current_resource_link\s*=\s*[\"\'](.*?)[\"\']\s*$", text, re.MULTILINE)
    if single and single.group(1).strip():
        return [single.group(1).strip()]
    return []


def fetch_remote_resource_links(ref: str = DEFAULT_BRANCH) -> list[str]:
    """Return the ordered resource part URLs declared for the given git ref.

    ``current_resource_links`` lives in app/foundation.py after the package
    overhaul; older refs declared it in main.py, so both files are tried.
    Supports the list form and the legacy single-string ``current_resource_link``.
    """
    for path in RESOURCE_LINK_FILES:
        url = GITHUB_RAW_FILE.format(ref=ref, path=path)
        try:
            with _request_with_retry(url, timeout=20) as response:
                text = response.text
        except Exception:
            logging.exception("Suppressed exception")
            continue
        links = _parse_resource_links(text)
        if links:
            return links
    return []


def fetch_branches() -> list[str]:
    """Return repository branch names, default branch first."""
    with _request_with_retry(
        GITHUB_API_BRANCHES, timeout=20,
        headers={"Accept": "application/vnd.github+json"},
    ) as response:
        data = response.json()
    if not isinstance(data, list):
        raise LauncherError("Branches response was not a list")
    names = [str(b.get("name")) for b in data if isinstance(b, dict) and b.get("name")]
    names.sort(key=lambda n: (n != DEFAULT_BRANCH, n.lower()))
    return names


def fetch_branch_head(branch: str) -> str:
    """Return the HEAD commit sha of a branch (used for update detection)."""
    with _request_with_retry(
        GITHUB_API_BRANCH.format(branch=branch), timeout=20,
        headers={"Accept": "application/vnd.github+json"},
    ) as response:
        data = response.json()
    sha = str((((data or {}).get("commit") or {}).get("sha")) or "").strip()
    if not sha:
        raise LauncherError(f"Could not resolve HEAD commit for branch '{branch}'")
    return sha


def _format_size(value: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = max(value, 0.0)
    idx = 0
    while size >= 1024.0 and idx < len(units) - 1:
        size /= 1024.0
        idx += 1
    return f"{size:.1f} {units[idx]}"


def download_file(
    url: str,
    out_path: Path,
    on_progress: Callable[[int, int, float], None] | None = None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_suffix(out_path.suffix + ".part")

    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                logging.exception("Suppressed exception")

        try:
            with _request_with_retry(url, timeout=120, stream=True, attempts=1) as response:
                total = int(response.headers.get("Content-Length", "0") or "0")
                downloaded = 0
                started = time.perf_counter()
                last_emit = started
                with temp_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 64):
                        if chunk:
                            handle.write(chunk)
                            downloaded += len(chunk)
                            now = time.perf_counter()
                            if on_progress and (now - last_emit >= 0.2):
                                elapsed = max(now - started, 0.001)
                                speed = downloaded / elapsed
                                on_progress(downloaded, total, speed)
                                last_emit = now

                if on_progress:
                    elapsed = max(time.perf_counter() - started, 0.001)
                    speed = downloaded / elapsed
                    on_progress(downloaded, total, speed)

            temp_path.replace(out_path)
            return
        except Exception as exc:
            last_error = exc
            if attempt >= HTTP_RETRY_ATTEMPTS:
                break
            if on_progress:
                on_progress(0, 0, 0.0)
            time.sleep(_retry_delay(attempt))

    raise LauncherError(f"Failed downloading {url}: {last_error}")


def extract_source_from_release(zip_path: Path, extract_parent: Path) -> Path:
    if extract_parent.exists():
        shutil.rmtree(extract_parent, ignore_errors=True)
    extract_parent.mkdir(parents=True, exist_ok=True)
    safe_extract_zip(zip_path, extract_parent)

    dirs = [p for p in extract_parent.iterdir() if p.is_dir()]
    if len(dirs) != 1:
        raise LauncherError("Unexpected release source layout")
    return dirs[0]


def ensure_venv(venv_dir: Path, logger, python_cmd: list[str]) -> Path:
    if os.name == "nt":
        python_path = venv_dir / "Scripts" / "python.exe"
    else:
        python_path = venv_dir / "bin" / "python"

    if python_path.exists():
        probe = subprocess.run(
            [str(python_path), "-c", "import sys; print(sys.version)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
        if probe.returncode == 0:
            return python_path

        logger("Cached virtual environment is invalid. Recreating venv...")
        shutil.rmtree(venv_dir, ignore_errors=True)

    logger("Creating virtual environment...")
    subprocess.run(python_cmd + ["-m", "venv", str(venv_dir)], check=True)
    if not python_path.exists():
        raise LauncherError("Failed to create virtual environment")

    pip_probe = subprocess.run(
        [str(python_path), "-m", "pip", "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
        check=False,
    )
    if pip_probe.returncode != 0:
        logger("Bootstrapping pip inside virtual environment...")
        subprocess.run([str(python_path), "-m", "ensurepip", "--upgrade"], check=True)

    return python_path


def _python_version_script() -> str:
    return (
        "import sys; "
        "print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
    )


def detect_python_command(logger=None) -> list[str] | None:
    """Return a command for the required free-threaded Python build, or None.

    DOOM-Tools requires the exact version AND a free-threaded (no-GIL) build:
    the launcher sets PYTHON_GIL=0, which fatally errors on a standard build.
    A standard build of the right version is therefore rejected (the user is
    prompted to install the free-threaded build). Each candidate is logged.
    """
    def _log(msg: str) -> None:
        if logger:
            try:
                logger(msg)
            except Exception:
                logging.exception("Suppressed exception")

    candidates: list[list[str]] = []
    if os.name == "nt" and shutil.which("py"):
        candidates += [["py", "-3.13t"], ["py", "-3.13"], ["py", "-3"]]
    for exe in ("python", "python3"):
        if shutil.which(exe):
            candidates.append([exe])

    required_version = ".".join(str(part) for part in REQUIRED_PYTHON_VERSION)
    version_script = _python_version_script()

    for base in candidates:
        label = " ".join(base)
        try:
            probe = subprocess.run(
                base + ["-c", version_script],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=10, check=False,
            )
        except Exception as exc:
            _log(f"Python probe '{label}' failed: {exc}")
            continue

        version = probe.stdout.strip()
        if probe.returncode != 0 or not version:
            continue
        if version != required_version:
            _log(f"Found Python {version} via '{label}' (need {required_version}); skipping.")
            continue
        if not python_is_free_threaded(base):
            _log(f"Found standard (with-GIL) Python {version} via '{label}'; the "
                 "free-threaded (no-GIL) build is required. Skipping.")
            continue

        _log(f"Using free-threaded Python {version} via '{label}'.")
        return base

    return None


def detect_any_python(logger=None) -> tuple[list[str] | None, str | None]:
    """Return (command, "X.Y.Z") for the first usable Python of ANY version.

    Having *any* Python is the signal that a user might want to build from
    source; the specific 3.13.11 requirement is checked separately and only
    after the user opts in.
    """
    candidates: list[list[str]] = []
    if os.name == "nt" and shutil.which("py"):
        candidates += [["py", "-3"], ["py"]]
    for exe in ("python", "python3"):
        if shutil.which(exe):
            candidates.append([exe])

    version_script = _python_version_script()
    for base in candidates:
        try:
            result = subprocess.run(
                base + ["-c", version_script],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                timeout=10, check=False,
            )
            version = result.stdout.strip()
            if result.returncode == 0 and version:
                if logger:
                    try:
                        logger(f"Detected Python {version} via '{' '.join(base)}'.")
                    except Exception:
                        logging.exception("Suppressed exception")
                return base, version
        except Exception:
            logging.exception("Suppressed exception")
            continue
    return None, None


def python_install_url() -> str:
    """Direct python.org download URL for the required version + platform."""
    version = ".".join(str(part) for part in REQUIRED_PYTHON_VERSION)
    base = f"https://www.python.org/ftp/python/{version}"
    if os.name == "nt":
        return f"{base}/python-{version}-amd64.exe"
    if sys.platform == "darwin":
        return f"{base}/python-{version}-macos11.pkg"
    # Linux/other: python.org ships source only — link the source tarball.
    return f"{base}/Python-{version}.tgz"


def python_is_free_threaded(python) -> bool:
    """True only if the interpreter is a free-threaded (no-GIL) build.

    Standard builds FATAL at startup if PYTHON_GIL=0 is set
    ("Disabling the GIL is not supported by this build"), so the launcher must
    only force no-GIL for builds that actually support it.
    """
    cmd = list(python) if isinstance(python, (list, tuple)) else [str(python)]
    try:
        result = subprocess.run(
            cmd + ["-c", "import sysconfig;print(1 if sysconfig.get_config_var('Py_GIL_DISABLED') else 0)"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            timeout=10, check=False,
        )
        return result.returncode == 0 and result.stdout.strip() == "1"
    except Exception:
        return False


def find_windows_builder_asset(release: dict) -> dict:
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        assets = []

    preferred = [
        BUILDER_ASSET_NAME,
        "DOOM-Tools-builder-windows.zip",
        "DOOM-Tools-python-toolchain-windows.zip",
    ]

    for wanted in preferred:
        for asset in assets:
            name = str(asset.get("name", ""))
            if name == wanted and asset.get("browser_download_url"):
                return asset

    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if "builder" in name and "windows" in name and name.endswith(".zip"):
            if asset.get("browser_download_url"):
                return asset

    raise LauncherError(
        "No bundled builder asset found in latest release. "
        f"Expected an asset like {BUILDER_ASSET_NAME}."
    )


def ensure_windows_builder_python(
    release: dict,
    cache_dir: Path,
    release_tag: str,
    logger,
    transfer_cb: Callable[[str, int, int, float], None] | None = None,
) -> list[str] | None:
    if os.name != "nt":
        return None

    toolchain_dir = cache_dir / BUILDER_DIR_NAME / release_tag

    def _pick_python(path_root: Path) -> Path | None:
        candidates = [p for p in path_root.rglob("python.exe") if p.is_file()]
        if not candidates:
            return None
        return sorted(candidates, key=lambda p: (len(p.parts), len(str(p))))[0]

    cached_python = _pick_python(toolchain_dir)
    if cached_python:
        logger(f"Using cached bundled builder Python: {cached_python}")
        return [str(cached_python)]

    asset = find_windows_builder_asset(release)
    asset_name = str(asset.get("name", BUILDER_ASSET_NAME))
    asset_url = str(asset.get("browser_download_url", ""))
    if not asset_url:
        raise LauncherError(f"Builder asset {asset_name} is missing browser_download_url")

    archive_path = cache_dir / asset_name
    download_file(
        asset_url,
        archive_path,
        on_progress=(
            (lambda d, t, s: transfer_cb("Builder toolchain", d, t, s))
            if transfer_cb
            else None
        ),
    )

    if toolchain_dir.exists():
        shutil.rmtree(toolchain_dir, ignore_errors=True)
    toolchain_dir.mkdir(parents=True, exist_ok=True)
    safe_extract_zip(archive_path, toolchain_dir)

    python_path = _pick_python(toolchain_dir)
    if not python_path:
        raise LauncherError("Bundled builder asset does not contain python.exe")

    probe = subprocess.run(
        [str(python_path), "-c", "import sys; print(sys.version)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=15,
        check=False,
    )
    if probe.returncode != 0:
        raise LauncherError("Bundled builder Python failed to start")

    logger(f"Bundled builder Python is ready: {python_path}")
    return [str(python_path)]


def find_windows_prebuilt_asset(release: dict) -> dict:
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        assets = []

    preferred = [
        f"{APP_NAME}-windows.zip",
        f"{APP_NAME}-windows-runtime.zip",
        f"{APP_NAME}.exe",
    ]

    for wanted in preferred:
        for asset in assets:
            name = str(asset.get("name", ""))
            if name == wanted and asset.get("browser_download_url"):
                return asset

    for asset in assets:
        name = str(asset.get("name", "")).lower()
        if "windows" in name and (name.endswith(".zip") or name.endswith(".exe")):
            if asset.get("browser_download_url"):
                return asset

    raise LauncherError(
        "No Windows runtime asset found in latest release. "
        "Expected an asset like DOOM-Tools-windows.zip."
    )


def install_prebuilt_runtime_from_file(target: Path, cache_dir: Path, runtime_dir: Path, logger) -> Path:
    asset_name = target.name
    runtime_dir.mkdir(parents=True, exist_ok=True)
    runtime_exe = runtime_dir / EXE_NAME

    if target.suffix.lower() == ".exe":
        shutil.copy2(target, runtime_exe)
        logger("Installed prebuilt executable from .exe asset")
        return runtime_exe

    if target.suffix.lower() == ".zip":
        temp_extract = cache_dir / "_runtime_extract"
        if temp_extract.exists():
            shutil.rmtree(temp_extract, ignore_errors=True)
        temp_extract.mkdir(parents=True, exist_ok=True)
        try:
            safe_extract_zip(target, temp_extract)
            candidates = [p for p in temp_extract.rglob(EXE_NAME) if p.is_file()]
            if not candidates:
                raise LauncherError(f"No {EXE_NAME} found in runtime zip asset")
            shutil.copy2(candidates[0], runtime_exe)
            logger("Installed prebuilt executable from zip asset")
            return runtime_exe
        finally:
            shutil.rmtree(temp_extract, ignore_errors=True)

    raise LauncherError(f"Unsupported runtime asset type: {asset_name}")


def run_logged(cmd: list[str], logger, cwd: Path | None = None) -> None:
    logger("Running: " + " ".join(cmd))
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(cwd) if cwd else None,
    )
    assert process.stdout is not None
    for line in process.stdout:
        logger(line.rstrip())
    code = process.wait()
    if code != 0:
        raise LauncherError(f"Command failed with exit code {code}: {' '.join(cmd)}")


def install_dependencies(venv_python: Path, source_root: Path, logger) -> None:
    req_file = source_root / "requirements.txt"
    if not req_file.exists():
        raise LauncherError("requirements.txt was not found in downloaded source")

    run_logged(
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
        logger,
    )
    run_logged(
        [str(venv_python), "-m", "pip", "install", "--upgrade", "--upgrade-strategy", "only-if-needed", "-r", str(req_file)],
        logger,
    )


def requirements_digest(source_root: Path) -> str:
    req_file = source_root / "requirements.txt"
    if not req_file.exists():
        raise LauncherError("requirements.txt was not found in downloaded source")
    return hashlib.sha256(req_file.read_bytes()).hexdigest()


def build_executable(venv_python: Path, source_root: Path, cache_dir: Path, logger) -> Path:
    dist_dir = cache_dir / DIST_DIR_NAME
    build_dir = cache_dir / BUILD_DIR_NAME

    if dist_dir.exists():
        shutil.rmtree(dist_dir, ignore_errors=True)
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    main_py = source_root / "main.py"
    images_dir = source_root / "images"
    if not main_py.exists():
        raise LauncherError("Downloaded source does not contain main.py")

    cmd = [
        str(venv_python),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "DOOM-Tools",
        # The app is now an `app/` package imported by main.py; bundle every
        # submodule and make the package importable from the source root.
        "--collect-submodules",
        "app",
        "--paths",
        str(source_root),
    ]

    if images_dir.exists():
        sep = ";" if os.name == "nt" else ":"
        cmd += ["--add-data", f"{images_dir}{sep}images"]

    cmd += [
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        str(main_py),
    ]

    run_logged(cmd, logger)

    exe_path = dist_dir / EXE_NAME
    if not exe_path.exists():
        raise LauncherError(f"Expected built executable not found: {exe_path}")
    return exe_path


def copy_source_runtime_content(source_root: Path, runtime_dir: Path, logger) -> None:
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for folder_name in SOURCE_COPY_DIRS:
        src = source_root / folder_name
        dst = runtime_dir / folder_name
        if not src.exists():
            continue
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(src, dst)
        logger(f"Synced {folder_name} directory")


def replace_resources_from_zip(zip_path: Path, runtime_dir: Path, logger) -> None:
    for folder_name in RESOURCE_DIRS:
        target = runtime_dir / folder_name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            logger(f"Removed old {folder_name} directory")

    temp_extract = Path(tempfile.mkdtemp(prefix="doom_resources_"))
    try:
        safe_extract_zip(zip_path, temp_extract)
        for folder_name in RESOURCE_DIRS:
            src = temp_extract / folder_name
            if src.exists() and src.is_dir():
                shutil.copytree(src, runtime_dir / folder_name)
                logger(f"Installed new {folder_name} directory")
    finally:
        shutil.rmtree(temp_extract, ignore_errors=True)


def list_font_files(fonts_dir: Path) -> list[Path]:
    files: list[Path] = []
    if not fonts_dir.exists():
        return files
    for path in fonts_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in FONT_SUFFIXES:
            files.append(path)
    return files


def get_system_font_names_windows() -> set[str]:
    # Only machine-wide fonts in C:\Windows\Fonts are treated as "already
    # installed" and skipped. Per-user fonts are (re)registered on every check
    # run, because a stale/incorrect registry entry can leave the file present
    # but the font unusable -- which is what made fonts appear to uninstall.
    names: set[str] = set()
    windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    if windows_fonts.exists():
        for file_path in windows_fonts.iterdir():
            if file_path.is_file():
                names.add(file_path.name.lower())
    return names


def install_font_windows(font_path: Path, logger) -> bool:
    import winreg

    user_fonts_dir = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
    user_fonts_dir.mkdir(parents=True, exist_ok=True)

    dest_name = font_path.name
    dest_path = user_fonts_dir / dest_name
    shutil.copy2(font_path, dest_path)

    # Load the font into the current session so it is usable immediately; without
    # this, WM_FONTCHANGE only notifies apps and the font is not registered with GDI.
    if ctypes.windll.gdi32.AddFontResourceW(str(dest_path)) == 0:
        logger(f"Warning: AddFontResourceW reported no fonts added for {dest_name}")

    # Persist across logons. Per-user fonts (HKCU) MUST store the FULL path to the
    # file in %LOCALAPPDATA%; only system fonts in C:\Windows\Fonts use a bare name.
    # Storing the bare name here is why fonts appeared to "uninstall" after logoff.
    font_type = "OpenType" if font_path.suffix.lower() == ".otf" else "TrueType"
    value_name = f"{font_path.stem} ({font_type})"
    reg_path = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, str(dest_path))

    HWND_BROADCAST = 0xFFFF
    WM_FONTCHANGE = 0x001D
    SMTO_ABORTIFHUNG = 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(
        HWND_BROADCAST,
        WM_FONTCHANGE,
        0,
        0,
        SMTO_ABORTIFHUNG,
        1000,
        None,
    )

    logger(f"Installed font: {dest_name}")
    return True


def install_missing_fonts(source_root: Path, state: dict, logger) -> None:
    fonts_dir = source_root / "fonts"
    remote_fonts = list_font_files(fonts_dir)
    if not remote_fonts:
        logger("No remote fonts found in release source")
        return

    if os.name != "nt":
        logger("Font installation is only automated on Windows")
        return

    system_fonts = get_system_font_names_windows()
    installed_any = False

    for font_file in remote_fonts:
        if font_file.name.lower() in system_fonts:
            continue
        try:
            installed_any = install_font_windows(font_file, logger) or installed_any
        except Exception as exc:
            logger(f"Font install failed for {font_file.name}: {exc}")

    if not installed_any:
        logger("All release fonts are already installed")

    state["installed_fonts_checked_tag"] = state.get("release_tag", "")
    state["font_install_version"] = FONT_INSTALL_VERSION


def prepare_or_update(
    cache_dir: Path,
    state_path: Path,
    logger,
    progress=None,
    transfer=None,
    use_prerelease: bool = False,
    branch: str = "",
    runtime_chooser=None,
) -> tuple[list[str], Path, dict]:
    def report(step: int, status: str, detail: str = "") -> None:
        if progress:
            progress(step, status, detail)

    def report_transfer(label: str, downloaded: int, total: int, speed: float) -> None:
        if transfer:
            transfer(label, downloaded, total, speed)

    state = load_json(state_path)
    branch = (branch or "").strip()
    branch_mode = bool(branch)

    runtime_dir = cache_dir / RUNTIME_DIR_NAME
    runtime_exe = runtime_dir / EXE_NAME
    release: dict | None = None

    def _acquire_source(zip_url: str, dest: Path, label: str) -> None:
        report(1, "Downloading source", f"Downloading {label}")
        safe = label.replace("/", "-").replace(" ", "_")
        tmp_zip = cache_dir / f"src_{safe}.zip"
        download_file(
            zip_url, tmp_zip,
            on_progress=lambda d, t, s: report_transfer("Source download", d, t, s),
        )
        extract_parent = cache_dir / SOURCE_DIR_NAME / f"_{safe}_extract"
        extracted_root = extract_source_from_release(tmp_zip, extract_parent)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.move(str(extracted_root), str(dest))
        shutil.rmtree(extract_parent, ignore_errors=True)
        tmp_zip.unlink(missing_ok=True)

    if branch_mode:
        report(0, "Checking release", f"Checking branch '{branch}'")
        logger(f"Checking GitHub branch '{branch}'...")
        head_sha = fetch_branch_head(branch)
        ref_label = f"{branch}@{head_sha[:7]}"
        resource_ref = branch
        safe_branch = branch.replace("/", "-")
        source_root = cache_dir / SOURCE_DIR_NAME / f"branch-{safe_branch}"
        needs_release_update = (
            state.get("branch_ref") != f"{branch}:{head_sha}" or not source_root.exists()
        )
        if needs_release_update:
            logger(f"Branch update detected: {ref_label}")
            _acquire_source(GITHUB_BRANCH_ZIP.format(ref=branch), source_root, f"branch {branch}")
            state["branch_ref"] = f"{branch}:{head_sha}"
            state["release_tag"] = ref_label
    else:
        report(0, "Checking release", "Checking latest GitHub release metadata")
        if use_prerelease:
            logger("Checking latest GitHub release (pre-releases included)...")
        else:
            logger("Checking latest GitHub release...")
        release = fetch_latest_release(include_prerelease=use_prerelease)
        latest_tag = release["tag"]
        ref_label = latest_tag
        resource_ref = DEFAULT_BRANCH
        source_root = cache_dir / SOURCE_DIR_NAME / latest_tag
        needs_release_update = (
            state.get("release_tag") != latest_tag or not source_root.exists()
        )
        state.pop("branch_ref", None)
        if needs_release_update:
            logger(f"Release update detected: {latest_tag}")
            _acquire_source(release["zipball_url"], source_root, f"release {latest_tag}")
            state["release_tag"] = latest_tag

    if not source_root.exists():
        raise LauncherError("Local source cache is missing unexpectedly")

    launch_cmd: list[str]
    launch_cwd: Path
    runtime_content_root: Path

    required_version = ".".join(str(part) for part in REQUIRED_PYTHON_VERSION)
    required_cmd = detect_python_command(logger=logger)   # exact required version
    any_cmd, any_version = detect_any_python(logger=logger)  # ANY python, as a signal

    report(2, "Preparing environment", "Selecting runtime")
    ctx = {
        "branch": branch,
        "branch_mode": branch_mode,
        "has_any_python": bool(any_cmd),
        "any_python_version": any_version,
        "has_required_python": bool(required_cmd),
        "required_version": required_version,
        "install_url": python_install_url(),
        "requirements_path": source_root / "requirements.txt",
    }

    # The chooser (provided by the UI) runs the consent flow and returns the
    # runtime decision. Without one, fall back to the old automatic behaviour.
    if runtime_chooser is not None:
        decision = runtime_chooser(ctx) or {}
    else:
        decision = {"mode": "source" if required_cmd else "prebuilt"}
    mode = decision.get("mode", "prebuilt")

    if branch_mode and mode != "source":
        raise LauncherError(
            f"Running branch '{branch}' requires building from source with "
            f"Python {required_version}."
        )

    if mode == "source":
        python_cmd = decision.get("python_cmd") or required_cmd
        if not python_cmd:
            raise LauncherError(
                f"Source build was selected but Python {required_version} was not found."
            )
        logger("Building and running from source via cached virtual environment")
        report(2, "Preparing environment", "Creating/updating venv")
        venv_dir = cache_dir / VENV_DIR_NAME
        venv_python = ensure_venv(venv_dir, logger, python_cmd)

        report(3, "Building executable", "Installing requirements (running from source)")
        req_digest = requirements_digest(source_root)
        logger("Syncing Python requirements in cached venv...")
        install_dependencies(venv_python, source_root, logger)

        main_py = source_root / "main.py"
        if not main_py.exists():
            raise LauncherError("Downloaded source does not contain main.py")

        launch_cmd = [str(venv_python), str(main_py)]
        launch_cwd = source_root
        runtime_content_root = source_root
        state["runtime_mode"] = "raw_source"
        state["python_source"] = "system"
        state["venv_ready"] = True
        state["requirements_digest"] = req_digest
    else:
        if os.name != "nt":
            raise LauncherError(
                "No prebuilt binary is available for this platform. Install "
                f"Python {required_version} and build from source instead."
            )
        logger("Using prebuilt runtime")
        report(2, "Preparing environment", "Using prebuilt runtime")
        report(3, "Building executable", "Downloading prebuilt executable")

        def _download_prebuilt_binary() -> Path:
            asset = find_windows_prebuilt_asset(release)
            asset_name = str(asset.get("name", "runtime asset"))
            asset_url = str(asset.get("browser_download_url", ""))
            if not asset_url:
                raise LauncherError(f"Runtime asset {asset_name} has no download URL")

            cached_asset = cache_dir / asset_name
            download_file(
                asset_url,
                cached_asset,
                on_progress=lambda d, t, s: report_transfer("Binary download", d, t, s),
            )

            return install_prebuilt_runtime_from_file(
                cached_asset,
                cache_dir,
                runtime_dir,
                logger,
            )

        prebuilt_missing = not runtime_exe.exists()
        if needs_release_update or prebuilt_missing or state.get("runtime_mode") != "prebuilt":
            _download_prebuilt_binary()
            copy_source_runtime_content(source_root, runtime_dir, logger)
        else:
            logger("Using cached prebuilt runtime")

        launch_cmd = [str(runtime_exe)]
        launch_cwd = runtime_dir
        runtime_content_root = runtime_dir
        state["runtime_mode"] = "prebuilt"

    if needs_release_update and state.get("runtime_mode") == "raw_source":
        logger("Release source cache updated")

    report(4, "Checking fonts", "Validating release fonts against installed fonts")
    fonts_need_check = (
        state.get("installed_fonts_checked_tag") != state.get("release_tag")
        or state.get("font_install_version") != FONT_INSTALL_VERSION
    )
    if fonts_need_check:
        logger("Checking release fonts...")
        install_missing_fonts(source_root, state, logger)
    else:
        logger("Fonts already checked for this release")

    report(5, "Checking resources", "Validating remote resource package link")
    logger("Checking remote resource link...")
    try:
        remote_resource_links = fetch_remote_resource_links(resource_ref)
    except Exception as link_exc:
        logger(f"Remote resource link check failed; keeping existing resources: {link_exc}")
        remote_resource_links = []
    if remote_resource_links and state.get("resource_links") != remote_resource_links:
        part_count = len(remote_resource_links)
        logger(f"Resource links changed. Downloading {part_count} part(s)...")
        resource_zip = cache_dir / "resources_latest.zip"
        try:
            # The zip is split across parts so each stays under the host's size
            # cap; download each in order and concatenate back into one zip.
            with open(resource_zip, "wb") as combined:
                for index, link in enumerate(remote_resource_links, start=1):
                    part_path = cache_dir / f"resources_part_{index}.bin"
                    label = f"Resource download (part {index}/{part_count})"
                    download_file(
                        link,
                        part_path,
                        on_progress=lambda d, t, s, _l=label: report_transfer(_l, d, t, s),
                    )
                    with open(part_path, "rb") as part_file:
                        shutil.copyfileobj(part_file, combined)
                    part_path.unlink(missing_ok=True)
            replace_resources_from_zip(resource_zip, runtime_content_root, logger)
            resource_zip.unlink(missing_ok=True)
            state["resource_links"] = remote_resource_links
        except Exception as resource_exc:
            logger(f"Resource update failed; keeping previous resources: {resource_exc}")
    elif not remote_resource_links:
        logger("Remote current_resource_links is empty; keeping local resources")
    else:
        logger("Resources are already up to date")

    ready_label = f"Branch {ref_label}" if branch_mode else f"Release {ref_label}"
    report(6, "Ready to launch", f"{ready_label} is ready")
    save_json(state_path, state)
    return launch_cmd, launch_cwd, state


class LauncherUI:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("900x640")
        self.root.minsize(820, 600)

        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.runtime_launch_cmd: list[str] | None = None
        self.runtime_cwd: Path | None = None
        self.has_launched = False
        self.active_progress_is_indeterminate = True
        self.is_dark_mode = False

        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            self.cache_dir = Path(local_appdata) / "soli_dstate" / "DOOM-Tools-Binary"
        else:
            self.cache_dir = Path.home() / "AppData" / "Local" / "soli_dstate" / "DOOM-Tools-Binary"
        self.state_path = self.cache_dir / STATE_FILE_NAME
        self.launch_settings_path = self.cache_dir / LAUNCH_SETTINGS_FILE_NAME
        self.launch_settings = self._load_launch_settings()
        self.logger, self.log_path = configure_launcher_logger(self.queue, self.cache_dir)

        self.style = ttk.Style(self.root)
        self._apply_windows11_theme()

        self._build_ui()

        self.worker = threading.Thread(target=self._worker_thread, daemon=True)
        self.worker.start()
        self.root.after(100, self._poll)

    def _apply_windows11_theme(self) -> None:
        if darkdetect is not None:
            try:
                self.is_dark_mode = bool(darkdetect.isDark())
            except Exception:
                self.is_dark_mode = False

        theme_applied = False
        if sv_ttk is not None:
            try:
                sv_ttk.set_theme("dark" if self.is_dark_mode else "light")
                theme_applied = True
            except Exception:
                theme_applied = False

        if not theme_applied:
            for theme in ("vista", "xpnative", "winnative", "clam"):
                if theme in self.style.theme_names():
                    self.style.theme_use(theme)
                    break

        self.style.configure("TLabel", font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI Semibold", 14))
        self.style.configure("Subtle.TLabel", font=("Segoe UI", 9))
        self.style.configure("TButton", font=("Segoe UI", 10), padding=(10, 6))
        self.style.configure("Small.TButton", font=("Segoe UI", 9), padding=(8, 4))
        self.style.configure("TCheckbutton", font=("Segoe UI", 10))

    def _normalize_launch_settings(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        raw = payload if isinstance(payload, dict) else {}
        normalized: dict[str, Any] = {}
        for key, default in DEFAULT_LAUNCH_SETTINGS.items():
            if isinstance(default, bool):
                normalized[key] = bool(raw.get(key, default))
            else:  # string settings (e.g. branch)
                value = raw.get(key, default)
                normalized[key] = str(value) if value is not None else default
        return normalized

    def _load_launch_settings(self) -> dict[str, bool]:
        return self._normalize_launch_settings(load_json(self.launch_settings_path))

    def _save_launch_settings(self) -> None:
        save_json(self.launch_settings_path, self.launch_settings)

    # ── main-thread marshaling for worker-initiated dialogs ──────────────────
    def _run_on_main(self, fn):
        """Run fn on the Tk main thread and return its result (blocking)."""
        if threading.current_thread() is threading.main_thread():
            return fn()
        holder: dict[str, Any] = {}
        done = threading.Event()
        self.queue.put(("ask", (fn, holder, done)))
        done.wait()
        if "error" in holder:
            raise holder["error"]
        return holder.get("result")

    def _notify_if_unfocused(self, message: str) -> None:
        """Desktop-notify + raise the window when a prompt needs attention."""
        try:
            focused = self.root.focus_displayof() is not None
        except Exception:
            focused = True
        if not focused:
            try:
                self.root.bell()
            except Exception:
                logging.exception("Suppressed exception")
            send_desktop_notification(APP_NAME, message, logger=self.logger)
        for action in (self.root.deiconify, self.root.lift):
            try:
                action()
            except Exception:
                logging.exception("Suppressed exception")
        try:
            self.root.attributes("-topmost", True)
            self.root.after(1500, lambda: self.root.attributes("-topmost", False))
        except Exception:
            logging.exception("Suppressed exception")

    def _show_requirements_popup(self, req_path: Path) -> None:
        try:
            content = Path(req_path).read_text(encoding="utf-8")
        except Exception as exc:
            content = f"Could not read requirements.txt:\n{exc}"
        win = tk.Toplevel(self.root)
        win.title("requirements.txt")
        win.transient(self.root)
        win.geometry("520x440")
        frame = ttk.Frame(win, padding=(12, 12, 12, 12))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Packages to be installed via pip:", style="Header.TLabel").pack(anchor=W)
        box = Text(frame, wrap="none", height=18)
        box.pack(fill="both", expand=True, pady=(8, 8))
        box.insert(END, content)
        box.configure(state=DISABLED)
        ttk.Button(frame, text="Close", command=win.destroy, width=12, style="Small.TButton").pack(anchor="e")
        win.grab_set()
        win.wait_visibility()
        win.focus_set()
        win.wait_window()

    def _do_source_consent(self, ctx: dict) -> dict:
        branch_mode = ctx["branch_mode"]
        self._notify_if_unfocused("DOOM-Tools needs your input: build from source?")
        dialog = tk.Toplevel(self.root)
        dialog.title("Build From Source?")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=(16, 14, 16, 14))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Run DOOM-Tools from source?", style="Header.TLabel").pack(anchor=W)
        ver = ctx.get("any_python_version") or "unknown"
        if branch_mode:
            msg = (f"Branch '{ctx['branch']}' has no prebuilt binary, so it must be built "
                   f"from source. Detected Python {ver}. Proceed?")
        else:
            msg = (f"A Python {ver} installation was detected. DOOM-Tools can build and "
                   "run from source (creates a virtual environment), or simply download "
                   "the prebuilt binary instead.")
        ttk.Label(frame, text=msg, style="Subtle.TLabel", wraplength=430, justify="left").pack(anchor=W, pady=(6, 10))

        result = {"choice": "cancel", "suppress": False}
        suppress_var = tk.BooleanVar(value=False)
        if not branch_mode:
            ttk.Checkbutton(
                frame,
                text="Don't ask again — always use the prebuilt binary",
                variable=suppress_var,
            ).pack(anchor=W, pady=(0, 10))

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(4, 0))

        def _pick(choice: str) -> None:
            result["choice"] = choice
            result["suppress"] = bool(suppress_var.get())
            dialog.destroy()

        if branch_mode:
            ttk.Button(row, text="Cancel", command=lambda: _pick("cancel"), width=14, style="Small.TButton").pack(side=RIGHT)
            ttk.Button(row, text="Build from source", command=lambda: _pick("source"), width=18).pack(side=RIGHT, padx=(0, 8))
        else:
            ttk.Button(row, text="Use prebuilt binary", command=lambda: _pick("prebuilt"), width=18, style="Small.TButton").pack(side=RIGHT)
            ttk.Button(row, text="Build from source", command=lambda: _pick("source"), width=18).pack(side=RIGHT, padx=(0, 8))

        dialog.protocol("WM_DELETE_WINDOW", lambda: _pick("cancel"))
        dialog.grab_set()
        dialog.wait_visibility()
        dialog.focus_set()
        dialog.wait_window()
        return result

    def _do_python_missing(self, ctx: dict) -> str:
        branch_mode = ctx["branch_mode"]
        required = ctx["required_version"]
        url = ctx["install_url"]
        self._notify_if_unfocused(f"DOOM-Tools needs the free-threaded Python {required} build.")
        dialog = tk.Toplevel(self.root)
        dialog.title("Free-Threaded Python Required")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=(16, 14, 16, 14))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"Free-threaded Python {required} is required", style="Header.TLabel").pack(anchor=W)
        ttk.Label(
            frame,
            text=(f"DOOM-Tools runs without the GIL and needs the free-threaded (no-GIL) "
                  f"build of Python {required}. A standard build won't work (it crashes "
                  "with 'Disabling the GIL is not supported by this build'). Install the "
                  "free-threaded build, then relaunch and choose 'Build from source' again."),
            style="Subtle.TLabel", wraplength=460, justify="left",
        ).pack(anchor=W, pady=(6, 8))

        if os.name == "nt":
            hint = ("In the installer pick 'Customize installation' -> 'Advanced Options' and "
                    "tick 'Download free-threaded binaries (experimental)'. That installs "
                    "python3.13t, runnable via 'py -3.13t'.")
        elif sys.platform == "darwin":
            hint = ("Install the python.org build and ensure the free-threaded interpreter "
                    "(python3.13t) is on your PATH.")
        else:
            hint = ("Install or build the free-threaded interpreter — e.g. a "
                    "python3.13-freethreading/nogil package, or build CPython with "
                    "'--disable-gil'.")
        ttk.Label(frame, text=hint, style="Subtle.TLabel", wraplength=460, justify="left").pack(anchor=W, pady=(0, 8))

        link = ttk.Label(frame, text=f"Download Python {required} (python.org)",
                         foreground="#3b82f6", cursor="hand2")
        link.pack(anchor=W, pady=(0, 2))
        link.bind("<Button-1>", lambda _e: webbrowser.open(url))
        ttk.Label(frame, text=url, style="Subtle.TLabel", wraplength=460, justify="left").pack(anchor=W, pady=(0, 12))

        result = {"choice": "cancel"}
        row = ttk.Frame(frame)
        row.pack(fill="x")

        def _pick(choice: str) -> None:
            result["choice"] = choice
            dialog.destroy()

        if branch_mode:
            ttk.Button(row, text="Close", command=lambda: _pick("cancel"), width=14).pack(side=RIGHT)
        else:
            ttk.Button(row, text="Use prebuilt binary", command=lambda: _pick("prebuilt"), width=18).pack(side=RIGHT, padx=(0, 8))
            ttk.Button(row, text="Cancel", command=lambda: _pick("cancel"), width=12, style="Small.TButton").pack(side=RIGHT)

        dialog.protocol("WM_DELETE_WINDOW", lambda: _pick("cancel"))
        dialog.grab_set()
        dialog.wait_visibility()
        dialog.focus_set()
        dialog.wait_window()
        return result["choice"]

    def _do_venv_consent(self, ctx: dict) -> bool:
        required = ctx["required_version"]
        req_path = ctx["requirements_path"]
        self._notify_if_unfocused("DOOM-Tools needs your input: set up the source environment?")
        dialog = tk.Toplevel(self.root)
        dialog.title("Create Virtual Environment?")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=(16, 14, 16, 14))
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Set up the source environment?", style="Header.TLabel").pack(anchor=W)
        ttk.Label(
            frame,
            text=(f"Python {required} was found. DOOM-Tools will create a virtual "
                  "environment (.venv) and install the packages listed in "
                  "requirements.txt via pip, then run from source."),
            style="Subtle.TLabel", wraplength=450, justify="left",
        ).pack(anchor=W, pady=(6, 12))

        result = {"ok": False}
        row = ttk.Frame(frame)
        row.pack(fill="x")

        def _proceed() -> None:
            result["ok"] = True
            dialog.destroy()

        ttk.Button(row, text="Cancel", command=dialog.destroy, width=12, style="Small.TButton").pack(side=RIGHT)
        ttk.Button(row, text="Proceed", command=_proceed, width=14).pack(side=RIGHT, padx=(0, 8))
        ttk.Button(row, text="Show requirements.txt",
                   command=lambda: self._show_requirements_popup(req_path),
                   width=20, style="Small.TButton").pack(side=LEFT)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        dialog.wait_visibility()
        dialog.focus_set()
        dialog.wait_window()
        return result["ok"]

    def runtime_chooser(self, ctx: dict) -> dict:
        """Worker-thread callback that runs the consent flow and returns the
        chosen runtime: {"mode": "source"|"prebuilt"}."""
        branch_mode = ctx["branch_mode"]

        if not ctx["has_any_python"]:
            if branch_mode:
                raise LauncherError(
                    f"Running branch '{ctx['branch']}' needs Python {ctx['required_version']}, "
                    "but no Python was found. Install it and relaunch."
                )
            self.log("No Python detected; using the prebuilt binary.")
            return {"mode": "prebuilt"}

        if not branch_mode and self.launch_settings.get("suppress_source_prompt", False):
            self.log("Source-build prompt suppressed in settings; using the prebuilt binary.")
            return {"mode": "prebuilt"}

        consent = self._run_on_main(lambda: self._do_source_consent(ctx))
        if consent["choice"] == "cancel":
            raise LauncherError("Setup cancelled by user.")
        if consent["choice"] == "prebuilt":
            if consent.get("suppress"):
                self.launch_settings["suppress_source_prompt"] = True
                self._save_launch_settings()
                self._run_on_main(self._refresh_launch_options_label)
                self.log("Future source-build prompts suppressed (re-enable in Settings).")
            return {"mode": "prebuilt"}

        # User opted to build from source -> require the exact Python version.
        if not ctx["has_required_python"]:
            outcome = self._run_on_main(lambda: self._do_python_missing(ctx))
            if outcome == "prebuilt":
                return {"mode": "prebuilt"}
            raise LauncherError(
                f"Python {ctx['required_version']} is required to build from source."
            )

        if not self._run_on_main(lambda: self._do_venv_consent(ctx)):
            if branch_mode:
                raise LauncherError("Setup cancelled by user.")
            return {"mode": "prebuilt"}
        return {"mode": "source"}

    def _launch_flags_text(self) -> str:
        labels = []
        if self.launch_settings.get("devmode", False):
            labels.append("dev")
        if self.launch_settings.get("debug", False):
            labels.append("debug")
        if self.launch_settings.get("dmmode", False):
            labels.append("dm")
        if not labels:
            return "none"
        return ", ".join(labels)

    def _refresh_launch_options_label(self) -> None:
        console_mode = "on" if self.launch_settings.get("keep_console_open", False) else "off"
        branch = str(self.launch_settings.get("branch", "") or "")
        if branch:
            channel = f"branch:{branch}"
        else:
            channel = "pre-release" if self.launch_settings.get("use_prerelease", False) else "stable"
        self.options_label.configure(
            text=f"Launch options: {self._launch_flags_text()} | console: {console_mode} | channel: {channel}"
        )

    def _open_settings_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Launch Settings")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=(14, 12, 14, 12))
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text="Launcher Settings",
            style="Header.TLabel",
        ).pack(anchor=W)
        ttk.Label(
            frame,
            text="Choose startup flags for DOOM-Tools.",
            style="Subtle.TLabel",
        ).pack(anchor=W, pady=(2, 10))

        flags_group = ttk.LabelFrame(frame, text="Launch Flags", padding=(10, 8, 10, 8))
        flags_group.pack(fill="x")

        devmode_var = tk.BooleanVar(value=self.launch_settings.get("devmode", False))
        debug_var = tk.BooleanVar(value=self.launch_settings.get("debug", False))
        dmmode_var = tk.BooleanVar(value=self.launch_settings.get("dmmode", False))
        console_var = tk.BooleanVar(value=self.launch_settings.get("keep_console_open", False))
        prerelease_var = tk.BooleanVar(value=self.launch_settings.get("use_prerelease", False))

        ttk.Checkbutton(flags_group, text="Enable Dev Mode (--dev)", variable=devmode_var).pack(anchor=W)
        ttk.Checkbutton(flags_group, text="Enable Debug Mode (--debug)", variable=debug_var).pack(anchor=W)
        ttk.Checkbutton(flags_group, text="Enable DM Mode (--dm)", variable=dmmode_var).pack(anchor=W)

        updates_group = ttk.LabelFrame(frame, text="Updates", padding=(10, 8, 10, 8))
        updates_group.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            updates_group,
            text="Use pre-release builds",
            variable=prerelease_var,
        ).pack(anchor=W)
        ttk.Label(
            updates_group,
            text="Installs the newest release including pre-releases (alpha/beta/rc). May be unstable.",
            style="Subtle.TLabel",
        ).pack(anchor=W, pady=(4, 0))

        # ── Branch / source channel ──
        STABLE_LABEL = "(Stable releases)"
        ttk.Label(updates_group, text="Source channel:").pack(anchor=W, pady=(10, 2))
        current_branch = str(self.launch_settings.get("branch", "") or "")
        branch_var = tk.StringVar(value=current_branch or STABLE_LABEL)
        branch_combo = ttk.Combobox(
            updates_group, textvariable=branch_var, values=[STABLE_LABEL], width=28,
        )
        branch_combo.pack(anchor=W)
        ttk.Label(
            updates_group,
            text="Pick a git branch to run its source directly (requires Python), "
                 "or stay on stable releases.",
            style="Subtle.TLabel",
        ).pack(anchor=W, pady=(4, 0))

        def _populate_branches() -> None:
            try:
                names = fetch_branches()
            except Exception:
                return
            def _apply() -> None:
                vals = [STABLE_LABEL] + names
                if current_branch and current_branch not in names:
                    vals.append(current_branch)
                branch_combo.configure(values=vals)
            try:
                branch_combo.after(0, _apply)
            except Exception:
                logging.exception("Suppressed exception")

        threading.Thread(target=_populate_branches, daemon=True).start()

        ask_source_var = tk.BooleanVar(
            value=not self.launch_settings.get("suppress_source_prompt", False)
        )
        ttk.Checkbutton(
            updates_group,
            text="Ask whether to build from source on launch",
            variable=ask_source_var,
        ).pack(anchor=W, pady=(10, 0))
        ttk.Label(
            updates_group,
            text="When off, the prebuilt binary is always used without prompting.",
            style="Subtle.TLabel",
        ).pack(anchor=W, pady=(2, 0))

        console_group = ttk.LabelFrame(frame, text="Console", padding=(10, 8, 10, 8))
        console_group.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            console_group,
            text="Show a console window when launching DOOM-Tools",
            variable=console_var,
        ).pack(anchor=W)
        ttk.Label(
            console_group,
            text="PYTHON_GIL=0 is always set for launched DOOM-Tools processes.",
            style="Subtle.TLabel",
        ).pack(anchor=W, pady=(4, 0))

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(12, 0))

        def _save_and_close() -> None:
            chosen = branch_var.get().strip()
            branch_val = "" if chosen in ("", STABLE_LABEL) else chosen
            self.launch_settings = {
                "devmode": bool(devmode_var.get()),
                "debug": bool(debug_var.get()),
                "dmmode": bool(dmmode_var.get()),
                "keep_console_open": bool(console_var.get()),
                "use_prerelease": bool(prerelease_var.get()),
                "branch": branch_val,
                "suppress_source_prompt": not bool(ask_source_var.get()),
            }
            self._save_launch_settings()
            self._refresh_launch_options_label()
            self.status_label.configure(text="Launch settings saved.")
            dialog.destroy()

        ttk.Button(button_row, text="Cancel", command=dialog.destroy, width=12, style="Small.TButton").pack(side=RIGHT)
        ttk.Button(button_row, text="Save", command=_save_and_close, width=12).pack(side=RIGHT, padx=(0, 8))

        dialog.wait_visibility()
        dialog.focus_set()

    def _build_ui(self) -> None:
        bg = self.style.lookup("TFrame", "background") or "#f0f0f0"
        self.root.configure(bg=bg)

        header = ttk.Frame(self.root, padding=(16, 12, 16, 8))
        header.pack(fill="x")

        ttk.Label(
            header,
            text="DOOM-Tools Setup",
            style="Header.TLabel",
            anchor=W,
        ).pack(fill="x")
        ttk.Label(
            header,
            text="This wizard checks for updates, installs resources, and prepares the runtime.",
            style="Subtle.TLabel",
            anchor=W,
        ).pack(fill="x", pady=(2, 0))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        top = ttk.Frame(self.root, padding=(16, 10, 16, 0))
        top.pack(fill="x")

        self.status_label = ttk.Label(top, text="Initializing installer checks...", anchor=W)
        self.status_label.pack(fill="x", pady=(0, 2))

        self.step_label = ttk.Label(top, text="Current step: starting", anchor=W)
        self.step_label.pack(fill="x")

        self.transfer_label = ttk.Label(top, text="Transfer: waiting", anchor=W)
        self.transfer_label.pack(fill="x", pady=(1, 0))

        self.options_label = ttk.Label(top, text="", anchor=W)
        self.options_label.pack(fill="x", pady=(1, 0))

        progress_frame = ttk.Frame(self.root, padding=(16, 6, 16, 8))
        progress_frame.pack(fill="x")

        ttk.Label(progress_frame, text="Overall progress", anchor=W).pack(fill="x")

        self.overall_progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            length=100,
            maximum=max(len(INSTALL_STEPS) - 1, 1),
            value=0,
        )
        self.overall_progress.pack(fill="x", pady=(2, 6))

        ttk.Label(progress_frame, text="Active task", anchor=W).pack(fill="x")

        self.active_progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="indeterminate",
            length=100,
        )
        self.active_progress.pack(fill="x", pady=(2, 0))
        self.active_progress.start(12)

        body = ttk.Frame(self.root, padding=(16, 0, 16, 8))
        body.pack(fill=BOTH, expand=True)

        log_container = ttk.Frame(body)
        log_container.pack(fill=BOTH, expand=True)

        log_scroll = ttk.Scrollbar(log_container, orient="vertical")
        log_scroll.pack(side=RIGHT, fill="y")

        self.log_box = Text(
            log_container,
            wrap="word",
            height=16,
            bg="#1f1f1f" if self.is_dark_mode else "white",
            fg="#e8e8e8" if self.is_dark_mode else "#202020",
            relief="sunken",
            borderwidth=1,
            font=("Consolas", 9),
            yscrollcommand=log_scroll.set,
            insertbackground="#e8e8e8" if self.is_dark_mode else "#202020",
        )
        self.log_box.pack(side=LEFT, fill=BOTH, expand=True)
        log_scroll.configure(command=self.log_box.yview)
        self.log_box.configure(state=DISABLED)
        self._configure_log_tags()

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        bottom = ttk.Frame(self.root, padding=(16, 8, 16, 12))
        bottom.pack(fill="x")

        self.settings_button = ttk.Button(bottom, text="Settings", command=self._open_settings_dialog, width=12)
        self.settings_button.pack(side=LEFT)

        self.cancel_button = ttk.Button(bottom, text="Cancel", command=self.root.destroy, width=12, style="Small.TButton")
        self.cancel_button.pack(side=RIGHT)

        self.launch_button = ttk.Button(
            bottom,
            text="Launch DOOM-Tools",
            state=DISABLED,
            command=self.launch,
            width=18,
        )
        self.launch_button.pack(side=RIGHT, padx=(0, 8))

        self._refresh_launch_options_label()

    def _configure_log_tags(self) -> None:
        default_fg = "#e8e8e8" if self.is_dark_mode else "#202020"
        self.log_box.tag_configure("INFO", foreground="#86efac" if self.is_dark_mode else "#166534")
        self.log_box.tag_configure("DEBUG", foreground="#93c5fd" if self.is_dark_mode else "#1d4ed8")
        self.log_box.tag_configure("WARNING", foreground="#facc15" if self.is_dark_mode else "#a16207")
        self.log_box.tag_configure("ERROR", foreground="#f87171" if self.is_dark_mode else "#b91c1c")
        self.log_box.tag_configure("CRITICAL", foreground="#f472b6" if self.is_dark_mode else "#be185d")
        self.log_box.tag_configure("DEFAULT", foreground=default_fg)

    def _infer_level_tag(self, message: str) -> str:
        known_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        upper_message = message.upper()
        for level in known_levels:
            if f"| {level} |" in upper_message:
                return level
        return "DEFAULT"

    def log(self, message: str) -> None:
        self.logger.info(message)

    def set_status(self, message: str) -> None:
        self.queue.put(("status", message))

    def set_progress(self, step: int, step_name: str, detail: str) -> None:
        self.queue.put(("progress", (step, step_name, detail)))

    def set_transfer(self, label: str, downloaded: int, total: int, speed: float) -> None:
        self.queue.put(("transfer", (label, downloaded, total, speed)))

    def _worker_thread(self) -> None:
        try:
            launch_cmd, launch_cwd, state = prepare_or_update(
                self.cache_dir,
                self.state_path,
                self.log,
                progress=self.set_progress,
                transfer=self.set_transfer,
                use_prerelease=self.launch_settings.get("use_prerelease", False),
                branch=str(self.launch_settings.get("branch", "") or ""),
                runtime_chooser=self.runtime_chooser,
            )
            self.runtime_launch_cmd = launch_cmd
            self.runtime_cwd = launch_cwd
            self.set_status(f"Setup complete. Release: {state.get('release_tag', 'unknown')}")
            self.logger.info("Setup complete. Release: %s", state.get("release_tag", "unknown"))
            self.queue.put(("ready", ""))
        except Exception as exc:
            self.set_status(f"Setup failed: {exc}")
            self.logger.exception("Setup failed")
            self.queue.put(("error", ""))

    def _append_log(self, payload: str | tuple[str, str]) -> None:
        tag = "DEFAULT"
        message = payload
        if isinstance(payload, tuple) and len(payload) == 2:
            level_name, text = payload
            tag = str(level_name).upper()
            message = text
        else:
            tag = self._infer_level_tag(str(message))
        self.log_box.configure(state=NORMAL)
        self.log_box.insert(END, str(message) + "\n", tag)
        self.log_box.see(END)
        self.log_box.configure(state=DISABLED)

    def _poll(self) -> None:
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(payload)
            elif kind == "status":
                self.status_label.configure(text=str(payload))
            elif kind == "progress":
                if isinstance(payload, tuple) and len(payload) == 3:
                    step, step_name, detail = payload
                    self.overall_progress.configure(value=float(step))
                    self.step_label.configure(text=f"Current step: {step_name} | {detail}")
            elif kind == "transfer":
                if isinstance(payload, tuple) and len(payload) == 4:
                    label, downloaded, total, speed = payload
                    downloaded_i = int(downloaded)
                    total_i = int(total)
                    speed_f = float(speed)

                    if total_i > 0:
                        if self.active_progress_is_indeterminate:
                            self.active_progress.stop()
                            self.active_progress.configure(mode="determinate", maximum=100.0, value=0.0)
                            self.active_progress_is_indeterminate = False
                        percent = min(100.0, (downloaded_i / total_i) * 100.0)
                        self.active_progress.configure(value=percent)
                        self.transfer_label.configure(
                            text=(
                                f"{label}: {_format_size(downloaded_i)} / {_format_size(total_i)} "
                                f"({percent:.1f}%) at {_format_size(speed_f)}/s"
                            )
                        )
                    else:
                        if not self.active_progress_is_indeterminate:
                            self.active_progress.configure(mode="indeterminate")
                            self.active_progress.start(12)
                            self.active_progress_is_indeterminate = True
                        self.transfer_label.configure(
                            text=f"{label}: {_format_size(downloaded_i)} downloaded at {_format_size(speed_f)}/s"
                        )
            elif kind == "ask":
                # A worker thread asked us to run something on the main thread
                # (a consent dialog) and is blocked until we set the event.
                fn, holder, done = payload
                try:
                    holder["result"] = fn()
                except Exception as exc:  # surface to the worker
                    holder["error"] = exc
                finally:
                    done.set()
            elif kind == "ready":
                self.active_progress.stop()
                self.active_progress_is_indeterminate = False
                self.overall_progress.configure(value=max(len(INSTALL_STEPS) - 1, 1))
                self.launch_button.configure(state=NORMAL)
                self.cancel_button.configure(text="Close")
                self.transfer_label.configure(text="Transfer: complete")
                send_desktop_notification(
                    APP_NAME,
                    "DOOM-Tools is ready to launch.",
                    logger=self.logger,
                )
            elif kind == "error":
                self.active_progress.stop()
                self.active_progress_is_indeterminate = False
                self.launch_button.configure(state=DISABLED)

        self.root.after(100, self._poll)

    def launch(self) -> None:
        if self.has_launched:
            return
        if not self.runtime_launch_cmd or not self.runtime_cwd:
            self.set_status("Cannot launch: runtime is not available")
            return
        launch_cmd = list(self.runtime_launch_cmd)
        runtime_dir = self.runtime_cwd

        if self.launch_settings.get("devmode", False):
            launch_cmd.append("--dev")
        if self.launch_settings.get("debug", False):
            launch_cmd.append("--debug")
        if self.launch_settings.get("dmmode", False):
            launch_cmd.append("--dm")

        self.set_status(f"Launching DOOM-Tools ({self._launch_flags_text()})...")
        self.has_launched = True
        self.launch_button.configure(state=DISABLED)
        self.settings_button.configure(state=DISABLED)

        launch_env = os.environ.copy()
        # DOOM-Tools requires a free-threaded (no-GIL) build, so always disable
        # the GIL. The runtime selection guarantees a free-threaded interpreter.
        launch_env["PYTHON_GIL"] = "0"
        self.logger.info("Launching DOOM-Tools with flags: %s", self._launch_flags_text())

        if os.name == "nt":
            if self.launch_settings.get("debug", False):
                # In debug mode, ALWAYS keep the console open after the app exits
                # (success or crash) so tracebacks / import errors stay readable.
                # The exit code is captured immediately into a var because the
                # following commands would otherwise reset %errorlevel%.
                cmdline = subprocess.list2cmdline(launch_cmd)
                guarded_cmd = (
                    f'{cmdline} & set "DT_RC=!errorlevel!" '
                    '& echo. & echo [DOOM-Tools debug] process exited with code !DT_RC!. '
                    '& echo Press any key to close this console... & pause >nul'
                )
                subprocess.Popen(
                    ["cmd", "/v:on", "/c", guarded_cmd],
                    cwd=str(runtime_dir),
                    env=launch_env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            elif self.launch_settings.get("keep_console_open", False):
                subprocess.Popen(
                    launch_cmd,
                    cwd=str(runtime_dir),
                    env=launch_env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(
                    launch_cmd,
                    cwd=str(runtime_dir),
                    env=launch_env,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
        else:
            subprocess.Popen(launch_cmd, cwd=str(runtime_dir), env=launch_env)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    hide_console_window()
    mutex = acquire_single_instance_lock()
    if os.name == "nt" and mutex == 0:
        messagebox.showinfo(APP_NAME, "DOOM-Tools Launcher is already running.")
        return 0

    try:
        ui = LauncherUI()
        ui.run()
        return 0
    finally:
        release_single_instance_lock(mutex)


if __name__ == "__main__":
    raise SystemExit(main())
