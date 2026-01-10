#!/usr/bin/env python3
"""
Open a Windows folder picker, rename audio files to track0..trackN and convert to .ogg

Requirements:
- `ffmpeg` must be installed and available on PATH.

Usage:
Run this script and choose a folder when prompted.
python scripts/rename_convert_tracks.py

The script will replace original files with `track{n}.ogg` files.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tkinter import Tk, filedialog
import sys


EXTS = {'.wav', '.mp3', '.flac', '.m4a', '.aac', '.wma', '.ogg', '.opus', '.aiff', '.aif'}


def choose_folder() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(title='Select folder containing audio files')
    root.destroy()
    if not folder:
        return None
    return Path(folder)


def check_ffmpeg() -> bool:
    return shutil.which('ffmpeg') is not None


def gather_audio_files(folder: Path) -> list[Path]:
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTS]
    return sorted(files, key=lambda p: p.name.lower())


def convert_to_ogg(src: Path, dst: Path) -> None:
    # Overwrite if exists
    if dst.exists():
        try:
            dst.unlink()
        except Exception:
            pass
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(src), str(dst)]
    subprocess.run(cmd, check=True)


def main() -> int:
    folder = choose_folder()
    if folder is None:
        print('No folder selected. Exiting.')
        return 1

    files = gather_audio_files(folder)
    if not files:
        print('No audio files found in the selected folder.')
        return 0

    # Only require ffmpeg if there are files that are not already .ogg
    needs_ffmpeg = any(p.suffix.lower() != '.ogg' for p in files)
    if needs_ffmpeg and not check_ffmpeg():
        print('ffmpeg not found on PATH but required to convert non-ogg files. Please install ffmpeg and try again.')
        return 2

    print(f'Found {len(files)} audio file(s). Converting and renaming to track0..')
    for i, src in enumerate(files):
        target = folder / f'track{i}.ogg'
        try:
            # If already an ogg file, try to rename first; otherwise convert and remove source
            if src.suffix.lower() == '.ogg':
                # Remove target if exists, then rename
                if target.exists():
                    target.unlink()
                src.rename(target)
            else:
                convert_to_ogg(src, target)
                try:
                    src.unlink()
                except Exception:
                    pass
            print(f'{src.name} -> {target.name}')
        except subprocess.CalledProcessError:
            print(f'Error converting {src.name}. Skipping.')
        except Exception as exc:
            print(f'Unexpected error for {src.name}: {exc}')

    print('Done.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
