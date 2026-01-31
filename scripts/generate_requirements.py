"""
Generate/update `requirements.txt` for the project.

Provides a single function `generate_requirements(ide_mode: bool)` which mirrors the
behavior previously embedded in `main.py`.
"""
from __future__ import annotations
import os
import sys
import subprocess
import logging


def _pip_freeze_output() -> str:
    try:
        out = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True, stderr=subprocess.DEVNULL)
        return out
    except Exception:
        # Fallback to run (capture_output)
        try:
            result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True)
            return result.stdout or ''
        except Exception:
            return ''


def generate_requirements(ide_mode: bool = False) -> None:
    """Create or update requirements.txt.

    If `ide_mode` is True, write the raw `pip freeze` output immediately.
    Then merge current environment packages into `requirements.txt` as a sorted, unique list.
    """
    try:
        if ide_mode:
            out = _pip_freeze_output()
            if out:
                with open('requirements.txt', 'w', encoding='utf-8') as _rq:
                    _rq.write(out)
                logging.info('Updated requirements.txt from pip freeze(IDE mode)')
    except Exception:
        logging.exception('Failed to refresh requirements.txt in IDE mode')

    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'freeze'], capture_output=True, text=True)
        current_packages = set(result.stdout.strip().split('\n')) if result.stdout else set()

        existing_packages = set()
        try:
            with open('requirements.txt', 'r') as f:
                existing_packages = set(line.strip() for line in f if line.strip())
        except FileNotFoundError:
            pass

        all_packages = existing_packages | current_packages
        all_packages.discard('')
        with open('requirements.txt', 'w') as f:
            for package in sorted(all_packages):
                f.write(f'{package}\n')
        logging.info(f"Updated requirements.txt with {len(all_packages)} packages")
    except Exception as e:
        logging.warning(f"Failed to update requirements.txt: {e}")


if __name__ == '__main__':
    generate_requirements(ide_mode=False)
