"""CombatmodeMixin — App methods for the "combatmode" feature area."""
from app.foundation import *
import logging


class CombatmodeMixin:

    def _open_combat_mode_tool(self):

        logging.info("Combat Mode opened")
        logging.debug("currentsave=%s debugmode=%s", self.currentsave, global_variables.get("debugmode", {}).get("value"))

        if self.currentsave is None:
            self._popup_show_info("Error", "No character loaded.Please load a character first.", sound = "error")
            return

        try:
            save_path = os.path.join(saves_folder or "saves", self.currentsave or "")
            if not save_path.endswith('.sldsv'):
                save_path +='.sldsv'
            save_data = self._load_file((self.currentsave or "")+".sldsv")
            if save_data is None:
                logging.error("Failed to load save for combat mode")
                self._popup_show_info("Error", "Failed to load save.", sound = "error")
                return
        except Exception as e:
            logging.error(f"Failed to load save: {e}")
            self._popup_show_info("Error", f"Failed to load save: {e}", sound = "error")
            return

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

        if "combat_state"not in save_data:
            save_data["combat_state"]= {
            "current_weapon_index":0,
            "barrel_temperatures":{},
            "barrel_cleanliness":{},
            "ambient_temperature":70,
            "weapon_last_used":{}
            }

        combat_state = save_data["combat_state"]

        equipped_weapons = self._get_equipped_weapons(save_data, table_data)

        if not equipped_weapons:
            self._popup_show_info("Error", "No weapons equipped.Please equip a weapon first.", sound = "error")
            return

        if combat_state["current_weapon_index"]>=len(equipped_weapons):
            combat_state["current_weapon_index"]= 0

        now_ts = time.time()
        ambient = combat_state.get("ambient_temperature", 70)

        for wpn in equipped_weapons:
            weapon_id = str(wpn["item"].get("id"))
            temp_map = combat_state.setdefault("barrel_temperatures", {})
            last_used_map = combat_state.setdefault("weapon_last_used", {})

            current_temp = temp_map.get(weapon_id, ambient)
            last_used = last_used_map.get(weapon_id)

            if last_used is None and weapon_id in temp_map:
                assumed_interval = combat_state.get("temp_poll_interval", 15)
                last_used = now_ts -float(assumed_interval)

            elapsed = max(0.0, now_ts -last_used)if last_used is not None else 0.0

            if elapsed >0 and current_temp !=ambient:

                default_k = math.log(2.0)/300.0
                magic_k = math.log(2.0)/600.0
                magicsys_local = str(wpn.get("magicsoundsystem")or "").lower()
                is_magic_local =(str(wpn.get("type")or "").lower()=="magic")or(magicsys_local in("hg", "at", "mg", "rf"))
                k = magic_k if is_magic_local else default_k
                try:
                    _ws = combat_state.get("weather", {})
                    _wt = _ws.get("weather", "clear") if isinstance(_ws, dict) else "clear"
                    if _wt in ("rain", "hard_rain", "thunderstorm", "thunder_hard_rain", "snowstorm", "thundersnow") and not combat_state.get("indoors"):
                        k *= 1.5
                except Exception:
                    logging.exception("Suppressed exception")
                new_temp = ambient +(current_temp -ambient)*math.exp(-k *elapsed)

                low = min(ambient, current_temp)
                high = max(ambient, current_temp)
                new_temp = min(max(new_temp, low), high)
                temp_map[weapon_id]= new_temp

                last_used_map[weapon_id]= now_ts
                logging.debug(
                "Weapon %s cooling: was %.1f°F, now %.1f°F after %.1f seconds",
                weapon_id,
                current_temp,
                new_temp,
                elapsed,
                )

        logging.info(
        "Combat UI init: %s weapons, current index=%s(%s)",
        len(equipped_weapons),
        combat_state["current_weapon_index"],
        equipped_weapons[combat_state["current_weapon_index"]]["item"].get("name", "Unknown")if equipped_weapons else "n/a"
        )

        self._init_combat_session_stats(save_data)

        try:
            _update_all_weapon_batteries(equipped_weapons, now_ts)
            self._save_combat_state(save_data)
        except Exception:
            logging.exception("Suppressed exception")

        def _get_equipped_watches(save_data, table_data):

            import copy

            watches = []
            seen = set()

            def _resolve_table_item(tid):
                try:
                    tables = table_data.get("tables", {}) if isinstance(table_data, dict) else {}
                    for arr in tables.values():
                        if isinstance(arr, list):
                            for it in arr:
                                if isinstance(it, dict) and it.get("id") == tid:
                                    return copy.deepcopy(it)
                except Exception:
                    logging.exception("Suppressed exception")
                return None

            def _add_watch(item, slot_name):
                try:
                    if not isinstance(item, dict) or not item.get("watch"):
                        return
                    watch_id = item.get("id")
                    key = (watch_id, slot_name)
                    if key in seen:
                        return
                    seen.add(key)
                    watches.append({
                        "item": item,
                        "slot": slot_name,
                        "display_name": item.get("name", "Unknown Watch"),
                    })
                except Exception:
                    logging.exception("Suppressed exception")

            try:
                for slot_name, item in (save_data.get("equipment", {}) or {}).items():
                    if isinstance(item, dict):
                        _add_watch(item, slot_name)
                    elif isinstance(item, int) or (isinstance(item, str) and item.isdigit()):
                        resolved = _resolve_table_item(int(item))
                        if resolved:
                            _add_watch(resolved, slot_name)

                    if not isinstance(item, dict):
                        continue

                    for subslot in (item.get("subslots") or []):
                        if not isinstance(subslot, dict):
                            continue
                        cur = subslot.get("current")
                        resolved = cur if isinstance(cur, dict) else None
                        if resolved is None and (isinstance(cur, int) or (isinstance(cur, str) and str(cur).isdigit())):
                            resolved = _resolve_table_item(int(cur))
                        if resolved:
                            _add_watch(resolved, f"{slot_name} -> {subslot.get('name', 'Subslot')}")
            except Exception:
                logging.exception("Suppressed exception")

            return watches

        def _watch_weather_icon_code(weather_name):
            mapping = {
                "clear": "1",
                "sun": "1",
                "cloud": "2",
                "cloudy": "2",
                "rain": "3",
                "hard_rain": "4",
                "snow": "5",
                "snowstorm": "5",
                "thunder_rain": "6",
                "thunder_hard_rain": "7",
                "thunderstorm": "6",
                "thundersnow": "6",
                "thunder": "8",
                "sun_and_cloud": "9",
            }
            return mapping.get(str(weather_name or "").strip().lower(), ":")

        def _watch_temperature_text(temp_f):
            try:
                temp_f = float(temp_f)
            except Exception:
                return f"{temp_f}°F"
            if appearance_settings.get("units") == "metric":
                temp_c = (temp_f - 32) * 5 / 9
                temp_ci = int(round(temp_c))
                if temp_ci >= 0:
                    return f"{temp_ci:03d}°C"
                return f"-{abs(temp_ci):02d}°C"
            temp_fi = int(round(temp_f))
            if temp_fi >= 0:
                return f"{temp_fi:03d}°F"
            return f"-{abs(temp_fi):02d}°F"

        def _watch_temperature_ghost_text():
            return "8888"

        def _watch_time_text(now_dt, show_seconds, use_24h = True):
            if use_24h:
                return now_dt.strftime("%H:%M:%S" if show_seconds else "%H:%M")
            return now_dt.strftime("%I:%M:%S" if show_seconds else "%I:%M")


        import pytz
        CST = pytz.timezone('US/Central')
        weather_state = {"weather": "clear", "wind_severity": 0, "temperature_f": combat_state.get("ambient_temperature", 70)}
        try:
            weather_path = os.path.join('remotedata', 'weather.json')
            if os.path.exists(weather_path):
                with open(weather_path, 'r', encoding = 'utf-8') as f:
                    weather_data = json.load(f)
                forecast = weather_data.get("forecast")
                if isinstance(forecast, dict):
                    now_dt = datetime.now(CST)
                    if now_dt.hour < 12:
                        effective_date = (now_dt - timedelta(days = 1)).strftime("%Y-%m-%d")
                    else:
                        effective_date = now_dt.strftime("%Y-%m-%d")
                    day_weather = forecast.get(effective_date) or forecast.get("default") or {}
                    if isinstance(day_weather, dict):
                        hourly = day_weather.get("hourly")
                        if isinstance(hourly, dict):
                            hour_key = f"{now_dt.hour:02d}"
                            hour_weather = hourly.get(hour_key)
                            if isinstance(hour_weather, dict):
                                merged_weather = dict(day_weather)
                                merged_weather.update(hour_weather)
                                day_weather = merged_weather
                                logging.info("Weather forecast: effective_date=%s hour=%s CST (actual=%s %02d:%02d CST)", effective_date, hour_key, now_dt.strftime("%Y-%m-%d"), now_dt.hour, now_dt.minute)
                            else:
                                logging.info("Weather forecast: effective_date=%s (no hourly match for %s; actual=%s %02d:%02d CST)", effective_date, hour_key, now_dt.strftime("%Y-%m-%d"), now_dt.hour, now_dt.minute)
                        else:
                            logging.info("Weather forecast: effective_date=%s (hourly unavailable; actual=%s %02d:%02d CST)", effective_date, now_dt.strftime("%Y-%m-%d"), now_dt.hour, now_dt.minute)
                    else:
                        logging.info("Weather forecast: effective_date=%s (invalid day payload; actual=%s %02d:%02d CST)", effective_date, now_dt.strftime("%Y-%m-%d"), now_dt.hour, now_dt.minute)
                else:
                    day_weather = weather_data

                w_type = str(day_weather.get("weather", "clear")).lower().strip()
                w_sev = int(day_weather.get("wind_severity", 0))
                w_temp = day_weather.get("temperature_f")
                if w_temp is not None:
                    combat_state["ambient_temperature"] = float(w_temp)
                valid_weather = ("clear", "sun_and_cloud", "cloudy", "rain", "hard_rain", "thunderstorm", "thunder_hard_rain", "thunder", "snowstorm", "thundersnow")
                if w_type not in valid_weather:
                    w_type = "clear"
                if w_type in ("snowstorm", "thundersnow") and combat_state.get("ambient_temperature", 70) >= 30:
                    w_type = "clear"
                    logging.warning("Weather %s requires temperature < 30°F, defaulting to clear", day_weather.get("weather"))
                w_sev = max(0, min(3, w_sev))
                weather_state = {"weather": w_type, "wind_severity": w_sev, "temperature_f": combat_state.get("ambient_temperature", 70)}
                logging.info("Weather loaded: %s, wind_severity=%d, temp=%.1f°F", w_type, w_sev, weather_state["temperature_f"])
        except Exception:
            logging.exception("Failed to load weather data")

        combat_state["weather"] = weather_state
        combat_state.setdefault("indoors", False)

        weather_sound_state = {"channel": None, "sound": None, "thunder_after_id": None}

        def _start_weather_sounds():
            if not appearance_settings.get("weather_audio_effects", True):
                return
            w = weather_state.get("weather", "clear")
            loop_map = {
                "rain": "rain_loop.ogg",
                "hard_rain": "rain_loop.ogg",
                "thunderstorm": "rain_loop.ogg",
                "thunder_hard_rain": "rain_loop.ogg",
                "snowstorm": "snowstorm_loop.ogg",
                "thundersnow": "snowstorm_loop.ogg"
            }
            loop_file = loop_map.get(w)
            wind_sev = weather_state.get("wind_severity", 0)
            if not loop_file and wind_sev > 0:
                loop_file = "wind_loop.ogg"
            if not loop_file:
                return
            try:
                loop_path = os.path.join("sounds", "ambience", loop_file)
                if os.path.exists(loop_path):
                    snd = pygame.mixer.Sound(loop_path)
                    vol = appearance_settings.get("sound_volume", 100) / 100.0
                    vol *= 0.5
                    snd.set_volume(min(1.0, max(0.0, vol)))
                    try:
                        ch = pygame.mixer.Channel(pygame.mixer.get_num_channels() - 1)
                    except Exception:
                        ch = pygame.mixer.find_channel(True)
                    if ch:
                        ch.play(snd, loops = -1)
                        weather_sound_state["channel"] = ch # type: ignore
                        weather_sound_state["sound"] = snd # type: ignore
                        self._weather_ambient_channel = ch
                        logging.debug("Weather ambient sound started: %s", loop_file)
            except Exception:
                logging.exception("Failed to start weather ambient sound")

        def _schedule_thunder():
            if not appearance_settings.get("weather_audio_effects", True):
                return
            w = weather_state.get("weather", "clear")
            if w not in ("thunderstorm", "thunder_hard_rain", "thundersnow", "thunder"):
                return

            def _play_thunder():
                try:
                    if appearance_settings.get("weather_visual_effects", True):
                        _weather_lightning_flash()
                    delay_ms = random.randint(200, 1500)
                    self.root.after(delay_ms, _play_thunder_sound)
                except Exception:
                    logging.exception("Failed in thunder sequence")
                interval = random.randint(15000, 45000)
                weather_sound_state["thunder_after_id"] = self.root.after(interval, _play_thunder) # type: ignore

            def _play_thunder_sound():
                try:
                    idx = random.randint(0, 4)
                    thunder_path = os.path.join("sounds", "ambience", f"thunder{idx}.ogg")
                    if os.path.exists(thunder_path):
                        snd = pygame.mixer.Sound(thunder_path)
                        vol = appearance_settings.get("sound_volume", 100) / 100.0 * 0.7
                        snd.set_volume(min(1.0, max(0.0, vol)))
                        ch = pygame.mixer.find_channel()
                        if ch:
                            ch.play(snd)
                except Exception:
                    logging.exception("Failed to play thunder sound")

            interval = random.randint(5000, 20000)
            weather_sound_state["thunder_after_id"] = self.root.after(interval, _play_thunder) # type: ignore

        def _weather_lightning_flash():
            try:
                ov = customtkinter.CTkToplevel(self.root)
                ov.overrideredirect(True)
                vx, vy, vw, vh = self._get_virtual_screen_rect()
                ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
                try:
                    ov.attributes('-topmost', True)
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    ov.attributes('-alpha', 0.0)
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    ov.configure(fg_color = 'white')
                except Exception:
                    try:
                        ov.configure(bg = 'white')
                    except Exception:
                        logging.exception("Suppressed exception")

                flicker_count = random.randint(2, 4)
                flicker_seq = []
                for i in range(flicker_count):
                    bright = random.uniform(0.5, 0.8) if i == 0 else random.uniform(0.25, 0.6)
                    hold = random.randint(40, 100) if i == 0 else random.randint(20, 60)
                    gap = random.randint(30, 80)
                    flicker_seq.append((bright, hold, gap))

                def _run_flicker(idx = 0):
                    try:
                        if not getattr(ov, 'winfo_exists', lambda: False)():
                            return
                        if idx >= len(flicker_seq):
                            _final_fade(0, 50)
                            return
                        bright, hold, gap = flicker_seq[idx]
                        try:
                            ov.attributes('-alpha', bright)
                        except Exception:
                            logging.exception("Suppressed exception")
                        def _after_hold():
                            try:
                                if not getattr(ov, 'winfo_exists', lambda: False)():
                                    return
                                try:
                                    ov.attributes('-alpha', 0.0)
                                except Exception:
                                    logging.exception("Suppressed exception")
                                ov.after(gap, lambda: _run_flicker(idx + 1))
                            except Exception:
                                try:
                                    ov.destroy()
                                except Exception:
                                    logging.exception("Suppressed exception")
                        ov.after(hold, _after_hold)
                    except Exception:
                        try:
                            ov.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")

                def _final_fade(step = 0, total_steps = 50):
                    try:
                        if not getattr(ov, 'winfo_exists', lambda: False)():
                            return
                        t = float(step) / float(total_steps)
                        smooth = t * t * (3.0 - 2.0 * t)
                        alpha = 0.35 * (1.0 - smooth)
                        try:
                            ov.attributes('-alpha', max(0.0, alpha))
                        except Exception:
                            logging.exception("Suppressed exception")
                        if step < total_steps:
                            ov.after(8, lambda: _final_fade(step + 1, total_steps))
                        else:
                            try:
                                ov.destroy()
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        try:
                            ov.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")

                ov.after(10, lambda: _run_flicker(0))
            except Exception:
                logging.exception("Failed to create lightning flash")

        _start_weather_sounds()
        _schedule_thunder()

        main_frame = customtkinter.CTkScrollableFrame(self.root, fg_color = "transparent")
        try:
            self.root.grid_rowconfigure(0, weight = 1)
            self.root.grid_columnconfigure(0, weight = 1)
        except Exception:
            logging.exception("Suppressed exception")
        main_frame.grid(row = 0, column = 0, sticky = "nsew", padx = 20, pady = 20)

        def _show_combat_stats():

            try:
                parts =[]

                sd_stats = save_data.get("stats", {})or {}
                parts.append("Player base stats:")
                if isinstance(sd_stats, dict)and sd_stats:
                    for k, v in sd_stats.items():
                        parts.append(f" {k}: {v}")
                else:
                    parts.append("(no base stats)")

                agg = {}
                parts.append("")
                parts.append("Weapon modifiers(per-weapon):")
                for idx, entry in enumerate(equipped_weapons):
                    w = entry.get("item")if isinstance(entry, dict)else None
                    name = w.get("name", f"weapon_{idx}")if isinstance(w, dict)else str(entry)
                    mods = {}
                    if isinstance(w, dict):
                        mods = w.get("_active_modifiers", {})or {}
                    parts.append(f" {name}:")
                    stats_mods = mods.get("stats", {})if isinstance(mods, dict)else {}
                    if stats_mods:
                        for sk, sv in stats_mods.items():
                            parts.append(f" {sk}: {sv}")
                            try:
                                agg[sk]= agg.get(sk, 0)+(int(sv)if isinstance(sv, (int, float))else 0)
                            except Exception:
                                logging.exception("Suppressed exception")
                    else:
                        parts.append("(no modifiers)")

                parts.append("")
                parts.append("Aggregated weapon modifiers:")

                try:
                    stat_clamp = 20
                    try:
                        tbl_path = get_current_table_path()
                        if tbl_path and os.path.exists(tbl_path):
                            with open(tbl_path, 'r', encoding = 'utf-8-sig')as tf:
                                td = json.load(tf)
                                stat_clamp = td.get("additional_settings", {}).get("stat_clamp", stat_clamp)
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    stat_clamp = 20

                if agg:
                    for k, v in agg.items():
                        try:
                            num = int(v)if isinstance(v, (int, float))else int(float(v))
                        except Exception:
                            try:
                                num = int(v)
                            except Exception:
                                num = 0

                        num = max(num, -20)
                        num = min(num, int(stat_clamp or 20))
                        parts.append(f" {k}: {num}")
                else:
                    parts.append("(none)")

                try:
                    equip_agg = {}
                    active_sets =[]
                    applied_set_keys = set()
                    equipment = save_data.get("equipment", {})if isinstance(save_data, dict)else {}
                    if isinstance(equipment, dict):

                        for slot_name, equipped_item in equipment.items():
                            if not equipped_item or not isinstance(equipped_item, dict):
                                continue
                            mods = equipped_item.get("modifiers")or {}
                            if isinstance(mods, dict):
                                stats = mods.get("stats")or {}
                                if isinstance(stats, dict):
                                    for sk, sv in stats.items():
                                        try:
                                            equip_agg[sk]= equip_agg.get(sk, 0)+(int(sv)if isinstance(sv, (int, float))else 0)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                            istats = equipped_item.get("stats")or {}
                            if isinstance(istats, dict):
                                for sk, sv in istats.items():
                                    try:
                                        equip_agg[sk]= equip_agg.get(sk, 0)+(int(sv)if isinstance(sv, (int, float))else 0)
                                    except Exception:
                                        logging.exception("Suppressed exception")

                        for slot_name, equipped_item in equipment.items():
                            try:
                                if not equipped_item or not isinstance(equipped_item, dict):
                                    continue
                                sb = equipped_item.get("set_bonus")or {}
                                if not sb or not isinstance(sb, dict):
                                    continue
                                requires = sb.get("requires")or[]
                                if not isinstance(requires, list)or not requires:
                                    continue

                                try:
                                    req_pairs =[]
                                    for req in requires:
                                        rslot = req.get("slot")
                                        rid = req.get("id")
                                        req_pairs.append((str(rslot), int(rid)if rid is not None and isinstance(rid, (int, float, str))and str(rid).isdigit()else rid))
                                    req_key = tuple(sorted(req_pairs))
                                except Exception:
                                    req_key = None
                                if req_key is None:
                                    continue
                                if req_key in applied_set_keys:
                                    continue

                                ok = True
                                member_names =[]
                                for req in requires:
                                    try:
                                        rslot = req.get("slot")
                                        rid = req.get("id")
                                        cur = equipment.get(rslot)
                                        if not cur or not isinstance(cur, dict)or cur.get("id")!=rid:
                                            ok = False
                                            break
                                        member_names.append(cur.get("name", f"{rslot}"))
                                    except Exception:
                                        ok = False
                                        break
                                if not ok:
                                    continue

                                sstats = sb.get("stats")or {}
                                if isinstance(sstats, dict):
                                    for sk, sv in sstats.items():
                                        try:
                                            equip_agg[sk]= equip_agg.get(sk, 0)+(int(sv)if isinstance(sv, (int, float))else 0)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                applied_set_keys.add(req_key)
                                set_name = sb.get("name")or equipped_item.get("name")or "Set Bonus"
                                active_sets.append({"name":set_name, "members":member_names, "stats":sstats})
                            except Exception:
                                logging.exception("Suppressed exception")

                    parts.append("")
                    parts.append("Equipment modifiers / Set bonuses:")
                    try:
                        clamp_val = None
                        tbl_path = get_current_table_path()
                        if tbl_path and os.path.exists(tbl_path):
                            with open(tbl_path, 'r', encoding = 'utf-8-sig')as tf:
                                td = json.load(tf)
                                clamp_val = td.get('additional_settings', {}).get('bonus_clamp')
                    except Exception:
                        clamp_val = None

                    if equip_agg:
                        for k, v in equip_agg.items():
                            try:
                                num = int(v)if isinstance(v, (int, float))else int(float(v))
                            except Exception:
                                try:
                                    num = int(v)
                                except Exception:
                                    num = 0
                            if k.lower()=='aim'and clamp_val is not None:
                                try:
                                    cnum = int(float(clamp_val))
                                    num = min(num, cnum)
                                except Exception:
                                    logging.exception("Suppressed exception")
                            parts.append(f" {k}: {num}")
                    else:
                        parts.append("(none)")

                    if active_sets:
                        parts.append("")
                        parts.append("Active set bonuses:")
                        for s in active_sets:
                            try:
                                stats_text =[]
                                if isinstance(s.get('stats'), dict):
                                    for sk, sv in s.get('stats', {}).items():
                                        stats_text.append(f"+{sv} {sk}")
                                members_text = ", ".join(s.get('members', [])or[])
                                parts.append(f" {s.get('name')}: {'; '.join(stats_text)}({members_text})")
                            except Exception:
                                logging.exception("Suppressed exception")
                except Exception as e:
                    logging.debug("Failed aggregating equipment modifiers for combat stats: %s", e)

                try:
                    w_weather = combat_state.get("weather", {})
                    w_type = w_weather.get("weather", "clear") if isinstance(w_weather, dict) else "clear"
                    indoors = bool(combat_state.get("indoors"))
                    parts.append("")
                    parts.append("Weather modifiers:")
                    weather_names = {"sun_and_cloud": "Partly Cloudy", "cloudy": "Cloudy", "rain": "Rain", "hard_rain": "Hard Rain", "thunderstorm": "Thunderstorm", "thunder_hard_rain": "Severe Thunderstorm", "thunder": "Thunder", "snowstorm": "Snowstorm", "thundersnow": "Thundersnow"}
                    w_sev = w_weather.get("wind_severity", 0) if isinstance(w_weather, dict) else 0
                    if indoors:
                        weather_label = "Clear" if w_type == "clear" else weather_names.get(w_type, w_type.title())
                        parts.append(f"  Indoors — sheltered ({weather_label} outside, no weather/wind effects)")
                    elif w_type == "clear":
                        parts.append("  (none — clear weather)")
                        if w_sev > 0:
                            aim_mod = -max(1, min(3, w_sev))
                            parts.append(f"  Wind: severity {w_sev}, Aim: {aim_mod}")
                    else:
                        parts.append(f"  Weather: {weather_names.get(w_type, w_type.title())}")
                        weather_aim_map = {"rain": -1, "hard_rain": -2, "thunderstorm": -1, "thunder_hard_rain": -2, "thunder": -1, "snowstorm": -2, "thundersnow": -2}
                        if w_type in weather_aim_map:
                            parts.append(f"  Aim: {weather_aim_map[w_type]}")
                        if w_type in ("rain", "hard_rain", "thunderstorm", "thunder_hard_rain", "snowstorm", "thundersnow"):
                            parts.append("  Barrel cooling: 1.5x")
                        if w_sev > 0:
                            aim_mod = -max(1, min(3, w_sev))
                            parts.append(f"  Wind: severity {w_sev}, Aim: {aim_mod}")
                except Exception:
                    logging.exception("Suppressed exception")

                def _build_popup_text():
                    live_parts = list(parts)
                    try:
                        temp_lines = self._get_temporary_effect_display_lines(save_data)
                        if temp_lines:
                            live_parts.append("")
                            live_parts.append("Temporary effects:")
                            live_parts.extend(temp_lines)
                    except Exception:
                        logging.exception("Suppressed exception")
                    return "\n".join(live_parts)

                popup_text = _build_popup_text()
            except Exception as e:
                logging.exception("Failed to build combat stats: %s", e)
                popup_text = f"Error building stats: {e}"
            try:
                popup = customtkinter.CTkToplevel(self.root)
                popup.title("Combat Stats")
                popup.transient(self.root)
                popup.geometry("620x560")

                frame = customtkinter.CTkFrame(popup)
                frame.pack(fill = 'both', expand = True, padx = 12, pady = 12)

                title_lbl = customtkinter.CTkLabel(frame, text = "Combat Stats", font = customtkinter.CTkFont(size = 20, weight = 'bold'))
                title_lbl.pack(pady =(4, 10))

                text_box = customtkinter.CTkTextbox(frame, wrap = 'word', font = customtkinter.CTkFont(family = 'Consolas', size = 12))
                text_box.pack(fill = 'both', expand = True, padx = 4, pady = 4)
                text_box.insert('1.0', popup_text)
                text_box.configure(state = 'disabled')

                button_row = customtkinter.CTkFrame(frame, fg_color = 'transparent')
                button_row.pack(fill = 'x', pady =(8, 0))
                close_btn = customtkinter.CTkButton(button_row, text = 'Close', width = 120, command = popup.destroy)
                close_btn.pack(side = 'right')

                _stats_timer = {'job': None}

                def _refresh_stats_popup():
                    if not popup.winfo_exists():
                        return
                    try:
                        live_text = _build_popup_text()
                        text_box.configure(state = 'normal')
                        text_box.delete('1.0', 'end')
                        text_box.insert('1.0', live_text)
                        text_box.configure(state = 'disabled')
                        _stats_timer['job'] = popup.after(1000, _refresh_stats_popup)
                    except Exception:
                        _stats_timer['job'] = None

                def _close_stats_popup():
                    job = _stats_timer.get('job')
                    if job:
                        try:
                            popup.after_cancel(job)
                        except Exception:
                            logging.exception("Suppressed exception")
                    try:
                        popup.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")

                close_btn.configure(command = _close_stats_popup)
                popup.protocol('WM_DELETE_WINDOW', _close_stats_popup)
                self._center_popup_on_window(popup, 620, 560)
                popup.grab_set()
                popup.lift()
                self._safe_focus(popup)
                if self._get_active_temporary_effects(save_data):
                    _refresh_stats_popup()
            except Exception:
                try:

                    from tkinter import messagebox as _mb
                    _mb.showinfo("Combat Stats", popup_text)
                except Exception:
                    logging.error("Unable to display combat stats popup")

        weapon_switch_outer = customtkinter.CTkFrame(main_frame)
        weapon_switch_outer.pack(fill = "x", pady =(0, 20))

        weapon_switch_frame = customtkinter.CTkScrollableFrame(weapon_switch_outer, orientation = "horizontal", height = 60, fg_color = "transparent")
        weapon_switch_frame.pack(fill = "x", expand = True)

        def refresh_weapon_display():

            self._save_combat_state(save_data)
            try:
                _update_nvg_button()
            except Exception:
                logging.exception("Suppressed exception")
            self._open_combat_mode_tool()

        def _container_type_from_entry(entry):
            if entry is None:
                return "unknown"
            slot = entry.get("slot", "")
            if slot =="Hands":
                return "hands"
            if "->"in slot:
                parts =[p.strip()for p in slot.split(">")]
                top_slot = parts[0].rstrip(" -")
                parent = save_data.get("equipment", {}).get(top_slot)
                if parent and isinstance(parent, dict):
                    if parent.get("holster_sling"):
                        pname = parent.get("name", "").lower()
                        ptypes =[pt.lower()for pt in parent.get("weapon_types", [])if isinstance(pt, str)]
                        if "pistol"in ptypes or "holster"in pname:
                            return "holster"
                        return "sling"
                    for ss in parent.get("subslots", [])or[]:
                        cur = ss.get("current")
                        if isinstance(cur, dict)and cur.get("holster_sling"):
                            cname = cur.get("name", "").lower()
                            ctypes =[ct.lower()for ct in cur.get("weapon_types", [])if isinstance(ct, str)]
                            if "pistol"in ctypes or "holster"in cname:
                                return "holster"
                            return "sling"
                if top_slot =="waistband":
                    return "waistband"
                return "unknown"
            if slot =="waistband":
                return "waistband"
            parent = save_data.get("equipment", {}).get(slot)
            if parent and isinstance(parent, dict):
                pname = parent.get("name", "").lower()
                ptypes =[pt.lower()for pt in parent.get("weapon_types", [])if isinstance(pt, str)]
                if "pistol"in ptypes or "holster"in pname:
                    return "holster"
                if parent.get("holster_sling"):
                    return "sling"
            return "unknown"

        def select_previous():
            logging.debug(
            "Switching weapon: prev from %s/%s",
            combat_state["current_weapon_index"],
            len(equipped_weapons)
            )

            try:

                try:
                    combat_state.pop("active_underbarrel", None)
                except Exception:
                    logging.exception("Suppressed exception")
                cur_idx = combat_state.get("current_weapon_index", 0)

                new_idx =(combat_state["current_weapon_index"]-1)%len(equipped_weapons)

                try:
                    combat_state.pop("active_underbarrel", None)
                except Exception:
                    logging.exception("Suppressed exception")

                old_entry = equipped_weapons[cur_idx]if 0 <=cur_idx <len(equipped_weapons)else None
                new_entry = equipped_weapons[new_idx]

                old_type = _container_type_from_entry(old_entry)
                new_type = _container_type_from_entry(new_entry)

                if old_type in("sling", "waistband"):
                    self._safe_sound_play("", "sounds/firearms/universal/slingunequip.ogg", block = True)
                elif old_type =="holster":
                    self._safe_sound_play("", "sounds/firearms/universal/holsterunequip.ogg", block = True)

                combat_state["current_weapon_index"]= new_idx

                if new_type in("sling", "waistband"):
                    self._safe_sound_play("", "sounds/firearms/universal/slingequip.ogg", block = False)
                elif new_type =="holster":
                    self._safe_sound_play("", "sounds/firearms/universal/holsterequip.ogg", block = False)

                try:
                    self._play_firearm_sound(new_entry["item"], "equip")
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            refresh_weapon_display()

        def select_next():
            logging.debug(
            "Switching weapon: next from %s/%s",
            combat_state["current_weapon_index"],
            len(equipped_weapons)
            )

            try:
                cur_idx = combat_state.get("current_weapon_index", 0)

                new_idx =(combat_state["current_weapon_index"]+1)%len(equipped_weapons)

                old_entry = equipped_weapons[cur_idx]if 0 <=cur_idx <len(equipped_weapons)else None
                new_entry = equipped_weapons[new_idx]

                old_type = _container_type_from_entry(old_entry)
                new_type = _container_type_from_entry(new_entry)

                if old_type in("sling", "waistband"):
                    self._safe_sound_play("", "sounds/firearms/universal/slingunequip.ogg", block = True)
                elif old_type =="holster":
                    self._safe_sound_play("", "sounds/firearms/universal/holsterunequip.ogg", block = True)

                combat_state["current_weapon_index"]= new_idx

                if new_type in("sling", "waistband"):
                    self._safe_sound_play("", "sounds/firearms/universal/slingequip.ogg", block = False)
                elif new_type =="holster":
                    self._safe_sound_play("", "sounds/firearms/universal/holsterequip.ogg", block = False)

                try:
                    new_weapon = new_entry["item"]
                    self._play_firearm_sound(new_weapon, "equip")
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            refresh_weapon_display()

        def _barrel_swap_current():

            try:

                wpn = None
                try:
                    wpn = current_weapon_state.get('weapon')if isinstance(current_weapon_state, dict)else None
                except Exception:
                    wpn = None
                if not wpn:
                    wpn = current_weapon

                if not wpn or not isinstance(wpn, dict):
                    try:
                        self._popup_show_info('Barrel Swap', 'No weapon selected.', sound = 'error')
                    except Exception:
                        logging.exception("Suppressed exception")
                    return

                if not bool(wpn.get('barrel_swap', False)):
                    try:
                        self._popup_show_info('Barrel Swap', 'Selected weapon does not support barrel swapping.')
                    except Exception:
                        logging.exception("Suppressed exception")
                    return

                wid = str(wpn.get('id'))
                temp_map = combat_state.setdefault('barrel_temperatures', {})
                last_used_map = combat_state.setdefault('weapon_last_used', {})
                ambient_local = combat_state.get('ambient_temperature', 70)
                now_local = time.time()
                temp_map[wid]= ambient_local
                last_used_map[wid]= now_local
                try:
                    self._save_combat_state(save_data)
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    self._popup_show_info('Barrel Swap', f"Swapped barrel on {wpn.get('name', 'weapon')}.Temperature reset to {ambient_local}{temp_unit}")
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception as e:
                logging.exception('Barrel swap failed: %s', e)
                try:
                    self._popup_show_info('Error', f'Barrel swap failed: {e}', sound = 'error')
                except Exception:
                    logging.exception("Suppressed exception")

        def on_left_arrow(event):
            logging.debug("Left arrow pressed - switching weapon")
            select_previous()

        def on_right_arrow(event):
            logging.debug("Right arrow pressed - switching weapon")
            select_next()

        self.root.bind("<Left>", on_left_arrow)
        self.root.bind("<Right>", on_right_arrow)

        def on_b_key(event):
            try:
                logging.debug("'b' pressed - barrel swap requested")
                _barrel_swap_current()
            except Exception:
                logging.exception("Suppressed exception")

        def on_n_key(event):
            try:
                logging.debug("'n' pressed - NVG toggle requested")
                _toggle_nvg()
            except Exception:
                logging.exception("Suppressed exception")

        def on_a_key(event):
            try:
                logging.debug("'a' pressed - accessories menu requested")
                manage_attachments()
            except Exception:
                logging.exception("Suppressed exception")

        def on_p_key(event):
            try:
                _is_hc = bool((table_data.get('additional_settings') or {}).get('hardcore_mode'))
                if not _is_hc:
                    return
                logging.debug("'p' pressed - parts menu requested")
                _view_parts()
            except Exception:
                logging.exception("Suppressed exception")

        try:
            self.root.bind("b", on_b_key)
            self.root.bind("B", on_b_key)
            self.root.bind("n", on_n_key)
            self.root.bind("N", on_n_key)
            self.root.bind("a", on_a_key)
            self.root.bind("A", on_a_key)
            self.root.bind("p", on_p_key)
            self.root.bind("P", on_p_key)
        except Exception:
            logging.exception("Suppressed exception")

        self._create_sound_button(
        weapon_switch_frame,
        text = "← Previous Weapon",
        command = select_previous,
        width = 150,
        height = 40
        ).pack(side = "left", padx = 10, pady = 10)

        active_ub = combat_state.get("active_underbarrel")
        def _resolve_active_underbarrel_obj(active_entry):
            try:
                if not active_entry or not isinstance(active_entry, dict):
                    return None
                parent_index = active_entry.get("parent_index")
                aid = active_entry.get("accessory_id")
                aname = active_entry.get("accessory_name")
                try:
                    logging.info("Resolving active underbarrel: parent_index=%s accessory_id=%s accessory_name=%s current_weapon_index=%s equipped_count=%s",
                    parent_index, aid, aname, combat_state.get("current_weapon_index"), len(equipped_weapons))
                except Exception:
                    logging.exception("Suppressed exception")
                if parent_index is None:
                    return None
                if parent_index <0 or parent_index >=len(equipped_weapons):
                    return None
                parent_slot = equipped_weapons[parent_index].get("slot", "")
                try:
                    logging.info("Resolved parent_slot from equipped_weapons[%s]-> %s", parent_index, parent_slot)
                except Exception:
                    logging.exception("Suppressed exception")

                if "->"in parent_slot:
                    parent_slot = parent_slot.split("->")[0].strip()
                parent_item = save_data.get("equipment", {}).get(parent_slot)
                try:
                    logging.info("Parent item found: %s", bool(parent_item))
                except Exception:
                    logging.exception("Suppressed exception")
                if not parent_item or not isinstance(parent_item, dict):
                    try:
                        logging.info("No parent_item present for slot '%s'", parent_slot)
                    except Exception:
                        logging.exception("Suppressed exception")
                    return None

                for acc in parent_item.get("accessories", [])or[]:
                    cur = acc.get("current")
                    try:
                        logging.info("Checking parent accessory entry current=%s", repr(cur))
                    except Exception:
                        logging.exception("Suppressed exception")
                    if isinstance(cur, dict):
                        if aid is not None and cur.get("id")==aid:
                            try:
                                logging.info("Resolver matched accessory by id: %s", cur.get("id"))
                            except Exception:
                                logging.exception("Suppressed exception")
                            return cur
                        if aname and cur.get("name")==aname:
                            try:
                                logging.info("Resolver matched accessory by name: %s", cur.get("name"))
                            except Exception:
                                logging.exception("Suppressed exception")
                            return cur
                    else:

                        try:
                            if aid is not None and(isinstance(cur, int)or(isinstance(cur, str)and cur.isdigit()))and int(cur)==int(aid):

                                tables = table_data.get("tables", {})if isinstance(table_data, dict)else {}
                                for arr in tables.values():
                                    if isinstance(arr, list):
                                        for it in arr:
                                            if isinstance(it, dict)and it.get("id")==int(cur):
                                                return it
                        except Exception:
                            logging.exception("Suppressed exception")

                for sub in parent_item.get("subslots", [])or[]:
                    try:
                        logging.info("Checking parent subslot '%s' for accessories", sub.get("name"))
                    except Exception:
                        logging.exception("Suppressed exception")
                    sub_cur = sub.get("current")if isinstance(sub, dict)else None
                    if not sub_cur or not isinstance(sub_cur, dict):
                        continue
                    for acc in sub_cur.get("accessories", [])or[]:
                        cur = acc.get("current")
                        try:
                            logging.info("Checking subslot accessory entry current=%s", repr(cur))
                        except Exception:
                            logging.exception("Suppressed exception")
                        if isinstance(cur, dict):
                            if aid is not None and cur.get("id")==aid:
                                try:
                                    logging.info("Resolver matched accessory in subslot by id: %s", cur.get("id"))
                                except Exception:
                                    logging.exception("Suppressed exception")
                                return cur
                            if aname and cur.get("name")==aname:
                                try:
                                    logging.info("Resolver matched accessory in subslot by name: %s", cur.get("name"))
                                except Exception:
                                    logging.exception("Suppressed exception")
                                return cur
                        else:
                            try:
                                if aid is not None and(isinstance(cur, int)or(isinstance(cur, str)and cur.isdigit()))and int(cur)==int(aid):
                                    tables = table_data.get("tables", {})if isinstance(table_data, dict)else {}
                                    for arr in tables.values():
                                        if isinstance(arr, list):
                                            for it in arr:
                                                if isinstance(it, dict)and it.get("id")==int(cur):
                                                    return it
                            except Exception:
                                logging.exception("Suppressed exception")
                return None
            except Exception:
                return None

        try:
            logging.info("Active underbarrel raw state: %s", repr(active_ub))
        except Exception:
            logging.exception("Suppressed exception")
        resolved_active_acc = _resolve_active_underbarrel_obj(active_ub)
        try:
            if resolved_active_acc is not None and hasattr(resolved_active_acc, 'get')and callable(getattr(resolved_active_acc, 'get')):
                name = resolved_active_acc.get('name', resolved_active_acc)
            else:
                name = resolved_active_acc
            logging.info("Resolved active accessory from resolver: %s", name)
        except Exception:
            try:
                logging.info("Resolved active accessory: %s", str(resolved_active_acc))
            except Exception:
                logging.exception("Suppressed exception")
        if active_ub and isinstance(active_ub, dict)and active_ub.get("parent_index")==combat_state.get("current_weapon_index")and resolved_active_acc:

            current_weapon = resolved_active_acc
            current_weapon_data = {"item":current_weapon, "slot":f"{equipped_weapons[combat_state['current_weapon_index']]['slot']} -> underbarrel"}
        else:
            current_weapon_data = equipped_weapons[combat_state["current_weapon_index"]]
            current_weapon = current_weapon_data["item"]
        current_weapon_state = {
        "weapon":current_weapon,
        "ammo_label_ref":None,
        "original_ammo_text":"",
        "clean_label_ref":None,
        "mag_checked":False
        }
        weapon_name_label = customtkinter.CTkLabel(
        weapon_switch_frame,
        text = f"Selected: {current_weapon.get('name', 'Unknown')}",
        font = customtkinter.CTkFont(size = 14, weight = "bold")
        )
        weapon_name_label.pack(side = "left", padx = 20, pady = 10, expand = True)

        top_right_controls = customtkinter.CTkFrame(weapon_switch_frame, fg_color = "transparent")
        top_right_controls.pack(side = "right", padx = 10, pady = 10)

        self._create_sound_button(
        top_right_controls,
        text = "Next Weapon →",
        command = select_next,
        width = 150,
        height = 40
        ).pack(side = "left", padx =(0, 10))

        stats_btn = self._create_sound_button(top_right_controls, "Show Stats", _show_combat_stats, width = 140, height = 40)
        stats_btn.pack(side = "left")

        details_frame = customtkinter.CTkFrame(main_frame)
        details_frame.pack(fill = "both", expand = True, pady =(0, 20))

        try:
            self._apply_item_overrides(current_weapon)
        except Exception:
            logging.exception("Suppressed exception")
        self._display_weapon_details(details_frame, current_weapon, combat_state, save_data, table_data, current_weapon_state)

        watch_rows = []

        def _build_watch_panel(parent_frame):

            local_rows = []
            watch_items_local = _get_equipped_watches(save_data, table_data)

            # Resolution-based scaling: 1920px-wide screen == 1.0, clamped so the
            # watch stays usable on small/large displays.
            from tkinter import font as _tkfont
            try:
                _res_w = int(str(appearance_settings.get("resolution", "1920x1080")).split("x")[0])
            except Exception:
                _res_w = 1920
            watch_scale = max(0.8, min(2.0, _res_w / 1920.0))

            def _s(v):
                return max(1, int(round(v * watch_scale)))

            def _wf(size, weight = "normal"):
                return customtkinter.CTkFont(size = max(7, int(round(size * watch_scale))), weight = weight)

            def _seg_dims(sample_text, family, base_size, pad_x = 8, pad_y = 6):
                """Measure a 7-segment/icon string at the scaled size so the canvas
                hugs its content (kills dead space) and scales with resolution."""
                size = max(7, int(round(base_size * watch_scale)))
                try:
                    fo = _tkfont.Font(family = family, size = size)
                    tw = fo.measure(sample_text)
                    th = fo.metrics("linespace")
                except Exception:
                    tw = int(len(sample_text) * size * 0.7)
                    th = int(size * 1.4)
                return size, tw + _s(pad_x), th + _s(pad_y)

            watch_frame_local = customtkinter.CTkFrame(parent_frame, corner_radius = _s(6))
            watch_frame_local.place(relx = 0.0, y = _s(4), anchor = "nw", x = _s(4))
            watch_beep_mute_map = combat_state.get("watch_hourly_beep_muted")
            if not isinstance(watch_beep_mute_map, dict):
                watch_beep_mute_map = {}
            combat_state["watch_hourly_beep_muted"] = watch_beep_mute_map

            time_24h_var = customtkinter.BooleanVar(value = bool(combat_state.get("watch_time_24h", True)))

            title_row = customtkinter.CTkFrame(watch_frame_local, fg_color = "transparent")
            title_row.pack(fill = "x", pady =(_s(4), _s(2)), padx = _s(8))

            watch_title = customtkinter.CTkLabel(
                title_row,
                text = "Watches",
                font = _wf(12, "bold")
            )
            watch_title.pack(side = "left")

            def _toggle_watch_time_mode():
                next_mode = not bool(time_24h_var.get())
                time_24h_var.set(next_mode)
                combat_state["watch_time_24h"] = next_mode
                try:
                    update_watch_display()
                except Exception:
                    logging.exception("Suppressed exception")

            toggle_btn = self._create_sound_button(
                title_row,
                text = "24H" if time_24h_var.get() else "12H",
                command = _toggle_watch_time_mode,
                width = _s(58),
                height = _s(24),
                font = _wf(10, "bold")
            )
            toggle_btn.pack(side = "right")

            if not watch_items_local:
                customtkinter.CTkLabel(
                    watch_frame_local,
                    text = "No watches equipped.",
                    font = _wf(10),
                    text_color = "#A0A0A0"
                ).pack(pady =(0, _s(6)), padx = _s(8))
                return local_rows

            for watch_data in watch_items_local:
                watch_item = watch_data["item"]
                watch_type = str(watch_item.get("watch_type", "")).strip().lower()
                is_digital = watch_type == "digital"
                beep_key = f"{watch_item.get('id', 'watch')}|{watch_data.get('slot', '')}"

                row_bg = "#2E3821" if is_digital else "#1F2B35"
                row = customtkinter.CTkFrame(watch_frame_local, fg_color = row_bg)
                row.pack(fill = "x", padx = _s(6), pady = _s(3))

                customtkinter.CTkLabel(
                    row,
                    text = str(watch_data.get("display_name", "Watch")),
                    font = _wf(10, "bold")
                ).pack(anchor = "w", padx = _s(8), pady =(_s(4), 0))

                time_label = None
                time_canvas = None
                time_ghost_item = None
                time_live_item = None
                analog_canvas = None
                weather_icon_label = None
                weather_canvas = None
                weather_ghost_item = None
                weather_live_item = None
                weather_temp_label = None
                temp_canvas = None
                temp_ghost_item = None
                temp_live_item = None
                am_label = None
                pm_label = None
                beep_toggle_btn = None
                if is_digital:
                    def _toggle_watch_hourly_beep(_k = beep_key):
                        try:
                            _muted = bool(watch_beep_mute_map.get(_k, False))
                            watch_beep_mute_map[_k] = not _muted
                            combat_state["watch_hourly_beep_muted"] = watch_beep_mute_map
                            update_watch_display()
                        except Exception:
                            logging.exception("Suppressed exception")

                    info_row = customtkinter.CTkFrame(row, fg_color = "#313B21")
                    info_row.pack(anchor = "w", padx = _s(8), pady =(0, _s(6)))

                    # Each segment canvas is measured to hug its content so there is
                    # no dead space, and a shared row height keeps them aligned.
                    time_size, time_w, row_h = _seg_dims("88:88:88", "DSEG7 Modern-Regular", 22)
                    cy = row_h // 2

                    time_stack = customtkinter.CTkFrame(info_row, fg_color = "transparent", width = time_w, height = row_h)
                    time_stack.pack(side = "left", padx =(_s(6), _s(4)), pady = _s(4))
                    time_stack.pack_propagate(False)
                    time_canvas = customtkinter.CTkCanvas(time_stack, width = time_w, height = row_h, bg = "#313B21", highlightthickness = 0)
                    time_canvas.pack(fill = "both", expand = True)
                    time_ghost_item = time_canvas.create_text(time_w - _s(4), cy, text = "88:88:88", fill = "#4F6338", font = ("DSEG7 Modern-Regular", time_size), anchor = "e")
                    time_live_item = time_canvas.create_text(time_w - _s(4), cy, text = "00:00", fill = "#C7F089", font = ("DSEG7 Modern-Regular", time_size), anchor = "e")

                    ampm_w = _seg_dims("PM", None, 10, pad_x = 6)[1]
                    ampm_frame = customtkinter.CTkFrame(info_row, fg_color = "transparent", width = ampm_w, height = row_h)
                    ampm_frame.pack(side = "left", padx =(0, _s(4)), pady =(_s(1), 0))
                    ampm_frame.pack_propagate(False)
                    pm_label = customtkinter.CTkLabel(
                        ampm_frame,
                        text = "PM",
                        font = _wf(10),
                        text_color = "#4F6338"
                    )
                    pm_label.place(relx = 0.5, rely = 0.36, anchor = "center")
                    am_label = customtkinter.CTkLabel(
                        ampm_frame,
                        text = "AM",
                        font = _wf(10),
                        text_color = "#4F6338"
                    )
                    am_label.place(relx = 0.5, rely = 0.77, anchor = "center")

                    wx_size, wx_w, _wx_h = _seg_dims("8", "DSEG Weather", 28, pad_x = 10, pad_y = 8)
                    weather_stack = customtkinter.CTkFrame(info_row, fg_color = "transparent", width = wx_w, height = row_h)
                    weather_stack.pack(side = "left", padx =(_s(2), _s(6)), pady = _s(4))
                    weather_stack.pack_propagate(False)
                    weather_canvas = customtkinter.CTkCanvas(weather_stack, width = wx_w, height = row_h, bg = "#313B21", highlightthickness = 0)
                    weather_canvas.pack(fill = "both", expand = True)
                    weather_ghost_item = weather_canvas.create_text(wx_w // 2, cy, text = "0", fill = "#4F6338", font = ("DSEG Weather", wx_size), anchor = "center")
                    weather_live_item = weather_canvas.create_text(wx_w // 2, cy, text = _watch_weather_icon_code(weather_state.get("weather", "clear")), fill = "#C7F089", font = ("DSEG Weather", wx_size), anchor = "center")

                    # Temperature: size to the widest reading the formatter can emit
                    # ("888°F"/"-88°F") and the ghost ("8888") so nothing clips.
                    temp_size = max(7, int(round(22 * watch_scale)))
                    try:
                        _temp_fo = _tkfont.Font(family = "DSEG7 Modern-Regular", size = temp_size)
                        temp_text_w = max(_temp_fo.measure(_t) for _t in ("8888", "888°F", "-88°F"))
                    except Exception:
                        temp_text_w = int(5 * temp_size * 0.7)
                    temp_w = temp_text_w + _s(8)
                    temp_stack = customtkinter.CTkFrame(info_row, fg_color = "transparent", width = temp_w, height = row_h)
                    temp_stack.pack(side = "left", padx =(0, _s(6)), pady = _s(4))
                    temp_stack.pack_propagate(False)
                    temp_canvas = customtkinter.CTkCanvas(temp_stack, width = temp_w, height = row_h, bg = "#313B21", highlightthickness = 0)
                    temp_canvas.pack(fill = "both", expand = True)
                    temp_ghost_item = temp_canvas.create_text(temp_w - _s(4), cy, text = _watch_temperature_ghost_text(), fill = "#4F6338", font = ("DSEG7 Modern-Regular", temp_size), anchor = "e")
                    temp_live_item = temp_canvas.create_text(temp_w - _s(4), cy, text = _watch_temperature_text(weather_state.get("temperature_f", combat_state.get("ambient_temperature", 70))), fill = "#C7F089", font = ("DSEG7 Modern-Regular", temp_size), anchor = "e")

                    beep_toggle_btn = self._create_sound_button(
                        info_row,
                        text = "BEEP ON" if not bool(watch_beep_mute_map.get(beep_key, False)) else "BEEP OFF",
                        command = _toggle_watch_hourly_beep,
                        width = _s(84),
                        height = _s(28),
                        font = _wf(9, "bold")
                    )
                    beep_toggle_btn.pack(side = "left", padx =(0, _s(6)), pady = _s(4))
                else:
                    analog_sz = _s(92)
                    analog_canvas = customtkinter.CTkCanvas(
                        row,
                        width = analog_sz,
                        height = analog_sz,
                        bg = "#1F2B35",
                        highlightthickness = 0
                    )
                    analog_canvas.pack(padx = _s(8), pady =(0, _s(6)))

                local_rows.append({
                    "item": watch_item,
                    "watch_type": watch_type,
                    "seconds": bool(watch_item.get("seconds")),
                    "time_label": time_label,
                    "time_canvas": time_canvas if is_digital else None,
                    "time_ghost_item": time_ghost_item if is_digital else None,
                    "time_live_item": time_live_item if is_digital else None,
                    "analog_canvas": analog_canvas,
                    "weather_icon_label": weather_icon_label,
                    "weather_canvas": weather_canvas if is_digital else None,
                    "weather_ghost_item": weather_ghost_item if is_digital else None,
                    "weather_live_item": weather_live_item if is_digital else None,
                    "weather_temp_label": weather_temp_label,
                    "temp_canvas": temp_canvas if is_digital else None,
                    "temp_ghost_item": temp_ghost_item if is_digital else None,
                    "temp_live_item": temp_live_item if is_digital else None,
                    "time_ghost_label": None,
                    "weather_ghost_label": None,
                    "weather_temp_ghost_label": None,
                    "beep_key": beep_key if is_digital else None,
                    "beep_toggle_btn": beep_toggle_btn if is_digital else None,
                    "am_label": am_label,
                    "pm_label": pm_label,
                    "time_24h_var": time_24h_var,
                    "toggle_btn": toggle_btn,
                    "last_second": None,
                    "last_minute": None,
                    "last_hour": None,
                })
            return local_rows

        watch_rows = _build_watch_panel(details_frame)

        def update_weapon_view():

            nonlocal watch_rows

            wpn = current_weapon_state["weapon"]
            weapon_name_label.configure(text = f"Selected: {wpn.get('name', 'Unknown')}")
            for child in details_frame.winfo_children():
                child.destroy()

            sd = globals().get('save_data')if 'save_data'in globals()else save_data
            try:
                self._apply_item_overrides(wpn)
            except Exception:
                logging.exception("Suppressed exception")
            self._display_weapon_details(details_frame, wpn, combat_state, sd, table_data, current_weapon_state)
            watch_rows = _build_watch_panel(details_frame)

            try:

                try:
                    new_max = _compute_rounds_max_for_weapon(wpn, current_weapon_state)
                    _apply_rounds_max(new_max)
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                dev_menu = current_weapon_state.get("dev_variant_menu_ref")
                dev_var = current_weapon_state.get("dev_variant_var")
                dev_cal_menu = current_weapon_state.get("dev_caliber_menu_ref")
                dev_cal_var = current_weapon_state.get("dev_caliber_var")
                if dev_menu and dev_var is not None:

                    try:

                        new_choices =[]
                        caliber_list = wpn.get("caliber", [])or[]

                        try:
                            if dev_cal_var and hasattr(dev_cal_var, 'get'):
                                sel_cal = dev_cal_var.get()
                                if sel_cal:
                                    cal = sel_cal
                                else:
                                    cal = caliber_list[0]if caliber_list else None
                            else:
                                cal = caliber_list[0]if caliber_list else None
                        except Exception:
                            cal = caliber_list[0]if caliber_list else None
                        ammo_tables = table_data.get("tables", {}).get("ammunition", [])if table_data else[]
                        for ammo in ammo_tables:
                            try:
                                if cal and ammo.get("caliber")==cal:
                                    for var in ammo.get("variants", [])or[]:
                                        new_choices.append(var.get("name", "Unknown"))
                                else:
                                    w_sounds = wpn.get("sounds")or wpn.get("sound_folder")or wpn.get("ammo_type")
                                    if w_sounds and(ammo.get("sounds")==w_sounds or ammo.get("ammo_type")==w_sounds):
                                        for var in ammo.get("variants", [])or[]:
                                            new_choices.append(var.get("name", "Unknown"))
                            except Exception:
                                logging.exception("Suppressed exception")
                        if not new_choices:
                            new_choices =["Ball"]

                        try:
                            dev_menu.configure(values = new_choices)
                            if dev_var.get()not in new_choices:
                                dev_var.set(new_choices[0])
                        except Exception:

                            try:
                                dev_menu.set_values(new_choices)
                                if dev_var.get()not in new_choices:
                                    dev_var.set(new_choices[0])
                            except Exception:
                                logging.exception("Suppressed exception")

                        try:
                            if dev_cal_menu is not None and dev_cal_var is not None:
                                calib_vals =[]
                                if isinstance(caliber_list, (list, tuple)):
                                    calib_vals =[str(x)for x in caliber_list if x is not None]
                                elif isinstance(caliber_list, str):
                                    calib_vals =[caliber_list]
                                if not calib_vals:
                                    calib_vals =[""]
                                try:
                                    dev_cal_menu.configure(values = calib_vals)
                                    if dev_cal_var.get()not in calib_vals:
                                        try:
                                            dev_cal_var.set(calib_vals[0])
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                    if len(calib_vals)<=1:
                                        try:
                                            dev_cal_menu.configure(state = "disabled")
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                    else:
                                        try:
                                            dev_cal_menu.configure(state = "normal")
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    try:
                                        dev_cal_menu.set_values(calib_vals)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            sd2 = globals().get('save_data')if 'save_data'in globals()else save_data
            self._save_combat_state(sd2)

            try:
                rb = current_weapon_state.get('reload_mag_btn_ref')
                if rb:
                    def _hands_have_compatible_rounds(wpn):
                        try:

                            if wpn and isinstance(wpn, dict)and wpn.get('has_ammo_in_pool')is False:
                                return False
                            cal_list = wpn.get('caliber')if isinstance(wpn, dict)else None
                            cal = None
                            if isinstance(cal_list, (list, tuple)):
                                cal = str(cal_list[0])if cal_list else None
                            elif isinstance(cal_list, str):
                                cal = cal_list

                            for itm in save_data.get('hands', {}).get('items', []):
                                if not itm or not isinstance(itm, dict):
                                    continue

                                if itm.get('magazinesystem')or itm.get('capacity'):
                                    continue

                                rds = itm.get('rounds')
                                if isinstance(rds, list)and rds:
                                    first = rds[0]
                                    if isinstance(first, dict)and cal and str(first.get('caliber'))==str(cal):
                                        return True
                                    if isinstance(first, str)and cal and str(cal)in first:
                                        return True

                                    return True

                                qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                                if qty >0:
                                    ical = itm.get('caliber')or itm.get('name')
                                    if not cal or(ical and str(ical)==str(cal)):
                                        return True

                                if itm.get('caliber')and(not cal or str(itm.get('caliber'))==str(cal)):
                                    return True
                            return False
                        except Exception:
                            return False

                    def _inventory_has_nonfull_magazine():
                        try:
                            def check_item(itm):
                                if not itm or not isinstance(itm, dict):
                                    return False
                                cap = itm.get('capacity')
                                if cap is None:
                                    return False
                                try:
                                    cap_i = int(cap)
                                except Exception:
                                    return False
                                rounds = itm.get('rounds')
                                cur = 0
                                if isinstance(rounds, list):
                                    cur = len(rounds)
                                else:
                                    try:
                                        cur = int(rounds or 0)
                                    except Exception:
                                        cur = 0
                                return cur <cap_i

                            for itm in save_data.get('hands', {}).get('items', []):
                                try:
                                    if check_item(itm):
                                        return True
                                except Exception:
                                    logging.exception("Suppressed exception")
                            for slot_name, eq_item in save_data.get('equipment', {}).items():
                                try:
                                    if not eq_item or not isinstance(eq_item, dict):
                                        continue
                                    for itm in eq_item.get('items', [])or[]:
                                        try:
                                            if check_item(itm):
                                                return True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                    for sub in eq_item.get('subslots', [])or[]:
                                        try:
                                            curr = sub.get('current')
                                            if curr and isinstance(curr, dict):
                                                for itm in curr.get('items', [])or[]:
                                                    try:
                                                        if check_item(itm):
                                                            return True
                                                    except Exception:
                                                        logging.exception("Suppressed exception")
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                            return False
                        except Exception:
                            return False

                    def _inventory_has_nonempty_magazine():

                        try:
                            def check_mag(itm):
                                if not itm or not isinstance(itm, dict):
                                    return False
                                if itm.get('capacity')is None:
                                    return False
                                rounds = itm.get('rounds', [])
                                return isinstance(rounds, list)and len(rounds)>0

                            for itm in save_data.get('hands', {}).get('items', []):
                                if check_mag(itm):
                                    return True
                            for slot_name, eq_item in save_data.get('equipment', {}).items():
                                try:
                                    if not eq_item or not isinstance(eq_item, dict):
                                        continue
                                    for itm in eq_item.get('items', [])or[]:
                                        if check_mag(itm):
                                            return True
                                    for sub in eq_item.get('subslots', [])or[]:
                                        try:
                                            curr = sub.get('current')
                                            if curr and isinstance(curr, dict):
                                                for itm in curr.get('items', [])or[]:
                                                    if check_mag(itm):
                                                        return True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")

                            wpn = current_weapon_state.get('weapon')or {}
                            loaded_mag = wpn.get('loaded')
                            if check_mag(loaded_mag):
                                return True
                            return False
                        except Exception:
                            return False

                    has_nonfull = _inventory_has_nonfull_magazine()
                    has_nonempty = _inventory_has_nonempty_magazine()
                    enabled = has_nonfull or has_nonempty
                    try:
                        rb.configure(state = 'normal'if enabled else 'disabled')
                    except Exception:
                        try:
                            if not enabled:
                                rb.configure(state = 'disabled')
                            else:
                                rb.configure(state = 'normal')
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

        nvg_btn = None

        def _find_nvg_item():

            def _is_nvg(itm):
                try:
                    if not itm or not isinstance(itm, dict):
                        return False
                    iid = itm.get("id")
                    if iid is not None and str(iid)=="98":
                        return True
                    if itm.get("night_vision"):
                        return True
                    name = itm.get("name")or ""
                    if isinstance(name, str)and "night"in name.lower()and "vision"in name.lower():
                        return True
                except Exception:
                    logging.exception("Suppressed exception")
                return False

            try:

                for itm in save_data.get("hands", {}).get("items", []):
                    try:
                        if _is_nvg(itm):
                            return itm
                    except Exception:
                        logging.exception("Suppressed exception")

                for slot_name, eq in save_data.get("equipment", {}).items():
                    try:
                        if not eq:
                            continue
                        if "items"in eq and isinstance(eq["items"], list):
                            for itm in eq["items"]:
                                try:
                                    if _is_nvg(itm):
                                        return itm
                                except Exception:
                                    logging.exception("Suppressed exception")

                        if "subslots"in eq:
                            for sub in eq.get("subslots", []):
                                try:
                                    curr = sub.get("current")if isinstance(sub, dict)else None

                                    try:
                                        if _is_nvg(curr):
                                            return curr
                                    except Exception:
                                        logging.exception("Suppressed exception")

                                    if curr and "items"in curr and isinstance(curr["items"], list):
                                        for itm in curr["items"]:
                                            try:
                                                if _is_nvg(itm):
                                                    return itm
                                            except Exception:
                                                logging.exception("Suppressed exception")

                                    try:
                                        nested = curr
                                        depth = 0
                                        while isinstance(nested, dict)and depth <4:
                                            nested = nested.get("current")
                                            if _is_nvg(nested):
                                                return nested
                                            depth +=1
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    for acc in current_weapon.get("accessories", [])or[]:
                        try:
                            cur = acc.get("current")
                            if _is_nvg(cur):
                                return cur

                            if isinstance(cur, dict)and "items"in cur and isinstance(cur["items"], list):
                                for itm in cur["items"]:
                                    try:
                                        if _is_nvg(itm):
                                            return itm
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            return None

        def _update_nvg_button():

            try:
                has = _find_nvg_item()is not None
                active = bool(combat_state.get("nvg_active"))
                if nvg_btn is None:
                    return
                if not has:
                    try:
                        nvg_btn.configure(state = "disabled", fg_color = None)
                    except Exception:
                        nvg_btn.configure(state = "disabled")
                    return

                try:
                    nvg_btn.configure(state = "normal")
                    if active:
                        nvg_btn.configure(fg_color = "#228B22", hover_color = "#2E8B57")
                    else:
                        nvg_btn.configure(fg_color = "#444444", hover_color = "#666666")
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

        def _update_indoor_button():
            try:
                if indoor_switch is None:
                    return
                indoors = bool(combat_state.get("indoors"))
                if indoors:
                    indoor_switch.configure(text = "Indoors", text_color = "#7CFC7C")
                    if indoor_switch.get() != 1:
                        indoor_switch.select()
                else:
                    indoor_switch.configure(text = "Outdoors", text_color = "#dddddd")
                    if indoor_switch.get() != 0:
                        indoor_switch.deselect()
            except Exception:
                logging.exception("Suppressed exception")

        actions_outer_frame = customtkinter.CTkFrame(main_frame)
        actions_outer_frame.pack(fill = "x", pady =(0, 20))

        actions_frame = customtkinter.CTkScrollableFrame(actions_outer_frame, orientation = "horizontal", height = 280, fg_color = "transparent")
        actions_frame.pack(fill = "x", expand = True)

        rounds_label_frame = customtkinter.CTkFrame(actions_frame)
        rounds_label_frame.pack(fill = "x", padx = 10, pady = 5)

        customtkinter.CTkLabel(
        rounds_label_frame,
        text = "Rounds to Fire:",
        font = customtkinter.CTkFont(size = 12)
        ).pack(side = "left", padx = 10)

        rounds_var = customtkinter.IntVar(value = 3)
        rounds_value_label = customtkinter.CTkLabel(
        rounds_label_frame,
        text = "3",
        font = customtkinter.CTkFont(size = 12, weight = "bold")
        )
        rounds_value_label.pack(side = "left", padx = 5)

        def update_rounds_label(val):

            try:
                iv = int(round(float(val)))
            except Exception:
                try:
                    iv = int(float(val))
                except Exception:
                    iv = 1
            rounds_value_label.configure(text = str(iv))
            try:

                rounds_slider.set(iv)
                rounds_var.set(iv)
            except Exception:
                logging.exception("Suppressed exception")

        def _compute_rounds_max_for_weapon(wpn, wpn_state = None):
            max_val = 10
            try:
                if not isinstance(wpn, dict):
                    return max_val
                try:
                    subtype = str(wpn.get("subtype", "")or "").lower()
                except Exception:
                    subtype = ""
                if subtype !="machine_gun":
                    return max_val
                total = 0
                try:
                    if wpn.get("chambered"):
                        total +=1
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    internal_rounds = wpn.get("rounds")or[]
                    if isinstance(internal_rounds, list):
                        total +=len(internal_rounds)
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    loaded = wpn.get("loaded")
                    if isinstance(loaded, dict):
                        lr = loaded.get("rounds")
                        if isinstance(lr, list):
                            total +=len(lr)
                        else:
                            cap = loaded.get("capacity")
                            if cap:
                                try:
                                    total +=int(cap)
                                except Exception:
                                    logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
                if total >0:
                    max_val = max(max_val, total)
            except Exception:
                logging.exception("Suppressed exception")
            return max_val

        def _apply_rounds_max(max_slider_local):
            try:
                rounds_slider.configure(to = max_slider_local)
            except Exception:
                try:
                    rounds_slider.config(to = max_slider_local)
                except Exception:
                    logging.exception("Suppressed exception")
            try:
                cur = int(rounds_var.get()or 1)
                if cur >max_slider_local:
                    rounds_var.set(max_slider_local)
                    rounds_slider.set(max_slider_local)
                    rounds_value_label.configure(text = str(max_slider_local))
            except Exception:
                logging.exception("Suppressed exception")

        max_slider = _compute_rounds_max_for_weapon(current_weapon, current_weapon_state)

        rounds_slider = customtkinter.CTkSlider(
        rounds_label_frame,
        from_ = 1,
        to = max_slider,
        variable = rounds_var,
        command = update_rounds_label,
        width = 200
        )
        rounds_slider.pack(side = "left", padx = 10, expand = True, fill = "x")

        firemode_label_frame = customtkinter.CTkFrame(actions_frame)
        firemode_label_frame.pack(side = "left", padx = 10, pady = 10)

        customtkinter.CTkLabel(
        firemode_label_frame,
        text = "Fire Mode:",
        font = customtkinter.CTkFont(size = 12)
        ).pack(side = "top", padx = 5, pady = 2)

        raw_modes = current_weapon.get("action", ["Semi"])or["Semi"]
        supported_modes =[]
        for m in raw_modes:
            try:
                if isinstance(m, str):
                    supported_modes.append(m.title())
                else:
                    supported_modes.append(str(m))
            except Exception:
                logging.exception("Suppressed exception")
        if not supported_modes:
            supported_modes =["Semi"]

        selected_modes = combat_state.setdefault("selected_firemode", {})
        weapon_id = str(current_weapon.get("id"))
        initial_mode = selected_modes.get(weapon_id, supported_modes[0])
        if initial_mode not in supported_modes:
            initial_mode = supported_modes[0]

        mode_angles = {
        "Safe":0,
        "Semi":90,
        "Auto":180,
        "Burst":270,
        "Bolt":315,
        "Single":135,
        "Double":225,
        "Pump":45,
        "Slam-fire": 65
        }

        firemode_var = customtkinter.StringVar(value = initial_mode)

        def play_fireselector_sound():
            self._safe_sound_play("firearms/universal", "fireselector")

        def on_firemode_change(new_mode):
            selected_modes[weapon_id]= new_mode
            play_fireselector_sound()

        dial_canvas = customtkinter.CTkCanvas(
        firemode_label_frame,
        width = 140,
        height = 140,
        bg = "#212121",
        highlightthickness = 0
        )
        dial_canvas.pack(side = "top", padx = 5, pady = 5)

        dial_state = {"current_angle":mode_angles.get(initial_mode, 90), "dragging":False}

        def draw_dial():
            dial_canvas.delete("all")
            center_x, center_y = 70, 70
            radius = 35

            dial_canvas.create_oval(
            center_x -radius, center_y -radius,
            center_x +radius, center_y +radius,
            fill = "#333333", outline = "#555555", width = 2
            )

            labels = {
            0:"SAFE",
            45:"PUMP",
            90:"SEMI",
            135:"SINGLE",
            180:"AUTO",
            225:"DOUBLE",
            270:"BURST",
            315:"BOLT"
            }

            for mode, angle in mode_angles.items():
                if mode not in supported_modes:
                    continue
                rad = math.radians(angle)

                x1 = center_x +(radius -8)*math.cos(rad)
                y1 = center_y +(radius -8)*math.sin(rad)
                x2 = center_x +radius *math.cos(rad)
                y2 = center_y +radius *math.sin(rad)
                dial_canvas.create_line(x1, y1, x2, y2, fill = "#888888", width = 3)

                label_dist = radius +14
                label_x = center_x +label_dist *math.cos(rad)
                label_y = center_y +label_dist *math.sin(rad)
                dial_canvas.create_text(
                label_x, label_y,
                text = labels.get(angle, mode),
                fill = "#AAAAAA",
                font =("Arial", 9, "bold")
                )

            current_angle = dial_state["current_angle"]
            rad = math.radians(current_angle)
            pointer_x = center_x +28 *math.cos(rad)
            pointer_y = center_y +28 *math.sin(rad)
            dial_canvas.create_line(center_x, center_y, pointer_x, pointer_y, fill = "#FF4444", width = 4)

            knob_radius = 6
            dial_canvas.create_oval(
            center_x -knob_radius, center_y -knob_radius,
            center_x +knob_radius, center_y +knob_radius,
            fill = "#FF4444", outline = "#FFFFFF", width = 2
            )

            dial_canvas.create_text(
            center_x, 10,
            text = firemode_var.get(),
            fill = "#00FF00",
            font =("Arial", 11, "bold")
            )

        def get_angle_from_point(x, y):

            center_x, center_y = 70, 70
            dx = x -center_x
            dy = y -center_y
            angle = math.degrees(math.atan2(dy, dx))%360
            return angle

        def snap_to_nearest_mode(angle):

            best_mode = None
            best_diff = 360

            for mode, mode_angle in mode_angles.items():
                if mode not in supported_modes:
                    continue
                diff = min(abs(angle -mode_angle), 360 -abs(angle -mode_angle))
                if diff <best_diff:
                    best_diff = diff
                    best_mode = mode

            return best_mode, mode_angles.get(best_mode or "", angle)

        def on_mouse_down(event):
            center_x, center_y = 70, 70
            dx = event.x -center_x
            dy = event.y -center_y
            distance = math.sqrt(dx **2 +dy **2)

            if distance <40:
                dial_state["dragging"]= True

        def on_mouse_move(event):
            if not dial_state["dragging"]:
                return

            angle = get_angle_from_point(event.x, event.y)
            dial_state["current_angle"]= angle
            draw_dial()

        def on_mouse_up(event):
            if not dial_state["dragging"]:
                return

            dial_state["dragging"]= False

            best_mode, snapped_angle = snap_to_nearest_mode(dial_state["current_angle"])
            if best_mode:
                dial_state["current_angle"]= snapped_angle
                firemode_var.set(best_mode)
                on_firemode_change(best_mode)
                draw_dial()

        dial_canvas.bind("<Button-1>", on_mouse_down)
        dial_canvas.bind("<B1-Motion>", on_mouse_move)
        dial_canvas.bind("<ButtonRelease-1>", on_mouse_up)

        if len(supported_modes)==1:
            dial_canvas.configure(state = "disabled")

        draw_dial()

        attach_mode_frame = customtkinter.CTkFrame(actions_frame)
        attach_mode_frame.pack(side = "left", padx = 10, pady = 10)

        customtkinter.CTkLabel(
        attach_mode_frame,
        text = "Attachment Mode:",
        font = customtkinter.CTkFont(size = 12)
        ).pack(side = "top", padx = 5, pady = 2)

        attach_canvas = customtkinter.CTkCanvas(
        attach_mode_frame,
        width = 140,
        height = 140,
        bg = "#212121",
        highlightthickness = 0
        )
        attach_canvas.pack(side = "top", padx = 5, pady = 5)

        acc_with_modes = None
        acc_modes =[]
        acc_slot_ref = None
        attachments_with_modes =[]
        for ai, acc in enumerate(current_weapon.get("accessories", [])or[]):
            cur = acc.get("current")
            if cur and isinstance(cur, dict):
                _has_modes = isinstance(cur.get("modes"), list)and cur.get("modes")
                _is_elec = bool(cur.get("electronic"))
                if _has_modes or _is_elec:
                    display = str(cur.get('name', 'Attachment'))
                    attachments_with_modes.append((ai, acc, display))

        attach_select_var = customtkinter.StringVar(value = "")
        def _update_attachment_selection(choice):
            nonlocal acc_with_modes, acc_modes, acc_slot_ref, attachments_with_modes

            attachments_with_modes =[]
            for ai, acc in enumerate(current_weapon.get("accessories", [])or[]):
                cur = acc.get("current")
                if cur and isinstance(cur, dict):
                    _has_modes = isinstance(cur.get("modes"), list)and cur.get("modes")
                    _is_elec = bool(cur.get("electronic"))
                    if _has_modes or _is_elec:
                        display = str(cur.get('name', 'Attachment'))
                        attachments_with_modes.append((ai, acc, display))

            try:
                new_names =[disp for(_ai, _acc, disp)in attachments_with_modes]
                if hasattr(attach_mode_frame, 'mode_option')and attach_mode_frame.mode_option:
                    try:
                        attach_mode_frame.mode_option.configure(values = new_names)
                    except Exception:
                        logging.exception("Suppressed exception")
                if 'attach_select'in locals()or 'attach_select'in globals():
                    try:
                        attach_select.configure(values = new_names)
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Failed to refresh attachment option menu values")

            sel = None
            for ai, acc, disp in attachments_with_modes:
                if disp ==choice:
                    sel =(ai, acc)
                    break
            if sel is None:
                acc_with_modes = None
                acc_modes =[]
                acc_slot_ref = None
            else:
                acc_with_modes = sel[1]
                cur =(acc_with_modes.get("current")if isinstance(acc_with_modes, dict)else None)or {}
                orig_modes = cur.get("modes")or[]

                try:
                    cleaned =[m for m in orig_modes if not(isinstance(m, dict)and m.get("mode_method")is not None and not m.get("name"))]
                except Exception:
                    cleaned = orig_modes

                try:
                    if acc_with_modes.get("_mode_index")is None:
                        acc_with_modes["_mode_index"]= 0
                    else:
                        old_idx = int(acc_with_modes.get("_mode_index")or 0)
                        if 0 <=old_idx <len(orig_modes):
                            try:
                                elem = orig_modes[old_idx]
                                if elem in cleaned:
                                    acc_with_modes["_mode_index"]= int(cleaned.index(elem))
                                else:
                                    acc_with_modes["_mode_index"]= 0
                            except Exception:
                                acc_with_modes["_mode_index"]= 0
                except Exception:
                    try:
                        acc_with_modes["_mode_index"]= int(acc_with_modes.get("_mode_index")or 0)
                    except Exception:
                        acc_with_modes["_mode_index"]= 0

                acc_modes = cleaned

                _is_electronic_acc = bool(cur.get("electronic"))
                if _is_electronic_acc:
                    _off_mode = {"name": "Off", "_is_off": True}
                    if acc_modes:
                        acc_modes = [_off_mode] + acc_modes
                    else:
                        acc_modes = [_off_mode, {"name": "On"}]
                    if not cur.get("power_on"):
                        acc_with_modes["_mode_index"] = 0
                    else:
                        _prev = int(acc_with_modes.get("_mode_index") or 0)
                        if _prev < 1:
                            acc_with_modes["_mode_index"] = 1
                        elif _prev >= len(acc_modes):
                            acc_with_modes["_mode_index"] = len(acc_modes) - 1

                acc_slot_ref = acc_with_modes

                try:
                    if acc_modes:
                        idx = int(acc_with_modes.get("_mode_index")or 0)
                        idx = max(0, min(idx, len(acc_modes)-1))
                        mode_obj = acc_modes[idx]
                        pos_deg = mode_obj.get("position")if isinstance(mode_obj, dict)else None
                        if pos_deg is None:
                            pos_deg =(idx *(360.0 /max(1, len(acc_modes))))
                        try:
                            attach_state["current_angle"]= float(pos_deg)
                        except Exception:
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                _refresh_mode_controls()
            draw_attach_dial()

        attach_names =[disp for(_ai, _acc, disp)in attachments_with_modes]
        if attach_names:
            attach_select = customtkinter.CTkOptionMenu(attach_mode_frame, values = attach_names, variable = attach_select_var, command = _update_attachment_selection)
            attach_select.pack(side = "top", padx = 5, pady =(2, 4))

            attach_select_var.set(attach_names[0])
        else:

            customtkinter.CTkLabel(attach_mode_frame, text = "No attachment selected", font = customtkinter.CTkFont(size = 10), text_color = "#888888").pack(side = "top", padx = 5, pady =(2, 4))

        attach_mode_var = customtkinter.StringVar(value = "")
        attach_mode_slider = None

        def _refresh_mode_controls():
            nonlocal attach_mode_slider

            visible_modes =[]
            mode_index_map =[]
            for mi, mode in enumerate(acc_modes):
                if isinstance(mode, dict)and mode.get("mode_method")is not None and not mode.get("name"):

                    continue

                visible_modes.append(mode)
                mode_index_map.append(mi)
            mode_names =[]
            for vmi, mode in enumerate(visible_modes):
                if isinstance(mode, dict):
                    mode_names.append(mode.get("name", f"Mode {vmi}"))
                else:
                    mode_names.append(str(mode))

            mode_method = None
            try:

                cur =(acc_with_modes.get("current")if acc_with_modes else None)or {}
                mode_method = cur.get("mode_method")
                if not mode_method and acc_with_modes and isinstance(acc_with_modes, dict):
                    mode_method = acc_with_modes.get("mode_method")
                if not mode_method and acc_slot_ref and isinstance(acc_slot_ref, dict):
                    mode_method = acc_slot_ref.get("mode_method")

                if not mode_method:
                    for m in acc_modes:
                        if isinstance(m, dict)and m.get("mode_method"):
                            mode_method = m.get("mode_method")
                            break
            except Exception:
                mode_method = None

            if not mode_method:
                has_position = any(isinstance(m, dict)and m.get("position")is not None for m in acc_modes)
                mode_method = "dial"if has_position else "option"

            try:

                if mode_method =="option":
                    if hasattr(attach_mode_frame, 'mode_option'):
                        try:
                            attach_mode_frame.mode_option.configure(values = mode_names)
                            attach_mode_frame.mode_option.pack(side = "top", padx = 5, pady =(2, 4))
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:
                        attach_mode_frame.mode_option = customtkinter.CTkOptionMenu(attach_mode_frame, values = mode_names, variable = attach_mode_var, command = lambda v:_set_mode_by_name(v))
                        attach_mode_frame.mode_option.pack(side = "top", padx = 5, pady =(2, 4))
                else:

                    if hasattr(attach_mode_frame, 'mode_option'):
                        try:
                            attach_mode_frame.mode_option.pack_forget()
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Failed to refresh mode option menu")

            try:

                if mode_method =="slider":

                    if hasattr(attach_mode_frame, 'mode_slider')and attach_mode_frame.mode_slider:
                        try:
                            attach_mode_frame.mode_slider.configure(from_ = 0, to = max(0, len(visible_modes)-1), number_of_steps = max(1, len(visible_modes)-1))
                            attach_mode_frame.mode_slider.pack(side = "top", padx = 5, pady =(2, 6), fill = "x")
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:
                        attach_mode_frame.mode_slider = customtkinter.CTkSlider(attach_mode_frame, from_ = 0, to = max(0, len(visible_modes)-1), number_of_steps = max(1, len(visible_modes)-1), command = lambda v:_set_mode_by_index(round(float(v))))
                        attach_mode_frame.mode_slider.pack(side = "top", padx = 5, pady =(2, 6), fill = "x")
                else:

                    if hasattr(attach_mode_frame, 'mode_slider')and attach_mode_frame.mode_slider:
                        try:
                            attach_mode_frame.mode_slider.pack_forget()
                        except Exception:
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Failed to refresh mode slider")

            if acc_with_modes and acc_modes:
                actual_mi = int(acc_with_modes.get("_mode_index")or 0)

                try:
                    vis_index = mode_index_map.index(actual_mi)if actual_mi in mode_index_map else 0
                except Exception:
                    vis_index = 0
                try:
                    attach_mode_var.set(mode_names[vis_index]if mode_names else "")
                except Exception:
                    attach_mode_var.set(mode_names[0]if mode_names else "")
                if hasattr(attach_mode_frame, 'mode_slider')and attach_mode_frame.mode_slider:
                    try:
                        attach_mode_frame.mode_slider.set(vis_index)
                    except Exception:
                        logging.exception("Suppressed exception")

            attach_mode_frame._visible_modes = visible_modes
            attach_mode_frame._mode_index_map = mode_index_map

            try:
                if not hasattr(attach_mode_frame, 'mode_label')or attach_mode_frame.mode_label is None:
                    attach_mode_frame.mode_label = customtkinter.CTkLabel(attach_mode_frame, text = "", font = customtkinter.CTkFont(size = 12, weight = "bold"), text_color = "#44AAFF")
            except Exception:
                attach_mode_frame.mode_label = None

            try:
                ml = getattr(attach_mode_frame, 'mode_label', None)
                current_mode_name = ""
                try:
                    if acc_with_modes and acc_modes:
                        actual_mi = int(acc_with_modes.get("_mode_index")or 0)
                        actual_mi = max(0, min(actual_mi, len(acc_modes)-1))
                        mode_obj = acc_modes[actual_mi]
                        current_mode_name = mode_obj.get("name")if isinstance(mode_obj, dict)else str(mode_obj)
                except Exception:
                    current_mode_name = ""
                if ml:
                    try:
                        ml.configure(text = current_mode_name)
                    except Exception:
                        logging.exception("Suppressed exception")
                    try:
                        if mode_method in("slider", "option"):
                            ml.pack(side = "top", padx = 5, pady =(0, 6))
                        else:
                            ml.pack_forget()
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if mode_method =="dial":
                    try:
                        attach_canvas.pack(side = "top", padx = 5, pady = 5)
                    except Exception:
                        logging.exception("Suppressed exception")

                    attach_canvas.configure(state = "normal")
                else:
                    try:
                        attach_canvas.pack_forget()
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Failed to adjust attach canvas visibility")

        def _set_mode_by_name(name):
            if not acc_with_modes or not acc_modes:
                return

            vis = getattr(attach_mode_frame, '_visible_modes', None)
            map_ = getattr(attach_mode_frame, '_mode_index_map', None)
            if vis is not None and map_ is not None:
                for vmi, mode in enumerate(vis):
                    mode_name = mode.get("name")if isinstance(mode, dict)else str(mode)
                    if mode_name ==name:

                        actual = map_[vmi]
                        _set_mode_by_index(actual)
                        return

            for mi, mode in enumerate(acc_modes):
                mode_name = mode.get("name")if isinstance(mode, dict)else str(mode)
                if mode_name ==name:
                    _set_mode_by_index(mi)
                    return

        def _set_mode_by_index(idx):
            if not acc_with_modes or not acc_modes:
                return

            try:
                map_ = getattr(attach_mode_frame, '_mode_index_map', None)
                if map_ is not None and 0 <=int(idx)<len(map_):
                    actual_idx = int(map_[int(idx)])
                else:
                    actual_idx = int(idx)
            except Exception:
                actual_idx = 0

            _cur_att = (acc_with_modes.get("current") if isinstance(acc_with_modes, dict) else None) or {}
            _is_elec_mode = bool(_cur_att.get("electronic"))
            if _is_elec_mode:
                _batt_pct_now = _get_battery_percentage(_cur_att)
                if _batt_pct_now is not None and _batt_pct_now <= 0 and actual_idx != 0:
                    actual_idx = 0

            try:
                old_index = acc_with_modes.get("_mode_index")
            except Exception:
                old_index = None
            try:
                acc_with_modes["_mode_index"]= int(actual_idx)
            except Exception:
                acc_with_modes["_mode_index"]= 0

            if _is_elec_mode:
                _sel_mode = acc_modes[actual_idx] if 0 <= actual_idx < len(acc_modes) else {}
                if isinstance(_sel_mode, dict) and _sel_mode.get("_is_off"):
                    _cur_att["power_on"] = False
                    _cur_att.pop("power_on_timestamp", None)
                else:
                    if not _cur_att.get("power_on"):
                        _cur_att["power_on"] = True
                        _cur_att["power_on_timestamp"] = time.time()
                try:
                    _is_hc_mode = False
                    _tbl_hc_m = globals().get('table_data', {})
                    if isinstance(_tbl_hc_m, dict):
                        _is_hc_mode = bool((_tbl_hc_m.get('additional_settings') or {}).get('hardcore_mode'))
                    if _is_hc_mode and old_index is not None and int(old_index) != actual_idx:
                        _drain_cap = float(_cur_att.get("battery_capacity", 0) or 0)
                        if _drain_cap > 0:
                            _drain_amt = _drain_cap * 0.0002
                            _cur_lvl = float(_cur_att.get("battery_level", _drain_cap) or _drain_cap)
                            _cur_att["battery_level"] = round(max(0.0, _cur_lvl - _drain_amt), 4)
                            if _cur_att["battery_level"] <= 0:
                                _cur_att["power_on"] = False
                                _cur_att.pop("power_on_timestamp", None)
                                acc_with_modes["_mode_index"] = 0
                except Exception:
                    logging.exception("Suppressed exception")

            try:
                new_index = acc_with_modes.get("_mode_index")
                if new_index !=old_index:
                    self._safe_sound_play("firearms/universal", "fireselector")
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._apply_item_overrides(current_weapon)
            except Exception:
                logging.exception("Failed to apply overrides after attachment mode change")

            _refresh_mode_controls()

            try:
                mi = int(acc_with_modes.get("_mode_index")or 0)
                pos_deg = acc_modes[mi].get("position")if isinstance(acc_modes[mi], dict)and acc_modes[mi].get("position")is not None else(mi *(360.0 /max(1, len(acc_modes))))
                attach_state["current_angle"]= float(pos_deg)# type: ignore
            except Exception:
                logging.exception("Suppressed exception")

            try:
                ml = getattr(attach_mode_frame, 'mode_label', None)
                if ml:
                    try:
                        mode_obj = acc_modes[int(acc_with_modes.get("_mode_index")or 0)]
                        mname = mode_obj.get("name")if isinstance(mode_obj, dict)else str(mode_obj)
                    except Exception:
                        mname = ""
                    try:
                        ml.configure(text = mname)
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            draw_attach_dial()

        attach_state = {"current_angle":90, "dragging":False}

        def draw_attach_dial():
            attach_canvas.delete("all")
            center_x, center_y = 70, 70
            radius = 35
            attach_canvas.create_oval(
            center_x -radius, center_y -radius,
            center_x +radius, center_y +radius,
            fill = "#333333", outline = "#555555", width = 2
            )

            if not acc_modes:
                attach_canvas.create_text(center_x, center_y, text = "No Modes", fill = "#AAAAAA", font =("Arial", 10))
                return

            for mi, mode in enumerate(acc_modes):
                try:
                    pos_deg = None
                    if isinstance(mode, dict):
                        pos_deg = mode.get("position")
                    if pos_deg is None:
                        pos_deg =(mi *(360.0 /max(1, len(acc_modes))))
                    rad = math.radians(float(pos_deg))
                    x1 = center_x +(radius -8)*math.cos(rad)
                    y1 = center_y +(radius -8)*math.sin(rad)
                    x2 = center_x +radius *math.cos(rad)
                    y2 = center_y +radius *math.sin(rad)
                    attach_canvas.create_line(x1, y1, x2, y2, fill = "#888888", width = 3)

                    label_dist = radius +12
                    label_x = center_x +label_dist *math.cos(rad)
                    label_y = center_y +label_dist *math.sin(rad)
                    label_text = mode.get("name", f"Mode {mi}")if isinstance(mode, dict)else str(mode)
                    attach_canvas.create_text(label_x, label_y, text = label_text.upper(), fill = "#AAAAAA", font =("Arial", 9, "bold"))
                except Exception:
                    logging.exception("draw_attach_dial tick failed")

            current_angle = attach_state["current_angle"]
            rad = math.radians(current_angle)
            pointer_x = center_x +28 *math.cos(rad)
            pointer_y = center_y +28 *math.sin(rad)
            attach_canvas.create_line(center_x, center_y, pointer_x, pointer_y, fill = "#44AAFF", width = 4)
            knob_radius = 6
            attach_canvas.create_oval(
            center_x -knob_radius, center_y -knob_radius,
            center_x +knob_radius, center_y +knob_radius,
            fill = "#44AAFF", outline = "#FFFFFF", width = 2
            )

            if acc_with_modes and isinstance(acc_with_modes.get("current"), dict):
                mode_idx = acc_with_modes.get("_mode_index")
                try:
                    mode_idx = int(mode_idx)if mode_idx is not None else 0
                except Exception:
                    mode_idx = 0
                mode_idx = max(0, min(mode_idx, len(acc_modes)-1))
                mode_name = acc_modes[mode_idx].get("name", "Mode")if isinstance(acc_modes[mode_idx], dict)else str(acc_modes[mode_idx])
            else:
                mode_name = "None"

            attach_canvas.create_text(70, 10, text = mode_name, fill = "#00FF00", font =("Arial", 11, "bold"))

        def get_attach_angle_from_point(x, y):
            center_x, center_y = 70, 70
            dx = x -center_x
            dy = y -center_y
            angle = math.degrees(math.atan2(dy, dx))%360
            return angle

        def snap_attach_to_nearest(angle):
            if not acc_modes:
                return None, angle
            best_idx = 0
            best_diff = 360
            for mi, mode in enumerate(acc_modes):
                try:
                    pos_deg = mode.get("position")if isinstance(mode, dict)else None
                    if pos_deg is None:
                        pos_deg =(mi *(360.0 /max(1, len(acc_modes))))
                    md = float(pos_deg)
                    diff = min(abs(angle -md), 360 -abs(angle -md))
                    if diff <best_diff:
                        best_diff = diff
                        best_idx = mi
                except Exception:
                    logging.exception("Suppressed exception")
            chosen_angle = acc_modes[best_idx].get("position")if isinstance(acc_modes[best_idx], dict)and acc_modes[best_idx].get("position")is not None else(best_idx *(360.0 /max(1, len(acc_modes))))
            return best_idx, float(chosen_angle)# type: ignore

        def attach_on_mouse_down(event):
            center_x, center_y = 70, 70
            dx = event.x -center_x
            dy = event.y -center_y
            distance = math.sqrt(dx **2 +dy **2)
            if distance <40:
                attach_state["dragging"]= True

        def attach_on_mouse_move(event):
            if not attach_state["dragging"]:
                return
            angle = get_attach_angle_from_point(event.x, event.y)
            attach_state["current_angle"]= angle
            draw_attach_dial()

        def attach_on_mouse_up(event):
            if not attach_state["dragging"]:
                return
            attach_state["dragging"]= False
            if not acc_modes:
                return
            idx, snapped = snap_attach_to_nearest(attach_state["current_angle"])
            if idx is None:
                return
            attach_state["current_angle"]= snapped

            _cur_att_d = (acc_with_modes.get("current") if isinstance(acc_with_modes, dict) else None) or {}
            _is_elec_d = bool(_cur_att_d.get("electronic"))
            if _is_elec_d:
                _batt_pct_d = _get_battery_percentage(_cur_att_d)
                if _batt_pct_d is not None and _batt_pct_d <= 0 and idx != 0:
                    idx = 0
                    _snapped_off = acc_modes[0].get("position") if isinstance(acc_modes[0], dict) and acc_modes[0].get("position") is not None else 0.0
                    attach_state["current_angle"] = float(_snapped_off) # type: ignore

            try:
                old_index = acc_with_modes.get("_mode_index")
            except Exception:
                old_index = None
            try:
                acc_with_modes["_mode_index"]= int(idx)
            except Exception:
                acc_with_modes["_mode_index"]= 0

            if _is_elec_d:
                _sel_mode_d = acc_modes[idx] if 0 <= idx < len(acc_modes) else {}
                if isinstance(_sel_mode_d, dict) and _sel_mode_d.get("_is_off"):
                    _cur_att_d["power_on"] = False
                    _cur_att_d.pop("power_on_timestamp", None)
                else:
                    if not _cur_att_d.get("power_on"):
                        _cur_att_d["power_on"] = True
                        _cur_att_d["power_on_timestamp"] = time.time()
                try:
                    _is_hc_d = False
                    _tbl_hc_d = globals().get('table_data', {})
                    if isinstance(_tbl_hc_d, dict):
                        _is_hc_d = bool((_tbl_hc_d.get('additional_settings') or {}).get('hardcore_mode'))
                    if _is_hc_d and old_index is not None and int(old_index) != idx:
                        _dc = float(_cur_att_d.get("battery_capacity", 0) or 0)
                        if _dc > 0:
                            _da = _dc * 0.0002
                            _dl = float(_cur_att_d.get("battery_level", _dc) or _dc)
                            _cur_att_d["battery_level"] = round(max(0.0, _dl - _da), 4)
                            if _cur_att_d["battery_level"] <= 0:
                                _cur_att_d["power_on"] = False
                                _cur_att_d.pop("power_on_timestamp", None)
                                acc_with_modes["_mode_index"] = 0
                except Exception:
                    logging.exception("Suppressed exception")

            try:
                new_index = acc_with_modes.get("_mode_index")
                if new_index !=old_index:
                    self._safe_sound_play("firearms/universal", "fireselector")
            except Exception:
                logging.exception("Suppressed exception")
            try:
                self._apply_item_overrides(current_weapon)
            except Exception:
                logging.exception("Failed to apply overrides after attachment mode change")

            try:
                ml = getattr(attach_mode_frame, 'mode_label', None)
                if ml:
                    try:
                        mode_obj = acc_modes[int(acc_with_modes.get("_mode_index")or 0)]
                        mname = mode_obj.get("name")if isinstance(mode_obj, dict)else str(mode_obj)
                    except Exception:
                        mname = ""
                    try:
                        ml.configure(text = mname)
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")
            draw_attach_dial()

        attach_canvas.bind("<Button-1>", attach_on_mouse_down)
        attach_canvas.bind("<B1-Motion>", attach_on_mouse_move)
        attach_canvas.bind("<ButtonRelease-1>", attach_on_mouse_up)

        if not acc_modes:
            attach_canvas.configure(state = "disabled")

        try:
            if attach_names:
                _update_attachment_selection(attach_names[0])
        except Exception:
            logging.exception("Initial attachment selection failed")

        draw_attach_dial()

        def fire_weapon():
            wpn = current_weapon_state["weapon"]

            try:
                magicsys_local = str(wpn.get("magicsoundsystem")or "").lower()
                is_magic_local =(str(wpn.get("type")or "").lower()=="magic")or(magicsys_local in("hg", "at", "mg", "rf"))
                if is_magic_local:
                    weapon_id_local = str(wpn.get("id"))
                    temp_local = combat_state.get("barrel_temperatures", {}).get(weapon_id_local, combat_state.get("ambient_temperature", 70))
                    overheat_thresh = float(wpn.get("overheat_temp", wpn.get("shutdown_temp", 600)or 600))
                    if temp_local >=overheat_thresh:
                        try:
                            self._popup_show_info("Overheated", "Weapon is overheated and cannot fire.Wait for cooling.")
                        except Exception:
                            logging.exception("Suppressed exception")
                        return
            except Exception:
                logging.exception("Suppressed exception")
            rounds_to_fire = rounds_var.get()
            logging.info(
            "Fire button pressed: weapon=%s, rounds=%s, mode=%s",
            wpn.get("name", "Unknown"),
            rounds_to_fire,
            firemode_var.get()
            )

            def _do_fire():
                try:
                    res = self._fire_weapon(wpn, combat_state, rounds_to_fire, firemode_var.get(), save_data)
                    logging.info("Fire result(background): %s", res)
                    try:

                        self.root.after(0, lambda:self._popup_show_info("Fire Result", res))
                        self.root.after(0, update_weapon_view)
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception as e:
                    logging.exception("Fire action failed(background): %s", e)
                    try:
                        self.root.after(0, lambda:self._popup_show_info("Fire Error", str(e)))
                    except Exception:
                        logging.exception("Suppressed exception")
                finally:
                    try:
                        fb = current_weapon_state.get('fire_button_ref')
                        if fb:
                            try:
                                self.root.after(0, lambda:(fb.configure(state = 'normal')))
                                self.root.after(0, lambda:fb.configure(text =(current_weapon_state.get('fire_button_orig_text')or "Fire")))
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

            try:
                fb = current_weapon_state.get('fire_button_ref')
                if fb:
                    try:
                        fb.configure(state = 'disabled')
                        fb.configure(text = "Firing...")
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                t = threading.Thread(target = _do_fire, name = "CombatFireThread", daemon = True)
                t.start()
            except Exception:

                try:
                    result = self._fire_weapon(wpn, combat_state, rounds_to_fire, firemode_var.get(), save_data)
                    logging.info("Fire result(sync fallback): %s", result)
                    self._popup_show_info("Fire Result", result)
                except Exception as e:
                    logging.exception("Fire action failed: %s", e)
                    self._popup_show_info("Fire Error", str(e))
                update_weapon_view()

        def reload_weapon():
            wpn = current_weapon_state["weapon"]
            logging.info("Reload requested for %s", wpn.get("name", "Unknown"))
            magazine_system = wpn.get("magazinesystem")
            magazine_type = wpn.get("magazinetype", "").lower()

            pf = None
            try:
                pf = wpn.get("platform")or wpn.get("underbarrel_platform")
            except Exception:
                pf = None
            if wpn.get("underbarrel_weapon")or(pf and pf in getattr(self, "PLATFORM_DEFAULTS", {})):
                result = self._reload_weapon(wpn, save_data)
                self._popup_show_info("Reload Result", result)
                update_weapon_view()
                return

            if wpn.get("infinite_ammo"):
                _inf_mag_type = str(wpn.get('magazinetype', '')or '').lower()
                if 'cylinder' in _inf_mag_type or 'revolver' in str(wpn.get('platform', '') or '').lower():
                    _handle_cylinder_reload()
                    return
                if 'break' in _inf_mag_type:
                    _handle_break_action_reload()
                    return
                if wpn.get('capacity')is not None and('internal'in _inf_mag_type or 'tube'in _inf_mag_type or 'box'in _inf_mag_type or 'en bloc' in _inf_mag_type or not wpn.get('magazinesystem')):
                    _handle_internal_magazine_reload()
                    return
                result = self._reload_weapon(wpn, save_data)
                self._popup_show_info("Reload Result", result)
                update_weapon_view()
                return

            if "break"in magazine_type:
                _handle_break_action_reload()
                return

            if "muzzle"in magazine_type:
                self._reload_muzzleloader_ui(wpn, save_data, update_weapon_view)
                return

            if "internal"in magazine_type or "tube"in magazine_type or "en bloc" in magazine_type:
                _handle_internal_magazine_reload()
                return

            if "revolver"in wpn.get("platform", "").lower()or "cylinder"in magazine_type:
                _handle_cylinder_reload()
                return

            if "belt"in magazine_type or "belt"in(wpn.get("platform", "")or "").lower():
                if wpn.get("dualfeed")and(wpn.get("submagazinesystem")or wpn.get("submagazinetype")):
                    self._perform_dualfeed_belt_reload_sequence(wpn, quick=False)
                else:
                    self._show_belt_variant_selection(wpn, quick=False)
                return

            if not magazine_system:
                inferred_ms = None
                if wpn.get("magazinetype"):
                    inferred_ms = wpn.get("magazinetype")
                else:
                    loaded_mag = wpn.get("loaded")
                    if isinstance(loaded_mag, dict)and loaded_mag.get("magazinesystem"):
                        inferred_ms = loaded_mag.get("magazinesystem")
                    else:

                        for item in save_data.get("hands", {}).get("items", []):
                            if item and isinstance(item, dict)and("rounds"in item or "capacity"in item):
                                inferred_ms = item.get("magazinesystem")or item.get("magazinetype")
                                if inferred_ms:
                                    break
                        if not inferred_ms:
                            for slot_name, eq_item in save_data.get("equipment", {}).items():
                                if eq_item and isinstance(eq_item, dict):
                                    if "items"in eq_item and isinstance(eq_item["items"], list):
                                        for mag in eq_item["items"]:
                                            if mag and isinstance(mag, dict)and("rounds"in mag or "capacity"in mag):
                                                inferred_ms = mag.get("magazinesystem")or mag.get("magazinetype")
                                                break
                                    if inferred_ms:
                                        break
                if inferred_ms:

                    wpn["magazinesystem"]= inferred_ms

            self._show_magazine_selection_menu(wpn, save_data, table_data, current_weapon_state, update_weapon_view)

        def clean_weapon():
            wpn = current_weapon_state["weapon"]
            logging.info("Clean requested for %s", wpn.get("name", "Unknown"))

            def _do_clean():
                try:
                    result = self._clean_weapon(wpn, combat_state)
                    self.root.after(0, lambda: self._popup_show_info("Clean Result", result))
                    self.root.after(0, update_weapon_view)
                except Exception as e:
                    logging.exception("Clean weapon failed: %s", e)
                    self.root.after(0, lambda: self._popup_show_info("Clean Error", str(e)))

            t = threading.Thread(target = _do_clean, name = "CleanWeaponThread", daemon = True)
            t.start()

        def on_spacebar(event):
            logging.debug("Spacebar pressed - firing")
            fire_weapon()

        self.root.bind("<space>", on_spacebar)

        reload_last_press_time =[0.0]
        reload_pending_id =[None]

        def on_r_press(event):

            current_time = time.time()
            time_since_last = current_time -reload_last_press_time[0]
            reload_last_press_time[0]= current_time

            if reload_pending_id[0]:
                self.root.after_cancel(reload_pending_id[0])
                reload_pending_id[0]= None

            if time_since_last <0.4:
                logging.debug("R double-tapped - auto-reload with drop")
                reload_auto_drop()
            else:

                try:
                    _rid = self.root.after(400, lambda:reload_weapon())
                    reload_pending_id[0]= _rid # type: ignore
                except Exception:
                    reload_pending_id[0]= None

        self.root.bind("r", on_r_press)
        self.root.bind("R", on_r_press)

        if global_variables.get("devmode", {}).get("value", False):
            g_last_press_time =[0.0]
            g_pending_id =[None]

            def _get_compatible_mag_count():
                try:
                    wpn = current_weapon_state.get("weapon", {})
                    needed = set()
                    needed.update(self._normalize_to_lower_set(wpn.get("magazinesystem")))
                    needed.update(self._normalize_to_lower_set(wpn.get("submagazinesystem")))
                    needed.update(self._normalize_to_lower_set(wpn.get("submagazinetype")))
                    if not needed:
                        return 0
                    magazines_table = table_data.get("tables", {}).get("magazines", [])
                    total = 0
                    for m in magazines_table:
                        if not isinstance(m, dict):
                            continue
                        mag_tokens = set()
                        mag_tokens.update(self._normalize_to_lower_set(m.get("magazinesystem")))
                        mag_tokens.update(self._normalize_to_lower_set(m.get("magazinetype")))
                        if mag_tokens.intersection(needed):
                            total += 1
                    return total
                except Exception:
                    return 0

            def on_g_press(event):
                mag_count = _get_compatible_mag_count()
                if mag_count <= 1:
                    add_individual_magazine()
                    return

                current_time = time.time()
                time_since_last = current_time -g_last_press_time[0]
                g_last_press_time[0]= current_time

                if g_pending_id[0]:
                    self.root.after_cancel(g_pending_id[0])
                    g_pending_id[0]= None

                if time_since_last <0.4:
                    logging.debug("G double-tapped - quick give magazine")
                    add_individual_magazine()
                else:
                    try:
                        _gid = self.root.after(400, add_individual_magazine)
                        g_pending_id[0]= _gid # type: ignore
                    except Exception:
                        g_pending_id[0]= None

            self.root.bind("g", on_g_press)
            self.root.bind("G", on_g_press)

        def reload_auto_drop():

            wpn = current_weapon_state["weapon"]

            if wpn.get("infinite_ammo"):
                result = self._reload_weapon(wpn, save_data)
                self._popup_show_info("Auto-Reload", result)
                update_weapon_view()
                return

            def _norm_token_set(value):
                out = set()
                if isinstance(value, (list, tuple, set)):
                    for v in value:
                        sv = str(v or "").strip().lower()
                        if sv:
                            out.add(sv)
                else:
                    sv = str(value or "").strip().lower()
                    if sv:
                        out.add(sv)
                return out

            needed_systems = set()
            needed_systems.update(_norm_token_set(wpn.get("magazinesystem")))
            needed_systems.update(_norm_token_set(wpn.get("submagazinesystem")))

            if not needed_systems:
                self._popup_show_info("Auto-Reload", "Weapon doesn't use detachable magazines")
                return

            all_magazines =[]

            def _mag_matches_needed_systems(item):
                if not isinstance(item, dict):
                    return False
                mag_tokens = set()
                mag_tokens.update(_norm_token_set(item.get("magazinesystem")))
                mag_tokens.update(_norm_token_set(item.get("magazinetype")))
                return bool(mag_tokens.intersection(needed_systems))

            for item in save_data.get("hands", {}).get("items", []):
                if item and _mag_matches_needed_systems(item):
                    all_magazines.append(("hands", item))

            for slot_name, eq_item in save_data.get("equipment", {}).items():
                if eq_item and isinstance(eq_item, dict):
                    if "items"in eq_item and isinstance(eq_item["items"], list):
                        for item in eq_item["items"]:
                            if item and _mag_matches_needed_systems(item):
                                all_magazines.append(("equipment", item))
                    if "subslots"in eq_item:
                        for subslot in eq_item["subslots"]:
                            if subslot.get("current"):
                                curr = subslot["current"]
                                if "items"in curr and isinstance(curr["items"], list):
                                    for item in curr["items"]:
                                        if item and _mag_matches_needed_systems(item):
                                            all_magazines.append(("equipment", item))

            if not all_magazines:
                self._popup_show_info("Auto-Reload", "No compatible magazines in inventory!")
                return

            best_mag_idx = 0
            best_round_count = len(all_magazines[0][1].get("rounds", []))

            for idx, (location, mag_item)in enumerate(all_magazines):
                round_count = len(mag_item.get("rounds", []))
                if round_count >best_round_count:
                    best_round_count = round_count
                    best_mag_idx = idx

            location, mag_item = all_magazines[best_mag_idx]

            current_mag = wpn.get("loaded")
            chambered = wpn.get("chambered")
            is_gun_empty = not chambered and(not current_mag or not current_mag.get("rounds", []))

            try:

                mag_type_current =((current_mag.get("magazinetype")if current_mag else None)or wpn.get("magazinetype")or "").lower()
                platform =(wpn.get("platform")or "").lower()
                is_belt =("belt"in mag_type_current)or("belt"in platform)or("m249"in platform)

                try:
                    logging.debug("reload_auto_drop: weapon=%s platform=%s magazinetype=%s current_mag_present=%s dualfeed=%s submagazinetype=%s submagazinesystem=%s is_belt=%s",
                    wpn.get("name", wpn.get("id", "unknown")),
                    platform,
                    mag_type_current,
                    bool(current_mag),
                    bool(wpn.get("dualfeed")),
                    wpn.get("submagazinetype"),
                    wpn.get("submagazinesystem"),
                    is_belt)
                except Exception:
                    logging.exception("Suppressed exception")

                handled_belt = False

                if current_mag and not("belt"in mag_type_current):

                    try:
                        self._play_weapon_action_sound(wpn, "magout")
                    except Exception:
                        logging.exception("Suppressed exception")

                    time.sleep(random.uniform(0.5, 1.0))

                    try:
                        magdrop_sound = f"magdrop{random.randint(0, 1)}"
                        self._safe_sound_play("", f"sounds/firearms/universal/{magdrop_sound}.ogg")
                    except Exception:
                        logging.exception("Suppressed exception")
                    time.sleep(random.uniform(0.5, 1.0))

                    try:
                        self._safe_sound_play("", "sounds/firearms/universal/pouchout.ogg")
                    except Exception:
                        logging.exception("Suppressed exception")
                    time.sleep(random.uniform(0.25, 0.5))

                    mag_type = wpn.get("magazinetype", "").lower()
                    platform_check = wpn.get("platform", "").lower()
                    if not any(k in mag_type for k in("internal", "tube", "cylinder"))and "revolver"not in platform_check:
                        try:
                            self._play_weapon_action_sound(wpn, "magin")
                        except Exception:
                            logging.exception("Suppressed exception")
                    time.sleep(random.uniform(0.25, 0.5))

                elif is_belt:

                    if wpn.get("dualfeed")and(wpn.get("submagazinesystem")or wpn.get("submagazinetype")):
                        try:
                            self._perform_dualfeed_belt_reload_sequence(wpn, quick=True)
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:
                        try:
                            self._show_belt_variant_selection(wpn, quick=True)
                        except Exception:
                            logging.exception("Suppressed exception")
                    handled_belt = True

                else:

                    try:
                        self._safe_sound_play("", "sounds/firearms/universal/pouchout.ogg")
                    except Exception:
                        logging.exception("Suppressed exception")
                    time.sleep(0.8)

                if not handled_belt and is_gun_empty:
                    rt_mag_type = str(wpn.get("magazinetype", "")or "").lower()
                    rt_platform_raw = wpn.get("platform", "")or ""
                    if isinstance(rt_platform_raw, (list, tuple)):
                        rt_platform_raw = rt_platform_raw[0]if rt_platform_raw else ""
                    rt_platform = str(rt_platform_raw).lower()
                    rt_action_raw = wpn.get("action", "")or ""
                    if isinstance(rt_action_raw, (list, tuple)):
                        rt_action_raw = rt_action_raw[0]if rt_action_raw else ""
                    rt_action = str(rt_action_raw).lower()
                    is_pump_reload =("pump"in rt_platform or rt_action =="pump"or "pump"in rt_mag_type)

                    if is_pump_reload:
                        try:
                            self._play_weapon_action_sound(wpn, "pumpback", block = True)
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            self._play_weapon_action_sound(wpn, "pumpforward")
                        except Exception:
                            logging.exception("Suppressed exception")
                    elif not wpn.get("bolt_catch"):
                        try:
                            self._play_weapon_action_sound(wpn, "boltback", block = True)
                        except Exception:
                            logging.exception("Suppressed exception")

                        try:
                            self._play_weapon_action_sound(wpn, "boltforward")
                        except Exception:
                            logging.exception("Suppressed exception")
                    else:
                        try:
                            self._play_weapon_action_sound(wpn, "boltforward")
                        except Exception:
                            logging.exception("Suppressed exception")

                try:
                    mag_type =(wpn.get("magazinetype")or "").lower()
                    platform_check =(wpn.get("platform")or "").lower()
                    _df_mag_loaded = wpn.get("dualfeed") and isinstance(wpn.get("loaded"), dict) and wpn.get("loaded")
                    is_detachable_box =(_df_mag_loaded or (not any(k in mag_type for k in("internal", "tube", "cylinder"))
                    and "revolver"not in platform_check
                    and "belt"not in mag_type and "belt"not in platform_check
                    and "m249"not in platform_check))
                except Exception:
                    is_detachable_box = True

                if is_detachable_box:

                    time.sleep(0.01)
                else:
                    time.sleep(0.75)
            except Exception as e:
                logging.error(f"reload_auto_drop sound sequence error: {e}")

            if current_mag:
                pass

            previous_chambered = wpn.get("chambered")
            wpn["loaded"]= mag_item

            try:
                _hc_tbl_rel = globals().get('table_data', {})
                if isinstance(_hc_tbl_rel, dict) and bool((_hc_tbl_rel.get('additional_settings') or {}).get('hardcore_mode')):
                    _sd_val = mag_item.get("spring_durability")
                    if _sd_val is not None:
                        try:
                            _sd_val = float(_sd_val)
                            _sd_val = max(0.0, _sd_val - random.uniform(0.3, 0.8))
                            mag_item["spring_durability"] = round(_sd_val, 2)
                        except (ValueError, TypeError):
                            logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            if is_gun_empty and mag_item.get("rounds", []):

                try:
                    wpn["chambered"]= mag_item["rounds"].pop(0)
                except Exception:
                    wpn["chambered"]= None
            else:

                wpn["chambered"]= previous_chambered

            if location =="hands":
                if mag_item in save_data.get("hands", {}).get("items", []):
                    save_data["hands"]["items"].remove(mag_item)
            elif location =="equipment":

                try:
                    self._play_weapon_action_sound(wpn, "pouchout")
                except Exception:
                    logging.exception("Suppressed exception")
                for slot_name, eq_item in save_data.get("equipment", {}).items():
                    if eq_item:
                        if "items"in eq_item and isinstance(eq_item["items"], list):
                            if mag_item in eq_item["items"]:
                                eq_item["items"].remove(mag_item)
                        if "subslots"in eq_item:
                            for subslot in eq_item["subslots"]:
                                if subslot.get("current"):
                                    curr = subslot["current"]
                                    if "items"in curr and isinstance(curr["items"], list):
                                        if mag_item in curr["items"]:
                                            curr["items"].remove(mag_item)

            mag_name = mag_item.get("name", "magazine")
            rounds = len(mag_item.get("rounds", []))
            chambered_info = " +1 in chamber"if is_gun_empty and wpn.get("chambered")else ""
            self._popup_show_info("Auto-Reload", f"Loaded {mag_name}({rounds}{chambered_info} rounds)!")
            update_weapon_view()

        fire_btn = self._create_sound_button(
        actions_frame,
        text = "Fire(Press SPACE)",
        command = fire_weapon,
        width = 150,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        )
        fire_btn.pack(side = "left", padx = 10, pady = 10)

        try:
            current_weapon_state['fire_button_ref']= fire_btn
            current_weapon_state['fire_button_orig_text']= "Fire(Press SPACE)"
        except Exception:
            logging.exception("Suppressed exception")

        self._create_sound_button(
        actions_frame,
        text = "Reload(Press R)",
        command = reload_weapon,
        width = 150,
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        ).pack(side = "left", padx = 10, pady = 10)

        self._create_sound_button(
        actions_frame,
        text = "Clean",
        command = clean_weapon,
        width = 150,
        height = 50,
        font = customtkinter.CTkFont(size = 14),
        fg_color = "#006400",
        hover_color = "#228B22"
        ).pack(side = "left", padx = 10, pady = 10)

        def cycle_bolt():
            wpn = current_weapon_state["weapon"]
            logging.info("Cycle bolt requested for %s", wpn.get("name", "Unknown"))
            result = self._cycle_bolt(wpn)
            self._popup_show_info("Cycle Action", result)
            update_weapon_view()

        def _toggle_nvg():
            try:
                nvg_item = _find_nvg_item()
                if not nvg_item:
                    self._popup_show_info("NVG", "No night-vision goggles found in inventory.")
                    try:
                        nvg_btn.configure(state = "disabled")
                    except Exception:
                        logging.exception("Suppressed exception")
                    return
                active = bool(combat_state.get("nvg_active"))

                combat_state["nvg_active"]= not active

                try:
                    combat_state["nvg_item_id"]= int(nvg_item.get("id"))
                except Exception:
                    combat_state["nvg_item_id"]= nvg_item.get("id")

                try:
                    if combat_state["nvg_active"]:
                        self._safe_sound_play("misc/nvg", "on")
                    else:
                        self._safe_sound_play("misc/nvg", "off")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    _update_nvg_button()
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("NVG toggle failed")

        try:
            nvg_btn = self._create_sound_button(actions_frame, "NVG", _toggle_nvg, width = 150, height = 50, font = customtkinter.CTkFont(size = 14))
            nvg_btn.pack(side = "left", padx = 10, pady = 10)
        except Exception:
            logging.exception("Failed to create NVG button")
        try:
            _update_nvg_button()
        except Exception:
            logging.exception("Suppressed exception")

        def _toggle_indoors():
            try:
                combat_state["indoors"] = bool(indoor_switch.get()) if indoor_switch is not None else not bool(combat_state.get("indoors"))
                try:
                    self._safe_sound_play("misc/nvg", "on" if combat_state["indoors"] else "off")
                except Exception:
                    logging.exception("Suppressed exception")
                _update_indoor_button()
            except Exception:
                logging.exception("Indoor toggle failed")

        try:
            indoor_frame = customtkinter.CTkFrame(actions_frame, fg_color = "#2b2b2b", corner_radius = 8)
            indoor_frame.pack(side = "left", padx = 10, pady = 10)
            customtkinter.CTkLabel(indoor_frame, text = "Location", font = customtkinter.CTkFont(size = 11, weight = "bold"), text_color = "#999999").pack(padx = 14, pady = (8, 2))
            indoor_switch = customtkinter.CTkSwitch(
                indoor_frame,
                text = "Outdoors",
                command = _toggle_indoors,
                font = customtkinter.CTkFont(size = 14, weight = "bold"),
                progress_color = "#228B22",
                width = 120,
            )
            indoor_switch.pack(padx = 14, pady = (0, 10))
            if bool(combat_state.get("indoors")):
                indoor_switch.select()
            _update_indoor_button()
        except Exception:
            logging.exception("Failed to create indoor/outdoor switch")

        def _toggle_electronics():
            try:
                wpn = current_weapon_state.get("weapon") or {}
                electronic_atts = []
                for acc in wpn.get("accessories", []) or []:
                    cur = acc.get("current")
                    if isinstance(cur, dict) and cur.get("electronic"):
                        electronic_atts.append(cur)
                    if isinstance(cur, dict):
                        for sub in cur.get("subslots", []) or []:
                            sub_cur = sub.get("current") if isinstance(sub, dict) else None
                            if isinstance(sub_cur, dict) and sub_cur.get("electronic"):
                                electronic_atts.append(sub_cur)

                if not electronic_atts:
                    self._popup_show_info("Electronics", "No electronic attachments on this weapon.")
                    return

                if len(electronic_atts) == 1:
                    att = electronic_atts[0]
                    ok, msg = _toggle_electronic_attachment(att)
                    self._popup_show_info("Electronics", f"{att.get('name', 'Device')}: {msg}")
                    try:
                        self._save_combat_state(save_data)
                    except Exception:
                        logging.exception("Suppressed exception")
                    update_weapon_view()
                    return

                elec_popup = customtkinter.CTkToplevel(self.root)
                elec_popup.title("Toggle Electronics")
                elec_popup.transient(self.root)
                self._center_popup_on_window(elec_popup, 400, 300)

                customtkinter.CTkLabel(elec_popup, text="Electronic Attachments", font=customtkinter.CTkFont(size=14, weight="bold")).pack(pady=8)

                for att in electronic_atts:
                    att_frame = customtkinter.CTkFrame(elec_popup, fg_color="transparent")
                    att_frame.pack(fill="x", padx=10, pady=3)

                    batt_pct = _get_battery_percentage(att)
                    pw = "ON" if att.get("power_on") else "OFF"
                    bt = f" ({batt_pct:.0f}%)" if batt_pct is not None else ""
                    lbl_text = f"{att.get('name', 'Device')} [{pw}{bt}]"
                    customtkinter.CTkLabel(att_frame, text=lbl_text, font=customtkinter.CTkFont(size=12)).pack(side="left", padx=5)

                    def _make_toggle(a=att):
                        def _do():
                            ok, msg = _toggle_electronic_attachment(a)
                            try:
                                self._save_combat_state(save_data)
                            except Exception:
                                logging.exception("Suppressed exception")
                            try:
                                elec_popup.destroy()
                            except Exception:
                                logging.exception("Suppressed exception")
                            update_weapon_view()
                        return _do

                    customtkinter.CTkButton(att_frame, text="Toggle", command=_make_toggle(), width=80, height=28).pack(side="right", padx=5)

                customtkinter.CTkButton(elec_popup, text="Close", command=elec_popup.destroy, width=120).pack(pady=8)
                try:
                    elec_popup.grab_set()
                    elec_popup.lift()
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Electronics toggle failed")

        try:
            elec_btn = self._create_sound_button(actions_frame, "Electronics", _toggle_electronics, width=150, height=50, font=customtkinter.CTkFont(size=14))
            elec_btn.pack(side="left", padx=10, pady=10)
        except Exception:
            logging.exception("Suppressed exception")

        def cooling_tick():
            try:
                ambient_temp = combat_state.get("ambient_temperature", 70)
                temps = combat_state.setdefault("barrel_temperatures", {})
                magic_ids = list(combat_state.get("magic_weapon_ids", {}).keys())

                for mid in magic_ids:
                    try:
                        t = float(temps.get(mid, ambient_temp))
                        if t >ambient_temp:

                            drop = max(1.0, (t -ambient_temp)*0.18)
                            t = max(ambient_temp, t -drop)
                            temps[mid]= t
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    w = current_weapon_state.get("weapon")
                    fb = current_weapon_state.get("fire_button_ref")
                    if fb and isinstance(fb, (customtkinter.CTkButton, )):
                        is_magic_w = False
                        try:
                            ms = str(w.get("magicsoundsystem")or "").lower()
                            is_magic_w =(str(w.get("type")or "").lower()=="magic")or(ms in("hg", "at", "mg", "rf"))
                        except Exception:
                            is_magic_w = False

                        if is_magic_w:
                            wid = str(w.get("id"))
                            tnow = temps.get(wid, ambient_temp)
                            overheat_thresh = float(w.get("overheat_temp", w.get("shutdown_temp", 600)or 600))
                            if tnow >=overheat_thresh:
                                try:
                                    fb.configure(state = "disabled")
                                    fb.configure(text =(current_weapon_state.get('fire_button_orig_text')or "Fire")+"(Overheated)")
                                except Exception:
                                    logging.exception("Suppressed exception")
                            else:
                                try:
                                    fb.configure(state = "normal")
                                    fb.configure(text = current_weapon_state.get('fire_button_orig_text')or "Fire")
                                except Exception:
                                    logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("cooling_tick failed")
            finally:
                try:
                    self.root.after(1000, cooling_tick)
                except Exception:
                    logging.exception("Suppressed exception")

        try:
            self.root.after(1000, cooling_tick)
        except Exception:
            logging.exception("Suppressed exception")

        def manage_attachments():
            wpn = current_weapon_state["weapon"]
            accessories = wpn.get("accessories", [])or[]
            if not accessories:
                self._popup_show_info("Attachments", "This weapon has no attachment slots.")
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Attachments")
            popup.transient(self.root)
            self._center_popup_on_window(popup, 420, 400)

            rows =[]

            def _weapon_acc_slot_blocked(slot_name):
                """Return the name of the slot/attachment blocking this slot, or None."""
                sl = str(slot_name or "").strip().lower()
                for other_acc in accessories:
                    if str(other_acc.get("slot") or "").strip().lower() == sl:
                        continue  # skip self
                    if not isinstance(other_acc.get("current"), dict):
                        continue  # nothing installed here
                    # Check if the other slot's conflicts_with mentions our slot
                    other_cw = other_acc.get("conflicts_with", [])
                    if isinstance(other_cw, str):
                        other_cw = [other_cw]
                    for c in (other_cw or []):
                        if str(c).strip().lower() == sl:
                            return other_acc.get("name") or other_acc.get("slot") or "another slot"
                    # Check if the installed attachment's conflicts_with mentions our slot
                    att_cw = other_acc["current"].get("conflicts_with", [])
                    if isinstance(att_cw, str):
                        att_cw = [att_cw]
                    for c in (att_cw or []):
                        if str(c).strip().lower() == sl:
                            return other_acc["current"].get("name") or other_acc.get("name") or "another slot"
                return None

            def candidates_for_slot(slot_req):
                matches =[]

                for itm in save_data.get("hands", {}).get("items", []):
                    if itm and isinstance(itm, dict)and itm.get("attachment"):
                        slot_field = itm.get("slot")
                        if slot_field ==slot_req or(isinstance(slot_field, list)and slot_req in slot_field):
                            matches.append(itm)

                for slot_name, eq_item in save_data.get("equipment", {}).items():
                    if eq_item and "items"in eq_item:
                        for itm in eq_item["items"]:
                            if itm and isinstance(itm, dict)and itm.get("attachment"):
                                slot_field = itm.get("slot")
                                if slot_field ==slot_req or(isinstance(slot_field, list)and slot_req in slot_field):
                                    matches.append(itm)
                return matches

            for acc in accessories:
                frame = customtkinter.CTkFrame(popup)
                frame.pack(fill = "x", padx = 10, pady = 6)
                blocker = _weapon_acc_slot_blocked(acc.get("slot"))
                slot_label_text = acc.get("name", "Slot")
                if blocker:
                    slot_label_text += f" \u26d4 Blocked by: {blocker}"
                customtkinter.CTkLabel(frame, text = slot_label_text, font = customtkinter.CTkFont(size = 12, weight = "bold"),
                                       text_color = ("#cc4444" if blocker else None)).pack(anchor = "w")
                opts =[(None, "None")]
                for itm in candidates_for_slot(acc.get("slot")):
                    label = itm.get("name", "Attachment")
                    opts.append((itm, label))

                cur = acc.get("current")
                current_label = "None"
                try:
                    if cur and isinstance(cur, dict):

                        found = False
                        cur_id = cur.get("id")
                        for itm, lbl in opts:
                            try:
                                if itm is cur:
                                    current_label = lbl
                                    found = True
                                    break
                                if isinstance(itm, dict)and cur_id is not None and itm.get("id")==cur_id:
                                    current_label = lbl
                                    found = True
                                    break
                            except Exception:
                                logging.exception("Suppressed exception")
                        if not found:

                            try:
                                installed_label = cur.get("name", "Installed")
                            except Exception:
                                installed_label = "Installed"
                            opts.append((cur, installed_label))# type: ignore
                            current_label = installed_label
                except Exception:
                    current_label = "None"

                current_choice = customtkinter.StringVar(value = current_label)
                option = customtkinter.CTkOptionMenu(frame, values =[o[1]for o in opts], variable = current_choice, width = 220)
                option.pack(anchor = "w", pady = 4)
                if blocker:
                    try:
                        option.configure(state = "disabled")
                    except Exception:
                        logging.exception("Suppressed exception")

                def _open_mode_dial_for(acc_ref):
                    try:

                        cur = acc_ref.get("current")
                        if not cur or not isinstance(cur, dict):
                            self._popup_show_info("Attachment Modes", "No attachment installed in this slot.")
                            return
                        modes = cur.get("modes")or[]
                        _is_elec_popup = bool(cur.get("electronic"))
                        if _is_elec_popup:
                            _off_m_p = {"name": "Off", "_is_off": True}
                            if modes:
                                modes = [_off_m_p] + list(modes)
                            else:
                                modes = [_off_m_p, {"name": "On"}]
                        if not modes or not isinstance(modes, list):
                            self._popup_show_info("Attachment Modes", "This attachment has no selectable modes.")
                            return

                        import tkinter as tk

                        dial = customtkinter.CTkToplevel(self.root)
                        dial.title("Select Mode")
                        size = 320
                        dial.transient(self.root)
                        self._center_popup_on_window(dial, size, size)

                        canvas = tk.Canvas(dial, width = size, height = size, highlightthickness = 0)
                        canvas.pack(fill = "both", expand = True)

                        cx = size //2
                        cy = size //2
                        r = int(size *0.35)

                        canvas.create_oval(cx -r, cy -r, cx +r, cy +r, outline = "#888", width = 2)

                        for mi, mode in enumerate(modes):
                            try:
                                pos_deg = mode.get("position")if isinstance(mode, dict)else None
                                if pos_deg is None:
                                    pos_deg =(mi *(360.0 /max(1, len(modes))))
                                theta = math.radians(float(pos_deg))
                                mx = cx +int(r *math.cos(theta))
                                my = cy +int(r *math.sin(theta))
                                label = mode.get("name", f"Mode {mi}")if isinstance(mode, dict)else str(mode)

                                btn = customtkinter.CTkButton(dial, text = label, width = 110, command =(lambda idx = mi, a = acc_ref, d = dial:_set_mode_and_close(a, idx, d)))

                                canvas.create_window(mx, my, window = btn)
                            except Exception:
                                logging.exception("Failed to render mode button")

                        cur_index = acc_ref.get("_mode_index")
                        if cur_index is None:
                            cur_index = acc_ref.get("mode_index")or 0
                        try:
                            cur_index = int(cur_index)
                        except Exception:
                            cur_index = 0

                        def _set_mode_and_close(acc_set, idx_set, dial_win):
                            _cur_p = (acc_set.get("current") if isinstance(acc_set, dict) else None) or {}
                            _is_elec_p = bool(_cur_p.get("electronic"))
                            if _is_elec_p:
                                _bp_p = _get_battery_percentage(_cur_p)
                                if _bp_p is not None and _bp_p <= 0 and idx_set != 0:
                                    idx_set = 0
                            try:
                                acc_set["_mode_index"]= int(idx_set)
                            except Exception:
                                acc_set["_mode_index"]= 0
                            if _is_elec_p:
                                _sel_p = modes[idx_set] if 0 <= idx_set < len(modes) else {}
                                if isinstance(_sel_p, dict) and _sel_p.get("_is_off"):
                                    _cur_p["power_on"] = False
                                    _cur_p.pop("power_on_timestamp", None)
                                else:
                                    if not _cur_p.get("power_on"):
                                        _cur_p["power_on"] = True
                                        _cur_p["power_on_timestamp"] = time.time()
                                try:
                                    _is_hc_p = False
                                    _tbl_hc_p = globals().get('table_data', {})
                                    if isinstance(_tbl_hc_p, dict):
                                        _is_hc_p = bool((_tbl_hc_p.get('additional_settings') or {}).get('hardcore_mode'))
                                    if _is_hc_p:
                                        _dcp = float(_cur_p.get("battery_capacity", 0) or 0)
                                        if _dcp > 0:
                                            _dap = _dcp * 0.0002
                                            _dlp = float(_cur_p.get("battery_level", _dcp) or _dcp)
                                            _cur_p["battery_level"] = round(max(0.0, _dlp - _dap), 4)
                                            if _cur_p["battery_level"] <= 0:
                                                _cur_p["power_on"] = False
                                                _cur_p.pop("power_on_timestamp", None)
                                                acc_set["_mode_index"] = 0
                                except Exception:
                                    logging.exception("Suppressed exception")
                            try:

                                self._apply_item_overrides(wpn)
                            except Exception:
                                logging.exception("Failed to apply overrides after mode change")
                            try:
                                dial_win.destroy()
                            except Exception:
                                logging.exception("Suppressed exception")

                    except Exception:
                        logging.exception("open_mode_dial failed")

                def _find_table_candidates(slot_req):
                    candidates =[]
                    try:
                        table_files = sorted(glob.glob(os.path.join('tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
                        for tf in table_files:
                            try:
                                with open(tf, 'r', encoding = 'utf-8')as tfh:
                                    td = json.load(tfh)
                                tables = td.get('tables', {})
                                for subname, items in tables.items():
                                    if not isinstance(items, list):
                                        continue
                                    for it in items:
                                        if not isinstance(it, dict):
                                            continue
                                        matched = False
                                        try:
                                            slot_field = it.get('slot')
                                            if slot_field ==slot_req or(isinstance(slot_field, (list, tuple))and slot_req in slot_field):
                                                matched = True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        try:
                                            accs = it.get('accessories')or[]
                                            if isinstance(accs, list):
                                                for a in accs:
                                                    if isinstance(a, dict)and a.get('slot'):
                                                        if a.get('slot')==slot_req:
                                                            matched = True
                                                            break
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                        if matched:

                                            try:
                                                if it.get('firearm'):
                                                    continue
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            candidates.append((it, tf, subname))
                            except Exception:
                                logging.exception("Suppressed exception")
                                continue
                    except Exception:
                        logging.exception("Suppressed exception")
                    return candidates

                def _open_add_from_table(acc_ref):
                    try:
                        slot_req = acc_ref.get("slot")
                        if not slot_req:
                            self._popup_show_info("Add From Table", "This slot has no slot name defined.")
                            return

                        candidates =[]
                        table_files = sorted(glob.glob(os.path.join('tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
                        for tf in table_files:
                            try:
                                with open(tf, 'r', encoding = 'utf-8')as tfh:
                                    td = json.load(tfh)
                                tables = td.get('tables', {})
                                for subname, items in tables.items():
                                    if not isinstance(items, list):
                                        continue
                                    for it in items:
                                        if not isinstance(it, dict):
                                            continue

                                        matched = False
                                        try:
                                            slot_field = it.get('slot')
                                            if slot_field ==slot_req or(isinstance(slot_field, (list, tuple))and slot_req in slot_field):
                                                matched = True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        try:
                                            accs = it.get('accessories')or[]
                                            if isinstance(accs, list):
                                                for a in accs:
                                                    if isinstance(a, dict)and a.get('slot'):
                                                        if a.get('slot')==slot_req:
                                                            matched = True
                                                            break
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                        try:
                                            subs = it.get('subslots')or[]
                                            if isinstance(subs, list):
                                                for s in subs:
                                                    if isinstance(s, dict)and s.get('slot'):
                                                        if s.get('slot')==slot_req:
                                                            matched = True
                                                            break
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                        if matched:

                                            try:
                                                if it.get('firearm'):
                                                    continue
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            candidates.append((it, tf, subname))
                            except Exception:
                                logging.exception("Suppressed exception")
                                continue

                        if not candidates:
                            self._popup_show_info("Add From Table", f"No table items found for slot '{slot_req}'.")
                            return

                        popup = customtkinter.CTkToplevel(self.root)
                        popup.title("Add From Table")
                        popup.transient(self.root)
                        self._center_popup_on_window(popup, 520, 360)

                        label = customtkinter.CTkLabel(popup, text = f"Select an item to add into slot '{slot_req}':", font = customtkinter.CTkFont(size = 13))
                        label.pack(pady = 8, padx = 12)

                        sel_var = customtkinter.StringVar(value = "")
                        names =[]
                        for it, tf, sub in candidates:
                            names.append(f"{it.get('name', '<unnamed>')}({os.path.basename(tf)}:{sub})")

                        opt = customtkinter.CTkOptionMenu(popup, values = names, variable = sel_var)
                        opt.pack(fill = "x", padx = 12, pady = 8)

                        def _do_add():
                            choice = sel_var.get()
                            if not choice:
                                self._popup_show_info("Add From Table", "Please select an item to add.")
                                return
                            idx = 0
                            try:
                                idx = names.index(choice)
                            except Exception:
                                idx = 0
                            item = candidates[idx][0]
                            try:
                                import copy as _copy
                                new_item = _copy.deepcopy(item)
                                save_data.setdefault('hands', {})
                                save_data['hands'].setdefault('items', [])
                                save_data['hands']['items'].append(new_item)
                                self._popup_show_info("Add From Table", f"Added '{new_item.get('name', 'item')}' to hands.")
                                try:
                                    popup.destroy()
                                except Exception:
                                    logging.exception("Suppressed exception")
                            except Exception as e:
                                logging.exception("Failed to add item from table: %s", e)

                        add_btn = customtkinter.CTkButton(popup, text = "Add Selected", command = _do_add, width = 140)
                        add_btn.pack(pady = 10)

                        cancel_btn = customtkinter.CTkButton(popup, text = "Cancel", command = popup.destroy, width = 120, fg_color = "#444444", hover_color = "#555555")
                        cancel_btn.pack(pady = 6)

                    except Exception as e:
                        logging.exception("_open_add_from_table failed: %s", e)

                dev_ok = False
                try:
                    dev_ok = bool(global_variables.get('devmode', {}).get('value'))
                except Exception:
                    dev_ok = False

                try:
                    slot_req = acc.get('slot')
                    candidates_here = _find_table_candidates(slot_req)if slot_req else[]
                except Exception:
                    candidates_here =[]

                add_table_btn = customtkinter.CTkButton(frame, text = "Add From Table...", width = 140, command =(lambda a = acc:_open_add_from_table(a)))
                if(not dev_ok)or(not candidates_here):
                    try:
                        add_table_btn.configure(state = "disabled")
                    except Exception:
                        logging.exception("Suppressed exception")
                add_table_btn.pack(anchor = "w", pady = 2)

                rows.append((acc, opts, current_choice, None))

            def apply_changes():
                def _sync_attachment_subslot(weapon, flattened_acc, new_value):

                    try:
                        parent_slot = flattened_acc.get('_parent_accessory_slot')
                        subslot_slot = flattened_acc.get('_subslot_slot')
                        if not parent_slot or not subslot_slot:
                            return

                        for parent_acc in weapon.get('accessories', [])or[]:
                            try:
                                if parent_acc.get('slot')!=parent_slot:
                                    continue
                                cur = parent_acc.get('current')
                                if not cur or not isinstance(cur, dict):
                                    continue
                                for sub in cur.get('subslots', [])or[]:
                                    if sub.get('slot')==subslot_slot:
                                        try:
                                            import copy as _c
                                            sub['current']= _c.deepcopy(new_value)if isinstance(new_value, dict)else new_value
                                        except Exception:
                                            sub['current']= new_value
                                        return
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                # ── Conflict validation ──────────────────────────────────
                try:
                    _will_install = {}
                    for _a, _o, _v, _sr in rows:
                        if _sr is not None:
                            continue
                        _lbl = _v.get()
                        _item = next((it for it, lb in _o if lb == _lbl), None)
                        _sn = str(_a.get("slot") or "").strip().lower()
                        if _sn:
                            _will_install[_sn] = _item

                    def _cw_set(val):
                        if isinstance(val, list):
                            return {str(c).strip().lower() for c in val if c}
                        if isinstance(val, str) and val.strip():
                            return {val.strip().lower()}
                        return set()

                    for _a, _o, _v, _sr in rows:
                        if _sr is not None:
                            continue
                        _lbl = _v.get()
                        _item = next((it for it, lb in _o if lb == _lbl), None)
                        if _item is None:
                            continue
                        _sn = str(_a.get("slot") or "").strip().lower()
                        for _cs in _cw_set(_a.get("conflicts_with")) | _cw_set(_item.get("conflicts_with") if isinstance(_item, dict) else None):
                            if _will_install.get(_cs) is not None:
                                _blocker_name = next(
                                    (_ba.get("name") or _cs for _ba, _, _, _bsr in rows
                                     if _bsr is None and str(_ba.get("slot") or "").lower() == _cs),
                                    _cs
                                )
                                self._popup_show_info(
                                    "Attachment Conflict",
                                    f"Cannot install '{_item.get('name', '?')}' in '{_a.get('name') or _sn}': "
                                    f"conflicts with '{_blocker_name}'.",
                                    sound="error"
                                )
                                return
                except Exception:
                    logging.exception("Attachment conflict check failed")

                for acc, opts, var, subslot_ref in rows:
                    chosen_label = var.get()
                    chosen_item = None
                    for itm, lbl in opts:
                        if lbl ==chosen_label:
                            chosen_item = itm
                            break

                    def _remove_all_references(item):
                        try:
                            if not item or not isinstance(item, dict):
                                return
                            item_id = item.get("id")
                        except Exception:
                            item_id = None

                        def _scan(obj):
                            if isinstance(obj, dict):
                                for k, v in list(obj.items()):
                                    _scan(v)
                            elif isinstance(obj, list):

                                to_remove =[]
                                for el in obj:
                                    try:
                                        if el is item:
                                            to_remove.append(el)
                                        elif isinstance(el, dict)and item_id is not None and el.get("id")==item_id:
                                            to_remove.append(el)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                for r in to_remove:
                                    try:
                                        while r in obj:
                                            obj.remove(r)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                for el in obj:
                                    _scan(el)

                        try:
                            _scan(save_data)
                        except Exception:
                            logging.exception("Suppressed exception")

                    if subslot_ref is not None:

                        if subslot_ref.get("current"):
                            try:
                                _remove_all_references(subslot_ref.get("current"))
                            except Exception:
                                logging.exception("Suppressed exception")
                            save_data.get("hands", {}).get("items", []).append(subslot_ref.get("current"))

                        if chosen_item is None:
                            subslot_ref["current"]= None
                        else:
                            try:
                                _remove_all_references(chosen_item)
                            except Exception:
                                logging.exception("Suppressed exception")
                            hands_items = save_data.get("hands", {}).get("items", [])
                            try:
                                if chosen_item in hands_items:
                                    hands_items.remove(chosen_item)
                            except Exception:
                                logging.exception("Suppressed exception")
                            try:
                                for slot_name, eq_item in save_data.get("equipment", {}).items():
                                    if eq_item and "items"in eq_item and isinstance(eq_item["items"], list):
                                        try:
                                            while chosen_item in eq_item["items"]:
                                                eq_item["items"].remove(chosen_item)
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                    if eq_item and "subslots"in eq_item:
                                        for sub in eq_item.get("subslots", []):
                                            if sub and sub.get("current")and "items"in sub.get("current", {}):
                                                try:
                                                    while chosen_item in sub["current"]["items"]:
                                                        sub["current"]["items"].remove(chosen_item)
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                import copy as _copy
                                new_installed = _copy.deepcopy(chosen_item)if isinstance(chosen_item, dict)else chosen_item
                            except Exception:
                                new_installed = chosen_item

                            subslot_ref["current"]= new_installed

                            try:
                                def _sync_subslot_to_save(accessory_obj, subslot_obj, installed_obj):
                                    try:

                                        aid = accessory_obj.get('id')if isinstance(accessory_obj, dict)else None
                                        aname = accessory_obj.get('name')if isinstance(accessory_obj, dict)else None
                                        aslot = accessory_obj.get('slot')if isinstance(accessory_obj, dict)else None
                                        for slot_name, eq_item in save_data.get('equipment', {}).items():
                                            if not eq_item or not isinstance(eq_item, dict):
                                                continue

                                            for acc in eq_item.get('accessories', [])or[]:
                                                try:
                                                    if not isinstance(acc, dict):
                                                        continue
                                                    match = False
                                                    if aid is not None and acc.get('id')==aid:
                                                        match = True
                                                    elif aname and acc.get('name')==aname:
                                                        match = True
                                                    elif aslot and acc.get('slot')==aslot:
                                                        match = True
                                                    if match:

                                                        for sub in acc.get('current', {}).get('subslots', [])if acc.get('current')else[]:
                                                            try:
                                                                if(sub.get('slot')and sub.get('slot')==subslot_obj.get('slot'))or(sub.get('name')and sub.get('name')==subslot_obj.get('name')):

                                                                    try:
                                                                        import copy as _c
                                                                        sub['current']= _c.deepcopy(installed_obj)if isinstance(installed_obj, dict)else installed_obj
                                                                    except Exception:
                                                                        sub['current']= installed_obj
                                                                    return True
                                                            except Exception:
                                                                logging.exception("Suppressed exception")
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                                        return False
                                    except Exception:
                                        return False

                                try:
                                    _sync_subslot_to_save(acc, subslot_ref, new_installed)
                                except Exception:
                                    logging.exception("Suppressed exception")
                            except Exception:
                                logging.exception("Suppressed exception")

                    else:

                        if acc.get("current"):
                            try:
                                _remove_all_references(acc["current"])
                            except Exception:
                                logging.exception("Suppressed exception")
                            save_data.get("hands", {}).get("items", []).append(acc["current"])

                        if chosen_item is None:
                            acc["current"]= None
                            if acc.get("_is_attachment_subslot"):
                                try:
                                    _sync_attachment_subslot(wpn, acc, None)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        else:
                            try:
                                _remove_all_references(chosen_item)
                            except Exception:
                                logging.exception("Suppressed exception")

                            hands_items = save_data.get("hands", {}).get("items", [])
                            try:
                                if chosen_item in hands_items:
                                    hands_items.remove(chosen_item)
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                for slot_name, eq_item in save_data.get("equipment", {}).items():
                                    if eq_item and "items"in eq_item and isinstance(eq_item["items"], list):
                                        try:
                                            while chosen_item in eq_item["items"]:
                                                eq_item["items"].remove(chosen_item)
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                    if eq_item and "subslots"in eq_item:
                                        for sub in eq_item.get("subslots", []):
                                            if sub and sub.get("current")and "items"in sub.get("current", {}):
                                                try:
                                                    while chosen_item in sub["current"]["items"]:
                                                        sub["current"]["items"].remove(chosen_item)
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                import copy as _copy
                                new_installed = _copy.deepcopy(chosen_item)if isinstance(chosen_item, dict)else chosen_item
                            except Exception:
                                new_installed = chosen_item

                            acc["current"]= new_installed

                            if acc.get("_is_attachment_subslot"):
                                try:
                                    _sync_attachment_subslot(wpn, acc, new_installed)
                                except Exception:
                                    logging.exception("Suppressed exception")

                            try:
                                if isinstance(acc.get("current"), dict):
                                    add_subslots_to_item(acc.get("current"))
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                modes = acc.get("current", {}).get("modes")or[]
                                if isinstance(modes, list)and modes:
                                    if acc.get("_mode_index")is None and acc.get("mode_index")is None:
                                        acc["_mode_index"]= 0
                            except Exception:
                                logging.exception("Suppressed exception")

                for acc, opts, var, subslot_ref in rows:
                    if acc.get('_is_attachment_subslot'):
                        continue
                    try:
                        acc_slot = acc.get('slot')
                        to_remove =[]
                        for i, other_acc in enumerate(wpn.get('accessories', [])or[]):
                            if other_acc.get('_is_attachment_subslot')and other_acc.get('_parent_accessory_slot')==acc_slot:
                                to_remove.append(other_acc)
                        for r in to_remove:
                            try:
                                wpn['accessories'].remove(r)
                            except Exception:
                                logging.exception("Suppressed exception")

                        if acc.get('current')and isinstance(acc.get('current'), dict):
                            try:
                                _add_attachment_subslots_to_weapon(wpn, acc, acc.get('current'))
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    self._apply_item_overrides(wpn)
                except Exception:
                    logging.exception("Failed to apply attachment overrides")

                try:
                    self._save_file(save_data)
                except Exception:
                    logging.exception("Failed to save save_data after applying attachments")

                popup.destroy()
                update_weapon_view()

            apply_btn = customtkinter.CTkButton(popup, text = "Apply", command = apply_changes, width = 120)
            apply_btn.pack(pady = 10)

            try:
                popup.update_idletasks()
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
                    self._center_popup_on_window(popup, 420, 400)
                except Exception:
                    logging.exception("Suppressed exception")

        def check_magazine():
            import time
            wpn = current_weapon_state["weapon"]
            loaded_mag = wpn.get("loaded")

            if not loaded_mag:
                ammo_label_ref = current_weapon_state.get("ammo_label_ref")
                if ammo_label_ref:
                    ammo_label_ref.configure(text = "Ammo: No magazine loaded", text_color =("gray10", "gray90"))
                    self.root.update()
                return

            rounds = loaded_mag.get("rounds", [])
            round_count = len(rounds)
            capacity = loaded_mag.get("capacity", "Unknown")

            tip_color = None
            if rounds:
                first_round = rounds[0]
                if isinstance(first_round, dict):
                    tip_color = first_round.get("tip")
                elif isinstance(first_round, str)and "|"in first_round:
                    variant_name = first_round.split("|")[-1].strip()
                    caliber_part = first_round.split("|")[0].strip()
                    try:
                        tbl_path = get_current_table_path()
                        if tbl_path and os.path.exists(tbl_path):
                            with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                                table_data = json.load(f)
                            for ammo in table_data.get("tables", {}).get("ammunition", []):
                                if ammo.get("caliber")==caliber_part or ammo.get("name")==caliber_part:
                                    for var in ammo.get("variants", []):
                                        if var.get("name")==variant_name:
                                            tip_color = var.get("tip")
                                            break
                                    break
                    except Exception:
                        logging.exception("Suppressed exception")

            is_belt =("belt"in(wpn.get("magazinetype", "")or ""))or("belt"in(wpn.get("platform", "")or ""))or("m249"in(wpn.get("platform", "")or ""))
            try:
                if is_belt:
                    logging.debug("check_magazine: skipping magout for belt-fed weapon(platform=%s)", wpn.get("platform"))
                else:
                    self._play_weapon_action_sound(wpn, "magout")
            except Exception:

                if not is_belt:
                    try:
                        self._play_weapon_action_sound(wpn, "magout")
                    except Exception:
                        logging.exception("Suppressed exception")

            ammo_label_ref = current_weapon_state.get("ammo_label_ref")

            if ammo_label_ref:
                ammo_label_ref.configure(text = "Checking magazine...", text_color =("gray10", "gray90"))
                self.root.update()

            time.sleep(2.5)

            if capacity !="Unknown"and capacity >0:
                fill_ratio = round_count /capacity
                is_hc_inspect = False
                try:
                    _tbl_hci = globals().get('table_data', {})
                    if isinstance(_tbl_hci, dict):
                        is_hc_inspect = bool((_tbl_hci.get('additional_settings') or {}).get('hardcore_mode'))
                except Exception:
                    is_hc_inspect = False
                if is_hc_inspect:
                    fuzz = random.uniform(-0.08, 0.08)
                    perceived = max(0.0, min(1.0, fill_ratio + fuzz))
                    if perceived == 0 and round_count == 0:
                        estimation = "Ammo: Empty"
                    elif perceived < 0.15:
                        estimation = "Ammo: Nearly empty"
                    elif perceived < 0.35:
                        estimation = "Ammo: Light"
                    elif perceived < 0.55:
                        estimation = "Ammo: About half"
                    elif perceived < 0.75:
                        estimation = "Ammo: More than half"
                    elif perceived < 0.95:
                        estimation = "Ammo: Heavy"
                    else:
                        estimation = "Ammo: Full"
                else:
                    if fill_ratio ==0:
                        estimation = "Ammo: Empty"
                    elif fill_ratio <0.5:
                        estimation = "Ammo: Less than halfway full"
                    elif fill_ratio ==0.5:
                        estimation = "Ammo: Halfway full"
                    elif fill_ratio <1.0:
                        estimation = "Ammo: More than halfway full"
                    else:
                        estimation = "Ammo: Full"
            else:
                estimation = "Ammo: Unknown capacity"

            self._play_weapon_action_sound(wpn, "magin")

            current_weapon_state["mag_checked"]= True

            next_variant_name = None
            try:
                if rounds:
                    first_r = rounds[0]
                    if isinstance(first_r, dict):
                        next_variant_name = first_r.get("variant")or first_r.get("name")
            except Exception:
                next_variant_name = None
            variant_suffix = f"[{next_variant_name}]"if next_variant_name and round_count >0 else ""

            if ammo_label_ref:
                if tip_color and round_count >0:
                    ammo_label_ref.configure(text = f"{estimation}{variant_suffix}", text_color = tip_color)
                else:
                    ammo_label_ref.configure(text = f"{estimation}{variant_suffix}", text_color =("gray10", "gray90"))
                self.root.update()

        def reload_magazine():

            try:
                wpn_check = current_weapon_state.get("weapon")or {}

                wpn_sounds = wpn_check.get("sounds")or wpn_check.get("sound_folder")or wpn_check.get("ammo_type")
                if wpn_check.get("underbarrel_weapon")or(isinstance(wpn_sounds, str)and "40mm"in wpn_sounds):

                    try:
                        result = self._reload_underbarrel(wpn_check, save_data, combat_reload = False)
                        if result:
                            update_weapon_view()
                        return
                    except Exception:
                        logging.exception("Underbarrel reload failed")
            except Exception:
                logging.exception("Suppressed exception")

            wpn = current_weapon_state["weapon"]

            wpn_mag_system = wpn.get("magazinesystem")or wpn.get("magazinetype")
            wpn_caliber_raw = wpn.get("caliber")
            wpn_calibers = set()
            if isinstance(wpn_caliber_raw, (list, tuple)):
                for c in wpn_caliber_raw:
                    if c:
                        wpn_calibers.add(str(c).lower().strip())
            elif isinstance(wpn_caliber_raw, str)and wpn_caliber_raw:
                wpn_calibers.add(wpn_caliber_raw.lower().strip())

            def _mag_is_compatible(mag_item):

                if not mag_item or not isinstance(mag_item, dict):
                    return False

                mag_system = mag_item.get("magazinesystem")
                if wpn_mag_system and mag_system:
                    if str(mag_system).lower().strip()!=str(wpn_mag_system).lower().strip():
                        return False

                mag_caliber_raw = mag_item.get("caliber")
                mag_calibers = set()
                if isinstance(mag_caliber_raw, (list, tuple)):
                    for c in mag_caliber_raw:
                        if c:
                            mag_calibers.add(str(c).lower().strip())
                elif isinstance(mag_caliber_raw, str)and mag_caliber_raw:
                    mag_calibers.add(mag_caliber_raw.lower().strip())
                if wpn_calibers and mag_calibers:
                    if not wpn_calibers.intersection(mag_calibers):
                        return False

                capacity = mag_item.get("capacity", 0)
                try:
                    capacity = int(capacity)
                except(ValueError, TypeError):
                    capacity = 0
                current_rounds = len(mag_item.get("rounds", []))
                if current_rounds >=capacity:
                    return False
                return True

            all_magazines =[]

            for item in save_data.get("hands", {}).get("items", []):
                if item and "magazinesystem"in item and "capacity"in item:
                    if _mag_is_compatible(item):
                        all_magazines.append(("hands", item))

            for slot_name, eq_item in save_data.get("equipment", {}).items():
                if eq_item:
                    if "items"in eq_item and isinstance(eq_item["items"], list):
                        for item in eq_item["items"]:
                            if item and "magazinesystem"in item and "capacity"in item:
                                if _mag_is_compatible(item):
                                    all_magazines.append(("equipment", item))

                    if "subslots"in eq_item:
                        for subslot in eq_item["subslots"]:
                            if subslot.get("current"):
                                curr = subslot["current"]
                                if "items"in curr and isinstance(curr["items"], list):
                                    for item in curr["items"]:
                                        if item and "magazinesystem"in item and "capacity"in item:
                                            if _mag_is_compatible(item):
                                                all_magazines.append(("equipment", item))

            loaded_mag = wpn.get("loaded")
            if loaded_mag and "magazinesystem"in loaded_mag and "capacity"in loaded_mag:
                if _mag_is_compatible(loaded_mag):
                    all_magazines.append(("loaded", loaded_mag))

            # Also find clips in inventory that are not full
            def _clip_is_compatible(clip_item):
                if not clip_item or not isinstance(clip_item, dict):
                    return False
                if not clip_item.get('clip_type'):
                    return False
                clip_cal_raw = clip_item.get('caliber')
                clip_cals = set()
                if isinstance(clip_cal_raw, (list, tuple)):
                    for c in clip_cal_raw:
                        if c:
                            clip_cals.add(str(c).lower().strip())
                elif isinstance(clip_cal_raw, str) and clip_cal_raw:
                    clip_cals.add(clip_cal_raw.lower().strip())
                if wpn_calibers and clip_cals:
                    if not wpn_calibers.intersection(clip_cals):
                        return False
                clip_cap = int(clip_item.get('capacity', 0) or 0)
                clip_rounds = clip_item.get('rounds', []) or []
                if len(clip_rounds) >= clip_cap:
                    return False
                return True

            for item in save_data.get("hands", {}).get("items", []):
                if item and isinstance(item, dict) and item.get('clip_type') and item.get('capacity'):
                    if _clip_is_compatible(item):
                        all_magazines.append(("hands", item))

            for slot_name, eq_item in save_data.get("equipment", {}).items():
                if eq_item:
                    if "items" in eq_item and isinstance(eq_item["items"], list):
                        for item in eq_item["items"]:
                            if item and isinstance(item, dict) and item.get('clip_type') and item.get('capacity'):
                                if _clip_is_compatible(item):
                                    all_magazines.append(("equipment", item))
                    if "subslots" in eq_item:
                        for subslot in eq_item["subslots"]:
                            if subslot.get("current"):
                                curr = subslot["current"]
                                if "items" in curr and isinstance(curr["items"], list):
                                    for item in curr["items"]:
                                        if item and isinstance(item, dict) and item.get('clip_type') and item.get('capacity'):
                                            if _clip_is_compatible(item):
                                                all_magazines.append(("equipment", item))

            if not all_magazines:
                msg = "No compatible magazines found!\n\nMake sure you have magazines that:\n• Match the weapon's magazine system"
                if wpn_mag_system:
                    msg +=f"({wpn_mag_system})"
                msg +="\n• Match the weapon's caliber"
                if wpn_calibers:
                    msg +=f"({', '.join(wpn_calibers)})"
                msg +="\n• Are not already full"
                self._popup_show_info("Reload Magazine", msg)
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Select Magazine to Reload")
            popup.transient(self.root)
            self._center_popup_on_window(popup, 550, 500)

            label = customtkinter.CTkLabel(
            popup,
            text = "Select a magazine to reload with rounds:",
            font = customtkinter.CTkFont(size = 13),
            wraplength = 500
            )
            label.pack(pady = 10, padx = 20)

            scroll_frame = customtkinter.CTkScrollableFrame(popup, fg_color = "transparent")
            scroll_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

            selected_mag = customtkinter.StringVar(value = "0")

            for idx, (location, mag_item)in enumerate(all_magazines):
                mag_name = mag_item.get("name", "Unknown Magazine")
                capacity = mag_item.get("capacity", "?")
                mag_rounds_list = mag_item.get("rounds", [])
                rounds = len(mag_rounds_list)
                is_clip_item = bool(mag_item.get('clip_type'))
                mag_system = mag_item.get("clip_type") if is_clip_item else mag_item.get("magazinesystem", "Unknown")
                _next_var = ""
                if mag_rounds_list and isinstance(mag_rounds_list, list)and len(mag_rounds_list)>0:
                    _nr = mag_rounds_list[0]
                    if isinstance(_nr, dict):
                        _nv = _nr.get("variant")or _nr.get("name")
                        if _nv:
                            _next_var = f"[next: {_nv}]"

                radio_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
                radio_frame.pack(fill = "x", pady = 5, padx = 5)

                _type_label = "Clip" if is_clip_item else "Mag"
                radio_text = f"{mag_name}({rounds}/{capacity}) - {mag_system} - {location} [{_type_label}]{_next_var}"
                radio = customtkinter.CTkRadioButton(
                radio_frame,
                text = radio_text,
                variable = selected_mag,
                value = str(idx),
                font = customtkinter.CTkFont(size = 11)
                )
                radio.pack(anchor = "w")

            def reload_selected():
                if not selected_mag.get():
                    self._popup_show_info("Reload Magazine", "Please select a magazine!")
                    return

                idx = int(selected_mag.get())
                location, mag_item = all_magazines[idx]

                # If this is a clip, route to clip editor
                if mag_item.get('clip_type'):
                    try:
                        popup.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")
                    _ed = customtkinter.CTkToplevel(self.root)
                    _ed.title('Clip Loader')
                    _ed.transient(self.root)
                    _open_clip_round_editor(mag_item, 'load', _ed)
                    return

                capacity = mag_item.get("capacity", 0)
                current_rounds = len(mag_item.get("rounds", []))

                if current_rounds >=capacity:
                    self._popup_show_info("Reload Magazine", f"Magazine is already full({current_rounds}/{capacity})")
                    return

                mcal = mag_item.get('caliber')
                mag_cals = set()
                if isinstance(mcal, (list, tuple)):
                    for c in mcal:
                        if c:
                            mag_cals.add(str(c).lower().strip())
                elif isinstance(mcal, str)and mcal:
                    mag_cals.add(mcal.lower().strip())

                filter_calibers = wpn_calibers if wpn_calibers else mag_cals

                def _get_available_rounds_by_variant():

                    variants = {}

                    def _caliber_matches(item_cal):

                        if not filter_calibers:
                            return True
                        if not item_cal:
                            return False
                        item_cal_str = str(item_cal).lower().strip()
                        return item_cal_str in filter_calibers

                    def _get_variant_name(itm):

                        variant = itm.get('variant')
                        if variant:
                            return str(variant)

                        name = itm.get('name')
                        if name:
                            return str(name)
                        return 'Unknown'

                    def _process_item(itm):

                        if not itm or not isinstance(itm, dict):
                            return
                        if itm.get('magazinesystem')or itm.get('capacity'):
                            return

                        itm_cal = itm.get('caliber')
                        if not _caliber_matches(itm_cal):
                            return

                        rds = itm.get('rounds')
                        if isinstance(rds, list)and rds:
                            for r in rds:
                                if isinstance(r, dict):
                                    r_cal = r.get('caliber')
                                    if not _caliber_matches(r_cal):
                                        continue
                                    variant = _get_variant_name(r)
                                    variants[variant]= variants.get(variant, 0)+1
                            return

                        qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                        if qty >0:
                            variant = _get_variant_name(itm)
                            variants[variant]= variants.get(variant, 0)+qty
                            return

                        if itm.get('caliber'):
                            variant = _get_variant_name(itm)
                            variants[variant]= variants.get(variant, 0)+1

                    for itm in save_data.get('hands', {}).get('items', []):
                        _process_item(itm)

                    for slot_name, eq_item in save_data.get('equipment', {}).items():
                        if not eq_item or not isinstance(eq_item, dict):
                            continue

                        for itm in eq_item.get('items', [])or[]:
                            _process_item(itm)

                        for sub in eq_item.get('subslots', [])or[]:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                for itm in curr.get('items', [])or[]:
                                    _process_item(itm)

                    return variants

                try:
                    available_by_variant = _get_available_rounds_by_variant()
                except Exception:
                    available_by_variant = {}

                total_available = sum(available_by_variant.values())

                if total_available <=0:
                    cal_str = ", ".join(sorted(filter_calibers))if filter_calibers else "compatible caliber"
                    self._popup_show_info("Reload Magazine", f"No loose rounds in hands matching {cal_str}")
                    return

                try:
                    popup.destroy()
                except Exception:
                    logging.exception("Suppressed exception")

                def _open_magazine_editor():
                    import tkinter as _tk_mag
                    try:
                        _is_loaded_mag_editor = (location == 'loaded')
                        _was_chamber_empty = not bool(wpn.get('chambered'))
                        if _is_loaded_mag_editor:
                            try:
                                self._play_weapon_action_sound(wpn, 'magout', block = True)
                            except Exception:
                                logging.exception("Suppressed exception")

                        editor = customtkinter.CTkToplevel(self.root)
                        editor.title('Magazine Loader')
                        editor.transient(self.root)
                        cap = int(mag_item.get('capacity', 0)or 0)
                        existing = list(mag_item.get('rounds', [])or[])

                        SLOT_H = 28
                        SLOT_W = 260
                        ox_mag = 20

                        vlist = sorted(available_by_variant.keys())
                        cpal =['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                        vcols = {v:cpal[i %len(cpal)]for i, v in enumerate(vlist)}

                        vtips = {}
                        arm_v2c = {}
                        try:
                            _mcals = mag_item.get('caliber')
                            if isinstance(_mcals, str):
                                _mcals = [_mcals]
                            elif not isinstance(_mcals, list):
                                _mcals = []
                            _ammo_tbl = self._get_ammo_table_data()
                            for _atbl in _ammo_tbl:
                                _ac = _atbl.get('caliber')
                                _ac_list = [_ac] if isinstance(_ac, str) else (_ac if isinstance(_ac, list) else [])
                                _ac_str = _ac_list[0] if _ac_list else None
                                _match = any(c in _ac_list for c in _mcals) if _mcals else False
                                if _match and _ac_str:
                                    for _av in _atbl.get('variants', []):
                                        _atn = _av.get('name')
                                        if _atn:
                                            arm_v2c[_atn] = _ac_str
                                            _att = _av.get('tip')
                                            if _att and isinstance(_att, str) and _att.startswith('#'):
                                                vtips[_atn] = _att
                        except Exception:
                            logging.exception("Suppressed exception")
                        _arm_cg_raw = {}
                        for _vn_a in vlist:
                            _arm_cg_raw.setdefault(arm_v2c.get(_vn_a, 'Unknown'), []).append(_vn_a)
                        arm_caliber_order = sorted(_arm_cg_raw.keys())
                        arm_caliber_groups = {k: sorted(v) for k, v in _arm_cg_raw.items()}

                        def _tip_for(vn):
                            return vtips.get(vn, '#e0c060')

                        def _tip_ol_for(vn):
                            tc = vtips.get(vn)
                            if not tc:
                                return '#aa8820'
                            try:
                                r_v = int(tc[1:3], 16)
                                g_v = int(tc[3:5], 16)
                                b_v = int(tc[5:7], 16)
                                return f'#{max(0, r_v -40):02x}{max(0, g_v -40):02x}{max(0, b_v -40):02x}'
                            except Exception:
                                return '#aa8820'

                        def _tip_for_round(r):
                            if isinstance(r, dict):
                                vn = r.get('variant')or r.get('name')or 'Unknown'
                                return _tip_for(vn)
                            return '#e0c060'

                        def _tip_ol_for_round(r):
                            if isinstance(r, dict):
                                vn = r.get('variant')or r.get('name')or 'Unknown'
                                return _tip_ol_for(vn)
                            return '#aa8820'

                        CHIP_W, CHIP_H, CHIP_PAD = 130, 28, 6
                        ARM_CAL_HEADER_H = 18
                        ARM_CAL_GROUP_PAD = 8
                        _cols = max(1, (SLOT_W +40)//(CHIP_W +CHIP_PAD))
                        _arm_sel_h = 22
                        for _arm_cg in arm_caliber_order:
                            _arm_cg_rows = max(1, (len(arm_caliber_groups[_arm_cg]) + _cols - 1) // _cols)
                            _arm_sel_h += ARM_CAL_HEADER_H + _arm_cg_rows * (CHIP_H + CHIP_PAD) + ARM_CAL_GROUP_PAD
                        SEL_H = _arm_sel_h + 4
                        HINT_H = 22
                        MAG_TOP = SEL_H +HINT_H
                        SPRING_H = 14
                        canvas_h = MAG_TOP +cap *SLOT_H +SPRING_H +8
                        canvas_w = SLOT_W +40

                        main_frame = customtkinter.CTkFrame(editor)
                        main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                        effective_h = min(canvas_h, 650)
                        mag_canvas = _tk_mag.Canvas(main_frame, width = canvas_w, height = effective_h, bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                        if canvas_h >650:
                            _mc_scroll = _tk_mag.Scrollbar(main_frame, orient = 'vertical', command = mag_canvas.yview)
                            _mc_scroll.pack(side = 'right', fill = 'y')
                            mag_canvas.configure(yscrollcommand = _mc_scroll.set, scrollregion =(0, 0, canvas_w, canvas_h))
                        mag_canvas.pack(side = 'left', fill = 'both', expand = True)

                        side = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 180)
                        side.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                        ls = {'dragging':False, 'drag_vn':None, 'di':None, 'dt':None, 'do':None,
                        'added':0, 'stoggle':0, 'animating':False}

                        chip_hitboxes = {}

                        def _draw_chips():
                            mag_canvas.delete('chips')
                            chip_hitboxes.clear()
                            mag_canvas.create_text(canvas_w //2, 10, text = 'AVAILABLE ROUNDS', fill = '#888888',
                            font =('Consolas', 9, 'bold'), tags = 'chips')
                            if not vlist:
                                mag_canvas.create_text(canvas_w //2, SEL_H //2 +10, text = 'No rounds available',
                                fill = '#555555', font =('Consolas', 9), tags = 'chips')
                                return
                            cur_y = 22
                            for cal in arm_caliber_order:
                                cal_vns = arm_caliber_groups[cal]
                                mag_canvas.create_text(6, cur_y + ARM_CAL_HEADER_H // 2, text = cal, fill = '#99aacc',
                                font = ('Consolas', 9, 'bold'), anchor = 'w', tags = 'chips')
                                cur_y += ARM_CAL_HEADER_H
                                start_x = (canvas_w - min(len(cal_vns), _cols) * (CHIP_W + CHIP_PAD) + CHIP_PAD) // 2
                                for idx, vn in enumerate(cal_vns):
                                    cnt = available_by_variant.get(vn, 0)
                                    row_i = idx //_cols
                                    col_i = idx %_cols
                                    x1 = start_x +col_i *(CHIP_W +CHIP_PAD)
                                    y1 = cur_y +row_i *(CHIP_H +CHIP_PAD)
                                    x2 = x1 +CHIP_W
                                    y2 = y1 +CHIP_H
                                    chip_hitboxes[vn]=(x1, y1, x2, y2)
                                    c = vcols.get(vn, '#c4a032')
                                    is_avail = cnt >0
                                    fill = c if is_avail else '#2a2a2a'
                                    ol = '#dddddd'if is_avail else '#3a3a3a'
                                    mag_canvas.create_rectangle(x1, y1, x2, y2, fill = fill, outline = ol, width = 1, tags = 'chips')
                                    mag_canvas.create_oval(x1 +3, y1 +3, x1 +19, y2 -3, fill = _tip_for(vn)if is_avail else '#3a3a3a',
                                    outline = _tip_ol_for(vn)if is_avail else '#3a3a3a', tags = 'chips')
                                    disp = vn if len(vn)<=11 else vn[:10]+'\u2026'
                                    mag_canvas.create_text((x1 +x2)//2 +8, (y1 +y2)//2,
                                    text = f'{disp} x{cnt}',
                                    fill = '#1a1a1a'if is_avail else '#555555',
                                    font =('Consolas', 8, 'bold'), tags = 'chips')
                                arm_rows_for_cal = max(1, (len(cal_vns) + _cols - 1) // _cols)
                                cur_y += arm_rows_for_cal * (CHIP_H + CHIP_PAD) + ARM_CAL_GROUP_PAD

                        def _draw_mag_body():
                            mag_canvas.delete('mag')
                            oy = MAG_TOP
                            mag_canvas.create_text(canvas_w //2, MAG_TOP -10, text = '\u2193 DROP INTO MAGAZINE \u2193',
                            fill = '#555555', font =('Consolas', 9), tags = 'mag')
                            mag_canvas.create_rectangle(ox_mag, oy, ox_mag +SLOT_W, oy +cap *SLOT_H,
                            outline = '#888888', width = 2, tags = 'mag')
                            mag_canvas.create_line(ox_mag, oy, ox_mag -15, oy -8, fill = '#888888', width = 2, tags = 'mag')
                            mag_canvas.create_line(ox_mag +SLOT_W, oy, ox_mag +SLOT_W +15, oy -8,
                            fill = '#888888', width = 2, tags = 'mag')
                            for i in range(cap):
                                sy = oy +i *SLOT_H
                                if i >0:
                                    mag_canvas.create_line(ox_mag, sy, ox_mag +SLOT_W, sy, fill = '#444444',
                                    dash =(2, 2), tags = 'mag')
                                if i <len(existing):
                                    r = existing[i]
                                    vn = r.get('variant')if isinstance(r, dict)else str(r)if r else 'Unknown'
                                    c = vcols.get(vn, '#c4a032')
                                    mag_canvas.create_rectangle(ox_mag +2, sy +2, ox_mag +SLOT_W -2, sy +SLOT_H -2,
                                    fill = c, outline = '#222222', tags = 'mag')
                                    mag_canvas.create_oval(ox_mag +4, sy +4, ox_mag +22, sy +SLOT_H -4,
                                    fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'mag')
                                    mag_canvas.create_text(ox_mag +SLOT_W //2 +10, sy +SLOT_H //2, text = vn, # type: ignore
                                    fill = '#1a1a1a', font =('Consolas', 9, 'bold'), tags = 'mag')
                                else:
                                    mag_canvas.create_text(ox_mag +SLOT_W //2, sy +SLOT_H //2, text = '[empty]',
                                    fill = '#444444', font =('Consolas', 9), tags = 'mag')
                            by = oy +cap *SLOT_H
                            mag_canvas.create_rectangle(ox_mag, by, ox_mag +SLOT_W, by +SPRING_H,
                            fill = '#555555', outline = '#666666', tags = 'mag')
                            mag_canvas.create_text(ox_mag +SLOT_W //2, by +SPRING_H //2,
                            text = '\u25b2 SPRING \u25b2', fill = '#888888',
                            font =('Consolas', 8), tags = 'mag')

                        def _draw_all():
                            _draw_chips()
                            _draw_mag_body()

                        def _take_round(vname):
                            for hi in range(len(save_data.get('hands', {}).get('items', []))-1, -1, -1):
                                itm = save_data['hands']['items'][hi]
                                try:
                                    if not itm or not isinstance(itm, dict):
                                        continue
                                    rds = itm.get('rounds')
                                    if isinstance(rds, list)and rds:
                                        for ri, r in enumerate(rds):
                                            rv =(r.get('variant')if isinstance(r, dict)else(str(r)if r else None))
                                            if rv ==vname:
                                                return rds.pop(ri)
                                    qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                                    if qty >0:
                                        nm = itm.get('variant')or itm.get('name')or itm.get('caliber')
                                        if nm and str(nm)==vname:
                                            itm['quantity']= qty -1
                                            return {k:v for k, v in itm.items()if k !='quantity'}
                                    if itm.get('caliber')and(itm.get('variant')or itm.get('name'))and(itm.get('variant')==vname or itm.get('name')==vname):
                                        try:
                                            save_data['hands']['items'].pop(hi)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                                    continue
                            for _sn_eq, eq_item in list(save_data.get('equipment', {}).items()):
                                if not eq_item or not isinstance(eq_item, dict):
                                    continue
                                for cidx in range(len(eq_item.get('items', []))-1, -1, -1):
                                    try:
                                        itm = eq_item['items'][cidx]
                                        if not itm or not isinstance(itm, dict):
                                            continue
                                        rds = itm.get('rounds')
                                        if isinstance(rds, list)and rds:
                                            for ri, r in enumerate(rds):
                                                rv =(r.get('variant')if isinstance(r, dict)else(str(r)if r else None))
                                                if rv ==vname:
                                                    return rds.pop(ri)
                                        qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                                        if qty >0:
                                            nm = itm.get('variant')or itm.get('name')or itm.get('caliber')
                                            if nm and str(nm)==vname:
                                                itm['quantity']= qty -1
                                                return {k:v for k, v in itm.items()if k !='quantity'}
                                    except Exception:
                                        logging.exception("Suppressed exception")
                            return None

                        def _play_insert():
                            try:
                                sn = f"bulletinsert{ls['stoggle']}"
                                ls['stoggle']= 1 -ls['stoggle']
                                self._play_weapon_action_sound(wpn, sn, block = False)
                            except Exception:
                                logging.exception("Suppressed exception")

                        def _do_insert_data(vname):
                            if len(existing)>=cap:
                                return False
                            r = _take_round(vname)
                            if r is None:
                                return False
                            existing.insert(0, r)
                            ls['added']+=1
                            if vname in available_by_variant:
                                available_by_variant[vname]-=1
                                if available_by_variant[vname]<=0:
                                    del available_by_variant[vname]
                            _play_insert()
                            return True

                        def _hit_chip(x, y):
                            for vn, (x1, y1, x2, y2)in chip_hitboxes.items():
                                if x1 <=x <=x2 and y1 <=y <=y2 and available_by_variant.get(vn, 0)>0:
                                    return vn
                            return None

                        def _on_press(event):
                            if ls['animating']or len(existing)>=cap:
                                return
                            vn = _hit_chip(event.x, event.y)
                            if not vn:
                                return
                            ls['dragging']= True
                            ls['drag_vn']= vn
                            c = vcols.get(vn, '#c4a032')
                            ls['di']= mag_canvas.create_rectangle(
                            ox_mag +2, event.y -SLOT_H //2, ox_mag +SLOT_W -2, event.y +SLOT_H //2,
                            fill = c, outline = '#ffffff', width = 2, tags = 'drag')
                            ls['do']= mag_canvas.create_oval(
                            ox_mag +4, event.y -SLOT_H //2 +2, ox_mag +22, event.y +SLOT_H //2 -2,
                            fill = _tip_for(vn), outline = _tip_ol_for(vn), tags = 'drag')
                            ls['dt']= mag_canvas.create_text(
                            ox_mag +SLOT_W //2 +10, event.y,
                            text = vn, fill = '#1a1a1a', font =('Consolas', 10, 'bold'), tags = 'drag')

                        def _on_move(event):
                            if not ls['dragging']:
                                return
                            y = event.y
                            ls_di, ls_do, ls_dt = ls['di'], ls['do'], ls['dt']
                            if ls_di and ls_dt and ls_do:
                                mag_canvas.coords(ls_di, ox_mag +2, y -SLOT_H //2,
                                ox_mag +SLOT_W -2, y +SLOT_H //2)
                                mag_canvas.coords(ls_do, ox_mag +4, y -SLOT_H //2 +2,
                                ox_mag +22, y +SLOT_H //2 -2)
                                mag_canvas.coords(ls_dt, ox_mag +SLOT_W //2 +10, y)

                        def _on_release(event):
                            if not ls['dragging']:
                                return
                            ls['dragging']= False
                            mag_canvas.delete('drag')
                            ls['di']= ls['dt']= ls['do']= None
                            if len(existing)>=cap or ls['animating']:
                                return
                            vn = ls['drag_vn']
                            if not vn or available_by_variant.get(vn, 0)<=0:
                                return
                            if event.y >=MAG_TOP -15:
                                _animate_push_insert(vn)

                        def _animate_push_insert(vname):
                            ls['animating']= True
                            oy = MAG_TOP
                            n_ex = len(existing)
                            c_new = vcols.get(vname, '#c4a032')

                            mag_canvas.delete('mag')
                            mag_canvas.create_text(canvas_w //2, MAG_TOP -10, text = '\u2193 DROP INTO MAGAZINE \u2193',
                            fill = '#555555', font =('Consolas', 9), tags = 'magshell')
                            mag_canvas.create_rectangle(ox_mag, oy, ox_mag +SLOT_W, oy +cap *SLOT_H,
                            outline = '#888888', width = 2, tags = 'magshell')
                            mag_canvas.create_line(ox_mag, oy, ox_mag -15, oy -8, fill = '#888888', width = 2, tags = 'magshell')
                            mag_canvas.create_line(ox_mag +SLOT_W, oy, ox_mag +SLOT_W +15, oy -8,
                            fill = '#888888', width = 2, tags = 'magshell')
                            for si in range(1, cap):
                                _sy = oy +si *SLOT_H
                                mag_canvas.create_line(ox_mag, _sy, ox_mag +SLOT_W, _sy, fill = '#444444',
                                dash =(2, 2), tags = 'magshell')
                            _by = oy +cap *SLOT_H
                            mag_canvas.create_rectangle(ox_mag, _by, ox_mag +SLOT_W, _by +SPRING_H,
                            fill = '#555555', outline = '#666666', tags = 'magshell')
                            mag_canvas.create_text(ox_mag +SLOT_W //2, _by +SPRING_H //2,
                            text = '\u25b2 SPRING \u25b2', fill = '#888888',
                            font =('Consolas', 8), tags = 'magshell')
                            for ei in range(n_ex, cap):
                                _esy = oy +ei *SLOT_H
                                mag_canvas.create_text(ox_mag +SLOT_W //2, _esy +SLOT_H //2, text = '[empty]',
                                fill = '#444444', font =('Consolas', 9), tags = 'magshell')

                            anim_ids =[]
                            for i in range(n_ex):
                                r = existing[i]
                                vn_e = r.get('variant')if isinstance(r, dict)else str(r)if r else 'Unknown'
                                c_e = vcols.get(vn_e, '#c4a032')
                                sy = oy +i *SLOT_H
                                _ri = mag_canvas.create_rectangle(ox_mag +2, sy +2, ox_mag +SLOT_W -2, sy +SLOT_H -2,
                                fill = c_e, outline = '#222222', tags = 'pushanim')
                                _oi = mag_canvas.create_oval(ox_mag +4, sy +4, ox_mag +22, sy +SLOT_H -4,
                                fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'pushanim')
                                _ti = mag_canvas.create_text(ox_mag +SLOT_W //2 +10, sy +SLOT_H //2, text = vn_e, # type: ignore
                                fill = '#1a1a1a', font =('Consolas', 9, 'bold'), tags = 'pushanim')
                                anim_ids.append((_ri, _oi, _ti, float(sy)))

                            new_start_y = float(oy -SLOT_H -4)
                            new_target_y = float(oy)
                            _nr = mag_canvas.create_rectangle(ox_mag +2, new_start_y +2, ox_mag +SLOT_W -2,
                            new_start_y +SLOT_H -2, fill = c_new,
                            outline = '#ffffff', width = 2, tags = 'pushanim')
                            _no = mag_canvas.create_oval(ox_mag +4, new_start_y +4, ox_mag +22,
                            new_start_y +SLOT_H -4, fill = _tip_for(vname),
                            outline = _tip_ol_for(vname), tags = 'pushanim')
                            _nt = mag_canvas.create_text(ox_mag +SLOT_W //2 +10, new_start_y +SLOT_H //2,
                            text = vname, fill = '#1a1a1a',
                            font =('Consolas', 10, 'bold'), tags = 'pushanim')

                            total_steps = 10
                            push_per_step = float(SLOT_H)/total_steps
                            new_per_step =(new_target_y -new_start_y)/total_steps

                            def _push_step(step):
                                if step >=total_steps:
                                    mag_canvas.delete('pushanim')
                                    mag_canvas.delete('magshell')
                                    _do_insert_data(vname)
                                    _draw_all()
                                    _update_side()
                                    ls['animating']= False
                                    return
                                frac = step +1
                                for _ri, _oi, _ti, base_y in anim_ids:
                                    cy = base_y +frac *push_per_step
                                    mag_canvas.coords(_ri, ox_mag +2, cy +2, ox_mag +SLOT_W -2, cy +SLOT_H -2)
                                    mag_canvas.coords(_oi, ox_mag +4, cy +4, ox_mag +22, cy +SLOT_H -4)
                                    mag_canvas.coords(_ti, ox_mag +SLOT_W //2 +10, cy +SLOT_H //2)
                                cn = new_start_y +frac *new_per_step
                                mag_canvas.coords(_nr, ox_mag +2, cn +2, ox_mag +SLOT_W -2, cn +SLOT_H -2)
                                mag_canvas.coords(_no, ox_mag +4, cn +4, ox_mag +22, cn +SLOT_H -4)
                                mag_canvas.coords(_nt, ox_mag +SLOT_W //2 +10, cn +SLOT_H //2)
                                editor.after(25, lambda:_push_step(step +1))

                            _push_step(0)

                        mag_canvas.bind('<Button-1>', _on_press)
                        mag_canvas.bind('<B1-Motion>', _on_move)
                        mag_canvas.bind('<ButtonRelease-1>', _on_release)

                        _cap_lbl = customtkinter.CTkLabel(side, text = f'{len(existing)}/{cap} rounds loaded',
                        font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                        _cap_lbl.pack(pady =(10, 6))

                        customtkinter.CTkLabel(side, text = 'Click & drag a round\nfrom the top area down\ninto the magazine',
                        font = customtkinter.CTkFont(size = 10), text_color = '#888888',
                        wraplength = 170).pack(pady = 6)

                        def _update_side():
                            _cap_lbl.configure(text = f'{len(existing)}/{cap} rounds loaded')

                        _has_reloader = self._check_for_reloader_item(save_data)
                        _reloader_state = {'hooked': False, 'channel': None, 'sound': None, 'btn': None, 'unhook_btn': None}

                        def _stop_reloader_sound():
                            if _reloader_state['channel']:
                                try:
                                    _reloader_state['channel'].stop()
                                except Exception:
                                    logging.exception("Suppressed exception")
                                _reloader_state['channel'] = None

                        def _start_reloader_loop():
                            try:
                                rpath = os.path.join('sounds', 'firearms', 'universal', 'reloaderloop.ogg')
                                if os.path.exists(rpath):
                                    snd = pygame.mixer.Sound(rpath)
                                    ch = pygame.mixer.find_channel()
                                    if ch:
                                        ch.play(snd, loops = -1)
                                        _reloader_state['channel'] = ch
                                        _reloader_state['sound'] = snd
                            except Exception:
                                logging.exception("Suppressed exception")

                        def _play_reloader_insert():
                            try:
                                rpath = os.path.join('sounds', 'firearms', 'universal', 'reloaderroundinsert.ogg')
                                if os.path.exists(rpath):
                                    snd = pygame.mixer.Sound(rpath)
                                    ch = pygame.mixer.find_channel()
                                    if ch:
                                        ch.play(snd)
                                        return int(snd.get_length() * 1000)
                            except Exception:
                                logging.exception("Suppressed exception")
                            return 0

                        def _reloader_auto_fill(vname):
                            if ls['animating']:
                                return
                            _reloader_state['hooked'] = True
                            ls['animating'] = True
                            if _reloader_state.get('btn'):
                                try:
                                    _reloader_state['btn'].configure(state = 'disabled')
                                except Exception:
                                    logging.exception("Suppressed exception")

                            insert_dur = _play_reloader_insert()

                            def _start_loop_and_fill():
                                _start_reloader_loop()
                                _reloader_fill_step(vname)

                            editor.after(max(insert_dur, 100), _start_loop_and_fill)

                        def _reloader_fill_step(vname):
                            if len(existing) >= cap or available_by_variant.get(vname, 0) <= 0:
                                _stop_reloader_sound()
                                ls['animating'] = False
                                _draw_all()
                                _update_side()
                                if _reloader_state.get('unhook_btn'):
                                    try:
                                        _reloader_state['unhook_btn'].configure(state = 'normal')
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                return
                            r = _take_round(vname)
                            if r is None:
                                _stop_reloader_sound()
                                ls['animating'] = False
                                _draw_all()
                                _update_side()
                                if _reloader_state.get('unhook_btn'):
                                    try:
                                        _reloader_state['unhook_btn'].configure(state = 'normal')
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                return
                            existing.insert(0, r)
                            ls['added'] += 1
                            if vname in available_by_variant:
                                available_by_variant[vname] -= 1
                                if available_by_variant[vname] <= 0:
                                    del available_by_variant[vname]
                            _play_insert()
                            _draw_all()
                            _update_side()
                            editor.after(100, lambda: _reloader_fill_step(vname))

                        def _unhook_reloader():
                            _stop_reloader_sound()
                            _reloader_state['hooked'] = False
                            ls['animating'] = False
                            if _reloader_state.get('btn'):
                                try:
                                    _reloader_state['btn'].configure(state = 'normal')
                                except Exception:
                                    logging.exception("Suppressed exception")
                            if _reloader_state.get('unhook_btn'):
                                try:
                                    _reloader_state['unhook_btn'].configure(state = 'disabled')
                                except Exception:
                                    logging.exception("Suppressed exception")
                            _play_reloader_insert()

                        def _use_reloader():
                            if ls['animating'] or _reloader_state['hooked']:
                                return
                            avail_vnames = [v for v in vlist if available_by_variant.get(v, 0) > 0]
                            if not avail_vnames:
                                self._popup_show_info('Reloader', 'No rounds available to load')
                                return
                            if len(avail_vnames) == 1:
                                _reloader_auto_fill(avail_vnames[0])
                                return
                            _arm_avail_cg = {}
                            for vn in avail_vnames:
                                cal = arm_v2c.get(vn, 'Unknown')
                                _arm_avail_cg.setdefault(cal, []).append(vn)
                            _arm_calibers = sorted(_arm_avail_cg.keys())
                            def _arm_open_variant_picker(cal_vns):
                                sel_popup = customtkinter.CTkToplevel(editor)
                                sel_popup.title('Select Round Type')
                                sel_popup.transient(editor)
                                sel_popup.grab_set()
                                customtkinter.CTkLabel(sel_popup, text = 'Select variant for reloader:', font = customtkinter.CTkFont(size = 12)).pack(pady = 8)
                                sel_var = customtkinter.StringVar(value = cal_vns[0])
                                sf = customtkinter.CTkScrollableFrame(sel_popup, height = min(240, len(cal_vns) * 36 + 10), width = 260)
                                sf.pack(fill = 'x', padx = 8, pady = 4)
                                for vn in cal_vns:
                                    cnt = available_by_variant.get(vn, 0)
                                    customtkinter.CTkRadioButton(sf, text = f'{vn} (x{cnt})', variable = sel_var, value = vn).pack(anchor = 'w', padx = 8, pady = 2)
                                def _go():
                                    v = sel_var.get()
                                    sel_popup.destroy()
                                    _reloader_auto_fill(v)
                                customtkinter.CTkButton(sel_popup, text = 'Hook Up & Load', command = _go, width = 160).pack(pady = 8)
                                customtkinter.CTkButton(sel_popup, text = 'Cancel', command = sel_popup.destroy, width = 120, fg_color = '#444444').pack(pady = 4)
                                sel_popup.update_idletasks()
                                _sw2 = sel_popup.winfo_screenwidth(); _sh2 = sel_popup.winfo_screenheight()
                                _pw = sel_popup.winfo_reqwidth(); _ph = sel_popup.winfo_reqheight()
                                sel_popup.geometry(f'+{_sw2 // 2 - _pw // 2}+{max(0, _sh2 // 2 - _ph // 2)}')
                                sel_popup.lift()
                                self._safe_focus(sel_popup)
                            if len(_arm_calibers) == 1:
                                _arm_open_variant_picker(avail_vnames)
                                return
                            cal_popup = customtkinter.CTkToplevel(editor)
                            cal_popup.title('Select Caliber')
                            cal_popup.transient(editor)
                            cal_popup.grab_set()
                            customtkinter.CTkLabel(cal_popup, text = 'Select caliber to load:', font = customtkinter.CTkFont(size = 12)).pack(pady = 8)
                            for cal in _arm_calibers:
                                cal_vns = list(_arm_avail_cg[cal])
                                cnt_total = sum(available_by_variant.get(vn, 0) for vn in cal_vns)
                                def _pick_arm(cv = cal_vns, ct = cnt_total):
                                    cal_popup.destroy()
                                    _arm_open_variant_picker(cv)
                                customtkinter.CTkButton(cal_popup, text = f'{cal}  ({cnt_total} rds)', command = _pick_arm, width = 240, height = 32).pack(padx = 16, pady = 4)
                            customtkinter.CTkButton(cal_popup, text = 'Cancel', command = cal_popup.destroy, width = 120, fg_color = '#444444').pack(pady = 8)
                            cal_popup.update_idletasks()
                            _sw3 = cal_popup.winfo_screenwidth(); _sh3 = cal_popup.winfo_screenheight()
                            _cw = cal_popup.winfo_reqwidth(); _ch2 = cal_popup.winfo_reqheight()
                            cal_popup.geometry(f'+{_sw3 // 2 - _cw // 2}+{max(0, _sh3 // 2 - _ch2 // 2)}')
                            cal_popup.lift()
                            self._safe_focus(cal_popup)

                        if _has_reloader:
                            _reloader_state['btn'] = customtkinter.CTkButton(side, text = '\u2699 Use Reloader', command = _use_reloader, width = 160, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = '#2a6a2a', hover_color = '#3a7a3a')
                            _reloader_state['btn'].pack(pady = 4)
                            _reloader_state['unhook_btn'] = customtkinter.CTkButton(side, text = '\u2716 Unhook Reloader', command = _unhook_reloader, width = 160, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = '#6a2a2a', hover_color = '#7a3a3a', state = 'disabled')
                            _reloader_state['unhook_btn'].pack(pady = 4)

                        def _done():
                            if _reloader_state.get('hooked'):
                                self._popup_show_info('Reloader', 'Please unhook the reloader first!')
                                return
                            _stop_reloader_sound()
                            if ls['added']>0:
                                mag_item['rounds']= existing

                                if _is_loaded_mag_editor:
                                    try:
                                        self._play_weapon_action_sound(wpn, 'magin', block = True)
                                    except Exception:
                                        logging.exception("Suppressed exception")

                                    if _was_chamber_empty and existing:
                                        if bool(wpn.get('bolt_catch')):
                                            try:
                                                self._play_weapon_action_sound(wpn, 'boltforward')
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                        else:
                                            _released = False
                                            try:
                                                _released = bool(self._play_weapon_action_sound_strict(wpn, 'boltrelease', block = True))
                                            except Exception:
                                                _released = False
                                            if not _released:
                                                try:
                                                    self._play_weapon_action_sound(wpn, 'boltback', block = True)
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                                                try:
                                                    self._play_weapon_action_sound(wpn, 'boltforward')
                                                except Exception:
                                                    logging.exception("Suppressed exception")

                            editor.destroy()
                            update_weapon_view()
                            if ls['added']>0:
                                self._popup_show_info('Magazine', f'Added {ls["added"]} rounds to {mag_item.get("name", "magazine")}')

                        editor.protocol('WM_DELETE_WINDOW', _done)
                        customtkinter.CTkButton(side, text = 'Done', command = _done, width = 160, height = 35,
                        font = customtkinter.CTkFont(size = 12)).pack(pady = 10)

                        _draw_all()

                        editor.update_idletasks()
                        ew = max(editor.winfo_reqwidth(), 520)
                        eh = max(editor.winfo_reqheight(), 420)
                        _sw_s = editor.winfo_screenwidth()
                        _sh_s = editor.winfo_screenheight()
                        x =(_sw_s //2)-(ew //2)
                        y =(_sh_s //2)-(eh //2)
                        editor.geometry(f'{ew}x{eh}+{x}+{y}')
                        editor.grab_set()
                        editor.lift()
                        self._safe_focus(editor)
                    except Exception:
                        logging.exception('Failed to open magazine loader')

                _open_magazine_editor()

            button_frame = customtkinter.CTkFrame(popup, fg_color = "transparent")
            button_frame.pack(fill = "x", padx = 10, pady = 10)

            reload_btn = customtkinter.CTkButton(
            button_frame,
            text = "Reload Selected",
            command = reload_selected,
            width = 150,
            height = 40
            )
            reload_btn.pack(side = "left", padx = 5)

            cancel_btn = customtkinter.CTkButton(
            button_frame,
            text = "Cancel",
            command = popup.destroy,
            width = 150,
            height = 40,
            fg_color = "#444444",
            hover_color = "#555555"
            )
            cancel_btn.pack(side = "left", padx = 5)

            popup.update_idletasks()
            popup_width = popup.winfo_reqwidth()
            popup_height = popup.winfo_reqheight()
            screen_width = popup.winfo_screenwidth()
            screen_height = popup.winfo_screenheight()
            x =(screen_width //2)-(popup_width //2)
            y =(screen_height //2)-(popup_height //2)
            popup.geometry(f"+{x}+{y}")
            popup.deiconify()
            popup.grab_set()
            popup.lift()
            self._safe_focus(popup)

        def check_cleanliness():
            import time
            wpn = current_weapon_state["weapon"]
            cleanliness = _get_weapon_cleanliness(combat_state, wpn, default = 100.0, cache_to_state = True)

            self._play_weapon_action_sound(wpn, "boltback", block = True)
            time.sleep(0.3)

            clean_label_ref = current_weapon_state.get("clean_label_ref")

            if clean_label_ref:
                clean_label_ref.configure(text = "Inspecting barrel...")
                self.root.update()

            time.sleep(2.5)

            if cleanliness >=90:
                estimation = "Cleanliness: Pristine"
            elif cleanliness >=70:
                estimation = "Cleanliness: Clean"
            elif cleanliness >=50:
                estimation = "Cleanliness: Dirty"
            elif cleanliness >=30:
                estimation = "Cleanliness: Very dirty"
            else:
                estimation = "Cleanliness: Fouled"

            self._play_weapon_action_sound(wpn, "boltforward")
            time.sleep(0.2)

            loaded_mag = wpn.get("loaded")
            if loaded_mag and loaded_mag.get("rounds"):
                removed_round = loaded_mag["rounds"].pop(0)
                logging.info(f"Removed round during inspection: {removed_round}")

            if clean_label_ref:
                clean_label_ref.configure(text = estimation)
                self.root.update()

        try:
            check_clean_btn = self._create_sound_button(
            actions_frame,
            text = "Check Cleanliness",
            command = check_cleanliness,
            width = 150,
            height = 50,
            font = customtkinter.CTkFont(size = 14)
            )
        except Exception:
            check_clean_btn = None
        try:
            check_mag_btn = self._create_sound_button(
            actions_frame,
            text = "Check Magazine",
            command = check_magazine,
            width = 150,
            height = 50,
            font = customtkinter.CTkFont(size = 14)
            )
        except Exception:
            check_mag_btn = None

        reload_mag_btn = self._create_sound_button(
        actions_frame,
        text = "Magazine Management",

        command = lambda:_show_magazine_popup(),
        width = 150,
        height = 50,
        font = customtkinter.CTkFont(size = 14),
        fg_color = "#1a4d1a",
        hover_color = "#2d7a2d"
        )
        reload_mag_btn.pack(side = "left", padx = 10, pady = 10)
        try:
            current_weapon_state['reload_mag_btn_ref']= reload_mag_btn
        except Exception:
            logging.exception("Suppressed exception")

        def unload_magazine():
            try:
                wpn = current_weapon_state.get('weapon')or {}
                loaded = wpn.get('loaded')
                if not loaded:
                    self._popup_show_info('Unload', 'No magazine loaded to unload')
                    return

                save_data.get('hands', {}).get('items', []).append(loaded)
                wpn['loaded']= None

                self._popup_show_info('Unload', f"Unloaded {loaded.get('name', 'magazine')} to hands")
                update_weapon_view()
            except Exception as e:
                logging.exception('Failed to unload magazine: %s', e)

        unload_btn = self._create_sound_button(actions_frame, text = 'Unload Magazine', command = unload_magazine, width = 150, height = 50, font = customtkinter.CTkFont(size = 14), fg_color = '#444444', hover_color = '#555555')
        try:
            current_weapon_state['unload_mag_btn_ref']= unload_btn
        except Exception:
            logging.exception("Suppressed exception")

        def remove_magazine():
            try:
                import random as _rand
                wpn = current_weapon_state.get('weapon')or {}
                loaded = wpn.get('loaded')
                if not loaded:
                    self._popup_show_info('Remove Magazine', 'No magazine loaded to remove')
                    return

                try:
                    is_belt =("belt"in(wpn.get('magazinetype', '')or ''))or("belt"in(wpn.get('platform', '')or ''))or("m249"in(wpn.get('platform', '')or ''))
                except Exception:
                    is_belt = False

                try:
                    if not is_belt:
                        self._play_weapon_action_sound(wpn, 'magout')
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    time.sleep(_rand.uniform(1, 1.25))
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    self._safe_sound_play("", "sounds/firearms/universal/pouchin.wav")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    save_data.setdefault('hands', {}).setdefault('items', []).append(loaded)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    wpn['loaded']= None
                except Exception:
                    logging.exception("Suppressed exception")

                mag_name = loaded.get('name', 'magazine')if isinstance(loaded, dict)else str(loaded)
                self._popup_show_info('Remove Magazine', f'Removed {mag_name} to hands')
                update_weapon_view()
            except Exception as e:
                logging.exception('Failed to remove magazine: %s', e)

        try:
            remove_btn = self._create_sound_button(actions_frame, text = 'Remove Magazine', command = remove_magazine, width = 150, height = 50, font = customtkinter.CTkFont(size = 14), fg_color = '#8B0000', hover_color = '#A00000')
            remove_btn.pack(side = 'left', padx = 10, pady = 10)
            try:
                current_weapon_state['remove_mag_btn_ref']= remove_btn
            except Exception:
                logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Suppressed exception")

        def _show_magazine_popup():
            try:
                popup = customtkinter.CTkToplevel(self.root)
                popup.title('Magazine')
                popup.geometry('420x220')
                popup.transient(self.root)

                lab = customtkinter.CTkLabel(popup, text = 'Magazine Actions', font = customtkinter.CTkFont(size = 14, weight = 'bold'))
                lab.pack(pady = 8)

                try:
                    wpn_mag_info = current_weapon_state.get('weapon')or {}
                    _loaded_mag_info = wpn_mag_info.get('loaded')
                    _mag_next_variant = None
                    if isinstance(_loaded_mag_info, dict):
                        _mag_rds = _loaded_mag_info.get('rounds', [])
                        if _mag_rds and isinstance(_mag_rds, list)and len(_mag_rds)>0:
                            _mnr = _mag_rds[0]
                            if isinstance(_mnr, dict):
                                _mag_next_variant = _mnr.get('variant')or _mnr.get('name')
                    if _mag_next_variant:
                        customtkinter.CTkLabel(popup, text = f'Next round: {_mag_next_variant}', font = customtkinter.CTkFont(size = 12)).pack(pady = 2)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    load_into_weapon_var = customtkinter.BooleanVar(value = True)
                    load_checkbox = customtkinter.CTkCheckBox(popup, text = 'Load magazine into weapon', variable = load_into_weapon_var)
                    load_checkbox.pack(pady = 4)
                except Exception:
                    load_into_weapon_var = None

                try:
                    wpn_local = current_weapon_state.get('weapon')or {}

                    wpn_mag_system = wpn_local.get("magazinesystem")or wpn_local.get("magazinetype")
                    wpn_caliber_raw = wpn_local.get("caliber")
                    wpn_calibers = set()
                    if isinstance(wpn_caliber_raw, (list, tuple)):
                        for c in wpn_caliber_raw:
                            if c:
                                wpn_calibers.add(str(c).lower().strip())
                    elif isinstance(wpn_caliber_raw, str)and wpn_caliber_raw:
                        wpn_calibers.add(wpn_caliber_raw.lower().strip())

                    def _mag_is_compatible_local(mag_item):

                        if not mag_item or not isinstance(mag_item, dict):
                            return False

                        mag_system = mag_item.get("magazinesystem")
                        if wpn_mag_system and mag_system:
                            if str(mag_system).lower().strip()!=str(wpn_mag_system).lower().strip():
                                return False

                        mag_caliber_raw = mag_item.get("caliber")
                        mag_calibers = set()
                        if isinstance(mag_caliber_raw, (list, tuple)):
                            for c in mag_caliber_raw:
                                if c:
                                    mag_calibers.add(str(c).lower().strip())
                        elif isinstance(mag_caliber_raw, str)and mag_caliber_raw:
                            mag_calibers.add(mag_caliber_raw.lower().strip())
                        if wpn_calibers and mag_calibers:
                            if not wpn_calibers.intersection(mag_calibers):
                                return False

                        capacity = mag_item.get("capacity", 0)
                        try:
                            capacity = int(capacity)
                        except(ValueError, TypeError):
                            capacity = 0
                        current_rounds = len(mag_item.get("rounds", []))
                        if current_rounds >=capacity:
                            return False
                        return True

                    def _hands_have_compatible_rounds_local(wpn):
                        try:
                            def check_container_items(item_iterable):
                                for itm in item_iterable:
                                    try:
                                        if not itm or not isinstance(itm, dict):
                                            continue

                                        if itm.get('magazinesystem')or itm.get('capacity'):
                                            continue
                                        rds = itm.get('rounds')
                                        if isinstance(rds, list)and rds:
                                            return True
                                        qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                                        if qty >0:
                                            return True
                                        if itm.get('caliber'):
                                            return True
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                        continue
                                return False

                            if check_container_items(save_data.get('hands', {}).get('items', [])):
                                return True

                            for slot_name, eq_item in save_data.get('equipment', {}).items():
                                try:
                                    if not eq_item or not isinstance(eq_item, dict):
                                        continue
                                    for itm in eq_item.get('items', [])or[]:
                                        if check_container_items([itm]):
                                            return True
                                    for sub in eq_item.get('subslots', [])or[]:
                                        try:
                                            curr = sub.get('current')
                                            if curr and isinstance(curr, dict):
                                                for itm in curr.get('items', [])or[]:
                                                    if check_container_items([itm]):
                                                        return True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")

                            return False
                        except Exception:
                            return False

                    def _inventory_has_compatible_nonfull_mag():

                        try:
                            def check_nonfull_mag(itm):
                                if not itm or not isinstance(itm, dict):
                                    return False
                                cap = itm.get('capacity')
                                if cap is None:
                                    return False
                                try:
                                    cap_i = int(cap)
                                except Exception:
                                    return False
                                rounds = itm.get('rounds', [])
                                cur = len(rounds)if isinstance(rounds, list)else 0
                                return cur <cap_i

                            for itm in save_data.get('hands', {}).get('items', []):
                                try:
                                    if check_nonfull_mag(itm):
                                        return True
                                except Exception:
                                    logging.exception("Suppressed exception")

                            for slot_name, eq_item in save_data.get('equipment', {}).items():
                                try:
                                    if not eq_item or not isinstance(eq_item, dict):
                                        continue
                                    for itm in eq_item.get('items', [])or[]:
                                        try:
                                            if check_nonfull_mag(itm):
                                                return True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                    for sub in eq_item.get('subslots', [])or[]:
                                        try:
                                            curr = sub.get('current')
                                            if curr and isinstance(curr, dict):
                                                for itm in curr.get('items', [])or[]:
                                                    try:
                                                        if check_nonfull_mag(itm):
                                                            return True
                                                    except Exception:
                                                        logging.exception("Suppressed exception")
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")

                            loaded_mag = wpn_local.get('loaded')
                            if check_nonfull_mag(loaded_mag):
                                return True

                            return False
                        except Exception:
                            return False

                    can_reload = _hands_have_compatible_rounds_local(wpn_local)and _inventory_has_compatible_nonfull_mag()

                    def _inventory_has_mag_with_rounds():

                        try:
                            def check_mag(itm):
                                if not itm or not isinstance(itm, dict):
                                    return False
                                if 'magazinesystem'not in itm and 'capacity'not in itm:
                                    return False
                                rounds = itm.get('rounds', [])
                                return isinstance(rounds, list)and len(rounds)>0

                            for itm in save_data.get('hands', {}).get('items', []):
                                if check_mag(itm):
                                    return True

                            for slot_name, eq_item in save_data.get('equipment', {}).items():
                                try:
                                    if not eq_item or not isinstance(eq_item, dict):
                                        continue
                                    for itm in eq_item.get('items', [])or[]:
                                        if check_mag(itm):
                                            return True
                                    for sub in eq_item.get('subslots', [])or[]:
                                        try:
                                            curr = sub.get('current')
                                            if curr and isinstance(curr, dict):
                                                for itm in curr.get('items', [])or[]:
                                                    if check_mag(itm):
                                                        return True
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")

                            loaded_mag_local = wpn_local.get('loaded')
                            if check_mag(loaded_mag_local):
                                return True

                            return False
                        except Exception:
                            return False

                    can_unload = _inventory_has_mag_with_rounds()
                except Exception:
                    can_reload = False
                    can_unload = False

                def unload_magazine_rounds():

                    try:
                        popup.destroy()
                    except Exception:
                        logging.exception("Suppressed exception")

                    wpn = current_weapon_state.get('weapon')or {}

                    all_magazines =[]

                    def check_mag_has_rounds(itm):
                        if not itm or not isinstance(itm, dict):
                            return False
                        if 'magazinesystem'not in itm and 'capacity'not in itm:
                            return False
                        rounds = itm.get('rounds', [])
                        return isinstance(rounds, list)and len(rounds)>0

                    for item in save_data.get("hands", {}).get("items", []):
                        if check_mag_has_rounds(item):
                            all_magazines.append(("hands", item))

                    for slot_name, eq_item in save_data.get("equipment", {}).items():
                        if eq_item:
                            if "items"in eq_item and isinstance(eq_item["items"], list):
                                for item in eq_item["items"]:
                                    if check_mag_has_rounds(item):
                                        all_magazines.append(("equipment", item))
                            if "subslots"in eq_item:
                                for subslot in eq_item["subslots"]:
                                    if subslot.get("current"):
                                        curr = subslot["current"]
                                        if "items"in curr and isinstance(curr["items"], list):
                                            for item in curr["items"]:
                                                if check_mag_has_rounds(item):
                                                    all_magazines.append(("equipment", item))

                    loaded_mag = wpn.get("loaded")
                    if check_mag_has_rounds(loaded_mag):
                        all_magazines.append(("loaded", loaded_mag))

                    if not all_magazines:
                        self._popup_show_info("Unload Magazine", "No magazines with rounds found!")
                        return

                    unload_popup = customtkinter.CTkToplevel(self.root)
                    unload_popup.title("Select Magazine to Unload")
                    unload_popup.transient(self.root)
                    self._center_popup_on_window(unload_popup, 550, 500)

                    label = customtkinter.CTkLabel(
                    unload_popup,
                    text = "Select a magazine to unload rounds from:",
                    font = customtkinter.CTkFont(size = 13),
                    wraplength = 500
                    )
                    label.pack(pady = 10, padx = 20)

                    scroll_frame = customtkinter.CTkScrollableFrame(unload_popup, fg_color = "transparent")
                    scroll_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

                    selected_mag = customtkinter.StringVar(value = "0")

                    for idx, (location, mag_item)in enumerate(all_magazines):
                        mag_name = mag_item.get("name", "Unknown Magazine")
                        capacity = mag_item.get("capacity", "?")
                        mag_rounds_list = mag_item.get("rounds", [])
                        rounds = len(mag_rounds_list)
                        mag_system = mag_item.get("magazinesystem", "Unknown")
                        _next_var = ""
                        if mag_rounds_list and isinstance(mag_rounds_list, list)and len(mag_rounds_list)>0:
                            _nr = mag_rounds_list[0]
                            if isinstance(_nr, dict):
                                _nv = _nr.get("variant")or _nr.get("name")
                                if _nv:
                                    _next_var = f"[next: {_nv}]"

                        radio_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
                        radio_frame.pack(fill = "x", pady = 5, padx = 5)

                        radio_text = f"{mag_name}({rounds}/{capacity}) - {mag_system} - {location}{_next_var}"
                        radio = customtkinter.CTkRadioButton(
                        radio_frame,
                        text = radio_text,
                        variable = selected_mag,
                        value = str(idx),
                        font = customtkinter.CTkFont(size = 11)
                        )
                        radio.pack(anchor = "w")

                    def unload_selected():
                        if not selected_mag.get():
                            self._popup_show_info("Unload Magazine", "Please select a magazine!")
                            return

                        idx = int(selected_mag.get())
                        location, mag_item = all_magazines[idx]

                        mag_rounds = mag_item.get("rounds", [])
                        current_round_count = len(mag_rounds)
                        if current_round_count <=0:
                            self._popup_show_info("Unload Magazine", "Magazine is already empty")
                            return

                        try:
                            unload_popup.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")

                        is_loaded = (location == "loaded")
                        _open_unload_magazine_editor(mag_item, is_loaded, wpn if is_loaded else None)

                    def _open_unload_magazine_editor(mag_item, is_loaded, weapon_ref):
                        import tkinter as _tk_unl
                        try:
                            ul_editor = customtkinter.CTkToplevel(self.root)
                            ul_editor.title('Magazine Unloader')
                            ul_editor.transient(self.root)
                            cap = int(mag_item.get('capacity', 0) or 0) or 30
                            existing = list(mag_item.get('rounds', []) or [])

                            vset = set()
                            for r in existing:
                                if isinstance(r, dict):
                                    vn = r.get('variant') or r.get('name') or 'Unknown'
                                    vset.add(vn)
                            vlist_unl = sorted(vset)
                            cpal = ['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                            vcols_unl = {v: cpal[i % len(cpal)] for i, v in enumerate(vlist_unl)}

                            vtips_unl = {}
                            try:
                                _ammo_tbl = self._get_ammo_table_data()
                                mag_cal = mag_item.get('caliber')
                                mcal_str = mag_cal if isinstance(mag_cal, str) else (mag_cal[0] if isinstance(mag_cal, list) and mag_cal else None)
                                for _atbl in _ammo_tbl:
                                    _ac = _atbl.get('caliber')
                                    _match = False
                                    if isinstance(_ac, list):
                                        _match = mcal_str in _ac if mcal_str else False
                                    else:
                                        _match = (_ac == mcal_str) if mcal_str else False
                                    if _match:
                                        for _av in _atbl.get('variants', []):
                                            _atn = _av.get('name')
                                            _att = _av.get('tip')
                                            if _atn and _att and isinstance(_att, str) and _att.startswith('#'):
                                                vtips_unl[_atn] = _att
                                        break
                            except Exception:
                                logging.exception("Suppressed exception")

                            def _utip(vn):
                                return vtips_unl.get(vn, '#e0c060')

                            def _utip_ol(vn):
                                tc = vtips_unl.get(vn)
                                if not tc:
                                    return '#aa8820'
                                try:
                                    rv = int(tc[1:3], 16); gv = int(tc[3:5], 16); bv = int(tc[5:7], 16)
                                    return f'#{max(0, rv - 40):02x}{max(0, gv - 40):02x}{max(0, bv - 40):02x}'
                                except Exception:
                                    return '#aa8820'

                            def _utip_r(r):
                                if isinstance(r, dict):
                                    return _utip(r.get('variant') or r.get('name') or 'Unknown')
                                return '#e0c060'

                            def _utip_ol_r(r):
                                if isinstance(r, dict):
                                    return _utip_ol(r.get('variant') or r.get('name') or 'Unknown')
                                return '#aa8820'

                            SLOT_H = 28; SLOT_W = 260; ox_mag = 20
                            SPRING_H = 14
                            canvas_h = 30 + cap * SLOT_H + SPRING_H + 8
                            canvas_w = SLOT_W + 40

                            main_frame = customtkinter.CTkFrame(ul_editor)
                            main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                            effective_h = min(canvas_h, 650)
                            ul_canvas = _tk_unl.Canvas(main_frame, width = canvas_w, height = effective_h, bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                            if canvas_h > 650:
                                _uc_scroll = _tk_unl.Scrollbar(main_frame, orient = 'vertical', command = ul_canvas.yview)
                                _uc_scroll.pack(side = 'right', fill = 'y')
                                ul_canvas.configure(yscrollcommand = _uc_scroll.set, scrollregion = (0, 0, canvas_w, canvas_h))
                            ul_canvas.pack(side = 'left', fill = 'both', expand = True)

                            side_unl = customtkinter.CTkFrame(ul_editor, fg_color = 'transparent', width = 180)
                            side_unl.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                            uls = {'removed': 0, 'animating': False, 'stoggle': 0,
                                   '_reloader_hooked': False, '_reloader_ch': None}
                            MAG_TOP_UNL = 30

                            def _draw_unl_mag():
                                ul_canvas.delete('mag')
                                oy = MAG_TOP_UNL
                                ul_canvas.create_text(canvas_w // 2, 12, text = '\u2191 CLICK ROUND TO REMOVE \u2191', fill = '#888888', font = ('Consolas', 9), tags = 'mag')
                                ul_canvas.create_rectangle(ox_mag, oy, ox_mag + SLOT_W, oy + cap * SLOT_H, outline = '#888888', width = 2, tags = 'mag')
                                ul_canvas.create_line(ox_mag, oy, ox_mag - 15, oy - 8, fill = '#888888', width = 2, tags = 'mag')
                                ul_canvas.create_line(ox_mag + SLOT_W, oy, ox_mag + SLOT_W + 15, oy - 8, fill = '#888888', width = 2, tags = 'mag')
                                for i in range(cap):
                                    sy = oy + i * SLOT_H
                                    if i > 0:
                                        ul_canvas.create_line(ox_mag, sy, ox_mag + SLOT_W, sy, fill = '#444444', dash = (2, 2), tags = 'mag')
                                    if i < len(existing):
                                        r = existing[i]
                                        vn = r.get('variant') if isinstance(r, dict) else str(r) if r else 'Unknown'
                                        c = vcols_unl.get(vn, '#c4a032')
                                        ul_canvas.create_rectangle(ox_mag + 2, sy + 2, ox_mag + SLOT_W - 2, sy + SLOT_H - 2, fill = c, outline = '#222222', tags = 'mag')
                                        ul_canvas.create_oval(ox_mag + 4, sy + 4, ox_mag + 22, sy + SLOT_H - 4, fill = _utip_r(r), outline = _utip_ol_r(r), tags = 'mag')
                                        ul_canvas.create_text(ox_mag + SLOT_W // 2 + 10, sy + SLOT_H // 2, text = vn, fill = '#1a1a1a', font = ('Consolas', 9, 'bold'), tags = 'mag') # type: ignore
                                    else:
                                        ul_canvas.create_text(ox_mag + SLOT_W // 2, sy + SLOT_H // 2, text = '[empty]', fill = '#444444', font = ('Consolas', 9), tags = 'mag')
                                by = oy + cap * SLOT_H
                                ul_canvas.create_rectangle(ox_mag, by, ox_mag + SLOT_W, by + SPRING_H, fill = '#555555', outline = '#666666', tags = 'mag')
                                ul_canvas.create_text(ox_mag + SLOT_W // 2, by + SPRING_H // 2, text = '\u25b2 SPRING \u25b2', fill = '#888888', font = ('Consolas', 8), tags = 'mag')

                            def _play_remove_sound():
                                try:
                                    sn = f"bulletinsert{uls['stoggle']}"
                                    uls['stoggle'] = 1 - uls['stoggle']
                                    sound_path = os.path.join('sounds', 'firearms', 'universal', f'{sn}.ogg')
                                    if os.path.exists(sound_path):
                                        snd = pygame.mixer.Sound(sound_path)
                                        ch = pygame.mixer.find_channel()
                                        if ch:
                                            ch.play(snd)
                                except Exception:
                                    logging.exception("Suppressed exception")

                            def _remove_round_at(idx):
                                if idx < 0 or idx >= len(existing) or uls['animating']:
                                    return
                                removed = existing.pop(idx)
                                uls['removed'] += 1
                                save_data.setdefault('hands', {}).setdefault('items', [])
                                self._add_rounds_to_container(save_data['hands']['items'], [removed])
                                _play_remove_sound()
                                _draw_unl_mag()
                                _update_unl_side()

                            def _hit_slot(x, y):
                                oy = MAG_TOP_UNL
                                if x < ox_mag or x > ox_mag + SLOT_W:
                                    return None
                                for i in range(len(existing)):
                                    sy = oy + i * SLOT_H
                                    if sy <= y <= sy + SLOT_H:
                                        return i
                                return None

                            def _unl_on_click(event):
                                if uls['animating']:
                                    return
                                idx = _hit_slot(event.x, event.y)
                                if idx is not None:
                                    _animate_pop(idx)

                            def _animate_pop(idx):
                                if idx < 0 or idx >= len(existing):
                                    return
                                uls['animating'] = True
                                oy = MAG_TOP_UNL
                                r = existing[idx]
                                vn = r.get('variant') if isinstance(r, dict) else str(r) if r else 'Unknown'
                                c = vcols_unl.get(vn, '#c4a032')
                                sy = oy + idx * SLOT_H
                                _pri = ul_canvas.create_rectangle(ox_mag + 2, sy + 2, ox_mag + SLOT_W - 2, sy + SLOT_H - 2, fill = c, outline = '#ffffff', width = 2, tags = 'popanim')
                                _poi = ul_canvas.create_oval(ox_mag + 4, sy + 4, ox_mag + 22, sy + SLOT_H - 4, fill = _utip_r(r), outline = _utip_ol_r(r), tags = 'popanim')
                                _pti = ul_canvas.create_text(ox_mag + SLOT_W // 2 + 10, sy + SLOT_H // 2, text = vn, fill = '#1a1a1a', font = ('Consolas', 9, 'bold'), tags = 'popanim') # type: ignore
                                target_y = oy - SLOT_H - 10
                                steps = 8
                                def _pop_step(s):
                                    if s >= steps:
                                        ul_canvas.delete('popanim')
                                        uls['animating'] = False
                                        _remove_round_at(idx)
                                        return
                                    frac = (s + 1) / steps
                                    ease = frac * frac
                                    ny = sy + (target_y - sy) * ease
                                    ul_canvas.coords(_pri, ox_mag + 2, ny + 2, ox_mag + SLOT_W - 2, ny + SLOT_H - 2)
                                    ul_canvas.coords(_poi, ox_mag + 4, ny + 4, ox_mag + 22, ny + SLOT_H - 4)
                                    ul_canvas.coords(_pti, ox_mag + SLOT_W // 2 + 10, ny + SLOT_H // 2)
                                    ul_editor.after(20, lambda: _pop_step(s + 1))
                                _pop_step(0)

                            ul_canvas.bind('<Button-1>', _unl_on_click)

                            _unl_cap_lbl = customtkinter.CTkLabel(side_unl, text = f'{len(existing)}/{cap} rounds remaining', font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                            _unl_cap_lbl.pack(pady = (10, 6))
                            customtkinter.CTkLabel(side_unl, text = 'Click a round to remove it.\nRounds go to your hands.', font = customtkinter.CTkFont(size = 10), text_color = '#888888', wraplength = 170).pack(pady = 6)

                            def _update_unl_side():
                                _unl_cap_lbl.configure(text = f'{len(existing)}/{cap} rounds remaining')

                            _has_reloader_unl = self._check_for_reloader_item(save_data)
                            _unl_reloader = {'btn': None, 'unhook_btn': None, 'ch': None}

                            def _stop_unl_reloader():
                                if _unl_reloader['ch']:
                                    try:
                                        _unl_reloader['ch'].stop()
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    _unl_reloader['ch'] = None

                            def _start_unl_reloader_loop():
                                try:
                                    rpath = os.path.join('sounds', 'firearms', 'universal', 'reloaderloop.ogg')
                                    if os.path.exists(rpath):
                                        snd = pygame.mixer.Sound(rpath)
                                        ch = pygame.mixer.find_channel()
                                        if ch:
                                            ch.play(snd, loops = -1)
                                            _unl_reloader['ch'] = ch # type: ignore
                                except Exception:
                                    logging.exception("Suppressed exception")

                            def _reloader_unload_all():
                                if uls['animating'] or not existing:
                                    return
                                uls['animating'] = True
                                uls['_reloader_hooked'] = True
                                if _unl_reloader.get('btn'):
                                    try:
                                        _unl_reloader['btn'].configure(state = 'disabled')
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                try:
                                    rpath = os.path.join('sounds', 'firearms', 'universal', 'reloaderroundinsert.ogg')
                                    if os.path.exists(rpath):
                                        snd = pygame.mixer.Sound(rpath)
                                        ch = pygame.mixer.find_channel()
                                        if ch:
                                            ch.play(snd)
                                except Exception:
                                    logging.exception("Suppressed exception")
                                def _start_loop():
                                    _start_unl_reloader_loop()
                                    _reloader_unload_step()
                                ul_editor.after(200, _start_loop)

                            def _reloader_unload_step():
                                if not existing:
                                    _stop_unl_reloader()
                                    uls['animating'] = False
                                    _draw_unl_mag()
                                    _update_unl_side()
                                    if _unl_reloader.get('unhook_btn'):
                                        try:
                                            _unl_reloader['unhook_btn'].configure(state = 'normal')
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                    return
                                removed = existing.pop(0)
                                uls['removed'] += 1
                                save_data.setdefault('hands', {}).setdefault('items', [])
                                self._add_rounds_to_container(save_data['hands']['items'], [removed])
                                _play_remove_sound()
                                _draw_unl_mag()
                                _update_unl_side()
                                ul_editor.after(100, _reloader_unload_step)

                            def _unhook_unl_reloader():
                                _stop_unl_reloader()
                                uls['_reloader_hooked'] = False
                                uls['animating'] = False
                                if _unl_reloader.get('btn'):
                                    try:
                                        _unl_reloader['btn'].configure(state = 'normal')
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                if _unl_reloader.get('unhook_btn'):
                                    try:
                                        _unl_reloader['unhook_btn'].configure(state = 'disabled')
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                try:
                                    rpath = os.path.join('sounds', 'firearms', 'universal', 'reloaderroundinsert.ogg')
                                    if os.path.exists(rpath):
                                        snd = pygame.mixer.Sound(rpath)
                                        ch = pygame.mixer.find_channel()
                                        if ch:
                                            ch.play(snd)
                                except Exception:
                                    logging.exception("Suppressed exception")

                            if _has_reloader_unl:
                                _unl_reloader['btn'] = customtkinter.CTkButton(side_unl, text = '\u2699 Reloader Unload All', command = _reloader_unload_all, width = 160, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = '#2a6a2a', hover_color = '#3a7a3a') # type: ignore
                                _unl_reloader['btn'].pack(pady = 4)
                                _unl_reloader['unhook_btn'] = customtkinter.CTkButton(side_unl, text = '\u2716 Unhook Reloader', command = _unhook_unl_reloader, width = 160, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = '#6a2a2a', hover_color = '#7a3a3a', state = 'disabled') # type: ignore
                                _unl_reloader['unhook_btn'].pack(pady = 4)

                            def _unl_done():
                                if uls.get('_reloader_hooked'):
                                    self._popup_show_info('Reloader', 'Please unhook the reloader first!')
                                    return
                                _stop_unl_reloader()
                                mag_item['rounds'] = existing
                                ul_editor.destroy()
                                update_weapon_view()
                                if uls['removed'] > 0:
                                    self._popup_show_info('Unload Magazine', f'Removed {uls["removed"]} rounds ({len(existing)}/{cap} remaining)')

                            ul_editor.protocol('WM_DELETE_WINDOW', _unl_done)
                            customtkinter.CTkButton(side_unl, text = 'Done', command = _unl_done, width = 160, height = 35, font = customtkinter.CTkFont(size = 12)).pack(pady = 10)

                            _draw_unl_mag()
                            ul_editor.update_idletasks()
                            ew = max(ul_editor.winfo_reqwidth(), 520)
                            eh = max(ul_editor.winfo_reqheight(), 420)
                            _sw_s = ul_editor.winfo_screenwidth(); _sh_s = ul_editor.winfo_screenheight()
                            x = (_sw_s // 2) - (ew // 2); y = (_sh_s // 2) - (eh // 2)
                            ul_editor.geometry(f'{ew}x{eh}+{x}+{y}')
                            ul_editor.grab_set()
                            ul_editor.lift()
                            self._safe_focus(ul_editor)
                        except Exception:
                            logging.exception('Failed to open unload magazine editor')

                    button_frame = customtkinter.CTkFrame(unload_popup, fg_color = "transparent")
                    button_frame.pack(fill = "x", padx = 10, pady = 10)

                    unload_btn = customtkinter.CTkButton(
                    button_frame,
                    text = "Unload Selected",
                    command = unload_selected,
                    width = 150,
                    height = 40
                    )
                    unload_btn.pack(side = "left", padx = 5)

                    cancel_btn = customtkinter.CTkButton(
                    button_frame,
                    text = "Cancel",
                    command = unload_popup.destroy,
                    width = 150,
                    height = 40,
                    fg_color = "#444444",
                    hover_color = "#555555"
                    )
                    cancel_btn.pack(side = "left", padx = 5)

                    unload_popup.update_idletasks()
                    popup_width = unload_popup.winfo_reqwidth()
                    popup_height = unload_popup.winfo_reqheight()
                    screen_width = unload_popup.winfo_screenwidth()
                    screen_height = unload_popup.winfo_screenheight()
                    x =(screen_width //2)-(popup_width //2)
                    y =(screen_height //2)-(popup_height //2)
                    unload_popup.geometry(f"+{x}+{y}")
                    unload_popup.deiconify()
                    unload_popup.grab_set()
                    unload_popup.lift()
                    self._safe_focus(unload_popup)

                try:
                    def reload_and_close():
                        try:
                            popup.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")
                        reload_magazine()

                    reload_btn = self._create_sound_button(popup, text = 'Reload Magazine', command = reload_and_close, width = 240, height = 40, font = customtkinter.CTkFont(size = 12), fg_color = '#1a4d1a')
                    reload_btn.pack(pady = 6)
                    try:
                        reload_btn.configure(state = 'normal'if can_reload else 'disabled')
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    unload_btn_popup = self._create_sound_button(popup, text = 'Unload Magazine', command = unload_magazine_rounds, width = 240, height = 40, font = customtkinter.CTkFont(size = 12), fg_color = '#444444')
                    unload_btn_popup.pack(pady = 6)
                    try:
                        unload_btn_popup.configure(state = 'normal'if can_unload else 'disabled')
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    _mark_mag = (current_weapon_state.get('weapon') or {}).get('loaded')
                    if isinstance(_mark_mag, dict) and _mark_mag.get('marking_system'):
                        def _open_marking():
                            try:
                                popup.destroy()
                            except Exception:
                                logging.exception("Suppressed exception")
                            self._open_magazine_marking_dialog(_mark_mag, current_weapon_state.get('weapon') or {}, save_data, update_callback=update_weapon_view)
                        mark_btn = self._create_sound_button(popup, text='Mark Magazine', command=_open_marking, width=240, height=40, font=customtkinter.CTkFont(size=12), fg_color='#4a3080', hover_color='#6040a0')
                        mark_btn.pack(pady=6)
                except Exception:
                    logging.exception("Suppressed exception")

                # ── Clip Management Buttons ──────────────────────────────
                try:
                    def _find_all_clips_in_inventory():
                        clips = []
                        def _is_clip(itm):
                            return itm and isinstance(itm, dict) and itm.get('clip_type')
                        for itm in save_data.get('hands', {}).get('items', []):
                            if _is_clip(itm):
                                clips.append(('hands', itm))
                        for slot_name, eq_item in save_data.get('equipment', {}).items():
                            if not eq_item or not isinstance(eq_item, dict):
                                continue
                            for itm in eq_item.get('items', []) or []:
                                if _is_clip(itm):
                                    clips.append(('equipment', itm))
                            for sub in eq_item.get('subslots', []) or []:
                                curr = sub.get('current')
                                if curr and isinstance(curr, dict):
                                    for itm in curr.get('items', []) or []:
                                        if _is_clip(itm):
                                            clips.append(('equipment', itm))
                        return clips

                    all_clips = _find_all_clips_in_inventory()
                    clips_with_rounds = [c for c in all_clips if isinstance(c[1].get('rounds'), list) and len(c[1].get('rounds', [])) > 0]
                    clips_not_full = [c for c in all_clips if len(c[1].get('rounds', []) or []) < int(c[1].get('capacity', 5) or 5)]

                    if all_clips:
                        customtkinter.CTkLabel(popup, text = '\u2500' * 30, text_color = '#444444').pack(pady = 2)

                    def _open_clip_loader():
                        try:
                            popup.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")
                        _open_clip_management_editor(all_clips, mode = 'load')

                    def _open_clip_unloader():
                        try:
                            popup.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")
                        _open_clip_management_editor(all_clips, mode = 'unload')

                    if clips_not_full:
                        load_clip_btn = self._create_sound_button(popup, text = 'Load Clip', command = _open_clip_loader,
                        width = 240, height = 40, font = customtkinter.CTkFont(size = 12), fg_color = '#4a6d1a', hover_color = '#5a8d2a')
                        load_clip_btn.pack(pady = 6)

                    if clips_with_rounds:
                        unload_clip_btn = self._create_sound_button(popup, text = 'Unload Clip', command = _open_clip_unloader,
                        width = 240, height = 40, font = customtkinter.CTkFont(size = 12), fg_color = '#6d4a1a', hover_color = '#8d5a2a')
                        unload_clip_btn.pack(pady = 6)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    customtkinter.CTkButton(popup, text = 'Close', command = popup.destroy, width = 140).pack(pady = 8)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    popup.grab_set()
                    popup.lift()
                    self._safe_focus(popup)
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

        def _open_clip_management_editor(all_clips, mode = 'load'):
            import tkinter as _tk_clip
            try:
                clip_editor = customtkinter.CTkToplevel(self.root)
                clip_editor.title('Clip Loader' if mode == 'load' else 'Clip Unloader')
                clip_editor.transient(self.root)

                if not all_clips:
                    self._popup_show_info('Clip Management', 'No clips found in inventory.')
                    clip_editor.destroy()
                    return

                # Select which clip to manage
                if len(all_clips) == 1:
                    _selected_clip = all_clips[0]
                    _open_clip_round_editor(_selected_clip[1], mode, clip_editor)
                    return

                customtkinter.CTkLabel(clip_editor, text = 'Select a clip:',
                font = customtkinter.CTkFont(size = 13, weight = 'bold')).pack(pady = 8)

                scroll = customtkinter.CTkScrollableFrame(clip_editor, width = 400, height = 300)
                scroll.pack(fill = 'both', expand = True, padx = 10, pady = 5)

                sel_var = customtkinter.StringVar(value = '0')

                for idx, (location, clip_item) in enumerate(all_clips):
                    clip_name = clip_item.get('name', 'Clip')
                    clip_cap = int(clip_item.get('capacity', 5) or 5)
                    clip_rounds = clip_item.get('rounds', []) or []
                    loaded = len(clip_rounds)
                    clip_type = clip_item.get('clip_type', '?')

                    radio_text = f'{clip_name} ({loaded}/{clip_cap}) - {clip_type} - {location}'
                    customtkinter.CTkRadioButton(scroll, text = radio_text, variable = sel_var,
                    value = str(idx), font = customtkinter.CTkFont(size = 11)).pack(anchor = 'w', pady = 4, padx = 6)

                def _select():
                    idx = int(sel_var.get())
                    _, clip_item = all_clips[idx]
                    clip_editor.destroy()
                    _ed = customtkinter.CTkToplevel(self.root)
                    _ed.title('Clip Loader' if mode == 'load' else 'Clip Unloader')
                    _ed.transient(self.root)
                    _open_clip_round_editor(clip_item, mode, _ed)

                btn_frame = customtkinter.CTkFrame(clip_editor, fg_color = 'transparent')
                btn_frame.pack(fill = 'x', padx = 10, pady = 10)
                customtkinter.CTkButton(btn_frame, text = 'Select', command = _select, width = 140, height = 35).pack(side = 'left', padx = 5)
                customtkinter.CTkButton(btn_frame, text = 'Cancel', command = clip_editor.destroy,
                width = 140, height = 35, fg_color = '#444444', hover_color = '#555555').pack(side = 'left', padx = 5)

                self._center_popup_on_window(clip_editor, 500, 400)
                clip_editor.grab_set()
                clip_editor.lift()
                self._safe_focus(clip_editor)

            except Exception:
                logging.exception('Failed to open clip management editor')

        def _open_clip_round_editor(clip_item, mode, editor):
            import tkinter as _tk_clr
            try:
                clip_cap = int(clip_item.get('capacity', 5) or 5)
                if 'rounds' not in clip_item or clip_item['rounds'] is None:
                    clip_item['rounds'] = []
                clip_rounds = clip_item['rounds']

                clip_caliber_raw = clip_item.get('caliber', [])
                if isinstance(clip_caliber_raw, str):
                    clip_caliber_raw = [clip_caliber_raw]
                clip_calibers = set()
                for c in clip_caliber_raw:
                    if c:
                        clip_calibers.add(str(c).lower().strip())

                if mode == 'load':
                    # Find compatible loose rounds
                    def _get_rounds_for_clip():
                        variants = {}
                        def _cal_match(item_cal):
                            if not clip_calibers:
                                return True
                            if not item_cal:
                                return False
                            return str(item_cal).lower().strip() in clip_calibers
                        def _proc(itm):
                            if not itm or not isinstance(itm, dict):
                                return
                            if itm.get('magazinesystem') or itm.get('clip_type'):
                                return
                            itm_cal = itm.get('caliber')
                            if not _cal_match(itm_cal):
                                return
                            qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                            if qty > 0:
                                vn = itm.get('variant') or itm.get('name') or 'Unknown'
                                variants[str(vn)] = variants.get(str(vn), 0) + qty
                                return
                            rds = itm.get('rounds')
                            if isinstance(rds, list) and rds:
                                for r in rds:
                                    if isinstance(r, dict):
                                        if not _cal_match(r.get('caliber')):
                                            continue
                                        vn = r.get('variant') or r.get('name') or 'Unknown'
                                        variants[str(vn)] = variants.get(str(vn), 0) + 1
                                return
                            if itm.get('caliber') and not itm.get('capacity'):
                                vn = itm.get('variant') or itm.get('name') or 'Unknown'
                                variants[str(vn)] = variants.get(str(vn), 0) + 1
                        for itm in save_data.get('hands', {}).get('items', []):
                            _proc(itm)
                        for slot_name, eq_item in save_data.get('equipment', {}).items():
                            if not eq_item or not isinstance(eq_item, dict):
                                continue
                            for itm in eq_item.get('items', []) or []:
                                _proc(itm)
                            for sub in eq_item.get('subslots', []) or []:
                                curr = sub.get('current')
                                if curr and isinstance(curr, dict):
                                    for itm in curr.get('items', []) or []:
                                        _proc(itm)
                        return variants

                    avail = _get_rounds_for_clip()
                    if not avail:
                        self._popup_show_info('Clip Loader', 'No compatible loose rounds found!')
                        editor.destroy()
                        return

                    vlist_c = sorted(avail.keys())
                    cpal = ['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                    vcols_c = {v: cpal[i % len(cpal)] for i, v in enumerate(vlist_c)}

                    SLOT_H = 28
                    SLOT_W = 200
                    ox = 15
                    CHIP_W, CHIP_H, CHIP_PAD = 120, 28, 6
                    _cols = max(1, (SLOT_W + 30) // (CHIP_W + CHIP_PAD))
                    _rows_need = max(1, (len(vlist_c) + _cols - 1) // _cols)
                    SEL_H = 22 + _rows_need * (CHIP_H + CHIP_PAD) + 4
                    HINT_H = 22
                    MAG_TOP = SEL_H + HINT_H
                    canvas_h = MAG_TOP + clip_cap * SLOT_H + 20
                    canvas_w = SLOT_W + 30

                    main_f = customtkinter.CTkFrame(editor)
                    main_f.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)
                    clip_canvas = _tk_clr.Canvas(main_f, width = canvas_w, height = min(canvas_h, 500),
                    bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                    clip_canvas.pack(fill = 'both', expand = True)

                    side_f = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 160)
                    side_f.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                    cls = {'added': 0, 'dragging': False, 'drag_vn': None, 'di': None, 'dt': None, 'do': None}
                    chip_hb = {}

                    def _take_clip_round(vname):
                        for hi in range(len(save_data.get('hands', {}).get('items', [])) - 1, -1, -1):
                            itm = save_data['hands']['items'][hi]
                            try:
                                if not itm or not isinstance(itm, dict):
                                    continue
                                if itm.get('magazinesystem') or itm.get('clip_type'):
                                    continue
                                rds = itm.get('rounds')
                                if isinstance(rds, list) and rds:
                                    for ri, r in enumerate(rds):
                                        rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                        if rv == vname:
                                            return rds.pop(ri)
                                qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                                if qty > 0:
                                    nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                    if nm and str(nm) == vname:
                                        itm['quantity'] = qty - 1
                                        return {k: v for k, v in itm.items() if k != 'quantity'}
                            except Exception:
                                logging.exception("Suppressed exception")
                                continue
                        for _sn, eq_item in list(save_data.get('equipment', {}).items()):
                            if not eq_item or not isinstance(eq_item, dict):
                                continue
                            for cidx in range(len(eq_item.get('items', [])) - 1, -1, -1):
                                try:
                                    itm = eq_item['items'][cidx]
                                    if not itm or not isinstance(itm, dict):
                                        continue
                                    if itm.get('magazinesystem') or itm.get('clip_type'):
                                        continue
                                    rds = itm.get('rounds')
                                    if isinstance(rds, list) and rds:
                                        for ri, r in enumerate(rds):
                                            rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                            if rv == vname:
                                                return rds.pop(ri)
                                    qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                                    if qty > 0:
                                        nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                        if nm and str(nm) == vname:
                                            itm['quantity'] = qty - 1
                                            return {k: v for k, v in itm.items() if k != 'quantity'}
                                except Exception:
                                    logging.exception("Suppressed exception")
                        return None

                    def _draw_clip_chips():
                        clip_canvas.delete('chips')
                        clip_canvas.create_text(canvas_w // 2, 10, text = 'AVAILABLE ROUNDS', fill = '#888888',
                        font = ('Consolas', 9, 'bold'), tags = 'chips')
                        start_x = (canvas_w - min(len(vlist_c), _cols) * (CHIP_W + CHIP_PAD) + CHIP_PAD) // 2
                        for idx, vn in enumerate(vlist_c):
                            cnt = avail.get(vn, 0)
                            row_i = idx // _cols
                            col_i = idx % _cols
                            x1 = start_x + col_i * (CHIP_W + CHIP_PAD)
                            y1 = 22 + row_i * (CHIP_H + CHIP_PAD)
                            x2 = x1 + CHIP_W
                            y2 = y1 + CHIP_H
                            chip_hb[vn] = (x1, y1, x2, y2)
                            c = vcols_c.get(vn, '#c4a032')
                            is_a = cnt > 0
                            fill = c if is_a else '#2a2a2a'
                            ol = '#dddddd' if is_a else '#3a3a3a'
                            clip_canvas.create_rectangle(x1, y1, x2, y2, fill = fill, outline = ol, width = 1, tags = 'chips')
                            disp = vn if len(vn) <= 10 else vn[:9] + '\u2026'
                            clip_canvas.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                            text = f'{disp} x{cnt}', fill = '#1a1a1a' if is_a else '#555555',
                            font = ('Consolas', 8, 'bold'), tags = 'chips')

                    def _draw_clip_body():
                        clip_canvas.delete('clipbody')
                        oy = MAG_TOP
                        clip_canvas.create_text(canvas_w // 2, MAG_TOP - 10, text = '\u2193 DROP INTO CLIP \u2193',
                        fill = '#555555', font = ('Consolas', 9), tags = 'clipbody')
                        clip_canvas.create_rectangle(ox, oy, ox + SLOT_W, oy + clip_cap * SLOT_H,
                        outline = '#999999', width = 2, fill = '#2a2a2a', tags = 'clipbody')
                        for i in range(clip_cap):
                            sy = oy + i * SLOT_H
                            if i > 0:
                                clip_canvas.create_line(ox, sy, ox + SLOT_W, sy, fill = '#444444', dash = (2, 2), tags = 'clipbody')
                            if i < len(clip_rounds):
                                r = clip_rounds[i]
                                vn = (r.get('variant') or r.get('name') or 'Unknown') if isinstance(r, dict) else str(r) if r else 'Unknown'
                                c = vcols_c.get(vn, '#c4a032')
                                clip_canvas.create_rectangle(ox + 2, sy + 2, ox + SLOT_W - 2, sy + SLOT_H - 2,
                                fill = c, outline = '#222222', tags = 'clipbody')
                                clip_canvas.create_text(ox + SLOT_W // 2, sy + SLOT_H // 2, text = vn,
                                fill = '#1a1a1a', font = ('Consolas', 9, 'bold'), tags = 'clipbody')
                            else:
                                clip_canvas.create_text(ox + SLOT_W // 2, sy + SLOT_H // 2, text = '[empty]',
                                fill = '#444444', font = ('Consolas', 9), tags = 'clipbody')

                    def _draw_clip_all():
                        _draw_clip_chips()
                        _draw_clip_body()

                    _ins_toggle = {'v': 0}
                    def _play_clip_insert():
                        try:
                            sn = f"bulletinsert{_ins_toggle['v']}"
                            _ins_toggle['v'] = 1 - _ins_toggle['v']
                            self._play_weapon_action_sound(wpn, sn, block=False)
                        except Exception:
                            logging.exception("Suppressed exception")

                    def _clip_on_press(event):
                        if len(clip_rounds) >= clip_cap:
                            return
                        for vn, (x1, y1, x2, y2) in chip_hb.items():
                            if x1 <= event.x <= x2 and y1 <= event.y <= y2 and avail.get(vn, 0) > 0:
                                cls['dragging'] = True
                                cls['drag_vn'] = vn
                                c = vcols_c.get(vn, '#c4a032')
                                cls['di'] = clip_canvas.create_rectangle(ox + 2, event.y - SLOT_H // 2,
                                ox + SLOT_W - 2, event.y + SLOT_H // 2, fill = c, outline = '#ffffff', width = 2, tags = 'drag')
                                cls['dt'] = clip_canvas.create_text(ox + SLOT_W // 2, event.y,
                                text = vn, fill = '#1a1a1a', font = ('Consolas', 10, 'bold'), tags = 'drag')
                                return

                    def _clip_on_move(event):
                        if not cls['dragging']:
                            return
                        y = event.y
                        if cls['di'] and cls['dt']:
                            clip_canvas.coords(cls['di'], ox + 2, y - SLOT_H // 2, ox + SLOT_W - 2, y + SLOT_H // 2)
                            clip_canvas.coords(cls['dt'], ox + SLOT_W // 2, y)

                    def _clip_on_release(event):
                        if not cls['dragging']:
                            return
                        cls['dragging'] = False
                        clip_canvas.delete('drag')
                        cls['di'] = cls['dt'] = None
                        if len(clip_rounds) >= clip_cap:
                            return
                        vn = cls['drag_vn']
                        if not vn or avail.get(vn, 0) <= 0:
                            return
                        if event.y >= MAG_TOP - 15:
                            r = _take_clip_round(vn)
                            if r:
                                clip_rounds.insert(0, r)
                                cls['added'] += 1
                                avail[vn] = avail.get(vn, 0) - 1
                                if avail[vn] <= 0:
                                    del avail[vn]
                                _play_clip_insert()
                                _draw_clip_all()
                                _update_clip_lbl()

                    clip_canvas.bind('<Button-1>', _clip_on_press)
                    clip_canvas.bind('<B1-Motion>', _clip_on_move)
                    clip_canvas.bind('<ButtonRelease-1>', _clip_on_release)

                    _clip_lbl = customtkinter.CTkLabel(side_f, text = f'{len(clip_rounds)}/{clip_cap} loaded',
                    font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                    _clip_lbl.pack(pady = (10, 6))
                    customtkinter.CTkLabel(side_f, text = 'Drag rounds into\nthe clip from above',
                    font = customtkinter.CTkFont(size = 10), text_color = '#888888', wraplength = 150).pack(pady = 6)

                    def _update_clip_lbl():
                        _clip_lbl.configure(text = f'{len(clip_rounds)}/{clip_cap} loaded')

                    def _clip_done():
                        editor.destroy()
                        update_weapon_view()
                        if cls['added'] > 0:
                            self._popup_show_info('Clip Loader', f'Loaded {cls["added"]} rounds into clip')

                    editor.protocol('WM_DELETE_WINDOW', _clip_done)
                    customtkinter.CTkButton(side_f, text = 'Done', command = _clip_done, width = 140, height = 35).pack(pady = 10)

                    _draw_clip_all()

                    self._center_popup_on_window(editor, 450, 400)
                    editor.grab_set()
                    editor.lift()
                    self._safe_focus(editor)

                else:
                    # Unload mode
                    if not clip_rounds:
                        self._popup_show_info('Clip Unloader', 'Clip is empty!')
                        editor.destroy()
                        return

                    SLOT_H = 28
                    SLOT_W = 200
                    ox = 15
                    canvas_h = clip_cap * SLOT_H + 40
                    canvas_w = SLOT_W + 30

                    main_f = customtkinter.CTkFrame(editor)
                    main_f.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)
                    clip_canvas = _tk_clr.Canvas(main_f, width = canvas_w, height = min(canvas_h, 400),
                    bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                    clip_canvas.pack(fill = 'both', expand = True)

                    side_f = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 160)
                    side_f.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                    uls = {'removed': 0}

                    cpal = ['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                    vset_u = set()
                    for r in clip_rounds:
                        if isinstance(r, dict):
                            vset_u.add(r.get('variant') or r.get('name') or 'Unknown')
                    vlist_u = sorted(vset_u)
                    vcols_u = {v: cpal[i % len(cpal)] for i, v in enumerate(vlist_u)}

                    round_hitboxes = {}

                    def _draw_unload_clip():
                        clip_canvas.delete('all')
                        clip_canvas.create_text(canvas_w // 2, 12, text = '\u25b2 CLICK ROUND TO REMOVE \u25b2',
                        fill = '#888888', font = ('Consolas', 9, 'bold'))
                        oy = 28
                        clip_canvas.create_rectangle(ox, oy, ox + SLOT_W, oy + clip_cap * SLOT_H,
                        outline = '#999999', width = 2, fill = '#2a2a2a')
                        round_hitboxes.clear()
                        for i in range(clip_cap):
                            sy = oy + i * SLOT_H
                            if i > 0:
                                clip_canvas.create_line(ox, sy, ox + SLOT_W, sy, fill = '#444444', dash = (2, 2))
                            if i < len(clip_rounds):
                                r = clip_rounds[i]
                                vn = (r.get('variant') or r.get('name') or 'Unknown') if isinstance(r, dict) else str(r) if r else 'Unknown'
                                c = vcols_u.get(vn, '#c4a032')
                                clip_canvas.create_rectangle(ox + 2, sy + 2, ox + SLOT_W - 2, sy + SLOT_H - 2,
                                fill = c, outline = '#222222')
                                clip_canvas.create_text(ox + SLOT_W // 2, sy + SLOT_H // 2, text = vn,
                                fill = '#1a1a1a', font = ('Consolas', 9, 'bold'))
                                round_hitboxes[i] = (ox, sy, ox + SLOT_W, sy + SLOT_H)
                            else:
                                clip_canvas.create_text(ox + SLOT_W // 2, sy + SLOT_H // 2, text = '[empty]',
                                fill = '#444444', font = ('Consolas', 9))

                    def _unload_click(event):
                        for idx, (x1, y1, x2, y2) in round_hitboxes.items():
                            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                                removed = clip_rounds.pop(idx)
                                uls['removed'] += 1
                                self._add_rounds_to_container(save_data.get('hands', {}).get('items', []), [removed])
                                _draw_unload_clip()
                                _update_unl_lbl()
                                return

                    clip_canvas.bind('<Button-1>', _unload_click)

                    _unl_lbl = customtkinter.CTkLabel(side_f, text = f'{len(clip_rounds)}/{clip_cap} loaded',
                    font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                    _unl_lbl.pack(pady = (10, 6))
                    customtkinter.CTkLabel(side_f, text = 'Click a round\nto remove it',
                    font = customtkinter.CTkFont(size = 10), text_color = '#888888', wraplength = 150).pack(pady = 6)

                    def _update_unl_lbl():
                        _unl_lbl.configure(text = f'{len(clip_rounds)}/{clip_cap} loaded')

                    def _unl_done():
                        editor.destroy()
                        update_weapon_view()
                        if uls['removed'] > 0:
                            self._popup_show_info('Clip Unloader', f'Removed {uls["removed"]} rounds from clip')

                    editor.protocol('WM_DELETE_WINDOW', _unl_done)
                    customtkinter.CTkButton(side_f, text = 'Done', command = _unl_done, width = 140, height = 35).pack(pady = 10)

                    _draw_unload_clip()

                    self._center_popup_on_window(editor, 400, 350)
                    editor.grab_set()
                    editor.lift()
                    self._safe_focus(editor)

            except Exception:
                logging.exception('Failed to open clip round editor')

        def _handle_break_action_reload():
            try:
                wpn = current_weapon_state.get('weapon') or {}
                caliber_list = wpn.get('caliber', []) or []
                if isinstance(caliber_list, str):
                    caliber_list = [caliber_list]
                caliber = caliber_list[0] if caliber_list else None
                if not caliber:
                    self._popup_show_info('Break Action Reload', 'Weapon has no caliber defined.')
                    return

                filter_calibers = set()
                for c in caliber_list:
                    if c:
                        filter_calibers.add(str(c).lower().strip())

                def _get_available_rounds_by_variant_ba():
                    variants = {}
                    def _caliber_matches(item_cal):
                        if not filter_calibers:
                            return True
                        if not item_cal:
                            return False
                        return str(item_cal).lower().strip() in filter_calibers

                    def _get_variant_name(itm):
                        v = itm.get('variant')
                        if v:
                            return str(v)
                        n = itm.get('name')
                        if n:
                            return str(n)
                        return 'Unknown'

                    def _process_item(itm):
                        if not itm or not isinstance(itm, dict):
                            return
                        if itm.get('magazinesystem') or itm.get('capacity'):
                            return
                        itm_cal = itm.get('caliber')
                        if not _caliber_matches(itm_cal):
                            return
                        rds = itm.get('rounds')
                        if isinstance(rds, list) and rds:
                            for r in rds:
                                if isinstance(r, dict):
                                    r_cal = r.get('caliber')
                                    if not _caliber_matches(r_cal):
                                        continue
                                    variant = _get_variant_name(r)
                                    variants[variant] = variants.get(variant, 0) + 1
                            return
                        qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                        if qty > 0:
                            variant = _get_variant_name(itm)
                            variants[variant] = variants.get(variant, 0) + qty
                            return
                        if itm.get('caliber'):
                            variant = _get_variant_name(itm)
                            variants[variant] = variants.get(variant, 0) + 1

                    for itm in save_data.get('hands', {}).get('items', []):
                        _process_item(itm)
                    for slot_name, eq_item in save_data.get('equipment', {}).items():
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for itm in eq_item.get('items', []) or []:
                            _process_item(itm)
                        for sub in eq_item.get('subslots', []) or []:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                for itm in curr.get('items', []) or []:
                                    _process_item(itm)
                    return variants

                is_infinite = bool(wpn.get('infinite_ammo'))

                if is_infinite:
                    available_by_variant = {'Infinite': 9999}
                else:
                    available_by_variant = _get_available_rounds_by_variant_ba()

                total_available = sum(available_by_variant.values())
                if total_available <= 0 and not is_infinite:
                    self._popup_show_info('Break Action Reload', 'No compatible ammunition found!')
                    return

                _open_break_action_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite)

            except Exception:
                logging.exception('Failed break action reload')

        def _handle_cylinder_reload():
            try:
                wpn = current_weapon_state.get('weapon') or {}
                caliber_list = wpn.get('caliber', []) or []
                if isinstance(caliber_list, str):
                    caliber_list = [caliber_list]
                caliber = caliber_list[0] if caliber_list else None
                if not caliber:
                    self._popup_show_info('Cylinder Reload', 'Weapon has no caliber defined.')
                    return

                filter_calibers = set()
                for c in caliber_list:
                    if c:
                        filter_calibers.add(str(c).lower().strip())

                def _get_available_rounds_by_variant_cyl():
                    variants = {}
                    def _caliber_matches(item_cal):
                        if not filter_calibers:
                            return True
                        if not item_cal:
                            return False
                        return str(item_cal).lower().strip() in filter_calibers

                    def _get_variant_name(itm):
                        v = itm.get('variant')
                        if v:
                            return str(v)
                        n = itm.get('name')
                        if n:
                            return str(n)
                        return 'Unknown'

                    def _process_item(itm):
                        if not itm or not isinstance(itm, dict):
                            return
                        if itm.get('magazinesystem') or itm.get('capacity'):
                            return
                        itm_cal = itm.get('caliber')
                        if not _caliber_matches(itm_cal):
                            return
                        rds = itm.get('rounds')
                        if isinstance(rds, list) and rds:
                            for r in rds:
                                if isinstance(r, dict):
                                    r_cal = r.get('caliber')
                                    if not _caliber_matches(r_cal):
                                        continue
                                    variant = _get_variant_name(r)
                                    variants[variant] = variants.get(variant, 0) + 1
                            return
                        qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                        if qty > 0:
                            variant = _get_variant_name(itm)
                            variants[variant] = variants.get(variant, 0) + qty
                            return
                        if itm.get('caliber'):
                            variant = _get_variant_name(itm)
                            variants[variant] = variants.get(variant, 0) + 1

                    for itm in save_data.get('hands', {}).get('items', []):
                        _process_item(itm)
                    for slot_name, eq_item in save_data.get('equipment', {}).items():
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for itm in eq_item.get('items', []) or []:
                            _process_item(itm)
                        for sub in eq_item.get('subslots', []) or []:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                for itm in curr.get('items', []) or []:
                                    _process_item(itm)
                    return variants

                is_infinite = bool(wpn.get('infinite_ammo'))

                if is_infinite:
                    available_by_variant = {'Infinite': 9999}
                else:
                    available_by_variant = _get_available_rounds_by_variant_cyl()

                total_available = sum(available_by_variant.values())
                if total_available <= 0:
                    self._popup_show_info('Cylinder Reload', 'No compatible ammunition found!')
                    return

                if bool(wpn.get('loading_gate')):
                    _open_loading_gate_cylinder_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite)
                else:
                    _open_cylinder_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite, bool(wpn.get('revolver_topbreak')))

            except Exception:
                logging.exception('Failed cylinder reload')

        def _handle_internal_magazine_reload():
            import tkinter as _tk_int
            try:
                wpn = current_weapon_state.get('weapon')or {}
                mag_type = str(wpn.get('magazinetype', '')or '').lower()
                is_en_bloc = 'en bloc' in mag_type

                caliber_list = wpn.get('caliber', [])or[]
                if isinstance(caliber_list, str):
                    caliber_list =[caliber_list]
                caliber = caliber_list[0]if caliber_list else None
                if not caliber:
                    self._popup_show_info('Internal Reload', 'Weapon has no caliber defined.')
                    return

                filter_calibers = set()
                for c in caliber_list:
                    if c:
                        filter_calibers.add(str(c).lower().strip())

                def _get_available_rounds_by_variant_internal():
                    variants = {}
                    def _caliber_matches(item_cal):
                        if not filter_calibers:
                            return True
                        if not item_cal:
                            return False
                        return str(item_cal).lower().strip()in filter_calibers

                    def _get_variant_name(itm):
                        v = itm.get('variant')
                        if v:
                            return str(v)
                        n = itm.get('name')
                        if n:
                            return str(n)
                        return 'Unknown'

                    def _process_item(itm):
                        if not itm or not isinstance(itm, dict):
                            return
                        if itm.get('magazinesystem')or itm.get('capacity'):
                            return
                        itm_cal = itm.get('caliber')
                        if not _caliber_matches(itm_cal):
                            return
                        rds = itm.get('rounds')
                        if isinstance(rds, list)and rds:
                            for r in rds:
                                if isinstance(r, dict):
                                    r_cal = r.get('caliber')
                                    if not _caliber_matches(r_cal):
                                        continue
                                    variant = _get_variant_name(r)
                                    variants[variant]= variants.get(variant, 0)+1
                            return
                        qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                        if qty >0:
                            variant = _get_variant_name(itm)
                            variants[variant]= variants.get(variant, 0)+qty
                            return
                        if itm.get('caliber'):
                            variant = _get_variant_name(itm)
                            variants[variant]= variants.get(variant, 0)+1

                    for itm in save_data.get('hands', {}).get('items', []):
                        _process_item(itm)
                    for slot_name, eq_item in save_data.get('equipment', {}).items():
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for itm in eq_item.get('items', [])or[]:
                            _process_item(itm)
                        for sub in eq_item.get('subslots', [])or[]:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                for itm in curr.get('items', [])or[]:
                                    _process_item(itm)
                    return variants

                is_infinite = bool(wpn.get('infinite_ammo'))

                if is_infinite:
                    available_by_variant = {'Infinite':9999}
                else:
                    available_by_variant = {} if is_en_bloc else _get_available_rounds_by_variant_internal()

                total_available = sum(available_by_variant.values())

                def _find_compatible_clips_internal():
                    clips_found = []
                    wpn_clip_type = wpn.get('clip_type')
                    wpn_mag_system = str(wpn.get('magazinesystem') or '').strip()
                    if not ((wpn.get('accepts_clips') and wpn_clip_type) or (is_en_bloc and wpn_mag_system)):
                        return clips_found
                    def _check_clip(itm, location):
                        if not itm or not isinstance(itm, dict):
                            return
                        clip_rounds = itm.get('rounds', [])
                        if not isinstance(clip_rounds, list) or len(clip_rounds) <= 0:
                            return
                        if is_en_bloc:
                            if str(itm.get('magazinesystem') or '').strip() == wpn_mag_system:
                                clips_found.append({'clip': itm, 'location': location})
                        elif itm.get('clip_type') and str(itm.get('clip_type')).strip() == str(wpn_clip_type).strip():
                            clips_found.append({'clip': itm, 'location': location})
                    for itm in save_data.get('hands', {}).get('items', []):
                        _check_clip(itm, 'hands')
                    for slot_name, eq_item in save_data.get('equipment', {}).items():
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for itm in eq_item.get('items', []) or []:
                            _check_clip(itm, 'equipment')
                        for sub in eq_item.get('subslots', []) or []:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                for itm in curr.get('items', []) or []:
                                    _check_clip(itm, 'equipment')
                    return clips_found

                available_clips = _find_compatible_clips_internal() if (wpn.get('accepts_clips') or is_en_bloc) else []

                if 'tube'in mag_type:
                    if total_available <=0:
                        self._popup_show_info('Internal Reload', 'No compatible ammunition found!')
                        return
                    _open_tube_magazine_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite)
                elif 'box'in mag_type or is_en_bloc:
                    if total_available <=0 and not available_clips:
                        msg = 'No compatible en bloc clips found!' if is_en_bloc else 'No compatible ammunition or clips found!'
                        self._popup_show_info('Internal Reload', msg)
                        return
                    _open_internal_box_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite, available_clips, is_en_bloc = is_en_bloc)
                else:
                    if is_infinite:
                        _open_internal_box_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite, is_en_bloc = is_en_bloc)
                    else:
                        _handle_bolt_only_reload(wpn, caliber)

            except Exception:
                logging.exception('Failed internal magazine reload')

        def _handle_bolt_only_reload(wpn, caliber):
            try:
                self._play_weapon_action_sound(wpn, 'boltback', block = True)
                import time as _t_bolt
                _t_bolt.sleep(0.3)
                self._play_weapon_action_sound(wpn, 'boltforward', block = False)
                update_weapon_view()
            except Exception:
                logging.exception("Suppressed exception")

        def _open_internal_box_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite = False, available_clips = None, is_en_bloc = False):
            import tkinter as _tk_ib
            try:
                _ibe_act_raw = wpn.get('action', '') or ''
                if isinstance(_ibe_act_raw, (list, tuple)):
                    _ibe_act_raw = _ibe_act_raw[0] if _ibe_act_raw else ''
                _ibe_act = str(_ibe_act_raw).lower()
                _ibe_plat_raw = wpn.get('platform', '') or ''
                if isinstance(_ibe_plat_raw, (list, tuple)):
                    _ibe_plat_raw = _ibe_plat_raw[0] if _ibe_plat_raw else ''
                _ibe_plat = str(_ibe_plat_raw).lower()
                _ibe_mag = str(wpn.get('magazinetype', '') or '').lower()
                _ibe_is_pump = ('pump' in _ibe_plat or _ibe_act == 'pump' or 'pump' in _ibe_mag)
                _ibe_is_bolt = _ibe_act in ('bolt', 'lever', 'single')
                if _ibe_is_pump:
                    try:
                        self._play_weapon_action_sound(wpn, 'pumpback', block = True)
                    except Exception:
                        logging.exception("Suppressed exception")
                elif _ibe_is_bolt:
                    try:
                        self._play_weapon_action_sound(wpn, 'boltactionback', block = True)
                    except Exception:
                        logging.exception("Suppressed exception")

                editor = customtkinter.CTkToplevel(self.root)
                editor.title('En Bloc Loader' if is_en_bloc else 'Internal Magazine Loader')
                editor.transient(self.root)
                cap = int(wpn.get('capacity', 0)or 0)
                existing = list(wpn.get('rounds', [])or[])
                _garand_hold_open_reload = bool(is_en_bloc and wpn.get('bolt_catch') and not wpn.get('chambered') and len(existing) == 0)

                _weapon_accepts_clips = bool(wpn.get('accepts_clips') or is_en_bloc)
                _clip_list = list(available_clips) if available_clips else []
                if cap <= 0:
                    _cap_candidates = []
                    try:
                        if isinstance(wpn.get('loaded'), dict):
                            _cap_candidates.append(int(wpn['loaded'].get('capacity', 0) or 0))
                    except Exception:
                        logging.exception("Suppressed exception")
                    for _clip_entry in _clip_list:
                        try:
                            _clip_obj = _clip_entry.get('clip', {})
                            _cap_candidates.append(int(_clip_obj.get('capacity', 0) or 0))
                            _clip_rounds = _clip_obj.get('rounds', [])
                            if isinstance(_clip_rounds, list):
                                _cap_candidates.append(len(_clip_rounds))
                        except Exception:
                            logging.exception("Suppressed exception")
                    cap = max([c for c in _cap_candidates if c > 0], default = (8 if is_en_bloc else 10))

                SLOT_H = 28
                SLOT_W = 260
                ox_mag = 20

                vlist = sorted(available_by_variant.keys())
                cpal =['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                vcols = {v:cpal[i %len(cpal)]for i, v in enumerate(vlist)}

                vtips = {}
                try:
                    _ammo_tbl = self._get_ammo_table_data()
                    for _atbl in _ammo_tbl:
                        _ac = _atbl.get('caliber')
                        _match = False
                        if isinstance(_ac, list):
                            _match = caliber in _ac if caliber else False
                        else:
                            _match =(_ac ==caliber)if caliber else False
                        if _match:
                            for _av in _atbl.get('variants', []):
                                _atn = _av.get('name')
                                _att = _av.get('tip')
                                if _atn and _att and isinstance(_att, str)and _att.startswith('#'):
                                    vtips[_atn]= _att
                            break
                except Exception:
                    logging.exception("Suppressed exception")

                def _tip_for(vn):
                    return vtips.get(vn, '#e0c060')

                def _tip_ol_for(vn):
                    tc = vtips.get(vn)
                    if not tc:
                        return '#aa8820'
                    try:
                        r_v = int(tc[1:3], 16)
                        g_v = int(tc[3:5], 16)
                        b_v = int(tc[5:7], 16)
                        return f'#{max(0, r_v -40):02x}{max(0, g_v -40):02x}{max(0, b_v -40):02x}'
                    except Exception:
                        return '#aa8820'

                def _tip_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant')or r.get('name')or 'Unknown'
                        return _tip_for(vn)
                    return '#e0c060'

                def _tip_ol_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant')or r.get('name')or 'Unknown'
                        return _tip_ol_for(vn)
                    return '#aa8820'

                CHIP_W, CHIP_H, CHIP_PAD = 130, 28, 6
                _cols = max(1, (SLOT_W +40)//(CHIP_W +CHIP_PAD))
                _rows_need = max(1, (len(vlist)+_cols -1)//_cols)if vlist else 1
                SEL_H = 22 +_rows_need *(CHIP_H +CHIP_PAD)+4
                HINT_H = 22
                MAG_TOP = SEL_H +HINT_H
                SPRING_H = 14
                CLIP_PANEL_W = 180
                _has_clips = bool(_weapon_accepts_clips and _clip_list)
                canvas_h = MAG_TOP +cap *SLOT_H +SPRING_H +8
                canvas_w = SLOT_W +40 + (CLIP_PANEL_W + 30 if _has_clips else 0)
                CLIP_PANEL_X = SLOT_W + 55

                main_frame = customtkinter.CTkFrame(editor)
                main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                effective_h = min(canvas_h, 650)
                mag_canvas = _tk_ib.Canvas(main_frame, width = canvas_w, height = effective_h, bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                if canvas_h >650:
                    _mc_scroll = _tk_ib.Scrollbar(main_frame, orient = 'vertical', command = mag_canvas.yview)
                    _mc_scroll.pack(side = 'right', fill = 'y')
                    mag_canvas.configure(yscrollcommand = _mc_scroll.set, scrollregion =(0, 0, canvas_w, canvas_h))
                mag_canvas.pack(side = 'left', fill = 'both', expand = True)

                side = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 180)
                side.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                ls = {'dragging':False, 'drag_vn':None, 'di':None, 'dt':None, 'do':None,
                'added':0, 'stoggle':0, 'animating':False,
                'clip_dragging':False, 'clip_idx':None, 'clip_di':None, 'clip_dt':None}

                chip_hitboxes = {}
                clip_hitboxes = {}

                def _draw_chips():
                    mag_canvas.delete('chips')
                    _chip_cx = ox_mag + SLOT_W // 2
                    mag_canvas.create_text(_chip_cx, 10, text = 'AVAILABLE ROUNDS', fill = '#888888',
                    font =('Consolas', 9, 'bold'), tags = 'chips')
                    if not vlist:
                        _no_rounds_text = 'Use loaded en bloc clips' if is_en_bloc else 'No rounds available'
                        mag_canvas.create_text(_chip_cx, SEL_H //2 +10, text = _no_rounds_text,
                        fill = '#555555', font =('Consolas', 9), tags = 'chips')
                        return
                    _chip_area_w = SLOT_W + 40
                    start_x =(_chip_area_w -min(len(vlist), _cols)*(CHIP_W +CHIP_PAD)+CHIP_PAD)//2
                    for idx, vn in enumerate(vlist):
                        cnt = available_by_variant.get(vn, 0)
                        row_i = idx //_cols
                        col_i = idx %_cols
                        x1 = start_x +col_i *(CHIP_W +CHIP_PAD)
                        y1 = 22 +row_i *(CHIP_H +CHIP_PAD)
                        x2 = x1 +CHIP_W
                        y2 = y1 +CHIP_H
                        chip_hitboxes[vn]=(x1, y1, x2, y2)
                        c = vcols.get(vn, '#c4a032')
                        is_avail = cnt >0
                        fill = c if is_avail else '#2a2a2a'
                        ol = '#dddddd'if is_avail else '#3a3a3a'
                        mag_canvas.create_rectangle(x1, y1, x2, y2, fill = fill, outline = ol, width = 1, tags = 'chips')
                        mag_canvas.create_oval(x1 +3, y1 +3, x1 +19, y2 -3, fill = _tip_for(vn)if is_avail else '#3a3a3a',
                        outline = _tip_ol_for(vn)if is_avail else '#3a3a3a', tags = 'chips')
                        disp = vn if len(vn)<=11 else vn[:10]+'\u2026'
                        cnt_str = '\u221e'if is_infinite else str(cnt)
                        mag_canvas.create_text((x1 +x2)//2 +8, (y1 +y2)//2,
                        text = f'{disp} x{cnt_str}',
                        fill = '#1a1a1a'if is_avail else '#555555',
                        font =('Consolas', 8, 'bold'), tags = 'chips')

                def _draw_mag_body():
                    mag_canvas.delete('mag')
                    oy = MAG_TOP
                    _mag_cx = ox_mag + SLOT_W // 2
                    mag_canvas.create_text(_mag_cx, MAG_TOP -10, text = '\u2193 DROP INTO MAGAZINE \u2193',
                    fill = '#555555', font =('Consolas', 9), tags = 'mag')
                    mag_canvas.create_rectangle(ox_mag, oy, ox_mag +SLOT_W, oy +cap *SLOT_H,
                    outline = '#888888', width = 2, tags = 'mag')
                    mag_canvas.create_line(ox_mag, oy, ox_mag -15, oy -8, fill = '#888888', width = 2, tags = 'mag')
                    mag_canvas.create_line(ox_mag +SLOT_W, oy, ox_mag +SLOT_W +15, oy -8,
                    fill = '#888888', width = 2, tags = 'mag')
                    for i in range(cap):
                        sy = oy +i *SLOT_H
                        if i >0:
                            mag_canvas.create_line(ox_mag, sy, ox_mag +SLOT_W, sy, fill = '#444444',
                            dash =(2, 2), tags = 'mag')
                        if i <len(existing):
                            r = existing[i]
                            vn = r.get('variant')if isinstance(r, dict)else str(r)if r else 'Unknown'
                            c = vcols.get(vn, '#c4a032')
                            mag_canvas.create_rectangle(ox_mag +2, sy +2, ox_mag +SLOT_W -2, sy +SLOT_H -2,
                            fill = c, outline = '#222222', tags = 'mag')
                            mag_canvas.create_oval(ox_mag +4, sy +4, ox_mag +22, sy +SLOT_H -4,
                            fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'mag')
                            mag_canvas.create_text(ox_mag +SLOT_W //2 +10, sy +SLOT_H //2, text = vn, # type: ignore
                            fill = '#1a1a1a', font =('Consolas', 9, 'bold'), tags = 'mag')
                        else:
                            mag_canvas.create_text(ox_mag +SLOT_W //2, sy +SLOT_H //2, text = '[empty]',
                            fill = '#444444', font =('Consolas', 9), tags = 'mag')
                    by = oy +cap *SLOT_H
                    mag_canvas.create_rectangle(ox_mag, by, ox_mag +SLOT_W, by +SPRING_H,
                    fill = '#555555', outline = '#666666', tags = 'mag')
                    mag_canvas.create_text(ox_mag +SLOT_W //2, by +SPRING_H //2,
                    text = '\u25b2 SPRING \u25b2', fill = '#888888',
                    font =('Consolas', 8), tags = 'mag')

                def _draw_clip_panel():
                    mag_canvas.delete('clippanel')
                    clip_hitboxes.clear()
                    if not _has_clips:
                        return
                    _cp_x = CLIP_PANEL_X
                    mag_canvas.create_text(_cp_x + CLIP_PANEL_W // 2, 10,
                    text = 'EN BLOC CLIPS' if is_en_bloc else 'STRIPPER CLIPS', fill = '#888888',
                    font = ('Consolas', 9, 'bold'), tags = 'clippanel')
                    mag_canvas.create_text(_cp_x + CLIP_PANEL_W // 2, 24,
                    text = 'Drag clip into receiver' if is_en_bloc else 'Drag clip onto charger slot',
                    fill = '#555555', font = ('Consolas', 8), tags = 'clippanel')
                    cy = 40
                    CLIP_CHIP_H = 42
                    for ci, clip_entry in enumerate(_clip_list):
                        clip_obj = clip_entry.get('clip', {})
                        clip_rnds = clip_obj.get('rounds', [])
                        clip_name = clip_obj.get('name', 'Clip')
                        clip_cap_c = int(clip_obj.get('capacity', 5) or 5)
                        loaded = len(clip_rnds) if isinstance(clip_rnds, list) else 0
                        has_rounds = loaded > 0
                        x1 = _cp_x
                        y1 = cy
                        x2 = _cp_x + CLIP_PANEL_W
                        y2 = cy + CLIP_CHIP_H - 4
                        fill = '#3a5a3a' if has_rounds else '#2a2a2a'
                        ol = '#66aa66' if has_rounds else '#3a3a3a'
                        mag_canvas.create_rectangle(x1, y1, x2, y2,
                        fill = fill, outline = ol, width = 2, tags = 'clippanel')
                        disp_name = clip_name if len(clip_name) <= 16 else clip_name[:15] + '\u2026'
                        txt_color = '#cccccc' if has_rounds else '#555555'
                        mag_canvas.create_text((x1 + x2) // 2, y1 + 12,
                        text = disp_name,
                        fill = txt_color, font = ('Consolas', 9, 'bold'), tags = 'clippanel')
                        mag_canvas.create_text((x1 + x2) // 2, y1 + 26,
                        text = f'{loaded}/{clip_cap_c} rounds',
                        fill = '#888888' if has_rounds else '#444444',
                        font = ('Consolas', 8), tags = 'clippanel')
                        if has_rounds:
                            clip_hitboxes[ci] = (x1, y1, x2, y2)
                        cy += CLIP_CHIP_H

                def _draw_all():
                    _draw_chips()
                    _draw_mag_body()
                    _draw_clip_panel()

                def _take_round(vname):
                    if is_infinite:
                        return {'name':f'{caliber} | Infinite', 'caliber':caliber, 'variant':'Infinite'}
                    for hi in range(len(save_data.get('hands', {}).get('items', []))-1, -1, -1):
                        itm = save_data['hands']['items'][hi]
                        try:
                            if not itm or not isinstance(itm, dict):
                                continue
                            rds = itm.get('rounds')
                            if isinstance(rds, list)and rds:
                                for ri, r in enumerate(rds):
                                    rv =(r.get('variant')if isinstance(r, dict)else(str(r)if r else None))
                                    if rv ==vname:
                                        return rds.pop(ri)
                            qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                            if qty >0:
                                nm = itm.get('variant')or itm.get('name')or itm.get('caliber')
                                if nm and str(nm)==vname:
                                    itm['quantity']= qty -1
                                    return {k:v for k, v in itm.items()if k !='quantity'}
                            if itm.get('caliber')and(itm.get('variant')or itm.get('name'))and(itm.get('variant')==vname or itm.get('name')==vname):
                                try:
                                    save_data['hands']['items'].pop(hi)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue
                    for _sn_eq, eq_item in list(save_data.get('equipment', {}).items()):
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for cidx in range(len(eq_item.get('items', []))-1, -1, -1):
                            try:
                                itm = eq_item['items'][cidx]
                                if not itm or not isinstance(itm, dict):
                                    continue
                                rds = itm.get('rounds')
                                if isinstance(rds, list)and rds:
                                    for ri, r in enumerate(rds):
                                        rv =(r.get('variant')if isinstance(r, dict)else(str(r)if r else None))
                                        if rv ==vname:
                                            return rds.pop(ri)
                                qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                                if qty >0:
                                    nm = itm.get('variant')or itm.get('name')or itm.get('caliber')
                                    if nm and str(nm)==vname:
                                        itm['quantity']= qty -1
                                        return {k:v for k, v in itm.items()if k !='quantity'}
                            except Exception:
                                logging.exception("Suppressed exception")
                    return None

                def _play_insert():
                    try:
                        sn = f"bulletinsert{ls['stoggle']}"
                        ls['stoggle']= 1 -ls['stoggle']
                        self._play_weapon_action_sound(wpn, sn, block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                def _do_insert_data(vname):
                    if len(existing)>=cap:
                        return False
                    r = _take_round(vname)
                    if r is None:
                        return False
                    existing.insert(0, r)
                    ls['added']+=1
                    if not is_infinite:
                        if vname in available_by_variant:
                            available_by_variant[vname]-=1
                            if available_by_variant[vname]<=0:
                                del available_by_variant[vname]
                    _play_insert()
                    return True

                def _hit_chip(x, y):
                    for vn, (x1, y1, x2, y2)in chip_hitboxes.items():
                        if x1 <=x <=x2 and y1 <=y <=y2 and available_by_variant.get(vn, 0)>0:
                            return vn
                    return None

                def _on_press(event):
                    if ls['animating']:
                        return
                    # Clip-seated mode: click top round to push all rounds down
                    if ls.get('clip_seated'):
                        hb = ls.get('_clip_top_hb')
                        if hb:
                            x1, y1, x2, y2 = hb
                            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                                clip_rounds_ref = ls.get('clip_rounds_ref', [])
                                space = cap - len(existing)
                                n_to_load = min(len(clip_rounds_ref), space)
                                if n_to_load > 0:
                                    ls['clip_push_dragging'] = True
                                    first_rnd = clip_rounds_ref[0]
                                    vn0 = (first_rnd.get('variant') or first_rnd.get('name') or 'Unknown') if isinstance(first_rnd, dict) else str(first_rnd) if first_rnd else 'Unknown'
                                    c0 = vcols.get(vn0, '#c4a032')
                                    ls['clip_push_di'] = mag_canvas.create_rectangle(
                                    ox_mag + 2, event.y - SLOT_H // 2, ox_mag + SLOT_W - 2, event.y + SLOT_H // 2,
                                    fill = c0, outline = '#ffffff', width = 2, tags = 'clippush')
                                    ls['clip_push_do'] = mag_canvas.create_oval(
                                    ox_mag + 4, event.y - SLOT_H // 2 + 2, ox_mag + 22, event.y + SLOT_H // 2 - 2,
                                    fill = _tip_for_round(first_rnd), outline = _tip_ol_for_round(first_rnd), tags = 'clippush')
                                    _lbl = f'{vn0}  (+{n_to_load - 1})' if n_to_load > 1 else vn0
                                    ls['clip_push_dt'] = mag_canvas.create_text(
                                    ox_mag + SLOT_W // 2 + 10, event.y,
                                    text = _lbl, fill = '#1a1a1a',
                                    font = ('Consolas', 10, 'bold'), tags = 'clippush')
                        return
                    # Check clip panel hitboxes first
                    if _has_clips:
                        for ci, (x1, y1, x2, y2) in clip_hitboxes.items():
                            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                                clip_entry = _clip_list[ci]
                                clip_obj = clip_entry.get('clip', {})
                                clip_rnds = clip_obj.get('rounds', [])
                                if isinstance(clip_rnds, list) and len(clip_rnds) > 0 and len(existing) < cap:
                                    ls['clip_dragging'] = True
                                    ls['clip_idx'] = ci
                                    n_rnds = len(clip_rnds)
                                    _cname = clip_obj.get('name', 'Clip')
                                    CLIP_VIS_W = 80
                                    CLIP_VIS_H = min(n_rnds, 5) * SLOT_H + 12
                                    cx = event.x - CLIP_VIS_W // 2
                                    cy = event.y - CLIP_VIS_H // 2
                                    ls['clip_di'] = mag_canvas.create_rectangle(
                                    cx, cy, cx + CLIP_VIS_W, cy + CLIP_VIS_H,
                                    fill = '#707070', outline = '#ffffff', width = 2, tags = 'clipdrag')
                                    ls['clip_dt'] = mag_canvas.create_text(
                                    cx + CLIP_VIS_W // 2, cy + CLIP_VIS_H // 2,
                                    text = f'CLIP\n{n_rnds} rds', fill = '#ffffff',
                                    font = ('Consolas', 8, 'bold'), tags = 'clipdrag')
                                    ls['_clip_vis_w'] = CLIP_VIS_W
                                    ls['_clip_vis_h'] = CLIP_VIS_H
                                    return
                    if is_en_bloc:
                        return
                    if len(existing) >= cap:
                        return
                    vn = _hit_chip(event.x, event.y)
                    if not vn:
                        return
                    ls['dragging']= True
                    ls['drag_vn']= vn
                    c = vcols.get(vn, '#c4a032')
                    ls['di']= mag_canvas.create_rectangle(
                    ox_mag +2, event.y -SLOT_H //2, ox_mag +SLOT_W -2, event.y +SLOT_H //2,
                    fill = c, outline = '#ffffff', width = 2, tags = 'drag')
                    ls['do']= mag_canvas.create_oval(
                    ox_mag +4, event.y -SLOT_H //2 +2, ox_mag +22, event.y +SLOT_H //2 -2,
                    fill = _tip_for(vn), outline = _tip_ol_for(vn), tags = 'drag')
                    ls['dt']= mag_canvas.create_text(
                    ox_mag +SLOT_W //2 +10, event.y,
                    text = vn, fill = '#1a1a1a', font =('Consolas', 10, 'bold'), tags = 'drag')

                def _on_move(event):
                    if ls.get('clip_push_dragging'):
                        y = event.y
                        _pdi = ls.get('clip_push_di')
                        _pdo = ls.get('clip_push_do')
                        _pdt = ls.get('clip_push_dt')
                        if _pdi and _pdt:
                            mag_canvas.coords(_pdi, ox_mag + 2, y - SLOT_H // 2,
                            ox_mag + SLOT_W - 2, y + SLOT_H // 2)
                            if _pdo:
                                mag_canvas.coords(_pdo, ox_mag + 4, y - SLOT_H // 2 + 2,
                                ox_mag + 22, y + SLOT_H // 2 - 2)
                            mag_canvas.coords(_pdt, ox_mag + SLOT_W // 2 + 10, y)
                        return
                    if ls.get('clip_dragging'):
                        cw = ls.get('_clip_vis_w', 80)
                        ch = ls.get('_clip_vis_h', 60)
                        cx = event.x - cw // 2
                        cy = event.y - ch // 2
                        if ls['clip_di'] and ls['clip_dt']:
                            mag_canvas.coords(ls['clip_di'], cx, cy, cx + cw, cy + ch)
                            mag_canvas.coords(ls['clip_dt'], cx + cw // 2, cy + ch // 2)
                        return
                    if not ls['dragging']:
                        return
                    y = event.y
                    ls_di, ls_do, ls_dt = ls['di'], ls['do'], ls['dt']
                    if ls_di and ls_dt and ls_do:
                        mag_canvas.coords(ls_di, ox_mag +2, y -SLOT_H //2,
                        ox_mag +SLOT_W -2, y +SLOT_H //2)
                        mag_canvas.coords(ls_do, ox_mag +4, y -SLOT_H //2 +2,
                        ox_mag +22, y +SLOT_H //2 -2)
                        mag_canvas.coords(ls_dt, ox_mag +SLOT_W //2 +10, y)

                def _on_release(event):
                    if ls.get('clip_push_dragging'):
                        ls['clip_push_dragging'] = False
                        mag_canvas.delete('clippush')
                        clip_rounds_ref = ls.get('clip_rounds_ref', [])
                        if clip_rounds_ref and len(existing) < cap and event.y >= MAG_TOP - 10:
                            # Push all fitting rounds into magazine at once
                            space = cap - len(existing)
                            n_to_load = min(len(clip_rounds_ref), space)
                            for _ in range(n_to_load):
                                rnd = clip_rounds_ref.pop(0)
                                existing.insert(0, rnd)
                                ls['added'] += 1
                            if not is_en_bloc:
                                _play_insert()
                            _redraw_clip_mode()
                            _update_side()
                        ls['clip_push_di'] = ls['clip_push_do'] = ls['clip_push_dt'] = None
                        return
                    if ls.get('clip_dragging'):
                        ls['clip_dragging'] = False
                        mag_canvas.delete('clipdrag')
                        ls['clip_di'] = ls['clip_dt'] = None
                        ci = ls.get('clip_idx')
                        if ci is not None and len(existing) < cap:
                            # Drop zone: near the charger slot (top of magazine area)
                            if event.x <= ox_mag + SLOT_W + 30 and event.y >= MAG_TOP - 40 and event.y <= MAG_TOP + cap * SLOT_H:
                                _animate_clip_load(ci)
                        return
                    if not ls['dragging']:
                        return
                    ls['dragging']= False
                    mag_canvas.delete('drag')
                    ls['di']= ls['dt']= ls['do']= None
                    if len(existing)>=cap or ls['animating']:
                        return
                    vn = ls['drag_vn']
                    if not vn or available_by_variant.get(vn, 0)<=0:
                        return
                    if event.y >=MAG_TOP -15:
                        _animate_push_insert(vn)

                def _animate_push_insert(vname):
                    ls['animating']= True
                    oy = MAG_TOP
                    n_ex = len(existing)
                    c_new = vcols.get(vname, '#c4a032')

                    mag_canvas.delete('mag')
                    mag_canvas.delete('clippanel')
                    mag_canvas.create_text(ox_mag + SLOT_W // 2, MAG_TOP -10, text = '\u2193 DROP INTO MAGAZINE \u2193',
                    fill = '#555555', font =('Consolas', 9), tags = 'magshell')
                    mag_canvas.create_rectangle(ox_mag, oy, ox_mag +SLOT_W, oy +cap *SLOT_H,
                    outline = '#888888', width = 2, tags = 'magshell')
                    mag_canvas.create_line(ox_mag, oy, ox_mag -15, oy -8, fill = '#888888', width = 2, tags = 'magshell')
                    mag_canvas.create_line(ox_mag +SLOT_W, oy, ox_mag +SLOT_W +15, oy -8,
                    fill = '#888888', width = 2, tags = 'magshell')
                    for si in range(1, cap):
                        _sy = oy +si *SLOT_H
                        mag_canvas.create_line(ox_mag, _sy, ox_mag +SLOT_W, _sy, fill = '#444444',
                        dash =(2, 2), tags = 'magshell')
                    _by = oy +cap *SLOT_H
                    mag_canvas.create_rectangle(ox_mag, _by, ox_mag +SLOT_W, _by +SPRING_H,
                    fill = '#555555', outline = '#666666', tags = 'magshell')
                    mag_canvas.create_text(ox_mag +SLOT_W //2, _by +SPRING_H //2,
                    text = '\u25b2 SPRING \u25b2', fill = '#888888',
                    font =('Consolas', 8), tags = 'magshell')
                    for ei in range(n_ex, cap):
                        _esy = oy +ei *SLOT_H
                        mag_canvas.create_text(ox_mag +SLOT_W //2, _esy +SLOT_H //2, text = '[empty]',
                        fill = '#444444', font =('Consolas', 9), tags = 'magshell')

                    anim_ids =[]
                    for i in range(n_ex):
                        r = existing[i]
                        vn_e = r.get('variant')if isinstance(r, dict)else str(r)if r else 'Unknown'
                        c_e = vcols.get(vn_e, '#c4a032')
                        sy = oy +i *SLOT_H
                        _ri = mag_canvas.create_rectangle(ox_mag +2, sy +2, ox_mag +SLOT_W -2, sy +SLOT_H -2,
                        fill = c_e, outline = '#222222', tags = 'pushanim')
                        _oi = mag_canvas.create_oval(ox_mag +4, sy +4, ox_mag +22, sy +SLOT_H -4,
                        fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'pushanim')
                        _ti = mag_canvas.create_text(ox_mag +SLOT_W //2 +10, sy +SLOT_H //2, text = vn_e, # type: ignore
                        fill = '#1a1a1a', font =('Consolas', 9, 'bold'), tags = 'pushanim')
                        anim_ids.append((_ri, _oi, _ti, float(sy)))

                    new_start_y = float(oy -SLOT_H -4)
                    new_target_y = float(oy)
                    _nr = mag_canvas.create_rectangle(ox_mag +2, new_start_y +2, ox_mag +SLOT_W -2,
                    new_start_y +SLOT_H -2, fill = c_new,
                    outline = '#ffffff', width = 2, tags = 'pushanim')
                    _no = mag_canvas.create_oval(ox_mag +4, new_start_y +4, ox_mag +22,
                    new_start_y +SLOT_H -4, fill = _tip_for(vname),
                    outline = _tip_ol_for(vname), tags = 'pushanim')
                    _nt = mag_canvas.create_text(ox_mag +SLOT_W //2 +10, new_start_y +SLOT_H //2,
                    text = vname, fill = '#1a1a1a',
                    font =('Consolas', 10, 'bold'), tags = 'pushanim')

                    total_steps = 10
                    push_per_step = float(SLOT_H)/total_steps
                    new_per_step =(new_target_y -new_start_y)/total_steps

                    def _push_step(step):
                        if step >=total_steps:
                            mag_canvas.delete('pushanim')
                            mag_canvas.delete('magshell')
                            _do_insert_data(vname)
                            _draw_all()
                            _update_side()
                            ls['animating']= False
                            return
                        frac = step +1
                        for _ri, _oi, _ti, base_y in anim_ids:
                            cy = base_y +frac *push_per_step
                            mag_canvas.coords(_ri, ox_mag +2, cy +2, ox_mag +SLOT_W -2, cy +SLOT_H -2)
                            mag_canvas.coords(_oi, ox_mag +4, cy +4, ox_mag +22, cy +SLOT_H -4)
                            mag_canvas.coords(_ti, ox_mag +SLOT_W //2 +10, cy +SLOT_H //2)
                        cn = new_start_y +frac *new_per_step
                        mag_canvas.coords(_nr, ox_mag +2, cn +2, ox_mag +SLOT_W -2, cn +SLOT_H -2)
                        mag_canvas.coords(_no, ox_mag +4, cn +4, ox_mag +22, cn +SLOT_H -4)
                        mag_canvas.coords(_nt, ox_mag +SLOT_W //2 +10, cn +SLOT_H //2)
                        editor.after(25, lambda:_push_step(step +1))

                    _push_step(0)

                mag_canvas.bind('<Button-1>', _on_press)
                mag_canvas.bind('<B1-Motion>', _on_move)
                mag_canvas.bind('<ButtonRelease-1>', _on_release)

                _cap_lbl = customtkinter.CTkLabel(side, text = f'{len(existing)}/{cap} rounds loaded',
                font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                _cap_lbl.pack(pady =(10, 6))

                if is_en_bloc:
                    _side_hint = 'Drag a loaded en bloc\nclip from the right\npanel into the receiver'
                else:
                    _side_hint = 'Click & drag a round\nfrom the top area down\ninto the magazine'
                    if _has_clips:
                        _side_hint += '\n\nDrag clips from right\npanel to charger slot'
                customtkinter.CTkLabel(side, text = _side_hint,
                font = customtkinter.CTkFont(size = 10), text_color = '#888888',
                wraplength = 170).pack(pady = 6)

                def _update_side():
                    _cap_lbl.configure(text = f'{len(existing)}/{cap} rounds loaded')

                def _animate_clip_load(clip_index):
                    if ls.get('clip_seated'):
                        return
                    if clip_index >= len(_clip_list):
                        return
                    clip_entry = _clip_list[clip_index]
                    clip_obj = clip_entry.get('clip', {})
                    clip_rounds_ref = clip_obj.get('rounds', [])
                    if not isinstance(clip_rounds_ref, list) or len(clip_rounds_ref) == 0:
                        return
                    space = cap - len(existing)
                    if space <= 0:
                        return
                    n_to_load = min(len(clip_rounds_ref), space)

                    ls['clip_seated'] = True
                    ls['clip_seated_idx'] = clip_index
                    ls['clip_rounds_ref'] = clip_rounds_ref
                    ls['clip_push_dragging'] = False
                    ls['clip_push_di'] = None
                    ls['clip_push_dt'] = None

                    mag_canvas.delete('mag')
                    mag_canvas.delete('chips')
                    mag_canvas.delete('clippanel')

                    oy = MAG_TOP
                    # Magazine shell
                    mag_canvas.create_text(ox_mag + SLOT_W // 2, MAG_TOP - 10,
                    text = '\u2193 PUSH ROUNDS DOWN \u2193',
                    fill = '#c4a032', font = ('Consolas', 9, 'bold'), tags = 'clipmode')
                    mag_canvas.create_rectangle(ox_mag, oy, ox_mag + SLOT_W, oy + cap * SLOT_H,
                    outline = '#888888', width = 2, tags = 'clipmode')
                    mag_canvas.create_line(ox_mag, oy, ox_mag - 15, oy - 8, fill = '#888888', width = 2, tags = 'clipmode')
                    mag_canvas.create_line(ox_mag + SLOT_W, oy, ox_mag + SLOT_W + 15, oy - 8,
                    fill = '#888888', width = 2, tags = 'clipmode')
                    for si in range(1, cap):
                        _sy = oy + si * SLOT_H
                        mag_canvas.create_line(ox_mag, _sy, ox_mag + SLOT_W, _sy, fill = '#444444',
                        dash = (2, 2), tags = 'clipmode')
                    _by = oy + cap * SLOT_H
                    mag_canvas.create_rectangle(ox_mag, _by, ox_mag + SLOT_W, _by + SPRING_H,
                    fill = '#555555', outline = '#666666', tags = 'clipmode')
                    mag_canvas.create_text(ox_mag + SLOT_W // 2, _by + SPRING_H // 2,
                    text = '\u25b2 SPRING \u25b2', fill = '#888888',
                    font = ('Consolas', 8), tags = 'clipmode')

                    # Clip body seated at charger slot - compact layout
                    CLIP_VIS_W = 80
                    CLIP_RD_H = 18
                    MAX_VIS_RDS = 8
                    n_vis = min(n_to_load, MAX_VIS_RDS)
                    CLIP_BODY_PAD = 14
                    CLIP_VIS_H = n_vis * CLIP_RD_H + CLIP_BODY_PAD
                    clip_x = ox_mag + (SLOT_W - CLIP_VIS_W) // 2
                    clip_seated_y = max(8, oy - CLIP_VIS_H - 2)
                    ls['_clip_vis'] = (clip_x, clip_seated_y, CLIP_VIS_W, CLIP_VIS_H, CLIP_RD_H, n_vis)

                    mag_canvas.create_rectangle(clip_x, clip_seated_y, clip_x + CLIP_VIS_W,
                    clip_seated_y + CLIP_VIS_H, fill = '#707070', outline = '#999999', width = 2, tags = 'clipmode_body')
                    mag_canvas.create_rectangle(clip_x + 10, clip_seated_y - 6,
                    clip_x + CLIP_VIS_W - 10, clip_seated_y + 2, fill = '#888888', outline = '#aaaaaa', tags = 'clipmode_body')

                    _redraw_clip_mode()

                def _redraw_clip_mode():
                    mag_canvas.delete('clipmode_rounds')
                    mag_canvas.delete('clipmode_mag')
                    clip_rounds_ref = ls.get('clip_rounds_ref', [])
                    oy = MAG_TOP
                    clip_x, clip_seated_y, CLIP_VIS_W, CLIP_VIS_H, CLIP_RD_H, MAX_VIS = ls['_clip_vis']
                    space = cap - len(existing)
                    n_to_load = min(len(clip_rounds_ref), space)
                    n_vis = min(n_to_load, MAX_VIS)

                    # Draw rounds in clip (compact) - top round highlighted
                    for ri in range(n_vis):
                        rnd = clip_rounds_ref[ri]
                        vn_r = (rnd.get('variant') or rnd.get('name') or 'Unknown') if isinstance(rnd, dict) else str(rnd) if rnd else 'Unknown'
                        c_r = vcols.get(vn_r, '#c4a032')
                        ry = clip_seated_y + 6 + ri * CLIP_RD_H
                        _is_top = (ri == 0)
                        _rd_ol = '#ffffff' if _is_top else '#333333'
                        _rd_w = 2 if _is_top else 1
                        mag_canvas.create_rectangle(clip_x + 4, ry + 1, clip_x + CLIP_VIS_W - 4, ry + CLIP_RD_H - 1,
                        fill = c_r, outline = _rd_ol, width = _rd_w, tags = 'clipmode_rounds')
                        mag_canvas.create_oval(clip_x + 6, ry + 2, clip_x + 18, ry + CLIP_RD_H - 2,
                        fill = _tip_for_round(rnd), outline = _tip_ol_for_round(rnd), tags = 'clipmode_rounds')
                        disp_r = vn_r if len(vn_r) <= 9 else vn_r[:8] + '\u2026'
                        mag_canvas.create_text(clip_x + CLIP_VIS_W // 2 + 6, ry + CLIP_RD_H // 2,
                        text = disp_r, fill = '#1a1a1a', font = ('Consolas', 7, 'bold'), tags = 'clipmode_rounds')
                    if n_vis > 0:
                        # Push hint on top round
                        _tr_y = clip_seated_y + 6
                        mag_canvas.create_text(clip_x + CLIP_VIS_W + 6, _tr_y + CLIP_RD_H // 2,
                        text = '\u25c0 push', fill = '#888888', anchor = 'w',
                        font = ('Consolas', 7), tags = 'clipmode_rounds')
                    if n_to_load > n_vis:
                        _ey = clip_seated_y + 6 + n_vis * CLIP_RD_H
                        mag_canvas.create_text(clip_x + CLIP_VIS_W // 2, _ey + 4,
                        text = f'+{n_to_load - n_vis} more', fill = '#aaaaaa',
                        font = ('Consolas', 7), tags = 'clipmode_rounds')

                    # Top-round hitbox for push-all interaction
                    if n_vis > 0:
                        _tr_y1 = clip_seated_y + 6 + 1
                        _tr_y2 = clip_seated_y + 6 + CLIP_RD_H - 1
                        ls['_clip_top_hb'] = (clip_x + 4, _tr_y1, clip_x + CLIP_VIS_W - 4, _tr_y2)
                    else:
                        ls['_clip_top_hb'] = None

                    # Draw existing rounds in magazine
                    for i in range(cap):
                        sy = oy + i * SLOT_H
                        if i < len(existing):
                            r = existing[i]
                            vn_e = (r.get('variant') or r.get('name') or 'Unknown') if isinstance(r, dict) else str(r) if r else 'Unknown'
                            c_e = vcols.get(vn_e, '#c4a032')
                            mag_canvas.create_rectangle(ox_mag + 2, sy + 2, ox_mag + SLOT_W - 2, sy + SLOT_H - 2,
                            fill = c_e, outline = '#222222', tags = 'clipmode_mag')
                            mag_canvas.create_oval(ox_mag + 4, sy + 4, ox_mag + 22, sy + SLOT_H - 4,
                            fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'clipmode_mag')
                            mag_canvas.create_text(ox_mag + SLOT_W // 2 + 10, sy + SLOT_H // 2, text = vn_e,
                            fill = '#1a1a1a', font = ('Consolas', 9, 'bold'), tags = 'clipmode_mag')
                        else:
                            mag_canvas.create_text(ox_mag + SLOT_W // 2, sy + SLOT_H // 2, text = '[empty]',
                            fill = '#444444', font = ('Consolas', 9), tags = 'clipmode_mag')

                    # Auto-remove clip if empty
                    if not clip_rounds_ref or n_to_load <= 0:
                        editor.after(200, _unseat_clip)

                def _unseat_clip():
                    if not ls.get('clip_seated'):
                        return
                    ls['clip_seated'] = False
                    ls['clip_push_dragging'] = False
                    mag_canvas.delete('clipmode')
                    mag_canvas.delete('clipmode_body')
                    mag_canvas.delete('clipmode_rounds')
                    mag_canvas.delete('clipmode_mag')
                    mag_canvas.delete('clippush')
                    _draw_all()
                    _update_side()

                def _done():
                    _garand_thumb_result = None
                    if ls.get('clip_seated'):
                        ls['clip_seated'] = False
                        ls['clip_push_dragging'] = False
                        mag_canvas.delete('clipmode')
                        mag_canvas.delete('clipmode_body')
                        mag_canvas.delete('clipmode_rounds')
                        mag_canvas.delete('clipmode_mag')
                        mag_canvas.delete('clippush')
                    if ls['animating']:
                        ls['animating'] = False
                    _rt_act_raw_d = wpn.get('action', '')or ''
                    if isinstance(_rt_act_raw_d, (list, tuple)):
                        _rt_act_raw_d = _rt_act_raw_d[0]if _rt_act_raw_d else ''
                    _rt_act_d = str(_rt_act_raw_d).lower()
                    _is_manual_bolt = _rt_act_d in ('bolt', 'lever', 'single')
                    _bolt_closed = False
                    if ls['added']>0:
                        wpn['rounds']= existing
                        if is_en_bloc:
                            if not wpn.get('chambered') and existing:
                                if not wpn.get('bolt_catch'):
                                    try:
                                        self._play_weapon_action_sound(wpn, 'boltback', block = True)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                try:
                                    self._play_weapon_action_sound(wpn, 'clipinsert', block = True)
                                except Exception:
                                    logging.exception("Suppressed exception")
                                if _garand_hold_open_reload:
                                    _garand_thumb_result = self._maybe_apply_garand_thumb(wpn, save_data)
                                wpn['chambered'] = existing.pop(0)
                                wpn['rounds'] = existing
                                try:
                                    self._play_weapon_action_sound(wpn, 'boltforward')
                                except Exception:
                                    logging.exception("Suppressed exception")
                            else:
                                try:
                                    self._play_weapon_action_sound(wpn, 'clipinsert', block = True)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        elif not wpn.get('chambered')and existing:
                            _rt_mag_type = str(wpn.get('magazinetype', '')or '').lower()
                            _rt_plat_raw = wpn.get('platform', '')or ''
                            if isinstance(_rt_plat_raw, (list, tuple)):
                                _rt_plat_raw = _rt_plat_raw[0]if _rt_plat_raw else ''
                            _rt_plat = str(_rt_plat_raw).lower()
                            _is_pump =('pump'in _rt_plat or _rt_act_d =='pump'or 'pump'in _rt_mag_type)
                            if _is_pump:
                                wpn['chambered']= existing.pop(0)
                                wpn['rounds']= existing
                                try:
                                    self._play_weapon_action_sound(wpn, 'pumpforward')
                                except Exception:
                                    logging.exception("Suppressed exception")
                                _bolt_closed = True
                            elif _is_manual_bolt:
                                wpn['chambered']= existing.pop(0)
                                wpn['rounds']= existing
                                try:
                                    self._play_weapon_action_sound(wpn, 'boltactionforward')
                                except Exception:
                                    logging.exception("Suppressed exception")
                                _bolt_closed = True
                            else:
                                if not wpn.get('bolt_catch'):
                                    try:
                                        self._play_weapon_action_sound(wpn, 'boltback', block = True)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                wpn['chambered']= existing.pop(0)
                                wpn['rounds']= existing
                                try:
                                    self._play_weapon_action_sound(wpn, 'boltforward')
                                except Exception:
                                    logging.exception("Suppressed exception")
                    if _is_manual_bolt and not _bolt_closed:
                        try:
                            self._play_weapon_action_sound(wpn, 'boltactionforward')
                        except Exception:
                            logging.exception("Suppressed exception")
                    editor.destroy()
                    update_weapon_view()
                    if ls['added']>0:
                        _msg_title = 'En Bloc Reload' if is_en_bloc else 'Internal Magazine'
                        _msg_body = f'Inserted en bloc clip with {ls["added"]} rounds' if is_en_bloc else f'Added {ls["added"]} rounds to internal magazine'
                        if isinstance(_garand_thumb_result, dict):
                            if _garand_thumb_result.get('applied'):
                                _msg_body += '\nGarand thumb: Aim -1 for 30 minutes.'
                            elif _garand_thumb_result.get('locked_out'):
                                _msg_body += '\nGarand thumb already received on this character.'
                            else:
                                _msg_body += f'\nGarand thumb check: d20 roll {_garand_thumb_result.get("roll")}'
                        self._popup_show_info(_msg_title, _msg_body)

                editor.protocol('WM_DELETE_WINDOW', _done)
                customtkinter.CTkButton(side, text = 'Done', command = _done, width = 160, height = 35,
                font = customtkinter.CTkFont(size = 12)).pack(pady = 10)

                _draw_all()

                editor.update_idletasks()
                _min_w = 560 if _has_clips else 520
                ew = max(editor.winfo_reqwidth(), _min_w)
                eh = max(editor.winfo_reqheight(), 420)
                _sw_s = editor.winfo_screenwidth()
                _sh_s = editor.winfo_screenheight()
                x =(_sw_s //2)-(ew //2)
                y =(_sh_s //2)-(eh //2)
                editor.geometry(f'{ew}x{eh}+{x}+{y}')
                editor.grab_set()
                editor.lift()
                self._safe_focus(editor)
            except Exception:
                logging.exception('Failed to open internal box magazine loader')

        def _open_cylinder_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite = False, is_topbreak = False):
            import tkinter as _tk_cy
            import math as _math_cy
            try:
                editor = customtkinter.CTkToplevel(self.root)
                editor.title('Top-Break Revolver Loader' if is_topbreak else 'Revolver Cylinder Loader')
                editor.transient(self.root)
                cap = int(wpn.get('capacity', 0) or 0) or 6
                live_rounds = list(wpn.get('rounds', []) or [])
                n_live = len(live_rounds)

                n_spent = int(wpn.get('_cylinder_spent', 0) or 0)
                n_spent = min(n_spent, cap - n_live)

                existing = []
                for i in range(cap):
                    if i < n_live:
                        existing.append(live_rounds[i])
                    elif i < n_live + n_spent:
                        existing.append({'_spent': True, 'caliber': caliber})
                    else:
                        existing.append(None)

                vlist = sorted(available_by_variant.keys())
                cpal = ['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                vcols = {v: cpal[i % len(cpal)] for i, v in enumerate(vlist)}

                vtips = {}
                try:
                    _ammo_tbl = self._get_ammo_table_data()
                    for _atbl in _ammo_tbl:
                        _ac = _atbl.get('caliber')
                        _match = False
                        if isinstance(_ac, list):
                            _match = caliber in _ac if caliber else False
                        else:
                            _match = (_ac == caliber) if caliber else False
                        if _match:
                            for _av in _atbl.get('variants', []):
                                _atn = _av.get('name')
                                _att = _av.get('tip')
                                if _atn and _att and isinstance(_att, str) and _att.startswith('#'):
                                    vtips[_atn] = _att
                            break
                except Exception:
                    logging.exception("Suppressed exception")

                def _tip_for(vn):
                    return vtips.get(vn, '#e0c060')

                def _tip_ol_for(vn):
                    tc = vtips.get(vn)
                    if not tc:
                        return '#aa8820'
                    try:
                        r_v = int(tc[1:3], 16)
                        g_v = int(tc[3:5], 16)
                        b_v = int(tc[5:7], 16)
                        return f'#{max(0, r_v - 40):02x}{max(0, g_v - 40):02x}{max(0, b_v - 40):02x}'
                    except Exception:
                        return '#aa8820'

                def _tip_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant') or r.get('name') or 'Unknown'
                        return _tip_for(vn)
                    return '#e0c060'

                def _tip_ol_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant') or r.get('name') or 'Unknown'
                        return _tip_ol_for(vn)
                    return '#aa8820'

                def _is_spent(r):
                    return isinstance(r, dict) and r.get('_spent', False)

                def _is_live(r):
                    return r is not None and isinstance(r, dict) and not r.get('_spent', False)

                CYL_CX = 200
                CYL_CY = 190
                CYL_R = 120
                CHAMBER_R = 18
                ROD_X = CYL_CX
                ROD_TOP = CYL_CY + CYL_R + 30
                ROD_W = 10
                ROD_H = 60
                ROD_PUSH = 40
                CHIP_W, CHIP_H, CHIP_PAD = 130, 28, 6
                CHIP_AREA_W = CHIP_W + 20

                canvas_w = CYL_CX * 2 + CHIP_AREA_W + 40
                canvas_h = ROD_TOP + ROD_H + ROD_PUSH + 30

                main_frame = customtkinter.CTkFrame(editor)
                main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                cy_canvas = _tk_cy.Canvas(main_frame, width = canvas_w, height = canvas_h,
                    bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                cy_canvas.pack(fill = 'both', expand = True)

                side = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 180)
                side.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                ls = {'open': False, 'dragging': False, 'drag_vn': None, 'di': None,
                    'added': 0, 'stoggle': 0, 'animating': False,
                    'slide_offset': 0.0,
                    'break_offset': 0.0,
                    'cyl_angle': 0.0,
                    'cyl_ang_vel': 0.0,
                    '_spin_job': None,
                    '_spin_active': False,
                    '_spin_dragging': False,
                    '_spin_drag_last_ang': 0.0,
                    '_spin_drag_last_t': 0.0,
                    '_spin_last_chamber_slot': -1,
                    '_drag_open_active': False, '_drag_open_start': 0,
                    '_drag_close_active': False, '_drag_close_start': 0,
                    '_rod_dragging': False, '_rod_drag_start_y': 0, '_rod_offset': 0.0,
                    '_ejecting': False}

                chip_hitboxes = {}

                def _draw_chips():
                    cy_canvas.delete('chips')
                    chip_x = CYL_CX * 2 + 20
                    cy_canvas.create_text(chip_x + CHIP_W // 2, 12, text = 'AVAILABLE ROUNDS',
                        fill = '#888888', font = ('Consolas', 9, 'bold'), tags = 'chips')
                    if not vlist:
                        cy_canvas.create_text(chip_x + CHIP_W // 2, 50, text = 'No rounds',
                            fill = '#555555', font = ('Consolas', 9), tags = 'chips')
                        return
                    for idx, vn in enumerate(vlist):
                        cnt = available_by_variant.get(vn, 0)
                        x1 = chip_x
                        y1 = 28 + idx * (CHIP_H + CHIP_PAD)
                        x2 = x1 + CHIP_W
                        y2 = y1 + CHIP_H
                        chip_hitboxes[vn] = (x1, y1, x2, y2)
                        c = vcols.get(vn, '#c4a032')
                        is_avail = cnt > 0
                        fill = c if is_avail else '#2a2a2a'
                        ol = '#dddddd' if is_avail else '#3a3a3a'
                        cy_canvas.create_rectangle(x1, y1, x2, y2, fill = fill, outline = ol,
                            width = 1, tags = 'chips')
                        cy_canvas.create_oval(x1 + 3, y1 + 3, x1 + 19, y2 - 3,
                            fill = _tip_for(vn) if is_avail else '#3a3a3a',
                            outline = _tip_ol_for(vn) if is_avail else '#3a3a3a', tags = 'chips')
                        disp = vn if len(vn) <= 11 else vn[:10] + '\u2026'
                        cnt_str = '\u221e' if is_infinite else str(cnt)
                        cy_canvas.create_text((x1 + x2) // 2 + 8, (y1 + y2) // 2,
                            text = f'{disp} x{cnt_str}',
                            fill = '#1a1a1a' if is_avail else '#555555',
                            font = ('Consolas', 8, 'bold'), tags = 'chips')

                def _draw_rod():
                    if is_topbreak:
                        return
                    cy_canvas.delete('rod')
                    if not ls['open']:
                        return
                    off = ls['slide_offset']
                    draw_cx = CYL_CX + off
                    rod_y = ROD_TOP + ls['_rod_offset']
                    has_shells = any(r is not None for r in existing)
                    rod_color = '#888888' if has_shells else '#555555'
                    rod_knob = '#aaaaaa' if has_shells else '#666666'
                    cy_canvas.create_rectangle(draw_cx - ROD_W // 2, ROD_TOP - 6,
                        draw_cx + ROD_W // 2, rod_y + ROD_H,
                        fill = '#555555', outline = '#666666', width = 1, tags = 'rod')
                    cy_canvas.create_rectangle(draw_cx - ROD_W // 2 + 1, rod_y,
                        draw_cx + ROD_W // 2 - 1, rod_y + ROD_H,
                        fill = rod_color, outline = '#999999', width = 1, tags = 'rod')
                    cy_canvas.create_oval(draw_cx - ROD_W - 2, rod_y + ROD_H - 4,
                        draw_cx + ROD_W + 2, rod_y + ROD_H + 8,
                        fill = rod_knob, outline = '#bbbbbb', width = 1, tags = 'rod')
                    if has_shells:
                        cy_canvas.create_text(draw_cx, rod_y + ROD_H + 18,
                            text = '\u2193 PUSH TO EJECT \u2193',
                            fill = '#888888', font = ('Consolas', 8), tags = 'rod')

                def _draw_cylinder():
                    cy_canvas.delete('cyl')
                    if not ls['open']:
                        cy_canvas.create_oval(CYL_CX - CYL_R, CYL_CY - CYL_R,
                            CYL_CX + CYL_R, CYL_CY + CYL_R,
                            fill = '#3a3a3a', outline = '#666666', width = 3, tags = 'cyl')
                        cy_canvas.create_oval(CYL_CX - 15, CYL_CY - 15, CYL_CX + 15, CYL_CY + 15,
                            fill = '#222222', outline = '#555555', width = 2, tags = 'cyl')
                        _closed_hint = '\u2193 DRAG DOWN TO OPEN TOP-BREAK \u2193' if is_topbreak else '\u2190 DRAG LEFT TO OPEN CYLINDER \u2190'
                        cy_canvas.create_text(CYL_CX, CYL_CY + CYL_R + 16,
                            text = _closed_hint,
                            fill = '#888888', font = ('Consolas', 10), tags = 'cyl')
                        n_loaded = sum(1 for r in existing if _is_live(r))
                        cy_canvas.create_text(CYL_CX, CYL_CY,
                            text = f'{n_loaded}/{cap}',
                            fill = '#888888', font = ('Consolas', 12, 'bold'), tags = 'cyl')
                        return

                    off = ls['slide_offset']
                    draw_cx = CYL_CX + off
                    draw_cy = CYL_CY + ls.get('break_offset', 0.0)

                    cy_canvas.create_oval(draw_cx - CYL_R, draw_cy - CYL_R,
                        draw_cx + CYL_R, draw_cy + CYL_R,
                        fill = '#2e2e2e', outline = '#777777', width = 3, tags = 'cyl')

                    cy_canvas.create_oval(draw_cx - 12, draw_cy - 12, draw_cx + 12, draw_cy + 12,
                        fill = '#1a1a1a', outline = '#555555', width = 2, tags = 'cyl')

                    positions = []
                    _cyl_ang = float(ls.get('cyl_angle', 0.0))
                    for i in range(cap):
                        angle = (2 * _math_cy.pi * i / cap) - _math_cy.pi / 2 + _cyl_ang
                        cx = draw_cx + CYL_R * 0.65 * _math_cy.cos(angle)
                        cy = draw_cy + CYL_R * 0.65 * _math_cy.sin(angle)
                        positions.append((cx, cy, angle, i))

                    for cx, cy, angle, idx in positions:
                        r = existing[idx]
                        if _is_spent(r):
                            cy_canvas.create_oval(cx - CHAMBER_R, cy - CHAMBER_R,
                                cx + CHAMBER_R, cy + CHAMBER_R,
                                fill = '#2a2a2a', outline = '#555555', width = 2, tags = 'cyl')
                            cy_canvas.create_oval(cx - CHAMBER_R + 5, cy - CHAMBER_R + 5,
                                cx + CHAMBER_R - 5, cy + CHAMBER_R - 5,
                                fill = '#8B7355', outline = '#6B5335',
                                width = 1, tags = 'cyl')
                            cy_canvas.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                fill = '#5a4a3a', outline = '#4a3a2a', tags = 'cyl')
                            cy_canvas.create_text(cx, cy + CHAMBER_R + 10,
                                text = 'spent', fill = '#665544',
                                font = ('Consolas', 7), tags = 'cyl')
                        elif _is_live(r):
                            vn = r.get('variant') or r.get('name') or 'Unknown'
                            c = vcols.get(vn, '#c4a032')
                            cy_canvas.create_oval(cx - CHAMBER_R, cy - CHAMBER_R,
                                cx + CHAMBER_R, cy + CHAMBER_R,
                                fill = '#333333', outline = '#666666', width = 2, tags = 'cyl')
                            cy_canvas.create_oval(cx - CHAMBER_R + 4, cy - CHAMBER_R + 4,
                                cx + CHAMBER_R - 4, cy + CHAMBER_R - 4,
                                fill = _tip_for_round(r), outline = _tip_ol_for_round(r),
                                width = 1, tags = 'cyl')
                            cy_canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3,
                                fill = c, outline = c, tags = 'cyl')
                            disp = vn if len(vn) <= 5 else vn[:4] + '\u2026'
                            cy_canvas.create_text(cx, cy + CHAMBER_R + 10,
                                text = disp, fill = '#aaaaaa',
                                font = ('Consolas', 7), tags = 'cyl')
                        elif r is not None:
                            cy_canvas.create_oval(cx - CHAMBER_R, cy - CHAMBER_R,
                                cx + CHAMBER_R, cy + CHAMBER_R,
                                fill = '#333333', outline = '#666666', width = 2, tags = 'cyl')
                            cy_canvas.create_oval(cx - CHAMBER_R + 4, cy - CHAMBER_R + 4,
                                cx + CHAMBER_R - 4, cy + CHAMBER_R - 4,
                                fill = '#c4a032', outline = '#aa8820',
                                width = 1, tags = 'cyl')
                            cy_canvas.create_text(cx, cy + CHAMBER_R + 10,
                                text = str(idx + 1), fill = '#666666',
                                font = ('Consolas', 7), tags = 'cyl')
                        else:
                            cy_canvas.create_oval(cx - CHAMBER_R, cy - CHAMBER_R,
                                cx + CHAMBER_R, cy + CHAMBER_R,
                                fill = '#1a1a1a', outline = '#555555', width = 2, tags = 'cyl')
                            cy_canvas.create_text(cx, cy,
                                text = str(idx + 1), fill = '#444444',
                                font = ('Consolas', 9), tags = 'cyl')

                    hint = ('DRAG UP TO CLOSE \u2191' if is_topbreak else 'DRAG RIGHT TO CLOSE \u2192') if not ls['animating'] else ''
                    cy_canvas.create_text(draw_cx, draw_cy - CYL_R - 14,
                        text = hint,
                        fill = '#666666', font = ('Consolas', 9), tags = 'cyl')

                def _draw_all():
                    _draw_chips()
                    _draw_cylinder()
                    _draw_rod()

                def _take_round(vname):
                    if is_infinite:
                        return {'name': f'{caliber} | {vname}', 'caliber': caliber, 'variant': vname}
                    for hi in range(len(save_data.get('hands', {}).get('items', [])) - 1, -1, -1):
                        itm = save_data['hands']['items'][hi]
                        try:
                            if not itm or not isinstance(itm, dict):
                                continue
                            rds = itm.get('rounds')
                            if isinstance(rds, list) and rds:
                                for ri, r in enumerate(rds):
                                    rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                    if rv == vname:
                                        return rds.pop(ri)
                            qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                            if qty > 0:
                                nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                if nm and str(nm) == vname:
                                    itm['quantity'] = qty - 1
                                    return {k: v for k, v in itm.items() if k != 'quantity'}
                            if itm.get('caliber') and (itm.get('variant') or itm.get('name')) and (itm.get('variant') == vname or itm.get('name') == vname):
                                try:
                                    save_data['hands']['items'].pop(hi)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue
                    for _sn_eq, eq_item in list(save_data.get('equipment', {}).items()):
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for cidx in range(len(eq_item.get('items', [])) - 1, -1, -1):
                            try:
                                itm = eq_item['items'][cidx]
                                if not itm or not isinstance(itm, dict):
                                    continue
                                rds = itm.get('rounds')
                                if isinstance(rds, list) and rds:
                                    for ri, r in enumerate(rds):
                                        rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                        if rv == vname:
                                            return rds.pop(ri)
                                qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                                if qty > 0:
                                    nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                    if nm and str(nm) == vname:
                                        itm['quantity'] = qty - 1
                                        return {k: v for k, v in itm.items() if k != 'quantity'}
                            except Exception:
                                logging.exception("Suppressed exception")
                    return None

                def _play_insert():
                    try:
                        sn = f"bulletinsert{ls['stoggle']}"
                        ls['stoggle'] = 1 - ls['stoggle']
                        self._play_cylinder_sound(wpn, sn, block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                def _find_empty_chamber():
                    for i in range(cap):
                        if existing[i] is None:
                            return i
                    return None

                def _norm_ang(a):
                    twopi = 2.0 * _math_cy.pi
                    if twopi <= 0.0:
                        return 0.0
                    a = a % twopi
                    if a < 0.0:
                        a += twopi
                    return a

                def _ang_diff(target, source):
                    return (target - source + _math_cy.pi) % (2.0 * _math_cy.pi) - _math_cy.pi

                def _chamber_step_angle():
                    return (2.0 * _math_cy.pi / cap) if cap > 0 else 0.0

                def _chamber_center(i, draw_cx, draw_cy):
                    angle = (2.0 * _math_cy.pi * i / cap) - _math_cy.pi / 2.0 + float(ls.get('cyl_angle', 0.0))
                    cx = draw_cx + CYL_R * 0.65 * _math_cy.cos(angle)
                    cy = draw_cy + CYL_R * 0.65 * _math_cy.sin(angle)
                    return cx, cy

                def _orientation_shift_index():
                    step_ang = _chamber_step_angle()
                    if step_ang <= 0.0:
                        return 0
                    # Chamber at top aligns to the first-to-fire slot when closing.
                    return int(round((-float(ls.get('cyl_angle', 0.0))) / step_ang)) % cap

                def _oriented_existing():
                    if cap <= 1:
                        return list(existing)
                    sh = _orientation_shift_index()
                    return existing[sh:] + existing[:sh]

                def _play_cyl_click():
                    try:
                        threading.Thread(
                            target = lambda: self._safe_sound_play('firearms/universal', 'cylinderspinonce'),
                            daemon = True
                        ).start()
                    except Exception:
                        logging.exception("Suppressed exception")

                def _check_chamber_pass(prev_ang, new_ang):
                    step_ang = _chamber_step_angle()
                    if step_ang <= 0 or cap <= 0:
                        return
                    prev_slot = int(prev_ang / step_ang) % cap
                    new_slot = int(new_ang / step_ang) % cap
                    if prev_slot != new_slot:
                        _play_cyl_click()

                def _cancel_spin_job():
                    job = ls.get('_spin_job')
                    if job is not None:
                        try:
                            editor.after_cancel(job)
                        except Exception:
                            logging.exception("Suppressed exception")
                    ls['_spin_job'] = None

                def _stop_spin_motion(snap_to_chamber = False):
                    _cancel_spin_job()
                    ls['_spin_active'] = False
                    ls['cyl_ang_vel'] = 0.0
                    ls['_spin_dragging'] = False
                    if snap_to_chamber and cap > 0:
                        step_ang = _chamber_step_angle()
                        idx = _orientation_shift_index()
                        ls['cyl_angle'] = _norm_ang(-idx * step_ang)

                def _advance_spin_motion():
                    if not ls.get('_spin_active'):
                        return
                    now_t = time.perf_counter()
                    last_t = float(ls.get('_spin_drag_last_t', now_t))
                    dt = max(0.001, min(0.05, now_t - last_t))
                    ls['_spin_drag_last_t'] = now_t

                    _prev_cyl_ang = float(ls.get('cyl_angle', 0.0))
                    ls['cyl_angle'] = _norm_ang(_prev_cyl_ang + float(ls.get('cyl_ang_vel', 0.0)) * dt)
                    _check_chamber_pass(_prev_cyl_ang, float(ls['cyl_angle']))

                    # Exponential damping gives a natural inertial slowdown.
                    drag_k = 2.2
                    ls['cyl_ang_vel'] = float(ls.get('cyl_ang_vel', 0.0)) * _math_cy.exp(-drag_k * dt)

                    step_ang = _chamber_step_angle()
                    if abs(float(ls.get('cyl_ang_vel', 0.0))) < 0.10 and step_ang > 0.0:
                        idx = _orientation_shift_index()
                        target = _norm_ang(-idx * step_ang)
                        curr = float(ls.get('cyl_angle', 0.0))
                        delta = _ang_diff(target, curr)
                        if abs(delta) <= 0.005:
                            ls['cyl_angle'] = target
                            ls['cyl_ang_vel'] = 0.0
                            ls['_spin_active'] = False
                        else:
                            ls['cyl_angle'] = _norm_ang(curr + delta * 0.35)

                    _draw_cylinder()
                    _draw_rod()

                    if ls.get('_spin_active'):
                        ls['_spin_job'] = editor.after(16, _advance_spin_motion)
                    else:
                        ls['_spin_job'] = None
                        ls['animating'] = False

                def _start_spin_motion(initial_velocity):
                    if ls.get('_ejecting') or not ls.get('open'):
                        return
                    _cancel_spin_job()
                    ls['_spin_active'] = True
                    ls['animating'] = True
                    ls['cyl_ang_vel'] = float(max(-55.0, min(55.0, initial_velocity)))
                    ls['_spin_drag_last_t'] = time.perf_counter()
                    ls['_spin_job'] = editor.after(16, _advance_spin_motion)

                def _hit_chamber(x, y):
                    if not ls['open']:
                        return None
                    off = ls['slide_offset']
                    draw_cx = CYL_CX + off
                    draw_cy = CYL_CY + ls.get('break_offset', 0.0)
                    for i in range(cap):
                        cx, cy = _chamber_center(i, draw_cx, draw_cy)
                        dist = _math_cy.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                        if dist <= CHAMBER_R + 4:
                            return i
                    return None

                def _hit_chip(x, y):
                    for vn, (x1, y1, x2, y2) in chip_hitboxes.items():
                        if x1 <= x <= x2 and y1 <= y <= y2 and available_by_variant.get(vn, 0) > 0:
                            return vn
                    return None

                def _hit_rod(x, y):
                    if is_topbreak:
                        return False
                    if not ls['open']:
                        return False
                    off = ls['slide_offset']
                    draw_cx = CYL_CX + off
                    rod_y = ROD_TOP + ls['_rod_offset']
                    rx1 = draw_cx - ROD_W - 6
                    rx2 = draw_cx + ROD_W + 6
                    ry1 = rod_y
                    ry2 = rod_y + ROD_H + 10
                    return rx1 <= x <= rx2 and ry1 <= y <= ry2

                def _hit_cylinder_body(x, y):
                    if not ls['open']:
                        return False
                    off = ls['slide_offset']
                    draw_cx = CYL_CX + off
                    draw_cy = CYL_CY + ls.get('break_offset', 0.0)
                    dist = _math_cy.sqrt((x - draw_cx) ** 2 + (y - draw_cy) ** 2)
                    return dist <= CYL_R + 10

                def _on_press(event):
                    if ls['animating'] or ls['_ejecting']:
                        return
                    if not ls['open']:
                        ls['_drag_open_start'] = event.y if is_topbreak else event.x
                        ls['_drag_open_active'] = True
                        return
                    if _hit_rod(event.x, event.y):
                        ls['_rod_dragging'] = True
                        ls['_rod_drag_start_y'] = event.y
                        ls['_rod_offset'] = 0.0
                        return
                    if _hit_cylinder_body(event.x, event.y):
                        off = ls['slide_offset']
                        draw_cx = CYL_CX + off
                        draw_cy = CYL_CY + ls.get('break_offset', 0.0)
                        d = _math_cy.sqrt((event.x - draw_cx) ** 2 + (event.y - draw_cy) ** 2)
                        spin_threshold = (CYL_R * 0.45) if is_topbreak else (CYL_R * 0.42)
                        if d >= spin_threshold:
                            _stop_spin_motion(snap_to_chamber = False)
                            ls['_spin_dragging'] = True
                            ls['_spin_drag_last_ang'] = _math_cy.atan2(event.y - draw_cy, event.x - draw_cx)
                            ls['_spin_drag_last_t'] = time.perf_counter()
                            return
                        ls['_drag_close_active'] = True
                        ls['_drag_close_start'] = event.y if is_topbreak else event.x
                        return
                    vn = _hit_chip(event.x, event.y)
                    if not vn:
                        return
                    ls['dragging'] = True
                    ls['drag_vn'] = vn
                    ls['di'] = cy_canvas.create_oval(
                        event.x - CHAMBER_R, event.y - CHAMBER_R,
                        event.x + CHAMBER_R, event.y + CHAMBER_R,
                        fill = _tip_for(vn), outline = '#ffffff', width = 2, tags = 'drag')

                def _on_move(event):
                    if ls.get('_drag_open_active') and not ls['open']:
                        return
                    if ls.get('_spin_dragging'):
                        off = ls['slide_offset']
                        draw_cx = CYL_CX + off
                        draw_cy = CYL_CY + ls.get('break_offset', 0.0)
                        now_ang = _math_cy.atan2(event.y - draw_cy, event.x - draw_cx)
                        prev_ang = float(ls.get('_spin_drag_last_ang', now_ang))
                        delta = _ang_diff(now_ang, prev_ang)
                        now_t = time.perf_counter()
                        dt = max(0.001, min(0.05, now_t - float(ls.get('_spin_drag_last_t', now_t))))
                        ls['_spin_drag_last_t'] = now_t
                        ls['_spin_drag_last_ang'] = now_ang
                        _prev_cyl_ang2 = float(ls.get('cyl_angle', 0.0))
                        ls['cyl_angle'] = _norm_ang(_prev_cyl_ang2 + delta)
                        ls['cyl_ang_vel'] = max(-60.0, min(60.0, delta / dt))
                        _check_chamber_pass(_prev_cyl_ang2, float(ls['cyl_angle']))
                        _draw_cylinder()
                        _draw_rod()
                        return
                    if ls.get('_drag_close_active'):
                        return
                    if ls.get('_rod_dragging'):
                        dy = event.y - ls['_rod_drag_start_y']
                        ls['_rod_offset'] = max(0.0, min(float(ROD_PUSH), float(dy)))
                        _draw_rod()
                        return
                    if not ls['dragging']:
                        return
                    x, y = event.x, event.y
                    if ls['di']:
                        cy_canvas.coords(ls['di'], x - CHAMBER_R, y - CHAMBER_R,
                            x + CHAMBER_R, y + CHAMBER_R)

                def _on_release(event):
                    if ls.get('_drag_open_active') and not ls['open']:
                        ls['_drag_open_active'] = False
                        if is_topbreak:
                            dy = event.y - ls.get('_drag_open_start', event.y)
                            if dy > 60:
                                _animate_open()
                        else:
                            dx = event.x - ls.get('_drag_open_start', event.x)
                            if dx < -60:
                                _animate_open()
                        return
                    if ls.get('_spin_dragging'):
                        ls['_spin_dragging'] = False
                        vel = float(ls.get('cyl_ang_vel', 0.0))
                        if abs(vel) > 0.05:
                            _start_spin_motion(vel)
                        else:
                            _stop_spin_motion(snap_to_chamber = True)
                            _draw_cylinder()
                            _draw_rod()
                        return
                    if ls.get('_drag_close_active'):
                        ls['_drag_close_active'] = False
                        if is_topbreak:
                            dy = event.y - ls.get('_drag_close_start', event.y)
                            if dy < -60:
                                _do_close_and_finish()
                        else:
                            dx = event.x - ls.get('_drag_close_start', event.x)
                            if dx > 60:
                                _do_close_and_finish()
                        return
                    if ls.get('_rod_dragging'):
                        ls['_rod_dragging'] = False
                        if ls['_rod_offset'] >= ROD_PUSH * 0.7:
                            _animate_eject()
                        else:
                            ls['_rod_offset'] = 0.0
                            _draw_rod()
                        return
                    if not ls['dragging']:
                        return
                    ls['dragging'] = False
                    cy_canvas.delete('drag')
                    ls['di'] = None
                    if ls['animating']:
                        return
                    vn = ls['drag_vn']
                    if not vn or available_by_variant.get(vn, 0) <= 0:
                        return
                    chamber_idx = _hit_chamber(event.x, event.y)
                    if chamber_idx is not None and existing[chamber_idx] is None:
                        _do_insert(vn, chamber_idx)
                    else:
                        empty = _find_empty_chamber()
                        if empty is not None:
                            off = ls['slide_offset']
                            draw_cx = CYL_CX + off
                            dist_to_cyl = _math_cy.sqrt((event.x - draw_cx) ** 2 + (event.y - CYL_CY) ** 2)
                            if dist_to_cyl <= CYL_R + 20:
                                _do_insert(vn, empty)

                def _do_insert(vname, chamber_idx):
                    r = _take_round(vname)
                    if r is None:
                        return
                    existing[chamber_idx] = r
                    ls['added'] += 1
                    if not is_infinite:
                        if vname in available_by_variant:
                            available_by_variant[vname] -= 1
                            if available_by_variant[vname] <= 0:
                                del available_by_variant[vname]
                    _play_insert()
                    _draw_all()
                    _update_side()

                def _animate_open():
                    _stop_spin_motion(snap_to_chamber = True)
                    ls['animating'] = True
                    try:
                        self._play_cylinder_sound(wpn, 'cylinderopen', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")
                    target = 80 if is_topbreak else -80
                    steps = 12

                    def _step(s):
                        if s >= steps:
                            if is_topbreak:
                                ls['break_offset'] = float(target)
                            else:
                                ls['slide_offset'] = float(target)
                            ls['open'] = True
                            ls['animating'] = False
                            _draw_all()
                            if is_topbreak and any(r is not None for r in existing):
                                editor.after(80, _animate_eject)
                            return
                        frac = (s + 1) / steps
                        ease = 1 - (1 - frac) ** 2
                        if is_topbreak:
                            ls['break_offset'] = float(target * ease)
                        else:
                            ls['slide_offset'] = float(target * ease)
                        _draw_cylinder()
                        _draw_rod()
                        editor.after(20, lambda: _step(s + 1))

                    ls['open'] = True
                    _step(0)

                def _animate_close(callback = None):
                    _stop_spin_motion(snap_to_chamber = True)
                    ls['animating'] = True
                    try:
                        self._play_cylinder_sound(wpn, 'cylinderclose', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")
                    start_off = ls['break_offset'] if is_topbreak else ls['slide_offset']
                    steps = 10

                    def _step(s):
                        if s >= steps:
                            if is_topbreak:
                                ls['break_offset'] = 0.0
                            else:
                                ls['slide_offset'] = 0.0
                            ls['open'] = False
                            ls['animating'] = False
                            _draw_all()
                            if callback:
                                editor.after(50, callback)
                            return
                        frac = (s + 1) / steps
                        ease = frac * frac
                        if is_topbreak:
                            ls['break_offset'] = float(start_off * (1 - ease))
                        else:
                            ls['slide_offset'] = float(start_off * (1 - ease))
                        _draw_cylinder()
                        _draw_rod()
                        editor.after(20, lambda: _step(s + 1))

                    _step(0)

                def _animate_eject():
                    _stop_spin_motion(snap_to_chamber = True)
                    ls['_ejecting'] = True
                    ls['_rod_offset'] = float(ROD_PUSH if not is_topbreak else 0)
                    _draw_rod()
                    try:
                        self._play_cylinder_sound(wpn, 'cylinderrelease', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                    shells_to_drop = []
                    off = ls['slide_offset']
                    draw_cx = CYL_CX + off
                    draw_cy = CYL_CY + ls.get('break_offset', 0.0)
                    for i in range(cap):
                        r = existing[i]
                        if r is not None:
                            cx, cy = _chamber_center(i, draw_cx, draw_cy)
                            ang = _math_cy.atan2(cy - draw_cy, cx - draw_cx)
                            is_sp = _is_spent(r)
                            shell_fill = '#8B7355' if is_sp else _tip_for_round(r)
                            shell_ol = '#6B5335' if is_sp else _tip_ol_for_round(r)
                            oid = cy_canvas.create_oval(cx - CHAMBER_R + 3, cy - CHAMBER_R + 3,
                                cx + CHAMBER_R - 3, cy + CHAMBER_R - 3,
                                fill = shell_fill, outline = shell_ol, width = 1, tags = 'ejectanim')
                            shells_to_drop.append((oid, cx, cy, ang))
                            existing[i] = None

                    wpn['_cylinder_spent'] = 0
                    _draw_cylinder()

                    drop_steps = 14
                    def _drop_step(s):
                        if s >= drop_steps:
                            cy_canvas.delete('ejectanim')
                            ls['_rod_offset'] = 0.0
                            ls['_ejecting'] = False
                            _draw_all()
                            _update_side()
                            return
                        frac = (s + 1) / drop_steps
                        for oid, sx, sy, ang in shells_to_drop:
                            if is_topbreak:
                                # Top-break ejector star throws cases outward before they drop.
                                radial = 78.0 * frac
                                nx = sx + _math_cy.cos(ang) * radial
                                ny = sy + _math_cy.sin(ang) * radial + (frac * frac) * 120.0 - (1.0 - frac) * 16.0
                            else:
                                ny = sy + frac * 180
                                nx = sx + frac * (sx - draw_cx) * 0.3
                            cy_canvas.coords(oid, nx - CHAMBER_R + 3, ny - CHAMBER_R + 3,
                                nx + CHAMBER_R - 3, ny + CHAMBER_R - 3)
                        editor.after(25, lambda: _drop_step(s + 1))

                    editor.after(80, lambda: _drop_step(0))

                def _do_close_and_finish():
                    if ls['animating'] or ls['_ejecting']:
                        return
                    _stop_spin_motion(snap_to_chamber = True)
                    _oriented = _oriented_existing()
                    final_rounds = [r for r in _oriented if _is_live(r)]
                    remaining_spent = sum(1 for r in _oriented if _is_spent(r))

                    def _finish():
                        wpn['rounds'] = final_rounds
                        wpn['chambered'] = None
                        wpn['_cylinder_spent'] = remaining_spent
                        wpn['_cylinder_layout'] = [r if isinstance(r, dict) else ('__spent__' if _is_spent(r) else None) for r in _oriented]
                        wpn['_cylinder_index'] = 0

                        action = wpn.get('action', '')
                        if isinstance(action, (list, tuple)):
                            action = action[0] if action else ''
                        action = str(action).lower()
                        if action == 'single' and final_rounds:
                            try:
                                self._play_cylinder_sound(wpn, 'hammerdown', block = False)
                            except Exception:
                                logging.exception("Suppressed exception")

                        try:
                            sd_ref = save_data if isinstance(save_data, dict) else globals().get('save_data') or getattr(self, '_current_save_data', None)
                            if isinstance(sd_ref, dict):
                                ts = sd_ref.setdefault('tracked_stats', {})
                                if isinstance(ts, dict):
                                    ts['mags_reloaded_total'] = int(ts.get('mags_reloaded_total', 0)) + 1
                                    added = int(ls['added'])
                                    ts['bullets_loaded_total'] = int(ts.get('bullets_loaded_total', 0)) + added
                                    bh = ts.setdefault('bullets_loaded_history', [])
                                    try:
                                        bh.append({'weapon_id': str(wpn.get('id', 'unknown')), 'count': added, 'time': time.time()})
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception('Failed updating tracked_stats after cylinder reload')
                        try:
                            self._update_session_reload_stats(save_data, int(ls['added']))
                        except Exception:
                            logging.exception("Suppressed exception")

                        editor.destroy()
                        update_weapon_view()
                        if ls['added'] > 0:
                            self._popup_show_info('Cylinder Reload', f'Loaded {ls["added"]} rounds into cylinder ({len(final_rounds)}/{cap})')

                    _animate_close(callback = _finish)

                def _spin_cylinder():
                    if ls['animating'] or not ls['open'] or ls['_ejecting']:
                        return
                    try:
                        self._play_cylinder_sound(wpn, 'cylinderspinonce', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")
                    import random as _rnd_cy
                    if cap <= 1:
                        return
                    direction = 1 if _rnd_cy.random() >= 0.5 else -1
                    launch_vel = direction * _rnd_cy.uniform(11.0, 19.0)
                    _start_spin_motion(launch_vel)

                cy_canvas.bind('<Button-1>', _on_press)
                cy_canvas.bind('<B1-Motion>', _on_move)
                cy_canvas.bind('<ButtonRelease-1>', _on_release)

                _cap_lbl = customtkinter.CTkLabel(side,
                    text = f'{sum(1 for r in existing if _is_live(r))}/{cap} chambers loaded',
                    font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                _cap_lbl.pack(pady = (10, 6))

                _help_txt = 'Drag cylinder down to open.\nAuto-ejects when opened.\nDrag outer cylinder to spin.\nDrag rounds onto chambers.\nDrag cylinder up to close.' if is_topbreak else 'Drag cylinder left to open.\nDrag outer cylinder to spin.\nPush rod down to eject.\nDrag rounds onto chambers.\nDrag center to right to close.'
                customtkinter.CTkLabel(side,
                    text = _help_txt,
                    font = customtkinter.CTkFont(size = 10), text_color = '#888888',
                    wraplength = 170).pack(pady = 6)

                def _update_side():
                    _cap_lbl.configure(text = f'{sum(1 for r in existing if _is_live(r))}/{cap} chambers loaded')

                customtkinter.CTkButton(side, text = 'Spin Cylinder', command = _spin_cylinder,
                    width = 160, height = 30, font = customtkinter.CTkFont(size = 11),
                    fg_color = '#2a4a6a', hover_color = '#3a5a7a').pack(pady = 4)

                def _done():
                    _stop_spin_motion(snap_to_chamber = True)
                    _oriented = _oriented_existing()
                    final_rounds = [r for r in _oriented if _is_live(r)]
                    remaining_spent = sum(1 for r in _oriented if _is_spent(r))

                    def _finish():
                        wpn['rounds'] = final_rounds
                        wpn['chambered'] = None
                        wpn['_cylinder_spent'] = remaining_spent
                        wpn['_cylinder_layout'] = [r if isinstance(r, dict) else ('__spent__' if _is_spent(r) else None) for r in _oriented]
                        wpn['_cylinder_index'] = 0

                        action = wpn.get('action', '')
                        if isinstance(action, (list, tuple)):
                            action = action[0] if action else ''
                        action = str(action).lower()
                        if action == 'single' and final_rounds:
                            try:
                                self._play_cylinder_sound(wpn, 'hammerdown', block = False)
                            except Exception:
                                logging.exception("Suppressed exception")

                        try:
                            sd_ref = save_data if isinstance(save_data, dict) else globals().get('save_data') or getattr(self, '_current_save_data', None)
                            if isinstance(sd_ref, dict):
                                ts = sd_ref.setdefault('tracked_stats', {})
                                if isinstance(ts, dict):
                                    ts['mags_reloaded_total'] = int(ts.get('mags_reloaded_total', 0)) + 1
                                    added = int(ls['added'])
                                    ts['bullets_loaded_total'] = int(ts.get('bullets_loaded_total', 0)) + added
                                    bh = ts.setdefault('bullets_loaded_history', [])
                                    try:
                                        bh.append({'weapon_id': str(wpn.get('id', 'unknown')), 'count': added, 'time': time.time()})
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception('Failed updating tracked_stats after cylinder reload')
                        try:
                            self._update_session_reload_stats(save_data, int(ls['added']))
                        except Exception:
                            logging.exception("Suppressed exception")

                        editor.destroy()
                        update_weapon_view()
                        if ls['added'] > 0:
                            self._popup_show_info('Cylinder Reload', f'Loaded {ls["added"]} rounds into cylinder ({len(final_rounds)}/{cap})')

                    if ls['open']:
                        _animate_close(callback = _finish)
                    else:
                        _finish()

                editor.protocol('WM_DELETE_WINDOW', _done)
                customtkinter.CTkButton(side, text = 'Done', command = _done,
                    width = 160, height = 35,
                    font = customtkinter.CTkFont(size = 12)).pack(pady = 10)

                _draw_all()

                editor.update_idletasks()
                ew = max(editor.winfo_reqwidth(), 620)
                eh = max(editor.winfo_reqheight(), 500)
                _sw_s = editor.winfo_screenwidth()
                _sh_s = editor.winfo_screenheight()
                x = (_sw_s // 2) - (ew // 2)
                y = (_sh_s // 2) - (eh // 2)
                editor.geometry(f'{ew}x{eh}+{x}+{y}')
                editor.grab_set()
                editor.lift()
                self._safe_focus(editor)
            except Exception:
                logging.exception('Failed to open cylinder editor')

        def _open_loading_gate_cylinder_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite = False):
            import tkinter as _tk_lg
            import math as _math_lg
            try:
                editor = customtkinter.CTkToplevel(self.root)
                editor.title('Loading Gate Revolver')
                editor.transient(self.root)

                cap = int(wpn.get('capacity', 0) or 0) or 6
                live_rounds = list(wpn.get('rounds', []) or [])
                n_live = len(live_rounds)
                n_spent = int(wpn.get('_cylinder_spent', 0) or 0)
                n_spent = min(n_spent, max(0, cap - n_live))

                existing = []
                for i in range(cap):
                    if i < n_live:
                        existing.append(live_rounds[i])
                    elif i < n_live + n_spent:
                        existing.append({'_spent': True, 'caliber': caliber})
                    else:
                        existing.append(None)

                vlist = sorted(available_by_variant.keys())
                cpal = ['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                vcols = {v: cpal[i % len(cpal)] for i, v in enumerate(vlist)}

                vtips = {}
                try:
                    _ammo_tbl = self._get_ammo_table_data()
                    for _atbl in _ammo_tbl:
                        _ac = _atbl.get('caliber')
                        _match = False
                        if isinstance(_ac, list):
                            _match = caliber in _ac if caliber else False
                        else:
                            _match = (_ac == caliber) if caliber else False
                        if _match:
                            for _av in _atbl.get('variants', []):
                                _atn = _av.get('name')
                                _att = _av.get('tip')
                                if _atn and _att and isinstance(_att, str) and _att.startswith('#'):
                                    vtips[_atn] = _att
                            break
                except Exception:
                    logging.exception("Suppressed exception")

                def _tip_for(vn):
                    return vtips.get(vn, '#e0c060')

                def _tip_ol_for(vn):
                    tc = vtips.get(vn)
                    if not tc:
                        return '#aa8820'
                    try:
                        r_v = int(tc[1:3], 16)
                        g_v = int(tc[3:5], 16)
                        b_v = int(tc[5:7], 16)
                        return f'#{max(0, r_v - 40):02x}{max(0, g_v - 40):02x}{max(0, b_v - 40):02x}'
                    except Exception:
                        return '#aa8820'

                def _tip_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant') or r.get('name') or 'Unknown'
                        return _tip_for(vn)
                    return '#e0c060'

                def _tip_ol_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant') or r.get('name') or 'Unknown'
                        return _tip_ol_for(vn)
                    return '#aa8820'

                def _is_spent(r):
                    return isinstance(r, dict) and r.get('_spent', False)

                def _is_live(r):
                    return r is not None and isinstance(r, dict) and not r.get('_spent', False)

                CYL_CX = 210
                CYL_CY = 195
                CYL_R = 120
                CHAMBER_R = 18
                CHIP_W, CHIP_H, CHIP_PAD = 130, 28, 6
                CHIP_AREA_W = CHIP_W + 20
                STEP_ANGLE = (2 * _math_lg.pi / cap) if cap > 0 else 0
                GATE_PORT_ANGLE = -STEP_ANGLE if cap > 0 else 0.0
                GATE_X = CYL_CX + (CYL_R + 26) * _math_lg.cos(GATE_PORT_ANGLE)
                GATE_Y = CYL_CY + (CYL_R + 26) * _math_lg.sin(GATE_PORT_ANGLE)
                HAMMER_X = CYL_CX - CYL_R - 42
                HAMMER_Y = CYL_CY - CYL_R + 22
                ROD_X = GATE_X + 58
                ROD_Y = GATE_Y + 24
                ROD_LEN = 64
                ROD_PULL = 46

                canvas_w = CYL_CX * 2 + CHIP_AREA_W + 40
                canvas_h = CYL_CY + CYL_R + 80

                main_frame = customtkinter.CTkFrame(editor)
                main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                cy_canvas = _tk_lg.Canvas(main_frame, width = canvas_w, height = canvas_h,
                    bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                cy_canvas.pack(fill = 'both', expand = True)

                side = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 190)
                side.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                ls = {
                    'hammer_half_cock': False,
                    'gate_open': False,
                    'gate_slide': 0.0,
                    'added': 0,
                    'ejected': 0,
                    'stoggle': 0,
                    'must_spin': False,
                    'chamber_idx': 0,
                    'angle_offset': 0.0,
                    'animating': False,
                    'dragging': False,
                    'drag_vn': None,
                    'di': None,
                    'selected_vn': vlist[0] if vlist else None,
                    '_drag_gate_active': False,
                    '_drag_gate_start': 0,
                    '_drag_spin_active': False,
                    '_drag_spin_start': 0,
                    '_drag_spin_dx': 0,
                    '_tap_active': False,
                    '_tap_x': 0,
                    '_tap_y': 0,
                    '_rod_dragging': False,
                    '_rod_drag_start_x': 0,
                    '_rod_drag_start_off': 0.0,
                    'rod_offset': 0.0,
                }

                chip_hitboxes = {}

                def _take_round(vname):
                    if is_infinite:
                        return {'name': f'{caliber} | {vname}', 'caliber': caliber, 'variant': vname}
                    for hi in range(len(save_data.get('hands', {}).get('items', [])) - 1, -1, -1):
                        itm = save_data['hands']['items'][hi]
                        try:
                            if not itm or not isinstance(itm, dict):
                                continue
                            rds = itm.get('rounds')
                            if isinstance(rds, list) and rds:
                                for ri, r in enumerate(rds):
                                    rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                    if rv == vname:
                                        return rds.pop(ri)
                            qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                            if qty > 0:
                                nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                if nm and str(nm) == vname:
                                    itm['quantity'] = qty - 1
                                    return {k: v for k, v in itm.items() if k != 'quantity'}
                            if itm.get('caliber') and (itm.get('variant') or itm.get('name')) and (itm.get('variant') == vname or itm.get('name') == vname):
                                try:
                                    save_data['hands']['items'].pop(hi)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue
                    for _sn_eq, eq_item in list(save_data.get('equipment', {}).items()):
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for cidx in range(len(eq_item.get('items', [])) - 1, -1, -1):
                            try:
                                itm = eq_item['items'][cidx]
                                if not itm or not isinstance(itm, dict):
                                    continue
                                rds = itm.get('rounds')
                                if isinstance(rds, list) and rds:
                                    for ri, r in enumerate(rds):
                                        rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                        if rv == vname:
                                            return rds.pop(ri)
                                qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                                if qty > 0:
                                    nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                    if nm and str(nm) == vname:
                                        itm['quantity'] = qty - 1
                                        return {k: v for k, v in itm.items() if k != 'quantity'}
                            except Exception:
                                logging.exception("Suppressed exception")
                    return None

                def _play_insert():
                    try:
                        sn = f"bulletinsert{ls['stoggle']}"
                        ls['stoggle'] = 1 - ls['stoggle']
                        self._play_cylinder_sound(wpn, sn, block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                def _get_chamber_center(idx):
                    base_rot = (GATE_PORT_ANGLE + (_math_lg.pi / 2)) - ((2 * _math_lg.pi * ls['chamber_idx'] / cap) if cap > 0 else 0.0)
                    angle = (2 * _math_lg.pi * idx / cap) - _math_lg.pi / 2 + base_rot + ls['angle_offset']
                    cx = CYL_CX + CYL_R * 0.65 * _math_lg.cos(angle)
                    cy = CYL_CY + CYL_R * 0.65 * _math_lg.sin(angle)
                    return cx, cy

                def _active_center():
                    return _get_chamber_center(ls['chamber_idx'])

                def _gate_port_center():
                    return (
                        CYL_CX + CYL_R * 0.65 * _math_lg.cos(GATE_PORT_ANGLE),
                        CYL_CY + CYL_R * 0.65 * _math_lg.sin(GATE_PORT_ANGLE),
                    )

                def _draw_chips():
                    cy_canvas.delete('chips')
                    chip_x = CYL_CX * 2 + 20
                    cy_canvas.create_text(chip_x + CHIP_W // 2, 12, text = 'AVAILABLE ROUNDS',
                        fill = '#888888', font = ('Consolas', 9, 'bold'), tags = 'chips')
                    chip_hitboxes.clear()
                    cur_keys = [v for v in sorted(available_by_variant.keys()) if is_infinite or available_by_variant.get(v, 0) > 0]
                    if not cur_keys and is_infinite:
                        cur_keys = ['Infinite']
                    if not cur_keys:
                        cy_canvas.create_text(chip_x + CHIP_W // 2, 48, text = 'No rounds',
                            fill = '#555555', font = ('Consolas', 9), tags = 'chips')
                        return
                    if ls['selected_vn'] not in cur_keys:
                        ls['selected_vn'] = cur_keys[0]
                    for idx, vn in enumerate(cur_keys):
                        cnt = available_by_variant.get(vn, 0)
                        x1 = chip_x
                        y1 = 28 + idx * (CHIP_H + CHIP_PAD)
                        x2 = x1 + CHIP_W
                        y2 = y1 + CHIP_H
                        chip_hitboxes[vn] = (x1, y1, x2, y2)
                        c = vcols.get(vn, '#c4a032')
                        is_sel = (vn == ls['selected_vn'])
                        ol = '#ffffff' if is_sel else '#dddddd'
                        cy_canvas.create_rectangle(x1, y1, x2, y2, fill = c, outline = ol,
                            width = 2 if is_sel else 1, tags = 'chips')
                        cy_canvas.create_oval(x1 + 3, y1 + 3, x1 + 19, y2 - 3,
                            fill = _tip_for(vn), outline = _tip_ol_for(vn), tags = 'chips')
                        disp = vn if len(vn) <= 11 else vn[:10] + '...'
                        cnt_str = 'inf' if is_infinite else str(cnt)
                        cy_canvas.create_text((x1 + x2) // 2 + 8, (y1 + y2) // 2,
                            text = f'{disp} x{cnt_str}', fill = '#1a1a1a',
                            font = ('Consolas', 8, 'bold'), tags = 'chips')

                def _draw_cylinder():
                    cy_canvas.delete('cyl')

                    hammer_txt = 'HALF-COCK' if ls['hammer_half_cock'] else 'DOWN'
                    hammer_col = '#8fcf7f' if ls['hammer_half_cock'] else '#cf7f7f'
                    cy_canvas.create_text(CYL_CX - 105, 16, text = f'Hammer: {hammer_txt}',
                        fill = hammer_col, font = ('Consolas', 11, 'bold'), tags = 'cyl')

                    gate_txt = 'OPEN' if ls['gate_open'] else 'CLOSED'
                    gate_col = '#8fcf7f' if ls['gate_open'] else '#cf7f7f'
                    cy_canvas.create_text(CYL_CX + 105, 16, text = f'Loading Gate: {gate_txt}',
                        fill = gate_col, font = ('Consolas', 11, 'bold'), tags = 'cyl')

                    cy_canvas.create_oval(CYL_CX - CYL_R, CYL_CY - CYL_R,
                        CYL_CX + CYL_R, CYL_CY + CYL_R,
                        fill = '#2e2e2e', outline = '#777777', width = 3, tags = 'cyl')
                    cy_canvas.create_oval(CYL_CX - 12, CYL_CY - 12, CYL_CX + 12, CYL_CY + 12,
                        fill = '#1a1a1a', outline = '#555555', width = 2, tags = 'cyl')
                    # Sideplate cover keeps most of the cylinder hidden like a fixed-frame loading-gate revolver.
                    cy_canvas.create_oval(CYL_CX - CYL_R + 14, CYL_CY - CYL_R + 14,
                        CYL_CX + CYL_R - 14, CYL_CY + CYL_R - 14,
                        fill = '#252525', outline = '#4e4e4e', width = 2, tags = 'cyl')

                    chx, chy = _active_center()
                    px, py = _gate_port_center()
                    active_round = existing[ls['chamber_idx']]
                    if ls['gate_open'] and ls['hammer_half_cock']:
                        chamber_fill = '#1a1a1a'
                        inner_fill = None
                        inner_ol = None
                        if _is_spent(active_round):
                            chamber_fill = '#2a2a2a'
                            inner_fill = '#8B7355'
                            inner_ol = '#6B5335'
                        elif _is_live(active_round):
                            chamber_fill = '#333333'
                            inner_fill = _tip_for_round(active_round)
                            inner_ol = _tip_ol_for_round(active_round)

                        cy_canvas.create_oval(chx - CHAMBER_R, chy - CHAMBER_R,
                            chx + CHAMBER_R, chy + CHAMBER_R,
                            fill = chamber_fill, outline = '#f0c060', width = 3, tags = 'cyl')
                        if inner_fill is not None:
                            cy_canvas.create_oval(chx - CHAMBER_R + 4, chy - CHAMBER_R + 4,
                                chx + CHAMBER_R - 4, chy + CHAMBER_R - 4,
                                fill = inner_fill, outline = inner_ol or '#666666', width = 1, tags = 'cyl')
                        cy_canvas.create_text(chx, chy - CHAMBER_R - 10, text = 'ACTIVE',
                            fill = '#f0c060', font = ('Consolas', 8, 'bold'), tags = 'cyl')

                    cy_canvas.create_text(GATE_X, GATE_Y + 58,
                        text = 'Gate', fill = '#888888', font = ('Consolas', 8), tags = 'cyl')

                    # Loading gate flap itself (fixed to frame, swings away from port when open).
                    t = float(ls['gate_slide'])
                    flap_cx = px + 56 * t
                    flap_cy = py - 26 * t
                    flap_r = CHAMBER_R + 8
                    flap_col = '#8a6a3a' if ls['gate_open'] else '#5a5a5a'
                    cy_canvas.create_oval(flap_cx - flap_r, flap_cy - flap_r,
                        flap_cx + flap_r, flap_cy + flap_r,
                        fill = flap_col, outline = '#444444', width = 2, tags = 'cyl')
                    cy_canvas.create_oval(flap_cx - flap_r + 6, flap_cy - flap_r + 6,
                        flap_cx + flap_r - 6, flap_cy + flap_r - 6,
                        fill = '#2f2f2f', outline = '#555555', width = 1, tags = 'cyl')
                    hinge_x = px + 8
                    hinge_y = py - flap_r + 4
                    cy_canvas.create_oval(hinge_x - 3, hinge_y - 3, hinge_x + 3, hinge_y + 3,
                        fill = '#b0b0b0', outline = '#8a8a8a', width = 1, tags = 'cyl')

                    if ls['gate_open'] and ls['hammer_half_cock']:
                        cy_canvas.create_oval(px - CHAMBER_R - 4, py - CHAMBER_R - 4,
                            px + CHAMBER_R + 4, py + CHAMBER_R + 4,
                            outline = '#bfa060', width = 2, dash = (3, 2), tags = 'cyl')
                        cy_canvas.create_text(px + 38, py - 26,
                            text = 'Gate port', fill = '#999999', font = ('Consolas', 8), tags = 'cyl')

                        rod_push = float(ls.get('rod_offset', 0.0))
                        rod_tip_x = ROD_X + ROD_LEN + rod_push
                        cy_canvas.create_rectangle(ROD_X, ROD_Y - 4,
                            rod_tip_x, ROD_Y + 4,
                            fill = '#666666', outline = '#888888', width = 1, tags = 'cyl')
                        cy_canvas.create_oval(rod_tip_x - 12, ROD_Y - 10,
                            rod_tip_x + 12, ROD_Y + 10,
                            fill = '#8a8a8a', outline = '#b0b0b0', width = 1, tags = 'cyl')
                        cy_canvas.create_text(ROD_X + ROD_LEN // 2, ROD_Y - 24,
                            text = 'Ejector', fill = '#888888', font = ('Consolas', 8), tags = 'cyl')

                    hammer_off = -10 if ls['hammer_half_cock'] else 0
                    cy_canvas.create_rectangle(HAMMER_X - 16, HAMMER_Y - 28 + hammer_off,
                        HAMMER_X + 16, HAMMER_Y + 20 + hammer_off,
                        fill = '#2a2a2a', outline = '#666666', width = 2, tags = 'cyl')
                    cy_canvas.create_rectangle(HAMMER_X - 8, HAMMER_Y - 38 + hammer_off,
                        HAMMER_X + 8, HAMMER_Y - 10 + hammer_off,
                        fill = '#777777', outline = '#999999', width = 1, tags = 'cyl')
                    cy_canvas.create_text(HAMMER_X, HAMMER_Y + 34,
                        text = 'Hammer', fill = '#888888', font = ('Consolas', 8), tags = 'cyl')

                    if not ls['hammer_half_cock']:
                        cy_canvas.create_text(CYL_CX, CYL_CY + CYL_R + 18,
                            text = 'Click hammer to half-cock',
                            fill = '#888888', font = ('Consolas', 9), tags = 'cyl')
                    elif not ls['gate_open']:
                        cy_canvas.create_text(CYL_CX, CYL_CY + CYL_R + 18,
                            text = 'Drag gate right to open',
                            fill = '#888888', font = ('Consolas', 9), tags = 'cyl')
                    elif ls['must_spin']:
                        cy_canvas.create_text(CYL_CX, CYL_CY + CYL_R + 18,
                            text = 'Drag cylinder to spin to next chamber',
                            fill = '#888888', font = ('Consolas', 9), tags = 'cyl')
                    else:
                        cy_canvas.create_text(CYL_CX, CYL_CY + CYL_R + 18,
                            text = 'Drag round chip to gate port, pull ejector rod to eject',
                            fill = '#888888', font = ('Consolas', 8), tags = 'cyl')

                def _draw_all():
                    _draw_chips()
                    _draw_cylinder()

                def _update_side():
                    _cap_lbl.configure(text = f'{sum(1 for r in existing if _is_live(r))}/{cap} chambers loaded')
                    ch = ls['chamber_idx'] + 1
                    cr = existing[ls['chamber_idx']]
                    if _is_spent(cr):
                        state_txt = 'spent case'
                    elif _is_live(cr):
                        state_txt = 'live round'
                    else:
                        state_txt = 'empty'
                    _ch_lbl.configure(text = f'Active chamber: {ch}/{cap} ({state_txt})')
                    if not ls['hammer_half_cock']:
                        _hint_lbl.configure(text = 'Half-cock the hammer first.')
                    elif not ls['gate_open']:
                        _hint_lbl.configure(text = 'Open loading gate first.')
                    elif ls['must_spin']:
                        _hint_lbl.configure(text = 'Spin cylinder before next action.')
                    else:
                        _hint_lbl.configure(text = 'Load through gate port or eject using rod.')

                def _animate_half_cock():
                    if ls['animating'] or ls['hammer_half_cock']:
                        return
                    ls['animating'] = True
                    try:
                        self._play_cylinder_sound(wpn, 'hammer', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")
                    steps = 8

                    def _step(s):
                        if s >= steps:
                            ls['hammer_half_cock'] = True
                            ls['animating'] = False
                            _draw_all()
                            _update_side()
                            return
                        _draw_cylinder()
                        editor.after(16, lambda: _step(s + 1))

                    _step(0)

                def _animate_gate(opening):
                    if ls['animating'] or not ls['hammer_half_cock']:
                        return
                    ls['animating'] = True
                    try:
                        self._play_cylinder_sound(wpn, 'cylinderopen' if opening else 'cylinderclose', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")
                    steps = 10
                    start = ls['gate_slide']
                    target = 1.0 if opening else 0.0

                    def _step(s):
                        if s >= steps:
                            ls['gate_slide'] = target
                            ls['gate_open'] = opening
                            ls['animating'] = False
                            _draw_all()
                            _update_side()
                            return
                        frac = (s + 1) / steps
                        ls['gate_slide'] = start + (target - start) * frac
                        _draw_cylinder()
                        editor.after(20, lambda: _step(s + 1))

                    _step(0)

                def _animate_spin(direction):
                    if ls['animating'] or not ls['gate_open']:
                        return
                    ls['animating'] = True
                    try:
                        self._play_cylinder_sound(wpn, 'cylinderspinonce', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                    delta = STEP_ANGLE if direction >= 0 else -STEP_ANGLE
                    steps = 12

                    def _step(s):
                        if s >= steps:
                            ls['angle_offset'] = 0.0
                            ls['chamber_idx'] = (ls['chamber_idx'] + (1 if direction >= 0 else -1)) % cap
                            ls['must_spin'] = False
                            ls['animating'] = False
                            _draw_all()
                            _update_side()
                            return
                        frac = (s + 1) / steps
                        ease = 1 - (1 - frac) ** 2
                        ls['angle_offset'] = delta * ease
                        _draw_cylinder()
                        editor.after(24, lambda: _step(s + 1))

                    _step(0)

                def _animate_eject(chx, chy, shell_fill, shell_ol):
                    if ls['animating']:
                        return
                    ls['animating'] = True
                    ls['rod_offset'] = float(ROD_PULL)
                    oid = cy_canvas.create_oval(chx - CHAMBER_R + 4, chy - CHAMBER_R + 4,
                        chx + CHAMBER_R - 4, chy + CHAMBER_R - 4,
                        fill = shell_fill, outline = shell_ol, width = 1, tags = 'ejectanim')
                    try:
                        self._play_cylinder_sound(wpn, 'cylinderrelease', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                    steps = 12

                    def _step(s):
                        if s >= steps:
                            cy_canvas.delete('ejectanim')
                            ls['rod_offset'] = 0.0
                            ls['animating'] = False
                            _draw_all()
                            _update_side()
                            return
                        frac = (s + 1) / steps
                        ls['rod_offset'] = float(max(0.0, ROD_PULL * (1.0 - frac)))
                        nx = chx + frac * 130
                        ny = chy + frac * 14
                        cy_canvas.coords(oid, nx - CHAMBER_R + 4, ny - CHAMBER_R + 4,
                            nx + CHAMBER_R - 4, ny + CHAMBER_R - 4)
                        editor.after(22, lambda: _step(s + 1))

                    _step(0)

                def _try_load_active(vn):
                    if not ls['gate_open'] or ls['must_spin'] or ls['animating']:
                        return False
                    idx = ls['chamber_idx']
                    if existing[idx] is not None:
                        return False
                    if not vn:
                        return False
                    if not is_infinite and available_by_variant.get(vn, 0) <= 0:
                        return False
                    r = _take_round(vn)
                    if r is None:
                        return False
                    existing[idx] = r
                    ls['added'] += 1
                    ls['must_spin'] = True
                    ls['selected_vn'] = vn
                    if not is_infinite:
                        if vn in available_by_variant:
                            available_by_variant[vn] -= 1
                            if available_by_variant[vn] <= 0:
                                del available_by_variant[vn]
                    _play_insert()
                    _draw_all()
                    _update_side()
                    return True

                def _try_eject_active():
                    if not ls['gate_open'] or ls['must_spin'] or ls['animating']:
                        return False
                    idx = ls['chamber_idx']
                    r = existing[idx]
                    if r is None:
                        return False
                    existing[idx] = None
                    ls['ejected'] += 1
                    ls['must_spin'] = True
                    chx, chy = _active_center()
                    is_sp = _is_spent(r)
                    shell_fill = '#8B7355' if is_sp else _tip_for_round(r)
                    shell_ol = '#6B5335' if is_sp else _tip_ol_for_round(r)
                    _animate_eject(chx, chy, shell_fill, shell_ol)
                    return True

                def _hit_chip(x, y):
                    for vn, (x1, y1, x2, y2) in chip_hitboxes.items():
                        if x1 <= x <= x2 and y1 <= y <= y2 and (is_infinite or available_by_variant.get(vn, 0) > 0):
                            return vn
                    return None

                def _hit_gate(x, y):
                    px, py = _gate_port_center()
                    t = float(ls.get('gate_slide', 0.0))
                    flap_cx = px + 56 * t
                    flap_cy = py - 26 * t
                    flap_r = CHAMBER_R + 10
                    return ((x - flap_cx) ** 2 + (y - flap_cy) ** 2) <= (flap_r ** 2)

                def _hit_hammer(x, y):
                    hammer_off = -10 if ls['hammer_half_cock'] else 0
                    return (HAMMER_X - 24) <= x <= (HAMMER_X + 24) and (HAMMER_Y - 45 + hammer_off) <= y <= (HAMMER_Y + 28 + hammer_off)

                def _hit_active(x, y):
                    cx, cy = _active_center()
                    dist = _math_lg.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    return dist <= CHAMBER_R + 6

                def _hit_gate_port(x, y):
                    if not ls['gate_open']:
                        return False
                    px, py = _gate_port_center()
                    return abs(x - px) <= (CHAMBER_R + 10) and abs(y - py) <= (CHAMBER_R + 10)

                def _hit_rod(x, y):
                    if not ls['gate_open']:
                        return False
                    rod_tip_x = ROD_X + ROD_LEN + float(ls.get('rod_offset', 0.0))
                    return (rod_tip_x - 16) <= x <= (rod_tip_x + 16) and (ROD_Y - 14) <= y <= (ROD_Y + 14)

                def _hit_cylinder_body(x, y):
                    dist = _math_lg.sqrt((x - CYL_CX) ** 2 + (y - CYL_CY) ** 2)
                    return dist <= CYL_R + 8

                def _on_press(event):
                    if ls['animating']:
                        return
                    if _hit_hammer(event.x, event.y) and not ls['hammer_half_cock']:
                        _animate_half_cock()
                        return
                    vn = _hit_chip(event.x, event.y)
                    if vn:
                        ls['selected_vn'] = vn
                        ls['dragging'] = True
                        ls['drag_vn'] = vn
                        ls['di'] = cy_canvas.create_oval(
                            event.x - CHAMBER_R, event.y - CHAMBER_R,
                            event.x + CHAMBER_R, event.y + CHAMBER_R,
                            fill = _tip_for(vn), outline = '#ffffff', width = 2, tags = 'drag')
                        _draw_chips()
                        _update_side()
                        return
                    if _hit_gate(event.x, event.y):
                        ls['_drag_gate_active'] = True
                        ls['_drag_gate_start'] = event.x
                        return
                    if ls['gate_open'] and _hit_rod(event.x, event.y):
                        ls['_rod_dragging'] = True
                        ls['_rod_drag_start_x'] = event.x
                        ls['_rod_drag_start_off'] = float(ls.get('rod_offset', 0.0))
                        return
                    if ls['gate_open'] and _hit_active(event.x, event.y):
                        ls['_tap_active'] = True
                        ls['_tap_x'] = event.x
                        ls['_tap_y'] = event.y
                        return
                    if ls['gate_open'] and _hit_cylinder_body(event.x, event.y):
                        ls['_drag_spin_active'] = True
                        ls['_drag_spin_start'] = event.x
                        ls['_drag_spin_dx'] = 0

                def _on_move(event):
                    if ls['dragging'] and ls['di']:
                        cy_canvas.coords(ls['di'], event.x - CHAMBER_R, event.y - CHAMBER_R,
                            event.x + CHAMBER_R, event.y + CHAMBER_R)
                        return
                    if ls.get('_rod_dragging') and not ls['animating']:
                        dx = event.x - ls.get('_rod_drag_start_x', event.x)
                        ls['rod_offset'] = float(max(0.0, min(float(ROD_PULL), ls.get('_rod_drag_start_off', 0.0) + dx)))
                        _draw_cylinder()
                        return
                    if ls.get('_drag_spin_active') and not ls['animating']:
                        dx = event.x - ls.get('_drag_spin_start', event.x)
                        ls['_drag_spin_dx'] = dx
                        if cap > 0:
                            ls['angle_offset'] = max(-STEP_ANGLE * 0.65, min(STEP_ANGLE * 0.65, (dx / 90.0) * STEP_ANGLE))
                            _draw_cylinder()

                def _on_release(event):
                    if ls.get('_drag_gate_active'):
                        ls['_drag_gate_active'] = False
                        dx = event.x - ls.get('_drag_gate_start', event.x)
                        if not ls['gate_open'] and dx > 26:
                            _animate_gate(True)
                        elif ls['gate_open'] and dx < -26:
                            _animate_gate(False)
                        return

                    if ls.get('_drag_spin_active'):
                        ls['_drag_spin_active'] = False
                        dx = ls.get('_drag_spin_dx', 0)
                        ls['_drag_spin_dx'] = 0
                        ls['angle_offset'] = 0.0
                        if abs(dx) > 28 and ls['gate_open'] and not ls['animating']:
                            _animate_spin(1 if dx > 0 else -1)
                        else:
                            _draw_cylinder()
                        return

                    if ls.get('_rod_dragging'):
                        ls['_rod_dragging'] = False
                        if ls.get('rod_offset', 0.0) >= float(ROD_PULL) * 0.65 and ls['gate_open'] and not ls['animating']:
                            _try_eject_active()
                        else:
                            ls['rod_offset'] = 0.0
                            _draw_cylinder()
                            _update_side()
                        return

                    if ls['dragging']:
                        ls['dragging'] = False
                        cy_canvas.delete('drag')
                        ls['di'] = None
                        vn = ls.get('drag_vn')
                        ls['drag_vn'] = None
                        if _hit_gate_port(event.x, event.y):
                            _try_load_active(vn)
                        else:
                            _draw_all()
                            _update_side()
                        return

                    if ls.get('_tap_active'):
                        ls['_tap_active'] = False
                        _draw_all()
                        _update_side()

                cy_canvas.bind('<Button-1>', _on_press)
                cy_canvas.bind('<B1-Motion>', _on_move)
                cy_canvas.bind('<ButtonRelease-1>', _on_release)

                _cap_lbl = customtkinter.CTkLabel(side,
                    text = f'{sum(1 for r in existing if _is_live(r))}/{cap} chambers loaded',
                    font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                _cap_lbl.pack(pady = (10, 6))

                _ch_lbl = customtkinter.CTkLabel(side, text = '',
                    font = customtkinter.CTkFont(size = 11))
                _ch_lbl.pack(pady = (0, 6))

                _hint_lbl = customtkinter.CTkLabel(side,
                    text = '',
                    font = customtkinter.CTkFont(size = 10), text_color = '#888888', wraplength = 170)
                _hint_lbl.pack(pady = (0, 10))

                customtkinter.CTkLabel(side,
                    text = 'Controls:\n- Click hammer to half-cock\n- Drag gate right to open, left to close\n- Drag a round chip to gate port\n- Pull ejector rod to eject\n- Drag cylinder to spin',
                    font = customtkinter.CTkFont(size = 10), text_color = '#888888',
                    wraplength = 170, justify = 'left').pack(pady = (2, 8))

                customtkinter.CTkButton(side, text = 'Spin Once', command = lambda: _animate_spin(1),
                    width = 160, height = 30, font = customtkinter.CTkFont(size = 11),
                    fg_color = '#2a4a6a', hover_color = '#3a5a7a').pack(pady = 4)

                def _done():
                    final_rounds = [r for r in existing if _is_live(r)]
                    remaining_spent = sum(1 for r in existing if _is_spent(r))
                    hammer_restored = False

                    if ls['gate_open']:
                        try:
                            self._play_cylinder_sound(wpn, 'cylinderclose', block = False)
                        except Exception:
                            logging.exception("Suppressed exception")

                    if ls['hammer_half_cock']:
                        try:
                            self._play_cylinder_sound(wpn, 'hammerdown', block = False)
                        except Exception:
                            logging.exception("Suppressed exception")
                        hammer_restored = True
                        ls['hammer_half_cock'] = False

                    wpn['rounds'] = final_rounds
                    wpn['chambered'] = None
                    wpn['_cylinder_spent'] = remaining_spent
                    wpn['_cylinder_layout'] = [r if isinstance(r, dict) else ('__spent__' if _is_spent(r) else None) for r in existing]
                    wpn['_cylinder_index'] = int(ls['chamber_idx']) if cap > 0 else 0

                    action = wpn.get('action', '')
                    if isinstance(action, (list, tuple)):
                        action = action[0] if action else ''
                    action = str(action).lower()
                    if action == 'single' and final_rounds and not hammer_restored:
                        try:
                            self._play_cylinder_sound(wpn, 'hammerdown', block = False)
                        except Exception:
                            logging.exception("Suppressed exception")

                    try:
                        sd_ref = save_data if isinstance(save_data, dict) else globals().get('save_data') or getattr(self, '_current_save_data', None)
                        if isinstance(sd_ref, dict):
                            ts = sd_ref.setdefault('tracked_stats', {})
                            if isinstance(ts, dict):
                                ts['mags_reloaded_total'] = int(ts.get('mags_reloaded_total', 0)) + 1
                                added = int(ls['added'])
                                ts['bullets_loaded_total'] = int(ts.get('bullets_loaded_total', 0)) + added
                                bh = ts.setdefault('bullets_loaded_history', [])
                                try:
                                    bh.append({'weapon_id': str(wpn.get('id', 'unknown')), 'count': added, 'time': time.time()})
                                except Exception:
                                    logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception('Failed updating tracked_stats after loading gate reload')
                    try:
                        self._update_session_reload_stats(save_data, int(ls['added']))
                    except Exception:
                        logging.exception("Suppressed exception")

                    editor.destroy()
                    update_weapon_view()
                    if ls['added'] > 0 or ls['ejected'] > 0:
                        self._popup_show_info('Loading Gate Reload', f'Loaded {ls["added"]} and ejected {ls["ejected"]} rounds ({len(final_rounds)}/{cap})')

                editor.protocol('WM_DELETE_WINDOW', _done)
                customtkinter.CTkButton(side, text = 'Done', command = _done,
                    width = 160, height = 35,
                    font = customtkinter.CTkFont(size = 12)).pack(pady = 10)

                _draw_all()
                _update_side()

                editor.update_idletasks()
                ew = max(editor.winfo_reqwidth(), 660)
                eh = max(editor.winfo_reqheight(), 520)
                _sw_s = editor.winfo_screenwidth()
                _sh_s = editor.winfo_screenheight()
                x = (_sw_s // 2) - (ew // 2)
                y = (_sh_s // 2) - (eh // 2)
                editor.geometry(f'{ew}x{eh}+{x}+{y}')
                editor.grab_set()
                editor.lift()
                self._safe_focus(editor)
            except Exception:
                logging.exception('Failed to open loading gate cylinder editor')

        def _open_tube_magazine_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite = False):
            import tkinter as _tk_tb
            try:
                editor = customtkinter.CTkToplevel(self.root)
                editor.title('Tube Magazine Loader')
                editor.transient(self.root)
                cap = int(wpn.get('capacity', 0)or 0)
                existing = list(wpn.get('rounds', [])or[])

                ROUND_W = 36
                ROUND_H = 22
                TUBE_PAD = 6
                TUBE_H = ROUND_H +TUBE_PAD *2
                TUBE_W = cap *ROUND_W +TUBE_PAD *2
                ox_tube = 30
                oy_tube = 0

                vlist = sorted(available_by_variant.keys())
                cpal =['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                vcols = {v:cpal[i %len(cpal)]for i, v in enumerate(vlist)}

                vtips = {}
                try:
                    _ammo_tbl = self._get_ammo_table_data()
                    for _atbl in _ammo_tbl:
                        _ac = _atbl.get('caliber')
                        _match = False
                        if isinstance(_ac, list):
                            _match = caliber in _ac if caliber else False
                        else:
                            _match =(_ac ==caliber)if caliber else False
                        if _match:
                            for _av in _atbl.get('variants', []):
                                _atn = _av.get('name')
                                _att = _av.get('tip')
                                if _atn and _att and isinstance(_att, str)and _att.startswith('#'):
                                    vtips[_atn]= _att
                            break
                except Exception:
                    logging.exception("Suppressed exception")

                def _tip_for(vn):
                    return vtips.get(vn, '#e0c060')

                def _tip_ol_for(vn):
                    tc = vtips.get(vn)
                    if not tc:
                        return '#aa8820'
                    try:
                        r_v = int(tc[1:3], 16)
                        g_v = int(tc[3:5], 16)
                        b_v = int(tc[5:7], 16)
                        return f'#{max(0, r_v -40):02x}{max(0, g_v -40):02x}{max(0, b_v -40):02x}'
                    except Exception:
                        return '#aa8820'

                def _tip_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant')or r.get('name')or 'Unknown'
                        return _tip_for(vn)
                    return '#e0c060'

                def _tip_ol_for_round(r):
                    if isinstance(r, dict):
                        vn = r.get('variant')or r.get('name')or 'Unknown'
                        return _tip_ol_for(vn)
                    return '#aa8820'

                CHIP_W, CHIP_H, CHIP_PAD = 130, 28, 6
                _cols = max(1, (TUBE_W +ox_tube *2)//(CHIP_W +CHIP_PAD))
                _rows_need = max(1, (len(vlist)+_cols -1)//_cols)if vlist else 1
                SEL_H = 22 +_rows_need *(CHIP_H +CHIP_PAD)+4
                HINT_H = 22
                oy_tube = SEL_H +HINT_H
                canvas_w = max(TUBE_W +ox_tube *2, _cols *(CHIP_W +CHIP_PAD)+40)
                canvas_h = oy_tube +TUBE_H +30

                main_frame = customtkinter.CTkFrame(editor)
                main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                tube_canvas = _tk_tb.Canvas(main_frame, width = canvas_w, height = canvas_h, bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                tube_canvas.pack(side = 'left', fill = 'both', expand = True)

                side = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 180)
                side.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                ls = {'dragging':False, 'drag_vn':None, 'di':None, 'dt':None, 'do':None,
                'added':0, 'stoggle':0, 'animating':False}

                chip_hitboxes = {}

                def _draw_chips():
                    tube_canvas.delete('chips')
                    tube_canvas.create_text(canvas_w //2, 10, text = 'AVAILABLE ROUNDS', fill = '#888888',
                    font =('Consolas', 9, 'bold'), tags = 'chips')
                    if not vlist:
                        tube_canvas.create_text(canvas_w //2, SEL_H //2 +10, text = 'No rounds available',
                        fill = '#555555', font =('Consolas', 9), tags = 'chips')
                        return
                    start_x =(canvas_w -min(len(vlist), _cols)*(CHIP_W +CHIP_PAD)+CHIP_PAD)//2
                    for idx, vn in enumerate(vlist):
                        cnt = available_by_variant.get(vn, 0)
                        row_i = idx //_cols
                        col_i = idx %_cols
                        x1 = start_x +col_i *(CHIP_W +CHIP_PAD)
                        y1 = 22 +row_i *(CHIP_H +CHIP_PAD)
                        x2 = x1 +CHIP_W
                        y2 = y1 +CHIP_H
                        chip_hitboxes[vn]=(x1, y1, x2, y2)
                        c = vcols.get(vn, '#c4a032')
                        is_avail = cnt >0
                        fill = c if is_avail else '#2a2a2a'
                        ol = '#dddddd'if is_avail else '#3a3a3a'
                        tube_canvas.create_rectangle(x1, y1, x2, y2, fill = fill, outline = ol, width = 1, tags = 'chips')
                        tube_canvas.create_oval(x1 +3, y1 +3, x1 +19, y2 -3, fill = _tip_for(vn)if is_avail else '#3a3a3a',
                        outline = _tip_ol_for(vn)if is_avail else '#3a3a3a', tags = 'chips')
                        disp = vn if len(vn)<=11 else vn[:10]+'\u2026'
                        cnt_str = '\u221e'if is_infinite else str(cnt)
                        tube_canvas.create_text((x1 +x2)//2 +8, (y1 +y2)//2,
                        text = f'{disp} x{cnt_str}',
                        fill = '#1a1a1a'if is_avail else '#555555',
                        font =('Consolas', 8, 'bold'), tags = 'chips')

                def _draw_tube_body():
                    tube_canvas.delete('tube')
                    ty = oy_tube
                    tube_canvas.create_text(ox_tube +TUBE_W +15, ty +TUBE_H //2, text = '\u2190 INSERT',
                    fill = '#555555', font =('Consolas', 9), anchor = 'w', tags = 'tube')
                    tube_canvas.create_rectangle(ox_tube, ty, ox_tube +TUBE_W, ty +TUBE_H,
                    outline = '#888888', width = 2, tags = 'tube', fill = '#222222')
                    tube_canvas.create_oval(ox_tube -6, ty +2, ox_tube +6, ty +TUBE_H -2,
                    fill = '#333333', outline = '#888888', tags = 'tube')
                    tube_canvas.create_oval(ox_tube +TUBE_W -6, ty +2, ox_tube +TUBE_W +6, ty +TUBE_H -2,
                    fill = '#444444', outline = '#888888', tags = 'tube')
                    for i in range(cap):
                        sx = ox_tube +TUBE_PAD +(cap -1 -i)*ROUND_W
                        ry1 = ty +TUBE_PAD
                        ry2 = ty +TUBE_H -TUBE_PAD
                        if i <len(existing):
                            r = existing[i]
                            vn = r.get('variant')if isinstance(r, dict)else str(r)if r else 'Unknown'
                            c = vcols.get(vn, '#c4a032')
                            tube_canvas.create_rectangle(sx, ry1, sx +ROUND_W -2, ry2, fill = c, outline = '#222222', tags = 'tube')
                            tube_canvas.create_oval(sx +ROUND_W -12, ry1 +2, sx +ROUND_W -2, ry2 -2,
                            fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'tube')
                        else:
                            tube_canvas.create_rectangle(sx, ry1, sx +ROUND_W -2, ry2,
                            fill = '#1a1a1a', outline = '#333333', dash =(2, 2), tags = 'tube')

                def _draw_all():
                    _draw_chips()
                    _draw_tube_body()

                def _take_round(vname):
                    if is_infinite:
                        return {'name':f'{caliber} | Infinite', 'caliber':caliber, 'variant':'Infinite'}
                    for hi in range(len(save_data.get('hands', {}).get('items', []))-1, -1, -1):
                        itm = save_data['hands']['items'][hi]
                        try:
                            if not itm or not isinstance(itm, dict):
                                continue
                            rds = itm.get('rounds')
                            if isinstance(rds, list)and rds:
                                for ri, r in enumerate(rds):
                                    rv =(r.get('variant')if isinstance(r, dict)else(str(r)if r else None))
                                    if rv ==vname:
                                        return rds.pop(ri)
                            qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                            if qty >0:
                                nm = itm.get('variant')or itm.get('name')or itm.get('caliber')
                                if nm and str(nm)==vname:
                                    itm['quantity']= qty -1
                                    return {k:v for k, v in itm.items()if k !='quantity'}
                            if itm.get('caliber')and(itm.get('variant')or itm.get('name'))and(itm.get('variant')==vname or itm.get('name')==vname):
                                try:
                                    save_data['hands']['items'].pop(hi)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue
                    for _sn_eq, eq_item in list(save_data.get('equipment', {}).items()):
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for cidx in range(len(eq_item.get('items', []))-1, -1, -1):
                            try:
                                itm = eq_item['items'][cidx]
                                if not itm or not isinstance(itm, dict):
                                    continue
                                rds = itm.get('rounds')
                                if isinstance(rds, list)and rds:
                                    for ri, r in enumerate(rds):
                                        rv =(r.get('variant')if isinstance(r, dict)else(str(r)if r else None))
                                        if rv ==vname:
                                            return rds.pop(ri)
                                qty = int(itm.get('quantity')or 0)if isinstance(itm.get('quantity'), (int, float))else 0
                                if qty >0:
                                    nm = itm.get('variant')or itm.get('name')or itm.get('caliber')
                                    if nm and str(nm)==vname:
                                        itm['quantity']= qty -1
                                        return {k:v for k, v in itm.items()if k !='quantity'}
                            except Exception:
                                logging.exception("Suppressed exception")
                    return None

                def _play_insert():
                    try:
                        self._play_weapon_action_sound(wpn, 'tubeinsert', block = False)
                    except Exception:
                        logging.exception("Suppressed exception")

                def _do_insert_data(vname):
                    if len(existing)>=cap:
                        return False
                    r = _take_round(vname)
                    if r is None:
                        return False
                    existing.append(r)
                    ls['added']+=1
                    if not is_infinite:
                        if vname in available_by_variant:
                            available_by_variant[vname]-=1
                            if available_by_variant[vname]<=0:
                                del available_by_variant[vname]
                    _play_insert()
                    return True

                def _hit_chip(x, y):
                    for vn, (x1, y1, x2, y2)in chip_hitboxes.items():
                        if x1 <=x <=x2 and y1 <=y <=y2 and available_by_variant.get(vn, 0)>0:
                            return vn
                    return None

                def _on_press(event):
                    if ls['animating']or len(existing)>=cap:
                        return
                    vn = _hit_chip(event.x, event.y)
                    if not vn:
                        return
                    ls['dragging']= True
                    ls['drag_vn']= vn
                    c = vcols.get(vn, '#c4a032')
                    ls['di']= tube_canvas.create_rectangle(
                    event.x -ROUND_W //2, event.y -ROUND_H //2,
                    event.x +ROUND_W //2, event.y +ROUND_H //2,
                    fill = c, outline = '#ffffff', width = 2, tags = 'drag')
                    ls['do']= tube_canvas.create_oval(
                    event.x +ROUND_W //2 -12, event.y -ROUND_H //2 +2,
                    event.x +ROUND_W //2, event.y +ROUND_H //2 -2,
                    fill = _tip_for(vn), outline = _tip_ol_for(vn), tags = 'drag')
                    ls['dt']= tube_canvas.create_text(
                    event.x, event.y,
                    text = vn[:4], fill = '#1a1a1a', font =('Consolas', 7, 'bold'), tags = 'drag')

                def _on_move(event):
                    if not ls['dragging']:
                        return
                    x, y = event.x, event.y
                    ls_di, ls_do, ls_dt = ls['di'], ls['do'], ls['dt']
                    if ls_di and ls_dt and ls_do:
                        tube_canvas.coords(ls_di, x -ROUND_W //2, y -ROUND_H //2,
                        x +ROUND_W //2, y +ROUND_H //2)
                        tube_canvas.coords(ls_do, x +ROUND_W //2 -12, y -ROUND_H //2 +2,
                        x +ROUND_W //2, y +ROUND_H //2 -2)
                        tube_canvas.coords(ls_dt, x, y)

                def _on_release(event):
                    if not ls['dragging']:
                        return
                    ls['dragging']= False
                    tube_canvas.delete('drag')
                    ls['di']= ls['dt']= ls['do']= None
                    if len(existing)>=cap or ls['animating']:
                        return
                    vn = ls['drag_vn']
                    if not vn or available_by_variant.get(vn, 0)<=0:
                        return
                    drop_zone_right = ox_tube +TUBE_W +6
                    drop_zone_top = oy_tube -10
                    drop_zone_bottom = oy_tube +TUBE_H +10
                    if event.y >=drop_zone_top and event.y <=drop_zone_bottom and event.x >=ox_tube +TUBE_W -40:
                        _animate_tube_insert(vn)

                def _animate_tube_insert(vname):
                    ls['animating']= True
                    ty = oy_tube
                    n_ex = len(existing)
                    c_new = vcols.get(vname, '#c4a032')

                    tube_canvas.delete('tube')
                    tube_canvas.create_text(ox_tube +TUBE_W +15, ty +TUBE_H //2, text = '\u2190 INSERT',
                    fill = '#555555', font =('Consolas', 9), anchor = 'w', tags = 'tubeshell')
                    tube_canvas.create_rectangle(ox_tube, ty, ox_tube +TUBE_W, ty +TUBE_H,
                    outline = '#888888', width = 2, tags = 'tubeshell', fill = '#222222')
                    tube_canvas.create_oval(ox_tube -6, ty +2, ox_tube +6, ty +TUBE_H -2,
                    fill = '#333333', outline = '#888888', tags = 'tubeshell')
                    tube_canvas.create_oval(ox_tube +TUBE_W -6, ty +2, ox_tube +TUBE_W +6, ty +TUBE_H -2,
                    fill = '#444444', outline = '#888888', tags = 'tubeshell')
                    for ei in range(n_ex, cap):
                        sx = ox_tube +TUBE_PAD +(cap -1 -ei)*ROUND_W
                        ry1 = ty +TUBE_PAD
                        ry2 = ty +TUBE_H -TUBE_PAD
                        tube_canvas.create_rectangle(sx, ry1, sx +ROUND_W -2, ry2,
                        fill = '#1a1a1a', outline = '#333333', dash =(2, 2), tags = 'tubeshell')

                    anim_ids =[]
                    for i in range(n_ex):
                        r = existing[i]
                        vn_e = r.get('variant')if isinstance(r, dict)else str(r)if r else 'Unknown'
                        c_e = vcols.get(vn_e, '#c4a032')
                        sx = ox_tube +TUBE_PAD +(cap -1 -i)*ROUND_W
                        ry1 = ty +TUBE_PAD
                        ry2 = ty +TUBE_H -TUBE_PAD
                        _ri = tube_canvas.create_rectangle(sx, ry1, sx +ROUND_W -2, ry2,
                        fill = c_e, outline = '#222222', tags = 'tubeanim')
                        _oi = tube_canvas.create_oval(sx +ROUND_W -12, ry1 +2, sx +ROUND_W -2, ry2 -2,
                        fill = _tip_for_round(r), outline = _tip_ol_for_round(r), tags = 'tubeanim')
                        anim_ids.append((_ri, _oi, float(sx)))

                    new_start_x = float(ox_tube +TUBE_W +10)
                    slot_idx = cap -1 -n_ex
                    new_target_x = float(ox_tube +TUBE_PAD +slot_idx *ROUND_W)
                    ry1 = ty +TUBE_PAD
                    ry2 = ty +TUBE_H -TUBE_PAD
                    _nr = tube_canvas.create_rectangle(new_start_x, ry1, new_start_x +ROUND_W -2, ry2,
                    fill = c_new, outline = '#ffffff', width = 2, tags = 'tubeanim')
                    _no = tube_canvas.create_oval(new_start_x +ROUND_W -12, ry1 +2, new_start_x +ROUND_W -2, ry2 -2,
                    fill = _tip_for(vname), outline = _tip_ol_for(vname), tags = 'tubeanim')

                    total_steps = 10
                    push_per_step = float(-ROUND_W)/total_steps
                    new_per_step =(new_target_x -new_start_x)/total_steps

                    def _tube_step(step):
                        if step >=total_steps:
                            tube_canvas.delete('tubeanim')
                            tube_canvas.delete('tubeshell')
                            _do_insert_data(vname)
                            _draw_all()
                            _update_side()
                            ls['animating']= False
                            return
                        frac = step +1
                        for _ri, _oi, base_x in anim_ids:
                            cx = base_x +frac *push_per_step
                            tube_canvas.coords(_ri, cx, ry1, cx +ROUND_W -2, ry2)
                            tube_canvas.coords(_oi, cx +ROUND_W -12, ry1 +2, cx +ROUND_W -2, ry2 -2)
                        cn = new_start_x +frac *new_per_step
                        tube_canvas.coords(_nr, cn, ry1, cn +ROUND_W -2, ry2)
                        tube_canvas.coords(_no, cn +ROUND_W -12, ry1 +2, cn +ROUND_W -2, ry2 -2)
                        editor.after(25, lambda:_tube_step(step +1))

                    _tube_step(0)

                tube_canvas.bind('<Button-1>', _on_press)
                tube_canvas.bind('<B1-Motion>', _on_move)
                tube_canvas.bind('<ButtonRelease-1>', _on_release)

                _cap_lbl = customtkinter.CTkLabel(side, text = f'{len(existing)}/{cap} rounds loaded',
                font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                _cap_lbl.pack(pady =(10, 6))

                customtkinter.CTkLabel(side, text = 'Click & drag a round\nfrom the top area\nto the tube opening',
                font = customtkinter.CTkFont(size = 10), text_color = '#888888',
                wraplength = 170).pack(pady = 6)

                def _update_side():
                    _cap_lbl.configure(text = f'{len(existing)}/{cap} rounds loaded')

                def _done():
                    if ls['added']>0:
                        wpn['rounds']= existing
                        if not wpn.get('chambered')and existing:
                            _rt_mag_type = str(wpn.get('magazinetype', '')or '').lower()
                            _rt_plat_raw = wpn.get('platform', '')or ''
                            if isinstance(_rt_plat_raw, (list, tuple)):
                                _rt_plat_raw = _rt_plat_raw[0]if _rt_plat_raw else ''
                            _rt_plat = str(_rt_plat_raw).lower()
                            _rt_act_raw = wpn.get('action', '')or ''
                            if isinstance(_rt_act_raw, (list, tuple)):
                                _rt_act_raw = _rt_act_raw[0]if _rt_act_raw else ''
                            _rt_act = str(_rt_act_raw).lower()
                            _is_pump =('pump'in _rt_plat or _rt_act =='pump'or 'pump'in _rt_mag_type)
                            if _is_pump:
                                wpn['chambered']= existing.pop(0)
                                wpn['rounds']= existing
                                try:
                                    self._play_weapon_action_sound(wpn, 'pumpforward')
                                except Exception:
                                    logging.exception("Suppressed exception")
                            else:
                                if not wpn.get('bolt_catch'):
                                    try:
                                        self._play_weapon_action_sound(wpn, 'boltback', block = True)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                wpn['chambered']= existing.pop(0)
                                wpn['rounds']= existing
                                try:
                                    self._play_weapon_action_sound(wpn, 'boltforward')
                                except Exception:
                                    logging.exception("Suppressed exception")
                    editor.destroy()
                    update_weapon_view()
                    if ls['added']>0:
                        self._popup_show_info('Tube Magazine', f'Added {ls["added"]} rounds to tube magazine')

                editor.protocol('WM_DELETE_WINDOW', _done)
                customtkinter.CTkButton(side, text = 'Done', command = _done, width = 160, height = 35,
                font = customtkinter.CTkFont(size = 12)).pack(pady = 10)

                _draw_all()

                editor.update_idletasks()
                ew = max(editor.winfo_reqwidth(), 520)
                eh = max(editor.winfo_reqheight(), 300)
                _sw_s = editor.winfo_screenwidth()
                _sh_s = editor.winfo_screenheight()
                x =(_sw_s //2)-(ew //2)
                y =(_sh_s //2)-(eh //2)
                editor.geometry(f'{ew}x{eh}+{x}+{y}')
                editor.grab_set()
                editor.lift()
                self._safe_focus(editor)
            except Exception:
                logging.exception('Failed to open tube magazine loader')

        def _open_break_action_editor(wpn, available_by_variant, caliber, filter_calibers, is_infinite = False):
            import tkinter as _tk_ba
            try:
                editor = customtkinter.CTkToplevel(self.root)
                editor.title('Break Action Loader')
                editor.transient(self.root)
                try:
                    _raw_cap = wpn.get('capacity')
                    if _raw_cap is None or _raw_cap == '' or _raw_cap == 0:
                        _raw_cap = wpn.get('loaded', {})
                        if isinstance(_raw_cap, dict):
                            _raw_cap = _raw_cap.get('capacity')
                    cap = int(_raw_cap) if _raw_cap else 2
                except Exception:
                    cap = 2
                if cap < 1:
                    cap = 2
                subtype_raw = str(wpn.get('magazinesubtype', '') or '').lower()
                if subtype_raw == 'single' and cap > 1:
                    cap = 1
                existing = list(wpn.get('rounds', []) or [])
                while len(existing) < cap:
                    existing.append(None)
                existing = existing[:cap]

                n_spent = int(wpn.get('_break_spent', 0) or 0)
                n_spent = min(n_spent, cap)
                live_count = sum(1 for r in existing if r is not None)
                if n_spent > 0 and live_count < cap:
                    new_existing = []
                    live_idx = 0
                    live_list = [r for r in existing if r is not None]
                    spent_placed = 0
                    for i in range(cap):
                        if live_idx < len(live_list):
                            new_existing.append(live_list[live_idx])
                            live_idx += 1
                        elif spent_placed < n_spent:
                            new_existing.append({'_spent': True, 'caliber': caliber})
                            spent_placed += 1
                        else:
                            new_existing.append(None)
                    existing = new_existing

                subtype = str(wpn.get('magazinesubtype', '') or 'side-by-side').lower()
                is_over_under = 'over' in subtype or 'under' in subtype
                is_single = subtype == 'single' or cap == 1

                vlist = sorted(available_by_variant.keys())
                cpal = ['#c4a032', '#b87333', '#a0a0a0', '#d4af37', '#8b4513', '#cd7f32', '#e8c872', '#a08060']
                vcols = {v: cpal[i % len(cpal)] for i, v in enumerate(vlist)}

                vtips = {}
                try:
                    _ammo_tbl = self._get_ammo_table_data()
                    for _atbl in _ammo_tbl:
                        _ac = _atbl.get('caliber')
                        _match = False
                        if isinstance(_ac, list):
                            _match = caliber in _ac if caliber else False
                        else:
                            _match = (_ac == caliber) if caliber else False
                        if _match:
                            for _av in _atbl.get('variants', []):
                                _atn = _av.get('name')
                                _att = _av.get('tip')
                                if _atn and _att and isinstance(_att, str) and _att.startswith('#'):
                                    vtips[_atn] = _att
                            break
                except Exception:
                    logging.exception("Suppressed exception")

                def _tip_for(vn):
                    return vtips.get(vn, '#e0c060')

                def _tip_ol_for(vn):
                    tc = vtips.get(vn)
                    if not tc:
                        return '#aa8820'
                    try:
                        rv = int(tc[1:3], 16); gv = int(tc[3:5], 16); bv = int(tc[5:7], 16)
                        return f'#{max(0, rv - 40):02x}{max(0, gv - 40):02x}{max(0, bv - 40):02x}'
                    except Exception:
                        return '#aa8820'

                def _tip_for_round(r):
                    if isinstance(r, dict):
                        return _tip_for(r.get('variant') or r.get('name') or 'Unknown')
                    return '#e0c060'

                def _tip_ol_for_round(r):
                    if isinstance(r, dict):
                        return _tip_ol_for(r.get('variant') or r.get('name') or 'Unknown')
                    return '#aa8820'

                def _is_live(r):
                    return r is not None and isinstance(r, dict) and not r.get('_spent')

                def _is_spent(r):
                    return r is not None and isinstance(r, dict) and r.get('_spent')

                BARREL_R = 38
                BARREL_GAP = 20
                canvas_w = 420
                canvas_h = 480
                HINGE_Y = 200
                CHIP_AREA_H = 60

                ls = {'open': False, 'animating': False, 'added': 0, 'stoggle': 0,
                      'dragging': False, 'drag_vn': None, 'di': None,
                      '_drag_open_active': False, '_drag_open_start': 0,
                      '_drag_close_active': False, '_drag_close_start': 0,
                      'open_angle': 0.0}

                main_frame = customtkinter.CTkFrame(editor)
                main_frame.grid(row = 0, column = 0, sticky = 'nsew', padx = 8, pady = 8)

                ba_canvas = _tk_ba.Canvas(main_frame, width = canvas_w, height = canvas_h,
                    bg = '#1a1a1a', highlightthickness = 1, highlightbackground = '#555555')
                ba_canvas.pack(fill = 'both', expand = True)

                side = customtkinter.CTkFrame(editor, fg_color = 'transparent', width = 180)
                side.grid(row = 0, column = 1, sticky = 'ns', padx = 8, pady = 8)

                chip_hitboxes = {}

                def _barrel_positions():
                    cx = canvas_w // 2
                    if is_over_under:
                        positions = []
                        for i in range(cap):
                            by = HINGE_Y + 60 + i * (BARREL_R * 2 + BARREL_GAP)
                            positions.append((cx, by))
                        return positions
                    else:
                        positions = []
                        total_w = cap * (BARREL_R * 2) + (cap - 1) * BARREL_GAP
                        start_x = cx - total_w // 2 + BARREL_R
                        by = HINGE_Y + 80
                        for i in range(cap):
                            bx = start_x + i * (BARREL_R * 2 + BARREL_GAP)
                            positions.append((bx, by))
                        return positions

                def _barrel_positions_open():
                    cx = canvas_w // 2
                    angle_frac = ls['open_angle']
                    offset_y = int(angle_frac * 80)
                    if is_over_under:
                        positions = []
                        for i in range(cap):
                            by = HINGE_Y + 60 + i * (BARREL_R * 2 + BARREL_GAP) + offset_y
                            positions.append((cx, by))
                        return positions
                    else:
                        positions = []
                        total_w = cap * (BARREL_R * 2) + (cap - 1) * BARREL_GAP
                        start_x = cx - total_w // 2 + BARREL_R
                        by = HINGE_Y + 80 + offset_y
                        for i in range(cap):
                            bx = start_x + i * (BARREL_R * 2 + BARREL_GAP)
                            positions.append((bx, by))
                        return positions

                def _draw_chips():
                    ba_canvas.delete('chips')
                    chip_hitboxes.clear()
                    if not ls['open']:
                        return
                    chip_x = 15
                    chip_y = 10
                    for vn in vlist:
                        cnt = available_by_variant.get(vn, 0)
                        if is_infinite:
                            cnt_str = '\u221e'
                        else:
                            cnt_str = str(cnt)
                        is_avail = cnt > 0 or is_infinite
                        c = vcols.get(vn, '#c4a032')
                        fill = c if is_avail else '#333333'
                        ol = '#ffffff' if is_avail else '#555555'
                        disp = vn if len(vn) <= 12 else vn[:11] + '\u2026'
                        tw = len(disp) * 7 + 40
                        ba_canvas.create_rectangle(chip_x, chip_y, chip_x + tw, chip_y + 22,
                            fill = fill, outline = ol, width = 1, tags = 'chips')
                        ba_canvas.create_oval(chip_x + 3, chip_y + 3, chip_x + 19, chip_y + 19,
                            fill = _tip_for(vn), outline = _tip_ol_for(vn), tags = 'chips')
                        ba_canvas.create_text(chip_x + 22, chip_y + 11,
                            text = f'{disp} x{cnt_str}',
                            fill = '#1a1a1a' if is_avail else '#555555',
                            font = ('Consolas', 8, 'bold'), anchor = 'w', tags = 'chips')
                        if is_avail:
                            chip_hitboxes[vn] = (chip_x, chip_y, chip_x + tw, chip_y + 22)
                        chip_x += tw + 8
                        if chip_x > canvas_w - 40:
                            chip_x = 15
                            chip_y += 26

                def _draw_barrels():
                    ba_canvas.delete('barrels')
                    cx = canvas_w // 2

                    if not ls['open']:
                        positions = _barrel_positions()
                        ba_canvas.create_rectangle(cx - 30, HINGE_Y - 10, cx + 30, HINGE_Y + 10,
                            fill = '#555555', outline = '#777777', width = 2, tags = 'barrels')
                        for i, (bx, by) in enumerate(positions):
                            ba_canvas.create_line(bx, HINGE_Y, bx, by - BARREL_R,
                                fill = '#666666', width = 4, tags = 'barrels')
                            ba_canvas.create_oval(bx - BARREL_R, by - BARREL_R,
                                bx + BARREL_R, by + BARREL_R,
                                fill = '#3a3a3a', outline = '#666666', width = 3, tags = 'barrels')
                            r = existing[i] if i < len(existing) else None
                            if _is_live(r):
                                vn = r.get('variant') or r.get('name') or 'Unknown'
                                ba_canvas.create_oval(bx - BARREL_R + 6, by - BARREL_R + 6,
                                    bx + BARREL_R - 6, by + BARREL_R - 6,
                                    fill = _tip_for_round(r), outline = _tip_ol_for_round(r),
                                    width = 1, tags = 'barrels')
                            elif _is_spent(r):
                                ba_canvas.create_oval(bx - BARREL_R + 6, by - BARREL_R + 6,
                                    bx + BARREL_R - 6, by + BARREL_R - 6,
                                    fill = '#8B7355', outline = '#6B5335',
                                    width = 1, tags = 'barrels')
                                ba_canvas.create_oval(bx - 5, by - 5, bx + 5, by + 5,
                                    fill = '#5a4a3a', outline = '#4a3a2a', tags = 'barrels')
                            else:
                                ba_canvas.create_oval(bx - 10, by - 10, bx + 10, by + 10,
                                    fill = '#1a1a1a', outline = '#444444', width = 1, tags = 'barrels')
                        n_loaded = sum(1 for r in existing if _is_live(r))
                        ba_canvas.create_text(cx, HINGE_Y + 160,
                            text = f'{n_loaded}/{cap}',
                            fill = '#888888', font = ('Consolas', 14, 'bold'), tags = 'barrels')
                        ba_canvas.create_text(cx, HINGE_Y - 30,
                            text = '\u2193 DRAG DOWN TO OPEN \u2193',
                            fill = '#888888', font = ('Consolas', 10), tags = 'barrels')
                        return

                    positions = _barrel_positions_open()
                    ba_canvas.create_rectangle(cx - 30, HINGE_Y - 10, cx + 30, HINGE_Y + 10,
                        fill = '#555555', outline = '#777777', width = 2, tags = 'barrels')
                    for i, (bx, by) in enumerate(positions):
                        ba_canvas.create_line(bx, HINGE_Y, bx, by - BARREL_R,
                            fill = '#666666', width = 4, tags = 'barrels')
                        ba_canvas.create_oval(bx - BARREL_R, by - BARREL_R,
                            bx + BARREL_R, by + BARREL_R,
                            fill = '#2e2e2e', outline = '#777777', width = 3, tags = 'barrels')

                        r = existing[i] if i < len(existing) else None
                        if _is_spent(r):
                            ba_canvas.create_oval(bx - BARREL_R + 6, by - BARREL_R + 6,
                                bx + BARREL_R - 6, by + BARREL_R - 6,
                                fill = '#8B7355', outline = '#6B5335', width = 1, tags = 'barrels')
                            ba_canvas.create_oval(bx - 5, by - 5, bx + 5, by + 5,
                                fill = '#5a4a3a', outline = '#4a3a2a', tags = 'barrels')
                            ba_canvas.create_text(bx, by + BARREL_R + 12,
                                text = 'spent', fill = '#665544',
                                font = ('Consolas', 8), tags = 'barrels')
                        elif _is_live(r):
                            vn = r.get('variant') or r.get('name') or 'Unknown'
                            c = vcols.get(vn, '#c4a032')
                            ba_canvas.create_oval(bx - BARREL_R + 4, by - BARREL_R + 4,
                                bx + BARREL_R - 4, by + BARREL_R - 4,
                                fill = '#333333', outline = '#666666', width = 2, tags = 'barrels')
                            ba_canvas.create_oval(bx - BARREL_R + 8, by - BARREL_R + 8,
                                bx + BARREL_R - 8, by + BARREL_R - 8,
                                fill = _tip_for_round(r), outline = _tip_ol_for_round(r),
                                width = 1, tags = 'barrels')
                            ba_canvas.create_oval(bx - 4, by - 4, bx + 4, by + 4,
                                fill = c, outline = c, tags = 'barrels')
                            disp = vn if len(vn) <= 6 else vn[:5] + '\u2026'
                            ba_canvas.create_text(bx, by + BARREL_R + 12,
                                text = disp, fill = '#aaaaaa',
                                font = ('Consolas', 8), tags = 'barrels')
                        else:
                            ba_canvas.create_oval(bx - BARREL_R + 6, by - BARREL_R + 6,
                                bx + BARREL_R - 6, by + BARREL_R - 6,
                                fill = '#1a1a1a', outline = '#555555', width = 2, tags = 'barrels')
                            ba_canvas.create_text(bx, by,
                                text = str(i + 1), fill = '#444444',
                                font = ('Consolas', 12), tags = 'barrels')

                    if not ls['animating']:
                        ba_canvas.create_text(cx, HINGE_Y - 30,
                            text = '\u2191 DRAG UP TO CLOSE \u2191',
                            fill = '#666666', font = ('Consolas', 10), tags = 'barrels')

                def _draw_all():
                    _draw_chips()
                    _draw_barrels()

                def _play_ba_sound(action_name):
                    try:
                        spath = os.path.join('sounds', 'firearms', 'weaponsounds', 'break action', f'{action_name}.ogg')
                        if os.path.exists(spath):
                            snd = pygame.mixer.Sound(spath)
                            ch = pygame.mixer.find_channel()
                            if ch:
                                ch.play(snd)
                    except Exception:
                        logging.exception("Suppressed exception")

                def _play_insert():
                    try:
                        sn = f"bulletinsert{ls['stoggle']}"
                        ls['stoggle'] = 1 - ls['stoggle']
                        spath = os.path.join('sounds', 'firearms', 'universal', f'{sn}.ogg')
                        if os.path.exists(spath):
                            snd = pygame.mixer.Sound(spath)
                            ch = pygame.mixer.find_channel()
                            if ch:
                                ch.play(snd)
                    except Exception:
                        logging.exception("Suppressed exception")

                def _take_round(vname):
                    if is_infinite:
                        return {'name': f'{caliber} | {vname}', 'caliber': caliber, 'variant': vname}
                    for hi in range(len(save_data.get('hands', {}).get('items', [])) - 1, -1, -1):
                        itm = save_data['hands']['items'][hi]
                        try:
                            if not itm or not isinstance(itm, dict):
                                continue
                            rds = itm.get('rounds')
                            if isinstance(rds, list) and rds:
                                for ri, r in enumerate(rds):
                                    rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                    if rv == vname:
                                        return rds.pop(ri)
                            qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                            if qty > 0:
                                nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                if nm and str(nm) == vname:
                                    itm['quantity'] = qty - 1
                                    return {k: v for k, v in itm.items() if k != 'quantity'}
                            if itm.get('caliber') and (itm.get('variant') or itm.get('name')) and (itm.get('variant') == vname or itm.get('name') == vname):
                                try:
                                    save_data['hands']['items'].pop(hi)
                                except Exception:
                                    logging.exception("Suppressed exception")
                                return itm
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue
                    for _sn_eq, eq_item in list(save_data.get('equipment', {}).items()):
                        if not eq_item or not isinstance(eq_item, dict):
                            continue
                        for cidx in range(len(eq_item.get('items', [])) - 1, -1, -1):
                            try:
                                itm = eq_item['items'][cidx]
                                if not itm or not isinstance(itm, dict):
                                    continue
                                rds = itm.get('rounds')
                                if isinstance(rds, list) and rds:
                                    for ri, r in enumerate(rds):
                                        rv = (r.get('variant') if isinstance(r, dict) else (str(r) if r else None))
                                        if rv == vname:
                                            return rds.pop(ri)
                                qty = int(itm.get('quantity') or 0) if isinstance(itm.get('quantity'), (int, float)) else 0
                                if qty > 0:
                                    nm = itm.get('variant') or itm.get('name') or itm.get('caliber')
                                    if nm and str(nm) == vname:
                                        itm['quantity'] = qty - 1
                                        return {k: v for k, v in itm.items() if k != 'quantity'}
                            except Exception:
                                logging.exception("Suppressed exception")
                    return None

                def _find_empty_barrel():
                    for i in range(cap):
                        if existing[i] is None:
                            return i
                    return None

                def _hit_barrel(x, y):
                    if not ls['open']:
                        return None
                    positions = _barrel_positions_open()
                    for i, (bx, by) in enumerate(positions):
                        import math as _m_ba
                        dist = _m_ba.sqrt((x - bx) ** 2 + (y - by) ** 2)
                        if dist <= BARREL_R + 5:
                            return i
                    return None

                def _hit_chip(x, y):
                    for vn, (x1, y1, x2, y2) in chip_hitboxes.items():
                        if x1 <= x <= x2 and y1 <= y <= y2 and (available_by_variant.get(vn, 0) > 0 or is_infinite):
                            return vn
                    return None

                def _hit_barrel_area(x, y):
                    if ls['open']:
                        return False
                    positions = _barrel_positions()
                    for bx, by in positions:
                        import math as _m_ba2
                        dist = _m_ba2.sqrt((x - bx) ** 2 + (y - by) ** 2)
                        if dist <= BARREL_R + 30:
                            return True
                    return y > HINGE_Y - 20

                def _hit_open_area(x, y):
                    if not ls['open']:
                        return False
                    return y > HINGE_Y - 20

                def _do_insert(vname, barrel_idx):
                    r = _take_round(vname)
                    if r is None:
                        return
                    existing[barrel_idx] = r
                    ls['added'] += 1
                    if not is_infinite:
                        if vname in available_by_variant:
                            available_by_variant[vname] -= 1
                            if available_by_variant[vname] <= 0:
                                del available_by_variant[vname]
                    _play_ba_sound('insert')
                    _draw_all()
                    _update_side()

                def _animate_open():
                    ls['animating'] = True
                    _play_ba_sound('open')
                    target = 1.0
                    steps = 12

                    def _step(s):
                        if s >= steps:
                            ls['open_angle'] = target
                            ls['open'] = True
                            ls['animating'] = False
                            _draw_all()
                            return
                        frac = (s + 1) / steps
                        ease = 1 - (1 - frac) ** 2
                        ls['open_angle'] = target * ease
                        _draw_barrels()
                        editor.after(20, lambda: _step(s + 1))

                    ls['open'] = True
                    _step(0)

                def _animate_close(callback = None):
                    ls['animating'] = True
                    _play_ba_sound('close')
                    start_angle = ls['open_angle']
                    steps = 10

                    def _step(s):
                        if s >= steps:
                            ls['open_angle'] = 0.0
                            ls['open'] = False
                            ls['animating'] = False
                            _draw_all()
                            if callback:
                                editor.after(50, callback)
                            return
                        frac = (s + 1) / steps
                        ease = frac * frac
                        ls['open_angle'] = start_angle * (1 - ease)
                        _draw_barrels()
                        editor.after(20, lambda: _step(s + 1))

                    _step(0)

                def _eject_spent():
                    if ls['animating'] or not ls['open']:
                        return
                    spent_indices = [i for i in range(cap) if _is_spent(existing[i])]
                    if not spent_indices:
                        return
                    ls['animating'] = True
                    positions = _barrel_positions_open()
                    shell_anims = []
                    for idx in spent_indices:
                        bx, by = positions[idx]
                        oid = ba_canvas.create_oval(bx - BARREL_R + 8, by - BARREL_R + 8,
                            bx + BARREL_R - 8, by + BARREL_R - 8,
                            fill = '#8B7355', outline = '#6B5335', width = 1, tags = 'ejectanim')
                        shell_anims.append((oid, bx, by))
                        existing[idx] = None
                    wpn['_break_spent'] = 0
                    _draw_barrels()
                    drop_steps = 12

                    def _drop_step(s):
                        if s >= drop_steps:
                            ba_canvas.delete('ejectanim')
                            ls['animating'] = False
                            _draw_all()
                            _update_side()
                            return
                        frac = (s + 1) / drop_steps
                        for oid, sx, sy in shell_anims:
                            ny = sy + frac * 120
                            ba_canvas.coords(oid, sx - BARREL_R + 8, ny - BARREL_R + 8,
                                sx + BARREL_R - 8, ny + BARREL_R - 8)
                        editor.after(25, lambda: _drop_step(s + 1))

                    editor.after(60, lambda: _drop_step(0))

                def _on_press(event):
                    if ls['animating']:
                        return
                    if not ls['open']:
                        if _hit_barrel_area(event.x, event.y):
                            ls['_drag_open_active'] = True
                            ls['_drag_open_start'] = event.y
                        return
                    if _hit_open_area(event.x, event.y):
                        barrel_idx = _hit_barrel(event.x, event.y)
                        if barrel_idx is None:
                            ls['_drag_close_active'] = True
                            ls['_drag_close_start'] = event.y
                            return
                    vn = _hit_chip(event.x, event.y)
                    if not vn:
                        return
                    ls['dragging'] = True
                    ls['drag_vn'] = vn
                    ls['di'] = ba_canvas.create_oval(
                        event.x - BARREL_R + 8, event.y - BARREL_R + 8,
                        event.x + BARREL_R - 8, event.y + BARREL_R - 8,
                        fill = _tip_for(vn), outline = '#ffffff', width = 2, tags = 'drag')

                def _on_move(event):
                    if ls.get('_drag_open_active') and not ls['open']:
                        return
                    if ls.get('_drag_close_active'):
                        return
                    if ls.get('dragging') and ls['di']:
                        ba_canvas.coords(ls['di'],
                            event.x - BARREL_R + 8, event.y - BARREL_R + 8,
                            event.x + BARREL_R - 8, event.y + BARREL_R - 8)

                def _on_release(event):
                    if ls.get('_drag_open_active'):
                        ls['_drag_open_active'] = False
                        dy = event.y - ls.get('_drag_open_start', event.y)
                        if dy > 50:
                            _animate_open()
                        return
                    if ls.get('_drag_close_active'):
                        ls['_drag_close_active'] = False
                        dy = ls.get('_drag_close_start', event.y) - event.y
                        if dy > 50:
                            _do_close_and_finish()
                        return
                    if not ls.get('dragging'):
                        return
                    ls['dragging'] = False
                    ba_canvas.delete('drag')
                    ls['di'] = None
                    if ls['animating']:
                        return
                    vn = ls['drag_vn']
                    if not vn or (available_by_variant.get(vn, 0) <= 0 and not is_infinite):
                        return
                    barrel_idx = _hit_barrel(event.x, event.y)
                    if barrel_idx is not None and (existing[barrel_idx] is None):
                        _do_insert(vn, barrel_idx)
                    else:
                        empty = _find_empty_barrel()
                        if empty is not None:
                            positions = _barrel_positions_open()
                            import math as _m_ba3
                            close_enough = False
                            for bx, by in positions:
                                dist = _m_ba3.sqrt((event.x - bx) ** 2 + (event.y - by) ** 2)
                                if dist <= BARREL_R * 2 + 20:
                                    close_enough = True
                                    break
                            if close_enough:
                                _do_insert(vn, empty)

                ba_canvas.bind('<Button-1>', _on_press)
                ba_canvas.bind('<B1-Motion>', _on_move)
                ba_canvas.bind('<ButtonRelease-1>', _on_release)

                barrel_word = 'barrel' if cap == 1 else 'barrels'
                _cap_lbl = customtkinter.CTkLabel(side,
                    text = f'{sum(1 for r in existing if _is_live(r))}/{cap} {barrel_word} loaded',
                    font = customtkinter.CTkFont(size = 13, weight = 'bold'))
                _cap_lbl.pack(pady = (10, 6))

                subtype_label = 'Single Barrel' if is_single else ('Over/Under' if is_over_under else 'Side-by-Side')
                barrel_word = 'barrel' if cap == 1 else 'barrels'
                customtkinter.CTkLabel(side,
                    text = f'{subtype_label} Break Action\n\nDrag down to open.\nDrag round onto barrel.\nDrag up to close.' if is_single else f'{subtype_label} Break Action\n\nDrag down to open.\nDrag rounds onto barrels.\nDrag up to close.',
                    font = customtkinter.CTkFont(size = 10), text_color = '#888888',
                    wraplength = 170).pack(pady = 6)

                def _update_side():
                    _cap_lbl.configure(text = f'{sum(1 for r in existing if _is_live(r))}/{cap} {barrel_word} loaded')

                customtkinter.CTkButton(side, text = 'Eject Spent', command = _eject_spent,
                    width = 160, height = 30, font = customtkinter.CTkFont(size = 11),
                    fg_color = '#6a4a2a', hover_color = '#7a5a3a').pack(pady = 4)

                def _do_close_and_finish():
                    if ls['animating']:
                        return
                    final_rounds = [r for r in existing if _is_live(r)]
                    remaining_spent = sum(1 for r in existing if _is_spent(r))

                    def _finish():
                        wpn['rounds'] = final_rounds
                        wpn['chambered'] = None
                        wpn['_break_spent'] = remaining_spent

                        try:
                            sd_ref = save_data if isinstance(save_data, dict) else globals().get('save_data') or getattr(self, '_current_save_data', None)
                            if isinstance(sd_ref, dict):
                                ts = sd_ref.setdefault('tracked_stats', {})
                                if isinstance(ts, dict):
                                    ts['mags_reloaded_total'] = int(ts.get('mags_reloaded_total', 0)) + 1
                                    added = int(ls['added'])
                                    ts['bullets_loaded_total'] = int(ts.get('bullets_loaded_total', 0)) + added
                                    bh = ts.setdefault('bullets_loaded_history', [])
                                    try:
                                        bh.append({'weapon_id': str(wpn.get('id', 'unknown')), 'count': added, 'time': time.time()})
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception('Failed updating tracked_stats after break action reload')
                        try:
                            self._update_session_reload_stats(save_data, int(ls['added']))
                        except Exception:
                            logging.exception("Suppressed exception")

                        editor.destroy()
                        update_weapon_view()
                        if ls['added'] > 0:
                            self._popup_show_info('Break Action Reload', f'Loaded {ls["added"]} rounds ({len(final_rounds)}/{cap})')

                    _animate_close(callback = _finish)

                def _done():
                    final_rounds = [r for r in existing if _is_live(r)]
                    remaining_spent = sum(1 for r in existing if _is_spent(r))

                    def _finish():
                        wpn['rounds'] = final_rounds
                        wpn['chambered'] = None
                        wpn['_break_spent'] = remaining_spent

                        try:
                            sd_ref = save_data if isinstance(save_data, dict) else globals().get('save_data') or getattr(self, '_current_save_data', None)
                            if isinstance(sd_ref, dict):
                                ts = sd_ref.setdefault('tracked_stats', {})
                                if isinstance(ts, dict):
                                    ts['mags_reloaded_total'] = int(ts.get('mags_reloaded_total', 0)) + 1
                                    added = int(ls['added'])
                                    ts['bullets_loaded_total'] = int(ts.get('bullets_loaded_total', 0)) + added
                                    bh = ts.setdefault('bullets_loaded_history', [])
                                    try:
                                        bh.append({'weapon_id': str(wpn.get('id', 'unknown')), 'count': added, 'time': time.time()})
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception('Failed updating tracked_stats after break action reload')
                        try:
                            self._update_session_reload_stats(save_data, int(ls['added']))
                        except Exception:
                            logging.exception("Suppressed exception")

                        editor.destroy()
                        update_weapon_view()
                        if ls['added'] > 0:
                            self._popup_show_info('Break Action Reload', f'Loaded {ls["added"]} rounds ({len(final_rounds)}/{cap})')

                    if ls['open']:
                        _animate_close(callback = _finish)
                    else:
                        _finish()

                editor.protocol('WM_DELETE_WINDOW', _done)
                customtkinter.CTkButton(side, text = 'Done', command = _done,
                    width = 160, height = 35,
                    font = customtkinter.CTkFont(size = 12)).pack(pady = 10)

                _draw_all()

                editor.update_idletasks()
                ew = max(editor.winfo_reqwidth(), 620)
                eh = max(editor.winfo_reqheight(), 520)
                _sw_s = editor.winfo_screenwidth()
                _sh_s = editor.winfo_screenheight()
                x = (_sw_s // 2) - (ew // 2)
                y = (_sh_s // 2) - (eh // 2)
                editor.geometry(f'{ew}x{eh}+{x}+{y}')
                editor.grab_set()
                editor.lift()
                self._safe_focus(editor)
            except Exception:
                logging.exception('Failed to open break action editor')

        def _find_throwables_in_inventory():
            items =[]

            for itm in save_data.get('hands', {}).get('items', []):
                try:
                    if itm and isinstance(itm, dict)and str(itm.get('type', '')).lower()in('fragmentation', 'smoke', 'stun', '9-bang', '9bang', '9_bang'):
                        items.append(('hands', itm))
                except Exception:
                    logging.exception("Suppressed exception")

            for slot_name, eq_item in save_data.get('equipment', {}).items():
                try:
                    if not eq_item or not isinstance(eq_item, dict):
                        continue
                    if 'items'in eq_item and isinstance(eq_item['items'], list):
                        for itm in eq_item['items']:
                            try:
                                if itm and isinstance(itm, dict)and str(itm.get('type', '')).lower()in('fragmentation', 'smoke', 'stun', '9-bang', '9bang', '9_bang'):
                                    items.append(('equipment', itm))
                            except Exception:
                                logging.exception("Suppressed exception")
                    if 'subslots'in eq_item:
                        for sub in eq_item.get('subslots', []):
                            try:
                                curr = sub.get('current')if isinstance(sub, dict)else None
                                if curr and isinstance(curr, dict)and 'items'in curr and isinstance(curr['items'], list):
                                    for itm in curr['items']:
                                        try:
                                            if itm and isinstance(itm, dict)and str(itm.get('type', '')).lower()in('fragmentation', 'smoke', 'stun', '9-bang', '9bang', '9_bang'):
                                                items.append(('equipment', itm))
                                        except Exception:
                                            logging.exception("Suppressed exception")
                            except Exception:
                                logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")
            return items

        def _find_consumables_in_inventory():
            # All carried containers (hands + every equipment container, nested),
            # excluding storage.
            try:
                return [
                    (loc, itm)
                    for loc, itm in self._iter_carried_items(save_data, include_storage = False)
                    if isinstance(itm, dict) and itm.get('consumable')
                ]
            except Exception:
                logging.exception("Failed to enumerate consumables")
                return []

        def _has_ear_protection():
            try:
                for slot, eq in save_data.get('equipment', {}).items():
                    if not eq or not isinstance(eq, dict):
                        continue

                    if eq.get('ear_protection'):
                        return True

                    for itm in eq.get('items', [])or[]:
                        try:
                            if itm and isinstance(itm, dict)and itm.get('ear_protection'):
                                return True
                        except Exception:
                            logging.exception("Suppressed exception")
                    for sub in eq.get('subslots', [])or[]:
                        try:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                if curr.get('ear_protection'):
                                    return True
                                for itm in curr.get('items', [])or[]:
                                    try:
                                        if itm and isinstance(itm, dict)and itm.get('ear_protection'):
                                            return True
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                return False
            except Exception:
                return False

        def _has_flash_goggles():
            try:
                for slot, eq in save_data.get('equipment', {}).items():
                    if not eq or not isinstance(eq, dict):
                        continue
                    if eq.get('flashbang_goggle'):
                        return True
                    for itm in eq.get('items', [])or[]:
                        try:
                            if itm and isinstance(itm, dict)and itm.get('flashbang_goggle'):
                                return True
                        except Exception:
                            logging.exception("Suppressed exception")
                    for sub in eq.get('subslots', [])or[]:
                        try:
                            curr = sub.get('current')
                            if curr and isinstance(curr, dict):
                                if curr.get('flashbang_goggle'):
                                    return True
                                for itm in curr.get('items', [])or[]:
                                    try:
                                        if itm and isinstance(itm, dict)and itm.get('flashbang_goggle'):
                                            return True
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                return False
            except Exception:
                return False

        def _handle_flashbang_effects(bang_count = 1):

            try:
                has_ears = _has_ear_protection()
                has_gog = _has_flash_goggles()

                if not has_ears:
                    try:
                        self._flashbang_mute = True
                        self._flashbang_volume = 0.0
                    except Exception:
                        logging.exception("Suppressed exception")

                    try:
                        def _play_ring():
                            try:
                                logging.debug("Flashbang: spawning ring playback thread")
                                self._safe_sound_play('', 'sounds/misc/throwable/ring.ogg')
                                logging.debug("Flashbang: ring playback attempted")
                            except Exception:
                                logging.exception('Flashbang ring playback failed')
                        threading.Thread(target = _play_ring, daemon = True).start()
                    except Exception:
                        logging.exception('Failed to start ring playback thread')

                    try:

                        try:
                            if hasattr(self, '_flashbang_fade_cancel')and self._flashbang_fade_cancel is not None:
                                try:
                                    self._flashbang_fade_cancel.set()
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")

                        fade_cancel = threading.Event()
                        self._flashbang_fade_cancel = fade_cancel

                        def _fade_in_after_delay(cancel_evt = fade_cancel):
                            try:
                                wait = random.uniform(7.0, 8.0)

                                waited = 0.0
                                step_wait = 0.1
                                while waited <wait:
                                    if cancel_evt.is_set():
                                        return
                                    time.sleep(step_wait)
                                    waited +=step_wait

                                steps = 20
                                dur = 3.0
                                step_sleep = dur /steps
                                for i in range(1, steps +1):
                                    if cancel_evt.is_set():
                                        return
                                    try:
                                        self._flashbang_volume = float(i)/float(steps)
                                    except Exception:
                                        self._flashbang_volume = 1.0
                                    time.sleep(step_sleep)

                                try:
                                    self._flashbang_mute = False
                                    self._flashbang_volume = 1.0

                                    try:
                                        cache = getattr(self, '_sound_cache', {})or {}
                                        for spath, ssound in cache.items():
                                            try:
                                                ssound.set_volume(1.0)
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                            except Exception:
                                try:
                                    self._flashbang_mute = False
                                    self._flashbang_volume = 1.0
                                except Exception:
                                    logging.exception("Suppressed exception")

                        t = threading.Thread(target = _fade_in_after_delay, daemon = True)
                        t.start()
                        self._flashbang_fade_thread = t
                    except Exception:
                        logging.exception("Suppressed exception")
                else:

                    try:
                        self._bang_muffle = True

                        self._bang_muffle_volume = getattr(self, '_bang_muffle_volume', 0.45)

                        try:
                            prev = getattr(self, '_bang_muffle_timer', None)
                            if prev:
                                try:
                                    prev.cancel()
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")

                        try:
                            mt = threading.Timer(5.0, lambda:setattr(self, '_bang_muffle', False))
                            mt.daemon = True
                            mt.start()
                            self._bang_muffle_timer = mt
                        except Exception:
                            logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                if not has_gog:
                    def _create_overlay():
                        try:
                            ov = customtkinter.CTkToplevel(self.root)
                            ov.overrideredirect(True)
                            vx, vy, vw, vh = self._get_virtual_screen_rect()
                            ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
                            try:
                                ov.attributes('-topmost', True)
                            except Exception:
                                logging.exception("Suppressed exception")
                            try:
                                ov.attributes('-alpha', 1.0)
                            except Exception:
                                logging.exception("Suppressed exception")
                            try:
                                ov.configure(fg_color = 'white')
                            except Exception:
                                try:
                                    ov.configure(bg = 'white')
                                except Exception:
                                    logging.exception("Suppressed exception")
                            return ov
                        except Exception:
                            return None

                    try:
                        def _make_and_fade():
                            try:

                                existing = getattr(self, '_flashbang_overlay', None)
                                existing_after = getattr(self, '_flashbang_overlay_after_id', None)
                                overlay = existing
                                if overlay is None or not getattr(overlay, 'winfo_exists', lambda:False)():
                                    overlay = _create_overlay()
                                    try:
                                        self._flashbang_overlay = overlay
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                else:
                                    try:

                                        if existing_after:
                                            try:
                                                overlay.after_cancel(existing_after)
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                    try:
                                        overlay.attributes('-alpha', 1.0)
                                    except Exception:
                                        logging.exception("Suppressed exception")

                                delay = int(random.uniform(7000, 8000))
                                def _fade_step(count = 0, steps = None):
                                    try:
                                        if not getattr(overlay, 'winfo_exists', lambda:False)():
                                            try:
                                                if getattr(self, '_flashbang_overlay', None)is overlay:
                                                    self._flashbang_overlay = None
                                                    self._flashbang_overlay_after_id = None
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            return

                                        dur = 3.0

                                        target_fps = 165

                                        if not steps:
                                            try:
                                                steps = max(1, int(dur *target_fps))
                                            except Exception:
                                                steps = 60

                                        try:
                                            interval_ms = max(1, int((dur *1000.0)/float(steps)))
                                        except Exception:
                                            interval_ms = max(1, int((dur *1000.0)/60))

                                        t = float(count)/float(steps)if steps else 1.0

                                        smooth = t *t *(3.0 -2.0 *t)
                                        alpha = 1.0 -smooth
                                        alpha = max(0.0, min(1.0, alpha))
                                        try:
                                            overlay.attributes('-alpha', alpha)
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                        if count <steps:
                                            aid = overlay.after(int(interval_ms), lambda:_fade_step(count +1, steps))
                                            try:
                                                self._flashbang_overlay_after_id = aid
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                        else:
                                            try:
                                                overlay.destroy()
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                            try:
                                                if getattr(self, '_flashbang_overlay', None)is overlay:
                                                    self._flashbang_overlay = None
                                                    self._flashbang_overlay_after_id = None
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    except Exception:
                                        try:
                                            if overlay:
                                                overlay.destroy()
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                try:
                                    aid = overlay.after(delay, lambda:_fade_step(0))
                                    try:
                                        self._flashbang_overlay_after_id = aid
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                except Exception:
                                    try:

                                        _fade_step(0)
                                    except Exception:
                                        logging.exception("Suppressed exception")
                            except Exception:
                                logging.exception("Suppressed exception")

                        self.root.after(0, _make_and_fade)
                    except Exception:
                        logging.exception("Suppressed exception")

                return True
            except Exception:
                return False

        def _handle_fragmentation_flash_effects():

            try:
                has_gog = _has_flash_goggles()
                if has_gog:
                    return True

                def _create_quick_flash():
                    try:
                        ov = customtkinter.CTkToplevel(self.root)
                        ov.overrideredirect(True)
                        vx, vy, vw, vh = self._get_virtual_screen_rect()
                        ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
                        try:
                            ov.attributes('-topmost', True)
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            ov.attributes('-alpha', 1.0)
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            ov.configure(fg_color = 'white')
                        except Exception:
                            try:
                                ov.configure(bg = 'white')
                            except Exception:
                                logging.exception("Suppressed exception")

                        def _quick_fade(step = 0, steps = None):
                            try:
                                if not getattr(ov, 'winfo_exists', lambda:False)():
                                    return

                                dur = random.uniform(0.2, 0.35)
                                target_fps = 165
                                if not steps:
                                    try:
                                        steps = max(1, int(dur *target_fps))
                                    except Exception:
                                        steps = 60

                                try:
                                    interval_ms = max(1, int((dur *1000.0)/float(steps)))
                                except Exception:
                                    interval_ms = max(1, int((dur *1000.0)/60))

                                t = float(step)/float(steps)if steps else 1.0
                                smooth = t *t *(3.0 -2.0 *t)
                                alpha = 1.0 -smooth
                                alpha = max(0.0, min(1.0, alpha))
                                try:
                                    ov.attributes('-alpha', alpha)
                                except Exception:
                                    logging.exception("Suppressed exception")

                                if step <steps:
                                    ov.after(int(interval_ms), lambda:_quick_fade(step +1, steps))
                                else:
                                    try:
                                        ov.destroy()
                                    except Exception:
                                        logging.exception("Suppressed exception")
                            except Exception:
                                try:
                                    ov.destroy()
                                except Exception:
                                    logging.exception("Suppressed exception")

                        ov.after(int(random.uniform(10, 30)), lambda:_quick_fade(1, None))
                        return ov
                    except Exception:
                        return None

                try:

                    try:
                        if _has_ear_protection():
                            try:
                                self._bang_muffle = True
                                self._bang_muffle_volume = getattr(self, '_bang_muffle_volume', 0.45)
                                prev = getattr(self, '_bang_muffle_timer', None)
                                if prev:
                                    try:
                                        prev.cancel()
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                mt = threading.Timer(3.0, lambda:setattr(self, '_bang_muffle', False))
                                mt.daemon = True
                                mt.start()
                                self._bang_muffle_timer = mt
                            except Exception:
                                logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                    self.root.after(0, _create_quick_flash)
                except Exception:
                    logging.exception("Suppressed exception")
                return True
            except Exception:
                return False

        def _handle_goggle_dark_flash_effects():

            try:

                if not _has_flash_goggles():
                    return False

                def _create_quick_dark():
                    try:
                        ov = customtkinter.CTkToplevel(self.root)
                        ov.overrideredirect(True)
                        vx, vy, vw, vh = self._get_virtual_screen_rect()
                        ov.geometry(f"{vw}x{vh}+{vx}+{vy}")
                        try:
                            ov.attributes('-topmost', True)
                        except Exception:
                            logging.exception("Suppressed exception")

                        try:
                            ov.attributes('-alpha', 0.8)
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            ov.configure(fg_color = 'black')
                        except Exception:
                            try:
                                ov.configure(bg = 'black')
                            except Exception:
                                logging.exception("Suppressed exception")

                        def _quick_fade(step = 0, steps = None):
                            try:
                                if not getattr(ov, 'winfo_exists', lambda:False)():
                                    return

                                dur = random.uniform(0.2, 0.4)
                                target_fps = 165
                                if not steps:
                                    try:
                                        steps = max(1, int(dur *target_fps))
                                    except Exception:
                                        steps = 60

                                try:
                                    interval_ms = max(1, int((dur *1000.0)/float(steps)))
                                except Exception:
                                    interval_ms = max(1, int((dur *1000.0)/60))

                                t = float(step)/float(steps)if steps else 1.0
                                smooth = t *t *(3.0 -2.0 *t)
                                alpha = 0.8 *(1.0 -smooth)
                                alpha = max(0.0, min(1.0, alpha))
                                try:
                                    ov.attributes('-alpha', alpha)
                                except Exception:
                                    logging.exception("Suppressed exception")

                                if step <steps:
                                    ov.after(int(interval_ms), lambda:_quick_fade(step +1, steps))
                                else:
                                    try:
                                        ov.destroy()
                                    except Exception:
                                        logging.exception("Suppressed exception")
                            except Exception:
                                try:
                                    ov.destroy()
                                except Exception:
                                    logging.exception("Suppressed exception")

                        ov.after(int(random.uniform(10, 30)), lambda:_quick_fade(1, None))
                        return ov
                    except Exception:
                        return None

                try:
                    self.root.after(0, _create_quick_dark)
                except Exception:
                    logging.exception("Suppressed exception")
                return True
            except Exception:
                return False

        def _do_throw_sequence(location, throwable_item):
            try:

                try:

                    def _consume_throwable_from_list(lst, target):
                        try:
                            for i, it in enumerate(lst):
                                if it is target:
                                    if isinstance(it, dict):
                                        qty = it.get('quantity')
                                        if isinstance(qty, (int, float))and qty >1:
                                            try:
                                                it['quantity']= int(qty)-1
                                                return True
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                        else:
                                            try:
                                                lst.pop(i)
                                                return True
                                            except Exception:
                                                logging.exception("Suppressed exception")
                                    return False
                        except Exception:
                            logging.exception("Suppressed exception")
                        return False

                    if location =='hands':
                        hands_list = save_data.get('hands', {}).get('items', [])
                        _consume_throwable_from_list(hands_list, throwable_item)
                    elif location =='equipment':
                        for slot_name, eq_item in save_data.get('equipment', {}).items():
                            if not eq_item or not isinstance(eq_item, dict):
                                continue
                            if 'items'in eq_item and isinstance(eq_item['items'], list):
                                if _consume_throwable_from_list(eq_item['items'], throwable_item):
                                    break
                            if 'subslots'in eq_item:
                                for sub in eq_item.get('subslots', []):
                                    try:
                                        curr = sub.get('current')
                                        if curr and isinstance(curr, dict)and 'items'in curr and isinstance(curr['items'], list):
                                            if _consume_throwable_from_list(curr['items'], throwable_item):
                                                break
                                    except Exception:
                                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    self._save_file(save_data)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    self._safe_sound_play('', 'sounds/misc/throwable/pin.ogg')
                except Exception:
                    logging.exception("Suppressed exception")
                time.sleep(random.uniform(0.2, 0.5))
                try:
                    self._safe_sound_play('', 'sounds/misc/throwable/throw.ogg')
                except Exception:
                    logging.exception("Suppressed exception")
                time.sleep(random.uniform(0.2, 0.3))
                try:
                    self._safe_sound_play('', 'sounds/misc/throwable/spoon.ogg')
                except Exception:
                    logging.exception("Suppressed exception")

                fuse = float(throwable_item.get('fuse_time')or throwable_item.get('fuse', 3))
                start_t = time.time()
                end_t = start_t +fuse

                time.sleep(random.uniform(0.8, 1.3))
                try:
                    idx = random.randint(0, 3)
                    self._safe_sound_play('', f'sounds/misc/throwable/bounce{idx}.ogg')
                except Exception:
                    logging.exception("Suppressed exception")

                extra = random.randint(0, 3)
                for bi in range(extra):

                    if time.time()>=end_t and str(throwable_item.get('type', '')).lower()in('fragmentation', 'stun', '9-bang', '9bang', '9_bang'):
                        break
                    if bi ==0:
                        time.sleep(random.uniform(0.2, 0.3))
                    elif bi ==1:
                        time.sleep(random.uniform(0.2, 0.3))
                    else:
                        time.sleep(random.uniform(0.1, 0.2))
                    try:
                        idx = random.randint(0, 3)
                        self._safe_sound_play('', f'sounds/misc/throwable/bounce{idx}.ogg')
                    except Exception:
                        logging.exception("Suppressed exception")

                typ = str(throwable_item.get('type', '')).lower()

                remaining = end_t -time.time()
                if remaining >0:
                    time.sleep(remaining)

                if typ =='fragmentation':
                    try:

                        try:
                            _handle_fragmentation_flash_effects()
                        except Exception:
                            logging.exception("Suppressed exception")

                        try:
                            if _has_flash_goggles():
                                try:
                                    _handle_goggle_dark_flash_effects()
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                        self._safe_sound_play('', 'sounds/misc/throwable/explosion.ogg')
                    except Exception:
                        logging.exception("Suppressed exception")
                elif typ =='smoke':
                    try:
                        self._safe_sound_play('', 'sounds/misc/throwable/smoke.ogg')
                    except Exception:
                        logging.exception("Suppressed exception")
                elif typ in('stun', 'flashbang', 'flash'):

                    try:
                        _handle_flashbang_effects(bang_count = 1)
                        self._safe_sound_play('', 'sounds/misc/throwable/flashbang.ogg')
                        try:

                            if _has_flash_goggles():
                                try:
                                    _handle_goggle_dark_flash_effects()
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                elif typ in('9-bang', '9bang', '9_bang'):
                    try:
                        _handle_flashbang_effects(bang_count = 9)
                        for i in range(9):
                            try:
                                self._safe_sound_play('', 'sounds/misc/throwable/flashbang.ogg')

                                try:
                                    if _has_flash_goggles():
                                        try:
                                            _handle_goggle_dark_flash_effects()
                                        except Exception:
                                            logging.exception("Suppressed exception")
                                except Exception:
                                    logging.exception("Suppressed exception")
                            except Exception:
                                logging.exception("Suppressed exception")
                            if i <8:
                                time.sleep(random.uniform(0.3, 0.5))
                    except Exception:
                        logging.exception("Suppressed exception")

                try:
                    update_weapon_view()
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception('Throwable sequence failed')

        def throw_throwable():
            all_throw = _find_throwables_in_inventory()
            if not all_throw:
                self._popup_show_info('Throw', 'No throwables in inventory')
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title('Select Throwable')
            popup.transient(self.root)
            self._center_popup_on_window(popup, 420, 320)

            lab = customtkinter.CTkLabel(popup, text = 'Select a throwable to throw:', font = customtkinter.CTkFont(size = 12))
            lab.pack(pady = 8)

            sel_var = customtkinter.StringVar(value = '0')
            frame = customtkinter.CTkScrollableFrame(popup, fg_color = 'transparent')
            frame.pack(fill = 'both', expand = True, padx = 10, pady = 10)
            for idx, (loc, itm)in enumerate(all_throw):
                name = itm.get('name')or itm.get('type')or f'Throwable {idx}'
                qty = int(itm.get('quantity')or 1)if isinstance(itm.get('quantity'), (int, float, str))else 1
                qty_text = f" x{qty}"if qty >1 else ""
                desc = f"{name}{qty_text} - {loc} - fuse {itm.get('fuse_time')or itm.get('fuse', '?')}s"
                rb = customtkinter.CTkRadioButton(frame, text = desc, variable = sel_var, value = str(idx))
                rb.pack(anchor = 'w', pady = 2)

            def do_throw():
                try:
                    idx = int(sel_var.get())
                    loc, itm = all_throw[idx]
                except Exception:
                    popup.destroy()
                    return
                popup.destroy()

                try:
                    threading.Thread(target = _do_throw_sequence, args =(loc, itm), daemon = True).start()
                except Exception:
                    _do_throw_sequence(loc, itm)

            bframe = customtkinter.CTkFrame(popup, fg_color = 'transparent')
            bframe.pack(fill = 'x', padx = 10, pady = 6)
            customtkinter.CTkButton(bframe, text = 'Throw', command = do_throw, width = 120).pack(side = 'left', padx = 6)
            customtkinter.CTkButton(bframe, text = 'Cancel', command = popup.destroy, width = 120).pack(side = 'left', padx = 6)
            try:
                popup.grab_set()
                popup.lift()
                self._safe_focus(popup)
            except Exception:
                logging.exception("Suppressed exception")

        def use_consumable():

            all_consumables = _find_consumables_in_inventory()
            if not all_consumables:
                self._popup_show_info('Use Consumable', 'No consumables in inventory(hands/equipment)')
                return

            popup = customtkinter.CTkToplevel(self.root)
            popup.title('Select Consumable')
            popup.transient(self.root)
            self._center_popup_on_window(popup, 500, 400)

            lab = customtkinter.CTkLabel(popup, text = 'Select a consumable to use:', font = customtkinter.CTkFont(size = 12))
            lab.pack(pady = 8)

            sel_var = customtkinter.StringVar(value = '0')
            frame = customtkinter.CTkScrollableFrame(popup, fg_color = 'transparent')
            frame.pack(fill = 'both', expand = True, padx = 10, pady = 10)

            for idx, (loc, itm)in enumerate(all_consumables):
                name = itm.get('name')or f'Consumable {idx}'
                uses = itm.get('uses_left')
                loc_display = loc.replace('equipment.', '').replace('.subslots.', ' > ').replace('.current', '')
                if uses:
                    uses_text = f"{uses} use{'s'if uses !=1 else ''}"
                elif itm.get('used_up'):
                    uses_text = "1 use"
                else:
                    uses_text = "∞ uses"
                desc = f"{name}({uses_text}) - {loc_display}"
                rb = customtkinter.CTkRadioButton(frame, text = desc, variable = sel_var, value = str(idx))
                rb.pack(anchor = 'w', pady = 2)

            def do_consume():
                try:
                    idx = int(sel_var.get())
                    loc, itm = all_consumables[idx]
                except Exception:
                    popup.destroy()
                    return
                popup.destroy()

                # itm is a live reference into save_data; consume it directly.
                if not isinstance(itm, dict):
                    self._popup_show_info('Error', 'Could not find item in inventory', sound = 'error')
                    return

                def on_consume_complete():
                    try:
                        update_weapon_view()
                    except Exception:
                        logging.exception("Suppressed exception")

                self._consume_item(itm, loc, save_data, on_complete = on_consume_complete)

            bframe = customtkinter.CTkFrame(popup, fg_color = 'transparent')
            bframe.pack(fill = 'x', padx = 10, pady = 6)
            customtkinter.CTkButton(bframe, text = 'Use', command = do_consume, width = 120).pack(side = 'left', padx = 6)
            customtkinter.CTkButton(bframe, text = 'Cancel', command = popup.destroy, width = 120).pack(side = 'left', padx = 6)

            try:
                popup.grab_set()
                popup.lift()
                self._safe_focus(popup)
            except Exception:
                logging.exception("Suppressed exception")

        def _view_parts():
            import copy as _copy_parts
            w = current_weapon_state.get('weapon') if isinstance(current_weapon_state, dict) else None
            if not w:
                w = current_weapon
            parts = w.get('parts') if isinstance(w, dict) else None
            if not parts or not isinstance(parts, list):
                self._popup_show_info('Parts', 'This weapon has no parts.')
                return

            id_to_item_parts = {}
            try:
                td_tables = table_data.get('tables', {}) if isinstance(table_data, dict) else {}
                for _sub_items in td_tables.values():
                    if not isinstance(_sub_items, list):
                        continue
                    for _it in _sub_items:
                        if isinstance(_it, dict) and 'id' in _it:
                            id_to_item_parts[_it['id']] = _it
            except Exception:
                logging.exception("Suppressed exception")

            def _resolve_part_current(p):
                cur = p.get('current')
                if cur is None:
                    return None
                if isinstance(cur, dict) and 'name' in cur:
                    return cur
                target_id = None
                overrides = {}
                if isinstance(cur, int):
                    target_id = cur
                elif isinstance(cur, dict) and 'id' in cur:
                    target_id = cur.get('id')
                    for k, v in cur.items():
                        if k != 'id':
                            overrides[k] = v
                if target_id is None:
                    return cur if isinstance(cur, dict) else None
                target = id_to_item_parts.get(target_id)
                if not target:
                    return cur if isinstance(cur, dict) else None
                resolved = _copy_parts.deepcopy(target)
                for k, v in overrides.items():
                    resolved[k] = v
                p['current'] = resolved
                return resolved

            is_devmode = global_variables.get('devmode', {}).get('value', False)

            def _get_durability_text(p, resolved):
                dur = None
                if isinstance(p, dict):
                    dur = p.get('current_durability')
                if dur is None and isinstance(resolved, dict):
                    dur = resolved.get('current_durability')
                if dur is not None and dur != 'null' and str(dur).strip().lower() != 'set_by_looting':
                    try:
                        dur_val = float(dur)
                        pct = max(0.0, min(100.0, (dur_val / PART_DURABILITY_MAX) * 100))
                        if dur_val <= 0:
                            if is_devmode:
                                return f'Worn Out ({pct:.2f}%)', '#ff4444'
                            return 'Worn Out', '#ff4444'
                        elif pct < 25:
                            if is_devmode:
                                return f'Poor ({pct:.2f}%)', '#ff6644'
                            return 'Poor', '#ff6644'
                        elif pct < 50:
                            if is_devmode:
                                return f'Fair ({pct:.2f}%)', '#ffaa44'
                            return 'Fair', '#ffaa44'
                        elif pct < 75:
                            if is_devmode:
                                return f'Good ({pct:.2f}%)', '#aacc44'
                            return 'Good', '#aacc44'
                        else:
                            if is_devmode:
                                return f'Excellent ({pct:.2f}%)', '#44cc44'
                            return 'Excellent', '#44cc44'
                    except (ValueError, TypeError):
                        return 'Unknown', '#888888'
                dur_raw = p.get('durability') if isinstance(p, dict) else None
                if dur_raw == 'set_by_looting':
                    return 'Set by looting', '#888888'
                return 'N/A', '#888888'

            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Weapon Parts")
            popup.transient(self.root)
            self._center_popup_on_window(popup, 440, 400)

            scroll_frame = customtkinter.CTkScrollableFrame(popup, fg_color = "transparent")
            scroll_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

            part_rows = []

            def _candidates_for_part_slot(slot_req, part_type, weapon_platform):
                matches = []
                for itm in save_data.get("hands", {}).get("items", []):
                    if itm and isinstance(itm, dict):
                        if itm.get('type') == part_type or itm.get('slot') == slot_req:
                            itp = itm.get('platform', '')
                            if not itp or not weapon_platform or str(itp).lower() == str(weapon_platform).lower():
                                matches.append(itm)
                for slot_name_eq, eq_item in save_data.get("equipment", {}).items():
                    if eq_item and isinstance(eq_item, dict) and isinstance(eq_item.get("items"), list):
                        for itm in eq_item["items"]:
                            if itm and isinstance(itm, dict):
                                if itm.get('type') == part_type or itm.get('slot') == slot_req:
                                    itp = itm.get('platform', '')
                                    if not itp or not weapon_platform or str(itp).lower() == str(weapon_platform).lower():
                                        matches.append(itm)
                return matches

            weapon_platform = w.get('platform', '') if isinstance(w, dict) else ''

            for p in parts:
                if not isinstance(p, dict):
                    continue
                resolved = _resolve_part_current(p)
                pname = p.get('name', p.get('type', 'Unknown'))
                ptype = p.get('type', '')
                slot = p.get('slot', '')

                frame = customtkinter.CTkFrame(scroll_frame)
                frame.pack(fill = "x", padx = 6, pady = 6)

                slot_label = ptype.replace('_', ' ').title() if ptype else pname
                customtkinter.CTkLabel(frame, text = slot_label, font = customtkinter.CTkFont(size = 12, weight = "bold")).pack(anchor = "w", padx = 8, pady = (4, 0))

                if resolved and isinstance(resolved, dict):
                    cur_name = resolved.get('name', f'ID {resolved.get("id", "?")}')
                elif resolved is not None:
                    cur_name = str(resolved)
                else:
                    cur_name = 'Empty'

                name_label = customtkinter.CTkLabel(frame, text = cur_name, font = customtkinter.CTkFont(size = 11))
                name_label.pack(anchor = "w", padx = 16)

                dur_text, dur_color = _get_durability_text(p, resolved)
                dur_label = customtkinter.CTkLabel(frame, text = f'Durability: {dur_text}', font = customtkinter.CTkFont(size = 10), text_color = dur_color)
                dur_label.pack(anchor = "w", padx = 16, pady = (0, 2))

                btn_frame = customtkinter.CTkFrame(frame, fg_color = "transparent")
                btn_frame.pack(anchor = "w", padx = 16, pady = (0, 4))

                opts = [(None, "None")]
                for itm in _candidates_for_part_slot(slot, ptype, weapon_platform):
                    label = itm.get("name", "Part")
                    itm_dur_text, _ = _get_durability_text(itm, itm)
                    if itm_dur_text and itm_dur_text not in ('N/A', 'Set by looting'):
                        label = f"{label} [{itm_dur_text}]"
                    opts.append((itm, label))

                current_label = cur_name if resolved else "None"

                if resolved and isinstance(resolved, dict):
                    found_in_opts = False
                    for itm, lbl in opts:
                        if itm is resolved or (isinstance(itm, dict) and itm.get('id') == resolved.get('id')):
                            found_in_opts = True
                            break
                    if not found_in_opts:
                        opts.append((resolved, cur_name)) # type: ignore

                current_choice = customtkinter.StringVar(value = current_label)
                if len(opts) > 1:
                    option = customtkinter.CTkOptionMenu(btn_frame, values = [o[1] for o in opts], variable = current_choice, width = 220)
                    option.pack(side = "left", padx = (0, 4))

                part_rows.append((p, opts, current_choice, resolved))

            def _apply_part_changes():
                for part_ref, opts, var, old_resolved in part_rows:
                    chosen_label = var.get()
                    chosen_item = None
                    for itm, lbl in opts:
                        if lbl == chosen_label:
                            chosen_item = itm
                            break

                    old_current = part_ref.get('current')
                    if old_current and isinstance(old_current, dict) and old_current.get('name'):
                        if chosen_item is not old_current and not (isinstance(chosen_item, dict) and chosen_item.get('id') == old_current.get('id')):
                            save_data.setdefault('hands', {}).setdefault('items', []).append(_copy_parts.deepcopy(old_current))

                    if chosen_item is None:
                        part_ref['current'] = None
                        part_ref.pop('current_durability', None)
                    else:
                        if chosen_item is not old_current:
                            hands_items = save_data.get("hands", {}).get("items", [])
                            try:
                                if chosen_item in hands_items:
                                    hands_items.remove(chosen_item)
                            except Exception:
                                logging.exception("Suppressed exception")
                            try:
                                for slot_name_eq, eq_item in save_data.get("equipment", {}).items():
                                    if eq_item and isinstance(eq_item, dict) and isinstance(eq_item.get("items"), list):
                                        try:
                                            while chosen_item in eq_item["items"]:
                                                eq_item["items"].remove(chosen_item)
                                        except Exception:
                                            logging.exception("Suppressed exception")
                            except Exception:
                                logging.exception("Suppressed exception")
                        new_installed = _copy_parts.deepcopy(chosen_item) if isinstance(chosen_item, dict) else chosen_item
                        part_ref['current'] = new_installed

                try:
                    self._save_file(save_data)
                except Exception:
                    logging.exception("Failed to save after part changes")

                popup.destroy()
                update_weapon_view()

            apply_btn = customtkinter.CTkButton(popup, text = "Apply", command = _apply_part_changes, width = 120)
            apply_btn.pack(pady = 10)

            try:
                popup.update_idletasks()
                req_w = popup.winfo_reqwidth()
                req_h = popup.winfo_reqheight()
                screen_w = popup.winfo_screenwidth()
                screen_h = popup.winfo_screenheight()
                max_w = max(200, screen_w - 100)
                max_h = max(150, screen_h - 100)
                final_w = min(req_w, max_w)
                final_h = min(req_h, max_h)
                self._center_popup_on_window(popup, final_w, final_h)
            except Exception:
                try:
                    self._center_popup_on_window(popup, 440, 400)
                except Exception:
                    logging.exception("Suppressed exception")

        def _show_more_actions():
            try:
                popup = customtkinter.CTkToplevel(self.root)
                popup.title('More Actions')
                popup.geometry('520x420')
                popup.transient(self.root)

                frame = customtkinter.CTkScrollableFrame(popup, fg_color = 'transparent')
                frame.pack(fill = 'both', expand = True, padx = 10, pady = 10)

                def _add(name, cmd, width = 200, height = 44, fg = None):
                    try:

                        def _wrap():
                            try:
                                cmd()
                            except Exception:
                                logging.exception("Suppressed exception")
                            try:
                                popup.destroy()
                            except Exception:
                                logging.exception("Suppressed exception")

                        btn = self._create_sound_button(frame, text = name, command = _wrap, width = width, height = height, font = customtkinter.CTkFont(size = 12))
                        if fg:
                            try:
                                btn.configure(fg_color = fg)
                            except Exception:
                                logging.exception("Suppressed exception")
                        btn.pack(pady = 6)
                        return btn
                    except Exception:
                        logging.exception("Suppressed exception")
                    return None

                if check_clean_btn is not None:
                    _add('Check Cleanliness', check_cleanliness)
                if check_mag_btn is not None:
                    _add('Check Magazine', check_magazine)

                try:
                    _add('Cycle Action', cycle_bolt)
                except Exception:
                    logging.exception("Suppressed exception")
                if throw_btn is not None:
                    _add('Throw', throw_throwable)
                if manage_attach_btn is not None:
                    _add('Manage Attachments', manage_attachments)

                try:
                    bs_btn = _add('Barrel Swap', _barrel_swap_current)

                    try:
                        w_check = None
                        try:
                            w_check = current_weapon_state.get('weapon')if isinstance(current_weapon_state, dict)else None
                        except Exception:
                            w_check = None
                        if not w_check:
                            w_check = current_weapon
                        if not w_check or not bool((w_check.get('barrel_swap')if isinstance(w_check, dict)else False)):
                            if bs_btn is not None:
                                try:
                                    bs_btn.configure(state = 'disabled')
                                except Exception:
                                    logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    vp_btn = _add('Manage Parts', _view_parts)
                    w_vp = current_weapon_state.get('weapon') if isinstance(current_weapon_state, dict) else None
                    if not w_vp:
                        w_vp = current_weapon
                    if not w_vp or not (w_vp.get('parts') if isinstance(w_vp, dict) else None):
                        if vp_btn is not None:
                            try:
                                vp_btn.configure(state = 'disabled')
                            except Exception:
                                logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    has_consumables = len(_find_consumables_in_inventory())>0

                    def _wrap_consume():
                        try:
                            use_consumable()
                        except Exception:
                            logging.exception("Suppressed exception")
                        try:
                            popup.destroy()
                        except Exception:
                            logging.exception("Suppressed exception")

                    consume_btn = self._create_sound_button(frame, text = 'Use Consumable', command = _wrap_consume, width = 200, height = 44, font = customtkinter.CTkFont(size = 12))
                    if not has_consumables:
                        consume_btn.configure(state = 'disabled')
                    consume_btn.pack(pady = 6)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    w_gas = current_weapon_state.get('weapon') if isinstance(current_weapon_state, dict) else None
                    if not w_gas:
                        w_gas = current_weapon
                    raw_cyclic_list = w_gas.get('cyclic') if isinstance(w_gas, dict) else None
                    if isinstance(raw_cyclic_list, list) and len(raw_cyclic_list) > 1:
                        gas_weapon_id = str(w_gas.get('id', ''))
                        gas_settings = combat_state.setdefault('gas_setting', {})
                        current_gas_idx = gas_settings.get(gas_weapon_id, 0)
                        if current_gas_idx < 0 or current_gas_idx >= len(raw_cyclic_list):
                            current_gas_idx = 0
                            gas_settings[gas_weapon_id] = 0

                        gas_frame = customtkinter.CTkFrame(frame)
                        gas_frame.pack(pady = 10, padx = 10, fill = 'x')

                        customtkinter.CTkLabel(
                            gas_frame,
                            text = 'Gas Regulator:',
                            font = customtkinter.CTkFont(size = 12, weight = 'bold')
                        ).pack(side = 'top', padx = 5, pady = 2)

                        gas_canvas = customtkinter.CTkCanvas(
                            gas_frame,
                            width = 160,
                            height = 160,
                            bg = '#212121',
                            highlightthickness = 0
                        )
                        gas_canvas.pack(side = 'top', padx = 5, pady = 5)

                        num_gas = len(raw_cyclic_list)
                        gas_angles = {}
                        for gi in range(num_gas):
                            gas_angles[gi] = gi * (360 / num_gas)

                        gas_dial_state = {'current_angle': gas_angles.get(current_gas_idx, 0), 'dragging': False}

                        gas_label_var = customtkinter.StringVar(value = f'{int(raw_cyclic_list[current_gas_idx])} RPM')

                        def _draw_gas_dial():
                            gas_canvas.delete('all')
                            cx, cy = 80, 80
                            r = 40

                            gas_canvas.create_oval(
                                cx - r, cy - r,
                                cx + r, cy + r,
                                fill = '#333333', outline = '#555555', width = 2
                            )

                            for gi, angle in gas_angles.items():
                                rad = math.radians(angle)
                                x1 = cx + (r - 8) * math.cos(rad)
                                y1 = cy + (r - 8) * math.sin(rad)
                                x2 = cx + r * math.cos(rad)
                                y2 = cy + r * math.sin(rad)
                                gas_canvas.create_line(x1, y1, x2, y2, fill = '#888888', width = 3)

                                label_dist = r + 18
                                lx = cx + label_dist * math.cos(rad)
                                ly = cy + label_dist * math.sin(rad)
                                gas_canvas.create_text(
                                    lx, ly,
                                    text = f'{int(raw_cyclic_list[gi])}',
                                    fill = '#AAAAAA',
                                    font = ('Arial', 9, 'bold')
                                )

                            ca = gas_dial_state['current_angle']
                            rad = math.radians(ca)
                            px = cx + 32 * math.cos(rad)
                            py = cy + 32 * math.sin(rad)
                            gas_canvas.create_line(cx, cy, px, py, fill = '#FF4444', width = 4)

                            knob_r = 6
                            gas_canvas.create_oval(
                                cx - knob_r, cy - knob_r,
                                cx + knob_r, cy + knob_r,
                                fill = '#FF4444', outline = '#FFFFFF', width = 2
                            )

                            gas_canvas.create_text(
                                cx, 12,
                                text = gas_label_var.get(),
                                fill = '#00FF00',
                                font = ('Arial', 11, 'bold')
                            )

                        def _gas_angle_from_point(x, y):
                            dx = x - 80
                            dy = y - 80
                            return math.degrees(math.atan2(dy, dx)) % 360

                        def _gas_snap(angle):
                            best_idx = 0
                            best_diff = 360
                            for gi, ga in gas_angles.items():
                                diff = min(abs(angle - ga), 360 - abs(angle - ga))
                                if diff < best_diff:
                                    best_diff = diff
                                    best_idx = gi
                            return best_idx, gas_angles.get(best_idx, 0)

                        def _gas_mouse_down(event):
                            dx = event.x - 80
                            dy = event.y - 80
                            if math.sqrt(dx ** 2 + dy ** 2) < 50:
                                gas_dial_state['dragging'] = True

                        def _gas_mouse_move(event):
                            if not gas_dial_state['dragging']:
                                return
                            gas_dial_state['current_angle'] = _gas_angle_from_point(event.x, event.y)
                            _draw_gas_dial()

                        def _gas_mouse_up(event):
                            if not gas_dial_state['dragging']:
                                return
                            gas_dial_state['dragging'] = False
                            idx, snapped = _gas_snap(gas_dial_state['current_angle'])
                            gas_dial_state['current_angle'] = snapped
                            gas_settings[gas_weapon_id] = idx
                            gas_label_var.set(f'{int(raw_cyclic_list[idx])} RPM')
                            try:
                                self._safe_sound_play('firearms/universal', 'fireselector')
                            except Exception:
                                logging.exception("Suppressed exception")
                            _draw_gas_dial()

                        gas_canvas.bind('<Button-1>', _gas_mouse_down)
                        gas_canvas.bind('<B1-Motion>', _gas_mouse_move)
                        gas_canvas.bind('<ButtonRelease-1>', _gas_mouse_up)

                        _draw_gas_dial()
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    b = customtkinter.CTkButton(popup, text = 'Close', command = popup.destroy, width = 120)
                    b.pack(pady = 6)
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    popup.grab_set()
                    popup.lift()
                    self._safe_focus(popup)
                except Exception:
                    logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

        try:
            self._create_sound_button(actions_frame, text = 'More Actions', command = _show_more_actions, width = 150, height = 50, font = customtkinter.CTkFont(size = 14)).pack(side = 'left', padx = 10, pady = 10)
        except Exception:
            logging.exception("Suppressed exception")

        try:
            throw_btn = self._create_sound_button(actions_frame, text = 'Throw', command = throw_throwable, width = 150, height = 50, font = customtkinter.CTkFont(size = 14), fg_color = '#333333', hover_color = '#444444')
        except Exception:
            throw_btn = None
        try:
            manage_attach_btn = self._create_sound_button(
            actions_frame,
            text = "Manage Attachments",
            command = manage_attachments,
            width = 170,
            height = 50,
            font = customtkinter.CTkFont(size = 14)
            )
        except Exception:
            manage_attach_btn = None

        if global_variables.get("devmode", {}).get("value", False):
            devmode_outer_frame = customtkinter.CTkFrame(main_frame)
            devmode_outer_frame.pack(fill = "x", pady =(0, 20))

            devmode_frame = customtkinter.CTkScrollableFrame(devmode_outer_frame, orientation = "horizontal", height = 60, fg_color = "transparent")
            devmode_frame.pack(fill = "x", expand = True)

            customtkinter.CTkLabel(
            devmode_frame,
            text = "DevMode:",
            font = customtkinter.CTkFont(size = 12)
            ).pack(side = "left", padx = 10)

            def get_variant_choices():
                choices =[]
                weapon_obj = current_weapon_state.get("weapon")or {}
                raw_cal = weapon_obj.get("caliber")
                selected_caliber = None

                cal = None
                if isinstance(raw_cal, (list, tuple)):
                    cal = raw_cal[0]if raw_cal else None
                elif isinstance(raw_cal, str):
                    cal = raw_cal

                w_sounds = weapon_obj.get("sounds")or weapon_obj.get("sound_folder")or weapon_obj.get("ammo_type")
                if not cal:
                    active_ub = combat_state.get("active_underbarrel")

                    if active_ub and isinstance(active_ub, dict)and active_ub.get("parent_index")==combat_state.get("current_weapon_index"):
                        aid = active_ub.get("accessory_id")
                        aname = active_ub.get("accessory_name")

                        parent_entry = equipped_weapons[combat_state.get("current_weapon_index")]
                        parent_slot = parent_entry.get("slot", "")
                        if "->"in parent_slot:
                            parent_slot = parent_slot.split("->")[0].strip()
                        parent_item = save_data.get("equipment", {}).get(parent_slot)
                        acc = None
                        if parent_item and isinstance(parent_item, dict):
                            for acc_entry in parent_item.get("accessories", [])or[]:
                                cur = acc_entry.get("current")
                                if isinstance(cur, dict):
                                    if aid is not None and cur.get("id")==aid:
                                        acc = cur ;break
                                    if aname and cur.get("name")==aname:
                                        acc = cur ;break
                                else:
                                    try:
                                        if aid is not None and(isinstance(cur, int)or(isinstance(cur, str)and cur.isdigit()))and int(cur)==int(aid):

                                            tables = table_data.get("tables", {})if isinstance(table_data, dict)else {}
                                            for arr in tables.values():
                                                if isinstance(arr, list):
                                                    for it in arr:
                                                        if isinstance(it, dict)and it.get("id")==int(cur):
                                                            acc = it ;break
                                                    if acc:break
                                    except Exception:
                                        logging.exception("Suppressed exception")
                        if acc and isinstance(acc, dict):
                            raw_cal2 = acc.get("caliber")
                            if isinstance(raw_cal2, (list, tuple)):
                                cal = raw_cal2[0]if raw_cal2 else None
                            elif isinstance(raw_cal2, str):
                                cal = raw_cal2
                            if not cal:
                                w_sounds = acc.get("sounds")or acc.get("sound_folder")or acc.get("ammo_type")

                try:
                    dev_cal_var = current_weapon_state.get("dev_caliber_var")
                    if dev_cal_var and hasattr(dev_cal_var, 'get'):
                        sel = dev_cal_var.get()
                        if sel:
                            cal = sel
                            selected_caliber = str(sel)
                except Exception:
                    logging.exception("Suppressed exception")

                ammo_tables = table_data.get("tables", {}).get("ammunition", [])if table_data else[]
                for ammo in ammo_tables:
                    try:

                        ammo_cal = ammo.get("caliber")
                        match_cal = False
                        if cal and ammo_cal:
                            if isinstance(ammo_cal, (list, tuple)):
                                match_cal = any((isinstance(a, str)and a ==cal)for a in ammo_cal)
                            elif isinstance(ammo_cal, str):
                                match_cal =(ammo_cal ==cal)

                        if match_cal:
                            for var in ammo.get("variants", [])or[]:
                                vname = var.get("name")
                                if vname and vname not in choices:
                                    choices.append(vname)
                            continue

                        # If a caliber is explicitly selected, only show variants from that caliber.
                        if selected_caliber:
                            continue

                        if w_sounds and(ammo.get("sounds")==w_sounds or ammo.get("ammo_type")==w_sounds):
                            for var in ammo.get("variants", [])or[]:
                                vname = var.get("name")
                                if vname and vname not in choices:
                                    choices.append(vname)
                    except Exception:
                        logging.exception("Suppressed exception")
                return choices or["Ball"]

            variant_var = customtkinter.StringVar(value = get_variant_choices()[0])
            customtkinter.CTkLabel(
            devmode_frame,
            text = "Variant:",
            font = customtkinter.CTkFont(size = 12)
            ).pack(side = "left", padx = 5)

            try:

                wpn_for_dev =(current_weapon_state.get("weapon")if isinstance(current_weapon_state, dict)else None)or {}
                raw_cal_list = wpn_for_dev.get("caliber")if isinstance(wpn_for_dev, dict)else None
                calib_values =[]
                if isinstance(raw_cal_list, (list, tuple)):
                    calib_values =[str(x)for x in raw_cal_list if x is not None]
                elif isinstance(raw_cal_list, str):
                    calib_values =[raw_cal_list]

                if not calib_values:
                    calib_values =[]

                caliber_var = customtkinter.StringVar(value =(calib_values[0]if calib_values else ""))

                def _on_caliber_change(val):
                    try:
                        current_weapon_state["dev_caliber_var"]= caliber_var

                        try:
                            new_choices = get_variant_choices()

                            try:
                                if variant_menu:
                                    variant_menu.configure(values = new_choices)
                                    if variant_var.get()not in new_choices:
                                        variant_var.set(new_choices[0])
                            except Exception:
                                try:
                                    variant_menu.set_values(new_choices)
                                    if variant_var.get()not in new_choices:
                                        variant_var.set(new_choices[0])
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")
                    except Exception:
                        logging.exception("Suppressed exception")

                calib_vals_for_widget = calib_values if calib_values else["None"]
                caliber_menu = customtkinter.CTkOptionMenu(devmode_frame, values = calib_vals_for_widget, variable = caliber_var, command = _on_caliber_change, width = 140)
                caliber_menu.pack(side = "left", padx = 5)
                if len(calib_values)<=1:
                    try:
                        caliber_menu.configure(state = "disabled")
                    except Exception:
                        logging.exception("Suppressed exception")
                current_weapon_state["dev_caliber_menu_ref"]= caliber_menu
                current_weapon_state["dev_caliber_var"]= caliber_var
            except Exception:
                logging.exception("Failed to create DevMode caliber menu")

            variant_menu = customtkinter.CTkOptionMenu(
            devmode_frame,
            values = get_variant_choices(),
            variable = variant_var,
            width = 120
            )
            variant_menu.pack(side = "left", padx = 5)

            current_weapon_state["dev_variant_menu_ref"]= variant_menu
            current_weapon_state["dev_variant_var"]= variant_var

            def add_ammo():
                try:
                    current_weapon = current_weapon_state["weapon"]
                    mag_type = current_weapon.get("magazinetype", "Unknown")
                    capacity = current_weapon.get("capacity", 30)

                    caliber_name = caliber_var.get()if caliber_var.get()else current_weapon.get('caliber', ['rnd'])[0]
                    variant_name = variant_var.get()

                    ammo_tables = table_data.get("tables", {}).get("ammunition", [])if table_data else[]
                    ammo_sounds = None
                    ammo_entry = None
                    for ammo in ammo_tables:
                        try:
                            ammo_cal = ammo.get("caliber")
                            if ammo_cal ==caliber_name:
                                ammo_sounds = ammo.get("sounds")
                                ammo_entry = ammo
                                break

                            if isinstance(ammo_cal, (list, tuple))and caliber_name in ammo_cal:
                                ammo_sounds = ammo.get("sounds")
                                ammo_entry = ammo
                                break
                        except Exception:
                            logging.exception("Suppressed exception")

                    dummy_round = {
                    "name":f"{caliber_name} | {variant_name}",
                    "caliber":caliber_name,
                    "variant":variant_name
                    }
                    if ammo_sounds:
                        dummy_round["sounds"]= ammo_sounds

                    if ammo_entry:
                        for var in ammo_entry.get("variants", [])or[]:
                            if var.get("name")==variant_name:
                                if var.get("type"):
                                    dummy_round["type"]= var.get("type")
                                if var.get("pen"):
                                    dummy_round["pen"]= var.get("pen")
                                if var.get("tip"):
                                    dummy_round["tip"]= var.get("tip")
                                if var.get("modifiers"):
                                    dummy_round["modifiers"]= var.get("modifiers")
                                break

                    loaded_mag = {
                    "magazinetype":mag_type,
                    "magazinesystem":current_weapon.get("magazinesystem"),
                    "capacity":capacity,
                    "rounds":[dict(dummy_round)for _ in range(capacity)]
                    }
                    current_weapon["loaded"]= loaded_mag

                    if loaded_mag["rounds"]:
                        current_weapon["chambered"]= loaded_mag["rounds"].pop(0)

                    self._popup_show_info("DevMode Ammo", f"Filled mag({mag_type}) with {capacity} {caliber_name} {variant_name} rounds and chambered one")
                    update_weapon_view()
                except Exception as e:
                    self._popup_show_info("DevMode Error", str(e))

            def devmode_debug():
                try:
                    wpn = current_weapon_state.get("weapon")or {}
                    cal =(wpn.get("caliber")or[])
                    if isinstance(cal, (list, tuple)):
                        cal_val = cal[0]if cal else None
                    else:
                        cal_val = cal
                    w_sounds = wpn.get("sounds")or wpn.get("sound_folder")or wpn.get("ammo_type")
                    ammo_tables = table_data.get("tables", {}).get("ammunition", [])if table_data else[]
                    matches =[]
                    for ammo in ammo_tables:
                        try:
                            if cal_val and ammo.get("caliber")==cal_val:
                                matches.append(ammo.get("name"))
                            elif w_sounds and(ammo.get("sounds")==w_sounds or ammo.get("ammo_type")==w_sounds):
                                matches.append(ammo.get("name"))
                        except Exception:
                            logging.exception("Suppressed exception")

                    msg = f"Weapon: {wpn.get('name')}\ncaliber: {cal_val}\nsounds: {w_sounds}\nMatched ammo: {matches}"
                    self._popup_show_info("DevMode Debug", msg)
                except Exception as e:
                    logging.exception("DevMode debug failed: %s", e)

            customtkinter.CTkButton(devmode_frame, text = "Debug Variants", command = devmode_debug, width = 140).pack(side = "left", padx = 8)

            def add_all_throwables():
                try:

                    found =[]
                    tables = table_data.get("tables", {})if table_data else {}
                    for tname, items in tables.items():
                        if not isinstance(items, list):
                            continue
                        try:
                            for it in items:
                                if not isinstance(it, dict):
                                    continue
                                try:
                                    typ = str(it.get('type', '')).lower()
                                    if typ in('fragmentation', 'smoke', 'stun', '9-bang', '9bang', '9_bang'):
                                        item_copy = it.copy()
                                        item_copy = add_subslots_to_item(item_copy)
                                        found.append(item_copy)
                                except Exception:
                                    logging.exception("Suppressed exception")
                        except Exception:
                            logging.exception("Suppressed exception")

                    if not found:

                        found =[
                        {"name":"Fragmentation Grenade", "type":"fragmentation", "fuse":3},
                        {"name":"Smoke Grenade", "type":"smoke", "fuse":3},
                        {"name":"Stun Grenade", "type":"stun", "fuse":3},
                        {"name":"9-Bang", "type":"9-bang", "fuse":3},
                        ]

                    if not self.currentsave:
                        self._popup_show_info('DevMode Error', 'No active save to modify.', sound = 'error')
                        return
                    save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
                    if not os.path.exists(save_path):
                        self._popup_show_info('DevMode Error', f'Save file not found: {save_path}', sound = 'error')
                        return

                    added = 0
                    sd = globals().get('save_data')if 'save_data'in globals()else None
                    logging.debug(f"DevMode Add Throwables: currentsave={self.currentsave}, save_path={save_path}, in_memory_save_present={isinstance(sd, dict)}")
                    if isinstance(sd, dict):
                        try:
                            before = len(sd.get('hands', {}).get('items', []))if sd.get('hands')else 0
                            sd.setdefault('hands', {})
                            sd['hands'].setdefault('items', [])
                            for itm in found:
                                try:
                                    itm_copy = itm.copy()if isinstance(itm, dict)else itm
                                    if isinstance(itm_copy, dict):
                                        _set_full_part_durability(itm_copy)
                                    sd['hands']['items'].append(itm_copy)
                                    added +=1
                                except Exception:
                                    logging.exception('Failed to append throwable to in-memory hands')
                            after = len(sd.get('hands', {}).get('items', []))
                            logging.debug(f"Added to in-memory hands: before={before}, after={after}, added={added}")

                            try:
                                globals()['save_data']= sd
                            except Exception:
                                logging.exception("Suppressed exception")

                            try:
                                self._save_file(sd)
                            except Exception:
                                logging.exception('Failed to persist save_data after adding throwables')

                            try:
                                if 'save_data'in globals():

                                    outer = globals().get('save_data')
                                    if outer is not sd and isinstance(outer, dict)and isinstance(sd, dict):
                                        outer.clear()
                                        outer.update(sd)
                                        globals()['save_data']= outer
                                        logging.debug('Synchronized global save_data object in-place after in-memory save')
                            except Exception:
                                logging.exception('Failed to synchronize save_data object in-place')
                        except Exception:
                            logging.exception('Failed to add throwables to in-memory save_data')
                    else:

                        try:
                            file_sd = self._read_save_from_path(save_path)
                            if file_sd is None:
                                file_sd = {}
                        except Exception:
                            file_sd = {}
                        try:
                            before = len(file_sd.get('hands', {}).get('items', []))if file_sd.get('hands')else 0
                            file_sd.setdefault('hands', {})
                            file_sd['hands'].setdefault('items', [])
                            for itm in found:
                                try:
                                    itm_copy = itm.copy()if isinstance(itm, dict)else itm
                                    if isinstance(itm_copy, dict):
                                        _set_full_part_durability(itm_copy)
                                    file_sd['hands']['items'].append(itm_copy)
                                    added +=1
                                except Exception:
                                    logging.exception('Failed to append throwable to save file hands')
                            after = len(file_sd.get('hands', {}).get('items', []))
                            logging.debug(f"Added to file hands: before={before}, after={after}, added={added}")

                            try:
                                self._save_file(file_sd)
                            except Exception:
                                logging.exception('Failed to persist save file after adding throwables')

                            try:
                                loaded = self._load_file(self.currentsave)
                                if loaded and isinstance(loaded, dict):

                                    globals()['save_data']= loaded
                                    logging.debug('Reloaded save into memory after DevMode add_all_throwables')

                                    try:

                                        if isinstance(save_data, dict):
                                            save_data.clear()
                                            save_data.update(loaded)
                                            logging.debug('Updated enclosing save_data object in-place after reload')
                                    except Exception:
                                        logging.debug('No enclosing save_data to update in-place or update failed')
                            except Exception:
                                logging.exception('Failed to reload save into memory after adding throwables')
                        except Exception:
                            logging.exception('Failed to add throwables to save file')

                    self._popup_show_info('DevMode', f'Added {added} throwables to hands', sound = 'success')
                    try:
                        update_weapon_view()
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception as e:
                    logging.exception('Failed to add throwables: %s', e)
                    self._popup_show_info('DevMode Error', str(e), sound = 'error')

            customtkinter.CTkButton(devmode_frame, text = "Add All Throwables", command = add_all_throwables, width = 160).pack(side = "left", padx = 8)

            def reset_temperature():
                try:
                    current_weapon = current_weapon_state["weapon"]
                    weapon_id = str(current_weapon.get("id"))
                    combat_state["barrel_temperatures"][weapon_id]= combat_state["ambient_temperature"]
                    self._popup_show_info("DevMode Temp", f"Barrel temperature reset to ambient")
                    update_weapon_view()
                except Exception as e:
                    self._popup_show_info("DevMode Error", str(e))

            def reset_cleanliness():
                try:
                    current_weapon = current_weapon_state["weapon"]
                    weapon_id = str(current_weapon.get("id"))
                    combat_state["barrel_cleanliness"][weapon_id]= 100
                    self._popup_show_info("DevMode Clean", f"Barrel cleanliness reset to 100%")
                    update_weapon_view()
                except Exception as e:
                    self._popup_show_info("DevMode Error", str(e))

            def add_individual_rounds():

                try:
                    current_weapon = current_weapon_state["weapon"]
                    selected_caliber = ""
                    try:
                        selected_caliber = str(caliber_var.get() or "").strip()
                    except Exception:
                        selected_caliber = ""

                    if not selected_caliber:
                        raw_cal = current_weapon.get("caliber", [])or[]
                        if isinstance(raw_cal, (list, tuple)):
                            selected_caliber = str(raw_cal[0]).strip() if raw_cal else ""
                        else:
                            selected_caliber = str(raw_cal).strip() if raw_cal is not None else ""

                    w_sounds = current_weapon.get("sounds")or current_weapon.get("sound_folder")or current_weapon.get("ammo_type")

                    ammo_tables = table_data.get("tables", {}).get("ammunition", [])if table_data else[]
                    ammo_def = None
                    for a in ammo_tables:
                        try:
                            a_cal = a.get("caliber")

                            if selected_caliber:
                                if isinstance(a_cal, (list, tuple))and selected_caliber in [str(x)for x in a_cal if x is not None]:
                                    ammo_def = a ;break
                                if isinstance(a_cal, str)and a_cal ==selected_caliber:
                                    ammo_def = a ;break

                            a_id = a.get("id")
                            if a_id is not None and selected_caliber and str(a_id)==selected_caliber:
                                ammo_def = a ;break

                            # Fallback by sounds only when no caliber was selected/resolved.
                            if w_sounds and(a.get("sounds")==w_sounds or a.get("ammo_type")==w_sounds):
                                if not selected_caliber:
                                    ammo_def = a ;break
                        except Exception:
                            logging.exception("Suppressed exception")
                            continue

                    if not ammo_def:
                        self._popup_show_info("DevMode Error", f"No ammunition definition found for {repr(selected_caliber or w_sounds)}")
                        return

                    variant_name = variant_var.get()
                    variant_info = None
                    for var in ammo_def.get("variants", []):
                        if var.get("name")==variant_name:
                            variant_info = var
                            break
                    if not variant_info and ammo_def.get("variants"):
                        variant_info = ammo_def["variants"][0]

                    single_round = {
                    "name":f"{selected_caliber or ammo_def.get('caliber') or 'Unknown'} | {variant_name}",
                    "caliber":selected_caliber or ammo_def.get("caliber"),
                    "variant":variant_name,
                    "weight":ammo_def.get("weight", 0.01),
                    "value":ammo_def.get("value", 0),
                    "sounds":ammo_def.get("sounds", ""),
                    "description":f"{selected_caliber or ammo_def.get('caliber') or 'Unknown'} - {variant_name}"
                    }
                    if variant_info:
                        _apply_ammo_variant_data(single_round, ammo_def, variant_info)

                    hands = save_data.get("hands", {})
                    if "items"not in hands or not isinstance(hands.get("items"), list):
                        hands["items"]=[]
                        save_data["hands"]= hands

                    ammo_item = dict(single_round)
                    ammo_item["quantity"]= 500
                    hands["items"].append(ammo_item)

                    self._popup_show_info("DevMode Ammo", f"Added 500 rounds(stacked) to hands")
                    update_weapon_view()
                except Exception as e:
                    logging.error(f"Error adding rounds: {e}")
                    self._popup_show_info("DevMode Error", str(e))

            def add_individual_magazine():

                try:

                    current_weapon = current_weapon_state.get("weapon", {})
                    needed = set()
                    needed.update(self._normalize_to_lower_set(current_weapon.get("magazinesystem")))
                    needed.update(self._normalize_to_lower_set(current_weapon.get("submagazinesystem")))
                    needed.update(self._normalize_to_lower_set(current_weapon.get("submagazinetype")))

                    if not needed:
                        self._popup_show_info("DevMode Error", "Weapon doesn't use detachable magazines")
                        return

                    magazines_table = table_data.get("tables", {}).get("magazines", [])
                    compatible_mags = []
                    for m in magazines_table:
                        if not isinstance(m, dict):
                            continue
                        mag_tokens = set()
                        mag_tokens.update(self._normalize_to_lower_set(m.get("magazinesystem")))
                        mag_tokens.update(self._normalize_to_lower_set(m.get("magazinetype")))
                        if mag_tokens.intersection(needed):
                            compatible_mags.append(m)

                    if not compatible_mags:
                        systems_text = ", ".join(sorted(needed)) if needed else "unknown"
                        self._popup_show_info("DevMode Error", f"No magazines in table for: {systems_text}")
                        return

                    mag_template = compatible_mags[0]
                    capacity = mag_template.get('capacity', 30)

                    rounds = []
                    try:
                        selected_caliber = ""
                        try:
                            selected_caliber = str(caliber_var.get() or "").strip()
                        except Exception:
                            selected_caliber = ""

                        if not selected_caliber:
                            raw_cal = current_weapon.get("caliber", [])or[]
                            if isinstance(raw_cal, (list, tuple)):
                                selected_caliber = str(raw_cal[0]).strip() if raw_cal else ""
                            else:
                                selected_caliber = str(raw_cal).strip() if raw_cal is not None else ""

                        w_sounds = current_weapon.get("sounds")or current_weapon.get("sound_folder")or current_weapon.get("ammo_type")

                        ammo_tables = table_data.get("tables", {}).get("ammunition", [])if table_data else[]
                        ammo_def = None
                        for a in ammo_tables:
                            try:
                                a_cal = a.get("caliber")
                                if selected_caliber:
                                    if isinstance(a_cal, (list, tuple))and selected_caliber in [str(x)for x in a_cal if x is not None]:
                                        ammo_def = a ;break
                                    if isinstance(a_cal, str)and a_cal ==selected_caliber:
                                        ammo_def = a ;break
                                a_id = a.get("id")
                                if a_id is not None and selected_caliber and str(a_id)==selected_caliber:
                                    ammo_def = a ;break

                                if w_sounds and(a.get("sounds")==w_sounds or a.get("ammo_type")==w_sounds):
                                    if not selected_caliber:
                                        ammo_def = a ;break
                            except Exception:
                                logging.exception("Suppressed exception")
                                continue

                        if ammo_def:
                            variant_name = variant_var.get()
                            variant_info = None
                            for var in ammo_def.get("variants", []):
                                if var.get("name")==variant_name:
                                    variant_info = var
                                    break
                            if not variant_info and ammo_def.get("variants"):
                                variant_info = ammo_def["variants"][0]

                            single_round = {
                            "name":f"{selected_caliber or ammo_def.get('caliber') or 'Unknown'} | {variant_name}",
                            "caliber":selected_caliber or ammo_def.get("caliber"),
                            "variant":variant_name,
                            "weight":ammo_def.get("weight", 0.01),
                            "value":ammo_def.get("value", 0),
                            "sounds":ammo_def.get("sounds", ""),
                            "description":f"{selected_caliber or ammo_def.get('caliber') or 'Unknown'} - {variant_name}"
                            }
                            if variant_info:
                                _apply_ammo_variant_data(single_round, ammo_def, variant_info)

                            rounds =[dict(single_round)for _ in range(capacity)]
                    except Exception:
                        logging.exception("Suppressed exception")

                    new_mag = {
                    'name':mag_template.get('name'),
                    'id':mag_template.get('id'),
                    'magazinetype':mag_template.get('magazinetype', 'Unknown'),
                    'magazinesystem':mag_template.get('magazinesystem', current_weapon.get('magazinesystem')),
                    'capacity':capacity,
                    'rounds':rounds
                    }

                    save_data.setdefault('hands', {}).setdefault('items', []).append(new_mag)
                    update_weapon_view()
                    round_desc = f"loaded with {len(rounds)} rounds"if rounds else "empty"
                    self._popup_show_info('DevMode Ammo', f"Added {new_mag.get('name')} to hands({round_desc})")
                except Exception as e:
                    logging.error(f"Error adding magazine: {e}")
                    self._popup_show_info("DevMode Error", str(e))

            def add_belt():
                try:
                    self._popup_show_info("DevMode", "Belt functionality removed.")
                    return
                except Exception:
                    return

            self._create_sound_button(
            devmode_frame,
            text = "Fill Magazine",
            command = add_ammo,
            width = 120,
            height = 40,
            font = customtkinter.CTkFont(size = 12),
            fg_color = "#8B4513",
            hover_color = "#A0522D"
            ).pack(side = "left", padx = 5, pady = 10)

            self._create_sound_button(
            devmode_frame,
            text = "Add Rounds",
            command = add_individual_rounds,
            width = 120,
            height = 40,
            font = customtkinter.CTkFont(size = 12),
            fg_color = "#8B4513",
            hover_color = "#A0522D"
            ).pack(side = "left", padx = 5, pady = 10)

            self._create_sound_button(
            devmode_frame,
            text = "Add Magazine",
            command = add_individual_magazine,
            width = 120,
            height = 40,
            font = customtkinter.CTkFont(size = 12),
            fg_color = "#8B4513",
            hover_color = "#A0522D"
            ).pack(side = "left", padx = 5, pady = 10)

            self._create_sound_button(
            devmode_frame,
            text = "Add Belt",
            command = add_belt,
            width = 120,
            height = 40,
            font = customtkinter.CTkFont(size = 12),
            state = "disabled",
            fg_color = "#8B4513",
            hover_color = "#A0522D",
            ).pack(side = "left", padx = 5, pady = 10)

            self._create_sound_button(
            devmode_frame,
            text = "Reset Temp",
            command = reset_temperature,
            width = 120,
            height = 40,
            font = customtkinter.CTkFont(size = 12),
            fg_color = "#8B4513",
            hover_color = "#A0522D"
            ).pack(side = "left", padx = 5, pady = 10)

            self._create_sound_button(
            devmode_frame,
            text = "Reset Clean",
            command = reset_cleanliness,
            width = 120,
            height = 40,
            font = customtkinter.CTkFont(size = 12),
            fg_color = "#8B4513",
            hover_color = "#A0522D"
            ).pack(side = "left", padx = 5, pady = 10)

        list_label = customtkinter.CTkLabel(
        main_frame,
        text = "Available Weapons",
        font = customtkinter.CTkFont(size = 14, weight = "bold")
        )
        list_label.pack(pady =(10, 5))

        list_frame = customtkinter.CTkFrame(main_frame)
        list_frame.pack(fill = "both", padx = 10, pady =(0, 20))

        for idx, weapon_data in enumerate(equipped_weapons):
            weapon_item = weapon_data["item"]
            is_selected =(idx ==combat_state["current_weapon_index"])

            weapon_btn_frame = customtkinter.CTkFrame(
            list_frame,
            fg_color = "#2D3B45"if is_selected else "#1F2B35"
            )
            weapon_btn_frame.pack(fill = "x", pady = 2)

            weapon_label = customtkinter.CTkLabel(
            weapon_btn_frame,
            text = f"{weapon_data['display_name']} - {weapon_data['slot']}",
            font = customtkinter.CTkFont(size = 12),
            text_color = "#00FF00"if is_selected else "#FFFFFF"
            )
            weapon_label.pack(side = "left", padx = 10, pady = 5)

            def switch_to(w_idx = idx, w_item = weapon_item):

                try:
                    self._play_firearm_sound(w_item, "equip")
                except Exception:
                    logging.exception("Suppressed exception")
                combat_state["current_weapon_index"]= w_idx
                refresh_weapon_display()

            self._create_sound_button(
            weapon_btn_frame,
            text = "Select",
            command = switch_to,
            width = 100,
            height = 30,
            font = customtkinter.CTkFont(size = 11)
            ).pack(side = "right", padx = 10, pady = 5)

        watch_cancel = None
        watch_runtime_active = [True]
        watch_sound_clock_state = {"last_second": (-1, -1, -1), "last_hourly_beep": (-1, -1, -1)}

        def _play_watch_sound(filename, *, volume, pitch_range):

            try:
                sound_path = os.path.join("sounds", "misc", "watch", filename)
                if not sound_path.lower().endswith(".ogg"):
                    sound_path +='.ogg'
                if not os.path.exists(sound_path):
                    alt_path = os.path.join("sounds", "misc", filename)
                    if not alt_path.lower().endswith(".ogg"):
                        alt_path +='.ogg'
                    if os.path.exists(alt_path):
                        sound_path = alt_path
                if not os.path.exists(sound_path):
                    return
                pitch = random.uniform(pitch_range[0], pitch_range[1])
                if not self._play_pitched_sound(sound_path, volume = volume, pitch = pitch):
                    base_name = os.path.splitext(os.path.basename(sound_path))[0]
                    if os.path.dirname(sound_path).replace('\\', '/').endswith("sounds/misc/watch"):
                        self._safe_sound_play("misc/watch", base_name, block = False)
                    else:
                        self._safe_sound_play("misc", base_name, block = False)
            except Exception:
                logging.exception("Failed to play watch sound")

        poll_cancel = None

        def _draw_analog_watch(canvas, now_dt, show_seconds):
            try:
                if not canvas or not canvas.winfo_exists():
                    return
                canvas.delete("all")

                # Derive geometry from the canvas size so the analog face scales
                # with the resolution-scaled canvas (design reference radius = 35).
                w = canvas.winfo_width()
                h = canvas.winfo_height()
                if w <= 1 or h <= 1:
                    try:
                        w = int(float(canvas.cget("width")))
                        h = int(float(canvas.cget("height")))
                    except Exception:
                        w = h = 92
                cx = w / 2.0
                cy = h / 2.0
                radius = min(cx, cy) - max(2.0, w * 0.12)
                sc = radius / 35.0

                def _lw(v):
                    return max(1, int(round(v * sc)))

                canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, fill = "#E8E1CC", outline = "#8E8A7D", width = _lw(2))

                for hh in range(12):
                    ang = math.radians((hh * 30) - 90)
                    x1 = cx +(radius - 6 * sc) * math.cos(ang)
                    y1 = cy +(radius - 6 * sc) * math.sin(ang)
                    x2 = cx +(radius - 2 * sc) * math.cos(ang)
                    y2 = cy +(radius - 2 * sc) * math.sin(ang)
                    canvas.create_line(x1, y1, x2, y2, fill = "#3B3B3B", width = _lw(2))

                hr = now_dt.hour % 12
                mn = now_dt.minute
                sec = now_dt.second

                hour_ang = math.radians(((hr + mn / 60.0) * 30) - 90)
                min_ang = math.radians(((mn + sec / 60.0) * 6) - 90)
                sec_ang = math.radians((sec * 6) - 90)

                canvas.create_line(cx, cy, cx +18 * sc * math.cos(hour_ang), cy +18 * sc * math.sin(hour_ang), fill = "#202020", width = _lw(4))
                canvas.create_line(cx, cy, cx +26 * sc * math.cos(min_ang), cy +26 * sc * math.sin(min_ang), fill = "#202020", width = _lw(3))
                if show_seconds:
                    canvas.create_line(cx, cy, cx +29 * sc * math.cos(sec_ang), cy +29 * sc * math.sin(sec_ang), fill = "#C23232", width = _lw(1))

                _dot = 3 * sc
                canvas.create_oval(cx - _dot, cy - _dot, cx + _dot, cy + _dot, fill = "#202020", outline = "#202020")
            except Exception:
                logging.exception("Suppressed exception")

        def update_watch_display():

            nonlocal watch_cancel
            try:
                if not watch_runtime_active[0]:
                    watch_cancel = None
                    return

                active_watch_rows = []
                for _row in watch_rows:
                    _widget = _row.get("time_canvas") or _row.get("time_label") or _row.get("analog_canvas")
                    try:
                        if _widget and _widget.winfo_exists():
                            active_watch_rows.append(_row)
                    except Exception:
                        logging.exception("Suppressed exception")

                if not active_watch_rows:
                    watch_cancel = None
                    return

                now_dt = datetime.now()
                weather_name = str(weather_state.get("weather", "clear")).strip().lower()
                weather_temp = weather_state.get("temperature_f", combat_state.get("ambient_temperature", 70))
                weather_temp_text = _watch_temperature_text(weather_temp)
                has_analog_watch = any(str(row.get("watch_type", "")).strip().lower() != "digital" for row in active_watch_rows)
                _beep_mutes = combat_state.get("watch_hourly_beep_muted", {})
                if not isinstance(_beep_mutes, dict):
                    _beep_mutes = {}
                has_unmuted_digital = any(
                    str(row.get("watch_type", "")).strip().lower() == "digital" and
                    not bool(_beep_mutes.get(row.get("beep_key"), False))
                    for row in active_watch_rows
                )

                second_key = (now_dt.hour, now_dt.minute, now_dt.second)
                if watch_sound_clock_state.get("last_second") != second_key:
                    watch_sound_clock_state["last_second"] = second_key
                    if has_unmuted_digital and now_dt.minute == 0 and now_dt.second == 0:
                        hourly_key = (now_dt.year, now_dt.timetuple().tm_yday, now_dt.hour)
                        if watch_sound_clock_state.get("last_hourly_beep") != hourly_key:
                            watch_sound_clock_state["last_hourly_beep"] = hourly_key
                            _play_watch_sound("hourly beep.ogg", volume = 0.45, pitch_range = (0.995, 1.005))
                    if has_analog_watch:
                        if now_dt.minute == 0 and now_dt.second == 0:
                            _play_watch_sound("clocktick.ogg", volume = 0.50, pitch_range = (0.985, 1.015))
                        elif now_dt.second == 0:
                            _play_watch_sound("clocktick.ogg", volume = 0.34, pitch_range = (0.95, 1.05))
                        else:
                            _play_watch_sound("clocktick.ogg", volume = 0.22, pitch_range = (0.96, 1.04))

                for row_state in active_watch_rows:
                    use_24h = True
                    try:
                        use_24h = bool(row_state.get("time_24h_var").get())
                    except Exception:
                        use_24h = bool(combat_state.get("watch_time_24h", True))

                    if row_state.get("toggle_btn") and row_state["toggle_btn"].winfo_exists():
                        row_state["toggle_btn"].configure(text = "24H" if use_24h else "12H")

                    time_label = row_state.get("time_label")
                    time_canvas = row_state.get("time_canvas")
                    analog_canvas = row_state.get("analog_canvas")
                    if not time_label and not time_canvas and not analog_canvas:
                        continue

                    if time_canvas and time_canvas.winfo_exists():
                        _time_live_item = row_state.get("time_live_item")
                        _time_ghost_item = row_state.get("time_ghost_item")
                        if _time_live_item is not None:
                            time_canvas.itemconfigure(_time_live_item, text = _watch_time_text(now_dt, row_state["seconds"], use_24h = use_24h))
                        if _time_ghost_item is not None:
                            time_canvas.itemconfigure(_time_ghost_item, text = "88:88:88")
                    elif time_label and time_label.winfo_exists():
                        time_label.configure(text = _watch_time_text(now_dt, row_state["seconds"], use_24h = use_24h))

                        time_ghost = row_state.get("time_ghost_label")
                        if time_ghost and time_ghost.winfo_exists():
                            time_ghost.configure(text = "88:88:88")

                    am_lbl = row_state.get("am_label")
                    pm_lbl = row_state.get("pm_label")
                    if am_lbl and pm_lbl and am_lbl.winfo_exists() and pm_lbl.winfo_exists():
                        if use_24h:
                            am_lbl.configure(text_color = "#4F6338")
                            pm_lbl.configure(text_color = "#4F6338")
                        else:
                            is_pm = now_dt.hour >= 12
                            am_lbl.configure(text_color = "#AEDD93" if not is_pm else "#4F6338")
                            pm_lbl.configure(text_color = "#AEDD93" if is_pm else "#4F6338")

                    if analog_canvas and analog_canvas.winfo_exists():
                        _draw_analog_watch(analog_canvas, now_dt, bool(row_state.get("seconds")))

                    if row_state["watch_type"] == "digital":
                        _row_beep_btn = row_state.get("beep_toggle_btn")
                        if _row_beep_btn and _row_beep_btn.winfo_exists():
                            _muted = bool(_beep_mutes.get(row_state.get("beep_key"), False))
                            _row_beep_btn.configure(
                                text = "BEEP OFF" if _muted else "BEEP ON",
                                fg_color = "#4D2E2E" if _muted else "#2E4D2E"
                            )
                        _weather_canvas = row_state.get("weather_canvas")
                        if _weather_canvas and _weather_canvas.winfo_exists():
                            _weather_live_item = row_state.get("weather_live_item")
                            _weather_ghost_item = row_state.get("weather_ghost_item")
                            if _weather_live_item is not None:
                                _weather_canvas.itemconfigure(_weather_live_item, text = _watch_weather_icon_code(weather_name))
                            if _weather_ghost_item is not None:
                                _weather_canvas.itemconfigure(_weather_ghost_item, text = "0")
                        elif row_state["weather_icon_label"] and row_state["weather_icon_label"].winfo_exists():
                            row_state["weather_icon_label"].configure(text = _watch_weather_icon_code(weather_name))

                        _temp_canvas = row_state.get("temp_canvas")
                        if _temp_canvas and _temp_canvas.winfo_exists():
                            _temp_live_item = row_state.get("temp_live_item")
                            _temp_ghost_item = row_state.get("temp_ghost_item")
                            if _temp_live_item is not None:
                                _temp_canvas.itemconfigure(_temp_live_item, text = weather_temp_text)
                            if _temp_ghost_item is not None:
                                _temp_canvas.itemconfigure(_temp_ghost_item, text = _watch_temperature_ghost_text())
                        elif row_state["weather_temp_label"] and row_state["weather_temp_label"].winfo_exists():
                            row_state["weather_temp_label"].configure(text = weather_temp_text)

                watch_cancel = self.root.after(1000, update_watch_display)
            except Exception:
                logging.exception("Watch display update failed")
                watch_cancel = self.root.after(1000, update_watch_display)

        if watch_rows:
            update_watch_display()

        def poll_temperature_update():

            nonlocal poll_cancel
            try:
                wpn = current_weapon_state["weapon"]
                weapon_id = str(wpn.get("id"))
                current_temp = combat_state.get("barrel_temperatures", {}).get(weapon_id)

                if current_temp is not None and current_temp !=combat_state.get("ambient_temperature", 70):
                    now_ts = time.time()
                    last_used = combat_state.get("weapon_last_used", {}).get(weapon_id)
                    if last_used is None and weapon_id in combat_state.get("barrel_temperatures", {}):

                        assumed_interval = combat_state.get("temp_poll_interval", 15)
                        last_used = now_ts -float(assumed_interval)
                    elapsed = max(0.0, now_ts -last_used)if last_used is not None else 0.0

                    if elapsed >0:
                        ambient = combat_state.get("ambient_temperature", 70)
                        default_k = math.log(2.0)/300.0
                        magic_k = math.log(2.0)/600.0
                        magicsys_local = str(wpn.get("magicsoundsystem")or "").lower()
                        is_magic_local =(str(wpn.get("type")or "").lower()=="magic")or(magicsys_local in("hg", "at", "mg", "rf"))
                        k = magic_k if is_magic_local else default_k
                        try:
                            _ws = combat_state.get("weather", {})
                            _wt = _ws.get("weather", "clear") if isinstance(_ws, dict) else "clear"
                            if _wt in ("rain", "hard_rain", "thunderstorm", "thunder_hard_rain", "snowstorm", "thundersnow") and not combat_state.get("indoors"):
                                k *= 1.5
                        except Exception:
                            logging.exception("Suppressed exception")
                        new_temp = ambient +(current_temp -ambient)*math.exp(-k *elapsed)
                        low = min(ambient, current_temp)
                        high = max(ambient, current_temp)
                        new_temp = min(max(new_temp, low), high)
                        combat_state["barrel_temperatures"][weapon_id]= new_temp
                        combat_state.setdefault("weapon_last_used", {})[weapon_id]= now_ts

                        update_weapon_view()
                        logging.debug(f"Temperature cooled from {current_temp:.2f}°F to {new_temp:.2f}°F")

                        try:
                            cookoff_thresh = float(combat_state.get("cookoff_temp", 1500))
                        except Exception:
                            cookoff_thresh = 1500.0
                        if new_temp >=cookoff_thresh:

                            per_sec_prob = min(0.02, max(0.0, (new_temp -cookoff_thresh)/10000.0))
                            cookoff_prob = 1.0 -((1.0 -per_sec_prob)**max(1.0, elapsed))
                            if random.random()<cookoff_prob:
                                try:

                                    fired = False
                                    if isinstance(wpn, dict)and wpn.get("chambered"):
                                        wpn["chambered"]= None
                                        fired = True
                                    elif isinstance(wpn, dict)and wpn.get("loaded")and isinstance(wpn.get("loaded"), dict)and wpn["loaded"].get("rounds"):
                                        try:
                                            wpn["loaded"]["rounds"].pop(0)
                                            fired = True
                                        except Exception:
                                            fired = False
                                    elif isinstance(wpn, dict)and wpn.get("rounds"):
                                        try:
                                            wpn["rounds"].pop(0)
                                            fired = True
                                        except Exception:
                                            fired = False

                                    if fired:
                                        try:

                                            self._play_firearm_sound(wpn, "fire")
                                        except Exception:
                                            logging.exception("Suppressed exception")

                                        try:
                                            temp_gain = float(wpn.get("temp_gain_per_shot", wpn.get("temp_gain", 7)))
                                        except Exception:
                                            temp_gain = 7.0
                                        if self._check_weapon_suppressed(wpn):
                                            temp_gain *=1.5
                                        new_temp = new_temp +(temp_gain *0.5)
                                        combat_state["barrel_temperatures"][weapon_id]= new_temp
                                        combat_state.setdefault("weapon_last_used", {})[weapon_id]= now_ts
                                        update_weapon_view()
                                        logging.warning("Cook-off occurred for weapon %s at %.1f°F", wpn.get("name", weapon_id), new_temp)
                                except Exception:
                                    logging.exception("Cook-off handling failed")

                poll_cancel = self.root.after(15000, poll_temperature_update)
            except Exception as e:
                logging.debug(f"Temperature polling error: {e}")

                poll_cancel = self.root.after(15000, poll_temperature_update)

        poll_cancel = self.root.after(15000, poll_temperature_update)

        def exit_combat():

            nonlocal poll_cancel, reload_pending_id, watch_cancel
            watch_runtime_active[0] = False

            if poll_cancel:
                try:
                    self.root.after_cancel(poll_cancel)
                except Exception:
                    logging.exception("Suppressed exception")

            try:
                if watch_cancel:
                    try:
                        self.root.after_cancel(watch_cancel)
                    except Exception:
                        logging.exception("Suppressed exception")
                    watch_cancel = None
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if reload_pending_id and reload_pending_id[0]:
                    try:
                        self.root.after_cancel(reload_pending_id[0])
                    except Exception:
                        logging.exception("Suppressed exception")
                    reload_pending_id[0]= None
            except Exception:
                logging.exception("Suppressed exception")

            try:
                for k in("<Left>", "<Right>", "<space>", "r", "R", "b", "B", "n", "N", "g", "G", "a", "A", "p", "P"):
                    try:
                        self.root.unbind(k)
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if weather_sound_state.get("channel"):
                    weather_sound_state["channel"].stop()
                    weather_sound_state["channel"] = None
                self._weather_ambient_channel = None
                if weather_sound_state.get("thunder_after_id"):
                    try:
                        self.root.after_cancel(weather_sound_state["thunder_after_id"]) # type: ignore
                    except Exception:
                        logging.exception("Suppressed exception")
                    weather_sound_state["thunder_after_id"] = None
            except Exception:
                logging.exception("Suppressed exception")

            self._save_combat_state(save_data)

            try:
                prev = current_weapon_state.get('prev_tk_scaling')
                if prev is not None:
                    try:
                        self.root.tk.call('tk', 'scaling', float(prev))
                    except Exception:
                        logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                tbl_addl = globals().get('table_data', {}).get('additional_settings', {})
                combat_reports_enabled = bool(tbl_addl.get('combat_repots')or tbl_addl.get('combat_reports'))
            except Exception:
                combat_reports_enabled = False

            if combat_reports_enabled:
                try:
                    report = self._generate_combat_report_data(save_data)
                    if report and report.get('rounds_fired', 0)>0:
                        self._clear_window()
                        self._build_main_menu()
                        self._show_combat_report_animation(report)
                        return
                except Exception:
                    logging.exception('Failed to generate/show combat report on exit')

            self._clear_window()
            self._build_main_menu()

        self._create_sound_button(
        main_frame,
        text = "Exit Combat Mode",
        command = exit_combat,
        fg_color = "#8B0000",
        hover_color = "#A52A2A",
        height = 50,
        font = customtkinter.CTkFont(size = 14)
        ).pack(pady = 10)

        try:

            main_frame.update_idletasks()
            req_w = main_frame.winfo_reqwidth()or 1
            req_h = main_frame.winfo_reqheight()or 1
            sw = self.root.winfo_screenwidth()or 1
            sh = self.root.winfo_screenheight()or 1
            margin = 40
            if req_w +margin >sw or req_h +margin >sh:
                scale_w = float(sw -margin)/float(req_w)
                scale_h = float(sh -margin)/float(req_h)
                new_scale = min(scale_w, scale_h, 1.0)

                new_scale = max(new_scale, 0.6)
                try:
                    prev_scale = float(self.root.tk.call('tk', 'scaling'))
                except Exception:
                    prev_scale = 1.0

                try:
                    current_weapon_state['prev_tk_scaling']= prev_scale
                except Exception:
                    logging.exception("Suppressed exception")
                try:
                    self.root.tk.call('tk', 'scaling', new_scale)
                    main_frame.update_idletasks()
                except Exception:
                    logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Suppressed exception")
