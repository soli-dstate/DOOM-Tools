import argparse
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

import requests


API_URL = "https://catbox.moe/user/api.php"
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


def upload_to_catbox(zip_path: Path, userhash: str | None, timeout: int) -> str:
    data = {"reqtype": "fileupload"}
    if userhash:
        data["userhash"] = userhash

    with zip_path.open("rb") as handle:
        files = {
            "fileToUpload": (
                zip_path.name,
                handle,
                "application/zip",
            )
        }
        response = requests.post(API_URL, data=data, files=files, timeout=timeout)

    response.raise_for_status()
    body = response.text.strip()
    if not body.lower().startswith("http"):
        raise RuntimeError(f"Unexpected Catbox response: {body}")

    _log(f"Uploaded to Catbox: {body}")
    return body


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
        description="Package sounds/images into a zip, upload to Catbox, and update main.py link."
    )
    parser.add_argument(
        "--userhash",
        default=os.getenv("CATBOX_USERHASH", "").strip(),
        help="Catbox userhash. Defaults to CATBOX_USERHASH env var. Optional for anonymous uploads.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
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
    userhash = args.userhash or None

    zip_path = create_resource_zip()
    try:
        link = upload_to_catbox(zip_path, userhash=userhash, timeout=args.timeout)
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
