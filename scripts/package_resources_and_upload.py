import argparse
import os
import re
import secrets
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests


CATBOX_API_URL = "https://catbox.moe/user/api.php"
# Catbox caps uploads at 200 MB; split parts stay comfortably under that.
CATBOX_MAX_PART_BYTES = 190 * 1000 * 1000
ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "main.py"
BUILD_DIR = ROOT / "build" / "resources"
RESOURCE_DIRS = ("sounds", "images")


def _log(message: str) -> None:
    print(f"[resource-pack] {message}")


def create_resource_zip() -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = BUILD_DIR / f"DOOM-Tools-resources-{timestamp}.zip"

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for folder_name in RESOURCE_DIRS:
            src_dir = ROOT / folder_name
            if not src_dir.exists():
                _log(f"Skipping missing folder: {src_dir}")
                continue
            if not src_dir.is_dir():
                _log(f"Skipping non-directory path: {src_dir}")
                continue

            for file_path in src_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                arcname = file_path.relative_to(ROOT)
                zf.write(file_path, arcname=str(arcname))

    _log(f"Created zip: {zip_path}")
    return zip_path


def split_file(path: Path, chunk_size: int) -> list[Path]:
    """Split a file into ordered byte-parts named <name>.001, .002, ... .

    Concatenating the parts in order reproduces the original file exactly.
    """
    parts: list[Path] = []
    block = 1024 * 1024
    with path.open("rb") as src:
        index = 1
        while True:
            written = 0
            part_path = path.parent / f"{path.name}.{index:03d}"
            with part_path.open("wb") as dst:
                while written < chunk_size:
                    buf = src.read(min(block, chunk_size - written))
                    if not buf:
                        break
                    dst.write(buf)
                    written += len(buf)
            if written == 0:
                part_path.unlink(missing_ok=True)
                break
            parts.append(part_path)
            _log(f"Created part {index}: {part_path.name} ({written / 1048576:.1f} MB)")
            index += 1
    return parts


def _make_progress_printer(total: int, prefix: str, width: int = 30):
    start = time.monotonic()
    last = [start]

    def printer(done: int) -> None:
        now = time.monotonic()
        # Throttle to ~10 fps, but always render the final 100% frame.
        if done < total and now - last[0] < 0.1:
            return
        last[0] = now
        elapsed = now - start
        speed = (done / elapsed / 1048576) if elapsed > 0 else 0.0
        frac = (done / total) if total else 1.0
        filled = int(width * frac)
        bar = "█" * filled + "-" * (width - filled)
        sys.stdout.write(
            f"\r{prefix} [{bar}] {frac * 100:5.1f}%  "
            f"{done / 1048576:7.1f}/{total / 1048576:.1f} MB  {speed:6.2f} MB/s"
        )
        sys.stdout.flush()

    return printer


class _MultipartUploadBody:
    """Streaming multipart/form-data body so requests sends parts with progress.

    Defining __iter__ makes requests treat it as a stream, and __len__ lets it set
    Content-Length (no chunked encoding) while the file is read in blocks rather
    than buffered whole.
    """

    def __init__(self, fields, file_field, file_path, filename, content_type,
                 on_progress, block=1024 * 1024):
        self.boundary = "----DOOMToolsBoundary" + secrets.token_hex(16)
        pre = b""
        for name, value in fields.items():
            pre += f"--{self.boundary}\r\n".encode()
            pre += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            pre += f"{value}\r\n".encode()
        pre += f"--{self.boundary}\r\n".encode()
        pre += (f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{filename}"\r\n').encode()
        pre += f"Content-Type: {content_type}\r\n\r\n".encode()
        self._pre = pre
        self._post = f"\r\n--{self.boundary}--\r\n".encode()
        self._file_path = file_path
        self._file_size = file_path.stat().st_size
        self._on_progress = on_progress
        self._block = block

    def __len__(self):
        return len(self._pre) + self._file_size + len(self._post)

    def __iter__(self):
        yield self._pre
        sent = 0
        with self._file_path.open("rb") as handle:
            while True:
                chunk = handle.read(self._block)
                if not chunk:
                    break
                sent += len(chunk)
                self._on_progress(sent)
                yield chunk
        yield self._post


def upload_part_to_catbox(part_path: Path, userhash: str | None, timeout: int,
                          prefix: str) -> str:
    fields = {"reqtype": "fileupload"}
    if userhash:
        fields["userhash"] = userhash

    total = part_path.stat().st_size
    body = _MultipartUploadBody(
        fields, "fileToUpload", part_path, part_path.name,
        "application/octet-stream", _make_progress_printer(total, prefix),
    )
    try:
        response = requests.post(
            CATBOX_API_URL,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={body.boundary}"},
            timeout=timeout,
        )
    finally:
        sys.stdout.write("\n")
        sys.stdout.flush()

    response.raise_for_status()
    text = response.text.strip()
    if not text.lower().startswith("http"):
        raise RuntimeError(f"Unexpected Catbox response: {text}")
    return text


def upload_parts(parts: list[Path], userhash: str | None, timeout: int) -> list[str]:
    links: list[str] = []
    total = len(parts)

    # Ensure the bar's block glyph survives a non-UTF-8 console / redirect.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    for index, part_path in enumerate(parts, start=1):
        prefix = f"[resource-pack] part {index}/{total}"
        link = upload_part_to_catbox(part_path, userhash, timeout, prefix)
        _log(f"part {index}/{total} -> {link}")
        links.append(link)
    return links


def update_main_resource_links(links: list[str]) -> None:
    if not MAIN_PY.exists():
        raise FileNotFoundError(f"Could not find main.py at: {MAIN_PY}")

    text = MAIN_PY.read_text(encoding="utf-8")
    pattern = re.compile(r"current_resource_links\s*=\s*\[.*?\]", re.DOTALL)
    body = "\n".join(f'    "{u}",' for u in links)
    replacement = "current_resource_links = [\n" + (body + "\n" if body else "") + "]"

    if not pattern.search(text):
        raise RuntimeError("Could not locate current_resource_links assignment in main.py")
    updated = pattern.sub(lambda _m: replacement, text, count=1)

    MAIN_PY.write_text(updated, encoding="utf-8")
    _log(f"Updated current_resource_links in main.py ({len(links)} part(s))")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package sounds/images into a zip, split it, upload the parts to "
        "Catbox, and update the current_resource_links list in main.py."
    )
    parser.add_argument(
        "--userhash",
        default=os.getenv("CATBOX_USERHASH", "").strip(),
        help="Catbox userhash. Defaults to CATBOX_USERHASH env var. Optional for anonymous uploads.",
    )
    parser.add_argument(
        "--part-size",
        type=int,
        default=CATBOX_MAX_PART_BYTES,
        help="Max bytes per part (default keeps each part under Catbox's 200 MB cap).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="HTTP timeout in seconds for each part upload.",
    )
    parser.add_argument(
        "--no-update-main",
        action="store_true",
        help="Upload parts but do not update current_resource_links in main.py.",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the local zip and parts after successful upload.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    userhash = args.userhash or None

    zip_path = create_resource_zip()
    parts: list[Path] = []
    try:
        parts = split_file(zip_path, args.part_size)
        if not parts:
            raise RuntimeError("Resource zip produced no parts (empty zip?).")
        links = upload_parts(parts, userhash=userhash, timeout=args.timeout)
        if not args.no_update_main:
            update_main_resource_links(links)
        _log("Done")
        for link in links:
            print(link)
        return 0
    finally:
        if not args.keep_zip:
            for part_path in parts:
                try:
                    part_path.unlink(missing_ok=True)
                except Exception:
                    _log(f"Warning: failed to remove part: {part_path}")
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    _log(f"Warning: failed to remove temporary zip: {zip_path}")


if __name__ == "__main__":
    raise SystemExit(main())
