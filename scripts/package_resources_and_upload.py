import argparse
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

import requests


PIXELDRAIN_UPLOAD_URL = "https://pixeldrain.com/api/file"
PIXELDRAIN_FILE_URL = "https://pixeldrain.com/api/file/{id}"
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


def upload_to_pixeldrain(zip_path: Path, api_key: str | None, timeout: int) -> str:
    # Pixeldrain accepts the raw file via PUT /api/file/{name}. An API key is
    # optional; when supplied it is sent as HTTP Basic auth (empty username,
    # key as password) so the file is tied to the account and not purged for
    # anonymous inactivity.
    auth = ("", api_key) if api_key else None

    with zip_path.open("rb") as handle:
        response = requests.put(
            f"{PIXELDRAIN_UPLOAD_URL}/{zip_path.name}",
            data=handle,
            auth=auth,
            headers={"Content-Type": "application/zip"},
            timeout=timeout,
        )
    response.raise_for_status()

    payload = response.json()
    file_id = payload.get("id")
    if not file_id:
        raise RuntimeError(f"Unexpected Pixeldrain response: {response.text}")

    link = PIXELDRAIN_FILE_URL.format(id=file_id)
    _log(f"Uploaded to Pixeldrain: {link}")
    return link


def update_main_resource_link(new_link: str) -> None:
    if not MAIN_PY.exists():
        raise FileNotFoundError(f"Could not find main.py at: {MAIN_PY}")

    text = MAIN_PY.read_text(encoding="utf-8")
    pattern = re.compile(r"^current_resource_link\s*=\s*[\"\'].*?[\"\']\s*$", re.MULTILINE)
    replacement = f'current_resource_link = "{new_link}"'

    if pattern.search(text):
        updated = pattern.sub(replacement, text, count=1)
    else:
        raise RuntimeError("Could not locate current_resource_link assignment in main.py")

    MAIN_PY.write_text(updated, encoding="utf-8")
    _log("Updated current_resource_link in main.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package sounds/images into a zip, upload to Pixeldrain, and update main.py link."
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("PIXELDRAIN_API_KEY", "").strip(),
        help=(
            "Pixeldrain API key. Defaults to PIXELDRAIN_API_KEY env var. Optional "
            "for anonymous uploads, but recommended so the file is not purged for inactivity."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="HTTP timeout in seconds for upload requests.",
    )
    parser.add_argument(
        "--no-update-main",
        action="store_true",
        help="Upload resource zip but do not update current_resource_link in main.py.",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Keep the local zip after successful upload.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = args.api_key or None

    zip_path = create_resource_zip()
    try:
        link = upload_to_pixeldrain(zip_path, api_key=api_key, timeout=args.timeout)
        if not args.no_update_main:
            update_main_resource_link(link)
        _log("Done")
        print(link)
        return 0
    finally:
        if zip_path.exists() and not args.keep_zip:
            try:
                zip_path.unlink()
            except Exception:
                _log(f"Warning: failed to remove temporary zip: {zip_path}")


if __name__ == "__main__":
    raise SystemExit(main())
