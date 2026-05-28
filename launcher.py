import ctypes
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import BOTH, DISABLED, END, LEFT, NORMAL, RIGHT, W, Text, Tk, messagebox, ttk
from typing import Any, Callable

import requests


OWNER = "soli-dstate"
REPO = "DOOM-Tools"
GITHUB_API_RELEASE = f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
GITHUB_RAW_MAIN = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/master/main.py"

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
}

SOURCE_COPY_DIRS = ("tables", "themes", "fonts")
RESOURCE_DIRS = ("sounds", "images")
FONT_SUFFIXES = (".ttf", ".otf")

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


class LauncherError(RuntimeError):
    pass


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
        pass


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


def fetch_latest_release() -> dict:
    response = requests.get(
        GITHUB_API_RELEASE,
        timeout=20,
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()
    data = response.json()
    tag = str(data.get("tag_name", "")).strip()
    zipball_url = str(data.get("zipball_url", "")).strip()
    assets = data.get("assets", [])
    if not isinstance(assets, list):
        assets = []
    if not tag or not zipball_url:
        raise LauncherError("Latest release response missing tag_name or zipball_url")
    return {"tag": tag, "zipball_url": zipball_url, "assets": assets}


def fetch_remote_resource_link() -> str:
    response = requests.get(GITHUB_RAW_MAIN, timeout=20)
    response.raise_for_status()
    pattern = re.compile(r"^current_resource_link\s*=\s*[\"\'](.*?)[\"\']\s*$", re.MULTILINE)
    match = pattern.search(response.text)
    if not match:
        return ""
    return match.group(1).strip()


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
    with requests.get(url, timeout=120, stream=True) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", "0") or "0")
        downloaded = 0
        started = time.perf_counter()
        last_emit = started
        with out_path.open("wb") as handle:
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
        return python_path

    logger("Creating virtual environment...")
    subprocess.run(python_cmd + ["-m", "venv", str(venv_dir)], check=True)
    if not python_path.exists():
        raise LauncherError("Failed to create virtual environment")
    return python_path


def detect_python_command() -> list[str] | None:
    candidates: list[list[str]] = []
    if os.name == "nt" and shutil.which("py"):
        candidates.append(["py", "-3"])
    if shutil.which("python"):
        candidates.append(["python"])
    if shutil.which("python3"):
        candidates.append(["python3"])

    for base in candidates:
        try:
            completed = subprocess.run(
                base + ["-c", "import sys; print(sys.version)"] ,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
            )
            if completed.returncode == 0:
                return base
        except Exception:
            continue
    return None


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

    run_logged([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], logger)
    run_logged([str(venv_python), "-m", "pip", "install", "-r", str(req_file)], logger)


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


def get_installed_font_names_windows() -> set[str]:
    names: set[str] = set()
    windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
    user_fonts = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"

    for folder in (windows_fonts, user_fonts):
        if folder.exists():
            for file_path in folder.iterdir():
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

    value_name = f"{font_path.stem} (TrueType)"
    reg_path = r"Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, dest_name)

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

    installed = get_installed_font_names_windows()
    installed_any = False

    for font_file in remote_fonts:
        if font_file.name.lower() in installed:
            continue
        try:
            installed_any = install_font_windows(font_file, logger) or installed_any
        except Exception as exc:
            logger(f"Font install failed for {font_file.name}: {exc}")

    if not installed_any:
        logger("All release fonts are already installed")

    state["installed_fonts_checked_tag"] = state.get("release_tag", "")


def prepare_or_update(
    cache_dir: Path,
    state_path: Path,
    logger,
    progress=None,
    transfer=None,
) -> tuple[Path, dict]:
    def report(step: int, status: str, detail: str = "") -> None:
        if progress:
            progress(step, status, detail)

    def report_transfer(label: str, downloaded: int, total: int, speed: float) -> None:
        if transfer:
            transfer(label, downloaded, total, speed)

    state = load_json(state_path)

    report(0, "Checking release", "Checking latest GitHub release metadata")
    logger("Checking latest GitHub release...")
    release = fetch_latest_release()
    latest_tag = release["tag"]

    source_root = cache_dir / SOURCE_DIR_NAME / latest_tag
    runtime_dir = cache_dir / RUNTIME_DIR_NAME
    runtime_exe = runtime_dir / EXE_NAME

    needs_release_update = (
        state.get("release_tag") != latest_tag
        or not source_root.exists()
        or not runtime_exe.exists()
    )

    if needs_release_update:
        logger(f"Release update detected: {latest_tag}")
        report(1, "Downloading source", f"Downloading release {latest_tag}")
        tmp_zip = cache_dir / f"release_{latest_tag}.zip"
        download_file(
            release["zipball_url"],
            tmp_zip,
            on_progress=lambda d, t, s: report_transfer("Source download", d, t, s),
        )

        extract_parent = cache_dir / SOURCE_DIR_NAME / f"_{latest_tag}_extract"
        extracted_root = extract_source_from_release(tmp_zip, extract_parent)
        source_root.parent.mkdir(parents=True, exist_ok=True)

        if source_root.exists():
            shutil.rmtree(source_root, ignore_errors=True)
        shutil.move(str(extracted_root), str(source_root))
        shutil.rmtree(extract_parent, ignore_errors=True)
        tmp_zip.unlink(missing_ok=True)

        def _download_prebuilt_binary() -> Path:
            if os.name != "nt":
                raise LauncherError("No Python detected on this platform and no local build is possible")

            logger("Using prebuilt release binary")
            report(2, "Preparing environment", "Using release binary fallback")
            report(3, "Building executable", "Downloading prebuilt executable")
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

        python_cmd = detect_python_command()
        python_source = "system"
        if not python_cmd and os.name == "nt":
            logger("No system Python detected; attempting bundled builder toolchain")
            report(2, "Preparing environment", "Downloading bundled builder toolchain")
            try:
                python_cmd = ensure_windows_builder_python(
                    release,
                    cache_dir,
                    latest_tag,
                    logger,
                    transfer_cb=report_transfer,
                )
                if python_cmd:
                    python_source = "bundled_toolchain"
            except Exception as toolchain_exc:
                logger(f"Bundled builder toolchain unavailable: {toolchain_exc}")
                python_cmd = None

        if python_cmd:
            try:
                logger("Preparing Python environment...")
                report(2, "Preparing environment", "Creating venv and installing dependencies")
                venv_dir = cache_dir / VENV_DIR_NAME
                venv_python = ensure_venv(venv_dir, logger, python_cmd)
                install_dependencies(venv_python, source_root, logger)

                logger("Building executable from latest release source...")
                report(3, "Building executable", "Compiling latest source with PyInstaller")
                built_exe = build_executable(venv_python, source_root, cache_dir, logger)
                state["build_mode"] = python_source
            except Exception as build_exc:
                logger(f"Source build failed; falling back to prebuilt binary: {build_exc}")
                built_exe = _download_prebuilt_binary()
                state["build_mode"] = "prebuilt"
        else:
            logger("No system Python detected; switching to prebuilt release binary")
            built_exe = _download_prebuilt_binary()
            state["build_mode"] = "prebuilt"

        runtime_dir.mkdir(parents=True, exist_ok=True)
        if built_exe.resolve() != runtime_exe.resolve():
            shutil.copy2(built_exe, runtime_exe)
        copy_source_runtime_content(source_root, runtime_dir, logger)

        state["release_tag"] = latest_tag
    else:
        logger("Using cached build for current release")
        report(3, "Building executable", "Using cached build")

    if not source_root.exists():
        raise LauncherError("Local source cache is missing unexpectedly")

    report(4, "Checking fonts", "Validating release fonts against installed fonts")
    if state.get("installed_fonts_checked_tag") != state.get("release_tag"):
        logger("Checking release fonts...")
        install_missing_fonts(source_root, state, logger)
    else:
        logger("Fonts already checked for this release")

    report(5, "Checking resources", "Validating remote resource package link")
    logger("Checking remote resource link...")
    remote_resource_link = fetch_remote_resource_link()
    if remote_resource_link and state.get("resource_link") != remote_resource_link:
        logger("Resource link changed. Downloading updated resources...")
        resource_zip = cache_dir / "resources_latest.zip"
        download_file(
            remote_resource_link,
            resource_zip,
            on_progress=lambda d, t, s: report_transfer("Resource download", d, t, s),
        )
        replace_resources_from_zip(resource_zip, runtime_dir, logger)
        resource_zip.unlink(missing_ok=True)
        state["resource_link"] = remote_resource_link
    elif not remote_resource_link:
        logger("Remote current_resource_link is empty; keeping local resources")
    else:
        logger("Resources are already up to date")

    report(6, "Ready to launch", f"Release {state.get('release_tag', 'unknown')} is ready")
    save_json(state_path, state)
    return runtime_exe, state


class LauncherUI:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title(APP_NAME)
        self.root.geometry("840x560")
        self.root.minsize(780, 520)

        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.runtime_exe: Path | None = None
        self.has_launched = False
        self.active_progress_is_indeterminate = True

        self.cache_dir = Path(__file__).resolve().parent / ".launcher_cache"
        self.state_path = self.cache_dir / STATE_FILE_NAME
        self.launch_settings_path = self.cache_dir / LAUNCH_SETTINGS_FILE_NAME
        self.launch_settings = self._load_launch_settings()

        self.style = ttk.Style(self.root)
        for theme in ("vista", "xpnative", "winnative", "clam"):
            if theme in self.style.theme_names():
                self.style.theme_use(theme)
                break

        self._build_ui()

        self.worker = threading.Thread(target=self._worker_thread, daemon=True)
        self.worker.start()
        self.root.after(100, self._poll)

    def _normalize_launch_settings(self, payload: dict[str, Any] | None) -> dict[str, bool]:
        raw = payload if isinstance(payload, dict) else {}
        normalized: dict[str, bool] = {}
        for key, default in DEFAULT_LAUNCH_SETTINGS.items():
            normalized[key] = bool(raw.get(key, default))
        return normalized

    def _load_launch_settings(self) -> dict[str, bool]:
        return self._normalize_launch_settings(load_json(self.launch_settings_path))

    def _save_launch_settings(self) -> None:
        save_json(self.launch_settings_path, self.launch_settings)

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
        self.options_label.configure(
            text=f"Launch options: {self._launch_flags_text()} | console: {console_mode}"
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
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor=W)
        ttk.Label(
            frame,
            text="Choose startup flags for DOOM-Tools.",
        ).pack(anchor=W, pady=(2, 10))

        flags_group = ttk.LabelFrame(frame, text="Launch Flags", padding=(10, 8, 10, 8))
        flags_group.pack(fill="x")

        devmode_var = tk.BooleanVar(value=self.launch_settings.get("devmode", False))
        debug_var = tk.BooleanVar(value=self.launch_settings.get("debug", False))
        dmmode_var = tk.BooleanVar(value=self.launch_settings.get("dmmode", False))
        console_var = tk.BooleanVar(value=self.launch_settings.get("keep_console_open", False))

        ttk.Checkbutton(flags_group, text="Enable Dev Mode (--dev)", variable=devmode_var).pack(anchor=W)
        ttk.Checkbutton(flags_group, text="Enable Debug Mode (--debug)", variable=debug_var).pack(anchor=W)
        ttk.Checkbutton(flags_group, text="Enable DM Mode (--dm)", variable=dmmode_var).pack(anchor=W)

        console_group = ttk.LabelFrame(frame, text="Console", padding=(10, 8, 10, 8))
        console_group.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            console_group,
            text="Keep console window open when launching DOOM-Tools",
            variable=console_var,
        ).pack(anchor=W)

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(12, 0))

        def _save_and_close() -> None:
            self.launch_settings = {
                "devmode": bool(devmode_var.get()),
                "debug": bool(debug_var.get()),
                "dmmode": bool(dmmode_var.get()),
                "keep_console_open": bool(console_var.get()),
            }
            self._save_launch_settings()
            self._refresh_launch_options_label()
            self.status_label.configure(text="Launch settings saved.")
            dialog.destroy()

        ttk.Button(button_row, text="Cancel", command=dialog.destroy, width=12).pack(side=RIGHT)
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
            font=("Segoe UI", 14, "bold"),
            anchor=W,
        ).pack(fill="x")
        ttk.Label(
            header,
            text="This wizard checks for updates, installs resources, and prepares the runtime.",
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
            height=20,
            bg="white",
            fg="#202020",
            relief="sunken",
            borderwidth=1,
            font=("Consolas", 9),
            yscrollcommand=log_scroll.set,
        )
        self.log_box.pack(side=LEFT, fill=BOTH, expand=True)
        log_scroll.configure(command=self.log_box.yview)
        self.log_box.configure(state=DISABLED)

        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        bottom = ttk.Frame(self.root, padding=(16, 8, 16, 12))
        bottom.pack(fill="x")

        self.settings_button = ttk.Button(bottom, text="Settings...", command=self._open_settings_dialog, width=12)
        self.settings_button.pack(side=LEFT)

        self.cancel_button = ttk.Button(bottom, text="Cancel", command=self.root.destroy, width=12)
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

    def log(self, message: str) -> None:
        self.queue.put(("log", message))

    def set_status(self, message: str) -> None:
        self.queue.put(("status", message))

    def set_progress(self, step: int, step_name: str, detail: str) -> None:
        self.queue.put(("progress", (step, step_name, detail)))

    def set_transfer(self, label: str, downloaded: int, total: int, speed: float) -> None:
        self.queue.put(("transfer", (label, downloaded, total, speed)))

    def _worker_thread(self) -> None:
        try:
            exe_path, state = prepare_or_update(
                self.cache_dir,
                self.state_path,
                self.log,
                progress=self.set_progress,
                transfer=self.set_transfer,
            )
            self.runtime_exe = exe_path
            self.set_status(f"Setup complete. Release: {state.get('release_tag', 'unknown')}")
            self.queue.put(("ready", ""))
        except Exception as exc:
            self.set_status(f"Setup failed: {exc}")
            self.log(f"ERROR: {exc}")
            self.queue.put(("error", ""))

    def _append_log(self, message: str) -> None:
        self.log_box.configure(state=NORMAL)
        self.log_box.insert(END, message + "\n")
        self.log_box.see(END)
        self.log_box.configure(state=DISABLED)

    def _poll(self) -> None:
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(str(payload))
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
            elif kind == "ready":
                self.active_progress.stop()
                self.active_progress_is_indeterminate = False
                self.overall_progress.configure(value=max(len(INSTALL_STEPS) - 1, 1))
                self.launch_button.configure(state=NORMAL)
                self.cancel_button.configure(text="Close")
                self.transfer_label.configure(text="Transfer: complete")
            elif kind == "error":
                self.active_progress.stop()
                self.active_progress_is_indeterminate = False
                self.launch_button.configure(state=DISABLED)

        self.root.after(100, self._poll)

    def launch(self) -> None:
        if self.has_launched:
            return
        if not self.runtime_exe or not self.runtime_exe.exists():
            self.set_status("Cannot launch: build is not available")
            return

        runtime_dir = self.runtime_exe.parent
        launch_cmd = [str(self.runtime_exe)]
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

        if os.name == "nt" and not self.launch_settings.get("keep_console_open", False):
            subprocess.Popen(
                launch_cmd,
                cwd=str(runtime_dir),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            subprocess.Popen(launch_cmd, cwd=str(runtime_dir))
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
