import logging
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

os.system("cls" if os.name == "nt" else "clear")  # nosec B605 - hardcoded literal, no shell injection possible


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record):
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


console_formatter = ColoredFormatter("%(asctime)s | %(levelname)s | %(message)s")
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
logging.basicConfig(level=logging.INFO, handlers=[console_handler])

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "main.py"
LAUNCHER_PY = ROOT / "launcher.py"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
ICON_PATH = ROOT / "images_local" / "Bitcrushed_Sanya.png"


def get_version_from_main():
    if not MAIN_PY.exists():
        return "0.0.0"
    with open(MAIN_PY, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    match = re.match(r"version\s*=\s*[\"\']([^\"\']+)[\"\']", first_line)
    if match:
        return match.group(1)
    return "0.0.0"


def run(cmd, **kwargs):
    logging.info("Running: %s", " ".join(cmd))
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)
    logging.info(res.stdout)
    return res.returncode


def build_exe(name="launcher", onefile=True, clean=True):
    if not LAUNCHER_PY.exists():
        logging.error("launcher.py not found at %s", LAUNCHER_PY)
        return False

    BUILD_DIR.mkdir(exist_ok=True)
    pyinstaller_cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm"]
    if clean:
        pyinstaller_cmd.append("--clean")
    if onefile:
        pyinstaller_cmd.append("--onefile")

    if ICON_PATH.exists():
        pyinstaller_cmd += ["--icon", str(ICON_PATH)]
    else:
        logging.warning("Icon file not found at %s; building without explicit icon", ICON_PATH)

    pyinstaller_cmd += ["--name", name, str(LAUNCHER_PY)]
    rc = run(pyinstaller_cmd, cwd=str(ROOT))
    return rc == 0


def find_executable(name="launcher"):
    exe_name = name + (".exe" if os.name == "nt" else "")
    exe_path = DIST_DIR / exe_name
    if exe_path.exists():
        return exe_path
    if DIST_DIR.exists():
        for p in DIST_DIR.iterdir():
            if p.name.startswith(name) and p.is_file():
                return p
    return None


def export_release_exe(exe_path: Path, out_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamp_dir = out_dir / "dist" / timestamp
    timestamp_dir.mkdir(parents=True, exist_ok=True)
    suffix = exe_path.suffix if exe_path.suffix else (".exe" if os.name == "nt" else "")
    out_path = timestamp_dir / f"DOOM-Tools Launcher{suffix}"
    shutil.copy2(exe_path, out_path)
    logging.info("Copied release executable to: %s", out_path)
    return out_path


def send_windows_notification(title: str, message: str):
    if os.name != "nt":
        return
    try:
        from winotify import Notification, audio

        toast = Notification(app_id="DOOM-Tools Build", title=title, msg=message, duration="short")
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except ImportError:
        logging.warning(
            "winotify not installed, cannot send Windows notification. Install it with `pip install winotify`"
        )


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--name", default="launcher", help="Executable name")
    p.add_argument("--onefile", dest="onefile", action="store_true", default=True)
    p.add_argument("--no-clean", dest="clean", action="store_false")
    args = p.parse_args()

    version = get_version_from_main()
    logging.info("Detected version: %s", version)
    logging.info("Starting launcher build")
    try:
        import PyInstaller  # type: ignore
    except Exception:
        logging.error("PyInstaller not available in this environment. Install it with `pip install pyinstaller`")
        return 2

    ok = build_exe(name=args.name, onefile=args.onefile, clean=args.clean)
    if not ok:
        logging.error("PyInstaller build failed")
        return 1

    exe = find_executable(name=args.name)
    if not exe:
        logging.error("Could not find built launcher executable in dist/")
        return 1

    release_exe = export_release_exe(exe, BUILD_DIR)
    logging.info("Launcher build is ready: %s", release_exe)
    send_windows_notification("Launcher Build Complete", f"Launcher v{version} is ready!\n{release_exe.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
