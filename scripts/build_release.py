import os
import sys
import subprocess
import shutil
import zipfile
import tempfile
import re
from datetime import datetime
import logging
from pathlib import Path
os.system('cls'if os.name =='nt'else 'clear')  # nosec B605 - hardcoded literal, no shell injection possible
class ColoredFormatter(logging.Formatter):
    COLORS = {
    'DEBUG':'\033[36m',
    'INFO':'\033[32m',
    'WARNING':'\033[33m',
    'ERROR':'\033[31m',
    'CRITICAL':'\033[35m',
    }
    RESET = '\033[0m'
    def format(self, record):
        orig_level = record.levelname
        color = self.COLORS.get(orig_level, '')
        formatted = super().format(record)
        if orig_level in('WARNING', 'ERROR', 'CRITICAL', 'DEBUG')and color:
            return f"{color}{formatted}{self.RESET}"
        if orig_level =='INFO'and color:
            try:
                return formatted.replace(orig_level, f"{color}{orig_level}{self.RESET}", 1)
            except Exception:
                return formatted
        return formatted
class StripAnsiFormatter(logging.Formatter):
    ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
    def format(self, record):
        formatted = super().format(record)
        return self.ANSI_RE.sub('', formatted)
console_formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
logging.basicConfig(
level = logging.INFO,
handlers =[console_handler]
)
ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / 'main.py'
FOUNDATION_PY = ROOT / 'app' / 'foundation.py'   # `version` lives here post-refactor
SOUNDS_DIR = ROOT / 'sounds'
TABLES_DIR = ROOT / 'tables'
BUILD_DIR = ROOT / 'build'
DIST_DIR = ROOT / 'dist'
FONTS_DIR = ROOT / 'fonts'
IMAGES_DIR = ROOT / 'images'
def get_version_from_main():
    # `version` moved out of main.py into app/foundation.py during the package
    # refactor; scan that file for it, falling back to main.py for older trees.
    for src in (FOUNDATION_PY, MAIN_PY):
        if not src.exists():
            continue
        with open(src, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'version\s*=\s*["\']([^"\']+)["\']', line.strip())
                if match:
                    return match.group(1)
    return '0.0.0'
def run(cmd, **kwargs):
    logging.info('Running: %s', ' '.join(cmd))
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)
    logging.info(res.stdout)
    return res.returncode
def build_exe(name='DOOM-Tools', onefile=True, clean=True):
    if not MAIN_PY.exists():
        logging.error('main.py not found at %s', MAIN_PY)
        return False
    BUILD_DIR.mkdir(exist_ok=True)
    pyinstaller_cmd = [sys.executable, '-m', 'PyInstaller', '--noconfirm']
    if clean:
        pyinstaller_cmd.append('--clean')
    if onefile:
        pyinstaller_cmd.append('--onefile')

    # Include the images directory as bundled data so images are available
    # inside the frozen application (_MEIPASS). Use os.pathsep so this works
    # cross-platform (PyInstaller expects ';' on Windows and ':' on POSIX).
    if IMAGES_DIR.exists():
        add_data_str = f"{str(IMAGES_DIR)}{os.pathsep}images"
        logging.info('Adding PyInstaller data: %s', add_data_str)
        pyinstaller_cmd += ['--add-data', add_data_str]

    # Cloud-saves modules are imported lazily inside functions; ensure PyInstaller
    # bundles them so prebuilt (no-Python) users never hit a frozen-only ImportError.
    for mod in ('http.server', 'webbrowser', 'urllib.parse'):
        pyinstaller_cmd += ['--hidden-import', mod]

    # The app is now an `app/` package whose mixin submodules are imported by
    # app.core. They are statically discoverable, but --collect-submodules makes
    # the bundling robust to any future lazy/dynamic imports of app.* modules.
    pyinstaller_cmd += ['--collect-submodules', 'app']

    # Bundle Google Drive OAuth credentials into the build WITHOUT committing them
    # to git. Provide a git-ignored cloud_credentials.json in the repo root (or set
    # CLOUD_CREDENTIALS_FILE) and it is embedded at the bundle root for main.py to
    # read from sys._MEIPASS. Absent -> cloud saves stay disabled in the build.
    creds_file = Path(os.getenv('CLOUD_CREDENTIALS_FILE', str(ROOT / 'cloud_credentials.json')))
    if creds_file.exists():
        add_creds_str = f"{str(creds_file)}{os.pathsep}."
        logging.info('Bundling cloud credentials (not logged): %s', creds_file.name)
        pyinstaller_cmd += ['--add-data', add_creds_str]
    else:
        logging.info('No cloud_credentials.json found; cloud saves will be disabled in this build')

    pyinstaller_cmd += ['--name', name, str(MAIN_PY)]
    rc = run(pyinstaller_cmd, cwd=str(ROOT))
    return rc == 0
def find_executable(name='DOOM-Tools'):
    exe_name = name + ('.exe' if os.name == 'nt' else '')
    exe_path = DIST_DIR / exe_name
    if exe_path.exists():
        return exe_path
    if DIST_DIR.exists():
        for p in DIST_DIR.iterdir():
            if p.name.startswith(name) and p.is_file():
                return p
    return None
def make_release_zip(exe_path: Path, out_dir: Path, version: str = '0.0.0', include_sounds=True):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = out_dir / f'DOOM-Tools-v{version}-{timestamp}.zip'
    tmpdir = Path(tempfile.mkdtemp(prefix='doom_release_'))
    try:
        shutil.copy2(exe_path, tmpdir / exe_path.name)
        devmode = ROOT / 'devmode.bat'
        runnogil = ROOT / 'runwithoutgil.bat'
        if devmode.exists():
            shutil.copy2(devmode, tmpdir / devmode.name)
        if runnogil.exists():
            shutil.copy2(runnogil, tmpdir / runnogil.name)
        if include_sounds and SOUNDS_DIR.exists():
            dest_sounds = tmpdir / 'sounds'
            shutil.copytree(SOUNDS_DIR, dest_sounds)
        if TABLES_DIR.exists():
            dest_tables = tmpdir / 'tables'
            # Copy only .sldtbl files from the tables directory, preserving relative paths
            for p in TABLES_DIR.rglob('*.sldtbl'):
                rel = p.relative_to(TABLES_DIR)
                dest_file = dest_tables / rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest_file)
        if FONTS_DIR.exists():
            dest_fonts = tmpdir / 'fonts'
            shutil.copytree(FONTS_DIR, dest_fonts)
        with zipfile.ZipFile(zip_name, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(tmpdir):
                for f in files:
                    full = Path(root) / f
                    rel = full.relative_to(tmpdir)
                    zf.write(full, arcname=str(rel))
        logging.info('Created release zip: %s', zip_name)
        return zip_name
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            logging.exception("Suppressed exception")
def send_windows_notification(title: str, message: str):
    if os.name != 'nt':
        return
    try:
        from winotify import Notification, audio
        toast = Notification(
            app_id="DOOM-Tools Build",
            title=title,
            msg=message,
            duration="short"
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except ImportError:
        logging.warning('winotify not installed, cannot send Windows notification. Install it with `pip install winotify`')
def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--name', default='DOOM-Tools', help='Executable name')
    p.add_argument('--onefile', dest='onefile', action='store_true', default=True)
    p.add_argument('--no-clean', dest='clean', action='store_false')
    p.add_argument('--no-sounds', dest='sounds', action='store_false', default=True)
    args = p.parse_args()
    version = get_version_from_main()
    logging.info('Detected version: %s', version)
    logging.info('Starting release build')
    try:
        import PyInstaller  # type: ignore
    except Exception:
        logging.error('PyInstaller not available in this environment. Install it with `pip install pyinstaller`')
        return 2
    ok = build_exe(name=args.name, onefile=args.onefile, clean=args.clean)
    if not ok:
        logging.error('PyInstaller build failed')
        return 1
    exe = find_executable(name=args.name)
    if not exe:
        logging.error('Could not find built executable in dist/')
        return 1
    zip_path = make_release_zip(exe, BUILD_DIR, version=version, include_sounds=args.sounds)
    logging.info('Release is ready: %s', zip_path)
    send_windows_notification("DOOM-Tools Build Complete", f"Release v{version} is ready!\n{zip_path.name}")
    return 0
if __name__ == '__main__':
    raise SystemExit(main())