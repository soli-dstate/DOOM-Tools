"""Composes the App class from its feature mixins."""
from app.foundation import *
from app.mixins.bugreport import BugreportMixin
from app.mixins.casino import CasinoMixin
from app.mixins.characters import CharactersMixin
from app.mixins.cloud import CloudMixin
from app.mixins.combat import CombatMixin
from app.mixins.combatmode import CombatmodeMixin
from app.mixins.dev import DevMixin
from app.mixins.dmtools import DmtoolsMixin
from app.mixins.gameplay import GameplayMixin
from app.mixins.inspect import InspectMixin
from app.mixins.inventory import InventoryMixin
from app.mixins.items import ItemsMixin
from app.mixins.loot import LootMixin
from app.mixins.marking import MarkingMixin
from app.mixins.popups import PopupsMixin
from app.mixins.reports import ReportsMixin
from app.mixins.saves import SavesMixin
from app.mixins.settings import SettingsMixin
from app.mixins.sound import SoundMixin
from app.mixins.store import StoreMixin
from app.mixins.ui import UiMixin
from app.mixins.updates import UpdatesMixin
from app.mixins.weapons import WeaponsMixin
import logging


class _ToastLogHandler(logging.Handler):
    """Pops a small dismissible toast for ERROR/CRITICAL log records, so an
    error is visible without having to look at the (now Textual-owned)
    terminal at all. Anchored to the single root window, so it shows up
    correctly regardless of which screen the app is currently displaying."""

    _COLORS = {"ERROR": ("#3a1a1a", "#e05a4a"), "CRITICAL": ("#3a0f0f", "#ff3b3b")}
    _MAX_VISIBLE = 4
    _DISMISS_AFTER_MS = 8000

    def __init__(self, root):
        super().__init__(level = logging.ERROR)
        self.root = root
        self._toasts = []

    def emit(self, record):
        try:
            message = record.getMessage()
        except Exception:
            return
        # logging fires from ANY thread (workers, audio, the log-view's own
        # thread) — never touch Tk state directly here, only ever schedule
        # it onto the main thread.
        try:
            self.root.after(0, lambda: self._show_toast(record.levelname, message))
        except Exception:
            pass

    def _show_toast(self, level, message):
        if not self.root.winfo_exists():
            return
        bg, border = self._COLORS.get(level, self._COLORS["ERROR"])
        frame = customtkinter.CTkFrame(self.root, fg_color = bg, border_color = border, border_width = 1, corner_radius = 8, width = 320)
        header = customtkinter.CTkFrame(frame, fg_color = "transparent")
        header.pack(fill = "x", padx = 8, pady = (6, 0))
        customtkinter.CTkLabel(header, text = level, text_color = border, font = ("", 12, "bold")).pack(side = "left")
        customtkinter.CTkButton(header, text = "✕", width = 20, height = 20, fg_color = "transparent", hover_color = bg, command = lambda: self._dismiss(frame)).pack(side = "right")
        customtkinter.CTkLabel(frame, text = message, wraplength = 300, justify = "left", anchor = "w").pack(fill = "x", padx = 8, pady = (2, 8))

        self._toasts.append(frame)
        while len(self._toasts) > self._MAX_VISIBLE:
            self._dismiss(self._toasts[0])
        self._reflow()
        try:
            self.root.after(self._DISMISS_AFTER_MS, lambda: self._dismiss(frame))
        except Exception:
            pass

    def _dismiss(self, frame):
        try:
            if frame in self._toasts:
                self._toasts.remove(frame)
            if frame.winfo_exists():
                frame.place_forget()
                frame.destroy()
        except Exception:
            pass
        self._reflow()

    def _reflow(self):
        y = 16
        for t in list(self._toasts):
            try:
                if not t.winfo_exists():
                    continue
                t.place(relx = 1.0, rely = 0.0, anchor = "ne", x = -16, y = y)
                t.update_idletasks()
                y += t.winfo_reqheight() + 10
            except Exception:
                continue


class App(BugreportMixin, CasinoMixin, CharactersMixin, CloudMixin, CombatMixin, CombatmodeMixin, DevMixin, DmtoolsMixin, GameplayMixin, InspectMixin, InventoryMixin, ItemsMixin, LootMixin, MarkingMixin, PopupsMixin, ReportsMixin, SavesMixin, SettingsMixin, SoundMixin, StoreMixin, UiMixin, UpdatesMixin, WeaponsMixin):

    PLATFORM_DEFAULTS = {
    "M203":{"ammo_type":"40mm_grenade", "capacity":1, "reload_sound_folder":"m203"}
    }
    currentsave = None
    def __init__(self):
        # Register this instance in the foundation module's globals so module-level
        # helpers (e.g. the dev console command loop) can reach the live App.
        try:
            import app.foundation as _foundation_mod
            _foundation_mod.app = self
        except Exception:
            logging.exception("Failed to register App instance on foundation module")

        # Diagnostic: record cloud-saves config so release-vs-local issues are
        # visible in the log (frozen builds set sys._MEIPASS; source mode does not).
        try:
            frozen = getattr(sys, "frozen", False)
            meipass = getattr(sys, "_MEIPASS", None)
            if cloud_is_configured():
                logging.info(f"Cloud saves configured (credentials from {_cloud_credentials_source()}; "
                             f"frozen={frozen}).")
            else:
                logging.warning(
                    "Cloud saves NOT configured: no Google credentials found "
                    f"(frozen={frozen}, _MEIPASS={meipass!r}). On a release build this means the "
                    "GDRIVE_CLIENT_ID/SECRET GitHub Actions secrets were missing at build time; "
                    "if frozen=False you are running from source, which never bundles credentials."
                )
        except Exception:
            logging.exception("Cloud config diagnostic failed")

        customtkinter.set_appearance_mode(appearance_settings["appearance_mode"])

        theme_name = appearance_settings["color_theme"]
        builtin_themes =["dark-blue", "blue", "green"]
        if theme_name not in builtin_themes:

            custom_theme_path = os.path.join(os.getcwd(), "themes", f"{theme_name}.json")
            if os.path.exists(custom_theme_path):
                customtkinter.set_default_color_theme(custom_theme_path)
            else:
                logging.warning(f"Custom theme '{custom_theme_path}' not found, falling back to dark-blue")
                appearance_settings["color_theme"]= "dark-blue"
                customtkinter.set_default_color_theme("dark-blue")
        else:
            customtkinter.set_default_color_theme(theme_name)

        try:
            import tkinter as _tk
            _orig_tk_report = getattr(_tk.Tk, 'report_callback_exception', None)
            def _tk_suppress(self, exc_type, exc_value, exc_tb):
                try:
                    msg = str(exc_value)
                    import re
                    if "invalid command name"in msg and("after"in msg or re.search(r'\d{6,}', msg)):
                        return
                except Exception:
                    logging.exception("Suppressed exception")
                if _orig_tk_report:
                    try:
                        return _orig_tk_report(self, exc_type, exc_value, exc_tb)
                    except Exception:
                        logging.exception("Suppressed exception")
            _tk.Tk.report_callback_exception = _tk_suppress
        except Exception:
            logging.exception("Suppressed exception")

        try:
            import re as _re_stderr
            _real_stderr = sys.stderr
            class _TclAfterFilter:
                def write(self, msg):
                    if msg and "invalid command name"in msg and("after"in msg or _re_stderr.search(r'\d{6,}', msg)):
                        return
                    _real_stderr.write(msg)
                def flush(self):
                    _real_stderr.flush()
                def __getattr__(self, name):
                    return getattr(_real_stderr, name)
            sys.stderr = _TclAfterFilter()
        except Exception:
            logging.exception("Suppressed exception")

        self.root = customtkinter.CTk()
        self.root.title("DOOM Tools")
        self.root.geometry(appearance_settings["resolution"])
        self.root.resizable(False, False)

        try:
            logging.getLogger().addHandler(_ToastLogHandler(self.root))
        except Exception:
            logging.exception("Failed to install error-toast log handler")

        # Multi-monitor support: auto-place every popup on the main window's
        # monitor. Patch CTkToplevel once so any dialog that defaults to the
        # primary display gets relocated after it is shown. Borderless overlays
        # (flashbang/lightning) and popups already on the correct monitor are
        # left untouched — see _reposition_popup_win32.
        try:
            if not getattr(customtkinter.CTkToplevel, "_doomtools_monitor_patch", False):
                _orig_ctk_toplevel_init = customtkinter.CTkToplevel.__init__
                _app_ref = self

                def _doomtools_toplevel_init(tl_self, *args, **kwargs):
                    _orig_ctk_toplevel_init(tl_self, *args, **kwargs)
                    try:
                        tl_self.after(0, lambda: _app_ref._reposition_popup_win32(tl_self))
                    except Exception:
                        logging.exception("Suppressed exception")

                customtkinter.CTkToplevel.__init__ = _doomtools_toplevel_init
                customtkinter.CTkToplevel._doomtools_monitor_patch = True
        except Exception:
            logging.exception("Failed to install multi-monitor popup patch")

        _original_report = self.root.report_callback_exception
        def _suppress_after_errors(exc_type, exc_value, exc_tb):
            msg = str(exc_value)
            try:
                import re
                if "invalid command name"in msg:
                    if re.search(r'"\d+(?:check_dpi_scaling|_click_animation|update)"', msg)or "after"in msg:
                        return
            except Exception:
                logging.exception("Suppressed exception")
            _original_report(exc_type, exc_value, exc_tb)
        self.root.report_callback_exception = _suppress_after_errors

        try:
            self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        except Exception:
            logging.exception("Suppressed exception")

        self.root.attributes('-fullscreen', appearance_settings.get("fullscreen", False))

        try:
            if appearance_settings.get("borderless")and not appearance_settings.get("fullscreen"):
                self.root.overrideredirect(True)
        except Exception:
            logging.exception("Suppressed exception")

        self._sound_cache = {}

        self._load_file(None)
        if persistentdata.get("last_loaded_save"):
            last_save_uuid = persistentdata["last_loaded_save"]
            last_save_name = persistentdata.get("save_uuids", {}).get(last_save_uuid)
            if not last_save_name:

                pattern = os.path.join(saves_folder or "saves", f"*_{last_save_uuid}.sldsv")
                matches = glob.glob(pattern)
                if matches:
                    last_save_name = os.path.basename(matches[0]).replace(f"_{last_save_uuid}.sldsv", "")
                    persistentdata["save_uuids"][last_save_uuid]= last_save_name
                    self._save_persistent_data()
                else:
                    logging.warning(f"Last save UUID {last_save_uuid} not found in save_uuids")
            if last_save_name:
                save_filename = f"{last_save_name}_{last_save_uuid}.sldsv"
                loaded_data = self._load_file(save_filename)
                if loaded_data:
                    current_table = global_variables.get('current_table')
                    save_table = loaded_data.get('_table')or loaded_data.get('table')

                    table_compatible = True
                    if current_table and save_table:
                        current_table_base = os.path.splitext(current_table)[0]
                        save_table_base = os.path.splitext(save_table)[0]
                        if current_table_base !=save_table_base and current_table !=save_table:
                            table_compatible = False
                            logging.warning(f"Last save '{save_filename}' uses table '{save_table}' but current table is '{current_table}'.Not auto-loading.")

                    if table_compatible:
                        try:
                            globals()['save_data']= loaded_data
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            self._current_save_data = loaded_data
                        except Exception:
                            logging.exception("Suppressed exception")
                        self.currentsave = save_filename.replace(".sldsv", "")
                        logging.info(f"Automatically loaded last save: {save_filename}")
                else:
                    logging.warning(f"Failed to load last save: {save_filename}")
        self._build_main_menu()

        try:
            self.root.after(600, self._maybe_prompt_cloud_restore)
        except Exception:
            logging.exception("Suppressed exception")

        # Auto-report uncaught tkinter errors, and detect a hard crash from the
        # previous session (then arm the sentinel for this one).
        try:
            self._install_exception_reporting()
        except Exception:
            logging.exception("Failed to install exception reporting")
        try:
            self._crash_check_and_arm()
        except Exception:
            logging.exception("Crash sentinel init failed")
        try:
            self.root.after(800, self._maybe_prompt_reporter_name)
        except Exception:
            logging.exception("Suppressed exception")

        try:
            if global_variables.get("devmode", {}).get("value"):
                try:
                    self._start_dev_stats_worker()
                except Exception:
                    logging.exception("Failed to initialize dev stats worker")
        except Exception:
            logging.exception("Suppressed exception")
        try:
            self._bg_pay_stop = threading.Event()
            _bg_stop = self._bg_pay_stop
            def _bg_pay_worker():
                _excluded_saves = {"persistent_data.sldsv", "settings.sldsv", "appearance_settings.sldsv", "dm_settings.sldsv"}
                try:
                    while not _bg_stop.is_set():
                        try:
                            saves_dir = saves_folder or 'saves'
                            pattern = os.path.join(saves_dir, "*_*.sldsv")
                            files = glob.glob(pattern)
                            for fpath in files:
                                if os.path.basename(fpath) in _excluded_saves:
                                    continue
                                try:
                                    data = self._read_save_from_path(fpath)
                                    if data:
                                        try:
                                            self._award_paychecks_for_save(data, fpath)
                                        except Exception:
                                            logging.exception('Error awarding paychecks for %s', fpath)
                                except Exception:
                                    logging.exception('Failed processing save for paychecks: %s', fpath)
                        except Exception:
                            logging.exception('Background paycheck loop error')
                        # Use Event.wait() not time.sleep(): Python 3.13 free-threaded
                        # GC stop-the-world crashes time.sleep() via PyEval_RestoreThread.
                        _bg_stop.wait(60)
                except BaseException:
                    logging.exception("Suppressed exception")
            threading.Thread(target = _bg_pay_worker, daemon = True).start()
        except Exception:
            logging.exception('Failed to start background paycheck worker')
        self.root.after(500, self._setup_drag_drop)

        # If the user quits the log view itself (ctrl+q in the terminal),
        # there's no console left to fall back to, so close the GUI too.
        # Route through _safe_exit() (not a bare root.destroy()) so autosave
        # and persistent-data saving still happen on that exit path.
        try:
            _logview_shutdown_event = globals().get('LOGVIEW_SHUTDOWN_EVENT')
            if _logview_shutdown_event is not None:
                def _poll_logview_shutdown():
                    if _logview_shutdown_event.is_set():
                        self._safe_exit()
                    else:
                        self.root.after(200, _poll_logview_shutdown)
                self.root.after(200, _poll_logview_shutdown)
        except Exception:
            logging.exception("Suppressed exception")

        self.root.mainloop()
        # mainloop() returned — either _safe_exit() already called os._exit(0),
        # or something caused mainloop to exit without it.  In either case, skip
        # Python's thread finalization (fatal on free-threaded Python 3.13 with
        # daemon threads blocked in C calls like time.sleep / input / network IO).
        try:
            os._exit(0)
        except Exception:
            logging.exception("Suppressed exception")
