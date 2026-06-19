version = "2.0.13"
current_resource_links = [
    "https://files.catbox.moe/gtbtty.001",
    "https://files.catbox.moe/r3ic2z.002",
]
import os
import logging
import re
from datetime import datetime
from datetime import timezone, timedelta
import zipfile
import glob
import requests
import platform
import pygame
import customtkinter
import tkinter as _tk
import base64
import json
import shutil
import subprocess
import psutil
import locale
import random
import math
import time
import secrets
import ctypes
import threading
import queue
import pyperclip
import sys
import inspect
import distro
import numpy as np

def _sanitize_log(s):
    if not isinstance(s, str):
        s = str(s)
    return s.replace('\n', '\\n').replace('\r', '\\r').replace('\x1b', '\\x1b')

import hashlib as _hashlib
import hmac as _hmac

def _get_shared_key_dir():
    # Single machine-wide location for the save signing key, independent of
    # devmode. Both devmode (./saves) and production (LOCALAPPDATA) sign with the
    # same key so character saves transfer between modes on the same PC.
    if os.name == 'nt':
        base = os.getenv('LOCALAPPDATA')or os.path.expanduser('~')
        return os.path.join(base, 'soli_dstate', 'DOOM-Tools')
    return os.path.expanduser('~/.local/share/soli_dstate/DOOM-Tools')

def _get_save_key_path():
    return os.path.join(_get_shared_key_dir(), ".save_key")

def _legacy_save_key_paths():
    # Older per-folder key locations, checked once to migrate existing saves so
    # they keep verifying after the key moved to a shared location.
    paths = []
    folder = saves_folder if 'saves_folder' in globals() and saves_folder else "saves"
    paths.append(os.path.join(folder, ".save_key"))
    paths.append(os.path.join("saves", ".save_key"))
    if os.name == 'nt':
        base = os.getenv('LOCALAPPDATA')or os.path.expanduser('~')
        paths.append(os.path.join(base, 'soli_dstate', 'DOOM-Tools', 'saves', ".save_key"))
    else:
        paths.append(os.path.expanduser('~/.local/share/soli_dstate/DOOM-Tools/saves/.save_key'))
    seen = set()
    out = []
    for p in paths:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            out.append(p)
    return out

def _get_save_key():
    key_path = _get_save_key_path()
    os.makedirs(os.path.dirname(key_path), exist_ok = True)
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            key = f.read()
        if len(key) >= 32:
            return key
    # Adopt an existing per-folder key (devmode or production) so saves signed
    # before this change still load and remain transferable between modes.
    for legacy_path in _legacy_save_key_paths():
        try:
            if os.path.exists(legacy_path):
                with open(legacy_path, 'rb') as f:
                    legacy_key = f.read()
                if len(legacy_key) >= 32:
                    with open(key_path, 'wb') as f:
                        f.write(legacy_key)
                    return legacy_key
        except Exception:
            pass
    key = secrets.token_bytes(32)
    with open(key_path, 'wb') as f:
        f.write(key)
    return key

_PORTABLE_KEY = _hashlib.sha256(b"DOOM-Tools-portable-transfer-signing-key-v1").digest()

def _candidate_save_keys():
    # The shared key (used for new signatures) plus any legacy per-folder keys,
    # so saves signed before the key was unified still verify on this machine.
    keys = []
    try:
        keys.append(_get_save_key())
    except Exception:
        pass
    for legacy_path in _legacy_save_key_paths():
        try:
            if os.path.exists(legacy_path):
                with open(legacy_path, 'rb') as f:
                    legacy_key = f.read()
                if len(legacy_key) >= 32 and legacy_key not in keys:
                    keys.append(legacy_key)
        except Exception:
            pass
    # Signing key imported from cloud restore, so saves created on another
    # machine still verify here.
    try:
        cloud_key_path = os.path.join(_get_shared_key_dir(), ".cloud_save_key")
        if os.path.exists(cloud_key_path):
            with open(cloud_key_path, 'rb') as f:
                cloud_key = f.read()
            if len(cloud_key) >= 32 and cloud_key not in keys:
                keys.append(cloud_key)
    except Exception:
        pass
    return keys

def _sign_data(payload_str, *, portable = False):
    key = _PORTABLE_KEY if portable else _get_save_key()
    return _hmac.new(key, payload_str.encode('utf-8'), _hashlib.sha256).hexdigest()

def _verify_signature(payload_str, signature, *, portable = False):
    if portable:
        expected = _hmac.new(_PORTABLE_KEY, payload_str.encode('utf-8'), _hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected, signature)
    for key in _candidate_save_keys():
        expected = _hmac.new(key, payload_str.encode('utf-8'), _hashlib.sha256).hexdigest()
        if _hmac.compare_digest(expected, signature):
            return True
    return False

def _signed_json_write(filepath, data, *, binary_mode = False, comment_lines = None, portable = False):
    payload_str = json.dumps(data, ensure_ascii = False, sort_keys = True)
    sig = _sign_data(payload_str, portable = portable)
    envelope = json.dumps({"_sig": sig, "_data": data}, ensure_ascii = False)
    encoded = base64.b85encode(envelope.encode('utf-8')).decode('ascii')
    if binary_mode:
        with open(filepath, 'wb') as f:
            if comment_lines:
                for cl in comment_lines:
                    line = cl if cl.endswith("\n") else cl + "\n"
                    f.write(line.encode('utf-8'))
            f.write(encoded.encode('ascii'))
    else:
        with open(filepath, 'w', encoding = 'utf-8') as f:
            if comment_lines:
                for cl in comment_lines:
                    f.write(cl if cl.endswith("\n") else cl + "\n")
            f.write(encoded)

def _signed_json_read(filepath, *, allow_unsigned = False, portable = False):
    try:
        with open(filepath, 'r', encoding = 'utf-8') as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(filepath, 'rb') as f:
            text = f.read().decode('utf-8', errors = 'replace')

    lines = text.splitlines(True)
    comment_lines = []
    data_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("//"):
            comment_lines.append(line)
        elif stripped == "" and not data_lines:
            comment_lines.append(line)
        else:
            data_lines.append(line)
    payload = "".join(data_lines).strip()

    if not payload:
        return None, comment_lines, "incompatible_format"

    # Try base85 decode first (current format)
    decoded_json = None
    try:
        decoded_bytes = base64.b85decode(payload.encode('ascii'))
        decoded_json = decoded_bytes.decode('utf-8')
    except Exception:
        pass

    # If base85 decode failed, treat raw payload as JSON (legacy unsigned)
    if decoded_json is None:
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            return None, comment_lines, "incompatible_format"
        if allow_unsigned and isinstance(parsed, dict):
            return parsed, comment_lines, "unsigned"
        elif isinstance(parsed, dict):
            return None, comment_lines, "unsigned"
        else:
            return None, comment_lines, "invalid_structure"

    try:
        parsed = json.loads(decoded_json)
    except (json.JSONDecodeError, ValueError):
        return None, comment_lines, "incompatible_format"

    if isinstance(parsed, dict) and "_sig" in parsed and "_data" in parsed:
        sig = parsed["_sig"]
        data = parsed["_data"]
        payload_str = json.dumps(data, ensure_ascii = False, sort_keys = True)
        if _verify_signature(payload_str, sig, portable = portable):
            return data, comment_lines, "ok"
        else:
            return None, comment_lines, "tampered"
    elif allow_unsigned and isinstance(parsed, dict):
        return parsed, comment_lines, "unsigned"
    elif isinstance(parsed, dict):
        return None, comment_lines, "unsigned"
    else:
        return None, comment_lines, "invalid_structure"

# ============================================================
# Optional cloud saves (Google Drive)
# ------------------------------------------------------------
# Talks to the Drive REST API directly (no google client libraries) using the
# drive.file scope, so the app can only ever see files it created. Sign-in uses
# the OAuth 2.0 loopback flow: a browser opens, the user authorises, and Google
# redirects back to a short-lived local web server.
#
# TO ENABLE: in Google Cloud, create a project, enable the Google Drive API,
# configure the OAuth consent screen (add yourself / users as testers, or
# publish), create an OAuth client of type "Desktop app", then supply its client
# id/secret WITHOUT committing them to git, via any of (checked in order):
#   1. env vars DOOMTOOLS_GDRIVE_CLIENT_ID / DOOMTOOLS_GDRIVE_CLIENT_SECRET
#   2. a git-ignored cloud_credentials.json: {"client_id": "...", "client_secret": "..."}
#      placed next to main.py / the exe, in the app data dir, or bundled into the
#      build (scripts/build_release.py adds it via PyInstaller --add-data).
# While none are present, every cloud feature stays disabled and the program
# behaves exactly as before.
# ============================================================
def _cloud_credential_file_candidates():
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "cloud_credentials.json"))
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_credentials.json"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "cloud_credentials.json"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(_get_shared_key_dir(), "cloud_credentials.json"))
    except Exception:
        pass
    candidates.append(os.path.join(os.getcwd(), "cloud_credentials.json"))
    return candidates


def _cloud_credentials_source():
    """Where valid credentials came from (for diagnostics); never returns the secret."""
    if os.getenv("DOOMTOOLS_GDRIVE_CLIENT_ID", "").strip() and os.getenv("DOOMTOOLS_GDRIVE_CLIENT_SECRET", "").strip():
        return "env vars"
    seen = set()
    for path in _cloud_credential_file_candidates():
        ap = os.path.abspath(path)
        if ap in seen:
            continue
        seen.add(ap)
        try:
            if os.path.exists(path):
                data = json.load(open(path, "r", encoding="utf-8"))
                if str(data.get("client_id", "")).strip() and str(data.get("client_secret", "")).strip():
                    return f"file: {path}"
        except Exception:
            pass
    return None


def _load_cloud_credentials():
    cid = os.getenv("DOOMTOOLS_GDRIVE_CLIENT_ID", "").strip()
    csecret = os.getenv("DOOMTOOLS_GDRIVE_CLIENT_SECRET", "").strip()
    if cid and csecret:
        return cid, csecret
    seen = set()
    for path in _cloud_credential_file_candidates():
        ap = os.path.abspath(path)
        if ap in seen:
            continue
        seen.add(ap)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cid = str(data.get("client_id", "")).strip()
                csecret = str(data.get("client_secret", "")).strip()
                if cid and csecret:
                    return cid, csecret
        except Exception as e:
            logging.warning(f"Failed to read cloud credentials from {path}: {e}")
    return "", ""


GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET = _load_cloud_credentials()
GOOGLE_OAUTH_SCOPE = "https://www.googleapis.com/auth/drive.file"
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"
CLOUD_FOLDER_NAME = "DOOM-Tools Cloud Saves"
CLOUD_KEY_REMOTE_NAME = "doomtools.savekey"
# Saves are bundled into this single zip in the cloud folder (one fast upload
# instead of many per-file requests). The arcname inside the zip is the
# saves-relative path; the signing key is stored under CLOUD_KEY_REMOTE_NAME.
CLOUD_ARCHIVE_NAME = "doomtools-cloud-saves.zip"
# Top-level saves we do NOT push to the cloud (kept device-local).
CLOUD_SYNC_EXCLUDE = {"dm_settings.sldsv"}


# ============================================================
# Bug reports -> GitHub issues (via a server-side relay)
# ------------------------------------------------------------
# The app NEVER holds a GitHub token. In-app bug reports are POSTed to a small
# relay (e.g. a Cloudflare Worker — see tools/bugreport-relay/) that holds a
# fine-grained PAT (issues + gist write) server-side and creates the issue (and
# a secret Gist for the attached log) on this repo's behalf. Only the public
# relay URL ships with the app; the URL is NOT a secret, so the token never
# reaches the user's machine.
#
# Configure the relay URL via (checked in order):
#   1. env var DOOMTOOLS_BUGREPORT_URL
#   2. a bugreport_endpoint.txt next to main.py / the exe / app data dir / cwd
#   3. the BUGREPORT_ENDPOINT_DEFAULT constant below (baked into the build)
# While none are set, the bug-report button stays disabled.
# ============================================================
BUGREPORT_ENDPOINT_DEFAULT = "https://doomtools-bugreport.doom-tools.workers.dev/"  # e.g. "https://doomtools-bugreport.example.workers.dev"


def _bugreport_endpoint_file_candidates():
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "bugreport_endpoint.txt"))
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bugreport_endpoint.txt"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "bugreport_endpoint.txt"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(_get_shared_key_dir(), "bugreport_endpoint.txt"))
    except Exception:
        pass
    candidates.append(os.path.join(os.getcwd(), "bugreport_endpoint.txt"))
    return candidates


def bugreport_endpoint():
    """Resolve the bug-report relay URL (never returns a secret)."""
    url = os.getenv("DOOMTOOLS_BUGREPORT_URL", "").strip()
    if url:
        return url
    seen = set()
    for path in _bugreport_endpoint_file_candidates():
        ap = os.path.abspath(path)
        if ap in seen:
            continue
        seen.add(ap)
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                if val:
                    return val
        except Exception:
            pass
    return BUGREPORT_ENDPOINT_DEFAULT.strip()


def bugreport_is_configured():
    return bool(bugreport_endpoint())


def cloud_is_configured():
    return bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)


def _cloud_token_path():
    return os.path.join(_get_shared_key_dir(), ".cloud_auth.json")


def _cloud_state_path():
    return os.path.join(_get_shared_key_dir(), ".cloud_state.json")


def _cloud_imported_key_path():
    return os.path.join(_get_shared_key_dir(), ".cloud_save_key")


def _cloud_load_json(path):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _cloud_save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return True
    except Exception as e:
        logging.error(f"Failed to write {path}: {e}")
        return False


def cloud_is_signed_in():
    return bool(_cloud_load_json(_cloud_token_path()).get("refresh_token"))


def cloud_sign_out():
    try:
        token_path = _cloud_token_path()
        if os.path.exists(token_path):
            os.remove(token_path)
    except Exception:
        pass


def cloud_oauth_login(timeout=180):
    """Run the loopback OAuth flow and persist tokens. Blocking; returns True."""
    import http.server
    import urllib.parse
    import webbrowser

    if not cloud_is_configured():
        raise RuntimeError("Cloud saves are not configured (missing OAuth client id/secret).")

    auth_result = {"code": None, "error": None}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in params:
                auth_result["code"] = params["code"][0]
                body = b"<html><body><h2>DOOM-Tools: sign-in complete.</h2><p>You can close this tab.</p></body></html>"
            elif "error" in params:
                auth_result["error"] = params["error"][0]
                body = b"<html><body><h2>DOOM-Tools: sign-in failed.</h2></body></html>"
            else:
                body = b"<html><body>Waiting...</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    server.timeout = 1
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}"

    params = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_OAUTH_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = GOOGLE_AUTH_ENDPOINT + "?" + urllib.parse.urlencode(params)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    deadline = time.time() + timeout
    while auth_result["code"] is None and auth_result["error"] is None and time.time() < deadline:
        server.handle_request()
    try:
        server.server_close()
    except Exception:
        pass

    if auth_result["error"]:
        raise RuntimeError(f"OAuth error: {auth_result['error']}")
    if not auth_result["code"]:
        raise RuntimeError("Sign-in timed out or was cancelled.")

    resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data={
        "code": auth_result["code"],
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=30)
    _cloud_raise(resp)
    tokens = resp.json()
    if "refresh_token" not in tokens:
        existing = _cloud_load_json(_cloud_token_path())
        if existing.get("refresh_token"):
            tokens["refresh_token"] = existing["refresh_token"]
    tokens["_obtained_at"] = int(time.time())
    _cloud_save_json(_cloud_token_path(), tokens)
    return True


def _cloud_access_token():
    tokens = _cloud_load_json(_cloud_token_path())
    if not tokens.get("refresh_token"):
        raise RuntimeError("Not signed in to cloud.")
    obtained = tokens.get("_obtained_at", 0)
    expires_in = tokens.get("expires_in", 0)
    access = tokens.get("access_token")
    if access and obtained and time.time() < obtained + expires_in - 120:
        return access
    resp = requests.post(GOOGLE_TOKEN_ENDPOINT, data={
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "refresh_token": tokens["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=30)
    _cloud_raise(resp)
    refreshed = resp.json()
    tokens["access_token"] = refreshed.get("access_token")
    tokens["expires_in"] = refreshed.get("expires_in", 3600)
    tokens["_obtained_at"] = int(time.time())
    _cloud_save_json(_cloud_token_path(), tokens)
    return tokens["access_token"]


def _cloud_headers():
    return {"Authorization": f"Bearer {_cloud_access_token()}"}


def _cloud_raise(resp):
    """raise_for_status, but surface Google's error message body (not just the URL)."""
    if resp.status_code < 400:
        return resp
    detail = resp.text
    try:
        payload = resp.json()
        err = payload.get("error")
        if isinstance(err, dict):
            detail = err.get("message") or detail
        elif isinstance(err, str):
            detail = payload.get("error_description") or err
    except Exception:
        pass
    raise RuntimeError(f"{resp.status_code} {resp.reason}: {str(detail).strip()[:400]}")


def _cloud_get_folder_id(create=True):
    state = _cloud_load_json(_cloud_state_path())
    folder_id = state.get("folder_id")
    if folder_id:
        check = requests.get(f"{DRIVE_API}/files/{folder_id}", headers=_cloud_headers(),
                             params={"fields": "id,trashed"}, timeout=30)
        if check.status_code == 200 and not check.json().get("trashed"):
            return folder_id
        folder_id = None
    query = ("mimeType='application/vnd.google-apps.folder' and trashed=false and "
             f"name='{CLOUD_FOLDER_NAME}'")
    resp = requests.get(f"{DRIVE_API}/files", headers=_cloud_headers(),
                        params={"q": query, "spaces": "drive", "fields": "files(id,name)"},
                        timeout=30)
    _cloud_raise(resp)
    files = resp.json().get("files", [])
    if files:
        folder_id = files[0]["id"]
    elif create:
        created = requests.post(f"{DRIVE_API}/files", headers=_cloud_headers(),
                                json={"name": CLOUD_FOLDER_NAME,
                                      "mimeType": "application/vnd.google-apps.folder"},
                                timeout=30)
        _cloud_raise(created)
        folder_id = created.json()["id"]
    else:
        return None
    state["folder_id"] = folder_id
    _cloud_save_json(_cloud_state_path(), state)
    return folder_id


def _cloud_list_folder(folder_id):
    resp = requests.get(f"{DRIVE_API}/files", headers=_cloud_headers(),
                        params={"q": f"'{folder_id}' in parents and trashed=false",
                                "spaces": "drive",
                                "fields": "files(id,name,modifiedTime,size)"},
                        timeout=30)
    _cloud_raise(resp)
    return resp.json().get("files", [])


class _CloudUploadBody:
    """Streaming body for a Drive media upload that reports bytes as they are sent.

    __iter__ makes requests stream it; __len__ sets Content-Length (no chunked).
    """

    def __init__(self, path, on_chunk=None, block=262144):
        self._path = path
        self._size = os.path.getsize(path)
        self._on_chunk = on_chunk
        self._block = block

    def __len__(self):
        return self._size

    def __iter__(self):
        with open(self._path, "rb") as handle:
            while True:
                chunk = handle.read(self._block)
                if not chunk:
                    break
                if self._on_chunk:
                    self._on_chunk(len(chunk))
                yield chunk


def _cloud_upload_file(folder_id, local_path, remote_name, existing_id=None, on_chunk=None):
    if not existing_id:
        meta = requests.post(f"{DRIVE_API}/files", headers=_cloud_headers(),
                             json={"name": remote_name, "parents": [folder_id]},
                             timeout=30)
        _cloud_raise(meta)
        existing_id = meta.json()["id"]
    media = requests.patch(
        f"{DRIVE_UPLOAD_API}/files/{existing_id}",
        headers={**_cloud_headers(), "Content-Type": "application/octet-stream"},
        params={"uploadType": "media"},
        data=_CloudUploadBody(local_path, on_chunk=on_chunk), timeout=120)
    _cloud_raise(media)
    return existing_id


def _cloud_download_file(file_id, dest_path):
    resp = requests.get(f"{DRIVE_API}/files/{file_id}", headers=_cloud_headers(),
                        params={"alt": "media"}, timeout=120)
    _cloud_raise(resp)
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(resp.content)


def _cloud_get_storage_quota():
    """Return the account's Drive storage quota dict (works with drive.file scope).

    Keys (bytes, as strings): 'limit' (absent if unlimited), 'usage',
    'usageInDrive', 'usageInDriveTrash'.
    """
    resp = requests.get(f"{DRIVE_API}/about", headers=_cloud_headers(),
                        params={"fields": "storageQuota"}, timeout=30)
    _cloud_raise(resp)
    return resp.json().get("storageQuota", {})


def _format_bytes(num):
    try:
        num = float(num)
    except (TypeError, ValueError):
        return "?"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num) < 1024.0 or unit == "PB":
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} B"
        num /= 1024.0
    return f"{num:.1f} PB"

pygame.init()

pygame.mixer.init(channels = 2)
pygame.mixer.set_num_channels(512)

try:
    import platform as _platform_mod

    _orig_ctk_sf_init = getattr(customtkinter.CTkScrollableFrame, "__init__", None)

    def _find_scrollable_canvas(widget):
        try:

            queue =[widget]
            while queue:
                w = queue.pop(0)
                if hasattr(w, "yview_scroll"):
                    return w
                try:
                    for _child in w.winfo_children():
                        queue.append(_child)
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def _ctk_scrollableframe_init_wrapper(self, *a, **k):
        if _orig_ctk_sf_init:
            _orig_ctk_sf_init(self, *a, **k)

        def _on_mousewheel_global(event):
            try:
                c = _find_scrollable_canvas(self)
                if not c:
                    return
                sys_platform = _platform_mod.system()

                if hasattr(event, 'num')and event.num in(4, 5):
                    if event.num ==4:
                        c.yview_scroll(-1, "units")
                    else:
                        c.yview_scroll(1, "units")
                else:
                    delta = getattr(event, 'delta', 0)
                    if sys_platform =="Windows":
                        lines = int(-1 *(delta /120))if delta else 0
                    elif sys_platform =="Darwin":
                        lines = int(-1 *delta)if delta else 0
                    else:

                        try:
                            lines = int(-1 *(delta /120))
                        except Exception:
                            lines = 0
                    if lines:
                        c.yview_scroll(lines, "units")
            except Exception:
                pass

        try:

            def _bt4(ev):
                try:

                    x = getattr(ev, 'x_root', None)
                    y = getattr(ev, 'y_root', None)
                    target = None
                    if x is not None and y is not None:
                        try:
                            target = self._parent_canvas.winfo_containing(x, y)
                        except Exception:
                            target = None
                    if target is None:
                        target = getattr(ev, 'widget', None)
                    if not target:
                        return
                    if not self.check_if_master_is_canvas(target):
                        return
                    class _E:pass
                    e = _E()
                    e.widget = getattr(self, "_parent_canvas", None)
                    e.delta = 1
                    e.num = 4
                except Exception:
                    e = ev
                try:
                    self._mouse_wheel_all(e)
                except Exception:
                    pass

            def _bt5(ev):
                try:
                    x = getattr(ev, 'x_root', None)
                    y = getattr(ev, 'y_root', None)
                    target = None
                    if x is not None and y is not None:
                        try:
                            target = self._parent_canvas.winfo_containing(x, y)
                        except Exception:
                            target = None
                    if target is None:
                        target = getattr(ev, 'widget', None)
                    if not target:
                        return
                    if not self.check_if_master_is_canvas(target):
                        return
                    class _E:pass
                    e = _E()
                    e.widget = getattr(self, "_parent_canvas", None)
                    e.delta = -1
                    e.num = 5
                except Exception:
                    e = ev
                try:
                    self._mouse_wheel_all(e)
                except Exception:
                    pass

            self.bind_all("<Button-4>", _bt4, add = "+")
            self.bind_all("<Button-5>", _bt5, add = "+")
        except Exception:
            pass

    try:
        customtkinter.CTkScrollableFrame.__init__ = _ctk_scrollableframe_init_wrapper
    except Exception:
        pass
except Exception as e:
    if global_variables["devmode"]["value"]:
        logging.exception("An error occurred: %s", e)
    else:
        pass

try:
    _orig_focus = getattr(_tk.Misc, 'focus', None)
    _orig_focus_set = getattr(_tk.Misc, 'focus_set', None)
    _orig_focus_force = getattr(_tk.Misc, 'focus_force', None)

    def _wrapped_focus(self, *a, **k):
        try:
            if getattr(self, 'winfo_exists', lambda:False)():
                if _orig_focus:
                    return _orig_focus(self, *a, **k)
        except Exception:
            pass

    def _wrapped_focus_set(self, *a, **k):
        try:
            self_obj = a[0]if a else None
        except Exception:
            self_obj = None
        try:
            widget = self_obj if self_obj is not None else None
            if widget is None:
                widget = getattr(k.get('self', None), 'winfo_exists', None)
        except Exception:
            widget = None
        try:

            obj = getattr(self_obj, '__self__', None)or self_obj
            if obj and getattr(obj, 'winfo_exists', lambda:False)():
                if _orig_focus_set:
                    return _orig_focus_set(obj, *a[1:], **k)if a else _orig_focus_set(obj, **k)
        except Exception:
            try:
                if getattr(self, 'winfo_exists', lambda:False)():
                    if _orig_focus_set:
                        return _orig_focus_set(self, *a, **k)
            except Exception:
                pass

    def _wrapped_focus_force(self, *a, **k):
        try:
            if getattr(self, 'winfo_exists', lambda:False)():
                if _orig_focus_force:
                    return _orig_focus_force(self, *a, **k)
        except Exception:
            pass

    try:
        if _orig_focus is not None:
            _tk.Misc.focus = _wrapped_focus
    except Exception:
        pass
    try:
        if _orig_focus_set is not None:
            _tk.Misc.focus_set = _wrapped_focus_set
    except Exception:
        pass
    try:
        if _orig_focus_force is not None:
            _tk.Misc.focus_force = _wrapped_focus_force
    except Exception:
        pass
except Exception as e:
    if global_variables["devmode"]["value"]:
        logging.exception("An error occurred: %s", e)
    else:
        pass

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

os.makedirs("logs", exist_ok = True)
os.makedirs("logs/archive", exist_ok = True)

log_files = glob.glob("logs/*.log")
if len(log_files)>=50:
    archive_name = f"logs/archive/logs_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED)as zipf:
        for log_file in log_files:
            zipf.write(log_file, os.path.basename(log_file))
            os.remove(log_file)

existing_logs = glob.glob("logs/log_*.log")
log_number = len(existing_logs)+1

log_filename = f"logs/log_{log_number}_{datetime.now().strftime('%A_%B_%d_%Y_%H_%M_%S_%f')[:-3]}.log"

file_formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
console_formatter = ColoredFormatter('%(asctime)s | %(levelname)s | %(message)s')

file_handler = logging.FileHandler(log_filename)
file_handler.setFormatter(StripAnsiFormatter('%(asctime)s | %(levelname)s | %(message)s'))

console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)

logging.basicConfig(
level = logging.INFO,
handlers =[file_handler, console_handler]
)

# Dump native (C-level) crash tracebacks into the session log so hard crashes
# leave a clue in the log that gets attached to the auto-filed bug report.
try:
    import faulthandler
    faulthandler.enable(file = file_handler.stream)
except Exception:
    pass

dev_log_counters = {
'DEBUG':0,
'INFO':0,
'WARNING':0,
'ERROR':0,
'CRITICAL':0,
}

class DevLogCounter(logging.Handler):

    def emit(self, record:logging.LogRecord)->None:
        try:
            lvl = record.levelname
            if lvl in dev_log_counters:
                dev_log_counters[lvl]+=1
        except Exception:
            pass

try:
    logging.getLogger().addHandler(DevLogCounter())
except Exception as e:
    if global_variables["devmode"]["value"]:
        logging.exception("An error occurred: %s", e)
    else:
        pass

ANSI_COLORS = {
'black':'\033[30m',
'red':'\033[31m',
'green':'\033[32m',
'yellow':'\033[33m',
'blue':'\033[34m',
'magenta':'\033[35m',
'cyan':'\033[36m',
'white':'\033[37m',
}

def color_text(text:str, color:str |None)->str:
    if not color:
        return text
    prefix = ANSI_COLORS.get(color, '')
    if not prefix:
        return text
    return f"{prefix}{text}\033[0m"

def strip_ansi(text:str)->str:
    return StripAnsiFormatter.ANSI_RE.sub('', text)

def log_console_colored(logger:logging.Logger, level:int, msg:str, color:str |None = None):

    plain = strip_ansi(msg)
    for h in getattr(logger, 'handlers', []):
        try:

            if isinstance(h, logging.FileHandler):
                rec = logging.LogRecord(logger.name, level, pathname = '', lineno = 0, msg = plain, args =(), exc_info = None)
                try:
                    h.handle(rec)
                except Exception:

                    try:
                        h.emit(rec)
                    except Exception:
                        pass

            elif isinstance(h, logging.StreamHandler):
                rec = logging.LogRecord(logger.name, level, pathname = '', lineno = 0, msg = plain, args =(), exc_info = None)
                try:
                    formatted = h.format(rec)
                except Exception:
                    formatted = plain
                if color:
                    try:
                        formatted = formatted.replace(plain, color_text(plain, color), 1)
                    except Exception:
                        pass
                try:
                    stream = h.stream
                    stream.write(formatted +getattr(h, 'terminator', '\n'))
                    stream.flush()
                except Exception:
                    pass
            else:

                rec = logging.LogRecord(logger.name, level, pathname = '', lineno = 0, msg = plain, args =(), exc_info = None)
                try:
                    h.handle(rec)
                except Exception:
                    try:
                        h.emit(rec)
                    except Exception:
                        pass
        except Exception:
            pass

def log_with_colored_substring(logger:logging.Logger, level:int, plain_msg:str, substring:str, color:str):

    plain = strip_ansi(plain_msg)
    logger.log(level, plain, extra = {"suppress_console":True})

    colored_sub = color_text(substring, color)
    for h in getattr(logger, 'handlers', []):
        try:
            if isinstance(h, logging.StreamHandler)and not isinstance(h, logging.FileHandler):
                try:
                    rec = logging.LogRecord(logger.name, level, pathname = '', lineno = 0, msg = plain, args =(), exc_info = None)
                    formatted = h.format(rec)

                    formatted = formatted.replace(substring, colored_sub, 1)
                    stream = h.stream
                    stream.write(formatted +(getattr(h, 'terminator', '\n')))
                    stream.flush()
                except Exception:
                    pass
        except Exception:
            pass

class ConsoleFilter(logging.Filter):

    def filter(self, record:logging.LogRecord)->bool:
        return not getattr(record, 'suppress_console', False)

try:
    console_handler.addFilter(ConsoleFilter())
except Exception as e:
    if global_variables["devmode"]["value"]:
        logging.exception("An error occurred: %s", e)
    else:
        pass
import warnings

logging.captureWarnings(True)
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical(
    "Uncaught exception",
    exc_info =(exc_type, exc_value, exc_traceback)
    )
    try:
        _app = globals().get("app")
        if _app is not None and hasattr(_app, "_report_exception"):
            _app._report_exception(exc_type, exc_value, exc_traceback, source="excepthook")
    except Exception:
        pass
import sys

sys.excepthook = handle_exception

def _thread_exception_handler(args):
    try:
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
    except Exception:
        pass
    logging.critical("Uncaught thread exception", exc_info =(args.exc_type, args.exc_value, args.exc_traceback))

try:
    threading.excepthook = _thread_exception_handler
except Exception:

    pass

os.system('cls'if os.name =='nt'else 'clear')

logging.info(f"DOOM Tools, version {version}")
try:
    response = requests.get("https://uselessfacts.jsph.pl/random.json?language=en")
    response.raise_for_status()
    fact = response.json().get("text", "No fact retrieved")
    logging.info(f"{fact}")
except requests.RequestException as e:
    logging.warning(f"Failed to fetch random fact: {e}")

logging.info("Start system information dump")
logging.info(f"Platform: {platform.platform()}")
logging.info(f"Processor: {platform.processor()}")
logging.info(f"Python version: {platform.python_version()}")
distribution_info = "Unknown"
try:
    if os.name !='nt':
        import distro
        distribution_info = f"{distro.name()} {distro.version()}({distro.codename()})"
    else:
        distribution_info = platform.platform()
except ImportError:
    logging.info("distro module not installed; skipping Linux distribution info")
logging.info(f"Distribution: {distribution_info}")
try:
    try:
        locale.setlocale(locale.LC_ALL, '')
    except Exception as e:
        logging.debug(f"Failed to set locale from environment: {e}")
    loc = None
    try:
        loc = locale.getlocale()
    except Exception as e:
        logging.debug(f"locale.getlocale() failed: {e}")
    enc = None
    if hasattr(locale, "getencoding"):
        try:
            enc = locale.getencoding()
        except Exception as e:
            logging.debug(f"locale.getencoding() failed: {e}")
    if not enc:
        try:
            enc = locale.getpreferredencoding(False)
        except Exception as e:
            logging.debug(f"locale.getpreferredencoding() failed: {e}")
    logging.info(f"Locale: {loc}, encoding: {enc}")
except Exception as e:
    logging.warning(f"Failed to determine locale information: {e}")
logging.info(f"CPU count: {psutil.cpu_count(logical = True)}")
logging.info(f"Total RAM: {round(psutil.virtual_memory().total /(1024 **3), 2)} GB")
logging.info(f"Available RAM: {round(psutil.virtual_memory().available /(1024 **3), 2)} GB")
logging.info(f"Python executable: {sys.executable}")
logging.info(f"Current working directory: {os.getcwd()}")
logging.info("End system information dump")

global_variables = {
"devmode":{"value":False, "forced":False},
"dmmode":{"value":False, "forced":False},
"debugmode":{"value":False, "forced":False},
"current_table":None,
"ide":False,
"table_extension":".sldtbl",
"save_extension":".sldsv",
"lootcrate_extension":".sldlct",
"transfer_extension":".sldtrf",
"enemyloot_extension":".sldenlt",
}

def get_current_table_path():

    current_tbl = global_variables.get('current_table')
    if current_tbl:
        path = os.path.join("tables", current_tbl)
        if os.path.exists(path):
            return path
        ext = global_variables.get('table_extension', '.sldtbl')
        if not current_tbl.endswith(ext):
            path_with_ext = os.path.join("tables", current_tbl +ext)
            if os.path.exists(path_with_ext):
                global_variables['current_table']= current_tbl +ext
                return path_with_ext
    table_files = sorted(glob.glob(os.path.join("tables", f"*{global_variables.get('table_extension', '.sldtbl')}")))
    if table_files:
        return table_files[0]
    return None

_currency_cache = {"rates": {}, "last_fetched": 0, "lock": threading.Lock()}
_table_currency_cache = {"path": None, "mtime": None, "currency": "USD", "lock": threading.Lock()}

_currency_symbols = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
    "KRW": "₩", "INR": "₹", "RUB": "₽", "BRL": "R$", "CAD": "CA$",
    "AUD": "A$", "CHF": "CHF ", "SEK": "kr ", "NOK": "kr ", "DKK": "kr ",
    "PLN": "zł ", "CZK": "Kč ", "HUF": "Ft ", "TRY": "₺", "MXN": "MX$",
    "ZAR": "R ", "NZD": "NZ$", "SGD": "S$", "HKD": "HK$", "TWD": "NT$",
    "THB": "฿", "PHP": "₱", "ILS": "₪", "AED": "د.إ ", "SAR": "﷼ ",
}

def _fetch_exchange_rates():
    try:
        now = time.time()
        with _currency_cache["lock"]:
            if _currency_cache["rates"] and (now - _currency_cache["last_fetched"]) < 3600:
                return
        resp = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            rates = data.get("rates", {})
            if rates:
                with _currency_cache["lock"]:
                    _currency_cache["rates"] = rates
                    _currency_cache["last_fetched"] = now
                logging.info("Fetched exchange rates: %d currencies", len(rates))
        else:
            logging.warning("Failed to fetch exchange rates (status %s)", resp.status_code)
    except Exception:
        logging.exception("Failed to fetch exchange rates")

def _get_table_currency():
    try:
        table_path = get_current_table_path()
        if table_path and os.path.exists(table_path):
            try:
                mtime = os.path.getmtime(table_path)
            except Exception:
                mtime = None
            with _table_currency_cache["lock"]:
                if _table_currency_cache["path"] == table_path and _table_currency_cache["mtime"] == mtime:
                    return _table_currency_cache["currency"] or 'USD'
            try:
                with open(table_path, 'r', encoding='utf-8') as tf:
                    td = json.load(tf)
                cur = ((td or {}).get('additional_settings') or {}).get('currency', 'USD') or 'USD'
                with _table_currency_cache["lock"]:
                    _table_currency_cache["path"] = table_path
                    _table_currency_cache["mtime"] = mtime
                    _table_currency_cache["currency"] = cur
                return cur
            except Exception:
                pass

        tbl = globals().get('table_data')
        if isinstance(tbl, dict):
            cur = (tbl.get('additional_settings') or {}).get('currency')
            if cur:
                return cur
    except Exception:
        pass
    return 'USD'

def _get_selected_display_currency():
    try:
        pref = str(appearance_settings.get("display_currency", "table")).strip()
        if not pref:
            return "table"
        if pref.lower() in ("table", "default", "table_default", "auto"):
            return "table"
        return pref.upper()
    except Exception:
        return "table"

def format_price(amount_usd):
    try:
        currency_pref = _get_selected_display_currency()
        currency = (_get_table_currency() if currency_pref == "table" else currency_pref).upper()
        if currency == "USD" or not currency:
            return f"${amount_usd:,.2f}" if isinstance(amount_usd, float) else f"${amount_usd:,}"
        with _currency_cache["lock"]:
            rates = _currency_cache["rates"]
        rate = rates.get(currency)
        symbol = _currency_symbols.get(currency, currency + " ")
        if rate is None:
            if currency in ("JPY", "KRW"):
                return f"{symbol}{float(amount_usd):,.0f}"
            return f"{symbol}{float(amount_usd):,.2f}"
        converted = float(amount_usd) * float(rate)
        if currency in ("JPY", "KRW"):
            return f"{symbol}{converted:,.0f}"
        return f"{symbol}{converted:,.2f}"
    except Exception:
        return f"${amount_usd}" if amount_usd is not None else "$0"

def parse_display_price_to_usd(value, default = None, round_to_int = False):
    raw = "" if value is None else str(value).strip()
    if not raw:
        if default is not None:
            return int(round(default)) if round_to_int else float(default)
        raise ValueError("No amount provided")

    currency_pref = _get_selected_display_currency()
    currency = (_get_table_currency() if currency_pref == "table" else currency_pref).upper()
    with _currency_cache["lock"]:
        rates = dict(_currency_cache["rates"] or {})
    rate = rates.get(currency)

    cleaned = raw
    try:
        cleaned = cleaned.replace(currency, "").replace(currency.lower(), "")
    except Exception:
        pass
    for sym in sorted(set(_currency_symbols.values()), key = len, reverse = True):
        if sym:
            cleaned = cleaned.replace(sym, "")

    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = re.sub(r"[^0-9,\.\-]", "", cleaned)

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = f"{parts[0]}.{parts[1]}"
        else:
            cleaned = cleaned.replace(",", "")

    if cleaned in ("", "-", ".", "-."):
        raise ValueError("Invalid amount")

    display_amount = float(cleaned)
    if currency != "USD" and rate:
        usd_amount = display_amount / float(rate)
    else:
        usd_amount = display_amount

    return int(round(usd_amount)) if round_to_int else float(usd_amount)

threading.Thread(target=_fetch_exchange_rates, daemon=True).start()

# Python 3.13 free-threaded (no-GIL) builds crash with PyEval_RestoreThread(NULL)
# if daemon threads are alive in C-level blocking calls when the interpreter
# starts finalizing.  Register os._exit(0) as an atexit handler so Python
# finalization never reaches the daemon-thread cleanup phase.
import atexit as _atexit
_atexit.register(os._exit, 0)

try:
    tfiles = sorted(glob.glob(os.path.join(os.getcwd(), 'tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
    if tfiles:
        with open(tfiles[0], 'r', encoding = 'utf-8')as _tf:
            _td = json.load(_tf)
        globals()['table_data']= _td
        global_variables['current_table']= os.path.basename(tfiles[0])
        logging.info(f"Loaded global table_data from {os.path.basename(tfiles[0])}")
except Exception:

    pass

def show_error_dialog(title, message):

    try:
        if os.name =='nt':
            try:
                ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0x10)
                return
            except Exception:

                pass
    except Exception:
        pass

    try:
        if shutil.which('zenity'):
            subprocess.run(['zenity', '--error', '--title', str(title), '--text', str(message)])
            return
        if shutil.which('kdialog'):
            subprocess.run(['kdialog', '--title', str(title), '--error', str(message)])
            return
        if shutil.which('notify-send'):
            subprocess.run(['notify-send', str(title), str(message)])
            return
    except Exception:
        pass

    try:
        import tkinter as _tk
        from tkinter import messagebox as _mb
        _root = _tk.Tk()
        _root.withdraw()
        _mb.showerror(str(title), str(message))
        try:
            _root.destroy()
        except Exception:
            pass
        return
    except Exception:
        logging.error("Unable to display GUI error dialog: %s - %s", title, message)
        logging.info(f"Linux distribution: {distribution_info}")

def show_table_selection_dialog():

    try:
        tfiles = sorted(glob.glob(os.path.join(os.getcwd(), 'tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
        if len(tfiles)<=1:
            return None

        table_info =[]
        for tpath in tfiles:
            try:
                with open(tpath, 'r', encoding = 'utf-8')as f:
                    tdata = json.load(f)
                prettyname = tdata.get('prettyname', os.path.basename(tpath))
                table_info.append({'path':tpath, 'filename':os.path.basename(tpath), 'prettyname':prettyname})
            except Exception:
                table_info.append({'path':tpath, 'filename':os.path.basename(tpath), 'prettyname':os.path.basename(tpath)})

        selected_table =[None]

        root = customtkinter.CTk()
        root.title("Select Data Table")
        root.geometry("500x400")
        root.resizable(False, False)

        try:
            root.attributes('-topmost', True)
        except Exception:
            pass

        title = customtkinter.CTkLabel(root, text = "Select Data Table", font = customtkinter.CTkFont(size = 20, weight = "bold"))
        title.pack(pady = 20)

        subtitle = customtkinter.CTkLabel(root, text = "Multiple data tables detected.Please select which table to use:", font = customtkinter.CTkFont(size = 12))
        subtitle.pack(pady =(0, 15))

        scroll_frame = customtkinter.CTkScrollableFrame(root, width = 450, height = 200)
        scroll_frame.pack(pady = 10, padx = 20)

        def select_table(info):
            selected_table[0]= info
            root.quit()
            root.destroy()

        for info in table_info:
            btn_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
            btn_frame.pack(fill = "x", pady = 5)

            btn = customtkinter.CTkButton(
            btn_frame,
            text = f"{info['prettyname']}\n({info['filename']})",
            command = lambda i = info:select_table(i),
            width = 420,
            height = 50,
            font = customtkinter.CTkFont(size = 14)
            )
            btn.pack()

        cancel_btn = customtkinter.CTkButton(root, text = "Exit", command = lambda:sys.exit(0), width = 150, height = 40, fg_color = "#666666")
        cancel_btn.pack(pady = 20)

        root.mainloop()

        if selected_table[0]:
            try:
                with open(selected_table[0]['path'], 'r', encoding = 'utf-8')as f:
                    globals()['table_data']= json.load(f)
                global_variables['current_table']= selected_table[0]['filename']
                logging.info(f"User selected table: {selected_table[0]['filename']}")
            except Exception as e:
                logging.error(f"Failed to load selected table: {e}")
        return selected_table[0]
    except Exception as e:
        logging.exception(f"Table selection dialog failed: {e}")
        return None

possible_flags =["--dev", "--dm", "--debug", "--force", "-debug"]

for flag in possible_flags:
    if flag in sys.argv:
        if flag =="--dev":
            global_variables["devmode"]["value"]= True
            logging.info("Development mode activated via command-line flag.")
        elif flag =="--dm":
            global_variables["dmmode"]["value"]= True
            logging.info("DM mode activated via command-line flag.")
        elif flag in("--debug", "-debug"):
            global_variables["debugmode"]["value"]= True
            logging.info("Debug mode activated via command-line flag.")
        elif flag =="--force":
            for var in global_variables:
                if isinstance(global_variables[var], dict)and "forced"in global_variables[var]:
                                    global_variables[var]["forced"]= True
            logging.info("Force flag applied to all modes.")

if global_variables["debugmode"]["value"]:
    logging.getLogger().setLevel(logging.DEBUG)
    logging.info("Debug mode enabled.Logging level set to DEBUG.")
    logging.info("Starting debug tests")
    logging.debug("Debug level test")
    logging.info("Info level test")
    logging.warning("Warning level test")
    logging.error("Error level test")
    logging.critical("Critical level test")
    logging.info("Debug tests complete")

appearance_settings = {
"appearance_mode":"system",
"color_theme":"dark-blue",
"resolution":"1920x1080",
"fullscreen":False,
"borderless":False,
"units":"imperial",
"display_currency":"table",
"auto_set_units":False,
"sound_volume":100,
"music_volume":100,
"mute_business_music":False,
"business_music_sync_mode":"random",
"business_music_sync_seed":"doom-tools-shared",
"business_music_sync_force_track":"",
"business_music_sync_force_position":-1.0,
"weather_visual_effects":True,
"weather_audio_effects":True
}

folders =[
{"name":"logs", "ignore_gitignore":False},
{"name":"sounds", "ignore_gitignore":False},
{"name":"tables", "ignore_gitignore":True},
{"name":"transfers", "ignore_gitignore":False},
{"name":"lootcrates", "ignore_gitignore":False},
{"name":"enemyloot", "ignore_gitignore":False},
{"name":"themes", "ignore_gitignore":False},
{"name":"combatreports", "ignore_gitignore":False},
]

themes_dir = "themes"
os.makedirs(themes_dir, exist_ok = True)

tmp_zip = None
extract_dir = None

try:
    if not any(os.scandir(themes_dir)):
        logging.info("Themes folder is empty.Downloading CTkThemesPack...")
        tmp_zip = "CTkThemesPack.zip"
        extract_dir = "CTkThemesPack_src"

        response = requests.get("https://github.com/a13xe/CTkThemesPack/archive/refs/heads/main.zip", timeout = 30)
        response.raise_for_status()
        with open(tmp_zip, "wb")as f:
            f.write(response.content)

        os.makedirs(extract_dir, exist_ok = True)
        import pathlib as _pathlib
        _extract_dest = _pathlib.Path(extract_dir).resolve()
        with zipfile.ZipFile(tmp_zip, "r")as zip_ref:
            for member in zip_ref.infolist():
                member_target = (_extract_dest / member.filename).resolve()
                if not str(member_target).startswith(str(_extract_dest)):
                    raise ValueError(f"Zip slip detected: {member.filename}")
                zip_ref.extract(member, extract_dir)

        extracted_roots =[d for d in os.listdir(extract_dir)if os.path.isdir(os.path.join(extract_dir, d))]
        if extracted_roots:
            src_theme_dir = os.path.join(extract_dir, extracted_roots[0], "themes")
            if os.path.isdir(src_theme_dir):
                for entry in os.listdir(src_theme_dir):
                    src_path = os.path.join(src_theme_dir, entry)
                    dst_path = os.path.join(themes_dir, entry)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, dst_path, dirs_exist_ok = True)
                    else:
                        shutil.copy2(src_path, dst_path)
                logging.info("Themes downloaded and installed successfully.")
            else:
                logging.warning("No 'themes' directory found in downloaded package.")
        else:
            logging.warning("Failed to locate extracted CTkThemesPack directory.")

except Exception as e:
    logging.error(f"Failed to populate themes: {e}")

ide_indicators =[
'PYCHARM_HOSTED',
'VSCODE_PID',
'SPYDER_KERNELS_NAMESPACE',
'PYDEVD_USE_FRAME_EVAL',
'TERM_PROGRAM',
'JUPYTER_RUNTIME_DIR',
'JPY_PARENT_PID',
'IPYTHONDIR',
'PYCHARM_MATPLOTLIB_INTERACTIVE',
'PYCHARM_DISPLAY_PORT',
'INTELLIJ_ENVIRONMENT_READER',
'IDEA_INITIAL_DIRECTORY',
'PYTHONIOENCODING',
'PYDEV_CONSOLE_ENCODING',
'VSCODE_CLI',
'VSCODE_GIT_ASKPASS_NODE',
'VSCODE_INJECTION'
]

try:
    _debugger_attached = sys.gettrace()is not None
except Exception:
    _debugger_attached = False
if not _debugger_attached:
    _debugger_attached = any(m in sys.modules for m in('pydevd', 'debugpy', 'ptvsd'))
if _debugger_attached:
    if('-debug'not in sys.argv)and('--debug'not in sys.argv):
        sys.argv.append('-debug')
        logging.info('Debugger detected; added -debug to argv')

dm_users = ["bGlseQ==", "amFjemk=", "cGhvbmU=", "YWlkZW4=", "V0RBR1V0aWxpdHlBY2NvdW50"]

def _decode_b64_if_possible(s):
    try:
        if not isinstance(s, str):
            return s
        b = s.encode('ascii')
    except Exception:
        return s
    try:
        # validate=True ensures only valid base64 is accepted
        decoded = base64.b64decode(b, validate=True)
        return decoded.decode('utf-8')
    except Exception:
        return s

try:
    dm_users = [_decode_b64_if_possible(u) for u in dm_users]
    logging.debug(f"Decoded dm_users: {dm_users}")
except Exception as _e:
    logging.debug(f"Failed to decode dm_users from base64: {_e}")

if any(indicator in os.environ for indicator in ide_indicators):
    if not global_variables["devmode"]["value"]and not global_variables["devmode"]["forced"]:
        global_variables["devmode"]["value"]= True
        logging.info("Development mode activated due to IDE environment detection.")
    elif global_variables["devmode"]["value"]:
        logging.info("IDE environment detected, but development mode is already set.")
    else:
        logging.info("IDE environment detected, but development mode is forced off.")
    logging.info(f"Trigger: {[key for key in os.environ if key in ide_indicators]}")
    global_variables["ide"]= True
    try:

            try:
                from scripts import generate_requirements
                generate_requirements.generate_requirements(ide_mode = True)
            except Exception:
                logging.exception('Failed to refresh requirements.txt in IDE mode')
    except Exception:
        pass
    for folder_entry in folders:
        folder = folder_entry["name"]
        ignore_gitignore = folder_entry.get("ignore_gitignore", False)

        if not os.path.exists(folder):
            os.makedirs(folder)
            logging.info(f"Created missing folder: {folder}")
        if ignore_gitignore:
            logging.info(f"Skipped.gitignore addition for '{folder}'(ignore_gitignore=True)")
            continue

        with open('.gitignore', 'a')as gitignore:
            existing_gitignore = set()
            try:
                with open('.gitignore', 'r')as read_gitignore:
                    existing_gitignore = set(line.strip()for line in read_gitignore)
            except FileNotFoundError:
                pass
            entry = f'/{folder}/'
            if entry not in existing_gitignore:
                gitignore.write(f'{entry}\n')
                logging.info(f"Added '{entry}' to.gitignore")
            else:
                logging.info(f"'{entry}' already exists in.gitignore")
    try:
        from scripts import generate_requirements
        generate_requirements.generate_requirements(ide_mode = False)
    except Exception as e:
        logging.warning(f"Failed to update requirements.txt: {e}")

saves_folder = "saves"

if not global_variables["devmode"]["value"]:
    logging.info("Running in production mode.")
    if os.name =='nt':
        base_ld = os.getenv('LOCALAPPDATA')or os.path.expanduser('~')
        saves_folder = os.path.join(base_ld, 'soli_dstate', 'DOOM-Tools', 'saves')
    else:
        saves_folder = os.path.expanduser('~/.local/share/soli_dstate/DOOM-Tools/saves')
else:
    logging.info("Running in development mode.")
    saves_folder = "saves"
    folders.append({"name":"saves", "ignore_gitignore":False})

for folder_entry in folders:
    folder = folder_entry["name"]
    if not os.path.exists(folder):
        os.makedirs(folder)
        logging.info(f"Created missing folder: {folder}")

os.makedirs(saves_folder or "saves", exist_ok = True)

try:
    appearance_settings_path = os.path.join(saves_folder, "appearance_settings.sldsv")
    if os.path.exists(appearance_settings_path):
        loaded_settings, _, a_status = _signed_json_read(appearance_settings_path, allow_unsigned = True)
        if isinstance(loaded_settings, dict):
            appearance_settings.update(loaded_settings)
            try:
                _disp_cur = str(appearance_settings.get("display_currency", "table")).strip()
                if not _disp_cur or _disp_cur.lower() in ("table", "default", "table_default", "auto"):
                    appearance_settings["display_currency"] = "table"
                else:
                    appearance_settings["display_currency"] = _disp_cur.upper()
            except Exception:
                appearance_settings["display_currency"] = "table"
            logging.info(f"Appearance settings loaded from {appearance_settings_path} (status: {a_status})")
        else:
            logging.warning(f"Appearance settings in {appearance_settings_path} could not be loaded (status: {a_status})")
except Exception as e:
    logging.warning(f"Failed to load appearance settings: {e}")

try:
    settings_path = os.path.join(saves_folder, "settings.sldsv")
    if os.path.exists(settings_path):
        loaded_globals, _, s_status = _signed_json_read(settings_path, allow_unsigned = True)
        if isinstance(loaded_globals, dict):
            for key, value in loaded_globals.items():
                if key in global_variables:
                    if isinstance(global_variables[key], dict)and isinstance(value, dict):
                        global_variables[key].update(value)
                    else:
                        global_variables[key]= value
                else:
                    global_variables[key]= value
            logging.info(f"Global settings loaded from {settings_path} (status: {s_status})")
        else:
            logging.warning(f"Global settings in {settings_path} could not be loaded (status: {s_status})")
except Exception as e:
    logging.warning(f"Failed to load global settings: {e}")

def _sync_remote_table():
    try:
        def _parse_table_version(value):
            try:
                parts = re.findall(r"\d+", str(value))
                return tuple(int(part)for part in parts)
            except Exception:
                return ()

        def _pad_version_parts(left, right):
            left_parts = list(left)
            right_parts = list(right)
            length = max(len(left_parts), len(right_parts))
            while len(left_parts)<length:
                left_parts.append(0)
            while len(right_parts)<length:
                right_parts.append(0)
            return tuple(left_parts), tuple(right_parts)

        table_dir = os.path.join(os.getcwd(), "tables")
        if not os.path.isdir(table_dir):
            logging.info("No tables directory present; skipping remote table sync")
            return

        local_tables = sorted(glob.glob(os.path.join("tables", f"*{global_variables.get('table_extension', '.sldtbl')}")))
        if not local_tables:
            logging.info("No local table files found; skipping remote table sync")
            return

        target_local = None
        cur_tbl = global_variables.get("current_table")
        if cur_tbl:
            for table_file in local_tables:
                if os.path.abspath(table_file).endswith(cur_tbl)or os.path.basename(table_file)==cur_tbl:
                    target_local = table_file
                    break

        if not target_local:
            target_local = local_tables[0]

        basename = os.path.basename(target_local)
        raw_base = "https://raw.githubusercontent.com/soli-dstate/DOOM-Tools/master/tables/"
        remote_url = raw_base + basename

        logging.info(f"Checking remote table for updates: {remote_url}")
        resp = requests.get(remote_url, timeout = 15, verify = True)
        if resp.status_code !=200:
            logging.info(f"Remote table not found(status {resp.status_code}): {remote_url}")
            return

        remote_text = resp.text

        import hashlib as _hl
        hash_url = raw_base + basename + ".sha256"
        try:
            hash_resp = requests.get(hash_url, timeout = 15, verify = True)
            if hash_resp.status_code == 200:
                import hmac as _hmac
                expected_hash = hash_resp.text.strip().split()[0].lower()
                actual_hash = _hl.sha256(resp.content).hexdigest().lower()
                if not _hmac.compare_digest(actual_hash, expected_hash):
                    logging.error(f"Remote table integrity check failed for {remote_url} (expected {expected_hash}, got {actual_hash})")
                    return
                logging.info(f"Remote table integrity verified (SHA-256: {actual_hash[:16]}...)")
            else:
                logging.warning(f"No SHA-256 hash file found at {hash_url} — skipping integrity check")
        except Exception as e:
            logging.warning(f"Could not verify remote table integrity: {e}")

        try:
            remote_data = json.loads(remote_text)
        except (json.JSONDecodeError, ValueError):
            logging.error("Remote table is not valid JSON — refusing to overwrite local table")
            return

        remote_version = remote_data.get("version", "0.0.0")if isinstance(remote_data, dict)else "0.0.0"
        remote_version_parts = _parse_table_version(remote_version)

        try:
            with open(target_local, 'r', encoding = 'utf-8')as f:
                local_text = f.read()
        except Exception as e:
            logging.warning(f"Failed to read local table {target_local}: {e}")
            local_text = None

        local_version = "0.0.0"
        local_version_parts = ()
        if local_text is not None:
            try:
                local_data = json.loads(local_text)
                if isinstance(local_data, dict):
                    local_version = local_data.get("version", "0.0.0")
                    local_version_parts = _parse_table_version(local_version)
            except (json.JSONDecodeError, ValueError) as e:
                logging.warning(f"Failed to parse local table JSON for version check: {e}")

        local_version_parts, remote_version_parts = _pad_version_parts(local_version_parts, remote_version_parts)

        if remote_version_parts <=local_version_parts:
            if local_text is not None and local_text !=remote_text:
                logging.info(f"Remote table version {remote_version} is not newer than local version {local_version}; skipping update")
            else:
                logging.info("Local table matches remote; no update needed")
            return

        if local_text is None or local_text !=remote_text:
            if global_variables.get("devmode", {}).get("value", False):
                logging.info("Devmode enabled: remote table differs but will not replace local file")
                return

            name_root, _ = os.path.splitext(basename)
            backup_name = name_root + ".backup"
            backup_path = os.path.join(table_dir, backup_name)
            try:
                if os.path.exists(target_local):
                    shutil.move(target_local, backup_path)
                    logging.info(f"Backed up local table {target_local} -> {backup_path}")

                with open(target_local, 'w', encoding = 'utf-8')as f:
                    f.write(remote_text)
                logging.info(f"Replaced local table with newer remote version {remote_version} (local was {local_version}): {target_local}")
            except Exception as e:
                logging.error(f"Failed to replace local table with remote version: {e}")
        else:
            logging.info("Local table matches remote; no update needed")
    except Exception as e:
        logging.error(f"Error during remote table sync: {e}")

if not global_variables.get("devmode", {}).get("value", False):
    logging.info("Remote table sync active, syncing...")
    _sync_remote_table()
    logging.info("Remote table sync complete.")
else:
    logging.info("Remote table sync active, skipped due to devmode.")

def _platforms_compatible(fplat, tplat, secondary=None):
    try:
        lf = str(fplat).strip().lower() if fplat is not None else ""
        lt = str(tplat).strip().lower() if tplat is not None else ""
        if not lf or not lt:
            return True
        if lf in lt or lt in lf:
            return True
        # Known equivalences between platforms (case-insensitive)
        PLATFORM_EQUIVALENTS = {
            "hk21": {"g3"},
            "g3": {"hk21"},
        }

        if secondary:
            ls = str(secondary).strip().lower()
            if ls and (ls in lf or lf in ls or ls in lt or lt in ls):
                return True

        # Check configured equivalences
        try:
            if lt in PLATFORM_EQUIVALENTS.get(lf, set()):
                return True
            if lf in PLATFORM_EQUIVALENTS.get(lt, set()):
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def validate_table_ids(secondary_platform=None):

    tables_dir = "tables"
    if not os.path.isdir(tables_dir):
        logging.warning(f"Tables directory '{tables_dir}' not found, skipping validation.")
        return

    table_files =[f for f in os.listdir(tables_dir)if f.endswith(".sldtbl") or f.endswith(".disabled")]
    if not table_files:
        logging.info("No table files found to validate.")
        return

    disabled_files = {f for f in table_files if f.endswith(".disabled")}

    global_id_map = {}

    magazine_errors =[]
    magazine_errors_details =[]
    magazine_errors_files =[]
    table_sequence_errors =[]
    table_sequence_details =[]
    table_sequence_errors_files =[]
    ammo_errors =[]
    ammo_errors_details =[]
    ammo_errors_files =[]
    sound_warnings =[]

    referenced_slots = set()
    referenced_slots_by_table = {}
    table_pretty_names = {}
    all_table_items =[]
    table_hardcore = {}

    for table_file in sorted(table_files):
        table_path = os.path.join(tables_dir, table_file)
        try:
            with open(table_path, 'r', encoding = 'utf-8')as f:
                table_data = json.load(f)

            table_name = table_data.get("prettyname", table_file)
            try:
                table_pretty_names[table_file]= table_name
            except Exception:
                pass
            tables = table_data.get("tables", {})

            try:
                table_hardcore[table_file]= bool((table_data.get('additional_settings')or {}).get('hardcore_mode'))
            except Exception:
                table_hardcore[table_file]= False

            try:
                magazine_items =[]
                clip_items = []
                if isinstance(tables, dict):
                    magazine_items = tables.get("magazines", [])or[]
                    clip_items = [m for m in magazine_items if isinstance(m, dict) and m.get("clip_type") and not m.get("firearm")]

                magazine_systems = set()
                for mag in magazine_items:
                    if isinstance(mag, dict):
                        ms = mag.get("magazinesystem")
                        if ms is None:
                            continue
                        if isinstance(ms, list):
                            for m in ms:
                                magazine_systems.add(str(m))
                        else:
                            magazine_systems.add(str(ms))

                for subtable_name_check, items_check in tables.items():
                    if not isinstance(items_check, list):
                        continue
                    for item_check in items_check:
                        if not isinstance(item_check, dict):
                            continue
                        mag_type_check = str(item_check.get("magazinetype", "") or "").strip().lower()
                        subtype_check = str(item_check.get("subtype", "") or "").strip().lower()
                        is_musket = subtype_check == "musket" or "muzzle" in mag_type_check
                        is_en_bloc = "en bloc" in mag_type_check
                        item_calibers = set()
                        for _cal_source in (item_check.get("musket_caliber"), item_check.get("caliber")):
                            if isinstance(_cal_source, list):
                                for _cal in _cal_source:
                                    if _cal is not None and str(_cal).strip():
                                        item_calibers.add(str(_cal).strip().lower())
                            elif _cal_source is not None and str(_cal_source).strip():
                                item_calibers.add(str(_cal_source).strip().lower())

                        if is_musket:
                            if not item_calibers:
                                msg = f"Table '{table_name}': Musket '{item_check.get('name')}'(ID {item_check.get('id')}) is missing 'musket_caliber' or 'caliber'"
                                ammo_errors.append(msg)
                                ammo_errors_files.append(table_file)
                            if "muzzle" not in mag_type_check:
                                msg = f"Table '{table_name}': Musket '{item_check.get('name')}'(ID {item_check.get('id')}) must use a muzzle-loading magazinetype"
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)

                        if item_check.get('accepts_clips'):
                            clip_type = str(item_check.get('clip_type') or '').strip()
                            if not clip_type:
                                msg = f"Table '{table_name}': Firearm '{item_check.get('name')}'(ID {item_check.get('id')}) has 'accepts_clips' but is missing 'clip_type'"
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                            try:
                                clip_cap = int(item_check.get('capacity', 0) or 0)
                            except Exception:
                                clip_cap = 0
                            if 'detachable box' not in mag_type_check and clip_cap <= 0:
                                msg = f"Table '{table_name}': Firearm '{item_check.get('name')}'(ID {item_check.get('id')}) has 'accepts_clips' but is missing a positive 'capacity'"
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                            if clip_type:
                                compatible_clip_found = False
                                for clip_item in clip_items:
                                    if str(clip_item.get('clip_type') or '').strip() != clip_type:
                                        continue
                                    clip_cal_raw = clip_item.get('caliber')
                                    clip_calibers = set()
                                    if isinstance(clip_cal_raw, list):
                                        for _clip_cal in clip_cal_raw:
                                            if _clip_cal is not None and str(_clip_cal).strip():
                                                clip_calibers.add(str(_clip_cal).strip().lower())
                                    elif clip_cal_raw is not None and str(clip_cal_raw).strip():
                                        clip_calibers.add(str(clip_cal_raw).strip().lower())
                                    if item_calibers and clip_calibers and not item_calibers.intersection(clip_calibers):
                                        continue
                                    compatible_clip_found = True
                                    break
                                if not compatible_clip_found:
                                    msg = f"Table '{table_name}': Firearm '{item_check.get('name')}'(ID {item_check.get('id')}) requires clip type '{clip_type}' but no compatible clip item exists in the magazines table"
                                    magazine_errors.append(msg)
                                    magazine_errors_files.append(table_file)

                        if is_en_bloc:
                            f_ms = item_check.get('magazinesystem')
                            if f_ms is None or (isinstance(f_ms, str) and not f_ms.strip()):
                                msg = f"Table '{table_name}': En-bloc firearm '{item_check.get('name')}'(ID {item_check.get('id')}) missing 'magazinesystem' field"
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                            try:
                                en_bloc_cap = int(item_check.get('capacity', 0) or 0)
                            except Exception:
                                en_bloc_cap = 0
                            if en_bloc_cap <= 0:
                                msg = f"Table '{table_name}': En-bloc firearm '{item_check.get('name')}'(ID {item_check.get('id')}) is missing a positive 'capacity'"
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                            if 'bolt_catch' not in item_check:
                                msg = f"Table '{table_name}': En-bloc firearm '{item_check.get('name')}'(ID {item_check.get('id')}) is missing 'bolt_catch'"
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                            needed_en_bloc = [str(f_ms)] if f_ms is not None and not isinstance(f_ms, list) else [str(n) for n in (f_ms or []) if str(n).strip()]
                            if needed_en_bloc:
                                compatible_en_bloc = False
                                for mag in magazine_items:
                                    if not isinstance(mag, dict) or mag.get('firearm'):
                                        continue
                                    ms = mag.get('magazinesystem')
                                    mag_system_values = [str(ms)] if ms is not None and not isinstance(ms, list) else [str(n) for n in (ms or []) if str(n).strip()]
                                    if not any(n in mag_system_values for n in needed_en_bloc):
                                        continue
                                    mag_cal_raw = mag.get('caliber')
                                    mag_calibers = set()
                                    if isinstance(mag_cal_raw, list):
                                        for _mag_cal in mag_cal_raw:
                                            if _mag_cal is not None and str(_mag_cal).strip():
                                                mag_calibers.add(str(_mag_cal).strip().lower())
                                    elif mag_cal_raw is not None and str(mag_cal_raw).strip():
                                        mag_calibers.add(str(mag_cal_raw).strip().lower())
                                    if item_calibers and mag_calibers and not item_calibers.intersection(mag_calibers):
                                        continue
                                    compatible_en_bloc = True
                                    break
                                if not compatible_en_bloc:
                                    msg = f"Table '{table_name}': En-bloc firearm '{item_check.get('name')}'(ID {item_check.get('id')}) has no compatible en-bloc clip item for magazinesystem(s): {needed_en_bloc}"
                                    magazine_errors.append(msg)
                                    magazine_errors_files.append(table_file)

                        if item_check.get("firearm")and str(item_check.get("magazinetype", "")).lower()=="detachable box":
                            f_ms = item_check.get("magazinesystem")
                            friendly = f"Table '{table_name}': Firearm '{item_check.get('name')}'(ID {item_check.get('id')})"

                            if item_check.get('has_magazine_in_pool')is False:
                                continue

                            if f_ms is None:
                                msg = f"{friendly} missing 'magazinesystem' field"
                                logging.error(msg)
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                                try:
                                    magazine_errors_details.append({'table':table_name, 'weapon':item_check, 'reason':'missing_magazinesystem', 'message':msg})
                                except Exception:
                                    pass
                                continue

                            needed =[f_ms]if not isinstance(f_ms, list)else f_ms

                            needed =[str(n)for n in needed]
                            compatible = any(n in magazine_systems for n in needed)
                            if not compatible:
                                msg = f"{friendly} has no magazines matching magazinesystem(s): {needed}"
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                                try:
                                    magazine_errors_details.append({'table':table_name, 'weapon':item_check, 'reason':'no_compatible_magazines', 'message':msg})
                                except Exception:
                                    pass

                        if item_check.get("firearm")and item_check.get("dualfeed")and item_check.get("submagazinesystem"):
                            sub_ms = item_check.get("submagazinesystem")
                            friendly = f"Table '{table_name}': Dualfeed firearm '{item_check.get('name')}'(ID {item_check.get('id')})"
                            sub_needed =[sub_ms]if not isinstance(sub_ms, list)else sub_ms
                            sub_needed =[str(n)for n in sub_needed]
                            sub_compatible = any(n in magazine_systems for n in sub_needed)
                            if not sub_compatible:
                                msg = f"{friendly} has no magazines matching submagazinesystem(s): {sub_needed}"
                                logging.warning(msg)
                                magazine_errors.append(msg)
                                magazine_errors_files.append(table_file)
                                try:
                                    magazine_errors_details.append({'table':table_name, 'weapon':item_check, 'reason':'no_compatible_submagazines', 'message':msg})
                                except Exception:
                                    pass
            except Exception as e:
                logging.warning(f"Failed to perform magazine compatibility check for '{table_file}': {e}")

            file_ids =[]

            for subtable_name, items in tables.items():
                if not isinstance(items, list):
                    continue
                for idx, item in enumerate(items):
                    if isinstance(item, dict)and "id"in item:
                        item_id = item["id"]
                        file_ids.append(item_id)

                        entry =(table_file, subtable_name, item.get("name")or f"index_{idx}")
                        global_id_map.setdefault(item_id, []).append(entry)

                    if isinstance(item, dict):
                        all_table_items.append((item, table_file, subtable_name))

                        try:
                            accs = item.get('accessories')or[]
                            if isinstance(accs, list):
                                for a in accs:
                                    if isinstance(a, dict)and a.get('slot'):
                                                slot_name = str(a.get('slot')).strip()
                                                referenced_slots.add(slot_name)
                                                try:
                                                    referenced_slots_by_table.setdefault(table_file, set()).add(slot_name)
                                                except Exception:
                                                    pass
                        except Exception:
                            pass

                        try:
                            subs = item.get('subslots')or[]
                            if isinstance(subs, list):
                                for s in subs:
                                    if isinstance(s, dict)and s.get('slot'):
                                        slot_name = str(s.get('slot')).strip()
                                        referenced_slots.add(slot_name)
                                        try:
                                            referenced_slots_by_table.setdefault(table_file, set()).add(slot_name)
                                        except Exception:
                                            pass
                        except Exception:
                            pass

            if not file_ids:
                logging.info(f"Table '{table_name}': No items with IDs found.")
                continue

            file_ids.sort()
            min_id = file_ids[0]
            max_id = file_ids[-1]
            next_id = max_id +1

            expected_ids = set(range(min_id, max_id +1))
            actual_ids = set(file_ids)
            if expected_ids ==actual_ids:
                plain = f"Table '{table_name}': IDs valid(sequential from {min_id} to {max_id}).Next ID: {next_id}"
                log_with_colored_substring(logging.getLogger(), logging.INFO, plain, str(next_id), 'blue')
            else:
                missing_ids = sorted(expected_ids -actual_ids)

                logging.error(f"Table '{table_name}': ID sequence broken(details collected for dialog).")

                try:
                    file_entries =[]
                    for iid in sorted(actual_ids):
                        locs = global_id_map.get(iid, [])
                        for f, sub, name in locs:
                            if f ==table_file:
                                file_entries.append((iid, sub, name))
                                break
                    suggested_lines =[]
                    new_id = min_id
                    for old_id, sub, name in file_entries:
                        if old_id !=new_id:
                            suggested_lines.append(f"Change ID {old_id}({sub}:{name}) -> {new_id}")
                        new_id +=1
                except Exception:
                    suggested_lines =["Unable to build suggested ID changes."]

                id_msg_lines =[
                f"Table: {table_name}",
                "ID sequence broken:",
                f" Missing IDs: {missing_ids}",
                f" Last ID: {max_id}",
                f" Next ID: {next_id}",
                ]
                if suggested_lines:
                    id_msg_lines.append("")
                    id_msg_lines.append("Suggested changes to fix IDs:")
                    id_msg_lines.extend([f" {l}"for l in suggested_lines])

                seq_msg = "\n".join(id_msg_lines)
                table_sequence_errors.append(seq_msg)
                table_sequence_errors_files.append(table_file)
                try:
                    table_sequence_details.append({'table':table_name, 'missing_ids':missing_ids, 'last_id':max_id, 'next_id':next_id, 'suggested_changes':suggested_lines})
                except Exception:
                    table_sequence_details.append({'table':table_name, 'message':seq_msg})
                logging.error("Table '%s': ID sequence error detected(collected, continuing checks).", table_name)

        except Exception as e:
            logging.error(f"Failed to validate table '{table_file}': {e}")

    ammo_names_present = set()
    ammo_calibers_present = set()
    try:
        for item, tf, sub in all_table_items:
            try:
                if isinstance(sub, str)and sub.lower()in('ammunition', 'ammo'):
                    name = item.get('name')
                    if name:
                        ammo_names_present.add(str(name).strip().lower())
                    for calib_src in (item.get('caliber'), item.get('musket_caliber')):
                        if isinstance(calib_src, list):
                            for calib in calib_src:
                                if calib is not None and str(calib).strip():
                                    ammo_calibers_present.add(str(calib).strip().lower())
                        elif calib_src is not None and str(calib_src).strip():
                            ammo_calibers_present.add(str(calib_src).strip().lower())
            except Exception:
                continue
    except Exception:
        pass

    hardcore_errors =[]
    hardcore_errors_details =[]
    hardcore_errors_files =[]
    try:
        import copy as _copy

        id_to_item_by_table = {}
        for it, tf, sub in all_table_items:
            try:
                if isinstance(it, dict)and 'id'in it:
                    if tf not in id_to_item_by_table:
                        id_to_item_by_table[tf]= {}
                    id_to_item_by_table[tf][it['id']]= it
            except Exception:
                pass

        try:
            for item, tf, sub in all_table_items:
                try:
                    if not isinstance(item, dict):
                        continue
                    if not table_hardcore.get(tf):
                        continue
                    if not item.get('firearm'):
                        continue

                    fname = item.get('name')or '<unnamed>'
                    fplat = item.get('platform')or ''
                    parts = item.get('parts')or[]
                    for p in parts:
                        try:
                            if not isinstance(p, dict):
                                continue
                            cur = p.get('current')
                            if cur is None:
                                continue

                            target_id = None
                            if isinstance(cur, int):
                                target_id = cur
                            elif isinstance(cur, dict)and 'id'in cur:
                                target_id = cur.get('id')

                            if target_id is None or(isinstance(target_id, str)and str(target_id).strip().lower()=='null'):
                                msg = f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{fname}' has part '{p.get('name')}' with invalid 'current' id: {target_id}"
                                hardcore_errors.append(msg)
                                hardcore_errors_files.append(tf)
                                try:
                                    hardcore_errors_details.append({'table':tf, 'weapon':item, 'part':p, 'reason':'invalid_part_current_id', 'id':target_id})
                                except Exception:
                                    pass
                                continue

                            table_id_map = id_to_item_by_table.get(tf, {})
                            if target_id not in table_id_map:
                                msg = f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{fname}' has part '{p.get('name')}' referencing missing item ID {target_id}"
                                hardcore_errors.append(msg)
                                hardcore_errors_files.append(tf)
                                try:
                                    hardcore_errors_details.append({'table':tf, 'weapon':item, 'part':p, 'reason':'missing_referenced_part', 'id':target_id})
                                except Exception:
                                    pass
                                continue

                            target = table_id_map.get(target_id)or {}
                            tplat =(target.get('platform')or '')
                            try:
                                # Use per-item secondary_platform when available
                                item_secondary = item.get('secondary_platform') if isinstance(item, dict) else None
                                item_secondary = item_secondary or secondary_platform
                                if str(fplat).strip() and str(tplat).strip() and not _platforms_compatible(fplat, tplat, item_secondary):
                                    msg = f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{fname}' part '{p.get('name')}' references item ID {target_id} with platform '{tplat}' which does not match firearm platform '{fplat}'"
                                    hardcore_errors.append(msg)
                                    hardcore_errors_files.append(tf)
                                    try:
                                        hardcore_errors_details.append({'table':tf, 'weapon':item, 'part':p, 'reason':'platform_mismatch', 'weapon_platform':fplat, 'part_platform':tplat, 'id':target_id})
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        def _resolve_current(obj, id_map):
            if not isinstance(obj, dict):
                return

            accs = obj.get('accessories')or[]
            if isinstance(accs, list):
                for acc in accs:
                    try:
                        cur = acc.get('current')
                        if cur is None:
                            continue

                        target_id = None
                        sub_attachment = None
                        overrides = {}

                        if isinstance(cur, int):
                            target_id = cur
                        elif isinstance(cur, dict)and 'id'in cur:
                            target_id = cur.get('id')
                            sub_attachment = cur.get('sub_attachment')
                            for k, v in cur.items():
                                if k not in('id', 'sub_attachment'):
                                    overrides[k]= v

                        if target_id is None:

                            if isinstance(cur, dict):
                                _resolve_current(cur, id_map)
                            continue

                        target = id_map.get(target_id)
                        if not target:
                            continue

                        # Skip resolving to obvious ammunition/magazine entries when
                        # resolving accessories/parts. Ammo entries commonly have
                        # a 'caliber' field and lack 'type'/'slot', which indicates
                        # an ID collision rather than a valid part.
                        try:
                            if isinstance(target, dict) and 'caliber' in target and not target.get('type') and not target.get('slot'):
                                continue
                        except Exception:
                            pass

                        new_installed = _copy.deepcopy(target)

                        for k, v in overrides.items():
                            try:
                                new_installed[k]= v
                            except Exception:
                                pass

                        acc['current']= new_installed

                        if sub_attachment:
                            sub_target = id_map.get(sub_attachment)
                            # don't place ammo into subslots
                            try:
                                if isinstance(sub_target, dict) and 'caliber' in sub_target and not sub_target.get('type') and not sub_target.get('slot'):
                                    sub_target = None
                            except Exception:
                                pass
                            if sub_target and isinstance(new_installed.get('subslots'), list):
                                placed = False
                                for ss in new_installed['subslots']:
                                    try:
                                        ss_slot = ss.get('slot')
                                        if ss_slot ==sub_target.get('slot')or ss.get('current')is None:
                                            ss['current']= _copy.deepcopy(sub_target)
                                            placed = True
                                            break
                                    except Exception:
                                        pass
                                if not placed:
                                    try:
                                        new_installed['subslots'][0]['current']= _copy.deepcopy(sub_target)
                                    except Exception:
                                        pass

                        try:
                            _resolve_current(new_installed, id_map)
                        except Exception:
                            pass
                    except Exception:
                        pass

            subs = obj.get('subslots')or[]
            if isinstance(subs, list):
                for s in subs:
                    try:
                        cur = s.get('current')
                        if cur is None:
                            continue
                        if isinstance(cur, int)or(isinstance(cur, dict)and 'id'in cur):

                            tmp = {'accessories':[{'current':cur}]}
                            _resolve_current(tmp, id_map)

                            try:
                                s['current']= tmp['accessories'][0].get('current')
                            except Exception:
                                pass
                        elif isinstance(cur, dict):
                            _resolve_current(cur, id_map)
                    except Exception:
                        pass

            parts_list = obj.get('parts')or[]
            if isinstance(parts_list, list):
                for p in parts_list:
                    try:
                        if not isinstance(p, dict):
                            continue
                        cur = p.get('current')
                        if cur is None:
                            continue
                        target_id = None
                        overrides = {}
                        if isinstance(cur, int):
                            target_id = cur
                        elif isinstance(cur, dict)and 'id'in cur and 'name'not in cur:
                            target_id = cur.get('id')
                            for k, v in cur.items():
                                if k != 'id':
                                    overrides[k]= v
                        if target_id is None:
                            continue
                        target = id_map.get(target_id)
                        if not target:
                            continue

                        try:
                            if isinstance(target, dict) and 'caliber' in target and not target.get('type') and not target.get('slot'):
                                continue
                        except Exception:
                            pass

                        import copy as _copy_p
                        new_part = _copy_p.deepcopy(target)
                        for k, v in overrides.items():
                            try:
                                new_part[k]= v
                            except Exception:
                                pass
                        p['current']= new_part
                    except Exception:
                        pass

        for item, tf, sub in all_table_items:
            try:
                _resolve_current(item, id_to_item_by_table.get(tf, {}))
            except Exception:
                pass
    except Exception:
        pass

    try:
        for item, tf, sub in all_table_items:
            try:
                if not isinstance(item, dict):
                    continue
                if item.get('firearm'):
                    name = item.get('name')or '<unnamed>'

                    calib = item.get('musket_caliber') or item.get('caliber')
                    if calib:
                        calibs = calib if isinstance(calib, list) else [calib]
                        missing = [c for c in calibs if str(c).strip().lower() not in ammo_calibers_present]
                        if missing:
                            msg = f"Firearm '{name}' in table '{tf}' references caliber '{missing}' but no ammunition with that caliber found."
                            ammo_errors.append(msg)
                            ammo_errors_files.append(tf)
                            try:
                                ammo_errors_details.append({'table':tf, 'weapon':item, 'reason':'missing_ammo_caliber', 'caliber':missing})
                            except Exception:
                                pass

                    ammo_type = item.get('ammo_type')or item.get('ammunition')
                    if ammo_type:
                        if str(ammo_type).strip().lower()not in ammo_names_present:
                            msg = f"Firearm '{name}' in table '{tf}' references ammunition '{ammo_type}' but no matching ammunition entry found."
                            ammo_errors.append(msg)
                            ammo_errors_files.append(tf)
                            try:
                                ammo_errors_details.append({'table':tf, 'weapon':item, 'reason':'missing_ammo_name', 'ammo':ammo_type})
                            except Exception:
                                pass
            except Exception:
                continue
    except Exception:
        pass

    duplicates = {}
    for item_id, locations in global_id_map.items():
        by_file = {}
        for f, sub, name in locations:
            by_file.setdefault(f, []).append((f, sub, name))
        for file_locs in by_file.values():
            if len(file_locs)>1:
                duplicates.setdefault(item_id, []).extend(file_locs)
    duplicate_errors =[]
    duplicate_errors_files =[]

    duplicate_suggestions =[]
    if duplicates:
        for dup_id, locations in duplicates.items():
            loc_str = "; ".join([f"{f}:{sub}:{name}"for f, sub, name in locations])
            msg = f"Duplicate ID detected: {dup_id} used in: {loc_str}"
            duplicate_errors.append(msg)
            duplicate_errors_files.append(locations[0][0] if locations else '')
            try:

                max_id = max(global_id_map.keys())if global_id_map else dup_id
                for idx, (f, sub, name)in enumerate(locations):
                    if idx ==0:

                        continue
                    max_id +=1
                    duplicate_suggestions.append(f"Change ID {dup_id}({f}:{sub}:{name}) -> {max_id}")
            except Exception:
                duplicate_suggestions.append(f"Unable to suggest fixes for duplicate ID {dup_id}.")

    try:
        missing_slots =[]

        try:
            sound_root = os.path.join('sounds', 'firearms', 'weaponsounds')
            for item, tf, sub in all_table_items:
                try:
                    if not isinstance(item, dict):
                        continue
                    if not item.get('firearm'):
                        continue
                    if item.get('ignore_weaponsound_in_log'):
                        continue
                    plat = item.get('platform')
                    if not plat:
                        continue
                    plat_key = str(plat).strip().lower().replace('/', '_')
                    if not plat_key:
                        continue
                    folder = os.path.join(sound_root, plat_key)
                    if not os.path.isdir(folder):
                        msg = f"Table '{table_pretty_names.get(tf, tf)}': Firearm '{item.get('name')}' platform '{plat}' missing weaponsound folder '{folder}'"
                        logging.warning(msg)
                        sound_warnings.append(msg)
                except Exception:
                    pass
        except Exception:
            pass

        def item_matches_slot(item, slot_name):
            try:
                if isinstance(item, (list, tuple))and item:
                    item = item[0]
                if not isinstance(item, dict):
                    return False

                for v in item.values():
                    if isinstance(v, str)and v.strip().lower()==slot_name.lower():
                        return True
                    if isinstance(v, (list, tuple)):
                        for e in v:
                            try:
                                if isinstance(e, str)and e.strip().lower()==slot_name.lower():
                                    return True
                            except Exception:
                                continue

                if isinstance(item.get('slot'), str)and item.get('slot').strip().lower()==slot_name.lower():
                    return True
            except Exception:
                pass
            return False

        for table_file, slots in referenced_slots_by_table.items():
            try:
                if not slots:
                    continue
                table_pretty = None
                try:

                    table_pretty = None
                except Exception:
                    table_pretty = None

                for slot in sorted(slots):
                    try:
                        if isinstance(slot, str)and slot.strip().lower()=='weapon_slot':
                            continue
                    except Exception:
                        pass

                    found = any(item_matches_slot(it, slot)for it, tf, sub in all_table_items if tf ==table_file)
                    if not found:

                        display_table = table_pretty_names.get(table_file, table_file)
                        logging.warning(f"Table '{display_table}' references slot '{slot}' but no items are available in that table to populate it.")
            except Exception:
                pass
    except Exception:
        pass

    try:
        for table_file in sorted(table_files):
            try:
                table_path_sc = os.path.join(tables_dir, table_file)
                with open(table_path_sc, 'r', encoding = 'utf-8') as f_sc:
                    table_data_sc = json.load(f_sc)
                tables_sc = table_data_sc.get("tables", {})
                stores_sc = tables_sc.get("stores", []) or []
                if not stores_sc:
                    continue
                display_table_sc = table_pretty_names.get(table_file, table_file)
                store_item_ids = set()
                store_table_names = set()
                for store_sc in stores_sc:
                    if not isinstance(store_sc, dict):
                        continue
                    for inv_entry in store_sc.get("inventory", []) or []:
                        if not isinstance(inv_entry, dict):
                            continue
                        if inv_entry.get("type") == "table":
                            tname = inv_entry.get("table")
                            if tname:
                                store_table_names.add(tname)
                        elif inv_entry.get("type") == "id":
                            iid = inv_entry.get("id")
                            if iid is not None:
                                store_item_ids.add(iid)
                for sub_name, sub_items in tables_sc.items():
                    if not isinstance(sub_items, list):
                        continue
                    in_store_table = sub_name in store_table_names
                    for item_sc in sub_items:
                        if not isinstance(item_sc, dict):
                            continue
                        in_store = in_store_table or item_sc.get("id") in store_item_ids
                        if in_store and not item_sc.get("shop_category"):
                            item_name_sc = item_sc.get("name") or f"ID {item_sc.get('id', '?')}"
                            logging.warning(f"Table '{display_table_sc}': Item '{item_name_sc}' in subtable '{sub_name}' is referenced by a store but missing 'shop_category' field.")
            except Exception:
                pass
    except Exception:
        pass

    try:
        skip_subtables = {
            'stores', 'armories', 'businesses', 'settings', 'additional_settings',
            'lootcrates', 'enemyloot', 'loot_crates', 'enemy_loot'
        }
        for item_cat, tf_cat, sub_cat in all_table_items:
            try:
                if not isinstance(item_cat, dict):
                    continue
                if sub_cat and str(sub_cat).lower() in skip_subtables:
                    continue
                has_armory = bool(item_cat.get("armory_category"))
                has_shop = bool(item_cat.get("shop_category"))
                if not has_armory and not has_shop:
                    item_name_cat = item_cat.get("name") or f"ID {item_cat.get('id', '?')}"
                    display_table_cat = table_pretty_names.get(tf_cat, tf_cat)
                    logging.warning(f"Table '{display_table_cat}': Item '{item_name_cat}' in subtable '{sub_cat}' is missing both 'armory_category' and 'shop_category' fields.")
            except Exception:
                pass
    except Exception:
        pass

    all_errors_with_source = (
        [(e, f) for e, f in zip(duplicate_errors, duplicate_errors_files)] +
        [(e, f) for e, f in zip(magazine_errors, magazine_errors_files)] +
        [(e, f) for e, f in zip(ammo_errors, ammo_errors_files)] +
        [(e, f) for e, f in zip(table_sequence_errors, table_sequence_errors_files)] +
        [(e, f) for e, f in zip(hardcore_errors, hardcore_errors_files)]
    )
    active_errors = [e for e, f in all_errors_with_source if f not in disabled_files]
    disabled_table_errors = [e for e, f in all_errors_with_source if f in disabled_files]

    if disabled_table_errors:
        for err in disabled_table_errors:
            logging.error(f"[Disabled table] {err}")

        disabled_displayed = disabled_table_errors[:10]
        disabled_numbered =[f"{i +1}. [Disabled table] {e}"for i, e in enumerate(disabled_displayed)]
        disabled_preview = "\n\n".join(disabled_numbered)
        disabled_more = len(disabled_table_errors)-len(disabled_displayed)
        if disabled_more >0:
            disabled_preview +=f"\n\n...and {disabled_more} more errors"
        disabled_title = f"Disabled Table Validation Errors({len(disabled_table_errors)})"
        disabled_msg = f"Errors detected in disabled tables (program will continue):\n\n{disabled_preview}\n\nSee logs for full details."
        show_error_dialog(disabled_title, disabled_msg)

    all_errors = active_errors
    if all_errors:

        for err in all_errors:
            logging.error(err)

        displayed = all_errors[:10]
        numbered =[f"{i +1}.{e}"for i, e in enumerate(displayed)]
        preview = "\n\n".join(numbered)
        more_count = len(all_errors)-len(displayed)
        if more_count >0:
            preview +=f"\n\n...and {more_count} more errors"

        try:
            if duplicate_suggestions:
                preview +="\n\nSuggested duplicate ID fixes:\n"
                preview +="\n".join([f" {s}"for s in duplicate_suggestions])
        except Exception:
            pass
        try:
            if table_sequence_details:
                preview +="\n\nID sequence issues detected in tables:\n"
                for det in table_sequence_details[:8]:
                    try:
                        preview +=f"- Table: {det.get('table')} Missing IDs: {det.get('missing_ids')} Last ID: {det.get('last_id')} Next ID: {det.get('next_id')}\n"
                        sug = det.get('suggested_changes')or[]
                        if sug:
                            preview +=" Suggested changes:\n"
                            for s in sug[:6]:
                                preview +=f" {s}\n"
                            if len(sug)>6:
                                preview +=f"...and {len(sug)-6} more suggested changes\n"
                    except Exception:
                        preview +="-(unable to render table sequence detail)\n"
                if len(table_sequence_details)>8:
                    preview +=f"...and {len(table_sequence_details)-8} more table sequence issues\n"
        except Exception:
            pass

        title = f"Table Validation Errors({len(all_errors)})"
        full_msg = f"Errors detected during table validation:\n\n{preview}\n\nSee logs for full details."
        show_error_dialog(title, full_msg)
        logging.critical("Aborting startup due to table validation errors.")
        raise SystemExit("Format for table tables is broken due to validation errors; aborting startup.Please fix/update the table(s).")

try:
    import argparse
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--secondary-platform', help='Optional secondary platform to allow when checking part compatibility', default=None)
    args, _ = parser.parse_known_args()
    _secondary_platform = args.secondary_platform
except Exception:
    _secondary_platform = None

validate_table_ids(secondary_platform=_secondary_platform)

currentsave = None

emptysave = {
"charactername":"",
"stats":{
"Aim":0,
"Strength":0,
"Agility":0,
"Intelligence":0,
"Charisma":0,
"Perception":0,
"Resistance":0,
"Stealth":0,
"Luck":0
},
"hands":{
"encumbrance_modifier":0.5,
"capacity":50,
"items":[]
},
"equipment":{
"head":None,
"ears":None,
"face":None,
"torso":None,
"left wrist":None,
"right wrist":None,
"left hand":None,
"right hand":None,
"feet":None,
"neck":None,
"chest":None,
"back":None,
"waist":None,
"waistband":None,
"left shoulder":None,
"right shoulder":None,
"left arm":None,
"right arm":None,
"left leg":None,
"right leg":None
},
"encumbrance":0,
"encumbered_threshold":50,
"encumbered":{"value":False, "level":0},
"storage":[],
"money":0
}

def populate_equipment_with_subslots(save_data, secondary_platform=None):

    if secondary_platform is None:
        secondary_platform = globals().get('_secondary_platform')

    try:
        tbl_path = get_current_table_path()
        if not tbl_path or not os.path.exists(tbl_path):
            return save_data

        with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
            table_data = json.load(f)

        tables = table_data.get("tables", {})
        equipment_items = (
            (tables.get("equipment") or []) +
            (tables.get("civilian_equipment") or []) +
            (tables.get("military_equipment") or [])
        )
        equipment_map = {item.get("id"): item for item in equipment_items}

        for slot_name, equipped_item in save_data.get("equipment", {}).items():
            items_to_process = []
            if isinstance(equipped_item, dict):
                items_to_process = [equipped_item]
            elif isinstance(equipped_item, list):
                items_to_process = [it for it in equipped_item if isinstance(it, dict)]

            for eq in items_to_process:
                try:
                    item_id = eq.get("id")
                    if item_id is not None and item_id in equipment_map:
                        table_item = equipment_map[item_id]
                        if "subslots" in table_item and "subslots" not in eq:
                            eq["subslots"] = [{
                                "name": subslot.get("name"),
                                "slot": subslot.get("slot"),
                                "current": None
                            } for subslot in table_item["subslots"]]
                            logging.debug(f"Added {len(eq['subslots'])} subslots to equipped item ID {item_id} in slot {slot_name}")

                        for sub in eq.get("subslots", []):
                            try:
                                cur = sub.get("current")
                                if isinstance(cur, dict):
                                    add_subslots_to_item(cur)
                            except Exception:
                                pass

                        try:
                            for sub in eq.get("subslots", []) or []:
                                try:
                                    s_slot = sub.get('slot')

                                    for candidate in equipment_items:
                                        try:
                                            if isinstance(candidate, dict) and candidate.get('slot') == s_slot and 'subslots' in candidate:
                                                nested = []
                                                for ss in candidate.get('subslots', []) or []:
                                                    try:
                                                        nested.append({'name': ss.get('name'), 'slot': ss.get('slot'), 'current': None})
                                                    except Exception:
                                                        pass
                                                if nested:
                                                    sub.setdefault('subslots', nested)
                                                    logging.debug(f"Added {len(nested)} nested subslots to subslot '{sub.get('name')}' on item ID {item_id}")

                                                    for nsub in sub.get('subslots', []) or []:
                                                        try:
                                                            cur2 = nsub.get('current')
                                                            if isinstance(cur2, dict):
                                                                add_subslots_to_item(cur2)
                                                        except Exception:
                                                            pass
                                                break
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        for acc in eq.get("accessories", []) or []:
                            try:
                                cur = acc.get("current")
                                if isinstance(cur, dict):
                                    add_subslots_to_item(cur)
                            except Exception:
                                pass

                        try:
                            eq.setdefault('accessories', [])
                            for sub in eq.get('subslots', []) or []:
                                try:
                                    s_slot = sub.get('slot')
                                    s_name = sub.get('name') or s_slot
                                    exists = False
                                    for a in eq.get('accessories', []) or []:
                                        try:
                                            if a and isinstance(a, dict) and (a.get('slot') == s_slot or a.get('name') == s_name):
                                                exists = True
                                                break
                                        except Exception:
                                            pass
                                    if not exists:
                                        try:
                                            eq['accessories'].append({'name': s_name, 'slot': s_slot, 'current': sub.get('current'), 'attachment': True})
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                        except Exception:
                            pass
                except Exception:
                    pass

        for item in save_data.get("storage", []):
            if isinstance(item, dict):
                add_subslots_to_item(item)
                for acc in item.get("accessories", [])or[]:
                    try:
                        cur = acc.get("current")
                        if isinstance(cur, dict):
                            _add_attachment_subslots_to_weapon(item, acc, cur)
                    except Exception:
                        pass

        if "hands"in save_data and "items"in save_data["hands"]:
            for item in save_data["hands"]["items"]:
                if isinstance(item, dict):
                    add_subslots_to_item(item)
                    for acc in item.get("accessories", [])or[]:
                        try:
                            cur = acc.get("current")
                            if isinstance(cur, dict):
                                _add_attachment_subslots_to_weapon(item, acc, cur)
                        except Exception:
                            pass

        for slot_name, equipped_item in save_data.get("equipment", {}).items():
            if equipped_item and isinstance(equipped_item, dict):
                for acc in equipped_item.get("accessories", [])or[]:
                    try:
                        cur = acc.get("current")
                        if isinstance(cur, dict):
                            add_subslots_to_item(cur)
                            _add_attachment_subslots_to_weapon(equipped_item, acc, cur)
                    except Exception:
                        pass

        for slot_name, equipped_item in save_data.get("equipment", {}).items():
            if equipped_item and isinstance(equipped_item, dict)and "items"in equipped_item:
                for item in equipped_item["items"]:
                    if isinstance(item, dict):
                        add_subslots_to_item(item)
                        for acc in item.get("accessories", [])or[]:
                            try:
                                cur = acc.get("current")
                                if isinstance(cur, dict):
                                    _add_attachment_subslots_to_weapon(item, acc, cur)
                            except Exception:
                                pass

    except Exception as e:
        logging.warning(f"Failed to populate equipment subslots: {e}")

    return save_data

def _resolve_adapter_output_slot(parent_slot, attachment):
    try:
        if not isinstance(attachment, dict):
            return None
        if not attachment.get('rail_adapter'):
            return None
        adapting_to = str(attachment.get('adapting_to') or '').strip().lower()
        if not adapting_to:
            return None

        pslot = str(parent_slot or '').strip().lower()
        if not pslot:
            return None

        if adapting_to == 'picatinny':
            if 'pistol' in pslot:
                return 'pistol_picatinny'
            if 'bottom' in pslot:
                return 'picatinny_bottom'
            return 'picatinny_rifle'

        return None
    except Exception:
        return None

def _add_attachment_subslots_to_weapon(weapon, parent_accessory, attachment):

    try:
        if not weapon or not isinstance(weapon, dict):
            return
        if not attachment or not isinstance(attachment, dict):
            return

        weapon.setdefault('accessories', [])
        parent_slot = parent_accessory.get('slot')
        attachment_name = attachment.get('name', 'Attachment')

        attachment_subslots = attachment.get('subslots', [])or[]
        if not isinstance(attachment_subslots, list):
            attachment_subslots = []

        try:
            adapted_slot = _resolve_adapter_output_slot(parent_slot, attachment)
            if adapted_slot and not any((isinstance(s, dict) and s.get('slot') == adapted_slot) for s in attachment_subslots):
                adap_to_label = str(attachment.get('adapting_to') or 'Adapter').strip() or 'Adapter'
                attachment_subslots = list(attachment_subslots)
                attachment_subslots.append({
                'name':f"{adap_to_label} Rail",
                'slot':adapted_slot,
                'current':None
                })
        except Exception:
            pass

        if not attachment_subslots:
            return

        for sub in attachment_subslots:
            try:
                s_slot = sub.get('slot')
                s_name = sub.get('name')or s_slot
                display_name = f"{attachment_name} → {s_name}"

                exists = False
                for a in weapon.get('accessories', [])or[]:
                    try:
                        if a and isinstance(a, dict):
                            if a.get('_is_attachment_subslot')and a.get('_parent_accessory_slot')==parent_slot and a.get('_subslot_slot')==s_slot:
                                exists = True
                                a['current']= sub.get('current')
                                a['name']= display_name
                                break
                    except Exception:
                        pass

                if not exists:
                    weapon['accessories'].append({
                    'name':display_name,
                    'slot':s_slot,
                    'current':sub.get('current'),
                    'attachment':True,
                    '_parent_accessory_slot':parent_slot,
                    '_subslot_slot':s_slot,
                    '_is_attachment_subslot':True
                    })
            except Exception:
                pass
    except Exception:
        pass

def add_subslots_to_item(item):

    try:
        return _add_subslots_to_item_recursive(item, seen = None)
    except Exception as e:
        logging.warning(f"Failed to add subslots to item: {e}")
        return item

def _add_subslots_to_item_recursive(item, seen = None):
    if not item or not isinstance(item, dict):
        return item

    if seen is None:
        seen = set()

    obj_id = id(item)
    if obj_id in seen:
        return item
    seen.add(obj_id)

    try:

        if "subslots"not in item:
            table_files = sorted(glob.glob(os.path.join("tables", f"*{global_variables.get('table_extension', '.sldtbl')}")))
            if table_files:
                item_id = item.get("id")
                if item_id is not None:
                    found = False
                    for tf in table_files:
                        try:
                            with open(tf, 'r', encoding = 'utf-8')as f:
                                table_data = json.load(f)
                        except Exception:
                            continue
                        tables = table_data.get("tables", {})
                        for tbl_items in tables.values():
                            if not isinstance(tbl_items, list):
                                continue
                            for it in tbl_items:
                                try:
                                    if isinstance(it, dict)and it.get("id")==item_id:
                                        table_item = it
                                        if "subslots"in table_item:

                                            resolved_subslots =[]
                                            for subslot in table_item["subslots"]:
                                                cur = subslot.get("current", None)
                                                resolved_cur = cur
                                                if cur is not None and(isinstance(cur, int)or(isinstance(cur, str)and str(cur).isdigit())):
                                                    try:
                                                        iid = int(cur)

                                                        for _tf in table_files:
                                                            try:
                                                                with open(_tf, 'r', encoding = 'utf-8')as _f:
                                                                    _td = json.load(_f)
                                                            except Exception:
                                                                continue
                                                            for arr in _td.get('tables', {}).values():
                                                                if isinstance(arr, list):
                                                                    for candidate in arr:
                                                                        if isinstance(candidate, dict)and candidate.get('id')==iid:
                                                                            resolved_cur = candidate.copy()
                                                                            break
                                                                    if isinstance(resolved_cur, dict):
                                                                        break
                                                            if isinstance(resolved_cur, dict):
                                                                break
                                                    except Exception:
                                                        resolved_cur = cur

                                                current_val = resolved_cur if isinstance(resolved_cur, dict)else None

                                                resolved_subslots.append({
                                                "name":subslot.get("name"),
                                                "slot":subslot.get("slot"),
                                                "current":current_val
                                                })

                                            try:
                                                if isinstance(item, dict):
                                                    item.setdefault('accessories', [])
                                                    for sub in resolved_subslots:
                                                        try:
                                                            s_slot = sub.get('slot')
                                                            s_name = sub.get('name')or s_slot
                                                            found = False
                                                            for a in item.get('accessories', [])or[]:
                                                                try:
                                                                    if a and isinstance(a, dict)and(a.get('slot')==s_slot or a.get('name')==s_name):
                                                                        found = True
                                                                        break
                                                                except Exception:
                                                                    pass
                                                            if not found:
                                                                try:
                                                                    item['accessories'].append({'name':s_name, 'slot':s_slot, 'current':None, 'attachment':True})
                                                                except Exception:
                                                                    pass
                                                        except Exception:
                                                            pass
                                            except Exception:
                                                pass
                                            item["subslots"]= resolved_subslots
                                            logging.debug(f"Added {len(item['subslots'])} subslots to item ID {item_id}({item.get('name')})")
                                        found = True
                                        break
                                except Exception:
                                    continue
                            if found:
                                break
                        if found:
                            break
    except Exception:
        pass

    try:

        for sub in item.get("items", [])or[]:
            try:
                if isinstance(sub, dict):
                    _add_subslots_to_item_recursive(sub, seen)
            except Exception:
                pass

        for subslot in item.get("subslots", [])or[]:
            try:
                cur = subslot.get("current")
                if isinstance(cur, dict):
                    _add_subslots_to_item_recursive(cur, seen)
            except Exception:
                pass

        for acc in item.get("accessories", [])or[]:
            try:
                cur = acc.get("current")
                if isinstance(cur, dict):
                    _add_subslots_to_item_recursive(cur, seen)
            except Exception:
                pass
    except Exception:
        pass

    return item

def update_item_keys_from_table(save_data):

    try:
        table_files = sorted(glob.glob(os.path.join("tables", f"*{global_variables.get('table_extension', '.sldtbl')}")))
        if not table_files:
            logging.warning("No table files found for item key update")
            return save_data

        cur_tbl = global_variables.get("current_table")
        target_file = None
        if cur_tbl:
            for fpath in table_files:
                if os.path.abspath(fpath).endswith(cur_tbl)or os.path.basename(fpath)==cur_tbl:
                    target_file = fpath
                    break

        if not target_file:
            target_file = table_files[0]

        try:
            with open(target_file, 'r', encoding = 'utf-8')as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table file for item key update: {target_file}: {e}")
            return save_data

        all_items_map = {}
        for table_name, items in table_data.get("tables", {}).items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict)and "id"in item:
                        all_items_map[item["id"]]= item

        variable_keys = {
        "quantity", "current", "items", "subslots", "uses_left", "hits_left",
        "battery_life", "loaded", "chambered", "rounds",
        "accessories", "attachment", "parts", "current_durability", "spring_durability"
        }

        changed_any = False

        def update_item(item):
            nonlocal changed_any
            """Update a single item's keys from table"""
            if not isinstance(item, dict)or "id"not in item:
                return item

            item_id = item.get("id")
            if item_id not in all_items_map:
                return item

            table_item = all_items_map[item_id]

            preserved_data = {key:item[key]for key in variable_keys if key in item}

            synced_keys =[]
            for key, value in table_item.items():
                if key in variable_keys:
                    continue
                if isinstance(key, str)and key.startswith("_"):
                    continue

                local_val = item.get(key, None)
                try:
                    different = local_val !=value
                except Exception:
                    different = True

                if different:
                    item[key]= value
                    synced_keys.append(key)

            if synced_keys:
                logging.info(f"Updated item id={item_id} name={item.get('name', '<unknown>')} keys_synced={synced_keys}")
                changed_any = True

            for key, value in preserved_data.items():
                item[key]= value

            if item.get("subslots"):
                for subslot in item["subslots"]:
                    if isinstance(subslot, dict)and subslot.get("current"):
                        update_item(subslot["current"])

            if "items"in item and isinstance(item["items"], list):
                for contained_item in item["items"]:
                    update_item(contained_item)

            return item

        for item in save_data.get("storage", []):
            update_item(item)

        if "hands"in save_data and "items"in save_data["hands"]:
            for item in save_data["hands"]["items"]:
                update_item(item)

        for slot_name, equipped_item in save_data.get("equipment", {}).items():
            if isinstance(equipped_item, dict):
                update_item(equipped_item)
            elif isinstance(equipped_item, list):
                for it in equipped_item:
                    if isinstance(it, dict):
                        update_item(it)

        if changed_any:
            logging.info(f"Item keys successfully synced from table {os.path.join('tables', os.path.basename(target_file))}")
        else:
            logging.info(f"Item keys updated from table data: no changes detected in {os.path.join('tables', os.path.basename(target_file))}")

    except Exception as e:
        logging.error(f"Failed to update item keys from table: {e}")

    return save_data

persistentdata = {
"last_loaded_save":None,
"save_uuids":{},
"lootcrate_uuids":{},
"transfer_uuids":{},
"reporter_name":None
}

ATTACHMENTS_VERSION = 0

import getpass as _getpass
_current_login = _getpass.getuser().lower()

for user in dm_users:
    if _current_login == user.lower():
        if not global_variables["dmmode"]["value"] and not global_variables["dmmode"]["forced"]:
            global_variables["dmmode"]["value"] = True
            logging.info(f"DM user '{user}' detected. DM mode toggled on.")
        elif global_variables["dmmode"]["value"]:
            logging.info(f"DM user '{user}' detected. DM mode already active.")
        else:
            logging.info(f"DM user '{user}' detected. DM mode is forced off.")
    else:
        logging.debug(f"Current login '{_current_login}' does not match DM user '{user}'.")

        def _console_command_loop():
            try:
                log_console_colored(logging.getLogger(), logging.INFO, "Console command thread started.Type 'help' for commands.", 'cyan')
            except Exception:
                pass

            import ast
            import copy

            ALLOWED_FUNCS = {
            'len':len, 'str':str, 'int':int, 'float':float, 'bool':bool,
            'sum':sum, 'min':min, 'max':max, 'sorted':sorted, 'repr':repr,
            }

            SAFE_ATTRS = frozenset({'get', 'keys', 'values', 'items', 'copy', 'count', 'index', 'upper', 'lower', 'strip', 'split', 'join', 'startswith', 'endswith', 'replace', 'format'})

            ALLOWED_NAMES = {
            'dm_users':list(dm_users),
            'global_variables':copy.deepcopy(global_variables),
            }

            ALLOWED_NODE_TYPES =(
            ast.Expression, ast.Tuple, ast.List, ast.Dict, ast.Set,
            ast.Load, ast.Constant, ast.BinOp, ast.UnaryOp, ast.BoolOp,
            ast.Compare, ast.IfExp, ast.Subscript, ast.Slice, ast.Index,
            ast.Name, ast.Call, ast.Attribute, ast.ListComp, ast.DictComp,
            ast.comprehension
            )

            def _is_ast_safe(node):

                if not isinstance(node, ALLOWED_NODE_TYPES):
                    return False
                if isinstance(node, ast.Attribute):
                    if node.attr not in SAFE_ATTRS:
                        return False
                    if node.attr.startswith('_'):
                        return False
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.Name):
                        if child.id in('True', 'False', 'None'):
                            continue
                        if child.id not in ALLOWED_NAMES and child.id not in ALLOWED_FUNCS:
                            return False
                    if isinstance(child, ast.Call):

                        func = child.func
                        if isinstance(func, ast.Name):
                            if func.id not in ALLOWED_FUNCS:
                                return False
                        elif isinstance(func, ast.Attribute):

                            value = func.value
                            if not(isinstance(value, ast.Name)and value.id in ALLOWED_FUNCS):
                                return False
                        else:
                            return False
                    if not _is_ast_safe(child):
                        return False
                return True

            def safe_eval(expr:str):
                try:
                    parsed = ast.parse(expr, mode = 'eval')
                except Exception as e:
                    raise ValueError(f"Invalid expression: {e}")
                if not _is_ast_safe(parsed):
                    raise ValueError("Expression contains disallowed operations or names")
                env = {}
                env.update(ALLOWED_FUNCS)
                env.update(ALLOWED_NAMES)
                return eval(compile(parsed, '<safe_eval>', 'eval'), {'__builtins__':{}}, env)

            while True:
                try:
                    try:

                        prompt = f"{os.getlogin()}:~ "
                        try:
                            cmd = input(prompt)
                        except EOFError:
                            # Use Event.wait not time.sleep — safer in Python 3.13t
                            threading.Event().wait(0.25)
                            continue
                        except Exception:
                            logging.exception('Console input error')
                            continue
                    except Exception:
                        logging.exception('Console prompt error')
                    if not cmd:
                        continue
                    cmd = cmd.strip()
                    dev_ok = bool(global_variables.get('devmode', {}).get('value'))or bool(global_variables.get('devmode', {}).get('forced'))
                    if not dev_ok:
                        log_console_colored(logging.getLogger(), logging.WARNING, "Console commands are disabled(devmode off).", 'yellow')
                        continue

                    lower = cmd.lower()
                    if lower in('help', '?'):
                        out = "Commands: help, print dm users, print globals, print global <key>, print inventory value, gil, exit, pause <secs>, eval <expr>, crash"
                        log_console_colored(logging.getLogger(), logging.INFO, out, 'green')
                        continue

                    if lower in('crash', 'force crash', 'test crash'):
                        log_console_colored(logging.getLogger(), logging.WARNING, "Forcing a hard crash now(skipping clean shutdown) to test crash reporting...", 'red')
                        os._exit(1)

                    if lower in('print dm users', 'print dm_users', 'print dmusers'):
                        try:
                            log_console_colored(logging.getLogger(), logging.INFO, f"dm_users(decoded): {dm_users}", 'cyan')
                        except Exception:
                            logging.exception('Failed to print dm_users')
                        continue

                    if lower in('print globals', 'print global_variables'):
                        try:
                            safe = json.dumps(global_variables, indent = 2, default = str)
                            log_console_colored(logging.getLogger(), logging.INFO, safe, 'cyan')
                        except Exception:
                            logging.exception('Failed to print global_variables')
                        continue

                    if lower =='gil':
                        try:
                            is_gil_fn = getattr(sys, '_is_gil_enabled', None)# type: ignore
                            if callable(is_gil_fn):
                                try:
                                    gil_enabled = bool(is_gil_fn())
                                    if gil_enabled:
                                        log_console_colored(logging.getLogger(), logging.INFO, "GIL is enabled(sys._is_gil_enabled() returned True)", 'cyan')
                                    else:
                                        log_console_colored(logging.getLogger(), logging.INFO, "GIL is disabled(sys._is_gil_enabled() returned False)", 'yellow')
                                except Exception:
                                    logging.exception('sys._is_gil_enabled() raised an exception')
                            else:

                                impl = platform.python_implementation()
                                gil_enabled =(impl =='CPython')
                                if gil_enabled:
                                    log_console_colored(logging.getLogger(), logging.INFO, f"GIL is likely enabled(implementation: {impl})", 'cyan')
                                else:
                                    log_console_colored(logging.getLogger(), logging.INFO, f"GIL is likely not present(implementation: {impl})", 'yellow')
                        except Exception:
                            logging.exception('Failed to check GIL')
                        continue

                    if lower.startswith('print global '):
                        key = cmd[len('print global '):].strip()
                        try:
                            val = global_variables.get(key)
                            log_console_colored(logging.getLogger(), logging.INFO, f"global {key}: {val}", 'cyan')
                        except Exception:
                            logging.exception('Failed to print global %s', key)
                        continue

                    if lower in('print inventory value', 'print inv value', 'inventory value', 'inv value'):
                        try:
                            app_obj = globals().get('app')
                            if not app_obj or not getattr(app_obj, 'currentsave', None):
                                log_console_colored(logging.getLogger(), logging.WARNING, "No character/save is currently loaded.", 'yellow')
                                continue
                            save_data = app_obj._load_file((app_obj.currentsave or "")+".sldsv")
                            if not isinstance(save_data, dict):
                                log_console_colored(logging.getLogger(), logging.WARNING, "Failed to load the current save data.", 'yellow')
                                continue

                            seen_nodes = set()

                            def _sum_item_value(node):
                                # Recursively sum base value * quantity for an item and
                                # everything installed/stored inside it (items, subslots,
                                # accessories, parts), counting each node only once.
                                if not isinstance(node, dict):
                                    return 0.0
                                nid = id(node)
                                if nid in seen_nodes:
                                    return 0.0
                                seen_nodes.add(nid)
                                try:
                                    qty = max(1, int(node.get("quantity", 1) or 1))
                                except Exception:
                                    qty = 1
                                try:
                                    base = float(node.get("value", 0) or 0)
                                except Exception:
                                    base = 0.0
                                total = base * qty
                                for child in node.get("items", []) or []:
                                    total += _sum_item_value(child)
                                for field in("subslots", "accessories", "parts"):
                                    for entry in node.get(field, []) or []:
                                        if isinstance(entry, dict):
                                            total += _sum_item_value(entry.get("current"))
                                return total

                            carried_value = 0.0
                            hands = save_data.get("hands", {})
                            if isinstance(hands, dict):
                                for it in hands.get("items", []) or []:
                                    carried_value += _sum_item_value(it)
                            for _slot, eq_item in(save_data.get("equipment", {}) or {}).items():
                                if isinstance(eq_item, dict):
                                    carried_value += _sum_item_value(eq_item)
                                elif isinstance(eq_item, list):
                                    for it in eq_item:
                                        carried_value += _sum_item_value(it)

                            storage_value = 0.0
                            for st_item in save_data.get("storage", []) or []:
                                storage_value += _sum_item_value(st_item)

                            try:
                                money = float(save_data.get("money", 0) or 0)
                            except Exception:
                                money = 0.0

                            # Best-store depreciated sale value: what the player would
                            # actually receive selling their sellable items to whichever
                            # regular store buys at the highest rate, after wear/rarity
                            # depreciation and live market demand.
                            table_data_obj = globals().get('table_data') or {}
                            best_buy_mult = 0.0
                            best_store_name = None
                            try:
                                for store in((table_data_obj.get("tables", {}) or {}).get("stores", []) or []):
                                    if not isinstance(store, dict):
                                        continue
                                    if store.get("type") != "store" or not store.get("display_in_program", True):
                                        continue
                                    try:
                                        bm = float((store.get("prices", {}) or {}).get("buy", 1.0) or 0.0)
                                    except Exception:
                                        bm = 0.0
                                    if bm > best_buy_mult:
                                        best_buy_mult = bm
                                        best_store_name = store.get("name", "Unknown Store")
                            except Exception:
                                logging.exception('Failed to resolve best buying store')

                            sale_value = 0.0
                            if best_buy_mult > 0:
                                try:
                                    market_demand = _get_market_demand()
                                except Exception:
                                    market_demand = {}

                                def _iter_sellable(sd):
                                    # Mirror the store sell tab's get_all_player_items: only
                                    # the top-level items inside containers are sellable; their
                                    # installed components are folded into each item's value.
                                    out = []
                                    h = sd.get("hands", {})
                                    if isinstance(h, dict):
                                        for it in h.get("items", []) or []:
                                            if isinstance(it, dict):
                                                out.append(it)
                                    for _sn, eq in(sd.get("equipment", {}) or {}).items():
                                        slot_items = eq if isinstance(eq, list) else [eq]
                                        for slot_item in slot_items:
                                            if not isinstance(slot_item, dict):
                                                continue
                                            if "items" in slot_item and "capacity" in slot_item:
                                                for it in slot_item.get("items", []) or []:
                                                    if isinstance(it, dict):
                                                        out.append(it)
                                            for sub in slot_item.get("subslots", []) or []:
                                                sub_cur = sub.get("current") if isinstance(sub, dict) else None
                                                if isinstance(sub_cur, dict) and "items" in sub_cur:
                                                    for it in sub_cur.get("items", []) or []:
                                                        if isinstance(it, dict):
                                                            out.append(it)
                                    return out

                                for item in _iter_sellable(save_data):
                                    if item.get("_from_armory"):
                                        continue
                                    try:
                                        base_value = app_obj._compute_item_value_with_installed_components(item)
                                        effective_value = _apply_sale_modifiers(base_value, item, table_data_obj)
                                        price = effective_value * best_buy_mult * _get_item_market_multiplier(item, market_demand)
                                        if item.get("firearm") and float(item.get("rounds_fired", 0) or 0) > 0:
                                            price = max(100, price)
                                        sale_value += price
                                    except Exception:
                                        continue

                            grand_total = carried_value + storage_value + money
                            item_count = len(seen_nodes)
                            if best_buy_mult > 0:
                                sale_repr = f"{format_price(round(sale_value, 2))} (sold to '{best_store_name}' @ {best_buy_mult}x)"
                            else:
                                sale_repr = "n/a (no buying store in table)"
                            log_console_colored(
                                logging.getLogger(), logging.INFO,
                                f"Inventory value for '{app_obj.currentsave}' ({item_count} item(s)): "
                                f"carried {format_price(round(carried_value, 2))} | "
                                f"storage {format_price(round(storage_value, 2))} | "
                                f"money {format_price(round(money, 2))} | "
                                f"total {format_price(round(grand_total, 2))} | "
                                f"best sale value {sale_repr}",
                                'green'
                            )
                        except Exception:
                            logging.exception('Failed to compute inventory value')
                        continue

                    if lower in('exit', 'quit'):
                        try:
                            log_console_colored(logging.getLogger(), logging.INFO, 'Exit requested from console — attempting graceful shutdown', 'green')
                        except Exception:
                            pass
                        try:

                            app_obj = globals().get('app')
                            if app_obj and hasattr(app_obj, '_safe_exit'):
                                try:
                                    app_obj._safe_exit()
                                except Exception:
                                    logging.exception('App._safe_exit() raised an exception')

                                time.sleep(0.25)
                                if 'os'in globals():
                                    globals()['os']._exit(0)
                                else:
                                    import os as _os
                                    _os._exit(0)
                            else:

                                safe_fn = globals().get('safe_exit')or globals().get('_safe_exit')
                                if callable(safe_fn):
                                    try:
                                        safe_fn()
                                    except Exception:
                                        logging.exception('Module-level safe exit raised an exception')
                                    time.sleep(0.25)
                                    if 'os'in globals():
                                        globals()['os']._exit(0)
                                    else:
                                        import os as _os
                                        _os._exit(0)
                                else:

                                    if 'os'in globals():
                                        globals()['os']._exit(0)
                                    else:
                                        import os as _os
                                        _os._exit(0)
                        except Exception:
                            try:
                                import sys
                                sys.exit(0)
                            except Exception:
                                return

                    if lower.startswith('pause ')or lower.startswith('sleep '):
                        try:
                            parts = cmd.split()
                            secs = float(parts[1])if len(parts)>1 else 1.0
                            log_console_colored(logging.getLogger(), logging.INFO, f'Pausing for {secs} seconds', 'green')
                            time.sleep(max(0.0, secs))
                        except Exception:
                            log_console_colored(logging.getLogger(), logging.WARNING, 'Usage: pause <seconds>', 'yellow')
                        continue

                    if lower.startswith('eval '):
                        expr = cmd[len('eval '):].strip()
                        try:
                            res = safe_eval(expr)
                            log_console_colored(logging.getLogger(), logging.INFO, f"=> {repr(res)}", 'cyan')
                        except Exception as e:
                            log_console_colored(logging.getLogger(), logging.WARNING, f"Eval error: {e}", 'yellow')
                        continue

                    try:
                        res = safe_eval(cmd)
                        log_console_colored(logging.getLogger(), logging.INFO, f"=> {repr(res)}", 'cyan')
                        continue
                    except Exception:
                        pass

                    log_console_colored(logging.getLogger(), logging.WARNING, f"Unknown or disallowed command: {cmd}", 'yellow')

                except Exception:
                    try:
                        logging.exception('Console command loop error')
                    except Exception:
                        pass

        try:
            t = threading.Thread(target = _console_command_loop, daemon = True)
            t.start()
        except Exception:
            logging.exception('Failed to start console command thread')

def send_windows_notification(title:str, message:str):

    if os.name !='nt':
        return
    try:
        from winotify import Notification, audio
        global version
        toast = Notification(
        app_id = f"DOOM Tools {version}",
        title = title,
        msg = message,
        duration = "short"
        )
        toast.set_audio(audio.Default, loop = False)
        toast.show()
    except ImportError:
        try:
            ps_script = f'''
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]| Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]| Out-Null
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
            $toast =[Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("DOOM-Tools").Show($toast)
            '''
            subprocess.run(['powershell', '-Command', ps_script], capture_output = True)
        except Exception:
            pass

def _resolve_effective_cyclic(weapon, combat_state=None, default=600):
    raw = weapon.get("cyclic", default) if weapon else default
    if isinstance(raw, list) and raw:
        idx = 0
        if combat_state is not None:
            gas_settings = combat_state.get("gas_setting", {})
            weapon_id = str(weapon.get("id", ""))
            idx = gas_settings.get(weapon_id, 0)
        if idx < 0 or idx >= len(raw):
            idx = 0
        val = raw[idx]
        try:
            return float(val) if val else float(default)
        except Exception:
            return float(default)
    try:
        return float(raw) if raw else float(default) # type: ignore
    except Exception:
        return float(default)

PART_DURABILITY_MAX = 1000
PART_DURABILITY_PER_SHOT = {
    "barrel": 0.15,
    "trigger_spring": 0.08,
    "recoil_spring": 0.12,
    "gas_piston": 0.10,
    "bolt_carrier_group": 0.10,
    "feed_tray": 0.06,
    "buffer_spring": 0.10,
    "bolt": 0.08,
}
PART_WRONG_AMMO_MULTIPLIER = {
    "barrel": 8.0,
    "bolt_carrier_group": 6.0,
    "bolt": 5.0,
}
PART_WRONG_AMMO_BREAK_CHANCE = {
    "barrel": 0.005,
    "bolt_carrier_group": 0.008,
    "bolt": 0.006,
}

def _parse_caliber_diameter_mm(caliber_str):
    if not caliber_str or not isinstance(caliber_str, str):
        return None
    import re as _re_cal, math as _math_cal
    s = caliber_str.strip()
    gauge_match = _re_cal.match(r'^(\d+)\s*gauge', s, _re_cal.IGNORECASE)
    if gauge_match:
        gauge = int(gauge_match.group(1))
        if gauge <= 0:
            return None
        mass_g = 453.592 / gauge
        vol_cm3 = mass_g / 11.34
        radius_cm = (3.0 * vol_cm3 / (4.0 * _math_cal.pi)) ** (1.0 / 3.0)
        return round(2.0 * radius_cm * 10.0, 3)
    metric_match = _re_cal.search(r'(\d+\.?\d*)\s*x\s*\d+', s, _re_cal.IGNORECASE)
    if metric_match:
        return float(metric_match.group(1))
    imp_match = _re_cal.match(r'^\.(\d+)', s)
    if imp_match:
        diameter_in = float('0.' + imp_match.group(1))
        return round(diameter_in * 25.4, 3)
    metric_ish = _re_cal.match(r'^(\d+\.?\d*)\s+[A-Za-z]', s)
    if metric_ish:
        val = float(metric_ish.group(1))
        if 1.0 < val < 30.0:
            return val
    return None

def _get_caliber_mismatched_parts(weapon):
    try:
        _tbl_cfg = globals().get("table_data", {})
        if isinstance(_tbl_cfg, dict):
            _add = _tbl_cfg.get("additional_settings") or {}
            if isinstance(_add, dict) and _add.get("hardcore_require_same_parts_for_caliber") is False:
                return set()
    except Exception:
        pass

    mismatched = set()
    weapon_calibers = weapon.get("caliber") or []
    if isinstance(weapon_calibers, str):
        weapon_calibers = [weapon_calibers]
    if not weapon_calibers:
        return mismatched
    weapon_cal_lower = {c.lower() for c in weapon_calibers if isinstance(c, str)}
    parts = weapon.get("parts") or []
    for p in parts:
        if not isinstance(p, dict):
            continue
        cur = p.get("current")
        if not isinstance(cur, dict):
            continue
        part_calibers = cur.get("caliber")
        if not part_calibers:
            continue
        if isinstance(part_calibers, str):
            part_calibers = [part_calibers]
        part_cal_lower = {c.lower() for c in part_calibers if isinstance(c, str)}
        if part_cal_lower and not part_cal_lower.intersection(weapon_cal_lower):
            mismatched.add(id(p))
    return mismatched

def _get_part_by_type(weapon, part_type):
    parts = weapon.get("parts") or []
    for p in parts:
        if isinstance(p, dict) and p.get("type") == part_type:
            return p
    return None

def _check_part_status(weapon, part_type):
    part = _get_part_by_type(weapon, part_type)
    if part is None:
        return "missing"
    dur = part.get("current_durability")
    if dur is None or dur == "null":
        return "ok"
    try:
        dur = float(dur)
    except (ValueError, TypeError):
        return "ok"
    if dur <= 0:
        return "worn"
    return "ok"

def _apply_part_wear(weapon, shots_fired=1, wrong_ammo=False):
    parts = weapon.get("parts")
    if not parts or not isinstance(parts, list):
        return []
    broken_parts = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        ptype = p.get("type", "")
        dur = p.get("current_durability")
        if dur is None or dur == "null":
            continue
        try:
            dur = float(dur)
        except (ValueError, TypeError):
            continue
        if dur <= 0:
            continue
        wear = PART_DURABILITY_PER_SHOT.get(ptype, 0.1) * shots_fired
        if wrong_ammo:
            mult = PART_WRONG_AMMO_MULTIPLIER.get(ptype, 1.0)
            wear *= mult
            break_chance = PART_WRONG_AMMO_BREAK_CHANCE.get(ptype, 0.0)
            if break_chance > 0 and random.random() < break_chance * shots_fired:
                p["current_durability"] = 0
                p["broken"] = True
                broken_parts.append(p)
                continue
        dur = max(0, dur - wear)
        p["current_durability"] = dur
        if dur <= 0:
            broken_parts.append(p)
    return broken_parts

RARITY_SALE_MULTIPLIERS = {
    "Common": 1.0,
    "Uncommon": 1.25,
    "Rare": 1.5,
    "Legendary": 2.5,
    "Mythic": 4.0,
}

RARITY_SALE_ALIASES = {
    "normal": "Common",
    "uncommon": "Uncommon",
    "rare": "Rare",
    "legendary": "Legendary",
    "mythic": "Mythic",
    "epic": "Legendary",
    "very rare": "Legendary",
}

def _normalize_rarity_name(rarity, default = "Common"):
    if rarity is None:
        return default
    txt = str(rarity).strip()
    if not txt:
        return default
    key = txt.lower()
    if key in RARITY_SALE_ALIASES:
        return RARITY_SALE_ALIASES[key]
    for known in RARITY_SALE_MULTIPLIERS.keys():
        if key == known.lower():
            return known
    return txt

def _rarity_sale_multiplier(rarity):
    return _safe_float(RARITY_SALE_MULTIPLIERS.get(_normalize_rarity_name(rarity), 1.0), 1.0) or 1.0

def _cc_item_price(item, apply_firearm_modifiers = True):
    """Budget price for character creation: base value × rarity multiplier (no market demand)."""
    base = float(item.get("value", 0) or 0)
    rarity = _normalize_rarity_name(item.get("rarity") or "Common")
    mult = _rarity_sale_multiplier(rarity)
    value = base * mult
    if apply_firearm_modifiers:
        value = _apply_firearm_round_wear_to_value(value, item)
    return round(value, 2)

def _safe_float(val, default = None):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def _get_ammo_variant_labels(variant_info):
    labels = []
    if not isinstance(variant_info, dict):
        return labels

    dirtiness_modifier = _safe_float(variant_info.get("dirtiness_modifier"), 1.0)
    if dirtiness_modifier is not None and dirtiness_modifier > 1.0:
        labels.append("Corrosive")

    usable_casing_chance = _safe_float(variant_info.get("usable_casing_chance"), None)
    if usable_casing_chance is not None and abs(usable_casing_chance - 10.0) < 1e-9:
        labels.append("Steel Case")

    return labels

def _apply_ammo_variant_data(item_obj, ammo_def = None, variant_info = None):
    if not isinstance(item_obj, dict) or not isinstance(variant_info, dict):
        return item_obj

    for key in [
        "type", "pen", "modifiers", "tip", "lead_free", "jam_modifier",
        "price_modifier", "usable_casing_chance", "dirtiness_modifier"
    ]:
        if key in variant_info:
            item_obj[key] = variant_info.get(key)

    if variant_info.get("pressure_override"):
        item_obj["pressure"] = variant_info.get("pressure_override")

    rarity_val = variant_info.get("rarity") or item_obj.get("rarity")
    if not rarity_val and isinstance(ammo_def, dict):
        rarity_val = ammo_def.get("rarity")
    item_obj["rarity"] = _normalize_rarity_name(rarity_val or "Common")

    labels = _get_ammo_variant_labels(variant_info)
    if labels:
        item_obj["ammo_labels"] = labels
    item_obj["corrosive"] = "Corrosive" in labels
    if "Steel Case" in labels:
        item_obj["casing_material"] = "Steel"

    base_value = _safe_float(item_obj.get("value"), None)
    if base_value is None and isinstance(ammo_def, dict):
        base_value = _safe_float(ammo_def.get("value"), 0.0)
    if base_value is not None:
        price_modifier = _safe_float(variant_info.get("price_modifier"), 1.0) or 1.0
        rarity_mult = _rarity_sale_multiplier(item_obj.get("rarity") or "Common")
        item_obj["value"] = max(0.01, float(base_value) * price_modifier * rarity_mult)

    return item_obj

def _get_weapon_caliber_family(caliber, all_tables):
    """Return the set of calibers that co-occur with *caliber* in any weapon entry.

    Used by the ammo-order system to discover 'military-equivalent' calibers
    without a hardcoded lookup table.  E.g. requesting "9x19mm Parabellum"
    returns {"9x19mm Parabellum", "9x19mm NATO"} because weapons in the table
    accept both.
    """
    family = {caliber}
    for table_items in all_tables.values():
        if not isinstance(table_items, list):
            continue
        for item in table_items:
            if not isinstance(item, dict):
                continue
            cals = item.get("caliber", [])
            if isinstance(cals, str):
                cals = [cals]
            if isinstance(cals, list) and caliber in cals:
                for c in cals:
                    if isinstance(c, str) and c:
                        family.add(c)
                cals = [cals]
            if isinstance(cals, list) and caliber in cals:
                for c in cals:
                    if isinstance(c, str) and c:
                        family.add(c)
    return family

def _estimate_ammo_unit_price(caliber, all_ammo, sell_mult, market_demand):
    """Return the estimated per-round shop price for *caliber*."""
    for ammo_def in all_ammo:
        if not isinstance(ammo_def, dict):
            continue
        cals = ammo_def.get("caliber", [])
        if isinstance(cals, str):
            cals = [cals]
        if caliber in cals:
            base = _safe_float(ammo_def.get("value"), 0.01) or 0.01
            market_mult = _get_item_market_multiplier(ammo_def, market_demand)
            return max(0.01, base * sell_mult * market_mult)
    return 0.01

def _resolve_ammo_order_item(caliber, quantity, table_data):
    """Pick a random ammo variant for an order, honouring caliber-family lookup.

    The returned dict is the item that will land in the player's inventory.
    Variant is chosen weighted by rarity across the full caliber family.
    """
    all_tables = table_data.get("tables", {})
    all_ammo = all_tables.get("ammunition", [])
    rarity_weights = table_data.get("rarity_weights", {})

    # Caliber family: co-occurring calibers from any weapon definition
    family = _get_weapon_caliber_family(caliber, all_tables)

    # Collect (ammo_def, variant_dict) pool weighted by rarity
    pool = []
    weights = []
    for ammo_def in all_ammo:
        if not isinstance(ammo_def, dict):
            continue
        cals = ammo_def.get("caliber", [])
        if isinstance(cals, str):
            cals = [cals]
        # Only include ammo whose caliber is in the family
        if not any(c in family for c in cals):
            continue
        variants = ammo_def.get("variants", []) or []
        for var in variants:
            if not isinstance(var, dict):
                continue
            rarity = var.get("rarity") or ammo_def.get("rarity") or "Common"
            w = _safe_float(rarity_weights.get(rarity, 1), 1.0) or 1.0
            pool.append((ammo_def, var))
            weights.append(w)

    if not pool:
        return None

    chosen_def, chosen_var = random.choices(pool, weights=weights, k=1)[0]
    cals_list = chosen_def.get("caliber", [])
    if isinstance(cals_list, str):
        cals_list = [cals_list]
    cal_str = ", ".join(cals_list) if cals_list else caliber
    vname = str(chosen_var.get("name") or chosen_var.get("type") or "FMJ")

    item_copy = chosen_def.copy()
    item_copy["name"] = f"{vname} ({cal_str})"
    item_copy["variant"] = vname
    item_copy["caliber"] = cal_str
    item_copy["quantity"] = quantity
    item_copy["_table_category"] = "ammunition"
    _apply_ammo_variant_data(item_copy, chosen_def, chosen_var)
    item_copy.pop("variants", None)
    return item_copy

def _generate_ammo_supplier_stock(store, tables, equipped_calibers, equipped_magazine_systems,
                                  all_ammo, all_mags, rarity_weights):
    """Build the in-stock item list for an ammo_supplier store."""
    rng = random.Random(_get_market_seed_for_store(store.get("name", "")))
    stock = []

    # ── 1. Guaranteed ammo ────────────────────────────────────────────────
    for g in store.get("guaranteed_ammo", []):
        if not isinstance(g, dict):
            continue
        item_id = g.get("id")
        qty = g.get("quantity", 1)
        variant_name = g.get("variant")
        for ammo_def in all_ammo:
            if not isinstance(ammo_def, dict) or ammo_def.get("id") != item_id:
                continue
            cals = ammo_def.get("caliber", [])
            if isinstance(cals, str):
                cals = [cals]
            cal_str = ", ".join(cals) if cals else "Unknown"
            variants = ammo_def.get("variants", []) or []
            variant_info = None
            if variant_name:
                for v in variants:
                    if isinstance(v, dict) and v.get("name") == variant_name:
                        variant_info = v
                        break
            if variant_info is None and variants:
                variant_info = variants[0]
            item_copy = ammo_def.copy()
            item_copy["_table_category"] = "ammunition"
            item_copy["quantity"] = qty
            if variant_info:
                vname = str(variant_info.get("name") or variant_info.get("type") or "FMJ")
                item_copy["name"] = f"{vname} ({cal_str})"
                item_copy["variant"] = vname
                item_copy["caliber"] = cal_str
                _apply_ammo_variant_data(item_copy, ammo_def, variant_info)
                item_copy.pop("variants", None)
            item_copy["_guaranteed"] = True
            stock.append(item_copy)
            break

    # ── 2. Random ammo stock (biased toward equipped calibers) ────────────
    compatible_ammo = []
    other_ammo = []
    for ammo_def in all_ammo:
        if not isinstance(ammo_def, dict):
            continue
        cals = ammo_def.get("caliber", [])
        if isinstance(cals, str):
            cals = [cals]
        if any(c in equipped_calibers for c in cals):
            compatible_ammo.append(ammo_def)
        else:
            other_ammo.append(ammo_def)

    def _expand_variants(ammo_def):
        cals = ammo_def.get("caliber", [])
        if isinstance(cals, str):
            cals = [cals]
        cal_str = ", ".join(cals) if cals else "Unknown"
        variants = ammo_def.get("variants", []) or []

        # Resolve quantity from random_quantity or fall back to quantity field
        rq = ammo_def.get("random_quantity")
        if isinstance(rq, dict):
            try:
                roll_qty = lambda: random.randint(int(rq.get("min", 1)), int(rq.get("max", 1)))
            except Exception:
                roll_qty = lambda: 1
        elif isinstance(ammo_def.get("quantity"), int) and ammo_def.get("quantity", 0) > 0:
            _fixed_qty = ammo_def["quantity"]
            roll_qty = lambda: _fixed_qty
        else:
            roll_qty = lambda: random.randint(10, 30)

        out = []
        for var in variants:
            if not isinstance(var, dict):
                continue
            vname = str(var.get("name") or var.get("type") or "FMJ")
            ic = ammo_def.copy()
            ic["_table_category"] = "ammunition"
            ic["name"] = f"{vname} ({cal_str})"
            ic["variant"] = vname
            ic["caliber"] = cal_str
            _apply_ammo_variant_data(ic, ammo_def, var)
            labels = ic.get("ammo_labels", [])
            if labels:
                ic["name"] = f"{ic['name']} [{' / '.join(labels)}]"
            ic.pop("variants", None)
            ic.pop("random_quantity", None)
            ic["quantity"] = roll_qty()
            out.append(ic)
        if not out:
            ic = ammo_def.copy()
            ic["_table_category"] = "ammunition"
            ic.pop("random_quantity", None)
            ic["quantity"] = roll_qty()
            out.append(ic)
        return out

    # Slight bias: compatible ammo appears ~3× as often in the random pool
    random_pool = []
    for a in compatible_ammo:
        random_pool += _expand_variants(a) * 3
    for a in other_ammo:
        random_pool += _expand_variants(a)

    if random_pool:
        # Take up to ~40 unique random entries beyond guaranteed
        sample_size = min(len(random_pool), 40)
        sampled = rng.sample(random_pool, sample_size)
        # Deduplicate by (name, variant, caliber)
        seen_keys = set()
        for item in sampled:
            key = (item.get("name"), item.get("variant"), item.get("caliber"))
            if key not in seen_keys:
                seen_keys.add(key)
                stock.append(item)

    # ── 3. Pre-filled magazines ───────────────────────────────────────────
    for mag_def in all_mags:
        if not isinstance(mag_def, dict):
            continue
        mag_sys = mag_def.get("magazinesystem")
        mag_cals = mag_def.get("caliber", [])
        if isinstance(mag_cals, str):
            mag_cals = [mag_cals]
        mag_sys_list = [mag_sys] if isinstance(mag_sys, str) and mag_sys else (
            mag_sys if isinstance(mag_sys, list) else [])
        compatible = (
            any(ms in equipped_magazine_systems for ms in mag_sys_list)
            and any(c in equipped_calibers for c in mag_cals)
        )
        if not compatible:
            continue
        mag_copy = mag_def.copy()
        mag_copy = add_subslots_to_item(mag_copy)
        mag_copy["_table_category"] = "magazines"
        capacity = mag_copy.get("capacity", 0)
        if capacity > 0 and mag_cals:
            fill_cal = mag_cals[0]
            fill_ammo_def = next(
                (a for a in all_ammo if isinstance(a, dict) and fill_cal in (
                    a.get("caliber", []) if isinstance(a.get("caliber", []), list) else [a.get("caliber")]
                )),
                None
            )
            if fill_ammo_def:
                variants = fill_ammo_def.get("variants", []) or []
                fill_var = next(
                    (v for v in variants if isinstance(v, dict) and str(v.get("name", "")).upper() == "FMJ"),
                    variants[0] if variants else None
                )
                rounds = []
                for _ in range(capacity):
                    rd = {"name": fill_cal, "caliber": fill_cal}
                    if fill_var:
                        _apply_ammo_variant_data(rd, fill_ammo_def, fill_var)
                        rd["variant"] = fill_var.get("name", "FMJ")
                    rounds.append(rd)
                mag_copy["rounds"] = rounds
        mag_copy["_prefilled"] = True
        stock.append(mag_copy)

    # ── 4. Occasional clips ───────────────────────────────────────────────
    for clip_def in tables.get("clips", []) or []:
        if not isinstance(clip_def, dict):
            continue
        clip_cals = clip_def.get("caliber", [])
        if isinstance(clip_cals, str):
            clip_cals = [clip_cals]
        if any(c in equipped_calibers for c in clip_cals) and rng.random() < 0.4:
            clip_copy = clip_def.copy()
            clip_copy["_table_category"] = "clips"
            stock.append(clip_copy)

    return stock

# ── Market system ─────────────────────────────────────────────────────────────
# Table-category → market segment mapping
_MARKET_TABLE_SEGMENTS = {
    "rifles": "firearms",
    "sniper_rifles": "firearms",
    "submachine_guns": "firearms",
    "shotguns": "firearms",
    "machine_guns": "firearms",
    "pistols": "firearms",
    "ammunition": "ammunition",
    "attachments": "attachments",
    "magazines": "magazines",
    "melee": "melee",
    "throwables": "throwables",
    "consumables": "consumables",
    "medical": "consumables",
    "equipment": "equipment",
    "gear": "equipment",
}
# All distinct market segments
_MARKET_SEGMENTS = ["firearms", "ammunition", "attachments", "magazines", "melee", "throwables", "consumables", "equipment"]
# Correlation pairs: (segment_a, segment_b, correlation_strength 0-1)
_MARKET_CORRELATIONS = [
    ("firearms", "ammunition",  0.75),
    ("firearms", "attachments", 0.55),
    ("firearms", "magazines",   0.65),
    ("throwables", "consumables", 0.35),
]
# Display names shown in the market ticker
_MARKET_SEGMENT_DISPLAY = {
    "firearms":    "Firearms",
    "ammunition":  "Ammo",
    "attachments": "Attachments",
    "magazines":   "Magazines",
    "melee":       "Melee",
    "throwables":  "Throwables",
    "consumables": "Consumables",
    "equipment":   "Equipment",
}

# Epoch from which the deterministic walk begins (v2 uses a continuous walk)
_MARKET_EPOCH = "2026-01-01"
# Walk parameters — tune these to control market behaviour
_MARKET_BASE_VOL      = 0.022   # daily noise std dev (~2.2 % per day normally)
_MARKET_MOMENTUM      = 0.28    # fraction of yesterday's delta that carries forward
_MARKET_MEAN_REVERT   = 0.07    # pull back toward 0 each day (7 %)
_MARKET_SPIKE_PROB    = 0.04    # probability of a volatility day (4 %)
_MARKET_SPIKE_MULT    = 3.2     # noise multiplier on a spike day
# After a spike the market tends to partially reverse the following day
_MARKET_SPIKE_REVERSE = 0.45    # fraction of spike delta that is reversed next day

# Simple LRU-style in-memory cache so the walk isn't recomputed on every price
_market_walk_cache: "dict[str, list]" = {}

def _get_market_day_key():
    """Return an ISO date string for the current market period (resets at noon)."""
    now = datetime.now()
    if now.hour < 12:
        market_date = (now - timedelta(days=1)).date()
    else:
        market_date = now.date()
    return market_date.isoformat()

def _compute_market_walk(up_to_day_key=None):
    """
    Run a continuous seeded random walk from _MARKET_EPOCH to up_to_day_key
    (defaults to today).  Each day uses only that day's seed for its noise, but
    the state (level + momentum) carries forward from the previous day, giving
    smooth, mean-reverting price action with rare volatility events.

    Returns a list of (date_key_str, demand_dict) tuples in chronological order.
    Cached by end-day-key.
    """
    import datetime as _dt

    if up_to_day_key is None:
        up_to_day_key = _get_market_day_key()

    if up_to_day_key in _market_walk_cache:
        return _market_walk_cache[up_to_day_key]

    epoch_date = _dt.date.fromisoformat(_MARKET_EPOCH)
    target_date = _dt.date.fromisoformat(up_to_day_key)
    total_days = max(1, (target_date - epoch_date).days + 1)

    # Walk state
    levels  = {seg: 0.0 for seg in _MARKET_SEGMENTS}
    deltas  = {seg: 0.0 for seg in _MARKET_SEGMENTS}
    # Track pending reversal from spike events
    reversal = {seg: 0.0 for seg in _MARKET_SEGMENTS}

    history = []

    for day_idx in range(total_days):
        d  = epoch_date + timedelta(days=day_idx)
        dk = d.isoformat()

        seed_int = int(_hashlib.sha256(f"market_v2_{dk}".encode()).hexdigest(), 16) & 0xFFFFFFFF
        rng = random.Random(seed_int)

        # Base independent Gaussian noise for each segment
        raw_noise = {seg: rng.gauss(0.0, 1.0) for seg in _MARKET_SEGMENTS}

        # Is today a volatility spike?
        is_spike = rng.random() < _MARKET_SPIKE_PROB
        noise_scale = _MARKET_BASE_VOL * (_MARKET_SPIKE_MULT if is_spike else 1.0)

        # Apply inter-segment correlations to blend noise
        corr_noise = dict(raw_noise)
        for seg_a, seg_b, strength in _MARKET_CORRELATIONS:
            shared = (raw_noise[seg_a] + raw_noise[seg_b]) / 2.0
            corr_noise[seg_a] = raw_noise[seg_a] * (1.0 - strength) + shared * strength
            corr_noise[seg_b] = raw_noise[seg_b] * (1.0 - strength) + shared * strength

        new_levels  = {}
        new_deltas  = {}
        new_reversal = {}

        for seg in _MARKET_SEGMENTS:
            # Components of today's delta
            noise_part     = corr_noise[seg] * noise_scale
            momentum_part  = _MARKET_MOMENTUM * deltas[seg]
            mean_rev_part  = -_MARKET_MEAN_REVERT * levels[seg]
            reversal_part  = reversal[seg]          # carry-over reversal from yesterday's spike

            new_delta = noise_part + momentum_part + mean_rev_part + reversal_part
            new_level = levels[seg] + new_delta

            new_levels[seg]  = new_level
            new_deltas[seg]  = new_delta
            # Schedule a partial reversal for tomorrow if today was a spike
            new_reversal[seg] = (-new_delta * _MARKET_SPIKE_REVERSE) if is_spike else 0.0

        levels   = new_levels
        deltas   = new_deltas
        reversal = new_reversal

        # Convert level (a signed %-like float) to a price multiplier, soft-capped
        demand = {}
        for seg, lv in levels.items():
            # Soft-cap via tanh so extremes compress rather than cut hard
            import math as _math
            soft = 0.38 * _math.tanh(lv / 0.30)
            demand[seg] = round(1.0 + soft, 4)

        history.append((dk, demand))

    _market_walk_cache[up_to_day_key] = history
    return history

def _get_market_demand(day_key=None):
    """Return the demand multiplier dict for the given (or current) market day."""
    if day_key is None:
        day_key = _get_market_day_key()
    history = _compute_market_walk(day_key)
    if history:
        return history[-1][1]
    return {seg: 1.0 for seg in _MARKET_SEGMENTS}

def _get_item_market_segment(item):
    """Resolve the market segment for an item dict."""
    table_cat = item.get("_table_category") or item.get("table_category") or ""
    seg = _MARKET_TABLE_SEGMENTS.get(table_cat)
    if seg:
        return seg
    if item.get("firearm"):
        return "firearms"
    if item.get("caliber") and not item.get("firearm") and not item.get("magazinesystem"):
        return "ammunition"
    if item.get("magazinesystem") and not item.get("firearm"):
        return "magazines"
    return None

def _get_item_market_multiplier(item, demand):
    """Return the demand multiplier for this item (1.0 if not categorised)."""
    seg = _get_item_market_segment(item)
    if seg and seg in demand:
        return demand[seg]
    return 1.0

def _format_market_ticker(demand):
    """Return a compact ticker string like 'Firearms ▲+9% | Ammo ▼-4%'."""
    parts = []
    for seg in _MARKET_SEGMENTS:
        mult = demand.get(seg, 1.0)
        pct = round((mult - 1.0) * 100)
        arrow = "▲" if pct >= 0 else "▼"
        sign  = "+" if pct >= 0 else ""
        label = _MARKET_SEGMENT_DISPLAY.get(seg, seg)
        parts.append(f"{label} {arrow}{sign}{pct}%")
    return "  |  ".join(parts)

def _get_market_seed_for_store(store_name):
    """Return an integer seed for deterministic store stock (same per player per day)."""
    day_key = _get_market_day_key()
    seed_int = int(_hashlib.sha256(f"store_stock_v1_{day_key}_{store_name}".encode()).hexdigest(), 16) & 0xFFFFFFFF
    return seed_int

def _get_seeded_store_firearm_rounds_fired(item, store_name, item_position, used_chance = 0.40):
    """Return deterministic rounds_fired for shop firearms, or None for new stock."""
    day_key = _get_market_day_key()
    item_id = item.get("id", "")
    item_name = item.get("name", "")
    seed_payload = f"store_condition_v1_{day_key}_{store_name}_{item_id}_{item_name}_{item_position}"
    seed_int = int(_hashlib.sha256(seed_payload.encode()).hexdigest(), 16) & 0xFFFFFFFF
    rng = random.Random(seed_int)

    if rng.random() >= max(0.0, min(1.0, float(used_chance))):
        return None

    # Bias hard toward lightly-used guns, keep a rare absurd high-mileage tail.
    roll = rng.random()
    if roll < 0.82:
        return int(1000 + ((rng.random() ** 1.5) * 4000))
    if roll < 0.97:
        return int(5000 + ((rng.random() ** 1.2) * 25000))
    return int(60000 + (rng.random() * 30000))
# ─────────────────────────────────────────────────────────────────────────────

def _apply_sale_modifiers(base_value, item, table_data=None):
    """Apply hardcore-mode rarity and rounds_fired modifiers to an item's sale value."""
    value = float(base_value)
    # Keep rarity-based hardcore economics as-is.
    if table_data and table_data.get("additional_settings", {}).get("hardcore_mode", False):
        rarity = _normalize_rarity_name(item.get("rarity") or "Common")
        value *= _rarity_sale_multiplier(rarity)
    # Firearm wear depreciation should apply consistently in all modes.
    value = _apply_firearm_round_wear_to_value(value, item)
    return value

def _is_new_historical_firearm(item):
    if not isinstance(item, dict) or not item.get("firearm"):
        return False

    table_cat = str(item.get("table_category") or item.get("_table_category") or "").strip().lower()
    is_historical = table_cat == "historical_firearms" or bool(item.get("_is_historical_firearm"))
    if not is_historical:
        return False

    try:
        rf = float(item.get("rounds_fired", 0) or 0)
    except (TypeError, ValueError):
        rf = 0.0
    return rf <= 0.0

def _get_firearm_round_wear_multiplier(rounds_fired):
    """Return value multiplier for firearm wear from round count.

    Targets (approx):
    - 3,000 rounds -> 75%
    - 10,000 rounds -> 33%
    - 30,000 rounds -> 8.3%
    """
    try:
        rf = max(0.0, float(rounds_fired or 0))
    except (TypeError, ValueError):
        rf = 0.0

    # Piecewise linear curve tuned to service-life expectations.
    points = [
        (0.0, 1.0),
        (3000.0, 0.75),
        (10000.0, 1.0 / 3.0),
        (30000.0, 1.0 / 12.0),
        (60000.0, 0.04),
        (100000.0, 0.02),
    ]

    if rf <= points[0][0]:
        return points[0][1]

    for idx in range(1, len(points)):
        x0, y0 = points[idx - 1]
        x1, y1 = points[idx]
        if rf <= x1:
            span = x1 - x0
            if span <= 0:
                return y1
            t = (rf - x0) / span
            return y0 + (y1 - y0) * t

    return points[-1][1]

def _get_firearm_installed_condition_ratio(item):
    """Return 0..1 condition ratio from installed firearm parts and spring."""
    if not isinstance(item, dict):
        return 0.0

    ratios = []

    def _to_float_or_none(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for part in item.get("parts") or []:
        if not isinstance(part, dict):
            continue
        current_obj = part.get("current")
        cur_val = part.get("current_durability")
        if cur_val is None and isinstance(current_obj, dict):
            cur_val = current_obj.get("current_durability")
        cur_num = _to_float_or_none(cur_val)
        if cur_num is None:
            continue

        max_val = part.get("durability")
        max_txt = str(max_val).strip().lower() if max_val is not None else ""
        if max_val is None or max_txt in ("", "null", "none", "set_by_looting"):
            if isinstance(current_obj, dict):
                max_val = current_obj.get("durability")

        max_num = _to_float_or_none(max_val)
        if max_num is None or max_num <= 0:
            max_num = float(PART_DURABILITY_MAX)

        ratio = max(0.0, min(1.0, cur_num / max_num))
        ratios.append(ratio)

    spring_num = _to_float_or_none(item.get("spring_durability"))
    if spring_num is not None:
        ratios.append(max(0.0, min(1.0, spring_num / float(PART_DURABILITY_MAX))))

    if not ratios:
        return 0.0
    return sum(ratios) / float(len(ratios))

def _apply_firearm_round_wear_to_value(base_value, item, min_price_floor = 100.0):
    """Return firearm value after historical/new markup and wear adjustments."""
    value = float(base_value or 0)
    if not isinstance(item, dict) or not item.get("firearm"):
        return value

    if _is_new_historical_firearm(item):
        return value * 25.0

    rf = item.get("rounds_fired")
    try:
        rf = float(rf) if rf is not None else 0.0
    except (TypeError, ValueError):
        rf = 0.0

    if rf <= 0:
        return value

    round_mult = _get_firearm_round_wear_multiplier(rf)
    condition_ratio = _get_firearm_installed_condition_ratio(item)

    # Good installed condition recovers up to 15% of value lost to high round count.
    recovery_mult = (1.0 - round_mult) * max(0.0, min(1.0, condition_ratio)) * 0.15
    effective_mult = min(1.0, round_mult + recovery_mult)

    worn_value = value * effective_mult
    # Floor at $100 for used firearms, but never increase above base value.
    return min(value, max(float(min_price_floor), worn_value))

def _get_depreciated_item_value(base_value, item):
    """Return base value after firearm wear depreciation."""
    return _apply_firearm_round_wear_to_value(base_value, item)

def _randomize_part_durability(weapon):
    parts = weapon.get("parts")
    if not parts or not isinstance(parts, list):
        return
    rf = weapon.get("rounds_fired", 0)
    if not isinstance(rf, (int, float)):
        rf = 0
    if rf > 0:
        wear_factor = min(1.0, rf / 50000.0)
        dur_max = PART_DURABILITY_MAX * max(0.1, 1.0 - (wear_factor * 0.85))
        dur_min = max(PART_DURABILITY_MAX * 0.05, dur_max * 0.3)
    else:
        dur_max = PART_DURABILITY_MAX
        dur_min = PART_DURABILITY_MAX * 0.15
    for p in parts:
        if not isinstance(p, dict):
            continue
        dur = p.get("durability")
        if dur == "set_by_looting" or dur is None:
            p["current_durability"] = random.uniform(dur_min, dur_max)
        elif isinstance(dur, (int, float)):
            dur_float = float(dur)
            adjusted_max = dur_float * max(0.1, 1.0 - (wear_factor * 0.85)) if rf > 0 else dur_float
            adjusted_min = max(dur_float * 0.05, adjusted_max * 0.3)
            p["current_durability"] = random.uniform(adjusted_min, adjusted_max)

def _set_full_part_durability(item):
    def _apply_full_to_part(part):
        if not isinstance(part, dict):
            return
        dur = part.get("durability")
        if dur == "set_by_looting":
            part["current_durability"] = float(PART_DURABILITY_MAX)
        elif isinstance(dur, (int, float)):
            part["current_durability"] = float(dur)
        cur = part.get("current")
        if isinstance(cur, dict):
            _apply_full_to_part(cur)

    parts = item.get("parts")
    if parts and isinstance(parts, list):
        for p in parts:
            _apply_full_to_part(p)
    if item.get("spring_durability") == "set_by_looting":
        item["spring_durability"] = float(PART_DURABILITY_MAX)
    _repair_item_parts_durability_recursive(item, fallback_value = PART_DURABILITY_MAX)

def _set_armory_used_good_weapon_condition(item):
    """Apply "used but good" condition to armory-issued firearms.

    Firearms should look used (rounds fired > 0) while keeping all mutable
    components at 90%+ condition.
    """
    if not isinstance(item, dict) or not item.get("firearm"):
        return

    try:
        current_rf = item.get("rounds_fired", 0)
        current_rf_num = int(current_rf) if isinstance(current_rf, (int, float, str)) else 0
    except Exception:
        current_rf_num = 0
    if current_rf_num <= 0:
        item["rounds_fired"] = random.randint(120, 2200)

    def _apply_used_good_to_part(part):
        if not isinstance(part, dict):
            return
        dur = part.get("durability")
        if dur == "set_by_looting":
            part["current_durability"] = round(random.uniform(PART_DURABILITY_MAX * 0.9, PART_DURABILITY_MAX), 2)
        else:
            try:
                if isinstance(dur, (int, float)):
                    base = float(dur)
                    part["current_durability"] = round(random.uniform(base * 0.9, base), 2)
            except Exception:
                pass
        cur = part.get("current")
        if isinstance(cur, dict):
            _apply_used_good_to_part(cur)

    parts = item.get("parts")
    if isinstance(parts, list):
        for p in parts:
            _apply_used_good_to_part(p)

    spring_dur = item.get("spring_durability")
    if spring_dur == "set_by_looting":
        item["spring_durability"] = round(random.uniform(PART_DURABILITY_MAX * 0.9, PART_DURABILITY_MAX), 2)
    else:
        try:
            if isinstance(spring_dur, (int, float)):
                spring_base = float(spring_dur)
                item["spring_durability"] = round(random.uniform(spring_base * 0.9, spring_base), 2)
        except Exception:
            pass

    # Ensure any still-unset part durability does not render as N/A in UI.
    _repair_item_parts_durability_recursive(item, fallback_value = PART_DURABILITY_MAX * 0.9)
    _sync_firearm_cleanliness_from_rounds_fired(item)

def _set_durability_from_rounds_fired(item, rounds_fired):
    """Set part durability proportional to a user-specified rounds-fired count.

    Uses the same wear curve as the looting system so results feel consistent.
    Also depreciates item value based on wear.
    """
    try:
        rf = max(0, int(rounds_fired))
    except (TypeError, ValueError):
        rf = 0
    item["rounds_fired"] = rf
    if rf == 0:
        _set_full_part_durability(item)
        return
    wear_factor = min(1.0, rf / 50000.0)
    dur_max = PART_DURABILITY_MAX * max(0.1, 1.0 - wear_factor * 0.85)
    dur_min = max(PART_DURABILITY_MAX * 0.05, dur_max * 0.3)

    def _apply(part):
        if not isinstance(part, dict):
            return
        dur = part.get("durability")
        if dur == "set_by_looting" or dur is None:
            part["current_durability"] = round(random.uniform(dur_min, dur_max), 2)
        elif isinstance(dur, (int, float)):
            base = float(dur)
            adj_max = base * max(0.1, 1.0 - wear_factor * 0.85)
            adj_min = max(base * 0.05, adj_max * 0.3)
            part["current_durability"] = round(random.uniform(adj_min, adj_max), 2)
        cur = part.get("current")
        if isinstance(cur, dict):
            _apply(cur)

    parts = item.get("parts")
    if isinstance(parts, list):
        for p in parts:
            _apply(p)
    spring_dur = item.get("spring_durability")
    if spring_dur == "set_by_looting":
        item["spring_durability"] = round(random.uniform(dur_min, dur_max), 2)
    elif isinstance(spring_dur, (int, float)):
        sd_max = float(spring_dur) * max(0.1, 1.0 - wear_factor * 0.85)
        sd_min = max(float(spring_dur) * 0.05, sd_max * 0.3)
        item["spring_durability"] = round(random.uniform(sd_min, sd_max), 2)
    _repair_item_parts_durability_recursive(item)

def _estimate_firearm_cleanliness_from_rounds_fired(rounds_fired):
    """Estimate starting barrel cleanliness from rounds fired.

    Used firearms should spawn noticeably dirty; brand-new firearms stay clean.
    """
    try:
        rf = max(0, int(float(rounds_fired or 0)))
    except (TypeError, ValueError):
        rf = 0
    if rf <= 0:
        return 100.0

    # Log-scale decay: quickly moves used guns out of "clean", then tapers.
    est = 72.0 - (math.log10(rf + 10.0) * 11.0)
    return max(12.0, min(68.0, est))

def _sync_firearm_cleanliness_from_rounds_fired(item):
    if not isinstance(item, dict) or not item.get("firearm"):
        return
    item["barrel_cleanliness"] = round(
        _estimate_firearm_cleanliness_from_rounds_fired(item.get("rounds_fired")),
        2,
    )

def _get_weapon_cleanliness(combat_state, weapon, default = 100.0, cache_to_state = False):
    """Resolve cleanliness from combat state, then item field, then rounds-fired estimate."""
    if not isinstance(combat_state, dict):
        combat_state = {}
    if not isinstance(weapon, dict):
        return float(default)

    weapon_id = str(weapon.get("id"))
    map_obj = combat_state.setdefault("barrel_cleanliness", {}) if cache_to_state else combat_state.get("barrel_cleanliness", {})
    if isinstance(map_obj, dict):
        mapped = map_obj.get(weapon_id)
        if mapped is not None:
            try:
                return float(mapped)
            except (TypeError, ValueError):
                pass

    item_clean = weapon.get("barrel_cleanliness")
    if item_clean is not None:
        try:
            clean_val = float(item_clean)
            if isinstance(map_obj, dict) and cache_to_state:
                map_obj[weapon_id] = clean_val
            return clean_val
        except (TypeError, ValueError):
            pass

    clean_val = float(default)
    if weapon.get("firearm"):
        clean_val = _estimate_firearm_cleanliness_from_rounds_fired(weapon.get("rounds_fired"))

    if isinstance(map_obj, dict) and cache_to_state:
        map_obj[weapon_id] = clean_val
    weapon["barrel_cleanliness"] = round(clean_val, 2)
    return clean_val

def _repair_item_parts_durability_recursive(node, fallback_value = 100.0):
    """Recursively normalize broken part durability values.

    Invalid or missing `current_durability` values under any `parts` list are
    repaired. If no usable durability source exists, fallback_value is used.
    """
    try:
        fallback_num = float(fallback_value)
    except (TypeError, ValueError):
        fallback_num = 100.0

    def _to_float_or_none(value):
        try:
            num = float(value)
            if math.isnan(num) or math.isinf(num):
                return None
            return num
        except (TypeError, ValueError):
            return None

    def _repair_part_dict(part_dict):
        if not isinstance(part_dict, dict):
            return

        current_val = part_dict.get("current_durability")
        current_num = _to_float_or_none(current_val)
        if current_num is not None:
            part_dict["current_durability"] = current_num
            return

        base_num = _to_float_or_none(part_dict.get("durability"))
        if base_num is not None:
            part_dict["current_durability"] = base_num
            return

        current_text = str(current_val).strip().lower() if current_val is not None else ""
        if current_text in ("", "n/a", "na", "none", "null", "set_by_looting") or "current_durability" not in part_dict:
            part_dict["current_durability"] = fallback_num

    def _walk(obj):
        if isinstance(obj, dict):
            parts_list = obj.get("parts")
            if isinstance(parts_list, list):
                for part_entry in parts_list:
                    if isinstance(part_entry, dict):
                        _repair_part_dict(part_entry)
                        part_current = part_entry.get("current")
                        if isinstance(part_current, dict):
                            _repair_part_dict(part_current)
                            _walk(part_current)
                        _walk(part_entry)

            for value in obj.values():
                if isinstance(value, (dict, list)):
                    _walk(value)
        elif isinstance(obj, list):
            for value in obj:
                if isinstance(value, (dict, list)):
                    _walk(value)

    _walk(node)
    return node

def _get_weapon_condition_label(item):
    """Return (condition_str, color) for a weapon item.
    Uses actual part current_durability if available, otherwise estimates from rounds_fired."""
    parts = item.get("parts")
    if parts and isinstance(parts, list):
        durabilities = []
        for p in parts:
            if not isinstance(p, dict):
                continue
            dur = p.get("current_durability")
            if dur is None or str(dur).strip().lower() in ("null", "set_by_looting"):
                continue
            try:
                durabilities.append(max(0.0, min(float(PART_DURABILITY_MAX), float(dur))))
            except (ValueError, TypeError):
                pass
        if durabilities:
            avg_pct = (sum(durabilities) / (len(durabilities) * PART_DURABILITY_MAX)) * 100
            if avg_pct <= 0:
                return "Worn Out", "#ff4444"
            elif avg_pct < 25:
                return "Poor", "#ff6644"
            elif avg_pct < 50:
                return "Fair", "#ffaa44"
            elif avg_pct < 75:
                return "Good", "#aacc44"
            else:
                return "Excellent", "#44cc44"
    # Fall back to rounds_fired estimate
    rf = item.get("rounds_fired")
    if rf is None:
        return "New (unissued)", "#44cc44"
    try:
        rf = int(rf)
    except (ValueError, TypeError):
        return "Unknown", "#888888"
    if rf < 2000:
        return "Like New", "#44cc44"
    elif rf < 10000:
        return "Excellent", "#44cc44"
    elif rf < 25000:
        return "Good", "#aacc44"
    elif rf < 45000:
        return "Fair", "#ffaa44"
    elif rf < 65000:
        return "Poor", "#ff6644"
    else:
        return "Worn Out", "#ff4444"

def _resolve_unset_durability(save_data):
    if not isinstance(save_data, dict):
        return save_data
    def _fix_item(item):
        if not isinstance(item, dict):
            return
        parts = item.get("parts")
        if parts and isinstance(parts, list):
            for p in parts:
                if not isinstance(p, dict):
                    continue
                if p.get("durability") == "set_by_looting" and p.get("current_durability") is None:
                    p["current_durability"] = random.uniform(PART_DURABILITY_MAX * 0.15, PART_DURABILITY_MAX)
                    logging.warning(f"Resolved unset durability for part '{p.get('name', 'Unknown')}' on '{item.get('name', 'Unknown')}' to {p['current_durability']:.1f}")
        if item.get("spring_durability") == "set_by_looting":
            item["spring_durability"] = random.uniform(100, PART_DURABILITY_MAX)
            logging.warning(f"Resolved unset spring_durability for '{item.get('name', 'Unknown')}' to {item['spring_durability']:.1f}")
    for slot_name, eq in save_data.get("equipment", {}).items():
        if isinstance(eq, dict):
            _fix_item(eq)
            for sub in eq.get("subslots", []) or []:
                if isinstance(sub, dict):
                    for si in sub.get("items", []) or []:
                        _fix_item(si)
    if "hands" in save_data and "items" in save_data.get("hands", {}):
        for item in save_data["hands"]["items"]:
            _fix_item(item)
    for item in save_data.get("storage", []):
        _fix_item(item)
    return save_data

def _check_weapon_can_fire(weapon):
    parts = weapon.get("parts")
    if not parts or not isinstance(parts, list):
        return True, None
    for p in parts:
        if not isinstance(p, dict):
            continue
        ptype = p.get("type", "")
        status = _check_part_status(weapon, ptype)
        if status == "missing":
            if ptype in ("bolt_carrier_group", "bolt"):
                return False, f"{ptype.replace('_', ' ').title()} is missing - weapon cannot fire!"
        if status in ("worn", "missing"):
            if ptype in ("trigger_spring", "bolt_carrier_group", "feed_tray", "bolt"):
                return False, f"{p.get('name', ptype)} is {'missing' if status == 'missing' else 'worn out'} - weapon cannot fire!"
    return True, None

def _get_weapon_part_effects(weapon):
    effects = {}
    parts = weapon.get("parts")
    if not parts or not isinstance(parts, list):
        return effects
    for p in parts:
        if not isinstance(p, dict):
            continue
        ptype = p.get("type", "")
        status = _check_part_status(weapon, ptype)
        if status in ("worn", "missing"):
            if ptype == "barrel":
                if status == "missing":
                    effects["aim_debuff"] = effects.get("aim_debuff", 0) - 8
                else:
                    effects["aim_debuff"] = effects.get("aim_debuff", 0) - 3
            elif ptype == "recoil_spring":
                effects["force_manual_action"] = True
            elif ptype == "gas_piston":
                effects["force_manual_action"] = True
            elif ptype == "buffer_spring":
                effects["inconsistent_feeding"] = True
    return effects

def _get_weapon_part_jam_data(weapon):
    """Return (jam_multiplier, low_part_labels) from current part durability."""
    parts = weapon.get("parts")
    if not parts or not isinstance(parts, list):
        return 1.0, []

    part_weights = {
        "barrel": 1.2,
        "trigger_spring": 1.55,
        "recoil_spring": 1.65,
        "gas_piston": 1.2,
        "bolt_carrier_group": 1.7,
        "feed_tray": 1.5,
        "buffer_spring": 1.35,
        "bolt": 1.6,
    }

    severity_sum = 0.0
    worst_pct = 1.0
    low_part_labels = []

    for p in parts:
        if not isinstance(p, dict):
            continue
        ptype = str(p.get("type", "") or "").strip()
        if not ptype:
            continue

        dur_val = p.get("current_durability")
        if dur_val is None or str(dur_val).strip().lower() in ("", "null", "set_by_looting"):
            continue

        try:
            dur_num = float(dur_val)
        except (ValueError, TypeError):
            continue

        pct = max(0.0, min(1.0, dur_num / float(PART_DURABILITY_MAX)))
        worst_pct = min(worst_pct, pct)

        if pct <= 0.35:
            label = p.get("name") or ptype.replace("_", " ").title()
            low_part_labels.append(f"{label} ({pct * 100:.0f}%)")

        weight = part_weights.get(ptype)
        if weight is None:
            continue

        # Start increasing jam risk once a part drops below ~85% condition.
        severity = max(0.0, (0.85 - pct) / 0.85)
        severity_sum += severity * weight

    if severity_sum <= 0.0:
        return 1.0, low_part_labels

    jam_mult = 1.0 + min(4.5, severity_sum * 0.55)
    if worst_pct <= 0.10:
        jam_mult *= 1.35

    return min(8.0, jam_mult), low_part_labels

MAGPUL_DOT_MATRIX = {
    "1": [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
    "2": [[1,1,0],[0,0,1],[0,1,0],[1,0,0],[1,1,1]],
    "3": [[1,1,0],[0,0,1],[0,1,0],[0,0,1],[1,1,0]],
    "4": [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
    "5": [[1,1,1],[1,0,0],[1,1,0],[0,0,1],[1,1,0]],
    "6": [[0,1,1],[1,0,0],[1,1,0],[1,0,1],[0,1,0]],
    "7": [[1,1,1],[0,0,1],[0,1,0],[0,1,0],[0,1,0]],
    "8": [[0,1,0],[1,0,1],[0,1,0],[1,0,1],[0,1,0]],
    "9": [[0,1,0],[1,0,1],[0,1,1],[0,0,1],[1,1,0]],
    "0": [[0,1,0],[1,0,1],[1,0,1],[1,0,1],[0,1,0]],
    "A": [[0,1,0],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
    "B": [[1,1,0],[1,0,1],[1,1,0],[1,0,1],[1,1,0]],
    "C": [[0,1,1],[1,0,0],[1,0,0],[1,0,0],[0,1,1]],
    "D": [[1,1,0],[1,0,1],[1,0,1],[1,0,1],[1,1,0]],
    "E": [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,1,1]],
    "F": [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,0,0]],
    "G": [[0,1,1],[1,0,0],[1,0,1],[1,0,1],[0,1,1]],
    "H": [[1,0,1],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
    "I": [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[1,1,1]],
    "J": [[0,0,1],[0,0,1],[0,0,1],[1,0,1],[0,1,0]],
    "K": [[1,0,1],[1,0,1],[1,1,0],[1,0,1],[1,0,1]],
    "L": [[1,0,0],[1,0,0],[1,0,0],[1,0,0],[1,1,1]],
    "M": [[1,0,1],[1,1,1],[1,0,1],[1,0,1],[1,0,1]],
    "N": [[1,0,1],[1,1,1],[1,1,1],[1,0,1],[1,0,1]],
    "O": [[0,1,0],[1,0,1],[1,0,1],[1,0,1],[0,1,0]],
    "P": [[1,1,0],[1,0,1],[1,1,0],[1,0,0],[1,0,0]],
    "Q": [[0,1,0],[1,0,1],[1,0,1],[1,1,1],[0,1,1]],
    "R": [[1,1,0],[1,0,1],[1,1,0],[1,0,1],[1,0,1]],
    "S": [[0,1,1],[1,0,0],[0,1,0],[0,0,1],[1,1,0]],
    "T": [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[0,1,0]],
    "U": [[1,0,1],[1,0,1],[1,0,1],[1,0,1],[0,1,0]],
    "V": [[1,0,1],[1,0,1],[1,0,1],[0,1,0],[0,1,0]],
    "W": [[1,0,1],[1,0,1],[1,0,1],[1,1,1],[1,0,1]],
    "X": [[1,0,1],[1,0,1],[0,1,0],[1,0,1],[1,0,1]],
    "Y": [[1,0,1],[1,0,1],[0,1,0],[0,1,0],[0,1,0]],
    "Z": [[1,1,1],[0,0,1],[0,1,0],[1,0,0],[1,1,1]],
    " ": [[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,0,0]],
    "-": [[0,0,0],[0,0,0],[1,1,1],[0,0,0],[0,0,0]],
    ".": [[0,0,0],[0,0,0],[0,0,0],[0,0,0],[0,1,0]],
    "+": [[0,0,0],[0,1,0],[1,1,1],[0,1,0],[0,0,0]],
}

MARKING_COLORS = {
    "white": "#FFFFFF",
    "red": "#FF3333",
    "green": "#33FF33",
    "blue": "#3399FF",
}

def get_magazine_grid_count(weapon_subtype):
    if weapon_subtype in ("pistol", "handgun", "revolver"):
        return 2
    return 4

def render_dot_matrix_text(text, max_chars=4):
    text = text.upper()[:max_chars]
    grids = []
    for ch in text:
        grids.append(MAGPUL_DOT_MATRIX.get(ch, MAGPUL_DOT_MATRIX.get(" ")))
    while len(grids) < max_chars:
        grids.append(MAGPUL_DOT_MATRIX[" "])
    return grids


def _update_electronic_attachment_battery(attachment, now_ts=None):
    if not attachment or not isinstance(attachment, dict):
        return
    if not attachment.get("electronic"):
        return
    if now_ts is None:
        now_ts = time.time()

    battery_capacity = attachment.get("battery_capacity", 0)
    if not battery_capacity or battery_capacity <= 0:
        return

    battery_level = attachment.get("battery_level")
    if battery_level is None:
        attachment["battery_level"] = float(battery_capacity)
        battery_level = float(battery_capacity)
    try:
        battery_level = float(battery_level)
    except (ValueError, TypeError):
        battery_level = float(battery_capacity)

    if not attachment.get("power_on"):
        return

    power_on_ts = attachment.get("power_on_timestamp")
    if power_on_ts is None:
        return

    try:
        power_on_ts = float(power_on_ts)
    except (ValueError, TypeError):
        return

    auto_off_seconds = attachment.get("auto_off_seconds")
    if auto_off_seconds:
        try:
            auto_off_seconds = float(auto_off_seconds)
        except (ValueError, TypeError):
            auto_off_seconds = None

    elapsed = max(0.0, now_ts - power_on_ts)

    if auto_off_seconds and elapsed >= auto_off_seconds:
        active_duration = auto_off_seconds
        attachment["power_on"] = False
        attachment.pop("power_on_timestamp", None)
    else:
        active_duration = elapsed

    drain_rate = attachment.get("drain_rate", 0)
    try:
        drain_rate = float(drain_rate)
    except (ValueError, TypeError):
        drain_rate = 0

    if drain_rate > 0 and active_duration > 0:
        hours_active = active_duration / 3600.0
        drained = drain_rate * hours_active
        battery_level = max(0.0, battery_level - drained)
        attachment["battery_level"] = round(battery_level, 4)

    if battery_level <= 0:
        attachment["power_on"] = False
        attachment.pop("power_on_timestamp", None)
        attachment["battery_level"] = 0.0

    if attachment.get("power_on"):
        attachment["power_on_timestamp"] = now_ts


def _update_all_weapon_batteries(equipped_weapons, now_ts=None):
    if now_ts is None:
        now_ts = time.time()
    for wpn in equipped_weapons:
        item = wpn if isinstance(wpn, dict) and "accessories" in wpn else wpn.get("item", {}) if isinstance(wpn, dict) else {}
        for acc in item.get("accessories", []) or []:
            cur = acc.get("current")
            if isinstance(cur, dict):
                _update_electronic_attachment_battery(cur, now_ts)
                for sub in cur.get("subslots", []) or []:
                    sub_cur = sub.get("current") if isinstance(sub, dict) else None
                    if isinstance(sub_cur, dict):
                        _update_electronic_attachment_battery(sub_cur, now_ts)


def _toggle_electronic_attachment(attachment):
    if not attachment or not isinstance(attachment, dict):
        return False, "No attachment"
    if not attachment.get("electronic"):
        return False, "Not an electronic device"

    battery_capacity = attachment.get("battery_capacity", 0)
    if not battery_capacity or battery_capacity <= 0:
        return False, "No battery"

    _update_electronic_attachment_battery(attachment)

    battery_level = float(attachment.get("battery_level", 0))
    if battery_level <= 0 and not attachment.get("power_on"):
        return False, "Battery dead"

    if attachment.get("power_on"):
        attachment["power_on"] = False
        attachment.pop("power_on_timestamp", None)
        return True, "OFF"
    else:
        attachment["power_on"] = True
        attachment["power_on_timestamp"] = time.time()
        return True, "ON"


def _get_battery_percentage(attachment):
    if not attachment or not isinstance(attachment, dict):
        return None
    if not attachment.get("electronic"):
        return None
    cap = attachment.get("battery_capacity", 0)
    if not cap or cap <= 0:
        return None
    level = attachment.get("battery_level")
    if level is None:
        return 100.0
    try:
        return max(0.0, min(100.0, float(level) / float(cap) * 100.0))
    except (ValueError, TypeError, ZeroDivisionError):
        return None

# Auto-generated by refactor_main.py: re-export every module-level symbol
# (including underscore-prefixed and conditionally-assigned names) so that
# `from app.foundation import *` exposes everything the App mixins reference.
__all__ = [name for name in dir() if not name.startswith("__")]
