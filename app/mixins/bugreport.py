"""BugreportMixin — submit in-app bug reports to GitHub issues via a relay.

The report (name, description and optionally the current session log) is POSTed
to a server-side relay (see tools/bugreport-relay/). The relay holds the GitHub
token and creates the issue + a Gist for the log, so no token ever lives on the
user's machine. The reporter name defaults to the Windows username and, once
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

    def _read_current_log_text(self):
        """Read the current session log, tail-capped to the payload limit."""
        try:
            path = globals().get("log_filename")
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
            logging.exception("Failed to read current log for bug report")
            return ""

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
        popup.geometry("520x560")
        popup.transient(self.root)

        customtkinter.CTkLabel(
            popup, text="Report a Bug",
            font=customtkinter.CTkFont(size=20, weight="bold")).pack(pady=(18, 4))
        customtkinter.CTkLabel(
            popup,
            text="This opens an issue on the DOOM-Tools GitHub repository.",
            font=customtkinter.CTkFont(size=12), text_color="gray").pack(pady=(0, 10))

        body = customtkinter.CTkFrame(popup, fg_color="transparent")
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
        desc_box = customtkinter.CTkTextbox(body, height=200, wrap="word")
        desc_box.pack(fill="both", expand=True, pady=(2, 12))

        include_log_var = customtkinter.BooleanVar(value=True)
        customtkinter.CTkCheckBox(
            body, text="Include the current log file (recommended)",
            variable=include_log_var).pack(anchor="w", pady=(0, 4))
        customtkinter.CTkLabel(
            body,
            text="The log helps diagnose the problem and is uploaded as a private Gist.",
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

            try:
                popup.destroy()
            except Exception:
                pass

            self._submit_bug_report(name or "Anonymous", description, log_text, log_name)

        self._create_sound_button(
            button_frame, "Submit", do_submit, width=160, height=38).pack(side="left", padx=8)
        self._create_sound_button(
            button_frame, "Cancel", lambda: popup.destroy(),
            width=160, height=38, fg_color="#444444").pack(side="left", padx=8)

        self._center_popup_on_window(popup, 520, 560)
        popup.deiconify()
        popup.lift()
        try:
            popup.grab_set()
            self._safe_focus(desc_box)
        except Exception:
            pass

    def _submit_bug_report(self, name, description, log_text, log_name):
        endpoint = bugreport_endpoint()
        payload = {
            "name": name,
            "description": description,
            "app_version": globals().get("version", "unknown"),
            "platform": f"{platform.system()} {platform.release()}",
        }
        if log_text:
            payload["log"] = log_text
            payload["log_filename"] = log_name

        def work():
            resp = requests.post(endpoint, json=payload, timeout=60)
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
