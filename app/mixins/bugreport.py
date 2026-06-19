"""BugreportMixin — submit in-app bug reports to GitHub issues via a relay.

The report (name, description and optionally the current session log) is POSTed
to a server-side relay (see tools/bugreport-relay/). The relay holds the GitHub
token and creates the issue (with the log embedded in the body), so no token
ever lives on the user's machine. The reporter name defaults to the Windows username and, once
changed, persists in persistent_data.sldsv.
"""
from app.foundation import *


# Cap the log payload so a giant session log can't produce an oversized request
# (the relay also clamps before creating the Gist).
_BUGREPORT_LOG_MAX_BYTES = 4 * 1024 * 1024


class BugreportMixin:

    def _default_reporter_name(self):
        """Saved reporter name if set, otherwise the OS username."""
        try:
            saved = persistentdata.get("reporter_name")
            if saved and str(saved).strip():
                return str(saved).strip()
        except Exception:
            pass
        try:
            import getpass
            return getpass.getuser() or ""
        except Exception:
            return ""

    def _read_log_text(self, path):
        """Read a log file, tail-capped to the payload limit."""
        try:
            if not path or not os.path.exists(path):
                return ""
            # Flush handlers so the freshest lines are on disk before we read.
            try:
                for h in logging.getLogger().handlers:
                    if isinstance(h, logging.FileHandler):
                        h.flush()
            except Exception:
                pass
            size = os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                if size > _BUGREPORT_LOG_MAX_BYTES:
                    f.seek(size - _BUGREPORT_LOG_MAX_BYTES)
                    f.readline()  # drop the partial first line after seeking
                    text = f.read()
                    return "[... earlier log lines truncated ...]\n" + text
                return f.read()
        except Exception:
            logging.exception("Failed to read log for bug report")
            return ""

    def _read_current_log_text(self):
        return self._read_log_text(globals().get("log_filename"))

    def _open_bug_report(self):
        if not bugreport_is_configured():
            self._popup_show_info(
                "Report a Bug",
                "Bug reporting is not configured for this build.\n\n"
                "Set the relay URL via the DOOMTOOLS_BUGREPORT_URL env var or a "
                "bugreport_endpoint.txt file to enable it.",
                sound="error")
            return

        self._play_ui_sound("popup")
        try:
            theme = customtkinter.ThemeManager.theme
            toplevel_fg = theme.get("CTkToplevel", {}).get("fg_color")
        except Exception:
            toplevel_fg = None

        if toplevel_fg:
            popup = customtkinter.CTkToplevel(self.root, fg_color=toplevel_fg)
        else:
            popup = customtkinter.CTkToplevel(self.root)
        popup.title("Report a Bug")
        popup.geometry("520x680")
        popup.transient(self.root)

        customtkinter.CTkLabel(
            popup, text="Report a Bug",
            font=customtkinter.CTkFont(size=20, weight="bold")).pack(pady=(18, 4))
        customtkinter.CTkLabel(
            popup,
            text="This opens an issue on the DOOM-Tools GitHub repository.",
            font=customtkinter.CTkFont(size=12), text_color="gray").pack(pady=(0, 10))

        # Scrollable so the Submit/Cancel row at the bottom of the popup never
        # gets pushed off-screen by the variable-height steps list above it.
        body = customtkinter.CTkScrollableFrame(popup, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20)

        customtkinter.CTkLabel(
            body, text="Your name",
            font=customtkinter.CTkFont(size=13, weight="bold")).pack(anchor="w")
        name_var = customtkinter.StringVar(value=self._default_reporter_name())
        name_entry = customtkinter.CTkEntry(body, textvariable=name_var)
        name_entry.pack(fill="x", pady=(2, 12))

        customtkinter.CTkLabel(
            body, text="What went wrong?",
            font=customtkinter.CTkFont(size=13, weight="bold")).pack(anchor="w")
        desc_box = customtkinter.CTkTextbox(body, height=140, wrap="word")
        desc_box.pack(fill="both", expand=True, pady=(2, 12))

        customtkinter.CTkLabel(
            body, text="Steps to Reproduce (optional)",
            font=customtkinter.CTkFont(size=13, weight="bold")).pack(anchor="w")
        steps_scroll = customtkinter.CTkScrollableFrame(body, height=110)
        steps_scroll.pack(fill="x", pady=(2, 4))

        step_rows = []

        def renumber_steps():
            for i, rd in enumerate(step_rows):
                rd["label"].configure(text=f"{i + 1}.")
                rd["entry"].configure(placeholder_text=f"Step {i + 1}")

        def remove_step(rd):
            try:
                rd["frame"].destroy()
            except Exception:
                pass
            if rd in step_rows:
                step_rows.remove(rd)
            renumber_steps()

        def add_step():
            step_num = len(step_rows) + 1
            row = customtkinter.CTkFrame(steps_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            num_label = customtkinter.CTkLabel(row, text=f"{step_num}.", width=20, anchor="w")
            num_label.pack(side="left")
            entry = customtkinter.CTkEntry(row, placeholder_text=f"Step {step_num}")
            entry.pack(side="left", fill="x", expand=True, padx=(4, 4))
            rd = {"frame": row, "label": num_label, "entry": entry}
            self._create_sound_button(
                row, "✕", lambda: remove_step(rd), width=26, height=26,
                font=customtkinter.CTkFont(size=12), fg_color="#444444").pack(side="left")
            step_rows.append(rd)

        add_step()

        self._create_sound_button(
            body, "+ Add Step", add_step, width=120, height=26,
            font=customtkinter.CTkFont(size=12)).pack(anchor="w", pady=(0, 12))

        include_log_var = customtkinter.BooleanVar(value=True)
        customtkinter.CTkCheckBox(
            body, text="Include the current log file (recommended)",
            variable=include_log_var).pack(anchor="w", pady=(0, 4))
        customtkinter.CTkLabel(
            body,
            text="The log helps diagnose the problem and is attached to the report.",
            font=customtkinter.CTkFont(size=11), text_color="gray",
            wraplength=460, justify="left").pack(anchor="w", pady=(0, 8))

        button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=(0, 16))

        def do_submit():
            name = name_var.get().strip()
            description = desc_box.get("1.0", "end").strip()
            include_log = bool(include_log_var.get())
            if not description:
                self._popup_show_info(
                    "Report a Bug",
                    "Please describe the problem before submitting.", sound="error")
                return

            # Persist the (possibly changed) name for next time.
            try:
                persistentdata["reporter_name"] = name or None
                self._save_persistent_data()
            except Exception:
                logging.exception("Failed to persist reporter name")

            log_text = self._read_current_log_text() if include_log else ""
            log_name = os.path.basename(globals().get("log_filename") or "session.log")

            steps = [rd["entry"].get().strip() for rd in step_rows if rd["entry"].get().strip()]
            steps_markdown = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))

            try:
                popup.destroy()
            except Exception:
                pass

            self._submit_bug_report(name or "Anonymous", description, log_text, log_name, steps_markdown)

        self._create_sound_button(
            button_frame, "Submit", do_submit, width=160, height=38).pack(side="left", padx=8)
        self._create_sound_button(
            button_frame, "Cancel", lambda: popup.destroy(),
            width=160, height=38, fg_color="#444444").pack(side="left", padx=8)

        self._center_popup_on_window(popup, 520, 680)
        popup.deiconify()
        popup.lift()
        try:
            popup.grab_set()
            self._safe_focus(desc_box)
        except Exception:
            pass

    def _build_report_payload(self, name, description, log_text=None, log_name=None, steps_markdown=None):
        payload = {
            "name": name or "Anonymous",
            "description": description,
            "app_version": globals().get("version", "unknown"),
            "platform": f"{platform.system()} {platform.release()}",
        }
        if log_text:
            payload["log"] = log_text
            payload["log_filename"] = log_name or "session.log"
        if steps_markdown:
            payload["steps_to_reproduce"] = steps_markdown
        return payload

    def _post_report(self, payload, timeout=60):
        """POST a report to the relay; raise on non-2xx. Returns parsed JSON."""
        resp = requests.post(bugreport_endpoint(), json=payload, timeout=timeout)
        if resp.status_code not in (200, 201):
            detail = ""
            try:
                detail = resp.json().get("error") or resp.text
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Relay returned HTTP {resp.status_code}: {detail[:300]}")
        try:
            return resp.json()
        except Exception:
            return {}

    def _submit_bug_report(self, name, description, log_text, log_name, steps_markdown=None):
        payload = self._build_report_payload(name, description, log_text, log_name, steps_markdown)

        def work():
            return self._post_report(payload)

        def done(result, error):
            if error:
                logging.error(f"Bug report submission failed: {error}")
                self._popup_show_info(
                    "Report a Bug",
                    f"Could not submit your report:\n{error}", sound="error")
                return
            issue_url = (result or {}).get("issue_url", "")
            logging.info(f"Bug report submitted: {issue_url or '(no url returned)'}")
            if issue_url:
                try:
                    self._copy_to_clipboard(issue_url)
                except Exception:
                    pass
                self._popup_show_info(
                    "Report a Bug",
                    "Thanks! Your report was submitted.\n\n"
                    f"Issue: {issue_url}\n(The link has been copied to your clipboard.)",
                    sound="success")
            else:
                self._popup_show_info(
                    "Report a Bug",
                    "Thanks! Your report was submitted.", sound="success")

        self._cloud_run_async(
            "Report a Bug", "Submitting your report...", work, done)

    # ----- Automatic crash / exception reporting -----

    def _auto_report(self, description, log_text=None, log_name=None, signature=None, block=False):
        """File a report without UI. Deduped per session; never raises."""
        if not bugreport_is_configured() or getattr(self, "_auto_reporting", False):
            return
        sig = signature or description[:200]
        seen = getattr(self, "_auto_reported_signatures", None)
        if seen is None:
            seen = set()
            self._auto_reported_signatures = seen
        if sig in seen:
            return
        seen.add(sig)

        payload = self._build_report_payload(
            self._default_reporter_name(), description, log_text, log_name)
        payload["automatic"] = True

        def work():
            self._auto_reporting = True
            try:
                result = self._post_report(payload, timeout=15)
                logging.info(f"Auto report submitted: {(result or {}).get('issue_url', '(no url)')}")
            except Exception as e:
                logging.error(f"Auto report failed: {e}")
            finally:
                self._auto_reporting = False

        if block:
            work()
        else:
            threading.Thread(target=work, daemon=True).start()

    def _report_exception(self, exc_type, exc_value, exc_tb, source="runtime"):
        try:
            import traceback
            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            try:
                summary = f"{getattr(exc_type, '__name__', exc_type)}: {exc_value}".strip()
            except Exception:
                summary = "Unhandled exception"
            description = (f"[auto] {summary}\n\n"
                           f"Automatic error report ({source}).\n\n{tb_text}")
            self._auto_report(
                description,
                log_text=self._read_current_log_text(),
                log_name=os.path.basename(globals().get("log_filename") or "session.log"),
                signature=f"exc:{summary}",
                block=(source == "excepthook"))
        except Exception:
            logging.exception("Failed to build auto exception report")
        # A fatal (excepthook) crash is already reported; don't re-report it as an
        # unclean shutdown on the next launch.
        if source == "excepthook":
            self._clear_crash_sentinel()

    def _install_exception_reporting(self):
        """Wrap the Tk callback-exception handler to auto-report real errors."""
        try:
            prev = self.root.report_callback_exception
        except Exception:
            prev = None

        def _reporting(exc_type, exc_value, exc_tb):
            try:
                msg = str(exc_value)
                # Skip Tk teardown noise ("invalid command name ...after").
                if "invalid command name" not in msg and "after" not in msg:
                    self._report_exception(exc_type, exc_value, exc_tb, source="tkinter")
            except Exception:
                pass
            if prev:
                try:
                    return prev(exc_type, exc_value, exc_tb)
                except Exception:
                    pass

        try:
            self.root.report_callback_exception = _reporting
        except Exception:
            logging.exception("Failed to install exception reporting")

    # ----- Hard-crash detection via a session sentinel -----

    def _crash_sentinel_path(self):
        return os.path.join("logs", ".session_active")

    def _crash_check_and_arm(self):
        """Report an unclean previous shutdown, then arm the sentinel for this run."""
        path = self._crash_sentinel_path()
        prev_log = None
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    prev_log = f.read().strip()
        except Exception:
            prev_log = None

        if prev_log is not None:
            logging.warning("Detected unclean shutdown from a previous session; filing crash report.")
            log_text = self._read_log_text(prev_log) if prev_log else ""
            log_name = os.path.basename(prev_log) if prev_log else "previous.log"
            self._auto_report(
                "[auto] Hard crash — previous session closed unexpectedly.\n\n"
                "The app terminated without a clean shutdown (force-close, native "
                "crash, or power loss). The previous session log is attached.",
                log_text=log_text, log_name=log_name,
                signature=f"crash:{log_name}")

        try:
            os.makedirs("logs", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(str(globals().get("log_filename") or ""))
        except Exception:
            logging.exception("Failed to arm crash sentinel")

    def _clear_crash_sentinel(self):
        try:
            p = self._crash_sentinel_path()
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

    # ----- First-run reporter name prompt -----

    def _maybe_prompt_reporter_name(self):
        if not bugreport_is_configured():
            return
        try:
            if persistentdata.get("reporter_name"):
                return
        except Exception:
            return

        self._play_ui_sound("popup")
        popup = customtkinter.CTkToplevel(self.root)
        popup.title("Bug Reporting")
        popup.geometry("440x230")
        popup.transient(self.root)

        customtkinter.CTkLabel(
            popup, text="Set your bug-reporting name",
            font=customtkinter.CTkFont(size=16, weight="bold")).pack(pady=(20, 6))
        customtkinter.CTkLabel(
            popup,
            text="This name is attached to any bug reports you send.\n"
                 "You can change it later from the Report a Bug screen.",
            font=customtkinter.CTkFont(size=12), text_color="gray",
            wraplength=400, justify="center").pack(pady=(0, 10))

        name_var = customtkinter.StringVar(value=self._default_reporter_name())
        entry = customtkinter.CTkEntry(popup, textvariable=name_var, width=300)
        entry.pack(pady=(0, 14))

        def save(name):
            try:
                persistentdata["reporter_name"] = name or self._default_reporter_name() or None
                self._save_persistent_data()
            except Exception:
                logging.exception("Failed to persist reporter name")
            try:
                popup.destroy()
            except Exception:
                pass

        button_frame = customtkinter.CTkFrame(popup, fg_color="transparent")
        button_frame.pack(pady=(0, 16))
        self._create_sound_button(
            button_frame, "Save", lambda: save(name_var.get().strip()),
            width=140, height=36).pack(side="left", padx=8)
        # Skip still persists a name (the OS username) so we don't nag every launch.
        self._create_sound_button(
            button_frame, "Skip", lambda: save(""),
            width=140, height=36, fg_color="#444444").pack(side="left", padx=8)

        entry.bind("<Return>", lambda e: save(name_var.get().strip()))
        self._center_popup_on_window(popup, 440, 230)
        popup.deiconify()
        popup.lift()
        try:
            popup.grab_set()
            self._safe_focus(entry)
        except Exception:
            pass
