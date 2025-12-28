"""
Build release script for DOOM-Tools
- Runs PyInstaller to build a one-file executable from `main.py`.
- Packages the generated executable together with the `sounds/` folder into a timestamped zip
  placed in `./build/`.

Usage:
  python scripts/build_release.py [--name NAME] [--onefile] [--no-clean]

Notes:
- Requires `pyinstaller` installed in the Python environment used to run this script.
- Runs on Windows (produces .exe); will also work on other OSes but executable extension differs.
"""

import os
import sys
import subprocess
import shutil
import zipfile
import tempfile
from datetime import datetime
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / 'main.py'
SOUNDS_DIR = ROOT / 'sounds'
BUILD_DIR = ROOT / 'build'
DIST_DIR = ROOT / 'dist'


def run(cmd, **kwargs):
    logging.info('Running: %s', ' '.join(cmd))
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs)
    logging.info(res.stdout)
    return res.returncode


def build_exe(name='DOOM-Tools', onefile=True, clean=True):
    if not MAIN_PY.exists():
        logging.error('main.py not found at %s', MAIN_PY)
        return False

    # Ensure build directories
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
    # Windows: .exe
    exe_name = name + ('.exe' if os.name == 'nt' else '')
    exe_path = DIST_DIR / exe_name
    if exe_path.exists():
        return exe_path
    # fallback: find any file in dist that startswith name
    if DIST_DIR.exists():
        for p in DIST_DIR.iterdir():
            if p.name.startswith(name) and p.is_file():
                return p
    return None


def make_release_zip(exe_path: Path, out_dir: Path, include_sounds=True):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_name = out_dir / f'{exe_path.stem}_{timestamp}.zip'

    tmpdir = Path(tempfile.mkdtemp(prefix='doom_release_'))
    try:
        # copy exe
        shutil.copy2(exe_path, tmpdir / exe_path.name)
        # copy sounds dir
        if include_sounds and SOUNDS_DIR.exists():
            dest_sounds = tmpdir / 'sounds'
            shutil.copytree(SOUNDS_DIR, dest_sounds)

        # create zip
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


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--name', default='DOOM-Tools', help='Executable name')
    p.add_argument('--onefile', dest='onefile', action='store_true', default=True)
    p.add_argument('--no-clean', dest='clean', action='store_false')
    p.add_argument('--no-sounds', dest='sounds', action='store_false', default=True)
    args = p.parse_args()

    logging.info('Starting release build')

    # Check PyInstaller availability
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

    zip_path = make_release_zip(exe, BUILD_DIR, include_sounds=args.sounds)
    logging.info('Release is ready: %s', zip_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
