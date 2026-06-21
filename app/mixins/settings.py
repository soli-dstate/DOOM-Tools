"""SettingsMixin — App methods for the "settings" feature area."""
from app.foundation import *
import logging


class SettingsMixin:

    def _safe_exit(self):
        # Clean shutdown: clear the crash sentinel so this run isn't reported as
        # a hard crash on next launch. (os._exit below means atexit won't fire.)
        try:
            self._clear_crash_sentinel()
        except Exception:
            logging.exception("Suppressed exception")
        try:
            autosaved = False
            if self.currentsave is not None:

                try:
                    global_save = globals().get('save_data')
                    if isinstance(global_save, dict):
                        try:
                            self._save_file(global_save)
                            logging.info("Autosaved current save using globals()['save_data'].")
                            autosaved = True
                        except Exception as e:
                            logging.error(f"Autosave failed for globals()['save_data']: {e}")
                except Exception:
                    logging.exception("Suppressed exception")

                if not autosaved and hasattr(self, '_current_save_data')and isinstance(getattr(self, '_current_save_data'), dict):
                    try:
                        self._save_file(getattr(self, '_current_save_data'))
                        logging.info("Autosaved current save using self._current_save_data.")
                        autosaved = True
                    except Exception as e:
                        logging.error(f"Autosave failed for self._current_save_data: {e}")

                if not autosaved:
                    candidate_names =(
                    'current_save_data', '_current_save_data', 'save_data', '_save_data',
                    'current_data', 'data', '_data'
                    )
                    for name in candidate_names:
                        try:
                            if hasattr(self, name):
                                d = getattr(self, name)
                                if isinstance(d, dict):
                                    try:
                                        self._save_file(d)
                                        logging.info(f"Autosaved current save using attribute '{name}'.")
                                        autosaved = True
                                    except Exception as e:
                                        logging.error(f"Autosave failed using attribute '{name}': {e}")
                                    break
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue

                if not autosaved:
                    logging.info("Exiting with current save loaded(no in-memory autosave performed).")
            else:
                logging.info("No current save loaded at exit.")

            try:
                self._save_persistent_data()
            except Exception as e:
                logging.error(f"Failed to save persistent data on exit: {e}")

            try:
                self._cloud_sync_on_exit()
            except Exception as e:
                logging.error(f"Cloud sync on exit failed: {e}")

            logging.info("Program exited safely.")
        except Exception as e:
            logging.exception("Error during safe exit: %s", e)
        # Signal daemon worker threads to stop cleanly before os._exit fires
        try:
            getattr(self, '_bg_pay_stop', threading.Event()).set()
        except Exception:
            logging.exception("Suppressed exception")
        try:
            getattr(self, '_dev_worker_stop', threading.Event()).set()
            self._dev_worker_running = False
        except Exception:
            logging.exception("Suppressed exception")
        try:

            try:

                for w in list(self.root.winfo_children()):
                    try:
                        if getattr(w, 'grab_release', None):
                            w.grab_release()
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                def _cancel_all_after(widget):
                    try:
                        for after_id in widget.tk.eval('after info').split():
                            try:
                                widget.after_cancel(after_id)
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                _cancel_all_after(self.root)
            except Exception:
                logging.exception("Suppressed exception")

            self.root.quit()
            try:

                self.root.update()
            except Exception:
                logging.exception("Suppressed exception")
            try:

                for w in list(self.root.winfo_children()):
                    try:
                        w.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self.root.destroy()
            except Exception:
                logging.exception("Suppressed exception")
        except Exception:
            try:
                self.root.destroy()
            except Exception:
                logging.exception("Suppressed exception")

        try:
            pygame.mixer.quit()
        except Exception:
            logging.exception("Suppressed exception")
        try:
            pygame.quit()
        except Exception:
            logging.exception("Suppressed exception")

        # In free-threaded Python 3.13 (no-GIL build), any daemon thread blocked
        # in a C call (time.sleep, input, network IO) will crash the interpreter
        # with PyEval_RestoreThread(NULL) the moment Python tries to finalize it.
        # os._exit(0) skips all Python finalization entirely, killing daemon threads
        # at OS level before they can be touched by the interpreter.
        # This must come BEFORE root.destroy()/quit() so no thread finalization runs.
        try:
            os._exit(0)
        except Exception:
            logging.exception("Suppressed exception")

        try:

            try:

                for w in list(self.root.winfo_children()):
                    try:
                        if getattr(w, 'grab_release', None):
                            w.grab_release()
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                def _cancel_all_after(widget):
                    try:
                        for after_id in widget.tk.eval('after info').split():
                            try:
                                widget.after_cancel(after_id)
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                _cancel_all_after(self.root)
            except Exception:
                logging.exception("Suppressed exception")

            self.root.quit()
            try:

                self.root.update()
            except Exception:
                logging.exception("Suppressed exception")
            try:

                for w in list(self.root.winfo_children()):
                    try:
                        w.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self.root.destroy()
            except Exception:
                logging.exception("Suppressed exception")
        except Exception:
            try:
                self.root.destroy()
            except Exception:
                logging.exception("Suppressed exception")

        try:
            import os as _os, sys as _sys
            _os._exit(0)
        except Exception:
            logging.exception("Suppressed exception")

    def _on_window_close(self):

        logging.info("Window close requested; prompting for confirmation.")
        try:
            def on_confirm(result):
                if result:
                    try:
                        self._safe_exit()
                    except Exception:
                        logging.exception("Error while exiting via window close")

            self._popup_confirm(
            "Confirm Exit",
            "Do you want to exit? Any unsaved changes will be autosaved before exiting.",
            on_confirm
            )
        except Exception:
            logging.info("Window close attempted but confirmation unavailable; ignored.")
    def _open_settings(self):
        logging.info("Settings definition called")

        self._clear_window()

        appearance_settings_initial = appearance_settings.copy()
        global_variables_initial = {k:v.copy()if isinstance(v, dict)else v for k, v in global_variables.items()}
        settings_modified =[False]

        builtin_themes =["dark-blue", "blue", "green"]
        themes_dir = os.path.join(os.getcwd(), "themes")
        custom_theme_files =[]
        if os.path.isdir(themes_dir):
            custom_theme_files =[f for f in os.listdir(themes_dir)if f.endswith(".json")]
        theme_sources = {name:name for name in builtin_themes}
        for fname in custom_theme_files:
            name = os.path.splitext(fname)[0]
            theme_sources[name]= os.path.join(themes_dir, fname)
        available_theme_names = list(theme_sources.keys())
        if not available_theme_names:
            available_theme_names =["dark-blue"]
            theme_sources = {"dark-blue":"dark-blue"}

        def update_appearance():
            settings_modified[0]= True
            customtkinter.set_appearance_mode(appearance_settings["appearance_mode"])
            theme_key = appearance_settings.get("color_theme", "dark-blue")
            theme_target = theme_sources.get(theme_key, "dark-blue")
            try:
                customtkinter.set_default_color_theme(theme_target)
            except Exception as e:
                logging.warning(f"Failed to load theme '{theme_target}': {e}")
                appearance_settings["color_theme"]= "dark-blue"
                fallback = theme_sources.get("dark-blue", "dark-blue")
                try:
                    customtkinter.set_default_color_theme(fallback)
                except Exception as e2:
                    logging.error(f"Fallback theme load failed: {e2}")

            try:
                appearance_settings_path = os.path.join(saves_folder or "saves", "appearance_settings.sldsv")
                _signed_json_write(appearance_settings_path, appearance_settings)
                logging.info(f"Appearance settings saved to {appearance_settings_path}")
            except Exception as e:
                logging.error(f"Failed to save appearance settings: {e}")

            self._clear_window()
            self._open_settings()
            try:
                self.root.geometry(appearance_settings["resolution"])
            except Exception as e:
                logging.warning(f"Failed to apply resolution {appearance_settings['resolution']}: {e}")
            self.root.attributes('-fullscreen', appearance_settings.get("fullscreen", False))
            if appearance_settings.get("borderless", False):
                self.root.overrideredirect(True)
            else:
                self.root.overrideredirect(False)

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_columnconfigure((0, 1), weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        title = customtkinter.CTkLabel(main_frame, text = "Settings", font = customtkinter.CTkFont(size = 22, weight = "bold"))
        title.grid(row = 0, column = 0, columnspan = 2, pady =(0, 15))

        content = customtkinter.CTkFrame(main_frame)
        content.grid(row = 1, column = 0, columnspan = 2, sticky = "nsew")
        content.grid_columnconfigure((0, 1), weight = 1)

        appearance_frame = customtkinter.CTkFrame(content)
        appearance_frame.grid(row = 0, column = 0, sticky = "nsew", padx =(0, 10), pady = 10)
        appearance_frame.grid_columnconfigure(1, weight = 1)

        customtkinter.CTkLabel(appearance_frame, text = "Appearance", font = customtkinter.CTkFont(size = 16, weight = "bold")).grid(row = 0, column = 0, columnspan = 2, pady =(10, 5), sticky = "w")

        customtkinter.CTkLabel(appearance_frame, text = "Mode:").grid(row = 1, column = 0, sticky = "w", padx = 10, pady = 4)
        mode_box = customtkinter.CTkOptionMenu(
        appearance_frame,
        values =["system", "dark", "light"],
        command = lambda v:appearance_settings.__setitem__("appearance_mode", v)or update_appearance()
        )
        mode_box.set(appearance_settings.get("appearance_mode", "system"))
        mode_box.grid(row = 1, column = 1, sticky = "ew", padx = 10, pady = 4)

        customtkinter.CTkLabel(appearance_frame, text = "Color Theme:").grid(row = 2, column = 0, sticky = "w", padx = 10, pady = 4)
        theme_box = customtkinter.CTkOptionMenu(
        appearance_frame,
        values = available_theme_names,
        command = lambda v:appearance_settings.__setitem__("color_theme", v)or update_appearance()
        )
        selected_theme = appearance_settings.get("color_theme", "dark-blue")
        if selected_theme not in available_theme_names:
            selected_theme = "dark-blue"
        theme_box.set(selected_theme)
        theme_box.grid(row = 2, column = 1, sticky = "ew", padx = 10, pady = 4)

        customtkinter.CTkLabel(appearance_frame, text = "Resolution:").grid(row = 3, column = 0, sticky = "w", padx = 10, pady = 4)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        common_res =[
        "5120x1440", "3840x2400", "3840x2160", "3840x1080", "2560x1600", "2560x1440",
        "2560x1080", "1920x1200", "1920x1080", "1680x1050", "1600x1200", "1600x900",
        "1440x900", "1366x768", "1280x960", "1280x800", "1280x720"
        ]

        def _fits(res_str:str)->bool:
            try:
                w, h = map(int, res_str.split("x"))
                return w <=screen_w and h <=screen_h
            except Exception:
                return False

        def _aspect_label(res_str:str)->str:
            try:
                w, h = map(int, res_str.split("x"))
                ratio = w /h if h else 0

                common_aspects =[
                (16, 9), (16, 10), (21, 9), (32, 9), (4, 3), (5, 4), (3, 2),
                (17, 9), (19, 10), (18, 9)
                ]
                closest = min(common_aspects, key = lambda a:abs(ratio -(a[0]/a[1])))if h else(w, h)
                closest_ratio = closest[0]/closest[1]if closest[1]else ratio

                if h and abs(ratio -closest_ratio)<=0.05:
                    aspect = f"{closest[0]}:{closest[1]}"
                else:
                    g = math.gcd(w, h)
                    aspect = f"{w //g}:{h //g}"if g else f"{w}:{h}"

                return f"{w}x{h}({aspect})"
            except Exception:
                return res_str

        filtered_res =[]
        seen = set()
        for r in common_res:
            if r not in seen and _fits(r):
                filtered_res.append(r)
                seen.add(r)

        current_res = appearance_settings.get("resolution", "1920x1080")
        if current_res not in filtered_res and _fits(current_res):
            filtered_res.insert(0, current_res)

        if not filtered_res:
            filtered_res =[f"{screen_w}x{screen_h}"]

        labeled_values =[_aspect_label(r)for r in filtered_res]

        current_label = _aspect_label(current_res)
        if current_label not in labeled_values and _fits(current_res):
            labeled_values.insert(0, current_label)

        def _on_resolution_change(label_val:str):
            res_val = label_val.split(" ")[0]
            appearance_settings["resolution"]= res_val
            update_appearance()

        resolution_box = customtkinter.CTkOptionMenu(
        appearance_frame,
        values = labeled_values,
        command = _on_resolution_change
        )
        resolution_box.set(current_label if current_label in labeled_values else labeled_values[0])
        resolution_box.grid(row = 3, column = 1, sticky = "ew", padx = 10, pady = 4)

        fullscreen_switch = customtkinter.CTkCheckBox(
        appearance_frame,
        text = "Fullscreen",
        command = lambda:(appearance_settings.__setitem__("fullscreen", bool(fullscreen_switch.get())), update_appearance())
        )
        fullscreen_switch.grid(row = 4, column = 0, columnspan = 2, sticky = "w", padx = 10, pady = 4)
        fullscreen_switch.select()if appearance_settings.get("fullscreen", False)else fullscreen_switch.deselect()

        borderless_switch = customtkinter.CTkCheckBox(
        appearance_frame,
        text = "Borderless",
        command = lambda:(appearance_settings.__setitem__("borderless", bool(borderless_switch.get())), update_appearance())
        )
        borderless_switch.grid(row = 5, column = 0, columnspan = 2, sticky = "w", padx = 10, pady = 4)
        borderless_switch.select()if appearance_settings.get("borderless", False)else borderless_switch.deselect()

        customtkinter.CTkLabel(appearance_frame, text = "Units:").grid(row = 6, column = 0, sticky = "w", padx = 10, pady = 4)
        units_box = customtkinter.CTkOptionMenu(
        appearance_frame,
        values =["imperial", "metric", "cheese"],
        command = lambda v:(appearance_settings.__setitem__("units", v), settings_modified.__setitem__(0, True))
        )
        units_box.set(appearance_settings.get("units", "imperial"))
        units_box.grid(row = 6, column = 1, sticky = "ew", padx = 10, pady = 4)

        customtkinter.CTkLabel(appearance_frame, text = "Display Currency:").grid(row = 7, column = 0, sticky = "w", padx = 10, pady = 4)
        currency_display_options = ["table (default)"] + sorted(_currency_symbols.keys())

        def _on_currency_change(value):
            try:
                selected = str(value).strip()
                appearance_settings["display_currency"] = "table" if selected.lower().startswith("table") else selected.upper()
            except Exception:
                appearance_settings["display_currency"] = "table"
            settings_modified[0] = True

        currency_box = customtkinter.CTkOptionMenu(
        appearance_frame,
        values = currency_display_options,
        command = _on_currency_change
        )
        current_currency_pref = str(appearance_settings.get("display_currency", "table")).strip()
        if not current_currency_pref or current_currency_pref.lower() in ("table", "default", "table_default", "auto"):
            current_currency_label = "table (default)"
        else:
            current_currency_label = current_currency_pref.upper()
            if current_currency_label not in currency_display_options:
                currency_display_options.append(current_currency_label)
                currency_box.configure(values = currency_display_options)
        currency_box.set(current_currency_label)
        currency_box.grid(row = 7, column = 1, sticky = "ew", padx = 10, pady = 4)

        customtkinter.CTkLabel(appearance_frame, text = "Sound Volume:").grid(row = 8, column = 0, sticky = "w", padx = 10, pady =(8, 4))
        volume_slider = customtkinter.CTkSlider(
        appearance_frame,
        from_ = 0,
        to = 100,
        number_of_steps = 100,
        command = lambda v:(appearance_settings.__setitem__("sound_volume", int(v)), settings_modified.__setitem__(0, True))
        )
        volume_slider.grid(row = 8, column = 1, sticky = "ew", padx = 10, pady =(8, 4))
        volume_slider.set(appearance_settings.get("sound_volume", 100))

        customtkinter.CTkLabel(appearance_frame, text = "Music Volume:").grid(row = 9, column = 0, sticky = "w", padx = 10, pady = 4)
        music_volume_slider = customtkinter.CTkSlider(
        appearance_frame,
        from_ = 0,
        to = 100,
        number_of_steps = 100,
        command = lambda v:(appearance_settings.__setitem__("music_volume", int(v)), settings_modified.__setitem__(0, True), self._apply_business_music_volume())
        )
        music_volume_slider.grid(row = 9, column = 1, sticky = "ew", padx = 10, pady = 4)
        music_volume_slider.set(appearance_settings.get("music_volume", 100))

        business_music_mute_chk = customtkinter.CTkCheckBox(
            appearance_frame,
            text = "Mute Store/Casino Music",
            command = lambda: (appearance_settings.__setitem__("mute_business_music", bool(business_music_mute_chk.get())), settings_modified.__setitem__(0, True), self._apply_business_music_volume())
        )
        business_music_mute_chk.grid(row = 10, column = 0, columnspan = 2, sticky = "w", padx = 10, pady = 4)
        if appearance_settings.get("mute_business_music", False):
            business_music_mute_chk.select()
        else:
            business_music_mute_chk.deselect()

        customtkinter.CTkLabel(appearance_frame, text = "Weather Effects", font = customtkinter.CTkFont(size = 14, weight = "bold")).grid(row = 11, column = 0, columnspan = 2, pady = (12, 4), sticky = "w", padx = 10)

        weather_visual_chk = customtkinter.CTkCheckBox(
            appearance_frame,
            text = "Visual Effects (lightning flashes)",
            command = lambda: (appearance_settings.__setitem__("weather_visual_effects", bool(weather_visual_chk.get())), settings_modified.__setitem__(0, True))
        )
        weather_visual_chk.grid(row = 12, column = 0, columnspan = 2, sticky = "w", padx = 10, pady = 4)
        if appearance_settings.get("weather_visual_effects", True):
            weather_visual_chk.select()
        else:
            weather_visual_chk.deselect()

        weather_audio_chk = customtkinter.CTkCheckBox(
            appearance_frame,
            text = "Audio Effects (rain, wind, thunder)",
            command = lambda: (appearance_settings.__setitem__("weather_audio_effects", bool(weather_audio_chk.get())), settings_modified.__setitem__(0, True))
        )
        weather_audio_chk.grid(row = 13, column = 0, columnspan = 2, sticky = "w", padx = 10, pady = 4)
        if appearance_settings.get("weather_audio_effects", True):
            weather_audio_chk.select()
        else:
            weather_audio_chk.deselect()

        right_frame = customtkinter.CTkFrame(content)
        right_frame.grid(row = 0, column = 1, sticky = "nsew", padx =(10, 0), pady = 10)
        right_frame.grid_columnconfigure(1, weight = 1)

        customtkinter.CTkLabel(right_frame, text = "Data", font = customtkinter.CTkFont(size = 16, weight = "bold")).grid(row = 0, column = 0, columnspan = 2, pady =(10, 5), sticky = "w")

        customtkinter.CTkLabel(right_frame, text = "Table(.sldtbl):").grid(row = 1, column = 0, sticky = "w", padx = 10, pady = 4)
        try:
            table_files =[f for f in os.listdir("tables")if f.endswith(global_variables.get("table_extension", ".sldtbl"))]
        except FileNotFoundError:
            table_files =[]

        table_display_names =[]
        table_name_map = {}

        for table_file in table_files:
            try:
                table_path = os.path.join("tables", table_file)
                with open(table_path, 'r', encoding = 'utf-8-sig')as f:
                    table_data = json.load(f)
                pretty_name = table_data.get("prettyname", table_file)
                table_display_names.append(pretty_name)
                table_name_map[pretty_name]= table_file
            except Exception as e:
                logging.warning(f"Failed to load table pretty name for {table_file}: {e}")
                table_display_names.append(table_file)
                table_name_map[table_file]= table_file

        if not table_display_names:
            table_display_names =["<none>"]
            table_name_map["<none>"]= None

        table_box = customtkinter.CTkOptionMenu(
        right_frame,
        values = table_display_names,
        state = "disabled"if table_display_names ==["<none>"]else "normal",
        command = lambda v:(global_variables.__setitem__("current_table", table_name_map.get(v)), settings_modified.__setitem__(0, True))
        )

        current_table_val = global_variables.get("current_table")
        current_display_name = "<none>"
        if current_table_val:
            current_table_base = os.path.splitext(current_table_val)[0]
            for display_name, filename in table_name_map.items():
                if filename ==current_table_val or os.path.splitext(filename)[0]==current_table_base:
                    current_display_name = display_name
                    break

        table_box.set(current_display_name)
        table_box.grid(row = 1, column = 1, sticky = "ew", padx = 10, pady = 4)

        customtkinter.CTkLabel(right_frame, text = "Developer Flags", font = customtkinter.CTkFont(size = 14, weight = "bold")).grid(row = 2, column = 0, columnspan = 2, pady =(12, 4), sticky = "w")
        dev_enabled = global_variables.get("devmode", {}).get("value", False)

        def make_toggle(row, label, key):
            chk = customtkinter.CTkCheckBox(
            right_frame,
            text = label,
            state = "normal"if dev_enabled else "disabled",
            command = lambda k = key, c = lambda:chk.get():(global_variables[k].__setitem__("value", bool(c())), settings_modified.__setitem__(0, True))
            )
            chk.grid(row = row, column = 0, columnspan = 2, sticky = "w", padx = 10, pady = 4)
            if global_variables[key].get("value", False):
                chk.select()
            else:
                chk.deselect()
            return chk

        dev_chk = make_toggle(3, "Development Mode", "devmode")
        dm_chk = make_toggle(4, "DM Mode", "dmmode")
        debug_chk = make_toggle(5, "Debug Mode", "debugmode")

        if not dev_enabled:
            info_label = customtkinter.CTkLabel(right_frame, text = "Enable devmode to edit these", text_color = "gray")
            info_label.grid(row = 6, column = 0, columnspan = 2, sticky = "w", padx = 10, pady =(0, 8))

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 2, column = 0, columnspan = 2, pady =(10, 0))
        button_frame.grid_columnconfigure((0, 1), weight = 1)

        def save_settings():
            try:

                appearance_settings_path = os.path.join(saves_folder or "saves", "appearance_settings.sldsv")
                _signed_json_write(appearance_settings_path, appearance_settings)
                logging.info(f"Appearance settings saved to {appearance_settings_path}")

                settings_path = os.path.join(saves_folder or "saves", "settings.sldsv")
                _signed_json_write(settings_path, global_variables)
                logging.info(f"Global settings saved to {settings_path}")

                settings_modified[0]= False
                self._popup_show_info("Success", "Settings saved successfully!", sound = "success")
            except Exception as e:
                logging.error(f"Failed to save settings: {e}")
                self._popup_show_info("Error", f"Failed to save settings: {e}", sound = "error")

        def go_back():
            if settings_modified[0]:
                def confirm_leave():
                    self._clear_window()
                    self._build_main_menu()
                    confirm_window.destroy()

                def cancel_leave():
                    confirm_window.destroy()

                confirm_window = customtkinter.CTkToplevel(self.root)
                confirm_window.title("Unsaved Changes")
                confirm_window.transient(self.root)
                self._center_popup_on_window(confirm_window, 400, 150)

                msg_label = customtkinter.CTkLabel(
                confirm_window,
                text = "You have unsaved changes.\nDo you want to leave without saving?",
                font = customtkinter.CTkFont(size = 12)
                )
                msg_label.pack(pady = 20)

                button_frame_confirm = customtkinter.CTkFrame(confirm_window, fg_color = "transparent")
                button_frame_confirm.pack(pady = 10)
                button_frame_confirm.grid_columnconfigure((0, 1), weight = 1)

                leave_btn = self._create_sound_button(
                button_frame_confirm,
                "Leave",
                confirm_leave,
                width = 150,
                height = 35
                )
                leave_btn.grid(row = 0, column = 0, padx =(0, 10))

                cancel_btn = self._create_sound_button(
                button_frame_confirm,
                "Cancel",
                cancel_leave,
                width = 150,
                height = 35
                )
                cancel_btn.grid(row = 0, column = 1, padx =(10, 0))

                confirm_window.grab_set()
            else:
                self._clear_window()
                self._build_main_menu()

        save_button = self._create_sound_button(
        button_frame,
        "Save Settings",
        save_settings,
        width = 200,
        height = 40
        )
        save_button.grid(row = 0, column = 0, padx =(0, 10))

        back_button = self._create_sound_button(
        button_frame,
        "Back",
        go_back,
        width = 200,
        height = 40
        )
        back_button.grid(row = 0, column = 1, padx =(10, 0))

        if cloud_is_configured():
            button_frame.grid_columnconfigure((0, 1, 2), weight = 1)
            cloud_button = self._create_sound_button(
            button_frame,
            "Cloud Saves",
            lambda: [self._clear_window(), self._open_cloud_saves()],
            width = 200,
            height = 40
            )
            cloud_button.grid(row = 0, column = 2, padx =(10, 0))

    def _open_modify_settings_tool(self):

        logging.info("Modify Settings tool called")

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                self._popup_show_info("Error", "No table file found.", sound = "error")
                return
            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound = "error")
            return

        dm_settings_path = os.path.join(saves_folder or "saves", "dm_settings.sldsv")
        dm_settings = {"enabled_enemies":{}}

        if os.path.exists(dm_settings_path):
            try:
                dm_settings_loaded, _, dm_status = _signed_json_read(dm_settings_path, allow_unsigned = True)
                if isinstance(dm_settings_loaded, dict):
                    dm_settings = dm_settings_loaded
                    if "enabled_enemies"not in dm_settings:
                        dm_settings["enabled_enemies"]= {}
            except Exception as e:
                logging.warning(f"Failed to load DM settings: {e}")

        enemy_list = table_data.get("tables", {}).get("enemy_drops", [])

        for enemy in enemy_list:
            enemy_name = enemy.get("name")
            if enemy_name and enemy_name not in dm_settings["enabled_enemies"]:
                dm_settings["enabled_enemies"][enemy_name]= True

        self._clear_window()
        self._play_ui_sound("whoosh1")

        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color = "transparent")
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = "DM Settings - Enemy Spawn Control",
        font = customtkinter.CTkFont(size = 24, weight = "bold")
        )
        title_label.pack(pady = 20)

        customtkinter.CTkLabel(
        main_frame,
        text = "Toggle enemies on/off for encounter rolls and loot generation:",
        font = customtkinter.CTkFont(size = 14)
        ).pack(pady = 10)

        enemy_vars = {}

        for enemy in enemy_list:
            enemy_name = enemy.get("name", "Unknown")
            enemy_frame = customtkinter.CTkFrame(main_frame)
            enemy_frame.pack(fill = "x", pady = 5, padx = 20)

            enemy_info = f"{enemy_name} - {enemy.get('difficulty', 'Unknown')} Difficulty"

            customtkinter.CTkLabel(
            enemy_frame,
            text = enemy_info,
            font = customtkinter.CTkFont(size = 12)
            ).pack(side = "left", padx = 10, pady = 10)

            var = customtkinter.BooleanVar(value = dm_settings["enabled_enemies"].get(enemy_name, True))
            enemy_vars[enemy_name]= var

            toggle = customtkinter.CTkSwitch(
            enemy_frame,
            text = "Enabled",
            variable = var,
            font = customtkinter.CTkFont(size = 12)
            )
            toggle.pack(side = "right", padx = 10, pady = 10)

        buttons_frame = customtkinter.CTkFrame(main_frame)
        buttons_frame.pack(fill = "x", pady = 20, padx = 20)

        def save_settings():

            try:

                for enemy_name, var in enemy_vars.items():
                    dm_settings["enabled_enemies"][enemy_name]= var.get()

                _signed_json_write(dm_settings_path, dm_settings)

                logging.info(f"DM settings saved to {dm_settings_path}")
                self._popup_show_info("Success", "DM settings saved successfully!", sound = "success")

            except Exception as e:
                logging.error(f"Failed to save DM settings: {e}")
                self._popup_show_info("Error", f"Failed to save settings: {e}", sound = "error")

        def enable_all():

            for var in enemy_vars.values():
                var.set(True)

        def disable_all():

            for var in enemy_vars.values():
                var.set(False)

        self._create_sound_button(
        buttons_frame,
        text = "Save Settings",
        command = save_settings,
        width = 200
        ).pack(side = "left", padx = 10)

        self._create_sound_button(
        buttons_frame,
        text = "Enable All",
        command = enable_all,
        width = 150,
        fg_color = "#006400"
        ).pack(side = "left", padx = 10)

        self._create_sound_button(
        buttons_frame,
        text = "Disable All",
        command = disable_all,
        width = 150,
        fg_color = "#8B0000"
        ).pack(side = "left", padx = 10)

        back_button = self._create_sound_button(
        main_frame,
        text = "Back to DM Tools",
        command = lambda:[self._clear_window(), self._open_dm_tools()],
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        back_button.pack(pady = 20)
