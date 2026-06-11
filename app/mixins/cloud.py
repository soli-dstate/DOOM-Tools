"""CloudMixin — App methods for the "cloud" feature area."""
from app.foundation import *


class CloudMixin:

    # ----- Cloud saves (Google Drive) -----
    def _cloud_sync_file_set(self):
        """(local_path, remote_name) pairs to push.

        Includes top-level .sldsv saves and the per-character backup saves under
        backups/<char>/, but NOT the zipped backup archives in backups/<char>/archive/.
        Backup files use their saves-relative path (posix) as the remote name so
        they restore back into the right subfolder; the signing key is also pushed.
        """
        pairs = []
        folder = saves_folder or "saves"
        try:
            for fname in os.listdir(folder):
                full = os.path.join(folder, fname)
                if os.path.isfile(full) and fname.lower().endswith(".sldsv") and fname not in CLOUD_SYNC_EXCLUDE:
                    pairs.append((full, fname))
        except Exception:
            pass

        backups_root = os.path.join(folder, "backups")
        if os.path.isdir(backups_root):
            for root, dirs, fnames in os.walk(backups_root):
                # Don't descend into archive/ folders -> excludes the backup archives.
                dirs[:] = [d for d in dirs if d.lower() != "archive"]
                for fname in fnames:
                    if not fname.lower().endswith(".sldsv"):
                        continue
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, folder).replace(os.sep, "/")
                    pairs.append((full, rel))

        key_path = _get_save_key_path()
        if os.path.exists(key_path):
            pairs.append((key_path, CLOUD_KEY_REMOTE_NAME))
        return pairs

    def _cloud_local_has_character_saves(self):
        folder = saves_folder or "saves"
        reserved = {"settings.sldsv", "appearance_settings.sldsv",
                    "persistent_data.sldsv", "dm_settings.sldsv"}
        try:
            for fname in os.listdir(folder):
                if fname.lower().endswith(".sldsv") and fname not in reserved:
                    return True
        except Exception:
            pass
        return False

    def _cloud_upload_all(self, logger=None, on_chunk=None, on_total=None, on_compress=None):
        """Bundle the sync set into one zip and upload it as a single Drive file.

        on_compress(done, total) fires as files are read into the zip (input bytes);
        on_total(zip_bytes) fires once the zip is built (so a progress UI can set
        its upload denominator); on_chunk(n) fires as the zip streams to Drive.
        """
        import tempfile
        log = logger or (lambda m: logging.info(m))
        pairs = self._cloud_sync_file_set()
        if not pairs:
            return 0

        pairs = [(p, a) for p, a in pairs if os.path.exists(p)]
        compress_total = sum(os.path.getsize(p) for p, _ in pairs)
        compressed = 0
        if on_compress:
            try:
                on_compress(0, compress_total)
            except Exception:
                pass

        tmp_zip = os.path.join(tempfile.gettempdir(), f"doomtools-cloud-up-{os.getpid()}.zip")
        added = 0
        try:
            with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for local_path, arcname in pairs:
                    try:
                        with open(local_path, "rb") as src, zf.open(arcname, "w") as dst:
                            while True:
                                block = src.read(262144)
                                if not block:
                                    break
                                dst.write(block)
                                compressed += len(block)
                                if on_compress:
                                    try:
                                        on_compress(compressed, compress_total)
                                    except Exception:
                                        pass
                        added += 1
                    except Exception as e:
                        log(f"Cloud zip add failed for {arcname}: {e}")
            if on_total:
                try:
                    on_total(os.path.getsize(tmp_zip))
                except Exception:
                    pass

            folder_id = _cloud_get_folder_id(create=True)
            existing = {f["name"]: f["id"] for f in _cloud_list_folder(folder_id)}
            _cloud_upload_file(folder_id, tmp_zip, CLOUD_ARCHIVE_NAME,
                               existing.get(CLOUD_ARCHIVE_NAME), on_chunk=on_chunk)
            log(f"Cloud sync uploaded {added} file(s) in {CLOUD_ARCHIVE_NAME}.")
        finally:
            try:
                os.remove(tmp_zip)
            except Exception:
                pass
        return added

    def _cloud_apply_key_bytes(self, raw):
        """Store a restored signing key so downloaded saves verify here."""
        try:
            with open(_cloud_imported_key_path(), "wb") as f:
                f.write(raw)
        except Exception:
            return
        primary = _get_save_key_path()
        if not os.path.exists(primary):
            try:
                os.makedirs(os.path.dirname(primary), exist_ok=True)
                shutil.copy2(_cloud_imported_key_path(), primary)
            except Exception:
                pass

    def _cloud_restore_all(self, logger=None):
        import tempfile
        log = logger or (lambda m: logging.info(m))
        folder_id = _cloud_get_folder_id(create=False)
        if not folder_id:
            return 0
        folder = saves_folder or "saves"
        os.makedirs(folder, exist_ok=True)
        listing = {f["name"]: f["id"] for f in _cloud_list_folder(folder_id)}

        archive_id = listing.get(CLOUD_ARCHIVE_NAME)
        if archive_id:
            tmp_zip = os.path.join(tempfile.gettempdir(), f"doomtools-cloud-dl-{os.getpid()}.zip")
            count = 0
            try:
                _cloud_download_file(archive_id, tmp_zip)
                with zipfile.ZipFile(tmp_zip, "r") as zf:
                    for member in zf.namelist():
                        if member.endswith("/"):
                            continue
                        parts = [p for p in member.replace("\\", "/").split("/")
                                 if p not in ("", ".", "..")]
                        if not parts:
                            continue
                        try:
                            if parts == [CLOUD_KEY_REMOTE_NAME]:
                                self._cloud_apply_key_bytes(zf.read(member))
                                continue
                            dest = os.path.join(folder, *parts)
                            os.makedirs(os.path.dirname(dest) or folder, exist_ok=True)
                            with zf.open(member) as src, open(dest, "wb") as dst:
                                shutil.copyfileobj(src, dst)
                            count += 1
                        except Exception as e:
                            log(f"Cloud restore failed for {member}: {e}")
            finally:
                try:
                    os.remove(tmp_zip)
                except Exception:
                    pass
            return count

        # Back-compat: clouds created before zip bundling stored individual files.
        count = 0
        for f in _cloud_list_folder(folder_id):
            name = f["name"]
            try:
                if name == CLOUD_KEY_REMOTE_NAME:
                    self._cloud_apply_key_bytes(requests.get(
                        f"{DRIVE_API}/files/{f['id']}", headers=_cloud_headers(),
                        params={"alt": "media"}, timeout=120).content)
                    continue
                if name in CLOUD_SYNC_EXCLUDE or not name.lower().endswith(".sldsv"):
                    continue
                rel_parts = [p for p in name.split("/") if p not in ("", ".", "..")]
                if not rel_parts:
                    continue
                _cloud_download_file(f["id"], os.path.join(folder, *rel_parts))
                count += 1
            except Exception as e:
                log(f"Cloud download failed for {name}: {e}")
        return count

    def _cloud_run_async(self, title, message, work, on_done):
        prog = self._popup_progress(title, message)
        result = {}

        def runner():
            try:
                result["value"] = work()
            except Exception as e:
                result["error"] = e

            def finish():
                try:
                    prog["close"]()
                except Exception:
                    pass
                on_done(result.get("value"), result.get("error"))

            try:
                self.root.after(0, finish)
            except Exception:
                pass

        threading.Thread(target=runner, daemon=True).start()

    def _cloud_sync_on_exit(self):
        """Upload saves during autosave-on-exit, with a progress popup (MB/s).

        Runs synchronously on the main thread (the UI is still alive here) and
        pumps the popup from the per-chunk upload callback.
        """
        try:
            if not (cloud_is_configured() and cloud_is_signed_in()):
                return
        except Exception:
            return

        popup = None
        bar = None
        status = None
        try:
            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Cloud Saves")
            popup.geometry("420x150")
            popup.transient(self.root)
            popup.protocol("WM_DELETE_WINDOW", lambda: None)
            customtkinter.CTkLabel(
                popup, text="Syncing saves to the cloud...",
                font=customtkinter.CTkFont(size=14, weight="bold")
            ).pack(pady=(22, 10))
            bar = customtkinter.CTkProgressBar(popup, width=360)
            bar.set(0.0)
            bar.pack(pady=4)
            status = customtkinter.CTkLabel(
                popup, text="Compressing saves...",
                font=customtkinter.CTkFont(size=12)
            )
            status.pack(pady=(8, 12))
            self._center_popup_on_window(popup, 420, 150)
            popup.update()
        except Exception:
            popup = None

        # total is the compressed zip size for upload; set once the archive is built.
        state = {"done": 0, "total": 0, "start": time.monotonic(), "last": 0.0}

        def _render(prefix, done, total, speed=None):
            if popup is None:
                return
            now = time.monotonic()
            if now - state["last"] < 0.05 and (not total or done < total):
                return
            state["last"] = now
            frac = min(done / total, 1.0) if total else 0.0
            text = f"{prefix}: {done / 1048576:.1f} / {total / 1048576:.1f} MB"
            if speed is not None:
                text += f"    {speed:.2f} MB/s"
            try:
                bar.set(frac)
                status.configure(text=text)
                popup.update()
            except Exception:
                pass

        def on_compress(done, total):
            _render("Compressing", done, total)

        def on_total(zip_bytes):
            state["total"] = zip_bytes
            state["start"] = time.monotonic()
            state["last"] = 0.0

        def on_chunk(n):
            state["done"] += n
            total = state["total"]
            elapsed = time.monotonic() - state["start"]
            speed = (state["done"] / elapsed / 1048576) if elapsed > 0 else 0.0
            _render("Uploading", state["done"], total, speed)

        try:
            logging.info("Uploading saves to cloud...")
            self._cloud_upload_all(on_chunk=on_chunk, on_total=on_total, on_compress=on_compress)
        except Exception as e:
            logging.error(f"Cloud sync on exit failed: {e}")
        finally:
            if popup is not None:
                try:
                    popup.destroy()
                except Exception:
                    pass

    def _cloud_begin_restore_flow(self):
        def work():
            if not cloud_is_signed_in():
                cloud_oauth_login()
            return self._cloud_restore_all()

        def done(result, error):
            if error:
                self._popup_show_info("Cloud Saves", f"Could not load from cloud:\n{error}", sound="error")
                return
            self._popup_show_info(
                "Cloud Saves",
                f"Loaded {result} file(s) from the cloud.\nOpen a character to use them.",
                sound="success")
            try:
                self._clear_window()
                self._build_main_menu()
            except Exception:
                pass

        self._cloud_run_async("Cloud Saves", "Connecting to Google Drive...", work, done)

    def _maybe_prompt_cloud_restore(self):
        try:
            if not cloud_is_configured():
                return
            if self._cloud_local_has_character_saves():
                return
            state = _cloud_load_json(_cloud_state_path())
            if state.get("fresh_prompt_done"):
                return
            state["fresh_prompt_done"] = True
            _cloud_save_json(_cloud_state_path(), state)

            def after_confirm(yes):
                if yes:
                    self._cloud_begin_restore_flow()

            self._popup_confirm(
                "Cloud Saves",
                "No local saves were found on this system.\n\n"
                "Would you like to sign in with Google and load your saves from the cloud?",
                after_confirm)
        except Exception:
            logging.exception("Cloud fresh-launch prompt failed")

    def _open_cloud_saves(self):
        self._clear_window()
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew")

        customtkinter.CTkLabel(main_frame, text="Cloud Saves",
                               font=customtkinter.CTkFont(size=24, weight="bold")).pack(pady=20)

        if not cloud_is_configured():
            customtkinter.CTkLabel(
                main_frame,
                text=("Cloud saves are not configured.\n\n"
                      "Provide a Google Desktop OAuth client id/secret via the\n"
                      "DOOMTOOLS_GDRIVE_CLIENT_ID / DOOMTOOLS_GDRIVE_CLIENT_SECRET env vars\n"
                      "or a cloud_credentials.json file to enable."),
                font=customtkinter.CTkFont(size=14), justify="center").pack(pady=20)
            self._create_sound_button(main_frame, "Back to Settings",
                                      lambda: [self._clear_window(), self._open_settings()],
                                      width=500, height=50,
                                      font=customtkinter.CTkFont(size=16)).pack(pady=10)
            return

        signed_in = cloud_is_signed_in()
        status = "Signed in to Google Drive" if signed_in else "Not signed in"
        customtkinter.CTkLabel(main_frame, text=status,
                               font=customtkinter.CTkFont(size=15)).pack(pady=10)

        if not signed_in:
            def do_login():
                def work():
                    cloud_oauth_login()
                    return True

                def done(_result, error):
                    if error:
                        self._popup_show_info("Cloud Saves", f"Sign-in failed:\n{error}", sound="error")
                    else:
                        self._popup_show_info("Cloud Saves", "Signed in successfully.", sound="success")
                    self._open_cloud_saves()

                self._cloud_run_async("Cloud Saves",
                                      "A browser window has opened.\nComplete sign-in there...",
                                      work, done)

            self._create_sound_button(main_frame, "Sign in with Google", do_login,
                                      width=500, height=50,
                                      font=customtkinter.CTkFont(size=16)).pack(pady=10)
        else:
            storage_label = customtkinter.CTkLabel(
                main_frame, text="Drive storage: checking...",
                font=customtkinter.CTkFont(size=13))
            storage_label.pack(pady=(0, 10))

            def _load_storage():
                try:
                    quota = _cloud_get_storage_quota()
                except Exception as exc:
                    text = f"Drive storage: unavailable ({exc})"
                else:
                    usage = int(quota.get("usage", 0) or 0)
                    limit_raw = quota.get("limit")
                    if limit_raw in (None, ""):
                        text = f"Drive storage: {_format_bytes(usage)} used (unlimited)"
                    else:
                        limit = int(limit_raw)
                        free = max(limit - usage, 0)
                        pct = (usage / limit * 100) if limit else 0
                        text = (f"Drive storage: {_format_bytes(usage)} / {_format_bytes(limit)} "
                                f"used ({pct:.0f}%)  •  {_format_bytes(free)} free")

                def apply():
                    try:
                        storage_label.configure(text=text)
                    except Exception:
                        pass

                try:
                    self.root.after(0, apply)
                except Exception:
                    pass

            threading.Thread(target=_load_storage, daemon=True).start()

            def do_upload():
                def done(result, error):
                    if error:
                        self._popup_show_info("Cloud Saves", f"Upload failed:\n{error}", sound="error")
                    else:
                        self._popup_show_info("Cloud Saves", f"Uploaded {result} file(s) to the cloud.", sound="success")

                self._cloud_run_async("Cloud Saves", "Uploading to Google Drive...",
                                      self._cloud_upload_all, done)

            def do_restore():
                def confirmed(yes):
                    if not yes:
                        return

                    def done(result, error):
                        if error:
                            self._popup_show_info("Cloud Saves", f"Restore failed:\n{error}", sound="error")
                        else:
                            self._popup_show_info("Cloud Saves",
                                                  f"Downloaded {result} file(s) from the cloud.", sound="success")
                            self._clear_window()
                            self._build_main_menu()

                    self._cloud_run_async("Cloud Saves", "Downloading from Google Drive...",
                                          self._cloud_restore_all, done)

                self._popup_confirm("Cloud Saves",
                                    "Download cloud saves into this system?\n"
                                    "Files with the same name will be overwritten.",
                                    confirmed)

            def do_signout():
                def confirmed(yes):
                    if yes:
                        cloud_sign_out()
                        self._open_cloud_saves()

                self._popup_confirm("Cloud Saves", "Sign out of Google Drive on this system?", confirmed)

            self._create_sound_button(main_frame, "Upload Saves to Cloud", do_upload,
                                      width=500, height=50, font=customtkinter.CTkFont(size=16)).pack(pady=10)
            self._create_sound_button(main_frame, "Restore Saves from Cloud", do_restore,
                                      width=500, height=50, font=customtkinter.CTkFont(size=16)).pack(pady=10)
            self._create_sound_button(main_frame, "Sign Out", do_signout,
                                      width=500, height=50, font=customtkinter.CTkFont(size=16)).pack(pady=10)

        self._create_sound_button(main_frame, "Back to Settings",
                                  lambda: [self._clear_window(), self._open_settings()],
                                  width=500, height=50, font=customtkinter.CTkFont(size=16)).pack(pady=10)
