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
os.system('cls'if os.name =='nt'else 'clear')
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
SOUNDS_DIR = ROOT / 'sounds'
TABLES_DIR = ROOT / 'tables'
BUILD_DIR = ROOT / 'build'
DIST_DIR = ROOT / 'dist'
FONTS_DIR = ROOT / 'fonts'
def get_version_from_main():
    if not MAIN_PY.exists():
        return '0.0.0'
    with open(MAIN_PY, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    match = re.match(r'version\s*=\s*["\']([^"\']+)["\']', first_line)
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
            shutil.copytree(TABLES_DIR, dest_tables)
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
            pass
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
        try:
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $template = @"
            <toast>
                <visual>
                    <binding template="ToastText02">
                        <text id="1">{title}</text>
                        <text id="2">{message}</text>
                    </binding>
                </visual>
                <audio src="ms-winsoundevent:Notification.Default"/>
            </toast>
"@
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("DOOM-Tools").Show($toast)
            '''
            subprocess.run(['powershell', '-Command', ps_script], capture_output=True)
        except Exception:
            pass
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