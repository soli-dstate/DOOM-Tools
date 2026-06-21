"""UiMixin — App methods for the "ui" feature area."""
from app.foundation import *
import logging


class UiMixin:

    def _format_item_name(self, item):
        try:
            if not isinstance(item, dict):
                return str(item)
            base = item.get('name', 'Unknown')
            arm = item.get('_from_armory')
            if arm:
                return f"{base}(Armory: {arm})"
            return base
        except Exception:
            try:
                return item.get('name', 'Unknown')
            except Exception:
                return 'Unknown'
    def _safe_focus(self, widget):

        try:
            if widget and getattr(widget, 'winfo_exists', lambda:False)():
                try:
                    widget.focus()
                except Exception:
                    try:
                        widget.focus_set()
                    except Exception:
                        logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Suppressed exception")
    def _setup_drag_drop(self):
        """Register the root window to accept file drops.

        Uses tkinterdnd2 when available — its callbacks fire through Tk's binding
        system (same path as button-click events) and are safe in Python 3.13
        free-threaded builds.  Falls back to ctypes WM_DROPFILES subclassing on
        older Python builds where tkinterdnd2 is not installed.
        """
        if platform.system() != "Windows":
            return

        # ── Primary: tkinterdnd2 (Python 3.13t-safe) ──────────────────────────
        try:
            # _require lives in tkinterdnd2.TkinterDnD, not the top-level package.
            # It monkey-patches dnd_bind / drop_target_register onto tkinter.BaseWidget
            # and loads the native TkDND Tcl extension into the interpreter.
            from tkinterdnd2.TkinterDnD import _require as _tkdnd_require
            import tkinterdnd2 as _tkdnd

            _tkdnd_require(self.root)

            def _on_tkdnd_drop(event):
                try:
                    # event.data is a Tcl list string; splitlist handles
                    # brace-quoted paths that contain spaces.
                    raw = getattr(event, 'data', '') or ''
                    paths = list(self.root.tk.splitlist(raw))
                    if paths:
                        self._handle_dropped_files(paths)
                except Exception:
                    logging.exception("Drag-drop tkdnd handler error")
                return _tkdnd.COPY

            # Keep a persistent reference so Tcl callback bindings remain valid.
            self._tkdnd_drop_handler = _on_tkdnd_drop

            # Bind all compatible live widgets so menu rebuilds don't break DnD.
            bound_widgets = []
            queue = [self.root]
            seen = set()
            while queue:
                w = queue.pop(0)
                try:
                    wid = str(w)
                    if wid in seen:
                        continue
                    seen.add(wid)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    if hasattr(w, 'drop_target_register') and hasattr(w, 'dnd_bind') and w.winfo_exists():
                        w.drop_target_register(_tkdnd.DND_FILES)
                        w.dnd_bind('<<Drop>>', self._tkdnd_drop_handler)
                        bound_widgets.append(w)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    for _child in w.winfo_children():
                        queue.append(_child)
                except Exception:
                    logging.exception("Suppressed exception")

            if not bound_widgets:
                raise RuntimeError("tkinterdnd2 loaded but no compatible Tk widget found for DnD binding")

            logging.info("Drag-and-drop registered via tkinterdnd2 on %d widget(s); primary=%s", len(bound_widgets), bound_widgets[0])
            return
        except Exception as exc:
            logging.warning("tkinterdnd2 unavailable (%s); falling back to ctypes WM_DROPFILES.", exc)

        # ctypes callback fallback is unsafe on Python 3.13 free-threaded
        # builds (PyEval_RestoreThread(NULL) crashes). Disable it there.
        try:
            if hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled():
                logging.error("Drag-and-drop disabled: ctypes WM_DROPFILES fallback is unsafe on free-threaded Python; install/use tkinterdnd2 path.")
                return
        except Exception:
            logging.exception("Suppressed exception")

        # ── Fallback: ctypes WM_DROPFILES window-procedure subclassing ────────
        # NOTE: This path crashes on Python 3.13 free-threaded builds because
        # WINFUNCTYPE callbacks invoke Python via PyGILState_Ensure() while the
        # main thread is in Py_BEGIN_ALLOW_THREADS inside Tcl's event loop.
        # Install tkinterdnd2 to use the safe path above.
        try:
            WM_DROPFILES = 0x0233
            GWL_WNDPROC = -4
            GA_ROOT = 2

            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32

            # 64-bit-safe WNDPROC signature: LRESULT, HWND, UINT, WPARAM, LPARAM
            _WNDPROC = ctypes.WINFUNCTYPE(
                ctypes.c_longlong,
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_uint64,
                ctypes.c_int64,
            )

            user32.GetWindowLongPtrW.restype = ctypes.c_void_p
            user32.GetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int]
            user32.SetWindowLongPtrW.restype = ctypes.c_void_p
            user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
            user32.CallWindowProcW.restype = ctypes.c_longlong
            user32.CallWindowProcW.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p,
                ctypes.c_uint, ctypes.c_uint64, ctypes.c_int64,
            ]
            user32.GetAncestor.restype = ctypes.c_void_p
            user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            shell32.DragAcceptFiles.argtypes = [ctypes.c_void_p, ctypes.c_bool]
            shell32.DragQueryFileW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
            shell32.DragQueryFileW.restype = ctypes.c_uint
            shell32.DragFinish.argtypes = [ctypes.c_void_p]

            wid = self.root.winfo_id()
            hwnd = user32.GetAncestor(wid, GA_ROOT)
            if not hwnd:
                hwnd = wid
            shell32.DragAcceptFiles(hwnd, True)

            try:
                MSGFLT_ALLOW = 1
                user32.ChangeWindowMessageFilterEx(hwnd, WM_DROPFILES, MSGFLT_ALLOW, None)
                user32.ChangeWindowMessageFilterEx(hwnd, 0x0049, MSGFLT_ALLOW, None)
            except Exception:
                logging.exception("Suppressed exception")

            _old_proc = user32.GetWindowLongPtrW(hwnd, GWL_WNDPROC)
            _active = [True]
            WM_NCDESTROY = 0x0082

            def _unsubclass():
                if not _active[0]:
                    return
                _active[0] = False
                try:
                    user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, _old_proc)
                except Exception:
                    logging.exception("Suppressed exception")

            def _wndproc(hwnd_inner, msg, wparam, lparam):
                try:
                    if msg == WM_NCDESTROY:
                        _unsubclass()
                        return user32.CallWindowProcW(_old_proc, hwnd_inner, msg, wparam, lparam)
                    if not _active[0]:
                        return user32.CallWindowProcW(_old_proc, hwnd_inner, msg, wparam, lparam)
                    if msg == WM_DROPFILES:
                        h_drop = wparam
                        count = shell32.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
                        paths = []
                        for i in range(count):
                            sz = shell32.DragQueryFileW(h_drop, i, None, 0) + 1
                            buf = ctypes.create_unicode_buffer(sz)
                            shell32.DragQueryFileW(h_drop, i, buf, sz)
                            paths.append(buf.value)
                        shell32.DragFinish(h_drop)
                        captured = list(paths)
                        self.root.after(0, lambda p=captured: self._handle_dropped_files(p))
                        return 0
                    return user32.CallWindowProcW(_old_proc, hwnd_inner, msg, wparam, lparam)
                except Exception:
                    try:
                        return user32.CallWindowProcW(_old_proc, hwnd_inner, msg, wparam, lparam)
                    except Exception:
                        return 0

            self._dnd_wndproc_ref = _WNDPROC(_wndproc)
            self._dnd_unsubclass = _unsubclass
            user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC, self._dnd_wndproc_ref)

            def _on_root_destroy(event=None):
                if event is None or event.widget is self.root:
                    _unsubclass()
            self.root.bind("<Destroy>", _on_root_destroy, add="+")

            logging.info("Drag-and-drop registered via ctypes WM_DROPFILES.")
        except Exception as exc:
            logging.warning("Could not register drag-and-drop handler: %s", exc)

    def _handle_dropped_files(self, paths):
        """Route dropped files to their appropriate directories based on extension."""
        lc_ext = global_variables.get("lootcrate_extension", ".sldlct")
        el_ext = global_variables.get("enemyloot_extension", ".sldenlt")
        _sv_folder = saves_folder if 'saves_folder' in globals() and saves_folder else "saves"
        ext_routes = {
            lc_ext: ("lootcrates", "Loot Crate"),
            el_ext: ("enemyloot", "Enemy Loot"),
            ".sldtrf": ("transfers", "Transfer File"),
            ".sldsv": (_sv_folder, "Character Save"),
            ".sldtbl": ("tables", "Table File"),
        }
        results = []
        moved_exts = set()
        for src_path in paths:
            ext = os.path.splitext(src_path)[1].lower()
            if ext not in ext_routes:
                results.append(f"\u2022 {os.path.basename(src_path)} \u2014 unrecognised type, skipped")
                continue
            dest_dir, label = ext_routes[ext]
            try:
                os.makedirs(dest_dir, exist_ok = True)
                dest_name = os.path.basename(src_path)
                dest_path = os.path.join(dest_dir, dest_name)
                if os.path.abspath(src_path) == os.path.abspath(dest_path):
                    results.append(f"\u2022 {dest_name} \u2014 already in {dest_dir}/")
                    continue
                shutil.move(src_path, dest_path)
                moved_exts.add(ext)
                results.append(f"\u2022 {dest_name} \u2192 {dest_dir}/ ({label})")
                logging.info("Drag-drop: moved '%s' -> '%s'", src_path, dest_path)
            except Exception as exc:
                results.append(f"\u2022 {os.path.basename(src_path)} \u2014 error: {exc}")
                logging.error("Drag-drop move failed '%s': %s", src_path, exc)
        if results:
            self._popup_show_info("Files Received", "\n".join(results))

        try:
            refresh_cfg = getattr(self, "_dnd_refresh_handler", None)
            if isinstance(refresh_cfg, dict) and moved_exts:
                cb = refresh_cfg.get("callback")
                exts = refresh_cfg.get("exts")
                if callable(cb):
                    if not exts or moved_exts.intersection(exts):
                        self.root.after(50, cb)
        except Exception:
            logging.exception("Drag-drop refresh callback failed")

    def _set_dnd_refresh_handler(self, callback = None, exts = None):
        """Set a menu-scoped callback invoked after successful drag-drop moves.

        exts: iterable of file extensions (e.g. ['.sldlct']). If omitted, callback
        runs after any moved file type.
        """
        try:
            ext_set = set()
            if exts:
                for e in exts:
                    if not e:
                        continue
                    ext_set.add(str(e).lower())
            self._dnd_refresh_handler = {"callback": callback, "exts": ext_set}
        except Exception:
            self._dnd_refresh_handler = {"callback": None, "exts": set()}

    def _get_window_monitor_rect(self, win = None):
        """Return (left, top, width, height) of the monitor containing `win`.

        Used so popups land on the same monitor as the main window instead of
        always snapping to the primary display. Detection uses the window's
        real HWND (MonitorFromWindow) — the same authoritative call CustomTkinter
        uses for DPI — so it does not depend on Tk coordinate reporting.

        On failure it falls back to the FULL virtual desktop (all monitors), not
        the primary monitor, so a detection hiccup never force-pins popups back
        to the primary display.
        """
        win = win or self.root

        if platform.system() == "Windows":
            try:
                MONITOR_DEFAULTTONEAREST = 2

                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                                ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]

                user32 = ctypes.windll.user32
                user32.GetParent.restype = ctypes.c_void_p
                user32.GetParent.argtypes = [ctypes.c_void_p]
                user32.MonitorFromWindow.restype = ctypes.c_void_p
                user32.MonitorFromWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                user32.GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)]

                win.update_idletasks()
                raw_id = ctypes.c_void_p(win.winfo_id())
                parent = user32.GetParent(raw_id)
                hwnd = ctypes.c_void_p(parent) if parent else raw_id

                hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                if hmon and user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                    r = mi.rcMonitor
                    w = r.right - r.left
                    h = r.bottom - r.top
                    if w > 0 and h > 0:
                        logging.debug(f"_get_window_monitor_rect: monitor=({r.left},{r.top},{w},{h})")
                        return (r.left, r.top, w, h)
            except Exception:
                logging.exception("_get_window_monitor_rect failed; using virtual screen")

        # Fallback: whole virtual desktop, so we never snap a popup to primary.
        return self._get_virtual_screen_rect()

    def _get_virtual_screen_rect(self):
        """Return (left, top, width, height) spanning ALL monitors.

        A single overrideredirect window using this geometry covers every
        display, so full-screen flashes (flashbang, lightning) hit both
        monitors at once. Falls back to the primary screen on failure.
        """
        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
                SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
                vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
                vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
                vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
                vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
                if vw > 0 and vh > 0:
                    return (vx, vy, vw, vh)
            except Exception:
                logging.exception("Suppressed exception")

        try:
            return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        except Exception:
            return (0, 0, 1920, 1080)
    def _clear_window(self):
        for widget in self.root.winfo_children():
            try:

                if getattr(widget, "_is_dev_toolbar", False):
                    continue
                if getattr(widget, "_is_persistent_window", False):
                    continue
            except Exception:
                logging.exception("Suppressed exception")
            try:
                widget.destroy()
            except Exception:
                logging.exception("Suppressed exception")
        logging.debug("Cleared window called")
    def _build_main_menu(self):
        try:
            self._set_dnd_refresh_handler(None, [])
        except Exception:
            logging.exception("Suppressed exception")
        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        try:
            bug_report_button = self._create_sound_button(
                main_frame, "Report a Bug", self._open_bug_report,
                width = 130, height = 32, font = customtkinter.CTkFont(size = 13),
                state = "normal" if bugreport_is_configured() else "disabled")
            bug_report_button.place(x = 12, y = 12)
        except Exception:
            logging.exception("Failed to create bug report button")
        title_label = customtkinter.CTkLabel(main_frame, text = "DOOM Tools", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady = 20)
        try:
            title_label.bind("<Button-1>", lambda e=None:self._start_title_easter_egg(title_label))
        except Exception:
            logging.exception("Suppressed exception")
        version_label = customtkinter.CTkLabel(main_frame, text = f"Version: {version}", font = customtkinter.CTkFont(size = 16))
        version_label.pack()
        try:
            import webbrowser
            def _open_releases(ev = None):
                try:

                    if not getattr(self, '_update_available', False):
                        return
                    try:
                        self._version_flash_active = False
                    except Exception:
                        logging.exception("Suppressed exception")
                    webbrowser.open('https://github.com/soli-dstate/DOOM-Tools/releases')
                except Exception:
                    logging.exception('Failed to open releases')

            version_label.bind("<Button-1>", _open_releases)
        except Exception:
            logging.exception("Suppressed exception")
        try:
            threading.Thread(target = lambda:self._check_remote_version(version_label), daemon = True).start()
        except Exception:
            logging.exception("Suppressed exception")
        current_character = customtkinter.CTkLabel(main_frame, text = f"Current Character: {self.currentsave if self.currentsave else 'None'}", font = customtkinter.CTkFont(size = 14))
        current_character.pack(pady = 10)
        current_table = customtkinter.CTkLabel(main_frame, text = f"Current Data Table: {global_variables.get('current_table', 'Default')}", font = customtkinter.CTkFont(size = 14))
        current_table.pack(pady = 5)
        loot_button = self._create_sound_button(main_frame, "Looting", self._open_loot_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled"if self.currentsave is None else "normal")
        loot_button.pack(pady = 10)
        business_button = self._create_sound_button(main_frame, "Businesses", self._open_business_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled"if self.currentsave is None else "normal")
        business_button.pack(pady = 10)
        inventoryman_button = self._create_sound_button(main_frame, "Inventory Manager", self._open_inventory_manager_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        inventoryman_button.pack(pady = 10)
        combatmode_button = self._create_sound_button(main_frame, "Combat Mode", self._open_combat_mode_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled"if self.currentsave is None else "normal")
        combatmode_button.pack(pady = 10)
        exitb_button = self._create_sound_button(main_frame, "Exit", self._safe_exit, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        exitb_button.pack(pady = 10)
        settings_button = self._create_sound_button(main_frame, "Settings", self._open_settings, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "normal")
        settings_button.pack(pady = 10)

        try:
            tbl_addl = globals().get('table_data', {}).get('additional_settings', {})
            combat_reports_enabled = bool(tbl_addl.get('combat_reports'))
        except Exception:
            combat_reports_enabled = False
        combat_reports_button = self._create_sound_button(main_frame, "Combat Reports", self._open_combat_reports_menu, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "normal"if combat_reports_enabled else "disabled")
        combat_reports_button.pack(pady = 10)

        try:
            tbl_addl = globals().get('table_data', {}).get('additional_settings', {})
            crafting_enabled = bool(tbl_addl.get('crafting'))
        except Exception:
            crafting_enabled = False
        crafting_button = self._create_sound_button(main_frame, "Crafting", self._open_crafting_menu, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "normal"if crafting_enabled else "disabled")
        crafting_button.pack(pady = 10)
        if global_variables["devmode"]["value"]:
            devtools_button = self._create_sound_button(main_frame, "Developer Tools", self._open_dev_tools, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled"if self.currentsave is None else "normal")
            devtools_button.pack(pady = 10)
        else:
            devtools_button = customtkinter.CTkButton(main_frame, text = "Developer Tools", width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled")
            devtools_button.pack(pady = 10)
        if global_variables["dmmode"]["value"]:
            dmmode_button = self._create_sound_button(main_frame, "DM Tools", self._open_dm_tools, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled"if self.currentsave is None else "normal")
            dmmode_button.pack(pady = 10)
        else:
            dmmode_button = customtkinter.CTkButton(main_frame, text = "DM Tools", width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled")
            dmmode_button.pack(pady = 10)
        if self.currentsave is None:
            currentsave_label = customtkinter.CTkLabel(main_frame, text = "No save loaded.Please load a save to enable tools.", font = customtkinter.CTkFont(size = 14), text_color = "red")
            currentsave_label.pack(pady = 20)
        konami_sequence =["Up", "Up", "Down", "Down", "Left", "Right", "Left", "Right"]
        konami_progress =[0]
        konami_triggered =[False]
        def _konami_key_handler(event):
            if konami_triggered[0]:
                return
            if event.keysym ==konami_sequence[konami_progress[0]]:
                konami_progress[0]+=1
                if konami_progress[0]==len(konami_sequence):
                    konami_triggered[0]= True
                    try:
                        tbl = globals().get('table_data', {})
                        tbl_addl_konami = tbl.get('additional_settings', {}) if isinstance(tbl, dict) else {}
                        if not bool(tbl_addl_konami.get('hidden_code_enabled', False)):
                            logging.debug("Konami code entered but hidden_code_enabled is false for this table")
                            konami_triggered[0] = False
                            konami_progress[0] = 0
                            return
                        code = tbl_addl_konami.get('hidden_code', '')
                        logging.info("Hidden code: %s", code)
                    except Exception:
                        logging.exception("Failed to retrieve hidden_code")
                    try:
                        self._play_ui_sound("success")
                    except Exception:
                        logging.exception("Failed to play konami sound")
                    def _konami_download():
                        try:
                            url = 'https://raw.githubusercontent.com/soli-dstate/DOOM-Tools/master/remotedata/Charlotte%20Baker.sldsv'
                            resp = requests.get(url, timeout = 15)
                            if resp.status_code ==200:
                                os.makedirs('saves', exist_ok = True)
                                appdata_path = os.path.expandvars(r'%LOCALAPPDATA%\soli_dstate\DOOM-Tools\saves_backup')
                                os.makedirs(appdata_path, exist_ok = True)
                                dest = os.path.join(appdata_path, 'Charlotte Baker.sldsv')
                                with open(dest, 'wb')as f:
                                    f.write(resp.content)
                                logging.debug("Downloaded Charlotte Baker.sldsv to saves folder")
                            else:
                                logging.warning("Failed to download Charlotte Baker.sldsv(status %s)", resp.status_code)
                        except Exception:
                            logging.exception("Failed to download Charlotte Baker.sldsv")
                    threading.Thread(target = _konami_download, daemon = True).start()
            else:
                konami_progress[0]= 1 if event.keysym ==konami_sequence[0]else 0
        _konami_bind_id = self.root.bind("<Key>", _konami_key_handler, add = "+")
        def _konami_cleanup(event = None):
            try:
                self.root.unbind("<Key>", _konami_bind_id)
            except Exception:
                logging.exception("Suppressed exception")
        main_frame.bind("<Destroy>", _konami_cleanup, add = "+") # type: ignore

        try:
            self.root.after(50, self._setup_drag_drop)
        except Exception:
            logging.exception("Suppressed exception")

    def _copy_to_clipboard(self, text):
        if getattr(self, "_suppress_clipboard_copy", False):
            logging.info("Clipboard copy suppressed")
            return False
        try:
            pyperclip.copy(text)
            logging.info(f"Copied to clipboard: {text}")
            return True
        except Exception as e:
            logging.warning(f"Failed to copy to clipboard: {e}")
            return False
