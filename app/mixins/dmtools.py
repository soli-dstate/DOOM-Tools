"""DmtoolsMixin — App methods for the "dmtools" feature area."""
from app.foundation import *


class DmtoolsMixin:
    def _open_add_item_by_id_tool(self):
        logging.info("Add Item By ID definition called")

        if self.currentsave is None:
            self._popup_show_info("Error", "No character loaded.", sound = "error")
            return

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                self._popup_show_info("Error", "No table files found.", sound = "error")
                return

            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)

            all_items =[]
            for table_name, items in table_data.get("tables", {}).items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict)or item.get("id")is None:
                        continue
                    item_copy = item.copy()
                    item_copy["table_category"]= table_name
                    all_items.append(item_copy)

            all_items.sort(key = lambda x:x.get("id", 999999))

            if not all_items:
                self._popup_show_info("Error", "No items found in table.", sound = "error")
                return
        except Exception as e:
            logging.error(f"Failed to load table: {e}")
            self._popup_show_info("Error", f"Failed to load table: {e}", sound = "error")
            return

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(2, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)

        title = customtkinter.CTkLabel(main_frame, text = "Add Item to Inventory By ID", font = customtkinter.CTkFont(size = 20, weight = "bold"))
        title.grid(row = 0, column = 0, pady =(0, 10))

        search_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        search_frame.grid(row = 1, column = 0, sticky = "ew", pady = 10)
        search_frame.grid_columnconfigure(1, weight = 1)

        search_label = customtkinter.CTkLabel(search_frame, text = "Search(ID or Name):", font = customtkinter.CTkFont(size = 13))
        search_label.grid(row = 0, column = 0, padx =(0, 10), sticky = "w")

        search_entry = customtkinter.CTkEntry(search_frame, placeholder_text = "Enter item ID or name...")
        search_entry.grid(row = 0, column = 1, sticky = "ew", padx =(0, 10))

        ITEMS_PER_PAGE = 25
        current_page =[0]
        current_filtered =[all_items]
        search_timer =[None]

        info_label = customtkinter.CTkLabel(search_frame, text = f"Page 1 | {len(all_items)} items total", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        info_label.grid(row = 0, column = 2, padx = 10)

        scroll_frame = customtkinter.CTkScrollableFrame(main_frame, width = 900, height = 450)
        scroll_frame.grid(row = 2, column = 0, sticky = "nsew", pady = 10)
        scroll_frame.grid_columnconfigure(0, weight = 1)

        pagination_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        pagination_frame.grid(row = 3, column = 0, pady = 5)

        def add_item_to_inventory(item):
            try:
                save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
                save_data = self._read_save_from_path(save_path)
                if save_data is None:
                    file_sd = {}
                else:
                    file_sd = save_data

                item_to_add = {k:v for k, v in item.items()if k !="table_category"}

                item_to_add = add_subslots_to_item(item_to_add)
                if item_to_add.get("firearm"):
                    _set_full_part_durability(item_to_add)

                try:
                    save_data.setdefault("hands", {})
                    save_data["hands"].setdefault("items", [])
                    save_data["hands"]["items"].append(item_to_add)
                    added_location = "hands"
                except Exception:

                    try:
                        save_data.setdefault("storage", [])
                        save_data["storage"].append(item_to_add)
                        added_location = "storage"
                    except Exception:
                        added_location = "unknown"

                self._save_file(save_data)

                logging.info(f"Added item ID {item.get('id')}({item.get('name')}) to {added_location}")
                self._popup_show_info("Success", f"Added '{item.get('name')}' to {added_location}!", sound = "success")
            except Exception as e:
                logging.error(f"Failed to add item: {e}")
                self._popup_show_info("Error", f"Failed to add item: {e}", sound = "error")

        def create_item_widget(item):

            item_frame = customtkinter.CTkFrame(scroll_frame)
            item_frame.pack(fill = "x", pady = 3, padx = 5)
            item_frame.grid_columnconfigure(1, weight = 1)

            id_label = customtkinter.CTkLabel(
            item_frame,
            text = f"ID: {item.get('id', 'N/A')}",
            font = customtkinter.CTkFont(size = 12, weight = "bold"),
            width = 80,
            fg_color =("gray75", "gray25"),
            corner_radius = 6
            )
            id_label.grid(row = 0, column = 0, padx = 8, pady = 8, sticky = "w")

            details_frame = customtkinter.CTkFrame(item_frame, fg_color = "transparent")
            details_frame.grid(row = 0, column = 1, sticky = "ew", padx = 8, pady = 8)

            name_label = customtkinter.CTkLabel(
            details_frame,
            text = item.get("name", "Unknown"),
            font = customtkinter.CTkFont(size = 13, weight = "bold"),
            anchor = "w"
            )
            name_label.pack(anchor = "w")

            category_label = customtkinter.CTkLabel(
            details_frame,
            text = f"{item.get('table_category', 'N/A')} | {item.get('rarity', 'N/A')} | {format_price(item.get('value', 0))}",
            font = customtkinter.CTkFont(size = 10),
            text_color = "gray",
            anchor = "w"
            )
            category_label.pack(anchor = "w")

            add_button = self._create_sound_button(
            item_frame,
            "Add",
            lambda it = item:add_item_to_inventory(it),
            width = 80,
            height = 30,
            font = customtkinter.CTkFont(size = 11)
            )
            add_button.grid(row = 0, column = 2, padx = 8, pady = 8)

        def display_page(page_num):

            items = current_filtered[0]
            total_pages = max(1, (len(items)+ITEMS_PER_PAGE -1)//ITEMS_PER_PAGE)

            page_num = max(0, min(page_num, total_pages -1))
            current_page[0]= page_num

            for widget in scroll_frame.winfo_children():
                widget.destroy()

            if not items:
                no_results = customtkinter.CTkLabel(scroll_frame, text = "No items found.", font = customtkinter.CTkFont(size = 14), text_color = "gray")
                no_results.pack(pady = 20)
                info_label.configure(text = "No items found")
                update_pagination_controls(0, 0)
                return

            start_idx = page_num *ITEMS_PER_PAGE
            end_idx = min(start_idx +ITEMS_PER_PAGE, len(items))

            for i in range(start_idx, end_idx):
                create_item_widget(items[i])

            info_label.configure(text = f"Page {page_num +1} of {total_pages} | {len(items)} items total")

            update_pagination_controls(page_num, total_pages)

            try:
                scroll_frame._parent_canvas.yview_moveto(0)
            except Exception:
                pass

        def update_pagination_controls(current, total):

            for widget in pagination_frame.winfo_children():
                widget.destroy()

            if total <=1:
                return

            first_btn = customtkinter.CTkButton(
            pagination_frame, text = "<<", width = 40, height = 30,
            command = lambda:display_page(0),
            state = "normal"if current >0 else "disabled"
            )
            first_btn.pack(side = "left", padx = 2)

            prev_btn = customtkinter.CTkButton(
            pagination_frame, text = "<", width = 40, height = 30,
            command = lambda:display_page(current -1),
            state = "normal"if current >0 else "disabled"
            )
            prev_btn.pack(side = "left", padx = 2)

            start_page = max(0, current -3)
            end_page = min(total, start_page +7)
            if end_page -start_page <7:
                start_page = max(0, end_page -7)

            for p in range(start_page, end_page):
                btn = customtkinter.CTkButton(
                pagination_frame,
                text = str(p +1),
                width = 35,
                height = 30,
                fg_color =("gray75", "gray25")if p ==current else None,
                command = lambda page = p:display_page(page)
                )
                btn.pack(side = "left", padx = 1)

            next_btn = customtkinter.CTkButton(
            pagination_frame, text = ">", width = 40, height = 30,
            command = lambda:display_page(current +1),
            state = "normal"if current <total -1 else "disabled"
            )
            next_btn.pack(side = "left", padx = 2)

            last_btn = customtkinter.CTkButton(
            pagination_frame, text = ">>", width = 40, height = 30,
            command = lambda:display_page(total -1),
            state = "normal"if current <total -1 else "disabled"
            )
            last_btn.pack(side = "left", padx = 2)

        def filter_items(search_term):

            search_lower = search_term.lower().strip()

            if search_lower:
                filtered =[
                item for item in all_items
                if search_lower in str(item.get("id", ""))or search_lower in item.get("name", "").lower()
                ]
            else:
                filtered = all_items

            current_filtered[0]= filtered
            current_page[0]= 0
            display_page(0)

        def on_search_change(*args):

            if search_timer[0]is not None:
                try:
                    self.root.after_cancel(search_timer[0])
                except Exception:
                    pass

            search_timer[0]= self.root.after(200, lambda:filter_items(search_entry.get()))# type: ignore

        search_entry.bind("<KeyRelease>", on_search_change)

        display_page(0)

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 4, column = 0, pady = 10)

        back_button = self._create_sound_button(
        button_frame,
        "Back",
        lambda:[self._clear_window(), self._open_modify_save_data_tool()],
        width = 200,
        height = 40,
        font = customtkinter.CTkFont(size = 14)
        )
        back_button.pack()
    def _open_dm_tools(self):
        logging.info("DM Tools definition called")
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")

        title_label = customtkinter.CTkLabel(main_frame, text = "DM Tools", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady = 20)

        scroll_frame = customtkinter.CTkScrollableFrame(main_frame)
        scroll_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        encounter_roll_button = self._create_sound_button(scroll_frame, "Encounter Roll", self._open_encounter_roll_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        encounter_roll_button.pack(pady = 10)

        enemy_loot_button = self._create_sound_button(scroll_frame, "Individual Enemy Loot", self._open_enemy_loot_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        enemy_loot_button.pack(pady = 10)

        create_lootcrate_button = self._create_sound_button(scroll_frame, "Create Loot Crate", self._open_create_lootcrate_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        create_lootcrate_button.pack(pady = 10)

        create_item_transfer_button = self._create_sound_button(scroll_frame, "Create Item Transfer", self._open_create_item_transfer_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        create_item_transfer_button.pack(pady = 10)

        create_magazine_transfer_button = self._create_sound_button(scroll_frame, "Create Loaded Magazine Transfer", self._open_create_magazine_transfer_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        create_magazine_transfer_button.pack(pady = 10)

        create_belt_transfer_button = self._create_sound_button(scroll_frame, "Create Belt Transfer", self._open_create_belt_transfer_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16), state = "disabled")
        create_belt_transfer_button.pack(pady = 10)

        modify_settings_button = self._create_sound_button(scroll_frame, "Modify Settings", self._open_modify_settings_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        modify_settings_button.pack(pady = 10)

        dungeon_generator_button = self._create_sound_button(scroll_frame, "Dungeon Generator", self._open_dungeon_generator, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        dungeon_generator_button.pack(pady = 10)

        weather_editor_button = self._create_sound_button(scroll_frame, "Weather Editor", self._open_weather_editor, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        weather_editor_button.pack(pady = 10)

        back_button = self._create_sound_button(main_frame, "Back to Main Menu", lambda:[self._clear_window(), self._build_main_menu()], width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        back_button.pack(pady = 20)

    def _open_weather_editor(self):

        import calendar as cal_module

        logging.info("Weather Editor called")

        weather_path = os.path.join('remotedata', 'weather.json')
        remote_url = 'https://raw.githubusercontent.com/soli-dstate/DOOM-Tools/master/remotedata/weather.json'
        weather_data = {"forecast": {"default": {"weather": "clear", "wind_severity": 0, "temperature_f": 70}}}

        try:
            resp = requests.get(remote_url, timeout = 10)
            if resp.status_code == 200:
                weather_data = resp.json()
                os.makedirs('remotedata', exist_ok = True)
                with open(weather_path, 'w', encoding = 'utf-8') as f:
                    json.dump(weather_data, f, indent = 4)
                logging.info('Pulled latest weather.json from GitHub')
            else:
                logging.warning('Could not fetch weather.json from GitHub (status %d), using local copy', resp.status_code)
                if os.path.exists(weather_path):
                    with open(weather_path, 'r', encoding = 'utf-8') as f:
                        weather_data = json.load(f)
        except Exception:
            logging.debug('Could not fetch weather.json from GitHub, using local copy')
            try:
                if os.path.exists(weather_path):
                    with open(weather_path, 'r', encoding = 'utf-8') as f:
                        weather_data = json.load(f)
            except Exception:
                logging.exception('Failed to load local weather.json')

        forecast = weather_data.get("forecast", {})
        if not isinstance(forecast, dict):
            forecast = {}
            weather_data["forecast"] = forecast
        if "default" not in forecast:
            forecast["default"] = {"weather": "clear", "wind_severity": 0, "temperature_f": 70}

        VALID_WEATHER = ("clear", "sun_and_cloud", "cloudy", "rain", "hard_rain", "thunderstorm", "thunder_hard_rain", "thunder", "snowstorm", "thundersnow")
        RAIN_TYPES = ("rain", "hard_rain", "thunderstorm", "thunder_hard_rain")
        SNOW_TYPES = ("snowstorm", "thundersnow")
        # When a wet type lands at an inconsistent temperature, swap to its warm/cold counterpart
        RAIN_TO_SNOW = {"rain": "snowstorm", "hard_rain": "snowstorm", "thunderstorm": "thundersnow", "thunder_hard_rain": "thundersnow"}
        SNOW_TO_RAIN = {"snowstorm": "rain", "thundersnow": "thunderstorm"}

        use_metric = appearance_settings.get("units", "imperial") == "metric"
        temp_unit = "°C" if use_metric else "°F"

        def _f_to_display(f_val):
            if use_metric:
                return round((f_val - 32) * 5 / 9, 1)
            return f_val

        def _display_to_f(display_val):
            if use_metric:
                return round(display_val * 9 / 5 + 32, 2)
            return display_val

        def _validate_weather_temp(weather_type, temp_f, label = ""):
            threshold_display = _f_to_display(32)
            if weather_type in RAIN_TYPES and temp_f <= 32:
                return f"{label}{weather_type.title()} requires temperature above {threshold_display}{temp_unit} (got {_f_to_display(temp_f)}{temp_unit})."
            if weather_type in SNOW_TYPES and temp_f >= 32:
                return f"{label}{weather_type.title()} requires temperature below {threshold_display}{temp_unit} (got {_f_to_display(temp_f)}{temp_unit})."
            return None

        self._clear_window()
        self._play_ui_sound("whoosh1")

        outer_frame = customtkinter.CTkScrollableFrame(self.root, fg_color = "transparent")
        outer_frame.pack(fill = "both", expand = True, padx = 10, pady = 5)

        title_label = customtkinter.CTkLabel(outer_frame, text = "Weather Editor", font = customtkinter.CTkFont(size = 22, weight = "bold"))
        title_label.pack(pady = (5, 8))

        now = datetime.now()
        current_year = [now.year]
        current_month = [now.month]

        # --- Default weather ---
        default_frame = customtkinter.CTkFrame(outer_frame)
        default_frame.pack(fill = "x", padx = 10, pady = (0, 6))

        default_data = forecast.get("default", {})
        default_weather_var = customtkinter.StringVar(value = default_data.get("weather", "clear"))
        default_wind_var = customtkinter.StringVar(value = str(default_data.get("wind_severity", 0)))
        default_temp_var = customtkinter.StringVar(value = str(_f_to_display(default_data.get("temperature_f", 70))))

        df_row = customtkinter.CTkFrame(default_frame, fg_color = "transparent")
        df_row.pack(pady = 6, anchor = "center")
        customtkinter.CTkLabel(df_row, text = "Default", font = customtkinter.CTkFont(size = 14, weight = "bold"), width = 60).pack(side = "left", padx = (0, 8))
        customtkinter.CTkLabel(df_row, text = "Type:").pack(side = "left", padx = (0, 2))
        customtkinter.CTkOptionMenu(df_row, values = list(VALID_WEATHER), variable = default_weather_var, width = 170).pack(side = "left", padx = (0, 8))
        customtkinter.CTkLabel(df_row, text = "Wind:").pack(side = "left", padx = (0, 2))
        customtkinter.CTkSegmentedButton(df_row, values = ["0", "1", "2", "3"], variable = default_wind_var, width = 120).pack(side = "left", padx = (0, 8))
        customtkinter.CTkLabel(df_row, text = f"Temp {temp_unit}:").pack(side = "left", padx = (0, 2))
        customtkinter.CTkEntry(df_row, textvariable = default_temp_var, width = 55).pack(side = "left")

        # --- Calendar ---
        cal_frame = customtkinter.CTkFrame(outer_frame)
        cal_frame.pack(fill = "x", padx = 10, pady = (0, 6))

        nav_frame = customtkinter.CTkFrame(cal_frame, fg_color = "transparent")
        nav_frame.pack(pady = (6, 2), anchor = "center")

        month_label = customtkinter.CTkLabel(nav_frame, text = "", font = customtkinter.CTkFont(size = 16, weight = "bold"))

        cal_grid_wrapper = customtkinter.CTkFrame(cal_frame, fg_color = "transparent")
        cal_grid_wrapper.pack(pady = (0, 6), anchor = "center")
        cal_grid = customtkinter.CTkFrame(cal_grid_wrapper, fg_color = "transparent")
        cal_grid.pack()

        btn_map = {}
        selected_date = [None]
        today_str = now.strftime("%Y-%m-%d")

        def _btn_color(date_key):
            if date_key == selected_date[0]:
                return "#1a6600"
            if date_key in forecast:
                return "#005f99"
            if date_key == today_str:
                return "#444444"
            return "transparent"

        def _update_selection(old_key, new_key):
            if old_key and old_key in btn_map:
                btn_map[old_key].configure(fg_color = _btn_color(old_key))
            if new_key and new_key in btn_map:
                btn_map[new_key].configure(fg_color = _btn_color(new_key))

        def on_day_click(date_key):
            old = selected_date[0]
            selected_date[0] = date_key
            _update_selection(old, date_key)
            detail_title.configure(text = f"Editing: {date_key}")
            if date_key in forecast:
                d = forecast[date_key]
                day_weather_var.set(d.get("weather", "clear"))
                day_wind_var.set(str(d.get("wind_severity", 0)))
                day_temp_var.set(str(_f_to_display(d.get("temperature_f", 70))))
                if "hourly" in d:
                    hourly_toggle_var.set(True)
                    hourly_scroll.pack(fill = "x", padx = 8, pady = (0, 4))
                else:
                    hourly_toggle_var.set(False)
                    hourly_scroll.pack_forget()
            else:
                day_weather_var.set("clear")
                day_wind_var.set("0")
                day_temp_var.set("70")
                hourly_toggle_var.set(False)
                hourly_scroll.pack_forget()
            _rebuild_hourly_rows()

        def render_calendar():
            for w in cal_grid.winfo_children():
                w.destroy()
            btn_map.clear()

            y = current_year[0]
            m = current_month[0]
            month_label.configure(text = f"{cal_module.month_name[m]} {y}")

            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for col, dn in enumerate(day_names):
                customtkinter.CTkLabel(cal_grid, text = dn, font = customtkinter.CTkFont(size = 11, weight = "bold"), width = 50).grid(row = 0, column = col, padx = 1, pady = (0, 2))

            for row_i, week in enumerate(cal_module.monthcalendar(y, m), start = 1):
                for col_i, day in enumerate(week):
                    if day == 0:
                        customtkinter.CTkLabel(cal_grid, text = "", width = 50, height = 36).grid(row = row_i, column = col_i, padx = 1, pady = 1)
                        continue
                    date_key = f"{y}-{m:02d}-{day:02d}"
                    btn_kwargs = {
                        "master": cal_grid,
                        "text": str(day),
                        "width": 50,
                        "height": 36,
                        "font": customtkinter.CTkFont(size = 12),
                        "fg_color": _btn_color(date_key),
                        "command": lambda dk = date_key: on_day_click(dk)
                    }
                    if date_key == today_str:
                        btn_kwargs["border_width"] = 2
                        btn_kwargs["border_color"] = "#ffcc00"
                    btn = customtkinter.CTkButton(**btn_kwargs)
                    btn.grid(row = row_i, column = col_i, padx = 1, pady = 1)
                    btn_map[date_key] = btn

        def prev_month():
            current_month[0] -= 1
            if current_month[0] < 1:
                current_month[0] = 12
                current_year[0] -= 1
            render_calendar()

        def next_month():
            current_month[0] += 1
            if current_month[0] > 12:
                current_month[0] = 1
                current_year[0] += 1
            render_calendar()

        self._create_sound_button(nav_frame, "\u25c0", prev_month, width = 32, height = 28).pack(side = "left", padx = (0, 4))
        month_label.pack(side = "left", padx = 8)
        self._create_sound_button(nav_frame, "\u25b6", next_month, width = 32, height = 28).pack(side = "left", padx = (4, 0))

        render_calendar()

        # --- Day detail editor ---
        detail_frame = customtkinter.CTkFrame(outer_frame)
        detail_frame.pack(fill = "x", padx = 10, pady = (0, 6))

        detail_title = customtkinter.CTkLabel(detail_frame, text = "Select a day to edit", font = customtkinter.CTkFont(size = 13, weight = "bold"))
        detail_title.pack(pady = (6, 2))

        detail_row = customtkinter.CTkFrame(detail_frame, fg_color = "transparent")
        detail_row.pack(pady = 2, anchor = "center")

        day_weather_var = customtkinter.StringVar(value = "clear")
        day_wind_var = customtkinter.StringVar(value = "0")
        day_temp_var = customtkinter.StringVar(value = "70")

        customtkinter.CTkLabel(detail_row, text = "Type:").pack(side = "left", padx = (0, 2))
        customtkinter.CTkOptionMenu(detail_row, values = list(VALID_WEATHER), variable = day_weather_var, width = 170).pack(side = "left", padx = (0, 8))
        customtkinter.CTkLabel(detail_row, text = "Wind:").pack(side = "left", padx = (0, 2))
        customtkinter.CTkSegmentedButton(detail_row, values = ["0", "1", "2", "3"], variable = day_wind_var, width = 120).pack(side = "left", padx = (0, 8))
        customtkinter.CTkLabel(detail_row, text = f"Temp {temp_unit}:").pack(side = "left", padx = (0, 2))
        customtkinter.CTkEntry(detail_row, textvariable = day_temp_var, width = 55).pack(side = "left")

        detail_btn_frame = customtkinter.CTkFrame(detail_frame, fg_color = "transparent")
        detail_btn_frame.pack(pady = 4, anchor = "center")

        # --- Hourly forecast ---
        hourly_toggle_var = customtkinter.BooleanVar(value = False)
        customtkinter.CTkSwitch(detail_btn_frame, text = "Hourly", variable = hourly_toggle_var, width = 60, command = lambda: _toggle_hourly()).pack(side = "left", padx = (0, 8))

        hourly_scroll = customtkinter.CTkScrollableFrame(detail_frame, height = 180)
        hourly_scroll.pack_forget()
        hourly_rows = {}
        HOURLY_COLS = 4

        def _toggle_hourly():
            if hourly_toggle_var.get():
                hourly_scroll.pack(fill = "x", padx = 8, pady = (0, 4))
                _rebuild_hourly_rows()
            else:
                hourly_scroll.pack_forget()

        def _rebuild_hourly_rows():
            for w in hourly_scroll.winfo_children():
                w.destroy()
            hourly_rows.clear()
            date_key = selected_date[0]
            existing_hourly = {}
            if date_key and date_key in forecast:
                existing_hourly = forecast[date_key].get("hourly", {})

            grid_frame = customtkinter.CTkFrame(hourly_scroll, fg_color = "transparent")
            grid_frame.pack(anchor = "center", pady = 2)

            WEATHER_OPTIONS = ["(none)"] + list(VALID_WEATHER)
            WIND_OPTIONS = ["(none)", "0", "1", "2", "3"]

            for h in range(24):
                h_key = f"{h:02d}"
                h_data = existing_hourly.get(h_key, {})
                grid_row = h // HOURLY_COLS
                grid_col = h % HOURLY_COLS

                cell = customtkinter.CTkFrame(grid_frame)
                cell.grid(row = grid_row, column = grid_col, padx = 4, pady = 3)

                top_row = customtkinter.CTkFrame(cell, fg_color = "transparent")
                top_row.pack(fill = "x", padx = 2, pady = (2, 0))
                customtkinter.CTkLabel(top_row, text = f"{h:02d}:00", font = customtkinter.CTkFont(size = 11, weight = "bold"), width = 40).pack(side = "left")

                # Use OptionMenu (dropdown) instead of SegmentedButton to avoid width overflow with 6 values
                raw_weather = h_data.get("weather", "")
                w_var = customtkinter.StringVar(value = raw_weather if raw_weather in VALID_WEATHER else "(none)")
                customtkinter.CTkOptionMenu(top_row, values = WEATHER_OPTIONS, variable = w_var, width = 140).pack(side = "left", padx = 2)

                bot_row = customtkinter.CTkFrame(cell, fg_color = "transparent")
                bot_row.pack(fill = "x", padx = 2, pady = (0, 2))
                customtkinter.CTkLabel(bot_row, text = "W:", font = customtkinter.CTkFont(size = 10)).pack(side = "left")

                raw_wind = str(h_data.get("wind_severity", "")) if "wind_severity" in h_data else ""
                wnd_var = customtkinter.StringVar(value = raw_wind if raw_wind in ("0", "1", "2", "3") else "(none)")
                customtkinter.CTkOptionMenu(bot_row, values = WIND_OPTIONS, variable = wnd_var, width = 90).pack(side = "left", padx = 2)

                customtkinter.CTkLabel(bot_row, text = f"T{temp_unit}:", font = customtkinter.CTkFont(size = 10)).pack(side = "left")
                stored_f = h_data.get("temperature_f")
                display_t = str(_f_to_display(stored_f)) if stored_f is not None else ""
                tmp_var = customtkinter.StringVar(value = display_t)
                customtkinter.CTkEntry(bot_row, textvariable = tmp_var, width = 45, placeholder_text = temp_unit).pack(side = "left", padx = 2)
                hourly_rows[h_key] = {"weather": w_var, "wind": wnd_var, "temp": tmp_var}

        def _collect_hourly():
            hourly = {}
            for h_key, vars_dict in hourly_rows.items():
                w = vars_dict["weather"].get().strip()
                wnd = vars_dict["wind"].get().strip()
                tmp = vars_dict["temp"].get().strip()
                # "(none)" is the empty sentinel from the OptionMenu dropdowns
                w_val = w if w not in ("", "(none)") else ""
                wnd_val = wnd if wnd not in ("", "(none)") else ""
                if not w_val and not wnd_val and not tmp:
                    continue
                entry = {}
                if w_val:
                    entry["weather"] = w_val
                if wnd_val:
                    try:
                        entry["wind_severity"] = int(wnd_val)
                    except ValueError:
                        pass
                if tmp:
                    try:
                        entry["temperature_f"] = _display_to_f(float(tmp))
                    except ValueError:
                        pass
                if entry:
                    hourly[h_key] = entry
            return hourly if hourly else None

        def set_day_weather():
            date_key = selected_date[0]
            if not date_key:
                self._popup_show_info("No Date", "Select a day on the calendar first.", sound = "error")
                return
            try:
                temp_val = _display_to_f(float(day_temp_var.get()))
            except ValueError:
                self._popup_show_info("Invalid", "Temperature must be a number.", sound = "error")
                return
            w_type = day_weather_var.get()
            err = _validate_weather_temp(w_type, temp_val)
            if err:
                self._popup_show_info("Invalid Weather", err, sound = "error")
                return
            day_entry = {
                "weather": w_type,
                "wind_severity": int(day_wind_var.get()),
                "temperature_f": temp_val
            }
            if hourly_toggle_var.get():
                hourly_data = _collect_hourly()
                if hourly_data:
                    for h_key, h_entry in hourly_data.items():
                        h_w = h_entry.get("weather", "")
                        h_t = h_entry.get("temperature_f")
                        if h_w and h_t is not None:
                            h_err = _validate_weather_temp(h_w, h_t, f"Hour {h_key}: ")
                            if h_err:
                                self._popup_show_info("Invalid Hourly Weather", h_err, sound = "error")
                                return
                    day_entry["hourly"] = hourly_data
            forecast[date_key] = day_entry
            if date_key in btn_map:
                btn_map[date_key].configure(fg_color = _btn_color(date_key))

        def remove_day_weather():
            date_key = selected_date[0]
            if not date_key:
                return
            if date_key in forecast and date_key != "default":
                del forecast[date_key]
            old = selected_date[0]
            selected_date[0] = None
            if old and old in btn_map:
                btn_map[old].configure(fg_color = _btn_color(old))
            detail_title.configure(text = "Select a day to edit")
            hourly_toggle_var.set(False)
            hourly_scroll.pack_forget()

        self._create_sound_button(detail_btn_frame, "Set Day Weather", set_day_weather, width = 130).pack(side = "left", padx = 4)
        self._create_sound_button(detail_btn_frame, "Remove Override", remove_day_weather, width = 130, fg_color = "#8B0000").pack(side = "left", padx = 4)

        # --- Bottom buttons ---
        bottom_frame = customtkinter.CTkFrame(outer_frame, fg_color = "transparent")
        bottom_frame.pack(pady = (4, 8), anchor = "center")

        def save_weather():
            try:
                try:
                    dt = _display_to_f(float(default_temp_var.get()))
                except ValueError:
                    self._popup_show_info("Invalid", "Default temperature must be a number.", sound = "error")
                    return
                dw = default_weather_var.get()
                err = _validate_weather_temp(dw, dt, "Default: ")
                if err:
                    self._popup_show_info("Invalid Default Weather", err, sound = "error")
                    return
                forecast["default"] = {
                    "weather": dw,
                    "wind_severity": int(default_wind_var.get()),
                    "temperature_f": dt
                }
                weather_data["forecast"] = forecast
                os.makedirs('remotedata', exist_ok = True)
                with open(weather_path, 'w', encoding = 'utf-8') as f:
                    json.dump(weather_data, f, indent = 4)
                logging.info("Weather data saved to %s", weather_path)
                self._popup_show_info("Saved", "Weather data saved locally.\nUpload remotedata/weather.json to GitHub to apply.", sound = "success")
            except Exception as e:
                logging.exception("Failed to save weather data")
                self._popup_show_info("Error", f"Failed to save: {e}", sound = "error")

        def download_weather():
            try:
                resp = requests.get(remote_url, timeout = 10)
                if resp.status_code == 200:
                    new_data = resp.json()
                    weather_data.clear()
                    weather_data.update(new_data)
                    fc = weather_data.get("forecast", {})
                    forecast.clear()
                    forecast.update(fc)
                    if "default" not in forecast:
                        forecast["default"] = {"weather": "clear", "wind_severity": 0, "temperature_f": 70}
                    d = forecast["default"]
                    default_weather_var.set(d.get("weather", "clear"))
                    default_wind_var.set(str(d.get("wind_severity", 0)))
                    default_temp_var.set(str(_f_to_display(d.get("temperature_f", 70))))
                    selected_date[0] = None
                    detail_title.configure(text = "Select a day to edit")
                    hourly_toggle_var.set(False)
                    hourly_scroll.pack_forget()
                    render_calendar()
                    self._popup_show_info("Downloaded", "Weather data refreshed from GitHub.", sound = "success")
                else:
                    self._popup_show_info("Error", f"GitHub returned status {resp.status_code}", sound = "error")
            except Exception as e:
                self._popup_show_info("Error", f"Download failed: {e}", sound = "error")

        # --- Generation settings ---
        gen_config_frame = customtkinter.CTkFrame(outer_frame, fg_color = "transparent")
        gen_config_frame.pack(pady = (2, 0), anchor = "center")
        customtkinter.CTkLabel(gen_config_frame, text = "Season for generator:").pack(side = "left", padx = (0, 6))
        _month_to_season = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
                            6: "Summer", 7: "Summer", 8: "Summer", 9: "Fall", 10: "Fall", 11: "Fall"}
        season_var = customtkinter.StringVar(value = _month_to_season.get(current_month[0], "Spring"))
        customtkinter.CTkSegmentedButton(gen_config_frame, values = ["Winter", "Spring", "Summer", "Fall"],
                                         variable = season_var, width = 300).pack(side = "left")

        def generate_realistic_weather():
            """Generate realistic weather for the currently displayed month with seasonal parameters and previous-month continuity."""
            rng = random.Random()
            season = season_var.get()
            target_year = current_year[0]
            target_month = current_month[0]
            days_in_month = cal_module.monthrange(target_year, target_month)[1]

            # Transition weights are normalised by rng.choices, so they need not sum to exactly 1.
            # "sun_and_cloud" and "cloudy" act as dry buffer states that absorb most transitions out
            # of fair weather, keeping precipitation comparatively infrequent and clustered into spells.
            season_params = {
                "Winter": {
                    "temp_mid": 18.0, "temp_min": -15.0, "temp_max": 38.0,
                    "transitions": {
                        "clear":             {"clear": 0.45, "sun_and_cloud": 0.22, "cloudy": 0.18, "snowstorm": 0.12, "thundersnow": 0.03},
                        "sun_and_cloud":     {"clear": 0.32, "sun_and_cloud": 0.28, "cloudy": 0.22, "snowstorm": 0.15, "thundersnow": 0.03},
                        "cloudy":            {"cloudy": 0.30, "sun_and_cloud": 0.22, "clear": 0.16, "snowstorm": 0.27, "thundersnow": 0.05},
                        "snowstorm":         {"snowstorm": 0.40, "cloudy": 0.28, "clear": 0.17, "thundersnow": 0.15},
                        "thundersnow":       {"snowstorm": 0.45, "thundersnow": 0.20, "cloudy": 0.20, "clear": 0.15},
                        "rain":              {"snowstorm": 0.35, "cloudy": 0.30, "clear": 0.25, "rain": 0.10},
                        "thunderstorm":      {"snowstorm": 0.35, "cloudy": 0.30, "clear": 0.25, "thundersnow": 0.10},
                    },
                    "wind_weights": [0.20, 0.30, 0.28, 0.22],
                },
                "Spring": {
                    "temp_mid": 52.0, "temp_min": 30.0, "temp_max": 72.0,
                    "transitions": {
                        "clear":             {"clear": 0.42, "sun_and_cloud": 0.26, "cloudy": 0.16, "rain": 0.13, "thunderstorm": 0.03},
                        "sun_and_cloud":     {"clear": 0.32, "sun_and_cloud": 0.28, "cloudy": 0.22, "rain": 0.14, "thunderstorm": 0.04},
                        "cloudy":            {"cloudy": 0.28, "sun_and_cloud": 0.24, "clear": 0.16, "rain": 0.24, "thunderstorm": 0.08},
                        "rain":              {"cloudy": 0.34, "rain": 0.28, "clear": 0.16, "hard_rain": 0.10, "thunderstorm": 0.12},
                        "hard_rain":         {"rain": 0.40, "cloudy": 0.24, "thunderstorm": 0.16, "thunder_hard_rain": 0.08, "clear": 0.12},
                        "thunderstorm":      {"rain": 0.34, "cloudy": 0.26, "thunderstorm": 0.18, "thunder_hard_rain": 0.07, "clear": 0.15},
                        "thunder_hard_rain": {"thunderstorm": 0.32, "hard_rain": 0.24, "rain": 0.24, "cloudy": 0.20},
                        "thunder":           {"cloudy": 0.38, "sun_and_cloud": 0.24, "thunderstorm": 0.16, "clear": 0.22},
                        "snowstorm":         {"cloudy": 0.36, "clear": 0.28, "rain": 0.26, "snowstorm": 0.10},
                        "thundersnow":       {"snowstorm": 0.34, "cloudy": 0.30, "rain": 0.22, "clear": 0.14},
                    },
                    "wind_weights": [0.40, 0.35, 0.15, 0.10],
                },
                "Summer": {
                    "temp_mid": 80.0, "temp_min": 60.0, "temp_max": 98.0,
                    "transitions": {
                        "clear":             {"clear": 0.50, "sun_and_cloud": 0.24, "cloudy": 0.12, "rain": 0.09, "thunderstorm": 0.05},
                        "sun_and_cloud":     {"clear": 0.38, "sun_and_cloud": 0.28, "cloudy": 0.16, "rain": 0.10, "thunderstorm": 0.08},
                        "cloudy":            {"cloudy": 0.26, "sun_and_cloud": 0.24, "clear": 0.20, "rain": 0.18, "thunderstorm": 0.12},
                        "rain":              {"cloudy": 0.34, "clear": 0.22, "rain": 0.24, "thunderstorm": 0.16, "hard_rain": 0.04},
                        "hard_rain":         {"rain": 0.38, "thunderstorm": 0.22, "cloudy": 0.22, "thunder_hard_rain": 0.08, "clear": 0.10},
                        "thunderstorm":      {"rain": 0.34, "cloudy": 0.24, "thunderstorm": 0.22, "thunder_hard_rain": 0.08, "clear": 0.12},
                        "thunder_hard_rain": {"thunderstorm": 0.34, "hard_rain": 0.24, "rain": 0.22, "cloudy": 0.20},
                        "thunder":           {"clear": 0.30, "sun_and_cloud": 0.28, "cloudy": 0.22, "thunderstorm": 0.20},
                        "snowstorm":         {"clear": 0.60, "sun_and_cloud": 0.40},
                        "thundersnow":       {"clear": 0.60, "sun_and_cloud": 0.40},
                    },
                    "wind_weights": [0.50, 0.30, 0.15, 0.05],
                },
                "Fall": {
                    "temp_mid": 48.0, "temp_min": 28.0, "temp_max": 68.0,
                    "transitions": {
                        "clear":             {"clear": 0.48, "sun_and_cloud": 0.24, "cloudy": 0.16, "rain": 0.09, "thunderstorm": 0.03},
                        "sun_and_cloud":     {"clear": 0.34, "sun_and_cloud": 0.28, "cloudy": 0.22, "rain": 0.12, "snowstorm": 0.04},
                        "cloudy":            {"cloudy": 0.30, "sun_and_cloud": 0.22, "clear": 0.16, "rain": 0.20, "snowstorm": 0.08, "thunderstorm": 0.04},
                        "rain":              {"cloudy": 0.34, "rain": 0.28, "clear": 0.16, "thunderstorm": 0.10, "snowstorm": 0.12},
                        "hard_rain":         {"rain": 0.40, "cloudy": 0.24, "thunderstorm": 0.14, "snowstorm": 0.12, "clear": 0.10},
                        "thunderstorm":      {"rain": 0.36, "cloudy": 0.26, "thunderstorm": 0.16, "snowstorm": 0.10, "clear": 0.12},
                        "thunder_hard_rain": {"thunderstorm": 0.32, "hard_rain": 0.24, "rain": 0.24, "cloudy": 0.20},
                        "thunder":           {"cloudy": 0.38, "sun_and_cloud": 0.24, "thunderstorm": 0.14, "clear": 0.24},
                        "snowstorm":         {"snowstorm": 0.40, "cloudy": 0.26, "clear": 0.16, "rain": 0.10, "thundersnow": 0.08},
                        "thundersnow":       {"snowstorm": 0.40, "cloudy": 0.28, "clear": 0.18, "thundersnow": 0.14},
                    },
                    "wind_weights": [0.35, 0.30, 0.20, 0.15],
                },
            }

            params = season_params.get(season, season_params["Spring"])
            transition_map = params["transitions"]
            temp_mid = params["temp_mid"]
            temp_min = params["temp_min"]
            temp_max = params["temp_max"]
            wind_weights = params["wind_weights"]

            # Look back at the previous month for temperature and weather continuity
            prev_month = target_month - 1
            prev_year = target_year
            if prev_month < 1:
                prev_month = 12
                prev_year -= 1
            prev_days_in_month = cal_module.monthrange(prev_year, prev_month)[1]

            lookback_temps = []
            current_weather = "clear"
            found_prev_weather = False
            for d in range(prev_days_in_month, max(prev_days_in_month - 7, 0), -1):
                pk = f"{prev_year}-{prev_month:02d}-{d:02d}"
                if pk in forecast:
                    entry = forecast[pk]
                    t = entry.get("temperature_f")
                    if t is not None:
                        lookback_temps.append(t)
                    if not found_prev_weather:
                        current_weather = entry.get("weather", "clear")
                        found_prev_weather = True

            if lookback_temps:
                current_temp = sum(lookback_temps) / len(lookback_temps)
            else:
                current_temp = temp_mid

            # Clamp starting temp loosely within seasonal range to allow gradual drift
            current_temp = max(temp_min - 10.0, min(temp_max + 10.0, current_temp))

            days_generated = 0
            for day_num in range(1, days_in_month + 1):
                date_key = f"{target_year}-{target_month:02d}-{day_num:02d}"

                if date_key in forecast:
                    # Use existing entry as a continuity anchor without overwriting it
                    current_temp = forecast[date_key].get("temperature_f", current_temp)
                    current_weather = forecast[date_key].get("weather", current_weather)
                    continue

                # Pick today's weather via seasonal transition probabilities
                day_transitions = transition_map.get(current_weather, {"clear": 1.0})
                weather_options = list(day_transitions.keys())
                weather_probs = [day_transitions[w] for w in weather_options]
                today_weather = rng.choices(weather_options, weights = weather_probs, k = 1)[0]

                # Drift temperature with mean reversion toward seasonal midpoint
                temp_pull = (temp_mid - current_temp) * 0.08
                if today_weather in RAIN_TYPES:
                    current_temp += temp_pull + rng.uniform(-6.0, 2.0)
                    current_temp = max(33.0, current_temp)
                elif today_weather in SNOW_TYPES:
                    current_temp += temp_pull + rng.uniform(-10.0, -1.0)
                    current_temp = max(-20.0, current_temp)
                else:
                    current_temp += temp_pull + rng.uniform(-4.0, 4.0)
                current_temp = max(temp_min - 15.0, min(temp_max + 15.0, current_temp))

                # Validate weather/temp consistency
                if today_weather in SNOW_TYPES and current_temp >= 32.0:
                    today_weather = SNOW_TO_RAIN.get(today_weather, "rain")
                elif today_weather in RAIN_TYPES and current_temp <= 32.0:
                    today_weather = RAIN_TO_SNOW.get(today_weather, "snowstorm")

                current_weather = today_weather
                day_wind = rng.choices([0, 1, 2, 3], weights = wind_weights, k = 1)[0]

                # Generate hourly with diurnal curve: coldest ~5am, warmest ~2pm
                hourly = {}
                for hour in range(24):
                    hour_weather = today_weather
                    if rng.random() < 0.15:
                        h_transitions = transition_map.get(today_weather, {"clear": 1.0})
                        h_options = list(h_transitions.keys())
                        h_probs = [h_transitions[w] for w in h_options]
                        if h_options:
                            hour_weather = rng.choices(h_options, weights = h_probs, k = 1)[0]

                    diurnal = -5.0 * math.cos(2.0 * math.pi * (hour - 14) / 24.0)
                    hour_temp = current_temp + diurnal + rng.uniform(-1.5, 1.5)

                    if hour_weather in SNOW_TYPES and hour_temp >= 32.0:
                        hour_weather = SNOW_TO_RAIN.get(hour_weather, "rain")
                    elif hour_weather in RAIN_TYPES and hour_temp <= 32.0:
                        hour_weather = RAIN_TO_SNOW.get(hour_weather, "snowstorm")

                    hour_wind = max(0, min(3, day_wind + rng.randint(-1, 1)))
                    hourly[f"{hour:02d}"] = {
                        "weather": hour_weather,
                        "wind_severity": int(hour_wind),
                        "temperature_f": round(hour_temp, 1)
                    }

                forecast[date_key] = {
                    "weather": today_weather,
                    "wind_severity": int(day_wind),
                    "temperature_f": round(current_temp, 1),
                    "hourly": hourly
                }
                days_generated += 1

            selected_date[0] = None
            detail_title.configure(text = "Select a day to edit")
            hourly_toggle_var.set(False)
            hourly_scroll.pack_forget()
            render_calendar()
            month_name_str = cal_module.month_name[target_month]
            self._popup_show_info("Generated", f"Weather generated for {days_generated} days in {month_name_str} {target_year} ({season}).", sound = "success")

        self._create_sound_button(bottom_frame, "Generate Weather", generate_realistic_weather, width = 180, height = 36, fg_color = "#FF8C00").pack(side = "left", padx = 6)
        self._create_sound_button(bottom_frame, "Download from GitHub", download_weather, width = 180, height = 36).pack(side = "left", padx = 6)
        self._create_sound_button(bottom_frame, "Save Locally", save_weather, width = 180, height = 36, fg_color = "#006400").pack(side = "left", padx = 6)
        self._create_sound_button(
            bottom_frame,
            text = "Back to DM Tools",
            command = lambda:[self._clear_window(), self._open_dm_tools()],
            width = 180,
            height = 36
        ).pack(side = "right", padx = 6)

    def _open_dungeon_generator(self):

        try:
            existing = getattr(self, '_dg_window', None)
            if existing and getattr(existing, 'winfo_exists', lambda:False)():
                try:
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    try:
                        self._popup_show_info("Dungeon Generator", "Dungeon Generator is already open.")
                    except Exception:
                        pass
                except Exception:
                    pass
                return

            try:
                theme = customtkinter.ThemeManager.theme
                toplevel_fg = theme.get('CTkToplevel', {}).get('fg_color')
            except Exception:
                toplevel_fg = None

            if toplevel_fg:
                dg = customtkinter.CTkToplevel(self.root, fg_color = toplevel_fg)
            else:
                dg = customtkinter.CTkToplevel(self.root)

            try:
                dg._is_persistent_window = True
            except Exception:
                pass

            dg.title("Dungeon Generator")
            dg.transient(self.root)
            dg.geometry("900x700")
            dg.minsize(700, 550)

            self._dg_map_window = None

            def _on_close():
                try:

                    if background_combat_timer[0]:
                        try:
                            dg.after_cancel(background_combat_timer[0])
                        except Exception:
                            pass
                        background_combat_timer[0]= None
                except Exception:
                    pass
                try:

                    continuous_gen_active[0]= False
                    if continuous_gen_timer[0]:
                        try:
                            dg.after_cancel(continuous_gen_timer[0])
                        except Exception:
                            pass
                        continuous_gen_timer[0]= None
                except Exception:
                    pass
                try:

                    if self._dg_map_window and self._dg_map_window.winfo_exists():
                        self._dg_map_window.destroy()
                    self._dg_map_window = None
                except Exception:
                    pass
                try:
                    dg.destroy()
                except Exception:
                    pass
                try:
                    self._dg_window = None
                except Exception:
                    self._dg_window = None

            def _confirm_close():
                try:
                    import tkinter as _tk_local
                    from tkinter import messagebox as _mb
                    if _mb.askyesno("Confirm", "Close Dungeon Generator?"):
                        _on_close()
                except Exception:
                    _on_close()

            dg.protocol("WM_DELETE_WINDOW", _confirm_close)

            frm = customtkinter.CTkFrame(dg)
            frm.pack(fill = "both", expand = True, padx = 12, pady = 12)
            lbl = customtkinter.CTkLabel(frm, text = "Dungeon Generator", font = customtkinter.CTkFont(size = 14))
            lbl.pack(pady = 8)

            main_content = customtkinter.CTkFrame(frm)
            main_content.pack(fill = "both", expand = True)

            left_column = customtkinter.CTkFrame(main_content)
            left_column.pack(side = "left", fill = "both", expand = True, padx =(0, 6))

            right_column = customtkinter.CTkFrame(main_content)
            right_column.pack(side = "right", fill = "both", expand = True, padx =(6, 0))

            controls = customtkinter.CTkFrame(left_column)
            controls.pack(fill = "x", pady = 8)

            try:
                self._dg_state = getattr(self, '_dg_state', {})
            except Exception:
                self._dg_state = {}

            diff_labels =["None/Friendly", "Easy", "Medium", "Hard", "Miniboss"]

            try:
                self._dg_state['levels']= _tk.IntVar(value = 1)
                self._dg_state.setdefault('floors', [])

                def _on_levels(v):
                    try:
                        iv = int(round(float(v)))
                        if iv <1:
                            iv = 1
                        if iv >3:
                            iv = 3
                        self._dg_state['levels'].set(iv)
                        lbl_levels.configure(text = f"Levels: {iv}")
                        _rebuild_floors()
                    except Exception:
                        pass

                lbl_levels = customtkinter.CTkLabel(controls, text = f"Levels: {self._dg_state['levels'].get()}")
                lbl_levels.pack(anchor = "w", pady = 4)
                s_levels = customtkinter.CTkSlider(controls, from_ = 1, to = 3, number_of_steps = 2, command = _on_levels)
                s_levels.set(self._dg_state['levels'].get())
                s_levels.pack(fill = "x", pady = 2)

                entrance_frame = customtkinter.CTkFrame(controls)

                floors_container = customtkinter.CTkFrame(left_column)
                floors_container.pack(fill = "x", expand = False, pady = 8)

                def _rebuild_floors():
                    try:
                        for w in floors_container.winfo_children():
                            try:
                                w.destroy()
                            except Exception:
                                pass
                        self._dg_state['floors']=[]
                        levels = max(1, min(3, int(self._dg_state['levels'].get())))
                        if levels !=3:
                            try:
                                entrance_frame.pack_forget()
                            except Exception:
                                pass
                        for i in range(levels):
                            ffrm = customtkinter.CTkFrame(floors_container)
                            ffrm.pack(fill = 'x', pady = 4, padx = 8)
                            floor_label = customtkinter.CTkLabel(ffrm, text = f"Floor {i +1}")
                            floor_label.pack(anchor = 'w')

                            fv_enemy = _tk.IntVar(value = 10)
                            def make_enemy_cb(var, lbl):
                                return lambda v:(var.set(int(round(float(v)))), lbl.configure(text = f"Enemies: {var.get()}"))
                            lbl_fe = customtkinter.CTkLabel(ffrm, text = f"Enemies: {fv_enemy.get()}")
                            lbl_fe.pack(anchor = 'w')
                            s_fe = customtkinter.CTkSlider(ffrm, from_ = 1, to = 50, number_of_steps = 49, command = make_enemy_cb(fv_enemy, lbl_fe))
                            s_fe.set(fv_enemy.get())
                            s_fe.pack(fill = 'x', pady = 2)

                            fv_diff = _tk.IntVar(value = 4)
                            def make_diff_cb(var, lbl):
                                return lambda v:(var.set(int(round(float(v)))), lbl.configure(text = f"Max Difficulty: {diff_labels[var.get()]}"))
                            lbl_fd = customtkinter.CTkLabel(ffrm, text = f"Max Difficulty: {diff_labels[fv_diff.get()]}")
                            lbl_fd.pack(anchor = 'w')
                            s_fd = customtkinter.CTkSlider(ffrm, from_ = 0, to = 4, number_of_steps = 4, command = make_diff_cb(fv_diff, lbl_fd))
                            s_fd.set(fv_diff.get())
                            s_fd.pack(fill = 'x', pady = 2)

                            try:
                                fv_x = _tk.IntVar(value = 20)
                                fv_y = _tk.IntVar(value = 20)

                                def make_x_cb(var, lbl):
                                    return lambda v:(var.set(int(round(float(v)))), lbl.configure(text = f"X Size: {var.get()}"))

                                def make_y_cb(var, lbl):
                                    return lambda v:(var.set(int(round(float(v)))), lbl.configure(text = f"Y Size: {var.get()}"))

                                lbl_x = customtkinter.CTkLabel(ffrm, text = f"X Size: {fv_x.get()}")
                                lbl_x.pack(anchor = 'w')
                                s_x = customtkinter.CTkSlider(ffrm, from_ = 10, to = 50, number_of_steps = 8, command = make_x_cb(fv_x, lbl_x))
                                s_x.set(fv_x.get())
                                s_x.pack(fill = 'x', pady = 2)

                                lbl_y = customtkinter.CTkLabel(ffrm, text = f"Y Size: {fv_y.get()}")
                                lbl_y.pack(anchor = 'w')
                                s_y = customtkinter.CTkSlider(ffrm, from_ = 10, to = 50, number_of_steps = 8, command = make_y_cb(fv_y, lbl_y))
                                s_y.set(fv_y.get())
                                s_y.pack(fill = 'x', pady = 2)
                            except Exception:
                                logging.exception("Failed to create per-floor size controls")

                            fv_transport = None
                            try:

                                try:
                                    tm_var = self._dg_state.get('transport_mode')
                                    tm = tm_var.get()if hasattr(tm_var, 'get')else(tm_var or 'Multiple')
                                except Exception:
                                    tm = 'Multiple'

                                if levels >1 and i <(levels -1)and not(tm =='Single'and i !=0):
                                    fv_transport = _tk.StringVar(value = "Stairs")
                                    lbl_ft = customtkinter.CTkLabel(ffrm, text = "Transport: Stairs")
                                    lbl_ft.pack(anchor = 'w')
                                    opt = customtkinter.CTkOptionMenu(ffrm, values =["Stairs", "Elevator"], command = lambda v, var = fv_transport, l = lbl_ft:(var.set(v), l.configure(text = f"Transport: {v}")))
                                    opt.set(fv_transport.get())
                                    opt.pack(fill = 'x', pady = 2)
                            except Exception:
                                logging.exception("Failed to create transport option for floor")

                            try:
                                self._dg_state['floors'].append({'enemy_count':fv_enemy, 'difficulty':fv_diff, 'transport':fv_transport, 'x_size':fv_x, 'y_size':fv_y})
                            except Exception:
                                self._dg_state['floors'].append({'enemy_count':fv_enemy, 'difficulty':fv_diff, 'transport':fv_transport})

                        try:
                            for w in entrance_frame.winfo_children():
                                try:
                                    w.destroy()
                                except Exception:
                                    pass
                            if levels ==3:

                                try:
                                    entrance_frame.pack(fill = 'x', pady = 4)
                                except Exception:
                                    pass
                                self._dg_state.setdefault('transport_mode', _tk.StringVar(value = 'Multiple'))
                                lbl_em = customtkinter.CTkLabel(entrance_frame, text = 'Transport Mode:')
                                lbl_em.pack(side = 'left', padx = 6)
                                def _set_transport_mode(v):
                                    try:
                                        self._dg_state['transport_mode'].set(v)
                                    except Exception:
                                        pass
                                    try:
                                        _rebuild_floors()
                                    except Exception:
                                        pass
                                opt_em = customtkinter.CTkOptionMenu(entrance_frame, values =['Multiple', 'Single'], command = _set_transport_mode)
                                opt_em.set(self._dg_state.get('transport_mode', _tk.StringVar(value = 'Multiple')).get())
                                opt_em.pack(side = 'left', padx = 6)
                        except Exception:
                            logging.exception('Failed to build entrance mode control')
                    except Exception:
                        logging.exception("Failed to rebuild floor controls")

                _rebuild_floors()
            except Exception:
                logging.exception("Failed to create levels/floors controls")

            dungeon_display_frame = customtkinter.CTkFrame(right_column)
            dungeon_display_frame.pack(fill = "both", expand = True, pady = 8)

            location_label = customtkinter.CTkLabel(dungeon_display_frame, text = "No dungeon generated", font = customtkinter.CTkFont(size = 12, weight = "bold"))
            location_label.pack(anchor = 'w', pady = 4)

            room_info_label = customtkinter.CTkLabel(dungeon_display_frame, text = "", font = customtkinter.CTkFont(size = 11), wraplength = 280, justify = "left")
            room_info_label.pack(anchor = 'w', pady = 4)

            grid_tiles = {}
            grid_rooms = {}
            TILE_SIZE = 20
            grid_canvas =[None]
            tooltip_label =[None]

            def _open_map_window():

                try:
                    if self._dg_map_window and self._dg_map_window.winfo_exists():
                        self._dg_map_window.focus_force()
                        self._dg_map_window.lift()
                        return
                except Exception:
                    pass

                try:
                    theme = customtkinter.ThemeManager.theme
                    toplevel_fg = theme.get('CTkToplevel', {}).get('fg_color')
                except Exception:
                    toplevel_fg = None

                if toplevel_fg:
                    map_win = customtkinter.CTkToplevel(dg, fg_color = toplevel_fg)
                else:
                    map_win = customtkinter.CTkToplevel(dg)

                map_win.title("Dungeon Map")
                map_win.transient(dg)

                dungeon = self._dg_state.get('generated_dungeon')
                if dungeon and dungeon.get("floors"):
                    floor_idx = self._dg_state.get('current_floor', 0)
                    floor = dungeon["floors"][floor_idx]if floor_idx <len(dungeon["floors"])else dungeon["floors"][0]
                    x_size = floor.get("x_size", 20)
                    y_size = floor.get("y_size", 20)
                    win_width = min(max(x_size *TILE_SIZE +80, 400), 1000)
                    win_height = min(max(y_size *TILE_SIZE +120, 350), 800)
                else:
                    win_width = 500
                    win_height = 400

                map_win.geometry(f"{win_width}x{win_height}")

                def _on_map_close():
                    try:
                        grid_canvas[0]= None
                        tooltip_label[0]= None
                        map_win.destroy()
                        self._dg_map_window = None
                    except Exception:
                        pass

                map_win.protocol("WM_DELETE_WINDOW", _on_map_close)
                self._dg_map_window = map_win

                map_frm = customtkinter.CTkFrame(map_win)
                map_frm.pack(fill = "both", expand = True, padx = 8, pady = 8)

                map_title = customtkinter.CTkLabel(map_frm, text = "Dungeon Map", font = customtkinter.CTkFont(size = 12, weight = "bold"))
                map_title.pack(pady = 4)

                canvas = _tk.Canvas(map_frm, bg = "#1a1a1a", highlightthickness = 0)
                canvas.pack(fill = 'both', expand = True, pady = 4)
                grid_canvas[0]= canvas # type: ignore

                tip_label = customtkinter.CTkLabel(map_frm, text = "", font = customtkinter.CTkFont(size = 10), wraplength = 400, justify = "left", fg_color =("gray80", "gray20"), corner_radius = 6)
                tooltip_label[0]= tip_label # type: ignore

                def _on_tile_hover(event):

                    try:
                        if not grid_canvas[0]:
                            return
                        canvas_x = grid_canvas[0].canvasx(event.x)
                        canvas_y = grid_canvas[0].canvasy(event.y)
                        tile_x = int(canvas_x //TILE_SIZE)
                        tile_y = int(canvas_y //TILE_SIZE)

                        room = grid_rooms.get((tile_x, tile_y))
                        if room:
                            info_lines =[]
                            info_lines.append(f"Room: {room.get('name', 'Unknown')}")
                            info_lines.append(f"Type: {room.get('type', 'unknown')}")

                            enemies =[e for e in room.get("enemies", [])if e.get("alive", True)]
                            if enemies:
                                enemy_info =[]
                                for e in enemies:
                                    name = e.get("name", "Unknown")
                                    health = e.get("health", 100)
                                    enemy_info.append(f"{name}({health}HP)")
                                info_lines.append(f"Enemies: {', '.join(enemy_info)}")

                            friendlies =[f for f in room.get("friendlies", [])if f.get("alive", True)]
                            if friendlies:
                                friendly_info =[]
                                for f in friendlies:
                                    name = f.get("name", "Unknown")
                                    health = f.get("health", 100)
                                    friendly_info.append(f"{name}({health}HP)")
                                info_lines.append(f"Friendlies: {', '.join(friendly_info)}")

                            loot_spawn = room.get("loot_spawn", [])
                            if loot_spawn:
                                info_lines.append(f"Loot spawns: {len(loot_spawn)}")

                            doors = room.get("doors_state", {})
                            if doors:
                                door_info =[]
                                for pos, state in doors.items():
                                    lock_status = "🔒"if state.get("locked")and not state.get("picked")else "🔓"
                                    door_info.append(f"{pos}: {lock_status}")
                                info_lines.append(f"Doors: {', '.join(door_info)}")

                            if room.get("type")=="transport":
                                transport_info =[]
                                if room.get("is_entry_transport")and room.get("leads_to_floor"):
                                    transport_info.append(f"↑ Floor {room.get('leads_to_floor')}")
                                if room.get("is_exit_transport")and room.get("leads_to_floor"):
                                    transport_info.append(f"↓ Floor {room.get('leads_to_floor')}")
                                if room.get("also_leads_to_floor"):
                                    transport_info.append(f"↓ Floor {room.get('also_leads_to_floor')}")
                                if transport_info:
                                    info_lines.append("Transport: "+", ".join(transport_info))
                                else:
                                    info_lines.append(f"→ Floor {room.get('leads_to_floor', '?')}")

                            if room.get("visited"):
                                info_lines.append("(Visited)")

                            if tooltip_label[0]:
                                tooltip_label[0].configure(text = "\n".join(info_lines))
                                tooltip_label[0].pack(anchor = 'w', pady = 2)
                        else:
                            if tooltip_label[0]:
                                tooltip_label[0].configure(text = "Empty")
                                tooltip_label[0].pack(anchor = 'w', pady = 2)
                    except Exception:
                        pass

                def _on_tile_leave(event):

                    try:
                        if tooltip_label[0]:
                            tooltip_label[0].pack_forget()
                    except Exception:
                        pass

                def _on_tile_click(event):

                    try:
                        if not grid_canvas[0]:
                            return
                        canvas_x = grid_canvas[0].canvasx(event.x)
                        canvas_y = grid_canvas[0].canvasy(event.y)
                        tile_x = int(canvas_x //TILE_SIZE)
                        tile_y = int(canvas_y //TILE_SIZE)

                        clicked_room = grid_rooms.get((tile_x, tile_y))
                        if not clicked_room:
                            return

                        current_room = _get_current_room()
                        if not current_room:
                            return

                        exits = _get_available_exits()
                        for exit_info in exits:
                            if exit_info.get("to_room")==clicked_room.get("room_id"):
                                _move_to_room(exit_info)
                                return

                    except Exception:
                        pass

                canvas.bind("<Motion>", _on_tile_hover)
                canvas.bind("<Leave>", _on_tile_leave)
                canvas.bind("<Button-1>", _on_tile_click)

                map_win.bind("<Up>", _handle_arrow_key)
                map_win.bind("<Down>", _handle_arrow_key)
                map_win.bind("<Left>", _handle_arrow_key)
                map_win.bind("<Right>", _handle_arrow_key)
                map_win.bind("<w>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Up'})()))
                map_win.bind("<s>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Down'})()))
                map_win.bind("<a>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Left'})()))
                map_win.bind("<d>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Right'})()))
                map_win.bind("<W>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Up'})()))
                map_win.bind("<S>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Down'})()))
                map_win.bind("<A>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Left'})()))
                map_win.bind("<D>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Right'})()))

                map_win.bind("<Shift-Up>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Up'})()))
                map_win.bind("<Shift-Down>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Down'})()))
                map_win.bind("<Shift-w>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Up'})()))
                map_win.bind("<Shift-s>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Down'})()))
                map_win.bind("<Shift-W>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Up'})()))
                map_win.bind("<Shift-S>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Down'})()))

                map_win.focus_force()

                _draw_grid()

            def _flash_muzzle(rx, ry, original_color):

                try:
                    if not grid_canvas[0]or not grid_canvas[0].winfo_exists():
                        return
                    if(rx, ry)not in grid_tiles:
                        return

                    tile_id = grid_tiles[(rx, ry)]

                    grid_canvas[0].itemconfigure(tile_id, fill = "#ffff00")

                    def restore():
                        try:
                            if grid_canvas[0]and grid_canvas[0].winfo_exists()and(rx, ry)in grid_tiles:
                                grid_canvas[0].itemconfigure(grid_tiles[(rx, ry)], fill = original_color)
                        except Exception:
                            pass

                    dg.after(80, restore)
                except Exception:
                    pass

            def _schedule_muzzle_flashes(rx, ry, shots, cyclic_delay, start_delay):

                combat_color = "#cc6633"

                for i in range(shots):
                    shot_delay = start_delay +(i *cyclic_delay)
                    dg.after(shot_delay, lambda x = rx, y = ry, c = combat_color:_flash_muzzle(x, y, c))

            def _draw_grid():

                try:
                    if not grid_canvas[0]:
                        return
                    grid_canvas[0].delete("all")
                    grid_tiles.clear()
                    grid_rooms.clear()

                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        return

                    floor_idx = self._dg_state.get('current_floor', 0)
                    if floor_idx >=len(dungeon["floors"]):
                        return

                    floor = dungeon["floors"][floor_idx]
                    x_size = floor.get("x_size", 20)
                    y_size = floor.get("y_size", 20)
                    current_room_id = self._dg_state.get('current_room_id')

                    canvas_width = x_size *TILE_SIZE +2
                    canvas_height = y_size *TILE_SIZE +2
                    grid_canvas[0].configure(width = min(canvas_width, 800), height = min(canvas_height, 600))

                    for gx in range(x_size):
                        for gy in range(y_size):
                            x1 = gx *TILE_SIZE
                            y1 = gy *TILE_SIZE
                            x2 = x1 +TILE_SIZE -1
                            y2 = y1 +TILE_SIZE -1
                            tile_id = grid_canvas[0].create_rectangle(x1, y1, x2, y2, fill = "#1a1a1a", outline = "#333333")
                            grid_tiles[(gx, gy)]= tile_id

                    for room in floor["rooms"]:
                        pos = room.get("position", {})
                        rx = pos.get("x", 0)
                        ry = pos.get("y", 0)

                        if rx <0 or rx >=x_size or ry <0 or ry >=y_size:
                            continue

                        enemies =[e for e in room.get("enemies", [])if e.get("alive", True)]
                        friendlies =[f for f in room.get("friendlies", [])if f.get("alive", True)]
                        loot_spawn = room.get("loot_spawn", [])
                        enemies_cleared = room.get("enemies_cleared", False)
                        has_pending_loot = room.get("pending_loot", [])

                        if enemies and friendlies:
                            fill_color = "#cc6633"
                        elif enemies:
                            fill_color = "#cc3333"
                        elif friendlies:
                            fill_color = "#3366cc"
                        elif has_pending_loot:
                            fill_color = "#33cc33"
                        elif loot_spawn:
                            fill_color = "#33cc33"
                        elif room.get("type")=="transport":
                            fill_color = "#3399ff"
                        elif room.get("visited"):
                            fill_color = "#808080"
                        else:
                            fill_color = "#e0e0e0"

                        outline_color = "#333333"
                        outline_width = 1

                        if room.get("type")=="transport":
                            outline_color = "#00ffff"
                            outline_width = 2

                        if friendlies and not enemies:
                            outline_color = "#00ff00"
                            outline_width = 2
                        elif friendlies and enemies:
                            outline_color = "#ffaa00"
                            outline_width = 2

                        if room.get("room_id")==current_room_id:
                            outline_color = "#ffcc00"
                            outline_width = 3

                        x1 = rx *TILE_SIZE
                        y1 = ry *TILE_SIZE
                        x2 = x1 +TILE_SIZE -1
                        y2 = y1 +TILE_SIZE -1

                        if(rx, ry)in grid_tiles:
                            grid_canvas[0].delete(grid_tiles[(rx, ry)])
                        tile_id = grid_canvas[0].create_rectangle(x1, y1, x2, y2, fill = fill_color, outline = outline_color, width = outline_width)
                        grid_tiles[(rx, ry)]= tile_id
                        grid_rooms[(rx, ry)]= room

                        room_type = room.get("type", "")
                        indicator = ""
                        if room_type =="entrance":
                            indicator = "E"
                        elif room_type =="transport":
                            indicator = "T"
                        elif room_type =="hallway":
                            indicator = "H"
                        elif room_type =="room":
                            indicator = "R"

                        if indicator:
                            text_color = "#000000"if fill_color in["#e0e0e0", "#33cc33", "#808080", "#3399ff", "#3366cc"]else "#ffffff"
                            grid_canvas[0].create_text(x1 +TILE_SIZE //2, y1 +TILE_SIZE //2, text = indicator, fill = text_color, font =("Arial", 8, "bold"))

                    for conn in floor.get("connections", []):
                        from_room = None
                        to_room = None
                        for room in floor["rooms"]:
                            if room.get("room_id")==conn.get("from_room"):
                                from_room = room
                            if room.get("room_id")==conn.get("to_room"):
                                to_room = room

                        if from_room and to_room:
                            from_pos = from_room.get("position", {})
                            to_pos = to_room.get("position", {})
                            fx = from_pos.get("x", 0)*TILE_SIZE +TILE_SIZE //2
                            fy = from_pos.get("y", 0)*TILE_SIZE +TILE_SIZE //2
                            tx = to_pos.get("x", 0)*TILE_SIZE +TILE_SIZE //2
                            ty = to_pos.get("y", 0)*TILE_SIZE +TILE_SIZE //2
                            grid_canvas[0].create_line(fx, fy, tx, ty, fill = "#666666", width = 2)

                except Exception as e:
                    logging.exception("Failed to draw grid")

            nav_frame = customtkinter.CTkFrame(dungeon_display_frame)
            nav_frame.pack(fill = 'x', pady = 8)

            door_frame = customtkinter.CTkFrame(dungeon_display_frame)
            door_frame.pack(fill = 'x', pady = 4)

            door_status_label = customtkinter.CTkLabel(door_frame, text = "", font = customtkinter.CTkFont(size = 11))
            door_status_label.pack(side = 'left', padx = 6)

            pick_door_btn = customtkinter.CTkButton(door_frame, text = "Door Picked Successfully", state = "disabled", width = 180)
            pick_door_btn.pack(side = 'left', padx = 6)

            combat_frame = customtkinter.CTkFrame(dungeon_display_frame)
            combat_frame.pack(fill = 'x', pady = 4)

            kill_enemy_btn = customtkinter.CTkButton(combat_frame, text = "Mark Enemies Killed", state = "disabled", width = 160)
            kill_enemy_btn.pack(side = 'left', padx = 6)

            collect_loot_btn = customtkinter.CTkButton(combat_frame, text = "Collect Loot", state = "disabled", width = 120)
            collect_loot_btn.pack(side = 'left', padx = 6)

            combat_log_frame = customtkinter.CTkFrame(dungeon_display_frame)
            combat_log_frame.pack(fill = 'x', pady = 4)

            combat_log_label = customtkinter.CTkLabel(combat_log_frame, text = "Combat Log:", font = customtkinter.CTkFont(size = 10, weight = "bold"))
            combat_log_label.pack(anchor = 'w', padx = 6)

            combat_log_text = customtkinter.CTkTextbox(combat_log_frame, height = 80, font = customtkinter.CTkFont(size = 9))
            combat_log_text.pack(fill = 'x', padx = 6, pady = 2)
            combat_log_text.configure(state = "disabled")

            def _add_combat_log(message):

                try:
                    combat_log_text.configure(state = "normal")
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    combat_log_text.insert("end", f"[{timestamp}]{message}\n")
                    combat_log_text.see("end")

                    lines = combat_log_text.get("1.0", "end").split("\n")
                    if len(lines)>50:
                        combat_log_text.delete("1.0", f"{len(lines)-50}.0")
                    combat_log_text.configure(state = "disabled")
                except Exception:
                    pass

            background_combat_timer =[None]
            continuous_gen_active =[False]
            continuous_gen_timer =[None]
            map_editor_window =[None]

            def _open_map_editor():

                try:
                    if map_editor_window[0]and map_editor_window[0].winfo_exists():
                        map_editor_window[0].focus_force()
                        map_editor_window[0].lift()
                        return
                except Exception:
                    pass

                try:
                    theme = customtkinter.ThemeManager.theme
                    toplevel_fg = theme.get('CTkToplevel', {}).get('fg_color')
                except Exception:
                    toplevel_fg = None

                if toplevel_fg:
                    editor_win = customtkinter.CTkToplevel(dg, fg_color = toplevel_fg)
                else:
                    editor_win = customtkinter.CTkToplevel(dg)

                editor_win.title("Map Editor")
                editor_win.transient(dg)
                editor_win.geometry("800x600")
                editor_win.minsize(600, 400)
                map_editor_window[0]= editor_win # type: ignore

                editor_state = {
                'current_tool':'select',
                'selected_room':None,
                'grid_size_x':20,
                'grid_size_y':20,
                }

                def _on_editor_close():
                    try:
                        map_editor_window[0]= None
                        editor_win.destroy()
                    except Exception:
                        pass

                editor_win.protocol("WM_DELETE_WINDOW", _on_editor_close)

                editor_frame = customtkinter.CTkFrame(editor_win)
                editor_frame.pack(fill = "both", expand = True, padx = 8, pady = 8)

                toolbar = customtkinter.CTkFrame(editor_frame)
                toolbar.pack(fill = "x", pady = 4)

                tool_label = customtkinter.CTkLabel(toolbar, text = "Tool:")
                tool_label.pack(side = "left", padx = 4)

                tool_buttons = {}

                def _set_tool(tool_name):
                    editor_state['current_tool']= tool_name
                    for name, btn in tool_buttons.items():
                        if name ==tool_name:
                            btn.configure(fg_color =("#3B8ED0", "#1F6AA5"))
                        else:
                            btn.configure(fg_color =("gray70", "gray30"))

                for tool in['select', 'room', 'hallway', 'transport', 'entrance', 'delete']:
                    btn = customtkinter.CTkButton(toolbar, text = tool.capitalize(), width = 70,
                    command = lambda t = tool:_set_tool(t),
                    fg_color =("gray70", "gray30"))
                    btn.pack(side = "left", padx = 2)
                    tool_buttons[tool]= btn

                tool_buttons['select'].configure(fg_color =("#3B8ED0", "#1F6AA5"))

                size_frame = customtkinter.CTkFrame(toolbar)
                size_frame.pack(side = "right", padx = 8)

                def _update_grid_size():
                    try:
                        editor_state['grid_size_x']= int(x_size_entry.get())
                        editor_state['grid_size_y']= int(y_size_entry.get())
                        _redraw_editor_grid()
                    except ValueError:
                        pass

                customtkinter.CTkLabel(size_frame, text = "X:").pack(side = "left")
                x_size_entry = customtkinter.CTkEntry(size_frame, width = 40)
                x_size_entry.insert(0, "20")
                x_size_entry.pack(side = "left", padx = 2)

                customtkinter.CTkLabel(size_frame, text = "Y:").pack(side = "left")
                y_size_entry = customtkinter.CTkEntry(size_frame, width = 40)
                y_size_entry.insert(0, "20")
                y_size_entry.pack(side = "left", padx = 2)

                resize_btn = customtkinter.CTkButton(size_frame, text = "Resize", width = 60, command = _update_grid_size)
                resize_btn.pack(side = "left", padx = 4)

                canvas_frame = customtkinter.CTkFrame(editor_frame)
                canvas_frame.pack(fill = "both", expand = True, pady = 4)

                editor_canvas = _tk.Canvas(canvas_frame, bg = "#1a1a1a", highlightthickness = 0)
                editor_canvas.pack(fill = "both", expand = True)

                EDITOR_TILE_SIZE = 25
                editor_rooms = {}
                editor_connections =[]
                room_id_counter =[0]

                def _redraw_editor_grid():
                    editor_canvas.delete("all")
                    x_size = editor_state['grid_size_x']
                    y_size = editor_state['grid_size_y']

                    for x in range(x_size +1):
                        editor_canvas.create_line(x *EDITOR_TILE_SIZE, 0,
                        x *EDITOR_TILE_SIZE, y_size *EDITOR_TILE_SIZE,
                        fill = "#333333")
                    for y in range(y_size +1):
                        editor_canvas.create_line(0, y *EDITOR_TILE_SIZE,
                        x_size *EDITOR_TILE_SIZE, y *EDITOR_TILE_SIZE,
                        fill = "#333333")

                    for(rx, ry), room in editor_rooms.items():
                        x1 = rx *EDITOR_TILE_SIZE
                        y1 = ry *EDITOR_TILE_SIZE
                        x2 = x1 +EDITOR_TILE_SIZE -1
                        y2 = y1 +EDITOR_TILE_SIZE -1

                        room_type = room.get("type", "room")
                        if room_type =="entrance":
                            color = "#ffcc00"
                        elif room_type =="transport":
                            color = "#3399ff"
                        elif room_type =="hallway":
                            color = "#666666"
                        else:
                            color = "#808080"

                        editor_canvas.create_rectangle(x1, y1, x2, y2, fill = color, outline = "#ffffff")

                        indicator = room_type[0].upper()
                        editor_canvas.create_text(x1 +EDITOR_TILE_SIZE //2, y1 +EDITOR_TILE_SIZE //2,
                        text = indicator, fill = "#ffffff", font =("Arial", 10, "bold"))

                    for conn in editor_connections:
                        if conn['from']in editor_rooms and conn['to']in editor_rooms:
                            fx, fy = conn['from']
                            tx, ty = conn['to']
                            editor_canvas.create_line(
                            fx *EDITOR_TILE_SIZE +EDITOR_TILE_SIZE //2,
                            fy *EDITOR_TILE_SIZE +EDITOR_TILE_SIZE //2,
                            tx *EDITOR_TILE_SIZE +EDITOR_TILE_SIZE //2,
                            ty *EDITOR_TILE_SIZE +EDITOR_TILE_SIZE //2,
                            fill = "#00ff00", width = 2
                            )

                def _on_editor_click(event):
                    x = event.x //EDITOR_TILE_SIZE
                    y = event.y //EDITOR_TILE_SIZE

                    if x <0 or x >=editor_state['grid_size_x']or y <0 or y >=editor_state['grid_size_y']:
                        return

                    tool = editor_state['current_tool']

                    if tool =='select':
                        editor_state['selected_room']=(x, y)if(x, y)in editor_rooms else None
                    elif tool =='delete':
                        if(x, y)in editor_rooms:
                            del editor_rooms[(x, y)]

                            editor_connections[:]=[c for c in editor_connections
                            if c['from']!=(x, y)and c['to']!=(x, y)]
                    elif tool in['room', 'hallway', 'transport', 'entrance']:
                        if(x, y)not in editor_rooms:
                            room_id_counter[0]+=1
                            editor_rooms[(x, y)]= {
                            'room_id':room_id_counter[0],
                            'type':tool,
                            'name':f"{tool.capitalize()} {room_id_counter[0]}",
                            'position':{'x':x, 'y':y},
                            'attachment_points':[],
                            'doors':[],
                            'enemies':[],
                            'friendlies':[],
                            'loot_spawn':[],
                            }

                            for dx, dy, direction in[(0, -1, 'top'), (0, 1, 'bottom'), (-1, 0, 'left'), (1, 0, 'right')]:
                                adj =(x +dx, y +dy)
                                if adj in editor_rooms:
                                    editor_connections.append({'from':(x, y), 'to':adj, 'direction':direction})

                    _redraw_editor_grid()

                editor_canvas.bind("<Button-1>", _on_editor_click)

                bottom_frame = customtkinter.CTkFrame(editor_frame)
                bottom_frame.pack(fill = "x", pady = 4)

                def _apply_to_dungeon():

                    if not editor_rooms:
                        self._popup_show_info("Error", "No rooms placed!", sound = "error")
                        return

                    floor_data = {
                    'floor_number':1,
                    'x_size':editor_state['grid_size_x'],
                    'y_size':editor_state['grid_size_y'],
                    'rooms':[],
                    'connections':[],
                    'enemies_remaining':0
                    }

                    for(rx, ry), room in editor_rooms.items():
                        floor_data['rooms'].append(room.copy())

                    for conn in editor_connections:
                        from_room = editor_rooms.get(conn['from'])
                        to_room = editor_rooms.get(conn['to'])
                        if from_room and to_room:
                            floor_data['connections'].append({
                            'from_room':from_room['room_id'],
                            'to_room':to_room['room_id'],
                            'direction':conn.get('direction', 'bottom')
                            })

                    dungeon = {
                    'floors':[floor_data],
                    'metadata':{'generated_at':datetime.now().isoformat(), 'manual_edit':True}
                    }

                    self._dg_state['generated_dungeon']= dungeon
                    self._dg_state['current_floor']= 0

                    start_room = None
                    for room in floor_data['rooms']:
                        if room.get('type')=='entrance':
                            start_room = room['room_id']
                            break
                    if start_room is None and floor_data['rooms']:
                        start_room = floor_data['rooms'][0]['room_id']
                    self._dg_state['current_room_id']= start_room

                    _update_display()
                    _draw_grid()
                    self._popup_show_info("Map Editor", f"Applied layout with {len(floor_data['rooms'])} rooms!")

                def _clear_editor():
                    editor_rooms.clear()
                    editor_connections.clear()
                    room_id_counter[0]= 0
                    _redraw_editor_grid()

                def _load_current_floor():

                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon or not dungeon.get('floors'):
                        self._popup_show_info("Error", "No dungeon to load!", sound = "error")
                        return

                    floor_idx = self._dg_state.get('current_floor', 0)
                    floor = dungeon['floors'][floor_idx]

                    editor_rooms.clear()
                    editor_connections.clear()

                    editor_state['grid_size_x']= floor.get('x_size', 20)
                    editor_state['grid_size_y']= floor.get('y_size', 20)
                    x_size_entry.delete(0, 'end')
                    x_size_entry.insert(0, str(editor_state['grid_size_x']))
                    y_size_entry.delete(0, 'end')
                    y_size_entry.insert(0, str(editor_state['grid_size_y']))

                    max_id = 0
                    for room in floor.get('rooms', []):
                        pos = room.get('position', {})
                        rx, ry = pos.get('x', 0), pos.get('y', 0)
                        editor_rooms[(rx, ry)]= room.copy()
                        max_id = max(max_id, room.get('room_id', 0))

                    room_id_counter[0]= max_id

                    for conn in floor.get('connections', []):
                        from_id = conn.get('from_room')
                        to_id = conn.get('to_room')
                        from_pos = None
                        to_pos = None
                        for(pos, room)in editor_rooms.items():
                            if room.get('room_id')==from_id:
                                from_pos = pos
                            if room.get('room_id')==to_id:
                                to_pos = pos
                        if from_pos and to_pos:
                            editor_connections.append({
                            'from':from_pos,
                            'to':to_pos,
                            'direction':conn.get('direction')
                            })

                    _redraw_editor_grid()
                    self._popup_show_info("Map Editor", f"Loaded floor {floor_idx +1} with {len(editor_rooms)} rooms")

                apply_btn = customtkinter.CTkButton(bottom_frame, text = "Apply to Dungeon", width = 120, command = _apply_to_dungeon)
                apply_btn.pack(side = "left", padx = 4)

                load_btn = customtkinter.CTkButton(bottom_frame, text = "Load Current Floor", width = 120, command = _load_current_floor)
                load_btn.pack(side = "left", padx = 4)

                clear_btn = customtkinter.CTkButton(bottom_frame, text = "Clear", width = 80, command = _clear_editor)
                clear_btn.pack(side = "left", padx = 4)

                close_btn = customtkinter.CTkButton(bottom_frame, text = "Close", width = 80, command = _on_editor_close)
                close_btn.pack(side = "right", padx = 4)

                info_label = customtkinter.CTkLabel(editor_frame,
                text = "Click to place rooms.Select tool to view, Delete to remove.Rooms auto-connect to neighbors.",
                font = customtkinter.CTkFont(size = 10))
                info_label.pack(pady = 2)

                _redraw_editor_grid()

            map_btn_frame = customtkinter.CTkFrame(dungeon_display_frame)
            map_btn_frame.pack(fill = 'x', pady = 4)
            open_map_btn = customtkinter.CTkButton(map_btn_frame, text = "Open Map", width = 120, command = lambda:_open_map_window())
            open_map_btn.pack(side = 'left', padx = 6)

            edit_map_btn = customtkinter.CTkButton(map_btn_frame, text = "Map Editor", width = 100, command = _open_map_editor)
            edit_map_btn.pack(side = 'left', padx = 6)

            self._dg_state.setdefault('generated_dungeon', None)
            self._dg_state.setdefault('current_floor', 0)
            self._dg_state.setdefault('current_room_id', None)
            self._dg_state.setdefault('pending_door', None)
            self._dg_state.setdefault('movement_locked', False)

            def _load_rooms_table():

                try:
                    tbl_path = get_current_table_path()
                    if not tbl_path or not os.path.exists(tbl_path):
                        return[]
                    with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                        table_data = json.load(f)
                    return table_data.get("tables", {}).get("rooms", [])
                except Exception as e:
                    logging.exception("Failed to load rooms table")
                    return[]

            def _load_enemies_table():

                try:
                    tbl_path = get_current_table_path()
                    if not tbl_path or not os.path.exists(tbl_path):
                        return[]
                    with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                        table_data = json.load(f)
                    return table_data.get("tables", {}).get("enemy_drops", [])
                except Exception as e:
                    logging.exception("Failed to load enemies table")
                    return[]

            _distant_combat_sound_cache = {}

            def _play_distant_combat_sound(sound_path, volume = 0.15):

                try:
                    sound = _distant_combat_sound_cache.get(sound_path)
                    if sound is None:
                        if not os.path.exists(sound_path):
                            return
                        sound = pygame.mixer.Sound(sound_path)
                        _distant_combat_sound_cache[sound_path] = sound
                    sound.set_volume(volume)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
                except Exception as e:
                    logging.debug(f"Failed to play distant combat sound: {e}")

            def _play_dungeon_sound(sound_name, volume = 0.3):

                try:
                    sound_paths = {
                    "step":[
                    os.path.join("sounds", "misc", "dungeon", f"step{i}.ogg")
                    for i in range(4)
                    ],
                    "locked":os.path.join("sounds", "misc", "dungeon", "locked.ogg"),
                    "door":os.path.join("sounds", "misc", "dungeon", "door.ogg"),
                    "elevator":os.path.join("sounds", "misc", "dungeon", "elevator.wav"),
                    "unlock":os.path.join("sounds", "misc", "lockpicking", "unlock.ogg"),
                    }

                    if sound_name =="step":

                        available_steps =[p for p in sound_paths["step"]if os.path.exists(p)]
                        if available_steps:
                            sound_path = random.choice(available_steps)
                        else:
                            return
                    else:
                        sound_path = sound_paths.get(sound_name)
                        if not sound_path or not os.path.exists(sound_path):
                            return

                    sound = pygame.mixer.Sound(sound_path)
                    sound.set_volume(volume)
                    channel = pygame.mixer.find_channel()
                    if channel:
                        channel.play(sound)
                except Exception as e:
                    logging.debug(f"Failed to play dungeon sound '{sound_name}': {e}")

            def _get_weapon_sound_for_npc(npc):

                try:
                    items = npc.get("items", [])

                    for item in items:
                        if isinstance(item, dict):
                            item_id = item.get("id")

                            if item_id:

                                caliber_folders =["556", "762_39", "9x19", "45acp", "308", "12gauge", "223"]
                                for cal in caliber_folders:
                                    sound_dir = os.path.join("sounds", "firearms", cal)
                                    if os.path.isdir(sound_dir):
                                        sounds = glob.glob(os.path.join(sound_dir, "*.wav"))+glob.glob(os.path.join(sound_dir, "*.ogg"))
                                        if sounds:
                                            return random.choice(sounds)

                    fallback_cals =["556", "762_39", "9x19"]
                    for cal in fallback_cals:
                        sound_dir = os.path.join("sounds", "firearms", cal)
                        if os.path.isdir(sound_dir):
                            sounds = glob.glob(os.path.join(sound_dir, "*.wav"))+glob.glob(os.path.join(sound_dir, "*.ogg"))
                            if sounds:
                                return random.choice(sounds)
                except Exception as e:
                    logging.debug(f"Failed to get weapon sound: {e}")
                return None

            def _get_npc_weapon_info(npc):

                try:
                    items = npc.get("items", [])
                    for item in items:
                        if isinstance(item, dict)and item.get("firearm"):
                            return item
                        elif isinstance(item, (int, float)):

                            for category in["rifles", "smgs", "pistols", "shotguns", "machineguns", "snipers"]:
                                weapons = table_data.get("tables", {}).get(category, [])
                                for weapon in weapons:
                                    if weapon.get("id")==item:
                                        return weapon
                except Exception as e:
                    logging.debug(f"Failed to get NPC weapon info: {e}")
                return None

            def _is_manual_action(weapon):

                if not weapon:
                    return False
                actions = weapon.get("action", [])
                manual_actions =["Bolt", "Pump", "Lever", "Single", "Break"]

                if actions and all(a in manual_actions for a in actions):
                    return True
                return False

            def _get_weapon_firemode(weapon):

                if not weapon:
                    return "Semi"
                actions = weapon.get("action", ["Semi"])
                if not actions:
                    return "Semi"
                return random.choice(actions)

            def _get_shots_for_firemode(firemode, weapon):

                if firemode in["Bolt", "Pump", "Lever", "Single", "Break", "Double"]:
                    return 1
                elif firemode =="Semi":
                    return random.randint(1, 4)
                elif firemode =="Burst":
                    burst_count = weapon.get("burst_count", 3)if weapon else 3
                    return burst_count
                elif firemode =="Auto":
                    return random.randint(3, 10)
                else:
                    return random.randint(1, 3)

            def _get_weapon_caliber_folder(weapon):

                if not weapon:
                    return "556"
                calibers = weapon.get("caliber", [])
                if not calibers:
                    return "556"
                caliber = calibers[0].lower()if calibers else ""

                caliber_map = {
                "5.56x45mm":"556", "5.56":"556", "5.56x45mm nato":"556",
                "7.62x39mm":"762_39", "7.62x39":"762_39",
                "7.62x51mm":"762_51", "7.62x51mm nato":"762_51", ".308":"308", "308 winchester":"308",
                "7.62x54mmr":"762_54", "7.62x54r":"762_54",
                "9x19mm":"9x19", "9mm":"9x19", "9x19mm parabellum":"9x19",
                "9x18mm":"9x18", "9x18mm makarov":"9x18",
                ".45 acp":"45acp", "45 acp":"45acp", ".45acp":"45acp",
                "12 gauge":"12gauge", "12gauge":"12gauge",
                "20 gauge":"20gauge", "20gauge":"20gauge",
                ".223":"223", "223 remington":"223", ".223 remington":"223",
                ".50 bmg":"50ae", "50 bmg":"50ae",
                ".338":"338", "338 lapua":"338", ".338 lapua":"338",
                "5.45x39mm":"545_39", "5.45x39":"545_39",
                ".357 magnum":"357mag", "357 magnum":"357mag",
                ".44 magnum":"44mag", "44 magnum":"44mag",
                ".380 acp":"380acp", "380 acp":"380acp",
                ".38 special":"38special", "38 special":"38special",
                ".30-06":"30_06", "30-06":"30_06",
                ".30-30":"30_30", "30-30":"30_30",
                ".300":"300", "300 win mag":"300",
                ".303":"303", "303 british":"303",
                }

                for key, folder in caliber_map.items():
                    if key in caliber:
                        return folder
                return "556"

            def _is_weapon_suppressed(weapon):

                if not weapon:
                    return False

                if weapon.get("integrally_suppressed", False):
                    return True

                attachments = weapon.get("attachments", [])
                for attachment in attachments:
                    if isinstance(attachment, dict):

                        if attachment.get("suppressor", False):
                            return True

                        current = attachment.get("current")
                        if isinstance(current, dict)and current.get("suppressor", False):
                            return True

                return False

            def _get_magazine_capacity(weapon):

                if not weapon:
                    return 30
                return weapon.get("magazine_capacity", weapon.get("capacity", 30))

            def _get_weapon_platform_folder(weapon):

                if not weapon:
                    return None
                platform = weapon.get("platform", "").lower().replace(" ", "-").replace("_", "-")
                if platform:
                    sound_dir = os.path.join("sounds", "firearms", "weaponsounds", platform)
                    if os.path.isdir(sound_dir):
                        return platform
                return None

            def _play_action_sound(weapon, volume = 0.1, delay = 0):

                def _play():
                    try:
                        platform_folder = _get_weapon_platform_folder(weapon)
                        if platform_folder:
                            sound_dir = os.path.join("sounds", "firearms", "weaponsounds", platform_folder)

                            bolt_back = os.path.join(sound_dir, "boltback.ogg")
                            bolt_forward = os.path.join(sound_dir, "boltforward.ogg")

                            if os.path.isfile(bolt_back):
                                _play_distant_combat_sound(bolt_back, volume = volume)
                            if os.path.isfile(bolt_forward):

                                dg.after(300, lambda:_play_distant_combat_sound(bolt_forward, volume = volume))
                    except Exception as e:
                        logging.debug(f"Failed to play action sound: {e}")

                if delay >0:
                    dg.after(delay, _play)
                else:
                    _play()

            def _get_cyclic_delay(weapon, firemode):

                if not weapon:
                    return 100

                if firemode in["Bolt", "Pump", "Lever", "Single", "Break"]:
                    return 1500

                if firemode =="Burst":
                    raw_burst = weapon.get("burst_cyclic")
                    if raw_burst:
                        try:
                            burst_cyclic = float(raw_burst)
                        except Exception:
                            burst_cyclic = _resolve_effective_cyclic(weapon, combat_state)
                    else:
                        burst_cyclic = _resolve_effective_cyclic(weapon, combat_state)
                    return max(50, int(60000 /burst_cyclic))

                cyclic = _resolve_effective_cyclic(weapon, combat_state)

                return max(50, int(60000 /cyclic))

            def _schedule_combat_sounds(sound_dir, weapon, firemode, shots, volume, start_delay, is_suppressed = False, callback = None):

                cyclic_delay = _get_cyclic_delay(weapon, firemode)
                is_manual = _is_manual_action(weapon)

                try:
                    if os.path.isdir(sound_dir):
                        all_sounds = glob.glob(os.path.join(sound_dir, "*.wav"))+glob.glob(os.path.join(sound_dir, "*.ogg"))
                    else:
                        all_sounds =[]
                except Exception:
                    all_sounds =[]

                if is_suppressed:
                    suppressed_sounds =[s for s in all_sounds if "_suppressed"in s.lower()]
                    resolved_sounds = suppressed_sounds if suppressed_sounds else all_sounds
                    resolved_volume = volume *0.5
                else:
                    resolved_sounds =[s for s in all_sounds if "_suppressed"not in s.lower()]
                    resolved_volume = volume

                def play_shot(shot_num):
                    try:
                        if resolved_sounds:
                            sound_path = random.choice(resolved_sounds)
                            _play_distant_combat_sound(sound_path, volume = resolved_volume)
                    except Exception:
                        pass

                for i in range(shots):
                    shot_delay = start_delay +(i *cyclic_delay)
                    dg.after(shot_delay, lambda num = i:play_shot(num))

                if is_manual and shots >0:
                    action_delay = start_delay +(shots *cyclic_delay)+100
                    _play_action_sound(weapon, volume = volume *0.7, delay = action_delay)

                total_duration = start_delay +(shots *cyclic_delay)
                if is_manual:
                    total_duration +=500

                if callback:
                    dg.after(total_duration +100, callback)

                return total_duration

            def _process_background_combat():

                try:
                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        return

                    floor_idx = self._dg_state.get('current_floor', 0)
                    if floor_idx >=len(dungeon["floors"]):
                        return

                    floor = dungeon["floors"][floor_idx]
                    player_room_id = self._dg_state.get('current_room_id')
                    combat_occurred = False
                    player_room_combat = False

                    player_room = None
                    for room in floor["rooms"]:
                        if room.get("room_id")==player_room_id:
                            player_room = room
                            break

                    if player_room:
                        player_enemies =[e for e in player_room.get("enemies", [])if e.get("alive", True)]
                        player_friendlies =[f for f in player_room.get("friendlies", [])if f.get("alive", True)]

                        if not(player_enemies and player_friendlies):
                            self._dg_state['movement_locked']= False

                    combat_actions =[]
                    current_delay = 0
                    TURN_PAUSE = 800
                    RELOAD_TIME = 1500

                    npc_shots_fired = {}

                    for room in floor["rooms"]:

                        is_player_room = room.get("room_id")==player_room_id

                        enemies =[e for e in room.get("enemies", [])if e.get("alive", True)]
                        friendlies =[f for f in room.get("friendlies", [])if f.get("alive", True)]

                        armed_enemies =[e for e in enemies if _get_npc_weapon_info(e)is not None]
                        armed_friendlies =[f for f in friendlies if _get_npc_weapon_info(f)is not None]

                        if armed_enemies and armed_friendlies:
                            combat_occurred = True
                            if is_player_room:
                                player_room_combat = True

                                self._dg_state['movement_locked']= True

                            combat_volume = 0.35 if is_player_room else 0.12

                            room_name = room.get("name", f"Room {room.get('room_id', '?')}")
                            room_pos = room.get("position", {})
                            room_loc = f"({room_pos.get('x', '?')}, {room_pos.get('y', '?')})"

                            for enemy in armed_enemies:
                                if random.random()<0.6:
                                    alive_friendlies =[f for f in armed_friendlies if f.get("alive", True)]
                                    if not alive_friendlies:
                                        break

                                    target = random.choice(alive_friendlies)
                                    weapon = _get_npc_weapon_info(enemy)
                                    if not weapon:
                                        continue

                                    is_manual = _is_manual_action(weapon)
                                    firemode = _get_weapon_firemode(weapon)
                                    shots = 1 if is_manual else _get_shots_for_firemode(firemode, weapon)
                                    is_suppressed = _is_weapon_suppressed(weapon)

                                    enemy_name = enemy.get("name", "Enemy")
                                    target_name = target.get("name", "Friendly")

                                    caliber_folder = _get_weapon_caliber_folder(weapon)
                                    sound_dir = os.path.join("sounds", "firearms", caliber_folder)

                                    enemy_id = id(enemy)
                                    npc_shots_fired[enemy_id]= npc_shots_fired.get(enemy_id, 0)+shots
                                    mag_capacity = _get_magazine_capacity(weapon)

                                    needs_reload = npc_shots_fired[enemy_id]>=mag_capacity

                                    hits = 0
                                    total_damage = 0

                                    for shot_num in range(shots):
                                        if not target.get("alive", True):
                                            alive_friendlies =[f for f in armed_friendlies if f.get("alive", True)]
                                            if alive_friendlies:
                                                target = random.choice(alive_friendlies)
                                                target_name = target.get("name", "Friendly")
                                            else:
                                                break

                                        if random.random()<0.4:
                                            damage = random.randint(8, 25)
                                            target["health"]= target.get("health", 100)-damage
                                            hits +=1
                                            total_damage +=damage

                                            if target["health"]<=0:
                                                target["alive"]= False

                                    cyclic_delay = _get_cyclic_delay(weapon, firemode)
                                    shot_duration = shots *cyclic_delay

                                    _schedule_combat_sounds(sound_dir, weapon, firemode, shots, combat_volume, current_delay, is_suppressed)

                                    if not is_suppressed:
                                        rx, ry = room_pos.get('x', 0), room_pos.get('y', 0)
                                        _schedule_muzzle_flashes(rx, ry, shots, cyclic_delay, current_delay)

                                    log_delay = current_delay
                                    suppressed_tag = "[suppressed]"if is_suppressed else ""
                                    if hits >0:
                                        if not target.get("alive", True):
                                            dg.after(log_delay, lambda rl = room_loc, en = enemy_name, s = shots, fm = firemode, tn = target_name, st = suppressed_tag:
                                            _add_combat_log(f"{rl} {en} fired {s}x({fm}){st}, killed {tn}!"))
                                        else:
                                            dg.after(log_delay, lambda rl = room_loc, en = enemy_name, s = shots, fm = firemode, h = hits, td = total_damage, st = suppressed_tag:
                                            _add_combat_log(f"{rl} {en} fired {s}x({fm}){st}, hit {h}x for {td} dmg"))
                                    else:
                                        dg.after(log_delay, lambda rl = room_loc, en = enemy_name, s = shots, fm = firemode, st = suppressed_tag:
                                        _add_combat_log(f"{rl} {en} fired {s}x({fm}){st}, missed"))

                                    current_delay +=shot_duration +(300 if is_manual else 100)

                                    if needs_reload:
                                        dg.after(current_delay, lambda en = enemy_name, rl = room_loc:
                                        _add_combat_log(f"{rl} {en} reloading..."))
                                        current_delay +=RELOAD_TIME
                                        npc_shots_fired[enemy_id]= 0

                            current_delay +=TURN_PAUSE

                            for friendly in armed_friendlies:
                                if not friendly.get("alive", True):
                                    continue
                                if random.random()<0.6:
                                    alive_enemies =[e for e in armed_enemies if e.get("alive", True)]
                                    if not alive_enemies:
                                        break

                                    target = random.choice(alive_enemies)
                                    weapon = _get_npc_weapon_info(friendly)
                                    if not weapon:
                                        continue

                                    is_manual = _is_manual_action(weapon)
                                    firemode = _get_weapon_firemode(weapon)
                                    shots = 1 if is_manual else _get_shots_for_firemode(firemode, weapon)
                                    is_suppressed = _is_weapon_suppressed(weapon)

                                    friendly_name = friendly.get("name", "Friendly")
                                    target_name = target.get("name", "Enemy")

                                    caliber_folder = _get_weapon_caliber_folder(weapon)
                                    sound_dir = os.path.join("sounds", "firearms", caliber_folder)

                                    friendly_id = id(friendly)
                                    npc_shots_fired[friendly_id]= npc_shots_fired.get(friendly_id, 0)+shots
                                    mag_capacity = _get_magazine_capacity(weapon)

                                    needs_reload = npc_shots_fired[friendly_id]>=mag_capacity

                                    hits = 0
                                    total_damage = 0

                                    for shot_num in range(shots):
                                        if not target.get("alive", True):
                                            alive_enemies =[e for e in armed_enemies if e.get("alive", True)]
                                            if alive_enemies:
                                                target = random.choice(alive_enemies)
                                                target_name = target.get("name", "Enemy")
                                            else:
                                                break

                                        if random.random()<0.45:
                                            damage = random.randint(10, 30)
                                            target["health"]= target.get("health", 100)-damage
                                            hits +=1
                                            total_damage +=damage

                                            if target["health"]<=0:
                                                target["alive"]= False
                                                if "pending_loot"not in room:
                                                    room["pending_loot"]=[]
                                                room["pending_loot"].append(target.copy())

                                    cyclic_delay = _get_cyclic_delay(weapon, firemode)
                                    shot_duration = shots *cyclic_delay

                                    _schedule_combat_sounds(sound_dir, weapon, firemode, shots, combat_volume, current_delay, is_suppressed)

                                    if not is_suppressed:
                                        rx, ry = room_pos.get('x', 0), room_pos.get('y', 0)
                                        _schedule_muzzle_flashes(rx, ry, shots, cyclic_delay, current_delay)

                                    log_delay = current_delay
                                    suppressed_tag = "[suppressed]"if is_suppressed else ""
                                    if hits >0:
                                        if not target.get("alive", True):
                                            dg.after(log_delay, lambda rl = room_loc, fn = friendly_name, s = shots, fm = firemode, tn = target_name, st = suppressed_tag:
                                            _add_combat_log(f"{rl} {fn} fired {s}x({fm}){st}, killed {tn}!"))
                                        else:
                                            dg.after(log_delay, lambda rl = room_loc, fn = friendly_name, s = shots, fm = firemode, h = hits, td = total_damage, st = suppressed_tag:
                                            _add_combat_log(f"{rl} {fn} fired {s}x({fm}){st}, hit {h}x for {td} dmg"))
                                    else:
                                        dg.after(log_delay, lambda rl = room_loc, fn = friendly_name, s = shots, fm = firemode, st = suppressed_tag:
                                        _add_combat_log(f"{rl} {fn} fired {s}x({fm}){st}, missed"))

                                    current_delay +=shot_duration +(300 if is_manual else 100)

                                    if needs_reload:
                                        dg.after(current_delay, lambda fn = friendly_name, rl = room_loc:
                                        _add_combat_log(f"{rl} {fn} reloading..."))
                                        current_delay +=RELOAD_TIME
                                        npc_shots_fired[friendly_id]= 0

                            current_delay +=TURN_PAUSE

                    if combat_occurred:

                        dg.after(current_delay +500, _draw_grid)

                        if player_room_combat:
                            dg.after(current_delay +500, lambda:self._dg_state.update({'movement_locked':False}))

                except Exception as e:
                    logging.debug(f"Background combat error: {e}")
                finally:

                    try:
                        if dg.winfo_exists():

                            next_delay = max(3000, current_delay +2000)if combat_occurred else random.randint(3000, 5000)
                            background_combat_timer[0]= dg.after(next_delay, _process_background_combat)# type: ignore
                    except Exception:
                        pass

            def _calculate_distance(pos1, pos2):

                return abs(pos1.get("x", 0)-pos2.get("x", 0))+abs(pos1.get("y", 0)-pos2.get("y", 0))

            def _get_adjacent_rooms(room, floor):

                adjacent =[]
                room_id = room.get("room_id")
                for conn in floor.get("connections", []):
                    if conn.get("from_room")==room_id:
                        adjacent.append(conn.get("to_room"))
                    elif conn.get("to_room")==room_id:
                        adjacent.append(conn.get("from_room"))
                return adjacent

            def _find_path_bfs(start_room_id, target_room_id, floor):

                if start_room_id ==target_room_id:
                    return[start_room_id]

                from collections import deque

                adj_map = {}
                for room in floor.get("rooms", []):
                    rid = room.get("room_id")
                    adj_map[rid]= _get_adjacent_rooms(room, floor)

                queue = deque([(start_room_id, [start_room_id])])
                visited = {start_room_id}

                while queue:
                    current_id, path = queue.popleft()

                    for neighbor_id in adj_map.get(current_id, []):
                        if neighbor_id ==target_room_id:
                            return path +[neighbor_id]

                        if neighbor_id not in visited:
                            visited.add(neighbor_id)
                            queue.append((neighbor_id, path +[neighbor_id]))

                return None

            def _get_path_distance(start_room_id, target_room_id, floor):

                path = _find_path_bfs(start_room_id, target_room_id, floor)
                if path:
                    return len(path)-1
                return float('inf')

            def _get_next_room_on_path(start_room_id, target_room_id, floor):

                path = _find_path_bfs(start_room_id, target_room_id, floor)
                if path and len(path)>1:

                    next_room_id = path[1]
                    for room in floor.get("rooms", []):
                        if room.get("room_id")==next_room_id:
                            return room
                return None

            npc_movement_timer =[None]

            def _find_combat_rooms(floor):

                combat_rooms =[]
                for room in floor.get("rooms", []):
                    enemies =[e for e in room.get("enemies", [])if e.get("alive", True)]
                    friendlies =[f for f in room.get("friendlies", [])if f.get("alive", True)]
                    if enemies and friendlies:
                        combat_rooms.append(room)
                return combat_rooms

            def _move_npc_towards(npc, npc_list, room, target_room_id, floor, npc_type = "enemies"):

                room_id = room.get("room_id")

                if room_id ==target_room_id:
                    return None

                next_room = _get_next_room_on_path(room_id, target_room_id, floor)

                if next_room:
                    npc_list.remove(npc)
                    next_room.setdefault(npc_type, []).append(npc)
                    return next_room
                return None

            def _move_npcs_support():

                try:
                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        return

                    floor_idx = self._dg_state.get('current_floor', 0)
                    if floor_idx >=len(dungeon["floors"]):
                        return

                    floor = dungeon["floors"][floor_idx]
                    player_room_id = self._dg_state.get('current_room_id')

                    player_room = None
                    for r in floor["rooms"]:
                        if r.get("room_id")==player_room_id:
                            player_room = r
                            break

                    combat_rooms = _find_combat_rooms(floor)

                    npcs_moved = False
                    backup_arrived =[]
                    enemies_arrived =[]

                    for room in floor["rooms"]:
                        room_pos = room.get("position", {})
                        room_id = room.get("room_id")

                        if room in combat_rooms:
                            continue

                        adjacent_room_ids = _get_adjacent_rooms(room, floor)
                        if not adjacent_room_ids:
                            continue

                        for enemy in list(room.get("enemies", [])):
                            if not enemy.get("alive", True):
                                continue

                            enemy_name = enemy.get("name", "Unknown")
                            enemy_health = enemy.get("health", 100)

                            nearest_combat = None
                            nearest_dist = float('inf')
                            for combat_room in combat_rooms:
                                combat_room_id = combat_room.get("room_id")
                                dist = _get_path_distance(room_id, combat_room_id, floor)
                                if dist <=10 and dist <nearest_dist:
                                    nearest_dist = dist
                                    nearest_combat = combat_room

                            if nearest_combat:
                                combat_room_id = nearest_combat.get("room_id")
                                dest_room = _move_npc_towards(enemy, room["enemies"], room, combat_room_id, floor, "enemies")
                                if dest_room:
                                    npcs_moved = True

                                    if dest_room.get("room_id")==player_room_id:
                                        enemies_arrived.append({
                                        "name":enemy_name,
                                        "health":enemy_health,
                                        "reason":"combat support"
                                        })

                            elif room_id !=player_room_id and player_room:
                                dist_to_player = _get_path_distance(room_id, player_room_id, floor)
                                if dist_to_player <=10 and random.random()<0.4:
                                    dest_room = _move_npc_towards(enemy, room["enemies"], room, player_room_id, floor, "enemies")
                                    if dest_room:
                                        npcs_moved = True

                                        if dest_room.get("room_id")==player_room_id:
                                            enemies_arrived.append({
                                            "name":enemy_name,
                                            "health":enemy_health,
                                            "reason":"hunting"
                                            })

                        for friendly in list(room.get("friendlies", [])):
                            if not friendly.get("alive", True):
                                continue

                            friendly_name = friendly.get("name", "Unknown")
                            friendly_health = friendly.get("health", 100)

                            nearest_combat = None
                            nearest_dist = float('inf')
                            for combat_room in combat_rooms:
                                combat_room_id = combat_room.get("room_id")
                                dist = _get_path_distance(room_id, combat_room_id, floor)
                                if dist <=10 and dist <nearest_dist:
                                    nearest_dist = dist
                                    nearest_combat = combat_room

                            if nearest_combat:
                                combat_room_id = nearest_combat.get("room_id")
                                dest_room = _move_npc_towards(friendly, room["friendlies"], room, combat_room_id, floor, "friendlies")
                                if dest_room:
                                    npcs_moved = True

                                    if dest_room.get("room_id")==player_room_id:
                                        backup_arrived.append({
                                        "name":friendly_name,
                                        "health":friendly_health,
                                        "reason":"combat support"
                                        })

                            elif room_id !=player_room_id and player_room:
                                dist_to_player = _get_path_distance(room_id, player_room_id, floor)
                                if dist_to_player <=10 and random.random()<0.5:
                                    dest_room = _move_npc_towards(friendly, room["friendlies"], room, player_room_id, floor, "friendlies")
                                    if dest_room:
                                        npcs_moved = True

                                        if dest_room.get("room_id")==player_room_id:
                                            backup_arrived.append({
                                            "name":friendly_name,
                                            "health":friendly_health,
                                            "reason":"patrol"
                                            })

                    if backup_arrived:
                        names =[f"{b['name']}({b['health']}HP)"for b in backup_arrived]
                        title = "🛡️ Backup Arrived!"
                        if len(backup_arrived)==1:
                            b = backup_arrived[0]
                            message = f"{b['name']} has arrived at your position!\nHealth: {b['health']}HP\nReason: {b['reason'].title()}"
                        else:
                            message = f"{len(backup_arrived)} friendlies have arrived!\n"+"\n".join(names)

                        try:
                            send_windows_notification(title, message)
                        except Exception:
                            pass

                        _add_combat_log(f"⚔ BACKUP: {', '.join(names)} arrived!")

                    if enemies_arrived:
                        names =[f"{e['name']}({e['health']}HP)"for e in enemies_arrived]
                        title = "⚠️ Enemy Reinforcements!"
                        if len(enemies_arrived)==1:
                            e = enemies_arrived[0]
                            message = f"{e['name']} has found your position!\nHealth: {e['health']}HP\nReason: {e['reason'].title()}"
                        else:
                            message = f"{len(enemies_arrived)} enemies have arrived!\n"+"\n".join(names)

                        try:
                            send_windows_notification(title, message)
                        except Exception:
                            pass

                        _add_combat_log(f"⚠ ENEMIES: {', '.join(names)} arrived!")

                    if npcs_moved:
                        _draw_grid()

                except Exception as e:
                    logging.debug(f"NPC support movement error: {e}")
                finally:

                    try:
                        if dg.winfo_exists():
                            npc_movement_timer[0]= dg.after(10000, _move_npcs_support)# type: ignore
                    except Exception:
                        pass

            def _move_npcs_once():

                try:
                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        return

                    floor_idx = self._dg_state.get('current_floor', 0)
                    if floor_idx >=len(dungeon["floors"]):
                        return

                    floor = dungeon["floors"][floor_idx]
                    player_room_id = self._dg_state.get('current_room_id')
                    player_room = None

                    for room in floor["rooms"]:
                        if room.get("room_id")==player_room_id:
                            player_room = room
                            break

                    for room in floor["rooms"]:
                        room_id = room.get("room_id")
                        distance_to_player = _get_path_distance(room_id, player_room_id, floor)if player_room else float('inf')

                        has_enemies = any(e.get("alive", True)for e in room.get("enemies", []))

                        adjacent_room_ids = _get_adjacent_rooms(room, floor)
                        if not adjacent_room_ids:
                            continue

                        for enemy in list(room.get("enemies", [])):
                            if not enemy.get("alive", True):
                                continue

                            if random.random()>0.6:
                                continue

                            if distance_to_player <=5:

                                next_room = _get_next_room_on_path(room_id, player_room_id, floor)
                                if next_room:
                                    room["enemies"].remove(enemy)
                                    next_room.setdefault("enemies", []).append(enemy)
                            else:

                                target_room_id = random.choice(adjacent_room_ids)
                                for r in floor["rooms"]:
                                    if r.get("room_id")==target_room_id:
                                        room["enemies"].remove(enemy)
                                        r.setdefault("enemies", []).append(enemy)
                                        break

                        if not has_enemies:
                            for friendly in list(room.get("friendlies", [])):
                                if not friendly.get("alive", True):
                                    continue

                                if random.random()>0.4:
                                    continue

                                nearest_enemy_room = None
                                nearest_enemy_dist = float('inf')
                                for other_room in floor["rooms"]:
                                    other_room_id = other_room.get("room_id")
                                    dist_to_room = _get_path_distance(room_id, other_room_id, floor)
                                    if dist_to_room <=5:
                                        alive_enemies =[e for e in other_room.get("enemies", [])if e.get("alive", True)]
                                        if alive_enemies and dist_to_room <nearest_enemy_dist:
                                            nearest_enemy_dist = dist_to_room
                                            nearest_enemy_room = other_room

                                if nearest_enemy_room and nearest_enemy_dist >0:

                                    enemy_room_id = nearest_enemy_room.get("room_id")
                                    next_room = _get_next_room_on_path(room_id, enemy_room_id, floor)
                                    if next_room:
                                        room["friendlies"].remove(friendly)
                                        next_room.setdefault("friendlies", []).append(friendly)
                                elif player_room and distance_to_player >0:

                                    next_room = _get_next_room_on_path(room_id, player_room_id, floor)
                                    if next_room:
                                        room["friendlies"].remove(friendly)
                                        next_room.setdefault("friendlies", []).append(friendly)

                except Exception as e:
                    logging.debug(f"NPC movement error: {e}")

            def _kill_enemies_in_room():

                try:
                    room = _get_current_room()
                    if not room:
                        return

                    enemies = room.get("enemies", [])
                    killed_count = 0

                    for enemy in enemies:
                        if enemy.get("alive", True):
                            enemy["alive"]= False
                            killed_count +=1

                            if "pending_loot"not in room:
                                room["pending_loot"]=[]
                            room["pending_loot"].append(enemy.copy())

                    room["enemies_cleared"]= True

                    self._dg_state['movement_locked']= False

                    if killed_count >0:
                        self._popup_show_info("Combat", f"Defeated {killed_count} enemy(s)! Loot is now available.")

                    _update_display()
                    _draw_grid()

                except Exception as e:
                    logging.exception("Failed to kill enemies")

            def _collect_loot_from_room():

                try:
                    room = _get_current_room()
                    if not room:
                        return

                    pending_loot = room.get("pending_loot", [])
                    if not pending_loot:
                        self._popup_show_info("Loot", "No loot to collect.")
                        return

                    table_data = None
                    try:
                        tbl_path = get_current_table_path()
                        if tbl_path and os.path.exists(tbl_path):
                            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                                full_table = json.load(f)

                                table_data = {
                                "rarity_weights":full_table.get("rarity_weights", {}),
                                "tables":full_table.get("tables", {})
                                }
                    except Exception as e:
                        logging.error(f"Failed to load table data: {e}")

                    files_generated =[]

                    for enemy in pending_loot:
                        enemy_name = enemy.get("name", "Unknown Enemy")

                        if table_data:

                            loot_items = self._generate_enemy_loot(enemy, table_data)
                            if loot_items:

                                self._save_enemy_loot_transfer_silent(enemy_name, loot_items)
                                files_generated.append(f"enemyloot_{enemy_name.replace(' ', '_').lower()}")
                        else:

                            self._save_enemy_loot_transfer_silent(enemy_name, enemy.get("items", []))
                            files_generated.append(f"enemyloot_{enemy_name.replace(' ', '_').lower()}")

                    loot_spawn = room.get("loot_spawn", [])
                    if loot_spawn and table_data:
                        lootcrates_table = table_data.get("lootcrates", [])
                        for spawn in loot_spawn:
                            spawn_type = spawn.get("type", "lootcrate")
                            spawn_id = spawn.get("id", 0)
                            to_spawn = spawn.get("to_spawn", {"min":1, "max":1})
                            spawn_count = random.randint(to_spawn.get("min", 1), to_spawn.get("max", 1))

                            for _ in range(spawn_count):

                                lootcrate_def = None
                                for lc in lootcrates_table:
                                    if lc.get("id_lct")==spawn_id:
                                        lootcrate_def = lc
                                        break

                                if lootcrate_def:

                                    crate_items = self._generate_lootcrate_contents(lootcrate_def, table_data)
                                    if crate_items:
                                        crate_name = lootcrate_def.get("name", "Lootcrate")
                                        self._save_lootcrate_transfer_silent(crate_name, crate_items)
                                        files_generated.append(f"lootcrate_{crate_name.replace(' ', '_').lower()}")

                        room["loot_spawn"]=[]

                    room["pending_loot"]=[]

                    if files_generated:
                        self._popup_show_info("Loot Generated", f"Generated {len(files_generated)} loot file(s):\n"+"\n".join(files_generated[:10])+("\n..."if len(files_generated)>10 else ""))
                    else:
                        self._popup_show_info("Loot", "No loot items were generated.")

                    _update_display()
                    _draw_grid()

                except Exception as e:
                    logging.exception("Failed to collect loot")
                    logging.exception("Failed to collect loot")

            def _generate_dungeon():

                try:
                    rooms_table = _load_rooms_table()
                    enemies_table = _load_enemies_table()
                    if not rooms_table:
                        self._popup_show_info("Error", "No rooms table found.", sound = "error")
                        return

                    floors_config = self._dg_state.get('floors', [])
                    num_floors = len(floors_config)
                    if num_floors ==0:
                        self._popup_show_info("Error", "No floors configured.", sound = "error")
                        return

                    diff_map = {0:"None/Friendly", 1:"Easy", 2:"Medium", 3:"Hard", 4:"Miniboss"}
                    diff_order =["None/Friendly", "Friendly", "Easy", "Medium", "Hard", "Miniboss"]
                    opposite_dir = {"top":"bottom", "bottom":"top", "left":"right", "right":"left"}
                    dir_offset = {"top":(0, -1), "bottom":(0, 1), "left":(-1, 0), "right":(1, 0)}

                    dungeon = {"floors":[], "metadata":{"generated_at":datetime.now().isoformat()}}

                    for floor_idx, floor_cfg in enumerate(floors_config):

                        try:
                            enemy_count = floor_cfg.get('enemy_count')
                            enemy_count = enemy_count.get()if hasattr(enemy_count, 'get')else(enemy_count or 10)
                            max_diff_idx = floor_cfg.get('difficulty')
                            max_diff_idx = max_diff_idx.get()if hasattr(max_diff_idx, 'get')else(max_diff_idx or 4)
                            x_size = floor_cfg.get('x_size')
                            x_size = x_size.get()if hasattr(x_size, 'get')else(x_size or 20)
                            y_size = floor_cfg.get('y_size')
                            y_size = y_size.get()if hasattr(y_size, 'get')else(y_size or 20)
                            transport_type = floor_cfg.get('transport')
                            transport_type = transport_type.get()if hasattr(transport_type, 'get')else transport_type
                        except Exception:
                            enemy_count, max_diff_idx, x_size, y_size, transport_type = 10, 4, 20, 20, None

                        max_diff = diff_map.get(max_diff_idx, "Miniboss")

                        entrance_rooms =[r for r in rooms_table if r.get("type")=="entrance"]
                        hallway_rooms =[r for r in rooms_table if r.get("type")=="hallway"]
                        regular_rooms =[r for r in rooms_table if r.get("type")=="room"]
                        transport_rooms =[r for r in rooms_table if r.get("type")=="transport"and r.get("subtype", "").lower()==(transport_type or "stairs").lower()]

                        if not transport_rooms:
                            transport_rooms =[r for r in rooms_table if r.get("type")=="transport"]
                            logging.warning(f"No transport rooms found for subtype '{transport_type or 'stairs'}', using all transports: {len(transport_rooms)} found")

                        logging.info(f"Loaded rooms: {len(entrance_rooms)} entrances, {len(hallway_rooms)} hallways, {len(regular_rooms)} rooms, {len(transport_rooms)} transports(subtype: {transport_type or 'stairs'})")

                        max_diff_order = diff_order.index(max_diff)if max_diff in diff_order else len(diff_order)
                        eligible_enemies =[e for e in enemies_table if diff_order.index(e.get("difficulty", "Medium"))<=max_diff_order if e.get("difficulty", "Medium")in diff_order]

                        floor_data = {
                        "floor_number":floor_idx +1,
                        "x_size":x_size,
                        "y_size":y_size,
                        "rooms":[],
                        "connections":[],
                        "enemies_remaining":enemy_count,
                        "transport_type":transport_type or "stairs"
                        }

                        grid =[[None for _ in range(x_size)]for _ in range(y_size)]

                        open_attachments =[]
                        room_id = 0
                        enemies_to_place = enemy_count

                        def _get_room_attachments(room):

                            return[ap.get("attachment_point")for ap in room.get("attachment_points", [])]

                        def _rotate_direction(direction, times = 1):

                            rotation_order =["top", "right", "bottom", "left"]
                            if direction not in rotation_order:
                                return direction
                            idx = rotation_order.index(direction)
                            return rotation_order[(idx +times)%4]

                        def _rotate_room_template(template, times = 1):

                            import copy
                            if times ==0:
                                return template.copy()
                            rotated = copy.deepcopy(template)

                            if "attachment_points"in rotated:
                                for ap in rotated["attachment_points"]:
                                    if "attachment_point"in ap:
                                        ap["attachment_point"]= _rotate_direction(ap["attachment_point"], times)

                            if "doors"in rotated:
                                for door in rotated["doors"]:
                                    if "position"in door:
                                        door["position"]= _rotate_direction(door["position"], times)
                            return rotated

                        def _check_room_fits(template, x, y, needed_attachment):

                            attachments = _get_room_attachments(template)
                            for att in attachments:
                                if att ==needed_attachment:
                                    continue
                                dx, dy = dir_offset[att]
                                nx, ny = x +dx, y +dy

                                if nx <0 or nx >=x_size or ny <0 or ny >=y_size:
                                    return False
                            return True

                        def _has_unconnected_adjacency(template, x, y, needed_attachment):

                            attachments = _get_room_attachments(template)

                            for direction in["top", "bottom", "left", "right"]:
                                dx, dy = dir_offset[direction]
                                nx, ny = x +dx, y +dy
                                if 0 <=nx <x_size and 0 <=ny <y_size:
                                    if grid[ny][nx]is not None:

                                        if direction not in attachments and direction !=opposite_dir.get(needed_attachment):
                                            return True
                            return False

                        def _find_fitting_room(needed_attachment, room_pool, target_x, target_y, allow_rotation = True):

                            candidates =[r for r in room_pool if needed_attachment in _get_room_attachments(r)]

                            if not candidates:

                                if allow_rotation:
                                    for original in room_pool:
                                        for rot in range(1, 4):
                                            rotated = _rotate_room_template(original, rot)
                                            if needed_attachment in _get_room_attachments(rotated):
                                                if _check_room_fits(rotated, target_x, target_y, needed_attachment):

                                                    if not _has_unconnected_adjacency(rotated, target_x, target_y, needed_attachment):
                                                        return rotated

                                    for original in room_pool:
                                        for rot in range(1, 4):
                                            rotated = _rotate_room_template(original, rot)
                                            if needed_attachment in _get_room_attachments(rotated):
                                                if _check_room_fits(rotated, target_x, target_y, needed_attachment):
                                                    return rotated
                                return None

                            random.shuffle(candidates)
                            good_candidates =[]
                            fallback_candidates =[]
                            for candidate in candidates:
                                if _check_room_fits(candidate, target_x, target_y, needed_attachment):
                                    if not _has_unconnected_adjacency(candidate, target_x, target_y, needed_attachment):
                                        good_candidates.append(candidate)
                                    else:
                                        fallback_candidates.append(candidate)

                            if good_candidates:
                                return random.choice(good_candidates)
                            if fallback_candidates:
                                return random.choice(fallback_candidates)

                            if allow_rotation:
                                for original in room_pool:
                                    original_atts = _get_room_attachments(original)

                                    for rot in range(1, 4):
                                        rotated = _rotate_room_template(original, rot)
                                        rotated_atts = _get_room_attachments(rotated)
                                        if needed_attachment in rotated_atts:
                                            if _check_room_fits(rotated, target_x, target_y, needed_attachment):
                                                if not _has_unconnected_adjacency(rotated, target_x, target_y, needed_attachment):
                                                    return rotated

                                for original in room_pool:
                                    for rot in range(1, 4):
                                        rotated = _rotate_room_template(original, rot)
                                        if needed_attachment in _get_room_attachments(rotated):
                                            if _check_room_fits(rotated, target_x, target_y, needed_attachment):
                                                return rotated

                            for candidate in candidates:
                                return candidate

                            return None

                        def _find_fitting_room_weighted(needed_attachment, room_pool, target_x, target_y, prefer_complex = True, allow_rotation = True):

                            candidates =[r for r in room_pool if needed_attachment in _get_room_attachments(r)]

                            rotated_candidates =[]
                            if allow_rotation:
                                for original in room_pool:
                                    for rot in range(1, 4):
                                        rotated = _rotate_room_template(original, rot)
                                        if needed_attachment in _get_room_attachments(rotated):
                                            if _check_room_fits(rotated, target_x, target_y, needed_attachment):
                                                rotated_candidates.append(rotated)

                            fitting_direct =[c for c in candidates if _check_room_fits(c, target_x, target_y, needed_attachment)]
                            all_fitting = fitting_direct +rotated_candidates

                            if not all_fitting:

                                return _find_fitting_room(needed_attachment, room_pool, target_x, target_y, allow_rotation)

                            good_rooms =[r for r in all_fitting if not _has_unconnected_adjacency(r, target_x, target_y, needed_attachment)]
                            fallback_rooms =[r for r in all_fitting if _has_unconnected_adjacency(r, target_x, target_y, needed_attachment)]

                            rooms_to_use = good_rooms if good_rooms else fallback_rooms

                            if not prefer_complex:
                                return random.choice(rooms_to_use)if rooms_to_use else random.choice(all_fitting)

                            weighted =[]
                            for r in rooms_to_use:
                                att_count = len(_get_room_attachments(r))

                                weight = att_count *att_count
                                if att_count >=3:
                                    weight *=2
                                weighted.extend([r]*weight)

                            return random.choice(weighted)if weighted else random.choice(all_fitting)

                        def _prepare_room(template, rid, x, y):

                            import copy
                            room = copy.deepcopy(template)
                            room["room_id"]= rid
                            room["position"]= {"x":x, "y":y}
                            room["doors_state"]= {}
                            for door in room.get("doors", []):
                                is_locked = door.get("locked", "random")
                                if is_locked =="random":
                                    is_locked = random.choice([True, False])
                                room["doors_state"][door.get("position", "unknown")]= {"locked":is_locked, "picked":False}
                            room["enemies"]=[]
                            room["friendlies"]=[]
                            room["visited"]= False
                            room["enemies_cleared"]= False
                            return room

                        def _spawn_enemies(room):

                            nonlocal enemies_to_place
                            if room.get("enemy_spawn_possible", False)and eligible_enemies:

                                hostile_npcs =[e for e in eligible_enemies if e.get("difficulty")not in("Friendly", "None/Friendly")]
                                friendly_npcs =[e for e in eligible_enemies if e.get("difficulty")in("Friendly", "None/Friendly")]

                                if enemies_to_place >0 and hostile_npcs and random.random()<0.4:

                                    spawn_count = random.randint(1, min(2, enemies_to_place))
                                    for _ in range(spawn_count):
                                        enemy = random.choice(hostile_npcs).copy()
                                        enemy["alive"]= True
                                        room["enemies"].append(enemy)
                                        enemies_to_place -=1

                                if friendly_npcs:
                                    if random.random()<0.15:
                                        if random.random()<0.5:

                                            friendly_count = random.randint(1, 2)
                                            for _ in range(friendly_count):
                                                friendly = random.choice(friendly_npcs).copy()
                                                friendly["alive"]= True
                                                friendly["health"]= 100
                                                room["friendlies"].append(friendly)

                        def _place_room(room, x, y):

                            grid[y][x]= room["room_id"]
                            floor_data["rooms"].append(room)

                            for direction in _get_room_attachments(room):
                                dx, dy = dir_offset[direction]
                                nx, ny = x +dx, y +dy
                                if 0 <=nx <x_size and 0 <=ny <y_size:
                                    if grid[ny][nx]is None:
                                        open_attachments.append((room["room_id"], direction, nx, ny))

                        def _find_room_with_attachment(needed_direction, room_pool):

                            candidates =[r for r in room_pool if needed_direction in _get_room_attachments(r)]
                            return random.choice(candidates)if candidates else None

                        def _connect_rooms(from_room_id, to_room_id, direction):

                            conn = {"from_room":from_room_id, "to_room":to_room_id, "direction":direction}
                            rev_conn = {"from_room":to_room_id, "to_room":from_room_id, "direction":opposite_dir[direction]}
                            if conn not in floor_data["connections"]and rev_conn not in floor_data["connections"]:
                                floor_data["connections"].append(conn)

                                from_room = None
                                to_room = None
                                for room in floor_data["rooms"]:
                                    if room.get("room_id")==from_room_id:
                                        from_room = room
                                    if room.get("room_id")==to_room_id:
                                        to_room = room

                                if from_room and to_room:
                                    opp_direction = opposite_dir[direction]
                                    from_door = from_room.get("doors_state", {}).get(direction, {})
                                    to_door = to_room.get("doors_state", {}).get(opp_direction, {})

                                    is_locked = from_door.get("locked", False)and to_door.get("locked", False)
                                    is_picked = from_door.get("picked", False)or to_door.get("picked", False)

                                    if direction in from_room.get("doors_state", {}):
                                        from_room["doors_state"][direction]= {"locked":is_locked, "picked":is_picked}
                                    if opp_direction in to_room.get("doors_state", {}):
                                        to_room["doors_state"][opp_direction]= {"locked":is_locked, "picked":is_picked}

                        transport_mode_var = self._dg_state.get('transport_mode')
                        transport_mode = transport_mode_var.get()if hasattr(transport_mode_var, 'get')else 'Multiple'
                        is_multi_entrance = transport_mode =='Multiple'

                        is_top_floor = floor_idx ==0
                        is_bottom_floor = floor_idx ==num_floors -1
                        is_middle_floor = not is_top_floor and not is_bottom_floor

                        start_x = random.randint(1, x_size -2)
                        start_y = random.randint(1, y_size -2)

                        if is_top_floor and entrance_rooms:

                            entrance_template = random.choice(entrance_rooms)
                            rotation = random.randint(0, 3)
                            rotated_entrance = _rotate_room_template(entrance_template, rotation)
                            entrance = _prepare_room(rotated_entrance, room_id, start_x, start_y)
                            _place_room(entrance, start_x, start_y)
                            room_id +=1
                        elif transport_rooms:

                            entry_transport_template = random.choice(transport_rooms)
                            rotation = random.randint(0, 3)
                            rotated_transport = _rotate_room_template(entry_transport_template, rotation)
                            entry_transport = _prepare_room(rotated_transport, room_id, start_x, start_y)
                            entry_transport["leads_to_floor"]= floor_idx
                            entry_transport["is_entry_transport"]= True
                            _place_room(entry_transport, start_x, start_y)
                            room_id +=1

                            if is_middle_floor and not is_multi_entrance:
                                entry_transport["leads_to_floor"]= floor_idx
                                entry_transport["also_leads_to_floor"]= floor_idx +2
                        else:

                            if hallway_rooms:
                                entry_hallway = _find_fitting_room("bottom", hallway_rooms, start_x, start_y)
                                if entry_hallway:
                                    hallway = _prepare_room(entry_hallway, room_id, start_x, start_y)
                                    _spawn_enemies(hallway)
                                    _place_room(hallway, start_x, start_y)
                                    room_id +=1

                        target_rooms = max(15, (x_size *y_size)//6)

                        need_transport_down = False
                        if is_top_floor and not is_bottom_floor:
                            need_transport_down = True
                        elif is_middle_floor and is_multi_entrance:
                            need_transport_down = True

                        logging.info(f"Floor {floor_idx +1}: is_top={is_top_floor}, is_bottom={is_bottom_floor}, is_middle={is_middle_floor}, need_transport_down={need_transport_down}, transport_rooms={len(transport_rooms)}")

                        need_transport = need_transport_down
                        max_iterations = target_rooms *20
                        iterations = 0

                        def _score_room_complexity(room_template):

                            attachments = _get_room_attachments(room_template)
                            return len(attachments)

                        def _weighted_room_select(room_list, prefer_complex = True):

                            if not room_list:
                                return None
                            if not prefer_complex:
                                return random.choice(room_list)

                            weighted =[]
                            for r in room_list:
                                score = _score_room_complexity(r)

                                weight = score *score
                                weighted.extend([r]*weight)
                            return random.choice(weighted)if weighted else random.choice(room_list)

                        def _calculate_sprawl_score(x, y, placed_rooms):

                            if not placed_rooms:
                                return 1

                            avg_x = sum(r["position"]["x"]for r in placed_rooms)/len(placed_rooms)
                            avg_y = sum(r["position"]["y"]for r in placed_rooms)/len(placed_rooms)
                            dist_from_center = abs(x -avg_x)+abs(y -avg_y)

                            edge_bonus = min(x, y, x_size -1 -x, y_size -1 -y)
                            edge_score = max(0, 3 -edge_bonus)
                            return dist_from_center +edge_score

                        def _select_sprawling_attachment(attachments, placed_rooms):

                            if not attachments:
                                return None

                            scored =[]
                            for att in attachments:
                                _, _, x, y = att
                                score = _calculate_sprawl_score(x, y, placed_rooms)
                                scored.append((att, score))

                            scored.sort(key = lambda x:x[1], reverse = True)

                            top_half = scored[:max(1, len(scored)//2)]
                            weights =[i +1 for i in range(len(top_half), 0, -1)]
                            weighted_list =[]
                            for(att, _), w in zip(top_half, weights):
                                weighted_list.extend([att]*w)
                            return random.choice(weighted_list)if weighted_list else attachments[0]

                        while len(floor_data["rooms"])<target_rooms and open_attachments and iterations <max_iterations:
                            iterations +=1

                            selected = _select_sprawling_attachment(open_attachments, floor_data["rooms"])
                            if not selected:
                                break
                            open_attachments.remove(selected)
                            from_room_id, from_direction, target_x, target_y = selected

                            if grid[target_y][target_x]is not None:

                                existing_room_id = grid[target_y][target_x]
                                for room in floor_data["rooms"]:
                                    if room["room_id"]==existing_room_id:
                                        if opposite_dir[from_direction]in _get_room_attachments(room):
                                            _connect_rooms(from_room_id, existing_room_id, from_direction)
                                        break
                                continue

                            needed_attachment = opposite_dir[from_direction]

                            progress = len(floor_data["rooms"])/target_rooms

                            room_pool =[]
                            roll = random.random()

                            straight_hallways =[h for h in hallway_rooms if len(_get_room_attachments(h))==2
                            and set(_get_room_attachments(h))in[{"top", "bottom"}, {"left", "right"}]]
                            branching_hallways =[h for h in hallway_rooms if len(_get_room_attachments(h))>=3]
                            corner_hallways =[h for h in hallway_rooms if len(_get_room_attachments(h))==2
                            and set(_get_room_attachments(h))not in[{"top", "bottom"}, {"left", "right"}]]

                            if progress <0.4:
                                if roll <0.5 and straight_hallways:
                                    room_pool = straight_hallways
                                elif roll <0.75 and corner_hallways:
                                    room_pool = corner_hallways
                                elif roll <0.9 and branching_hallways:
                                    room_pool = branching_hallways
                                elif hallway_rooms:
                                    room_pool = hallway_rooms

                            elif progress <0.7:
                                if roll <0.35 and branching_hallways:
                                    room_pool = branching_hallways
                                elif roll <0.6 and corner_hallways:
                                    room_pool = corner_hallways
                                elif roll <0.8 and straight_hallways:
                                    room_pool = straight_hallways
                                elif hallway_rooms:
                                    room_pool = hallway_rooms

                            elif progress <0.85:
                                if roll <0.5 and hallway_rooms:
                                    room_pool = hallway_rooms
                                elif regular_rooms:
                                    room_pool = regular_rooms

                            else:
                                if roll <0.3 and hallway_rooms:
                                    room_pool = hallway_rooms
                                elif regular_rooms:
                                    room_pool = regular_rooms

                            if not room_pool:
                                room_pool = hallway_rooms +regular_rooms

                            prefer_complex = progress <0.7
                            new_template = _find_fitting_room_weighted(needed_attachment, room_pool, target_x, target_y, prefer_complex)
                            if not new_template:
                                continue

                            new_room = _prepare_room(new_template, room_id, target_x, target_y)
                            _spawn_enemies(new_room)
                            _place_room(new_room, target_x, target_y)
                            _connect_rooms(from_room_id, room_id, from_direction)
                            room_id +=1

                        transport_placed_early = False
                        if need_transport and transport_rooms and open_attachments:
                            logging.info(f"Floor {floor_idx +1}: Attempting early transport placement, {len(open_attachments)} open attachments")

                            for i, (from_room_id, from_direction, target_x, target_y)in enumerate(list(open_attachments)):
                                if grid[target_y][target_x]is not None:
                                    continue
                                needed_attachment = opposite_dir[from_direction]
                                transport_template = _find_fitting_room(needed_attachment, transport_rooms, target_x, target_y)
                                if transport_template:
                                    transport = _prepare_room(transport_template, room_id, target_x, target_y)
                                    transport["leads_to_floor"]= floor_idx +2
                                    transport["is_exit_transport"]= True
                                    _place_room(transport, target_x, target_y)
                                    _connect_rooms(from_room_id, room_id, from_direction)
                                    open_attachments.pop(i)
                                    room_id +=1
                                    transport_placed_early = True
                                    logging.info(f"Placed exit transport(early) on floor {floor_idx +1} at({target_x}, {target_y})")
                                    break

                        fill_iterations = 0
                        max_fill = len(open_attachments)*2
                        while open_attachments and fill_iterations <max_fill:
                            fill_iterations +=1
                            from_room_id, from_direction, target_x, target_y = open_attachments.pop(0)

                            if grid[target_y][target_x]is not None:

                                existing_room_id = grid[target_y][target_x]
                                for room in floor_data["rooms"]:
                                    if room["room_id"]==existing_room_id:
                                        if opposite_dir[from_direction]in _get_room_attachments(room):
                                            _connect_rooms(from_room_id, existing_room_id, from_direction)
                                        break
                                continue

                            needed_attachment = opposite_dir[from_direction]

                            single_att_rooms =[r for r in regular_rooms if len(_get_room_attachments(r))==1]
                            terminal_template = _find_fitting_room(needed_attachment, single_att_rooms, target_x, target_y)

                            if not terminal_template:
                                terminal_template = _find_fitting_room(needed_attachment, regular_rooms +hallway_rooms, target_x, target_y)

                            if terminal_template:
                                new_room = _prepare_room(terminal_template, room_id, target_x, target_y)
                                _spawn_enemies(new_room)
                                _place_room(new_room, target_x, target_y)
                                _connect_rooms(from_room_id, room_id, from_direction)
                                room_id +=1

                        if need_transport and transport_rooms and not transport_placed_early:
                            placed_transport = False

                            for i, (from_room_id, from_direction, target_x, target_y)in enumerate(list(open_attachments)):
                                if grid[target_y][target_x]is not None:
                                    continue
                                needed_attachment = opposite_dir[from_direction]

                                transport_template = _find_fitting_room(needed_attachment, transport_rooms, target_x, target_y)
                                if transport_template:
                                    transport = _prepare_room(transport_template, room_id, target_x, target_y)
                                    transport["leads_to_floor"]= floor_idx +2
                                    transport["is_exit_transport"]= True
                                    _place_room(transport, target_x, target_y)
                                    _connect_rooms(from_room_id, room_id, from_direction)
                                    open_attachments.pop(i)
                                    room_id +=1
                                    placed_transport = True
                                    logging.info(f"Placed exit transport on floor {floor_idx +1} at({target_x}, {target_y})")
                                    break

                            if not placed_transport:

                                for room in floor_data["rooms"]:
                                    if placed_transport:
                                        break
                                    if room.get("type")=="transport":
                                        continue
                                    rx, ry = room["position"]["x"], room["position"]["y"]
                                    for att in _get_room_attachments(room):
                                        dx, dy = dir_offset[att]
                                        nx, ny = rx +dx, ry +dy
                                        if 0 <=nx <x_size and 0 <=ny <y_size and grid[ny][nx]is None:
                                            needed_attachment = opposite_dir[att]
                                            transport_template = _find_fitting_room(needed_attachment, transport_rooms, nx, ny)
                                            if transport_template:
                                                transport = _prepare_room(transport_template, room_id, nx, ny)
                                                transport["leads_to_floor"]= floor_idx +2
                                                transport["is_exit_transport"]= True
                                                _place_room(transport, nx, ny)
                                                _connect_rooms(room["room_id"], room_id, att)
                                                room_id +=1
                                                placed_transport = True
                                                logging.info(f"Placed exit transport on floor {floor_idx +1} at({nx}, {ny}) via room search")
                                                break

                        final_pass = 0
                        max_final = 100
                        while open_attachments and final_pass <max_final:
                            final_pass +=1
                            from_room_id, from_direction, target_x, target_y = open_attachments.pop(0)

                            if grid[target_y][target_x]is not None:
                                existing_room_id = grid[target_y][target_x]
                                for room in floor_data["rooms"]:
                                    if room["room_id"]==existing_room_id:
                                        if opposite_dir[from_direction]in _get_room_attachments(room):
                                            _connect_rooms(from_room_id, existing_room_id, from_direction)
                                        break
                                continue

                            needed_attachment = opposite_dir[from_direction]

                            single_att_rooms =[r for r in regular_rooms if len(_get_room_attachments(r))==1]
                            template = _find_fitting_room(needed_attachment, single_att_rooms, target_x, target_y)

                            if not template:
                                template = _find_fitting_room(needed_attachment, regular_rooms +hallway_rooms, target_x, target_y)

                            if not template:
                                continue

                            new_room = _prepare_room(template, room_id, target_x, target_y)
                            _spawn_enemies(new_room)
                            grid[target_y][target_x]= room_id
                            floor_data["rooms"].append(new_room)
                            _connect_rooms(from_room_id, room_id, from_direction)

                            for att in _get_room_attachments(new_room):
                                if att ==needed_attachment:
                                    continue
                                dx, dy = dir_offset[att]
                                nx, ny = target_x +dx, target_y +dy
                                if 0 <=nx <x_size and 0 <=ny <y_size and grid[ny][nx]is None:
                                    open_attachments.append((room_id, att, nx, ny))

                            room_id +=1

                        has_exit_transport = any(r.get("is_exit_transport")for r in floor_data["rooms"])

                        if need_transport_down and not has_exit_transport and transport_rooms:

                            logging.warning(f"Floor {floor_idx +1} missing exit transport, forcing placement...")

                            transport_placed = False
                            for room in floor_data["rooms"]:
                                if transport_placed:
                                    break
                                if room.get("type")=="transport":
                                    continue
                                rx, ry = room["position"]["x"], room["position"]["y"]
                                for att in _get_room_attachments(room):
                                    dx, dy = dir_offset[att]
                                    nx, ny = rx +dx, ry +dy
                                    if 0 <=nx <x_size and 0 <=ny <y_size and grid[ny][nx]is None:
                                        needed_attachment = opposite_dir[att]

                                        transport_template = _find_fitting_room(needed_attachment, transport_rooms, nx, ny)
                                        if transport_template:
                                            transport = _prepare_room(transport_template, room_id, nx, ny)
                                            transport["leads_to_floor"]= floor_idx +2
                                            transport["is_exit_transport"]= True
                                            grid[ny][nx]= room_id
                                            floor_data["rooms"].append(transport)
                                            _connect_rooms(room["room_id"], room_id, att)
                                            room_id +=1
                                            transport_placed = True
                                            logging.info(f"Forced transport placement on floor {floor_idx +1} at({nx}, {ny})")
                                            break

                            if not transport_placed:
                                logging.warning(f"Floor {floor_idx +1} - forcing transport with manual rotation...")
                                for room in floor_data["rooms"]:
                                    if transport_placed:
                                        break
                                    if room.get("type")=="transport":
                                        continue
                                    rx, ry = room["position"]["x"], room["position"]["y"]
                                    for att in _get_room_attachments(room):
                                        dx, dy = dir_offset[att]
                                        nx, ny = rx +dx, ry +dy
                                        if 0 <=nx <x_size and 0 <=ny <y_size and grid[ny][nx]is None:
                                            needed_attachment = opposite_dir[att]

                                            for transport_template in transport_rooms:
                                                if transport_placed:
                                                    break
                                                for rot in range(4):
                                                    rotated = _rotate_room_template(transport_template, rot)
                                                    if needed_attachment in _get_room_attachments(rotated):
                                                        transport = _prepare_room(rotated, room_id, nx, ny)
                                                        transport["leads_to_floor"]= floor_idx +2
                                                        transport["is_exit_transport"]= True
                                                        grid[ny][nx]= room_id
                                                        floor_data["rooms"].append(transport)
                                                        _connect_rooms(room["room_id"], room_id, att)
                                                        room_id +=1
                                                        transport_placed = True
                                                        logging.info(f"Forced rotated transport on floor {floor_idx +1} at({nx}, {ny})")
                                                        break
                                            if transport_placed:
                                                break

                            if not transport_placed:
                                logging.warning(f"Floor {floor_idx +1} - last resort transport placement...")
                                for room in floor_data["rooms"]:
                                    if transport_placed:
                                        break
                                    if room.get("type")=="transport":
                                        continue
                                    rx, ry = room["position"]["x"], room["position"]["y"]

                                    for direction in["top", "bottom", "left", "right"]:
                                        dx, dy = dir_offset[direction]
                                        nx, ny = rx +dx, ry +dy
                                        if 0 <=nx <x_size and 0 <=ny <y_size and grid[ny][nx]is None:
                                            needed_attachment = opposite_dir[direction]

                                            for transport_template in transport_rooms:
                                                if transport_placed:
                                                    break
                                                for rot in range(4):
                                                    rotated = _rotate_room_template(transport_template, rot)
                                                    if needed_attachment in _get_room_attachments(rotated):
                                                        transport = _prepare_room(rotated, room_id, nx, ny)
                                                        transport["leads_to_floor"]= floor_idx +2
                                                        transport["is_exit_transport"]= True
                                                        grid[ny][nx]= room_id
                                                        floor_data["rooms"].append(transport)

                                                        floor_data["connections"].append({
                                                        "from_room":room["room_id"],
                                                        "to_room":room_id,
                                                        "direction":direction,
                                                        "forced":True
                                                        })
                                                        room_id +=1
                                                        transport_placed = True
                                                        logging.info(f"Last resort transport on floor {floor_idx +1} at({nx}, {ny})")
                                                        break
                                            if transport_placed:
                                                break

                            if not transport_placed:
                                logging.error(f"Floor {floor_idx +1} - FAILED to place exit transport!")

                        dungeon["floors"].append(floor_data)

                    self._dg_state['generated_dungeon']= dungeon
                    self._dg_state['current_floor']= 0
                    self._dg_state['current_room_id']= 0 if dungeon["floors"][0]["rooms"]else None
                    self._dg_state['pending_door']= None

                    _update_display()
                    self._popup_show_info("Dungeon Generator", f"Generated dungeon with {num_floors} floor(s)!")
                    logging.info(f"Generated dungeon: {num_floors} floors")

                    if background_combat_timer[0]:
                        try:
                            dg.after_cancel(background_combat_timer[0])
                        except Exception:
                            pass

                    background_combat_timer[0]= dg.after(3000, _process_background_combat)# type: ignore

                    if npc_movement_timer[0]:
                        try:
                            dg.after_cancel(npc_movement_timer[0])
                        except Exception:
                            pass
                    npc_movement_timer[0]= dg.after(10000, _move_npcs_support)# type: ignore

                except Exception as e:
                    logging.exception("Failed to generate dungeon")
                    self._popup_show_info("Error", f"Failed to generate dungeon: {e}", sound = "error")

            def _get_current_room():

                try:
                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        return None
                    floor_idx = self._dg_state.get('current_floor', 0)
                    room_id = self._dg_state.get('current_room_id')
                    if floor_idx >=len(dungeon["floors"])or room_id is None:
                        return None
                    floor = dungeon["floors"][floor_idx]
                    for room in floor["rooms"]:
                        if room["room_id"]==room_id:
                            return room
                    return None
                except Exception:
                    return None

            def _get_available_exits():

                try:
                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        return[]
                    floor_idx = self._dg_state.get('current_floor', 0)
                    room_id = self._dg_state.get('current_room_id')
                    if floor_idx >=len(dungeon["floors"])or room_id is None:
                        return[]
                    floor = dungeon["floors"][floor_idx]
                    exits =[]
                    for conn in floor["connections"]:
                        if conn["from_room"]==room_id:
                            exits.append({"direction":conn["direction"], "to_room":conn["to_room"], "type":"connection"})
                        elif conn["to_room"]==room_id:
                            opposite = {"top":"bottom", "bottom":"top", "left":"right", "right":"left"}
                            exits.append({"direction":opposite.get(conn["direction"], conn["direction"]), "to_room":conn["from_room"], "type":"connection"})

                    current_room = _get_current_room()
                    if current_room and current_room.get("type")=="transport":

                        if current_room.get("is_entry_transport")and current_room.get("leads_to_floor"):
                            exits.append({"direction":"up", "to_floor":current_room["leads_to_floor"]-1, "type":"transport", "label":f"↑ Floor {current_room['leads_to_floor']}"})

                        if current_room.get("is_exit_transport")and current_room.get("leads_to_floor"):
                            exits.append({"direction":"down", "to_floor":current_room["leads_to_floor"]-1, "type":"transport", "label":f"↓ Floor {current_room['leads_to_floor']}"})

                        if current_room.get("also_leads_to_floor"):
                            exits.append({"direction":"down", "to_floor":current_room["also_leads_to_floor"]-1, "type":"transport", "label":f"↓ Floor {current_room['also_leads_to_floor']}"})

                    return exits
                except Exception:
                    return[]

            def _check_door_locked(direction):

                try:
                    room = _get_current_room()
                    if not room:
                        return False
                    doors_state = room.get("doors_state", {})
                    door_info = doors_state.get(direction, {})
                    return door_info.get("locked", False)and not door_info.get("picked", False)
                except Exception:
                    return False

            def _move_to_room(exit_info):

                try:

                    if self._dg_state.get('movement_locked', False):
                        return

                    direction = exit_info.get("direction")

                    if _check_door_locked(direction):
                        _play_dungeon_sound("locked", volume = 0.4)
                        self._dg_state['pending_door']= exit_info
                        _update_display()
                        return

                    if exit_info.get("type")!="transport":
                        current_room = _get_current_room()
                        if current_room:
                            doors_state = current_room.get("doors_state", {})
                            if direction in doors_state:
                                _play_dungeon_sound("door", volume = 0.3)
                            else:

                                _play_dungeon_sound("step", volume = 0.25)

                    if exit_info.get("type")=="transport":

                        current_room = _get_current_room()
                        transport_subtype = current_room.get("subtype", "stairs").lower()if current_room else "stairs"

                        self._dg_state['movement_locked']= True

                        if transport_subtype =="elevator":
                            _play_dungeon_sound("elevator", volume = 0.35)
                            unlock_delay = 2500
                        else:

                            _play_dungeon_sound("step", volume = 0.4)
                            unlock_delay = 800

                        dg.after(unlock_delay, lambda:self._dg_state.update({'movement_locked':False}))

                        next_floor = exit_info.get("to_floor", 0)
                        direction = exit_info.get("direction")
                        dungeon = self._dg_state.get('generated_dungeon')
                        current_floor = self._dg_state.get('current_floor', 0)
                        if dungeon and next_floor <len(dungeon["floors"]):
                            self._dg_state['current_floor']= next_floor

                            dest_room_id = None

                            if next_floor ==0:

                                for room in dungeon["floors"][next_floor]["rooms"]:
                                    if room.get("type")=="entrance":
                                        dest_room_id = room["room_id"]
                                        break
                            elif direction =="up":

                                for room in dungeon["floors"][next_floor]["rooms"]:
                                    if room.get("is_exit_transport")and room.get("leads_to_floor")==current_floor +1:
                                        dest_room_id = room["room_id"]
                                        break

                                    if room.get("also_leads_to_floor")==current_floor +1:
                                        dest_room_id = room["room_id"]
                                        break
                            else:

                                for room in dungeon["floors"][next_floor]["rooms"]:
                                    if room.get("is_entry_transport")and room.get("leads_to_floor")==current_floor +1:
                                        dest_room_id = room["room_id"]
                                        break

                            if dest_room_id is None:
                                dest_room_id = dungeon["floors"][next_floor]["rooms"][0]["room_id"]if dungeon["floors"][next_floor]["rooms"]else 0

                            self._dg_state['current_room_id']= dest_room_id
                    else:

                        self._dg_state['current_room_id']= exit_info.get("to_room")

                    room = _get_current_room()
                    if room:
                        room["visited"]= True

                    self._dg_state['pending_door']= None

                    _move_npcs_once()

                    _update_display()

                except Exception as e:
                    logging.exception("Failed to move to room")

            def _pick_door_success():

                try:
                    pending = self._dg_state.get('pending_door')
                    if not pending:
                        return
                    room = _get_current_room()
                    if room:
                        direction = pending.get("direction")

                        if direction in room.get("doors_state", {}):
                            room["doors_state"][direction]["picked"]= True

                        opposite = {"top":"bottom", "bottom":"top", "left":"right", "right":"left"}
                        dest_room_id = pending.get("to_room")
                        if dest_room_id is not None:
                            dungeon = self._dg_state.get('generated_dungeon')
                            floor_idx = self._dg_state.get('current_floor', 0)
                            if dungeon and floor_idx <len(dungeon["floors"]):
                                for dest_room in dungeon["floors"][floor_idx]["rooms"]:
                                    if dest_room.get("room_id")==dest_room_id:
                                        opp_dir = opposite.get(direction)
                                        if opp_dir and opp_dir in dest_room.get("doors_state", {}):
                                            dest_room["doors_state"][opp_dir]["picked"]= True
                                        break

                    _play_dungeon_sound("unlock", volume = 0.35)
                    self._dg_state['pending_door']= None
                    _move_to_room(pending)
                except Exception as e:
                    logging.exception("Failed to pick door")

            def _update_display():

                try:
                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        location_label.configure(text = "No dungeon generated")
                        room_info_label.configure(text = "Click 'Generate Dungeon' to create a new dungeon.")
                        door_status_label.configure(text = "")
                        pick_door_btn.configure(state = "disabled")
                        for w in nav_frame.winfo_children():
                            w.destroy()
                        if grid_canvas[0]:
                            grid_canvas[0].delete("all")
                        return

                    floor_idx = self._dg_state.get('current_floor', 0)
                    room = _get_current_room()

                    if not room:
                        location_label.configure(text = f"Floor {floor_idx +1} - No room")
                        room_info_label.configure(text = "")
                        return

                    location_label.configure(text = f"Floor {floor_idx +1} - {room.get('name', 'Unknown Room')}")

                    info_parts =[]
                    info_parts.append(f"Type: {room.get('type', 'unknown')}")
                    if room.get("visited"):
                        info_parts.append("(Visited)")
                    else:
                        info_parts.append("(New)")

                    enemies =[e for e in room.get("enemies", [])if e.get("alive", True)]
                    if enemies:
                        enemy_names =[e.get("name", "Unknown")for e in enemies]
                        info_parts.append(f"⚔ Enemies({len(enemies)}): {', '.join(enemy_names)}")
                    else:
                        info_parts.append("Enemies: None")

                    friendlies =[f for f in room.get("friendlies", [])if f.get("alive", True)]
                    if friendlies:
                        friendly_names =[f.get("name", "Unknown")for f in friendlies]
                        info_parts.append(f"🛡 Friendlies({len(friendlies)}): {', '.join(friendly_names)}")

                    pending_loot = room.get("pending_loot", [])
                    if pending_loot:
                        info_parts.append(f"💀 Loot available from {len(pending_loot)} defeated enemy(s)")

                    loot_spawn = room.get("loot_spawn", [])
                    if loot_spawn:
                        info_parts.append(f"Loot: {len(loot_spawn)} spawn point(s)")

                    if room.get("type")=="transport":
                        transport_info =[]
                        if room.get("is_entry_transport")and room.get("leads_to_floor"):
                            transport_info.append(f"↑ Floor {room.get('leads_to_floor')}")
                        if room.get("is_exit_transport")and room.get("leads_to_floor"):
                            transport_info.append(f"↓ Floor {room.get('leads_to_floor')}")
                        if room.get("also_leads_to_floor"):
                            transport_info.append(f"↓ Floor {room.get('also_leads_to_floor')}")
                        if transport_info:
                            info_parts.append("Transport: "+", ".join(transport_info))
                        else:
                            info_parts.append(f"Transport to Floor {room.get('leads_to_floor', '?')}")

                    room_info_label.configure(text = "\n".join(info_parts))

                    _draw_grid()

                    for w in nav_frame.winfo_children():
                        w.destroy()

                    exits = _get_available_exits()
                    direction_labels = {"top":"↑ North(↑/W)", "bottom":"↓ South(↓/S)", "left":"← West(←/A)", "right":"→ East(→/D)", "up":"⬆ Ascend"}
                    key_hints = {"top":"↑", "bottom":"↓", "left":"←", "right":"→"}

                    if exits:

                        exits_text = "Exits: "
                        exit_parts =[]
                        for exit_info in exits:
                            direction = exit_info.get("direction")
                            is_locked = _check_door_locked(direction)
                            dir_label = direction_labels.get(direction, direction.title())
                            if is_locked:
                                dir_label +=" 🔒"# type: ignore
                            exit_parts.append(dir_label)
                        exits_text +=" | ".join(exit_parts)
                        nav_label = customtkinter.CTkLabel(nav_frame, text = exits_text, font = customtkinter.CTkFont(size = 11))
                        nav_label.pack(side = 'left', padx = 4)

                    pending = self._dg_state.get('pending_door')
                    if pending:
                        direction = pending.get("direction")
                        door_status_label.configure(text = f"Door to {direction} is LOCKED! Pick the lock to proceed.")
                        pick_door_btn.configure(state = "normal", command = _pick_door_success)
                    else:
                        door_status_label.configure(text = "")
                        pick_door_btn.configure(state = "disabled")

                    if enemies:

                        kill_enemy_btn.configure(state = "normal", command = _kill_enemies_in_room)
                        collect_loot_btn.configure(state = "disabled")

                        for w in nav_frame.winfo_children():
                            if isinstance(w, customtkinter.CTkLabel):
                                w.configure(text = "⚔ Movement blocked - enemies present!")
                    else:
                        kill_enemy_btn.configure(state = "disabled")

                        if pending_loot:
                            collect_loot_btn.configure(state = "normal", command = _collect_loot_from_room)
                        else:
                            collect_loot_btn.configure(state = "disabled")

                except Exception as e:
                    logging.exception("Failed to update dungeon display")

            def _handle_arrow_key(event):

                try:

                    key_to_direction = {
                    "Up":"top",
                    "Down":"bottom",
                    "Left":"left",
                    "Right":"right"
                    }

                    direction = key_to_direction.get(event.keysym)
                    if not direction:
                        return

                    room = _get_current_room()
                    if room:
                        enemies =[e for e in room.get("enemies", [])if e.get("alive", True)]
                        if enemies:
                            return

                    exits = _get_available_exits()
                    for exit_info in exits:
                        if exit_info.get("direction")==direction:
                            _move_to_room(exit_info)
                            return

                except Exception as e:
                    logging.debug(f"Arrow key handling error: {e}")

            def _handle_floor_transport(event):

                try:
                    room = _get_current_room()
                    if not room or room.get("type")!="transport":
                        return

                    enemies =[e for e in room.get("enemies", [])if e.get("alive", True)]
                    if enemies:
                        return

                    transport_direction = None
                    if event.keysym =="Up":
                        transport_direction = "up"
                    elif event.keysym =="Down":
                        transport_direction = "down"

                    if not transport_direction:
                        return

                    exits = _get_available_exits()
                    for exit_info in exits:
                        if exit_info.get("type")=="transport"and exit_info.get("direction")==transport_direction:
                            _move_to_room(exit_info)
                            return

                except Exception as e:
                    logging.debug(f"Floor transport handling error: {e}")

            dg.bind("<Up>", _handle_arrow_key)
            dg.bind("<Down>", _handle_arrow_key)
            dg.bind("<Left>", _handle_arrow_key)
            dg.bind("<Right>", _handle_arrow_key)

            dg.bind("<w>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Up'})()))
            dg.bind("<s>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Down'})()))
            dg.bind("<a>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Left'})()))
            dg.bind("<d>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Right'})()))
            dg.bind("<W>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Up'})()))
            dg.bind("<S>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Down'})()))
            dg.bind("<A>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Left'})()))
            dg.bind("<D>", lambda e:_handle_arrow_key(type('Event', (), {'keysym':'Right'})()))

            dg.bind("<Shift-Up>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Up'})()))
            dg.bind("<Shift-Down>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Down'})()))
            dg.bind("<Shift-w>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Up'})()))
            dg.bind("<Shift-s>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Down'})()))
            dg.bind("<Shift-W>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Up'})()))
            dg.bind("<Shift-S>", lambda e:_handle_floor_transport(type('Event', (), {'keysym':'Down'})()))

            def _save_dungeon():

                try:
                    dungeon = self._dg_state.get('generated_dungeon')
                    if not dungeon:
                        self._popup_show_info("Error", "No dungeon to save.", sound = "error")
                        return

                    dungeons_dir = os.path.join(saves_folder or "saves", "dungeons")
                    os.makedirs(dungeons_dir, exist_ok = True)

                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"dungeon_{timestamp}.slddng"
                    filepath = os.path.join(dungeons_dir, filename)

                    save_data = {
                    "dungeon":dungeon,
                    "current_floor":self._dg_state.get('current_floor', 0),
                    "current_room_id":self._dg_state.get('current_room_id'),
                    "saved_at":datetime.now().isoformat()
                    }

                    _signed_json_write(filepath, save_data)

                    self._popup_show_info("Dungeon Saved", f"Saved to: {filename}")
                    logging.info(f"Saved dungeon to {filepath}")

                except Exception as e:
                    logging.exception("Failed to save dungeon")
                    self._popup_show_info("Error", f"Failed to save: {e}", sound = "error")

            def _load_dungeon():

                try:
                    dungeons_dir = os.path.join(saves_folder or "saves", "dungeons")
                    if not os.path.isdir(dungeons_dir):
                        self._popup_show_info("Error", "No saved dungeons found.", sound = "error")
                        return

                    dungeon_files = sorted(glob.glob(os.path.join(dungeons_dir, "*.slddng")), reverse = True)
                    if not dungeon_files:
                        self._popup_show_info("Error", "No saved dungeons found.", sound = "error")
                        return

                    options =[os.path.basename(f)for f in dungeon_files[:10]]
                    selected = self._popup_select_option("Load Dungeon", "Select a dungeon to load:", options)
                    if not selected:
                        return

                    filepath = os.path.join(dungeons_dir, selected)
                    save_data, _, dng_status = _signed_json_read(filepath, allow_unsigned = True)
                    if not isinstance(save_data, dict):
                        self._popup_show_info("Error", f"Failed to load dungeon (status: {dng_status})", sound = "error")
                        return

                    self._dg_state['generated_dungeon']= save_data.get("dungeon")
                    self._dg_state['current_floor']= save_data.get("current_floor", 0)
                    self._dg_state['current_room_id']= save_data.get("current_room_id", 0)
                    self._dg_state['pending_door']= None

                    _update_display()
                    self._popup_show_info("Dungeon Loaded", f"Loaded: {selected}")
                    logging.info(f"Loaded dungeon from {filepath}")

                except Exception as e:
                    logging.exception("Failed to load dungeon")
                    self._popup_show_info("Error", f"Failed to load: {e}", sound = "error")

            action_frame = customtkinter.CTkFrame(frm)
            action_frame.pack(fill = 'x', pady = 8)

            generate_btn = customtkinter.CTkButton(action_frame, text = "Generate Dungeon", width = 140, command = _generate_dungeon)
            generate_btn.pack(side = 'left', padx = 4)

            save_btn = customtkinter.CTkButton(action_frame, text = "Save Layout", width = 100, command = _save_dungeon)
            save_btn.pack(side = 'left', padx = 4)

            load_btn = customtkinter.CTkButton(action_frame, text = "Load Layout", width = 100, command = _load_dungeon)
            load_btn.pack(side = 'left', padx = 4)

            def _toggle_continuous_generation():
                if continuous_gen_active[0]:

                    continuous_gen_active[0]= False
                    if continuous_gen_timer[0]:
                        try:
                            dg.after_cancel(continuous_gen_timer[0])
                        except Exception:
                            pass
                        continuous_gen_timer[0]= None
                    continuous_gen_btn.configure(text = "Start Continuous Gen", fg_color =("gray70", "gray30"))
                    logging.info("Continuous dungeon generation stopped")
                else:

                    continuous_gen_active[0]= True
                    continuous_gen_btn.configure(text = "Stop Continuous Gen", fg_color =("#D35B58", "#C77C78"))
                    logging.info("Continuous dungeon generation started")
                    _continuous_generate_cycle()

            def _continuous_generate_cycle():
                if not continuous_gen_active[0]:
                    return
                try:
                    if not dg.winfo_exists():
                        continuous_gen_active[0]= False
                        return
                    _generate_dungeon()

                    continuous_gen_timer[0]= dg.after(10000, _continuous_generate_cycle)# type: ignore
                except Exception as e:
                    logging.error(f"Continuous generation error: {e}")
                    continuous_gen_active[0]= False
                    try:
                        continuous_gen_btn.configure(text = "Start Continuous Gen", fg_color =("gray70", "gray30"))
                    except Exception:
                        pass

            if global_variables.get("devmode", {}).get("value", False):
                continuous_gen_btn = customtkinter.CTkButton(
                action_frame,
                text = "Start Continuous Gen",
                width = 140,
                command = _toggle_continuous_generation,
                fg_color =("gray70", "gray30")
                )
                continuous_gen_btn.pack(side = 'left', padx = 4)

            _update_display()

            btn_close = customtkinter.CTkButton(frm, text = "Close", command = _confirm_close)
            btn_close.pack(pady = 8)

            self._dg_window = dg
            try:
                dg.focus_force()
                dg.lift()
            except Exception:
                pass
        except Exception:
            logging.exception("Failed to open Dungeon Generator window")

    def _open_encounter_roll_tool(self):

        logging.info("Encounter Roll tool called")

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
        enabled_enemies = {}

        if os.path.exists(dm_settings_path):
            try:
                dm_settings_loaded, _, dm_status = _signed_json_read(dm_settings_path, allow_unsigned = True)
                if isinstance(dm_settings_loaded, dict):
                    enabled_enemies = dm_settings_loaded.get("enabled_enemies", {})
            except Exception as e:
                logging.warning(f"Failed to load DM settings: {e}")

        enemy_list = table_data.get("tables", {}).get("enemy_drops", [])

        available_enemies =[
        enemy for enemy in enemy_list
        if enabled_enemies.get(enemy.get("name"), True)
        ]

        if not available_enemies:
            self._popup_show_info("Error", "No enabled enemies in table.", sound = "error")
            return

        self._clear_window()
        self._play_ui_sound("whoosh1")

        main_frame = customtkinter.CTkFrame(self.root, fg_color = "transparent")
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = "Encounter Roll",
        font = customtkinter.CTkFont(size = 24, weight = "bold")
        )
        title_label.pack(pady = 20)

        info_frame = customtkinter.CTkFrame(main_frame)
        info_frame.pack(fill = "x", pady = 10)

        info_text = """Encounter Difficulty Ranges:
        1 = Miniboss
        2-5 = Hard
        6-10 = Medium
        11-14 = Easy
        15-20 = None/Friendly(50/50)"""

        customtkinter.CTkLabel(
        info_frame,
        text = info_text,
        font = customtkinter.CTkFont(size = 12),
        justify = "left"
        ).pack(padx = 20, pady = 10)

        content_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        content_frame.pack(fill = "both", expand = True, pady = 10)

        loot_list_frame = customtkinter.CTkScrollableFrame(content_frame, width = 400, height = 300)
        loot_list_frame.pack(side = "left", fill = "both", expand = True, padx =(0, 10))

        loot_list_label = customtkinter.CTkLabel(
        loot_list_frame,
        text = "Enemy Loot",
        font = customtkinter.CTkFont(size = 16, weight = "bold")
        )
        loot_list_label.pack(pady = 10)

        right_frame = customtkinter.CTkFrame(content_frame, fg_color = "transparent")
        right_frame.pack(side = "right", fill = "both", expand = True, padx =(10, 0))

        result_label = customtkinter.CTkLabel(
        right_frame,
        text = "",
        font = customtkinter.CTkFont(size = 14),
        wraplength = 400,
        justify = "left"
        )
        result_label.pack(pady = 20)

        encounter_state = {"spawned_enemies":[], "all_loot":[]}

        def clear_loot_list():
            for widget in loot_list_frame.winfo_children():
                if widget !=loot_list_label:
                    widget.destroy()
            encounter_state["spawned_enemies"]=[]
            encounter_state["all_loot"]=[]

        def add_enemy_to_list(enemy_name, difficulty, loot_items):
            enemy_frame = customtkinter.CTkFrame(loot_list_frame)
            enemy_frame.pack(fill = "x", pady = 5, padx = 5)

            header_frame = customtkinter.CTkFrame(enemy_frame, fg_color = "transparent")
            header_frame.pack(fill = "x", padx = 5, pady =(5, 2))

            enemy_header = customtkinter.CTkLabel(
            header_frame,
            text = f"▸ {enemy_name}({difficulty})",
            font = customtkinter.CTkFont(size = 13, weight = "bold"),
            anchor = "w"
            )
            enemy_header.pack(side = "left", fill = "x", expand = True)

            if loot_items:
                def save_this_enemy_loot(name = enemy_name, loot = loot_items):
                    self._save_enemy_loot_transfer(name, loot)

                save_btn = customtkinter.CTkButton(
                header_frame,
                text = "Save",
                width = 50,
                height = 24,
                font = customtkinter.CTkFont(size = 11),
                command = save_this_enemy_loot
                )
                save_btn.pack(side = "right", padx = 2)

            if loot_items:
                for item in loot_items:
                    item_name = item.get('name', 'Unknown Item')
                    qty = item.get('quantity', 1)
                    item_text = f" • {item_name}"
                    if qty >1:
                        item_text +=f" x{qty}"
                    item_label = customtkinter.CTkLabel(
                    enemy_frame,
                    text = item_text,
                    font = customtkinter.CTkFont(size = 11),
                    anchor = "w"
                    )
                    item_label.pack(fill = "x", padx = 10)
                encounter_state["all_loot"].extend(loot_items)
            else:
                no_loot_label = customtkinter.CTkLabel(
                enemy_frame,
                text = "(No items)",
                font = customtkinter.CTkFont(size = 11),
                text_color = "gray",
                anchor = "w"
                )
                no_loot_label.pack(fill = "x", padx = 10)

            encounter_state["spawned_enemies"].append({
            "name":enemy_name,
            "difficulty":difficulty,
            "loot":loot_items
            })

        def perform_roll():
            clear_loot_list()
            roll = random.randint(1, 20)

            if roll ==1:
                difficulty = "Miniboss"
            elif 2 <=roll <=5:
                difficulty = "Hard"
            elif 6 <=roll <=10:
                difficulty = "Medium"
            elif 11 <=roll <=14:
                difficulty = "Easy"
            else:
                is_friendly = random.choice([True, False])
                difficulty = "Friendly"if is_friendly else "None"

            result_text = f"Roll: {roll}\nDifficulty: {difficulty}\n\n"

            if difficulty =="None":
                result_text +="No encounter!"
                result_label.configure(text = result_text)
                return

            if difficulty =="Friendly":
                friendly_enemies =[e for e in available_enemies if e.get("difficulty", "").lower()=="friendly"]
                if not friendly_enemies:
                    friendly_enemies = available_enemies

                selected_enemy = random.choice(friendly_enemies)
                enemy_name = selected_enemy.get('name', 'Unknown')
                result_text +=f"Friendly encounter!\nEnemy: {enemy_name}\n\n"
                result_text +="Friendly enemies have no loot."
                result_label.configure(text = result_text)

                add_enemy_to_list(enemy_name, "Friendly", [])
                return

            matching_enemies =[e for e in available_enemies if e.get("difficulty", "").lower()==difficulty.lower()]

            if not matching_enemies:
                result_text +=f"No enemies found for difficulty: {difficulty}"
                result_label.configure(text = result_text)
                return

            selected_enemy = random.choice(matching_enemies)
            enemy_name = selected_enemy.get('name', 'Unknown')
            result_text +=f"Enemy: {enemy_name}\n\n"

            loot = self._generate_enemy_loot(selected_enemy, table_data)

            result_text +=f"Generated {len(loot)} item(s)"
            result_label.configure(text = result_text)

            add_enemy_to_list(enemy_name, difficulty, loot)

        def save_all_loot():
            if not encounter_state["all_loot"]:
                self._popup_show_info("Info", "No loot to save.", sound = "error")
                return
            enemy_names = ", ".join([e["name"]for e in encounter_state["spawned_enemies"]])
            self._save_enemy_loot_transfer(enemy_names, encounter_state["all_loot"])

        self._create_sound_button(
        right_frame,
        text = "Roll for Encounter",
        command = perform_roll,
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        ).pack(pady = 10)

        self._create_sound_button(
        right_frame,
        text = "Save All Loot as Transfer",
        command = save_all_loot,
        width = 300
        ).pack(pady = 10)

        back_button = self._create_sound_button(
        right_frame,
        text = "Back to DM Tools",
        command = lambda:[self._clear_window(), self._open_dm_tools()],
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        back_button.pack(pady = 20)

    def _open_create_item_transfer_tool(self):
        logging.info("Create Item Transfer tool called")
        self._clear_window()

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                self._popup_show_info("Error", "No table files found.", sound = "error")
                return
            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                table_data = json.load(f)
        except Exception as e:
            logging.error(f"Failed to load tables for item transfer: {e}")
            self._popup_show_info("Error", f"Failed to load tables: {e}", sound = "error")
            return

        all_items =[]
        for table_name, items in table_data.get("tables", {}).items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict)or item.get("id")is None:
                    continue
                item_copy = item.copy()
                item_copy["table_category"]= table_name
                all_items.append(item_copy)

        all_items.sort(key = lambda x:x.get("id", 999999))

        if not all_items:
            self._popup_show_info("Error", "No items found in table.", sound = "error")
            return

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(3, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_columnconfigure(1, weight = 0)

        title_label = customtkinter.CTkLabel(main_frame, text = "Create Item Transfer", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.grid(row = 0, column = 0, columnspan = 2, pady =(0, 10))

        top_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        top_frame.grid(row = 1, column = 0, columnspan = 2, sticky = "ew", pady = 10)
        top_frame.grid_columnconfigure(1, weight = 1)

        money_label = customtkinter.CTkLabel(top_frame, text = "Money Amount:")
        money_label.grid(row = 0, column = 0, padx =(0, 10), sticky = "w")
        money_entry = customtkinter.CTkEntry(top_frame, placeholder_text = format_price(0), width = 120)
        money_entry.grid(row = 0, column = 1, sticky = "w", padx =(0, 30))

        search_label = customtkinter.CTkLabel(top_frame, text = "Search(ID or Name):", font = customtkinter.CTkFont(size = 13))
        search_label.grid(row = 0, column = 2, padx =(0, 10), sticky = "w")

        search_entry = customtkinter.CTkEntry(top_frame, placeholder_text = "Enter item ID or name...", width = 250)
        search_entry.grid(row = 0, column = 3, sticky = "ew", padx =(0, 10))

        ITEMS_PER_PAGE = 25
        current_page =[0]
        current_filtered =[all_items]
        search_timer =[None]
        selected_items =[]

        info_label = customtkinter.CTkLabel(top_frame, text = f"Page 1 | {len(all_items)} items total", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        info_label.grid(row = 0, column = 4, padx = 10)

        content_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        content_frame.grid(row = 3, column = 0, columnspan = 2, sticky = "nsew", pady = 10)
        content_frame.grid_rowconfigure(0, weight = 1)
        content_frame.grid_columnconfigure(0, weight = 1)
        content_frame.grid_columnconfigure(1, weight = 0)

        scroll_frame = customtkinter.CTkScrollableFrame(content_frame, width = 600, height = 350)
        scroll_frame.grid(row = 0, column = 0, sticky = "nsew", padx =(0, 10))
        scroll_frame.grid_columnconfigure(0, weight = 1)

        selected_frame = customtkinter.CTkFrame(content_frame)
        selected_frame.grid(row = 0, column = 1, sticky = "nsew")

        selected_label = customtkinter.CTkLabel(selected_frame, text = "Selected Items", font = customtkinter.CTkFont(size = 14, weight = "bold"))
        selected_label.pack(pady = 10)

        selected_count_label = customtkinter.CTkLabel(selected_frame, text = "0 items selected", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        selected_count_label.pack(pady = 5)

        selected_scroll = customtkinter.CTkScrollableFrame(selected_frame, width = 280, height = 300)
        selected_scroll.pack(fill = "both", expand = True, padx = 5, pady = 5)

        def update_selected_display():
            for widget in selected_scroll.winfo_children():
                widget.destroy()

            selected_count_label.configure(text = f"{len(selected_items)} item(s) selected")

            for idx, item in enumerate(selected_items):
                item_row = customtkinter.CTkFrame(selected_scroll)
                item_row.pack(fill = "x", pady = 2, padx = 2)

                item_label = customtkinter.CTkLabel(
                item_row,
                text = f"ID {item.get('id', '?')}: {self._format_item_name(item)[:25]}",
                font = customtkinter.CTkFont(size = 11),
                anchor = "w"
                )
                item_label.pack(side = "left", fill = "x", expand = True, padx = 5)

                remove_btn = customtkinter.CTkButton(
                item_row,
                text = "X",
                width = 25,
                height = 25,
                font = customtkinter.CTkFont(size = 10),
                fg_color = "darkred",
                hover_color = "red",
                command = lambda i = idx:remove_item(i)
                )
                remove_btn.pack(side = "right", padx = 2)

        def remove_item(index):
            if 0 <=index <len(selected_items):
                selected_items.pop(index)
                update_selected_display()
                display_page(current_page[0])

        def add_item_to_transfer(item):
            item_copy = item.copy()
            selected_items.append(item_copy)
            update_selected_display()
            display_page(current_page[0])

        def is_item_selected(item):
            item_id = item.get("id")
            for sel in selected_items:
                if sel.get("id")==item_id:
                    return True
            return False

        pagination_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        pagination_frame.grid(row = 4, column = 0, columnspan = 2, pady = 5)

        def create_item_widget(item):
            item_frame = customtkinter.CTkFrame(scroll_frame)
            item_frame.pack(fill = "x", pady = 3, padx = 5)
            item_frame.grid_columnconfigure(1, weight = 1)

            id_label = customtkinter.CTkLabel(
            item_frame,
            text = f"ID: {item.get('id', 'N/A')}",
            font = customtkinter.CTkFont(size = 12, weight = "bold"),
            width = 80,
            fg_color =("gray75", "gray25"),
            corner_radius = 6
            )
            id_label.grid(row = 0, column = 0, padx = 8, pady = 8, sticky = "w")

            details_frame = customtkinter.CTkFrame(item_frame, fg_color = "transparent")
            details_frame.grid(row = 0, column = 1, sticky = "ew", padx = 8, pady = 8)

            name_label = customtkinter.CTkLabel(
            details_frame,
            text = item.get("name", "Unknown"),
            font = customtkinter.CTkFont(size = 13, weight = "bold"),
            anchor = "w"
            )
            name_label.pack(anchor = "w")

            category_label = customtkinter.CTkLabel(
            details_frame,
            text = f"{item.get('table_category', 'N/A')} | {item.get('rarity', 'N/A')} | {format_price(item.get('value', 0))}",
            font = customtkinter.CTkFont(size = 10),
            text_color = "gray",
            anchor = "w"
            )
            category_label.pack(anchor = "w")

            already_selected = is_item_selected(item)
            add_button = self._create_sound_button(
            item_frame,
            "Added"if already_selected else "Add",
            lambda it = item:add_item_to_transfer(it),
            width = 80,
            height = 30,
            font = customtkinter.CTkFont(size = 11)
            )
            if already_selected:
                add_button.configure(state = "disabled", fg_color = "gray")
            add_button.grid(row = 0, column = 2, padx = 8, pady = 8)

        def display_page(page_num):
            items = current_filtered[0]
            total_pages = max(1, (len(items)+ITEMS_PER_PAGE -1)//ITEMS_PER_PAGE)

            page_num = max(0, min(page_num, total_pages -1))
            current_page[0]= page_num

            for widget in scroll_frame.winfo_children():
                widget.destroy()

            if not items:
                no_results = customtkinter.CTkLabel(scroll_frame, text = "No items found.", font = customtkinter.CTkFont(size = 14), text_color = "gray")
                no_results.pack(pady = 20)
                info_label.configure(text = "No items found")
                update_pagination_controls(0, 0)
                return

            start_idx = page_num *ITEMS_PER_PAGE
            end_idx = min(start_idx +ITEMS_PER_PAGE, len(items))

            for i in range(start_idx, end_idx):
                create_item_widget(items[i])

            info_label.configure(text = f"Page {page_num +1} of {total_pages} | {len(items)} items total")

            update_pagination_controls(page_num, total_pages)

            try:
                scroll_frame._parent_canvas.yview_moveto(0)
            except Exception:
                pass

        def update_pagination_controls(current, total):
            for widget in pagination_frame.winfo_children():
                widget.destroy()

            if total <=1:
                return

            first_btn = customtkinter.CTkButton(
            pagination_frame, text = "<<", width = 40, height = 30,
            command = lambda:display_page(0),
            state = "normal"if current >0 else "disabled"
            )
            first_btn.pack(side = "left", padx = 2)

            prev_btn = customtkinter.CTkButton(
            pagination_frame, text = "<", width = 40, height = 30,
            command = lambda:display_page(current -1),
            state = "normal"if current >0 else "disabled"
            )
            prev_btn.pack(side = "left", padx = 2)

            start_page = max(0, current -3)
            end_page = min(total, start_page +7)
            if end_page -start_page <7:
                start_page = max(0, end_page -7)

            for p in range(start_page, end_page):
                btn = customtkinter.CTkButton(
                pagination_frame,
                text = str(p +1),
                width = 35,
                height = 30,
                fg_color =("gray75", "gray25")if p ==current else None,
                command = lambda page = p:display_page(page)
                )
                btn.pack(side = "left", padx = 1)

            next_btn = customtkinter.CTkButton(
            pagination_frame, text = ">", width = 40, height = 30,
            command = lambda:display_page(current +1),
            state = "normal"if current <total -1 else "disabled"
            )
            next_btn.pack(side = "left", padx = 2)

            last_btn = customtkinter.CTkButton(
            pagination_frame, text = ">>", width = 40, height = 30,
            command = lambda:display_page(total -1),
            state = "normal"if current <total -1 else "disabled"
            )
            last_btn.pack(side = "left", padx = 2)

        def filter_items(search_term):
            search_lower = search_term.lower().strip()

            if search_lower:
                filtered =[
                item for item in all_items
                if search_lower in str(item.get("id", ""))or search_lower in item.get("name", "").lower()
                ]
            else:
                filtered = all_items

            current_filtered[0]= filtered
            current_page[0]= 0
            display_page(0)

        def on_search_change(*args):
            if search_timer[0]is not None:
                try:
                    self.root.after_cancel(search_timer[0])
                except Exception:
                    pass

            search_timer[0]= self.root.after(200, lambda:filter_items(search_entry.get()))# type: ignore

        search_entry.bind("<KeyRelease>", on_search_change)

        display_page(0)

        def save_transfer():
            try:
                transfer_money = parse_display_price_to_usd(money_entry.get(), default = 0, round_to_int = True)
            except ValueError:
                self._popup_show_info("Error", "Money amount must be a valid currency value.", sound = "error")
                return
            try:
                if not selected_items and transfer_money ==0:
                    self._popup_show_info("Error", "Add money or select at least one item.", sound = "error")
                    return
                items_to_send =[]
                for item in selected_items:
                    itm = {k:v for k, v in item.items()if k !="table_category"}
                    itm = add_subslots_to_item(itm)
                    items_to_send.append(itm)
                transfer_data = {
                "money":transfer_money,
                "items":items_to_send,
                "timestamp":datetime.now().isoformat(),
                "from_character":"DM"
                }
                encoded_data = json.dumps(transfer_data, ensure_ascii = False)
                os.makedirs("transfers", exist_ok = True)
                filename = os.path.join("transfers", f"transfer_dm_{datetime.now().strftime('%Y%m%d_%H%M%S')}{global_variables['transfer_extension']}")
                _signed_json_write(filename, transfer_data, portable = True)
                self._popup_show_info("Success", f"Saved transfer with {format_price(transfer_money)} and {len(items_to_send)} items.", sound = "success")
                logging.info(f"Saved DM transfer to {filename}")
                self._open_dm_tools()
            except Exception as e:
                logging.error(f"Failed to save item transfer: {e}")
                self._popup_show_info("Error", f"Failed to save item transfer: {e}", sound = "error")

        def clear_selected():
            selected_items.clear()
            update_selected_display()
            display_page(current_page[0])

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 5, column = 0, columnspan = 2, pady = 10)

        clear_button = self._create_sound_button(button_frame, "Clear Selection", clear_selected, width = 150, height = 40, font = customtkinter.CTkFont(size = 14))
        clear_button.pack(side = "left", padx = 10)

        save_button = self._create_sound_button(button_frame, "Save Transfer", save_transfer, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        save_button.pack(side = "left", padx = 10)

        back_button = self._create_sound_button(button_frame, "Back to DM Tools", lambda:[self._clear_window(), self._open_dm_tools()], width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_button.pack(side = "left", padx = 10)

    def _open_create_magazine_transfer_tool(self):

        logging.info("Create Loaded Magazine Transfer tool called")

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

        magazines = table_data.get("tables", {}).get("magazines", [])

        if not magazines:
            self._popup_show_info("Error", "No magazines found in table.", sound = "error")
            return

        all_magazines = sorted(magazines, key = lambda x:x.get("name", "").lower())

        self._clear_window()
        self._play_ui_sound("whoosh1")

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)
        main_frame.grid_rowconfigure(2, weight = 1)
        main_frame.grid_columnconfigure(0, weight = 1)

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = "Create Loaded Magazine Transfer",
        font = customtkinter.CTkFont(size = 24, weight = "bold")
        )
        title_label.grid(row = 0, column = 0, pady =(0, 10))

        top_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        top_frame.grid(row = 1, column = 0, sticky = "ew", pady = 10)
        top_frame.grid_columnconfigure(1, weight = 1)

        search_label = customtkinter.CTkLabel(top_frame, text = "Search(Name or Caliber):", font = customtkinter.CTkFont(size = 13))
        search_label.grid(row = 0, column = 0, padx =(0, 10), sticky = "w")

        search_entry = customtkinter.CTkEntry(top_frame, placeholder_text = "Enter magazine name or caliber...", width = 300)
        search_entry.grid(row = 0, column = 1, sticky = "w", padx =(0, 20))

        ITEMS_PER_PAGE = 20
        current_page =[0]
        current_filtered =[all_magazines]
        search_timer =[None]

        info_label = customtkinter.CTkLabel(top_frame, text = f"Page 1 | {len(all_magazines)} magazines total", font = customtkinter.CTkFont(size = 11), text_color = "gray")
        info_label.grid(row = 0, column = 2, padx = 10)

        scroll_frame = customtkinter.CTkScrollableFrame(main_frame, height = 400)
        scroll_frame.grid(row = 2, column = 0, sticky = "nsew", pady = 10)
        scroll_frame.grid_columnconfigure(0, weight = 1)

        pagination_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        pagination_frame.grid(row = 3, column = 0, pady = 5)

        def create_mag_widget(mag):
            mag_frame = customtkinter.CTkFrame(scroll_frame)
            mag_frame.pack(fill = "x", pady = 3, padx = 5)
            mag_frame.grid_columnconfigure(1, weight = 1)

            mag_info = f"{mag.get('name', 'Unknown')}"
            mag_details = f"Caliber: {', '.join(mag.get('caliber', ['Unknown']))} | Capacity: {mag.get('capacity', 0)}"
            if mag.get("magazinesystem"):
                mag_details +=f" | System: {mag.get('magazinesystem')}"

            name_label = customtkinter.CTkLabel(
            mag_frame,
            text = mag_info,
            font = customtkinter.CTkFont(size = 13, weight = "bold"),
            anchor = "w"
            )
            name_label.grid(row = 0, column = 0, padx = 10, pady =(8, 2), sticky = "w")

            details_label = customtkinter.CTkLabel(
            mag_frame,
            text = mag_details,
            font = customtkinter.CTkFont(size = 11),
            text_color = "gray",
            anchor = "w"
            )
            details_label.grid(row = 1, column = 0, padx = 10, pady =(0, 8), sticky = "w")

            def create_mag_transfer(m = mag):
                self._create_loaded_magazine_dialog(m, table_data)

            create_btn = self._create_sound_button(
            mag_frame,
            text = "Create Transfer",
            command = create_mag_transfer,
            width = 140,
            height = 32
            )
            create_btn.grid(row = 0, column = 1, rowspan = 2, padx = 10, pady = 8, sticky = "e")

        def display_page(page_num):
            items = current_filtered[0]
            total_pages = max(1, (len(items)+ITEMS_PER_PAGE -1)//ITEMS_PER_PAGE)
            page_num = max(0, min(page_num, total_pages -1))
            current_page[0]= page_num

            for widget in scroll_frame.winfo_children():
                widget.destroy()

            if not items:
                no_results = customtkinter.CTkLabel(scroll_frame, text = "No magazines found.", font = customtkinter.CTkFont(size = 14), text_color = "gray")
                no_results.pack(pady = 20)
                info_label.configure(text = "No magazines found")
                update_pagination_controls(0, 0)
                return

            start_idx = page_num *ITEMS_PER_PAGE
            end_idx = min(start_idx +ITEMS_PER_PAGE, len(items))

            for i in range(start_idx, end_idx):
                create_mag_widget(items[i])

            info_label.configure(text = f"Page {page_num +1} of {total_pages} | {len(items)} magazines total")
            update_pagination_controls(page_num, total_pages)

            try:
                scroll_frame._parent_canvas.yview_moveto(0)
            except Exception:
                pass

        def update_pagination_controls(current, total):
            for widget in pagination_frame.winfo_children():
                widget.destroy()

            if total <=1:
                return

            first_btn = customtkinter.CTkButton(pagination_frame, text = "<<", width = 40, height = 30, command = lambda:display_page(0), state = "normal"if current >0 else "disabled")
            first_btn.pack(side = "left", padx = 2)

            prev_btn = customtkinter.CTkButton(pagination_frame, text = "<", width = 40, height = 30, command = lambda:display_page(current -1), state = "normal"if current >0 else "disabled")
            prev_btn.pack(side = "left", padx = 2)

            start_page = max(0, current -3)
            end_page = min(total, start_page +7)
            if end_page -start_page <7:
                start_page = max(0, end_page -7)

            for p in range(start_page, end_page):
                btn = customtkinter.CTkButton(pagination_frame, text = str(p +1), width = 35, height = 30, fg_color =("gray75", "gray25")if p ==current else None, command = lambda page = p:display_page(page))
                btn.pack(side = "left", padx = 1)

            next_btn = customtkinter.CTkButton(pagination_frame, text = ">", width = 40, height = 30, command = lambda:display_page(current +1), state = "normal"if current <total -1 else "disabled")
            next_btn.pack(side = "left", padx = 2)

            last_btn = customtkinter.CTkButton(pagination_frame, text = ">>", width = 40, height = 30, command = lambda:display_page(total -1), state = "normal"if current <total -1 else "disabled")
            last_btn.pack(side = "left", padx = 2)

        def filter_magazines(search_term):
            search_lower = search_term.lower().strip()

            if search_lower:
                filtered =[
                mag for mag in all_magazines
                if search_lower in mag.get("name", "").lower()
                or any(search_lower in cal.lower()for cal in mag.get("caliber", []))
                or search_lower in mag.get("magazinesystem", "").lower()
                ]
            else:
                filtered = all_magazines

            current_filtered[0]= filtered
            current_page[0]= 0
            display_page(0)

        def on_search_change(*args):
            if search_timer[0]is not None:
                try:
                    self.root.after_cancel(search_timer[0])
                except Exception:
                    pass
            search_timer[0]= self.root.after(200, lambda:filter_magazines(search_entry.get()))# type: ignore

        search_entry.bind("<KeyRelease>", on_search_change)

        display_page(0)

        back_button = self._create_sound_button(
        main_frame,
        text = "Back to DM Tools",
        command = lambda:[self._clear_window(), self._open_dm_tools()],
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        back_button.grid(row = 4, column = 0, pady = 20)

    def _create_loaded_magazine_dialog(self, magazine, table_data):

        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title(f"Create: {magazine.get('name', 'Magazine')}")
        dialog.transient(self.root)
        self._center_popup_on_window(dialog, 600, 700)
        try:
            dialog.wait_visibility()
            dialog.grab_set()
        except Exception as e:
            logging.warning("Dialog grab_set failed: %s", e)

        customtkinter.CTkLabel(
        dialog,
        text = f"Configure {magazine.get('name', 'Magazine')}",
        font = customtkinter.CTkFont(size = 16, weight = "bold")
        ).pack(pady = 10)

        quantity_frame = customtkinter.CTkFrame(dialog)
        quantity_frame.pack(fill = "x", padx = 20, pady = 10)

        customtkinter.CTkLabel(
        quantity_frame,
        text = "Number of magazines:",
        font = customtkinter.CTkFont(size = 12)
        ).pack(side = "left", padx = 10)

        quantity_var = customtkinter.StringVar(value = "1")
        quantity_entry = customtkinter.CTkEntry(quantity_frame, textvariable = quantity_var, width = 100)
        quantity_entry.pack(side = "right", padx = 10)

        customtkinter.CTkLabel(
        dialog,
        text = "Select ammunition type:",
        font = customtkinter.CTkFont(size = 14, weight = "bold")
        ).pack(pady = 10)

        mag_calibers = magazine.get("caliber", [])
        ammunition_table = table_data.get("tables", {}).get("ammunition", [])

        compatible_ammo =[
        ammo for ammo in ammunition_table
        if ammo.get("caliber")in mag_calibers
        ]

        if not compatible_ammo:
            customtkinter.CTkLabel(
            dialog,
            text = "No compatible ammunition found!",
            font = customtkinter.CTkFont(size = 12),
            text_color = "red"
            ).pack(pady = 20)

            self._create_sound_button(
            dialog,
            text = "Close",
            command = dialog.destroy,
            fg_color = "#8B0000"
            ).pack(pady = 10)
            return

        selected_ammo = customtkinter.StringVar(value = compatible_ammo[0].get("name", ""))
        selected_variant = customtkinter.StringVar(value = "")

        ammo_scroll = customtkinter.CTkScrollableFrame(dialog, height = 200)
        ammo_scroll.pack(fill = "x", padx = 20, pady = 10)

        for ammo in compatible_ammo:
            ammo_frame = customtkinter.CTkFrame(ammo_scroll)
            ammo_frame.pack(fill = "x", pady = 2)

            radio = customtkinter.CTkRadioButton(
            ammo_frame,
            text = ammo.get("name", "Unknown"),
            variable = selected_ammo,
            value = ammo.get("name", ""),
            font = customtkinter.CTkFont(size = 12)
            )
            radio.pack(anchor = "w", padx = 10, pady = 5)

            if ammo.get("variants"):
                variant_frame = customtkinter.CTkFrame(ammo_frame)
                variant_frame.pack(fill = "x", padx = 30)

                for variant in ammo["variants"]:
                    var_radio = customtkinter.CTkRadioButton(
                    variant_frame,
                    text = variant.get("name", "Unknown Variant"),
                    variable = selected_variant,
                    value = f"{ammo.get('name')}|{variant.get('name')}",
                    font = customtkinter.CTkFont(size = 11)
                    )
                    var_radio.pack(anchor = "w", padx = 10, pady = 2)

        fill_frame = customtkinter.CTkFrame(dialog)
        fill_frame.pack(fill = "x", padx = 20, pady = 10)

        customtkinter.CTkLabel(
        fill_frame,
        text = "Fill level(% of capacity):",
        font = customtkinter.CTkFont(size = 12)
        ).pack(side = "left", padx = 10)

        fill_var = customtkinter.StringVar(value = "100")
        fill_entry = customtkinter.CTkEntry(fill_frame, textvariable = fill_var, width = 100)
        fill_entry.pack(side = "right", padx = 10)

        def create_transfer():
            try:
                qty = int(quantity_var.get())
                fill_percent = int(fill_var.get())

                if qty <=0 or fill_percent <0 or fill_percent >100:
                    raise ValueError("Invalid quantity or fill percentage")

                ammo_obj = None
                for ammo in compatible_ammo:
                    if ammo.get("name")==selected_ammo.get():
                        ammo_obj = ammo
                        break

                if not ammo_obj:
                    raise ValueError("No ammunition selected")

                variant_info = None
                if selected_variant.get():
                    variant_parts = selected_variant.get().split("|")
                    if len(variant_parts)==2:
                        for var in ammo_obj.get("variants", []):
                            if var.get("name")==variant_parts[1]:
                                variant_info = var
                                break

                if not variant_info:
                    variants = ammo_obj.get("variants", [])
                    if variants:
                        variant_info = variants[0]

                magazines =[]
                capacity = magazine.get("capacity", 30)
                rounds_to_load = int(capacity *(fill_percent /100.0))

                for i in range(qty):
                    mag_copy = json.loads(json.dumps(magazine))
                    mag_copy["rounds"]=[]

                    if not mag_copy.get("magazinesystem"):
                        mag_copy["magazinesystem"]= magazine.get("magazinesystem", "Unknown")

                    for j in range(rounds_to_load):
                        caliber = ammo_obj.get("caliber", "Unknown")
                        if isinstance(caliber, list):
                            caliber = caliber[0]if caliber else "Unknown"

                        round_data = {
                        "caliber":caliber,
                        "name":f"{caliber} | {variant_info.get('name', 'FMJ')if variant_info else 'FMJ'}",
                        "variant":variant_info.get("name", "FMJ")if variant_info else "FMJ"
                        }

                        if variant_info:
                            if variant_info.get("type"):
                                round_data["type"]= variant_info.get("type")
                            if variant_info.get("pen"):
                                round_data["pen"]= variant_info.get("pen")
                            if variant_info.get("tip"):
                                round_data["tip"]= variant_info.get("tip")
                            if variant_info.get("modifiers"):
                                round_data["modifiers"]= variant_info.get("modifiers")

                        mag_copy["rounds"].append(round_data)

                    magazines.append(mag_copy)

                self._save_magazine_transfer(magazines)
                dialog.destroy()

            except ValueError as e:
                self._popup_show_info("Error", f"Invalid input: {e}", sound = "error")

        self._create_sound_button(
        dialog,
        text = "Create Transfer",
        command = create_transfer,
        width = 200
        ).pack(pady = 10)

        self._create_sound_button(
        dialog,
        text = "Cancel",
        command = dialog.destroy,
        fg_color = "#8B0000",
        width = 200
        ).pack(pady = 5)

    def _open_create_belt_transfer_tool(self):

        logging.info("Create Belt Transfer tool called")

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

        magazines = table_data.get("tables", {}).get("magazines", [])
        belt_links =[mag for mag in magazines if mag.get("beltlink")]

        if not belt_links:
            self._popup_show_info("Error", "No belt links found in table.", sound = "error")
            return

        self._clear_window()
        self._play_ui_sound("whoosh1")

        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color = "transparent")
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = "Create Loaded Belt Transfer",
        font = customtkinter.CTkFont(size = 24, weight = "bold")
        )
        title_label.pack(pady = 20)

        customtkinter.CTkLabel(
        main_frame,
        text = "Select a belt link type to create:",
        font = customtkinter.CTkFont(size = 14)
        ).pack(pady = 10)

        for belt in belt_links:
            belt_frame = customtkinter.CTkFrame(main_frame)
            belt_frame.pack(fill = "x", pady = 5, padx = 20)

            belt_info = f"{belt.get('name', 'Unknown')}\n"
            belt_info +=f"Caliber: {', '.join(belt.get('caliber', ['Unknown']))}\n"
            belt_info +=f"Belt Link: {belt.get('beltlink')}"

            customtkinter.CTkLabel(
            belt_frame,
            text = belt_info,
            font = customtkinter.CTkFont(size = 12),
            justify = "left"
            ).pack(side = "left", padx = 10, pady = 10)

            def create_belt_transfer(b = belt):
                self._create_loaded_belt_dialog(b, table_data)

            self._create_sound_button(
            belt_frame,
            text = "Create Transfer",
            command = create_belt_transfer,
            width = 150
            ).pack(side = "right", padx = 10, pady = 5)

        back_button = self._create_sound_button(
        main_frame,
        text = "Back to DM Tools",
        command = lambda:[self._clear_window(), self._open_dm_tools()],
        width = 300,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        back_button.pack(pady = 20)

    def _create_loaded_belt_dialog(self, belt_link, table_data):

        dialog = customtkinter.CTkToplevel(self.root)
        dialog.title(f"Create: {belt_link.get('name', 'Belt')}")
        dialog.transient(self.root)
        self._center_popup_on_window(dialog, 600, 700)
        dialog.grab_set()

        customtkinter.CTkLabel(
        dialog,
        text = f"Configure {belt_link.get('name', 'Belt')}",
        font = customtkinter.CTkFont(size = 16, weight = "bold")
        ).pack(pady = 10)

        count_frame = customtkinter.CTkFrame(dialog)
        count_frame.pack(fill = "x", padx = 20, pady = 10)

        customtkinter.CTkLabel(
        count_frame,
        text = "Number of rounds in belt:",
        font = customtkinter.CTkFont(size = 12)
        ).pack(side = "left", padx = 10)

        count_var = customtkinter.StringVar(value = "100")
        count_entry = customtkinter.CTkEntry(count_frame, textvariable = count_var, width = 100)
        count_entry.pack(side = "right", padx = 10)

        customtkinter.CTkLabel(
        dialog,
        text = "Select ammunition type:",
        font = customtkinter.CTkFont(size = 14, weight = "bold")
        ).pack(pady = 10)

        belt_calibers = belt_link.get("caliber", [])
        ammunition_table = table_data.get("tables", {}).get("ammunition", [])

        compatible_ammo =[
        ammo for ammo in ammunition_table
        if ammo.get("caliber")in belt_calibers
        ]

        if not compatible_ammo:
            customtkinter.CTkLabel(
            dialog,
            text = "No compatible ammunition found!",
            font = customtkinter.CTkFont(size = 12),
            text_color = "red"
            ).pack(pady = 20)

            self._create_sound_button(
            dialog,
            text = "Close",
            command = dialog.destroy,
            fg_color = "#8B0000"
            ).pack(pady = 10)
            return

        selected_ammo = customtkinter.StringVar(value = compatible_ammo[0].get("name", ""))
        selected_variant = customtkinter.StringVar(value = "")

        ammo_scroll = customtkinter.CTkScrollableFrame(dialog, height = 250)
        ammo_scroll.pack(fill = "x", padx = 20, pady = 10)

        for ammo in compatible_ammo:
            ammo_frame = customtkinter.CTkFrame(ammo_scroll)
            ammo_frame.pack(fill = "x", pady = 2)

            radio = customtkinter.CTkRadioButton(
            ammo_frame,
            text = ammo.get("name", "Unknown"),
            variable = selected_ammo,
            value = ammo.get("name", ""),
            font = customtkinter.CTkFont(size = 12)
            )
            radio.pack(anchor = "w", padx = 10, pady = 5)

            if ammo.get("variants"):
                variant_frame = customtkinter.CTkFrame(ammo_frame)
                variant_frame.pack(fill = "x", padx = 30)

                for variant in ammo["variants"]:
                    var_radio = customtkinter.CTkRadioButton(
                    variant_frame,
                    text = variant.get("name", "Unknown Variant"),
                    variable = selected_variant,
                    value = f"{ammo.get('name')}|{variant.get('name')}",
                    font = customtkinter.CTkFont(size = 11)
                    )
                    var_radio.pack(anchor = "w", padx = 10, pady = 2)

        def create_transfer():
            try:
                round_count = int(count_var.get())

                if round_count <=0:
                    raise ValueError("Invalid round count")

                ammo_obj = None
                for ammo in compatible_ammo:
                    if ammo.get("name")==selected_ammo.get():
                        ammo_obj = ammo
                        break

                if not ammo_obj:
                    raise ValueError("No ammunition selected")

                belt_copy = json.loads(json.dumps(belt_link))
                belt_copy["rounds"]=[]

                variant_info = None
                if selected_variant.get():
                    variant_parts = selected_variant.get().split("|")
                    if len(variant_parts)==2:
                        for var in ammo_obj.get("variants", []):
                            if var.get("name")==variant_parts[1]:
                                variant_info = var
                                break

                if not variant_info:
                    variants = ammo_obj.get("variants", [])
                    if variants:
                        variant_info = variants[0]

                for i in range(round_count):
                    caliber = ammo_obj.get("caliber")
                    if isinstance(caliber, list):
                        caliber = caliber[0]if caliber else "Unknown"

                    round_data = {
                    "caliber":caliber,
                    "name":f"{caliber} | {variant_info.get('name', 'FMJ')if variant_info else 'FMJ'}",
                    "variant":variant_info.get("name", "FMJ")if variant_info else "FMJ"
                    }

                    if variant_info:
                        if variant_info.get("type"):
                            round_data["type"]= variant_info.get("type")
                        if variant_info.get("pen"):
                            round_data["pen"]= variant_info.get("pen")
                        if variant_info.get("tip"):
                            round_data["tip"]= variant_info.get("tip")
                        if variant_info.get("modifiers"):
                            round_data["modifiers"]= variant_info.get("modifiers")

                    belt_copy["rounds"].append(round_data)

                self._save_belt_transfer(belt_copy, round_count)
                dialog.destroy()

            except ValueError as e:
                self._popup_show_info("Error", f"Invalid input: {e}", sound = "error")

        self._create_sound_button(
        dialog,
        text = "Create Transfer",
        command = create_transfer,
        width = 200
        ).pack(pady = 10)

        self._create_sound_button(
        dialog,
        text = "Cancel",
        command = dialog.destroy,
        fg_color = "#8B0000",
        width = 200
        ).pack(pady = 5)
