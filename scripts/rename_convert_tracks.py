#!/usr/bin/env python3
"""
Open a Windows folder picker, rename audio files to track0..trackN and convert to .ogg

Requirements:
- Internet connection (for automatic ffmpeg download on first run)

Usage:
Run this script and choose a folder when prompted.
python scripts/rename_convert_tracks.py

The script will replace original files with `track{n}.ogg` files.
Files are automatically resampled to stay under 4 MB if possible (minimum 12 kHz).
FFmpeg is automatically downloaded and stored locally on first run.
"""
from __future__ import annotations

import shutil
import subprocess
import zipfile
import io
import os
import platform
import logging
from pathlib import Path
from tkinter import Tk, filedialog
from urllib.request import urlopen, Request
import sys

os.system('cls' if os.name == 'nt' else 'clear')

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
    }
    RESET = '\033[0m'

    def format(self, record):
        orig_level = record.levelname
        color = self.COLORS.get(orig_level, '')
        formatted = super().format(record)
        if orig_level in ('WARNING', 'ERROR', 'CRITICAL', 'DEBUG') and color:
            return f"{color}{formatted}{self.RESET}"
        if orig_level == 'INFO' and color:
            try:
                return formatted.replace(orig_level, f"{color}{orig_level}{self.RESET}", 1)
            except Exception:
                return formatted
        return formatted

console_formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(message)s')
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler]
)


def send_windows_notification(title: str, message: str):
    if os.name != 'nt':
        return
    try:
        from winotify import Notification, audio
        toast = Notification(
            app_id="DOOM-Tools Audio Converter",
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


EXTS = {'.wav', '.mp3', '.flac', '.m4a', '.aac', '.wma', '.ogg', '.opus', '.aiff', '.aif', '.ogv', '.webm', '.mkv', '.mp4'}
MAX_FILE_SIZE = 4 * 1024 * 1024  # 4 MB
MIN_SAMPLE_RATE = 12000
SAMPLE_RATES = [48000, 44100, 32000, 24000, 22050, 16000, 12000]  # Descending order

# Local ffmpeg storage
SCRIPT_DIR = Path(__file__).parent
TOOLS_DIR = SCRIPT_DIR / 'tools'
FFMPEG_DIR = TOOLS_DIR / 'ffmpeg'

# FFmpeg release from BtbN GitHub builds (essentials build, smaller download)
FFMPEG_RELEASE_URL = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'


def get_ffmpeg_path() -> Path | None:
    """Get path to ffmpeg executable, downloading if necessary."""
    # Check local installation first
    local_ffmpeg = FFMPEG_DIR / 'bin' / 'ffmpeg.exe'
    if local_ffmpeg.exists():
        return local_ffmpeg
    
    # Check if ffmpeg is on system PATH
    system_ffmpeg = shutil.which('ffmpeg')
    if system_ffmpeg:
        return Path(system_ffmpeg)
    
    # Need to download
    return None


def download_ffmpeg() -> Path | None:
    """Download and extract ffmpeg from GitHub."""
    if platform.system() != 'Windows':
        logging.warning('Automatic ffmpeg download only supported on Windows.')
        logging.warning('Please install ffmpeg manually and ensure it is on PATH.')
        return None
    
    logging.info('FFmpeg not found. Downloading from GitHub...')
    
    try:
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Download the zip file
        request = Request(FFMPEG_RELEASE_URL, headers={'User-Agent': 'Mozilla/5.0'})
        logging.info(f'Downloading from {FFMPEG_RELEASE_URL}...')
        
        with urlopen(request, timeout=120) as response:
            total_size = response.headers.get('Content-Length')
            if total_size:
                total_size = int(total_size)
                logging.info(f'Download size: {total_size / 1024 / 1024:.1f} MB')
            
            data = response.read()
        
        logging.info('Extracting ffmpeg...')
        
        # Extract from zip
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # Find the root folder name in the zip (varies by release)
            root_folders = set()
            for name in zf.namelist():
                parts = name.split('/')
                if parts[0]:
                    root_folders.add(parts[0])
            
            if len(root_folders) != 1:
                logging.error(f'Unexpected zip structure: {root_folders}')
                return None
            
            zip_root = root_folders.pop()
            
            # Extract all files
            zf.extractall(TOOLS_DIR)
            
            # Rename extracted folder to 'ffmpeg'
            extracted_path = TOOLS_DIR / zip_root
            if FFMPEG_DIR.exists():
                shutil.rmtree(FFMPEG_DIR)
            extracted_path.rename(FFMPEG_DIR)
        
        ffmpeg_exe = FFMPEG_DIR / 'bin' / 'ffmpeg.exe'
        if ffmpeg_exe.exists():
            logging.info(f'FFmpeg installed to: {ffmpeg_exe}')
            return ffmpeg_exe
        else:
            logging.error('FFmpeg executable not found after extraction.')
            return None
            
    except Exception as e:
        logging.error(f'Failed to download ffmpeg: {e}')
        return None


def ensure_ffmpeg() -> Path | None:
    """Ensure ffmpeg is available, downloading if necessary."""
    ffmpeg = get_ffmpeg_path()
    if ffmpeg:
        return ffmpeg
    return download_ffmpeg()


def choose_folder() -> Path | None:
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(title='Select folder containing audio files')
    root.destroy()
    if not folder:
        return None
    return Path(folder)


def gather_audio_files(folder: Path) -> list[Path]:
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXTS]
    return sorted(files, key=lambda p: p.name.lower())


def convert_to_ogg(src: Path, dst: Path, ffmpeg: Path) -> None:
    """Convert audio file to ogg, reducing sample rate if needed to stay under 4 MB."""
    # Overwrite if exists
    if dst.exists():
        try:
            dst.unlink()
        except Exception:
            pass
    
    # Try each sample rate from highest to lowest until file is under MAX_FILE_SIZE
    for sample_rate in SAMPLE_RATES:
        if dst.exists():
            try:
                dst.unlink()
            except Exception:
                pass
        
        cmd = [
            str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-y',
            '-i', str(src),
            '-vn',  # Strip any video streams (audio only)
            '-ar', str(sample_rate),
            '-c:a', 'libvorbis',
            str(dst)
        ]
        subprocess.run(cmd, check=True)
        
        file_size = dst.stat().st_size
        if file_size <= MAX_FILE_SIZE:
            if sample_rate != SAMPLE_RATES[0]:
                logging.info(f'  (resampled to {sample_rate} Hz, {file_size / 1024 / 1024:.2f} MB)')
            break
        
        if sample_rate == MIN_SAMPLE_RATE:
            # Already at minimum sample rate, keep the file as is
            logging.warning(f'  (warning: {file_size / 1024 / 1024:.2f} MB at minimum {MIN_SAMPLE_RATE} Hz)')
            break


def main() -> int:
    folder = choose_folder()
    if folder is None:
        logging.warning('No folder selected. Exiting.')
        return 1

    files = gather_audio_files(folder)
    if not files:
        logging.warning('No audio files found in the selected folder.')
        return 0

    # Ensure ffmpeg is available (download if needed)
    ffmpeg = ensure_ffmpeg()
    if not ffmpeg:
        logging.error('FFmpeg is required but could not be found or downloaded.')
        return 2

    logging.info(f'Found {len(files)} audio file(s). Converting and renaming to track0..')
    converted_count = 0
    error_count = 0
    for i, src in enumerate(files):
        target = folder / f'track{i}.ogg'
        try:
            # If already an ogg file and under size limit, just rename
            if src.suffix.lower() == '.ogg' and src.stat().st_size <= MAX_FILE_SIZE:
                # Remove target if exists, then rename
                if target.exists():
                    target.unlink()
                src.rename(target)
            else:
                # Convert (and resample if needed) for non-ogg or oversized ogg files
                convert_to_ogg(src, target, ffmpeg)
            logging.info(f'{src.name} -> {target.name}')
            converted_count += 1
        except subprocess.CalledProcessError:
            logging.error(f'Error converting {src.name}. Skipping.')
            error_count += 1
        except Exception as exc:
            logging.error(f'Unexpected error for {src.name}: {exc}')
            error_count += 1

    logging.info('Done.')
    
    # Send Windows notification
    if error_count == 0:
        send_windows_notification(
            "Audio Conversion Complete",
            f"Successfully converted {converted_count} file(s) to OGG format."
        )
    else:
        send_windows_notification(
            "Audio Conversion Complete",
            f"Converted {converted_count} file(s), {error_count} error(s)."
        )
    
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
