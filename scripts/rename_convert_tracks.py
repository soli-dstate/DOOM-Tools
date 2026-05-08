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
from datetime import datetime
import base64

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
    
    # Build metadata flags from source tags so ffmpeg writes Vorbis comments directly
    try:
        meta_map = extract_vorbis_tag_map(src)
    except Exception:
        meta_map = {}
    metadata_flags: list[str] = []
    for mk, mv in meta_map.items():
        # Use only the first value for ffmpeg metadata and sanitize newlines
        try:
            val = (mv[0] if isinstance(mv, (list, tuple)) else mv) or ''
            val = str(val).replace('\n', ' ').replace('\r', '')
            # ffmpeg will write these as Vorbis comments; use lowercase keys
            metadata_flags.extend(['-metadata', f'{mk}={val}'])
        except Exception:
            continue

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
            '-map', '0:a',  # map audio streams
            '-map', '0:v?',  # map optional video streams (cover art)
            '-map_metadata', '0',  # copy input metadata to output
        ] + metadata_flags + [
            '-ar', str(sample_rate),
            '-c:a', 'libvorbis',
            '-c:v', 'copy',
            str(dst)
        ]
        subprocess.run(cmd, check=True)
        
        file_size = dst.stat().st_size
        if file_size <= MAX_FILE_SIZE:
            if sample_rate != SAMPLE_RATES[0]:
                logging.info(f'  (resampled to {sample_rate} Hz, {file_size / 1024 / 1024:.2f} MB)')
            try:
                # Preserve original file timestamps and permissions where possible
                shutil.copystat(src, dst)
            except Exception:
                pass
            try:
                copy_metadata_with_mutagen(src, dst)
            except Exception:
                pass
            break
        # If we've reached the minimum sample rate and the file is still too large,
        # emit a warning and keep the current output as-is.
        if file_size > MAX_FILE_SIZE and sample_rate == MIN_SAMPLE_RATE:
            logging.warning(f'  (warning: {file_size / 1024 / 1024:.2f} MB at minimum {MIN_SAMPLE_RATE} Hz)')
            break


def copy_metadata_with_mutagen(src: Path, dst: Path) -> None:
    """Attempt to copy metadata and embedded cover art from src to dst using mutagen.

    This is a best-effort operation; failures are logged but do not stop conversion.
    """
    try:
        from mutagen import File as MutagenFile
        from mutagen.oggvorbis import OggVorbis
        from mutagen.flac import Picture
        import mutagen
    except Exception as e:
        logging.debug(f'mutagen not available or failed to import: {e}')
        return

    try:
        src_file = MutagenFile(str(src))
        if src_file is None:
            logging.debug('mutagen could not open source file for metadata copy')
            return

        # Build a normalized Vorbis-comment style tag dictionary (lowercase keys)
        vorbis_tags: dict[str, list[str]] = {}

        # Prefer easy tags when available (already normalized)
        try:
            easy = MutagenFile(str(src), easy=True)
            if easy and getattr(easy, 'tags', None):
                for k, v in easy.tags.items():
                    key = str(k).lower()
                    if isinstance(v, (list, tuple)):
                        vorbis_tags[key] = [str(x) for x in v]
                    else:
                        vorbis_tags[key] = [str(v)]
        except Exception:
            pass

        # If no easy tags found, attempt to map ID3 frames to Vorbis-like keys
        if not vorbis_tags:
            try:
                id3 = getattr(src_file, 'tags', None)
                if id3 is not None:
                    id3_map = {
                        'TIT2': 'title', 'TPE1': 'artist', 'TALB': 'album',
                        'TRCK': 'tracknumber', 'TDRC': 'date', 'TYER': 'date',
                        'TCON': 'genre', 'TIT1': 'title'
                    }
                    # Handle ID3 frames
                    for key in list(id3.keys()):
                        try:
                            frame = id3.get(key)
                            if key.startswith('TXXX'):
                                # TXXX: user-defined text frame with description
                                for f in id3.getall('TXXX'):
                                    desc = (getattr(f, 'desc', '') or '').strip()
                                    tag_key = desc.lower() if desc else 'comment'
                                    txt = getattr(f, 'text', None)
                                    if txt:
                                        vorbis_tags.setdefault(tag_key, []).extend([str(x) for x in txt])
                            elif key.startswith('COMM'):
                                for f in id3.getall('COMM'):
                                    txt = getattr(f, 'text', None)
                                    if txt:
                                        vorbis_tags.setdefault('comment', []).extend([str(x) for x in txt])
                            else:
                                mapped = id3_map.get(key)
                                if mapped:
                                    txt = getattr(frame, 'text', None)
                                    if txt:
                                        vorbis_tags.setdefault(mapped, []).extend([str(x) for x in txt])
                        except Exception:
                            continue
            except Exception:
                pass

        # Extract picture data if present in common containers
        picture_data = None
        picture_mime = None
        try:
            # MP3 ID3 APIC
            if src_file.__class__.__name__.lower().startswith('mp3'):
                id3 = getattr(src_file, 'tags', None)
                if id3 and hasattr(id3, 'getall'):
                    apics = id3.getall('APIC')
                    if apics:
                        picture_data = apics[0].data
                        picture_mime = apics[0].mime
        except Exception:
            pass

        try:
            # FLAC pictures
            if hasattr(src_file, 'pictures') and src_file.pictures:
                pic = src_file.pictures[0]
                picture_data = pic.data
                picture_mime = getattr(pic, 'mime', None)
        except Exception:
            pass

        try:
            # MP4 / M4A cover art
            if src_file.__class__.__name__.lower().startswith('mp4'):
                tags = getattr(src_file, 'tags', None)
                if tags and 'covr' in tags:
                    covr = tags['covr']
                    if covr:
                        cover = covr[0]
                        picture_data = bytes(cover)
                        import imghdr
                        imgtype = imghdr.what(None, picture_data)
                        if imgtype:
                            picture_mime = f'image/{imgtype}'
        except Exception:
            pass

        # Open destination as OggVorbis to write Vorbis comments
        try:
            dst_vorbis = OggVorbis(str(dst))
        except Exception:
            dst_vorbis = MutagenFile(str(dst))
            if dst_vorbis is None:
                logging.debug('mutagen could not open destination file for metadata writing')
                return

        # Ensure tags container exists
        if getattr(dst_vorbis, 'tags', None) is None:
            try:
                dst_vorbis.add_tags()
            except Exception:
                dst_vorbis.tags = {}

        # Build a clean set of Vorbis-comment keys (prefer lowercase keys)
        clean_tags: dict[str, list[str]] = {}
        for k, v in list(vorbis_tags.items()):
            key = str(k).lower()
            vals = [str(x) for x in (v if isinstance(v, (list, tuple)) else [v])]
            clean_tags[key] = vals

        # Remove all existing tags to ensure only normalized Vorbis-comments remain
        try:
            for ek in list(getattr(dst_vorbis, 'tags', {}).keys()):
                try:
                    del dst_vorbis.tags[ek]
                except Exception:
                    pass
        except Exception:
            pass

        # Write cleaned/normalized tags, add both lowercase and uppercase versions for compatibility
        for key, vals in clean_tags.items():
            try:
                dst_vorbis.tags[key] = vals
            except Exception:
                logging.debug(f'Failed to set tag {key} on destination')
            try:
                dst_vorbis.tags[key.upper()] = vals
            except Exception:
                pass

        # If we found a picture, encode as FLAC Picture and store as METADATA_BLOCK_PICTURE
        if picture_data:
            try:
                pic = Picture()
                pic.data = picture_data
                pic.type = 3
                pic.mime = picture_mime or 'image/jpeg'
                pic.desc = ''
                encoded = base64.b64encode(pic.write()).decode('ascii')
                dst_vorbis.tags['METADATA_BLOCK_PICTURE'] = [encoded]
            except Exception as e:
                logging.debug(f'Failed to embed picture into destination: {e}')

        try:
            dst_vorbis.save()
        except Exception as e:
            logging.debug(f'Failed to save destination tags: {e}')

    except Exception as e:
        logging.debug(f'Unexpected error copying metadata: {e}')


def extract_vorbis_tag_map(src: Path) -> dict[str, list[str]]:
    """Extract a normalized Vorbis-comment style tag map from src (best-effort)."""
    try:
        from mutagen import File as MutagenFile
    except Exception:
        return {}

    vorbis_tags: dict[str, list[str]] = {}
    try:
        src_file = MutagenFile(str(src))
        if src_file is None:
            return {}

        # Try easy tags first
        try:
            easy = MutagenFile(str(src), easy=True)
            if easy and getattr(easy, 'tags', None):
                for k, v in easy.tags.items():
                    key = str(k).lower()
                    if isinstance(v, (list, tuple)):
                        vorbis_tags[key] = [str(x) for x in v]
                    else:
                        vorbis_tags[key] = [str(v)]
        except Exception:
            pass

        # If still empty, map ID3 frames
        if not vorbis_tags:
            try:
                id3 = getattr(src_file, 'tags', None)
                if id3 is not None:
                    id3_map = {
                        'TIT2': 'title', 'TPE1': 'artist', 'TALB': 'album',
                        'TRCK': 'tracknumber', 'TDRC': 'date', 'TYER': 'date',
                        'TCON': 'genre', 'TIT1': 'title'
                    }
                    for key in list(id3.keys()):
                        try:
                            frame = id3.get(key)
                            if key.startswith('TXXX'):
                                for f in id3.getall('TXXX'):
                                    desc = (getattr(f, 'desc', '') or '').strip()
                                    tag_key = desc.lower() if desc else 'comment'
                                    txt = getattr(f, 'text', None)
                                    if txt:
                                        vorbis_tags.setdefault(tag_key, []).extend([str(x) for x in txt])
                            elif key.startswith('COMM'):
                                for f in id3.getall('COMM'):
                                    txt = getattr(f, 'text', None)
                                    if txt:
                                        vorbis_tags.setdefault('comment', []).extend([str(x) for x in txt])
                            else:
                                mapped = id3_map.get(key)
                                if mapped:
                                    txt = getattr(frame, 'text', None)
                                    if txt:
                                        vorbis_tags.setdefault(mapped, []).extend([str(x) for x in txt])
                        except Exception:
                            continue
            except Exception:
                pass

    except Exception:
        return {}

    return vorbis_tags
        


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
    # Create a backup folder to store all originals before conversion
    base_backup = folder / 'pre_conversion'
    if base_backup.exists():
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = folder / f'pre_conversion_{ts}'
    else:
        backup_dir = base_backup
    backup_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f'Original files will be moved to: {backup_dir}')

    converted_count = 0
    error_count = 0
    for i, src in enumerate(files):
        target = folder / f'track{i}.ogg'
        try:
            # Move the original into the backup folder first
            backup_src = backup_dir / src.name
            try:
                # If src and backup_src are the same path, skip move
                if src.resolve() != backup_src.resolve():
                    shutil.move(str(src), str(backup_src))
            except Exception as mov_exc:
                logging.warning(f'Could not move {src.name} to backup folder: {mov_exc}')
                backup_src = src

            # If already an ogg file and under size limit, copy to target (preserve original in backup)
            if backup_src.suffix.lower() == '.ogg' and backup_src.stat().st_size <= MAX_FILE_SIZE:
                if target.exists():
                    try:
                        target.unlink()
                    except Exception:
                        pass
                shutil.copy2(str(backup_src), str(target))
                try:
                    copy_metadata_with_mutagen(backup_src, target)
                except Exception:
                    pass
            else:
                # Convert (and resample if needed) for non-ogg or oversized ogg files
                convert_to_ogg(backup_src, target, ffmpeg)

            logging.info(f'{src.name} -> {target.name} (original moved to {backup_dir.name})')
            converted_count += 1
        except subprocess.CalledProcessError:
            logging.error(f'Error converting {src.name}. Skipping.')
            # Remove potentially partial target file
            try:
                if target.exists():
                    target.unlink()
            except Exception:
                pass
            error_count += 1
        except Exception as exc:
            logging.error(f'Unexpected error for {src.name}: {exc}')
            try:
                if target.exists():
                    target.unlink()
            except Exception:
                pass
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
