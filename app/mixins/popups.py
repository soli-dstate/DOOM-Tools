"""PopupsMixin — App methods for the "popups" feature area."""
from app.foundation import *


class PopupsMixin:

    def _center_popup_on_window(self, popup, width = None, height = None):

        try:
            popup.update_idletasks()

            if width is None:
                width = popup.winfo_reqwidth()
            if height is None:
                height = popup.winfo_reqheight()

            root_x = self.root.winfo_x()
            root_y = self.root.winfo_y()
            root_width = self.root.winfo_width()
            root_height = self.root.winfo_height()

            x = root_x +(root_width //2)-(width //2)
            y = root_y +(root_height //2)-(height //2)

            # Clamp to the monitor the main window is on (not just the primary
            # display) so popups stay on the correct screen in multi-monitor setups.
            mon_left, mon_top, mon_w, mon_h = self._get_window_monitor_rect(self.root)
            x = max(mon_left, min(x, mon_left + mon_w - width))
            y = max(mon_top, min(y, mon_top + mon_h - height))

            logging.debug(f"_center_popup_on_window: root=({root_x},{root_y},{root_width},{root_height}) "
                          f"monitor=({mon_left},{mon_top},{mon_w},{mon_h}) popup={width}x{height}+{x}+{y}")
            popup.geometry(f"{width}x{height}+{x}+{y}")

            # Tk's window coordinates can be skewed across monitors (mixed-DPI),
            # and an un-positioned Toplevel defaults to the PRIMARY monitor. Once
            # the popup is realized, re-place it physically with Win32 GetWindowRect
            # + SetWindowPos (true screen pixels) so it lands on the main window's
            # monitor regardless of what Tk reports.
            try:
                popup.after(0, lambda p = popup: self._reposition_popup_win32(p))
            except Exception:
                pass
        except Exception:

            try:
                popup.geometry("+100+100")
            except Exception:
                pass

    def _reposition_popup_win32(self, popup):
        """Center `popup` on the main window's monitor using raw Win32 calls.

        Reads true physical screen rectangles via GetWindowRect (for both the
        main window and the popup) and moves the popup with SetWindowPos. This
        bypasses Tk/CTk coordinate reporting, which can place popups on the
        wrong monitor in multi-monitor / mixed-DPI setups. No-op off Windows.
        """
        if platform.system() != "Windows":
            return False
        try:
            if not popup.winfo_exists():
                return False
        except Exception:
            return False

        # Never move borderless full-screen overlays (flashbang/lightning) — they
        # are intentionally sized to span every monitor.
        try:
            if bool(popup.overrideredirect()):
                return False
        except Exception:
            pass

        try:
            user32 = ctypes.windll.user32

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

            user32.GetParent.restype = ctypes.c_void_p
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
            user32.GetWindowRect.restype = ctypes.c_int
            user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                            ctypes.c_int, ctypes.c_uint]

            def _top_hwnd(win):
                raw = ctypes.c_void_p(win.winfo_id())
                parent = user32.GetParent(raw)
                return ctypes.c_void_p(parent) if parent else raw

            root_hwnd = _top_hwnd(self.root)
            popup_hwnd = _top_hwnd(popup)

            rr = RECT()
            pr = RECT()
            if not user32.GetWindowRect(root_hwnd, ctypes.byref(rr)):
                return False
            if not user32.GetWindowRect(popup_hwnd, ctypes.byref(pr)):
                return False

            pw = pr.right - pr.left
            ph = pr.bottom - pr.top
            if pw <= 1 or ph <= 1:
                return False

            mon_left, mon_top, mon_w, mon_h = self._get_window_monitor_rect(self.root)

            # Only relocate popups that actually landed on a DIFFERENT monitor than
            # the main window. If the popup is already on the correct monitor, leave
            # its position untouched so intentionally-placed dialogs aren't disturbed.
            popup_cx = pr.left + (pr.right - pr.left) // 2
            popup_cy = pr.top + (pr.bottom - pr.top) // 2
            if (mon_left <= popup_cx < mon_left + mon_w
                    and mon_top <= popup_cy < mon_top + mon_h):
                return False

            cx = rr.left + (rr.right - rr.left) // 2
            cy = rr.top + (rr.bottom - rr.top) // 2
            x = cx - (pw // 2)
            y = cy - (ph // 2)

            x = max(mon_left, min(x, mon_left + mon_w - pw))
            y = max(mon_top, min(y, mon_top + mon_h - ph))

            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            user32.SetWindowPos(popup_hwnd, None, int(x), int(y), 0, 0,
                                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
            logging.debug(f"_reposition_popup_win32: root_rect=({rr.left},{rr.top},{rr.right},{rr.bottom}) "
                          f"popup={pw}x{ph} monitor=({mon_left},{mon_top},{mon_w},{mon_h}) -> +{x}+{y}")
            return True
        except Exception:
            logging.exception("_reposition_popup_win32 failed")
            return False

    def _popup_show_info(self, title, message, sound = "popup"):
        self._play_ui_sound(sound)

        try:
            theme = customtkinter.ThemeManager.theme
            toplevel_fg = theme.get("CTkToplevel", {}).get("fg_color")
            label_text_color = theme.get("CTkLabel", {}).get("text_color")
            button_fg = theme.get("CTkButton", {}).get("fg_color")
            button_text = theme.get("CTkButton", {}).get("text_color")
        except Exception:
            toplevel_fg = None
            label_text_color = None
            button_fg = None
            button_text = None

        if toplevel_fg:
            popup = customtkinter.CTkToplevel(self.root, fg_color = toplevel_fg)
        else:
            popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.transient(self.root)

        try:
            screen_w = self.root.winfo_screenwidth()
            wraplength = min(1000, max(300, screen_w -200))
        except Exception:
            wraplength = 400

        label_kwargs = {"text":message, "wraplength":wraplength, "font":customtkinter.CTkFont(size = 13)}
        if label_text_color:
            label_kwargs["text_color"]= label_text_color
        label = customtkinter.CTkLabel(popup, **label_kwargs)
        label.pack(pady = 30, padx = 20)

        def close_popup():
            self._play_ui_sound("click")
            popup.destroy()

        btn_kwargs = {"text":"OK", "command":close_popup, "width":120, "height":35}
        if button_fg:
            btn_kwargs["fg_color"]= button_fg
        if button_text:
            btn_kwargs["text_color"]= button_text
        ok_button = customtkinter.CTkButton(popup, **btn_kwargs)
        ok_button.pack(pady = 10)

        popup.update_idletasks()

        try:
            req_w = popup.winfo_reqwidth()
            req_h = popup.winfo_reqheight()
            screen_w = popup.winfo_screenwidth()
            screen_h = popup.winfo_screenheight()
            max_w = max(200, screen_w -100)
            max_h = max(150, screen_h -100)
            final_w = min(req_w, max_w)
            final_h = min(req_h, max_h)
            self._center_popup_on_window(popup, final_w, final_h)
        except Exception:
            try:
                popup.geometry("+100+100")
            except Exception:
                pass

        popup.deiconify()
        popup.grab_set()
        popup.lift()
        self._safe_focus(popup)

    def _popup_progress(self, title, message):

        self._play_ui_sound("popup")
        try:
            theme = customtkinter.ThemeManager.theme
            toplevel_fg = theme.get("CTkToplevel", {}).get("fg_color")
            label_text_color = theme.get("CTkLabel", {}).get("text_color")
        except Exception:
            toplevel_fg = None
            label_text_color = None

        if toplevel_fg:
            popup = customtkinter.CTkToplevel(self.root, fg_color = toplevel_fg)
        else:
            popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("450x120")
        popup.transient(self.root)

        label_kwargs = {"text":message, "wraplength":400, "font":customtkinter.CTkFont(size = 13)}
        if label_text_color:
            label_kwargs["text_color"]= label_text_color
        label = customtkinter.CTkLabel(popup, **label_kwargs)
        label.pack(pady = 20, padx = 20)

        def update(text):
            try:
                label.configure(text = text)
                popup.update_idletasks()
            except Exception:
                pass

        def close():
            try:
                self._play_ui_sound("click")
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass

        self._center_popup_on_window(popup, 450, 120)
        popup.deiconify()
        popup.lift()
        return {"update":update, "close":close, "popup":popup}

    def _create_action_minigame_popup(self, title, cause_text, key_count = 6):

        import threading as _mg_threading

        completed = _mg_threading.Event()

        self._play_ui_sound("popup")
        try:
            theme = customtkinter.ThemeManager.theme
            toplevel_fg = theme.get("CTkToplevel", {}).get("fg_color")
            label_text_color = theme.get("CTkLabel", {}).get("text_color")
        except Exception:
            toplevel_fg = None
            label_text_color = None

        if toplevel_fg:
            popup = customtkinter.CTkToplevel(self.root, fg_color = toplevel_fg)
        else:
            popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("450x310")
        popup.transient(self.root)

        label_kwargs_base = {}
        if label_text_color:
            label_kwargs_base["text_color"] = label_text_color

        cause_label = customtkinter.CTkLabel(
            popup, text = cause_text, wraplength = 400,
            font = customtkinter.CTkFont(size = 12), **label_kwargs_base
        )
        cause_label.pack(pady = (10, 5), padx = 20)

        status_label = customtkinter.CTkLabel(
            popup, text = "", wraplength = 400,
            font = customtkinter.CTkFont(size = 13), **label_kwargs_base
        )
        status_label.pack(pady = 5, padx = 20)

        progress_bar = customtkinter.CTkProgressBar(popup, width = 380, height = 14)
        progress_bar.pack(pady = (2, 5), padx = 30)
        progress_bar.set(0.0)

        sep = customtkinter.CTkFrame(popup, height = 2, fg_color = "gray50")
        sep.pack(fill = "x", padx = 30, pady = 5)

        key_pool = ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "A", "S", "D", "F", "G", "H", "J", "K", "L", "Z", "X", "C", "V", "B", "N", "M"]
        keys = [random.choice(key_pool) for _ in range(key_count)]
        current_index = [0]

        _button_sounds = []
        try:
            import os as _mg_os
            for bn in ("button0.ogg", "button1.ogg", "button2.ogg"):
                bp = _mg_os.path.join("sounds", "firearms", "universal", bn)
                if _mg_os.path.exists(bp):
                    _button_sounds.append(bp)
        except Exception:
            pass

        mg_header = customtkinter.CTkLabel(
            popup, text = "Press the keys in order to skip waiting:",
            font = customtkinter.CTkFont(size = 11), **label_kwargs_base
        )
        mg_header.pack(pady = (5, 2))

        key_display = customtkinter.CTkLabel(
            popup, text = f"[ {keys[0]} ]",
            font = customtkinter.CTkFont(size = 24, weight = "bold"), **label_kwargs_base
        )
        key_display.pack(pady = 5)

        progress_parts = []
        for i, k in enumerate(keys):
            progress_parts.append(f"[{k}]")
        progress_label = customtkinter.CTkLabel(
            popup, text = " ".join(progress_parts),
            font = customtkinter.CTkFont(size = 11), **label_kwargs_base
        )
        progress_label.pack(pady = 2)

        def _on_minigame_key(event):
            if completed.is_set():
                return
            ch = (event.char or "").upper()
            if not ch:
                return
            idx = current_index[0]
            if idx < len(keys) and ch == keys[idx]:
                try:
                    if _button_sounds:
                        self._safe_sound_play("", random.choice(_button_sounds))
                    else:
                        self._play_ui_sound("click")
                except Exception:
                    pass
                current_index[0] += 1
                idx = current_index[0]
                if idx >= len(keys):
                    completed.set()
                    try:
                        key_display.configure(text = "Done!")
                        progress_label.configure(text = " ".join("\u2713" for _ in keys))
                        progress_bar.set(1.0)
                    except Exception:
                        pass
                else:
                    try:
                        key_display.configure(text = f"[ {keys[idx]} ]")
                        parts = []
                        for i, k in enumerate(keys):
                            parts.append("\u2713" if i < idx else f"[{k}]")
                        progress_label.configure(text = " ".join(parts))
                    except Exception:
                        pass

        popup.bind("<Key>", _on_minigame_key)

        self._center_popup_on_window(popup, 450, 310)
        popup.deiconify()
        popup.lift()
        try:
            popup.focus_force()
        except Exception:
            pass

        def update(text):
            try:
                status_label.configure(text = text)
                popup.update_idletasks()
            except Exception:
                pass

        def close():
            try:
                self._play_ui_sound("click")
            except Exception:
                pass
            try:
                popup.destroy()
            except Exception:
                pass

        def set_progress(value):
            try:
                progress_bar.set(max(0.0, min(1.0, value)))
            except Exception:
                pass

        return {"update": update, "close": close, "popup": popup, "completed": completed, "set_progress": set_progress}

    def _interruptible_wait(self, completed_event, duration, progress_callback = None):

        start_time = time.time()
        end_time = start_time + duration
        while time.time() < end_time:
            if completed_event.is_set():
                if progress_callback:
                    try:
                        self.root.after(0, lambda: progress_callback(1.0))
                    except Exception:
                        pass
                return True
            if progress_callback:
                elapsed = time.time() - start_time
                frac = min(1.0, elapsed / duration) if duration > 0 else 1.0
                try:
                    self.root.after(0, lambda f = frac: progress_callback(f))
                except Exception:
                    pass
            time.sleep(0.05)
        if progress_callback:
            try:
                self.root.after(0, lambda: progress_callback(1.0))
            except Exception:
                pass
        return False

    def _popup_confirm(self, title, message, on_confirm):
        self._play_ui_sound("popup")
        popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("450x220")
        popup.transient(self.root)

        label = customtkinter.CTkLabel(popup, text = message, wraplength = 400, font = customtkinter.CTkFont(size = 13))
        label.pack(pady = 30, padx = 20)

        button_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
        button_frame.pack(pady = 10)

        def confirm():
            self._play_ui_sound("click")
            popup.destroy()

            try:
                on_confirm(True)
            except TypeError:
                on_confirm()

        def cancel():
            self._play_ui_sound("click")
            popup.destroy()

            try:
                on_confirm(False)
            except TypeError:
                pass

        yes_button = customtkinter.CTkButton(button_frame, text = "Yes", command = confirm, width = 120, height = 35)
        yes_button.pack(side = "left", padx = 10)
        no_button = customtkinter.CTkButton(button_frame, text = "No", command = cancel, width = 120, height = 35)
        no_button.pack(side = "left", padx = 10)

        self._center_popup_on_window(popup, 450, 220)
        popup.deiconify()
        popup.lift()
        try:
            self._safe_focus(popup)
        except Exception:
            pass
        try:
            popup.grab_set()
        except Exception:
            pass
        try:
            popup.wait_window()
        except Exception:
            pass

    def _popup_ask_integer(self, title, prompt, initial_value = 1, min_value = 1, max_value = 100, on_result = None):

        self._play_ui_sound("popup")
        popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("400x180")
        popup.transient(self.root)

        label = customtkinter.CTkLabel(popup, text = prompt, wraplength = 380, font = customtkinter.CTkFont(size = 13))
        label.pack(pady =(16, 8), padx = 16)

        input_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
        input_frame.pack(fill = "x", padx = 16, pady =(0, 8))

        try:
            iv = int(initial_value)
        except Exception:
            iv = min_value
        if iv <min_value:
            iv = min_value
        if iv >max_value:
            iv = max_value

        value_var = customtkinter.StringVar(value = str(iv))

        entry = customtkinter.CTkEntry(input_frame, width = 80, textvariable = value_var)
        entry.pack(side = "left", padx =(0, 10))

        slider = None
        _syncing = [False]
        if max_value >min_value:

            steps = max_value -min_value
            slider = customtkinter.CTkSlider(
            input_frame,
            from_ = min_value,
            to = max_value,
            number_of_steps = steps,
            width = 200
            )
            slider.set(iv)
            slider.pack(side = "left", fill = "x", expand = True)

            def _on_slider_change(val):
                if _syncing[0]:
                    return
                _syncing[0] = True
                try:
                    value_var.set(str(int(round(float(val)))))
                except Exception:
                    pass
                _syncing[0] = False
            slider.configure(command = _on_slider_change)

            def _on_entry_change(*_args):
                if _syncing[0]:
                    return
                _syncing[0] = True
                try:
                    v = int(value_var.get())
                    if v < min_value:
                        v = min_value
                    elif v > max_value:
                        v = max_value
                    slider.set(v)
                except (ValueError, TypeError):
                    pass
                _syncing[0] = False
            value_var.trace_add("write", _on_entry_change)

        min_label = customtkinter.CTkLabel(input_frame, text = f"({min_value}-{max_value})", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        min_label.pack(side = "left", padx =(10, 0))

        result:dict = {"value":None}

        def validate_and_confirm():
            try:
                val = int(value_var.get())
                if val <min_value:
                    val = min_value
                elif val >max_value:
                    val = max_value
                result["value"]= val
                self._play_ui_sound("click")
                popup.destroy()
                if on_result:
                    on_result(val)
            except(ValueError, TypeError):
                self._popup_show_info("Invalid Input", "Please enter a valid number")

        def cancel():
            self._play_ui_sound("click")
            result["value"]= None
            popup.destroy()
            if on_result:
                on_result(None)

        button_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
        button_frame.pack(pady =(8, 12))

        ok_btn = customtkinter.CTkButton(button_frame, text = "OK", command = validate_and_confirm, width = 120, height = 34)
        ok_btn.pack(side = "left", padx = 8)

        cancel_btn = customtkinter.CTkButton(button_frame, text = "Cancel", command = cancel, width = 120, height = 34, fg_color = "#444444")
        cancel_btn.pack(side = "left", padx = 8)

        entry.bind("<Return>", lambda e:validate_and_confirm())
        popup.bind("<Escape>", lambda e:cancel())

        self._center_popup_on_window(popup, 400, 180)
        popup.deiconify()
        popup.lift()
        popup.grab_set()
        self._safe_focus(entry)

        if on_result is None:

            popup.wait_window()
            return result.get("value")

    def _popup_select_option(self, title, prompt, options):

        self._play_ui_sound("popup")
        popup = customtkinter.CTkToplevel(self.root)
        popup.title(title)
        popup.geometry("480x160")
        popup.transient(self.root)

        label = customtkinter.CTkLabel(popup, text = prompt, wraplength = 440, font = customtkinter.CTkFont(size = 13))
        label.pack(pady =(16, 8), padx = 16)

        sel_var = customtkinter.StringVar(value =(options[0]if options else ""))
        opt = customtkinter.CTkOptionMenu(popup, values = options, variable = sel_var)
        opt.pack(pady =(0, 12), padx = 16, fill = "x")

        result = {"value":None}

        def confirm():
            try:
                self._play_ui_sound("click")
            except Exception:
                pass
            result["value"]= sel_var.get()# type: ignore
            popup.destroy()

        def cancel():
            try:
                self._play_ui_sound("click")
            except Exception:
                pass
            result["value"]= None
            popup.destroy()

        button_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
        button_frame.pack(pady =(4, 12))
        ok_btn = customtkinter.CTkButton(button_frame, text = "OK", command = confirm, width = 120, height = 34)
        ok_btn.pack(side = "left", padx = 8)
        cancel_btn = customtkinter.CTkButton(button_frame, text = "Cancel", command = cancel, width = 120, height = 34)
        cancel_btn.pack(side = "left", padx = 8)

        self._center_popup_on_window(popup, 480, 160)
        popup.deiconify()
        popup.lift()

        popup.grab_set()
        popup.wait_window()
        return result.get("value")
