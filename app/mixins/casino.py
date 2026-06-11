"""CasinoMixin — App methods for the "casino" feature area."""
from app.foundation import *


class CasinoMixin:

    def _play_card_sound(self, sound_name):
        try:
            base_dir = os.path.dirname(__file__)
            sound_path = os.path.join(base_dir, "sounds", "misc", "cards", f"{sound_name}.ogg")
            if os.path.exists(sound_path):
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
        except Exception as e:
            logging.debug(f"Failed to play card sound {sound_name}: {e}")

    def _load_card_image(self, suit, value, size =(80, 112)):
        try:
            if not hasattr(self, '_card_image_cache'):
                self._card_image_cache = {}

            cache_key =(suit, value, size)
            if cache_key in self._card_image_cache:
                return self._card_image_cache[cache_key]

            base_dir = os.path.dirname(__file__)
            if suit is None and value =="back":
                img_path = os.path.join(base_dir, "images", "cards", "back.png")
            else:
                img_path = os.path.join(base_dir, "images", "cards", suit, f"{value}.png")

            if os.path.exists(img_path):
                from PIL import Image
                img = Image.open(img_path)
                img = img.resize(size, Image.Resampling.LANCZOS)
                ctk_img = customtkinter.CTkImage(light_image = img, dark_image = img, size = size)
                self._card_image_cache[cache_key]= ctk_img
                return ctk_img
            else:
                logging.warning(f"Card image not found: {img_path}")
        except Exception as e:
            logging.warning(f"Failed to load card image {suit}/{value}: {e}")
        return None

    def _normalize_casino_game_key(self, game_name):
        try:
            return str(game_name or "").strip().lower().replace("_", "-").replace(" ", "-")
        except Exception:
            return ""

    def _get_casino_house_edge_fraction(self, store, game_key):
        try:
            edge_cfg = (store or {}).get("house_edge")
            edge_pct = 0.0
            if isinstance(edge_cfg, dict):
                normalized_target = self._normalize_casino_game_key(game_key)
                for raw_key, raw_value in edge_cfg.items():
                    if self._normalize_casino_game_key(raw_key) == normalized_target:
                        try:
                            edge_pct = float(raw_value)
                        except Exception:
                            edge_pct = 0.0
                        break
            elif isinstance(edge_cfg, (int, float)):
                edge_pct = float(edge_cfg)

            edge_pct = max(0.0, min(100.0, edge_pct))
            return edge_pct / 100.0
        except Exception:
            return 0.0

    def _apply_casino_house_edge(self, store, game_key, winnings):
        try:
            amount = int(winnings)
        except Exception:
            return winnings

        if amount <= 0:
            return amount

        edge = self._get_casino_house_edge_fraction(store, game_key)
        adjusted = int(round(amount * (1.0 - edge)))
        return max(0, adjusted)

    def _get_casino_ban_until_next_noon(self):
        now = datetime.now()
        tomorrow = now + timedelta(days = 1)
        return tomorrow.replace(hour = 12, minute = 0, second = 0, microsecond = 0)

    def _open_casino_interface(self, store, table_data):
        logging.info(f"Opening casino: {store.get('name')}")

        music_channel = None
        if store.get("music")and store.get("playlist"):
            requested_playlists = store.get("playlist")
            if isinstance(requested_playlists, str):
                requested_playlists = [requested_playlists]

            current_music = getattr(self, "_current_business_music", None)
            current_playlists = []
            try:
                if isinstance(current_music, dict):
                    cp = current_music.get("playlist")
                    if isinstance(cp, str):
                        current_playlists = [cp]
                    elif isinstance(cp, (list, tuple, set)):
                        current_playlists = list(cp)
            except Exception:
                current_playlists = []

            same_playlist = set(str(p) for p in (requested_playlists or [])) == set(str(p) for p in (current_playlists or []))
            if same_playlist and pygame.mixer.music.get_busy():
                music_channel = current_music
                self._apply_business_music_volume()
            else:
                music_channel = self._start_business_music(requested_playlists, first_play = True)

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = store.get("name", "Casino"), font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        shopkeeper_label = customtkinter.CTkLabel(header_frame, text = f"Proprietor: {store.get('shopkeeper', 'Unknown')}", font = customtkinter.CTkFont(size = 14), text_color = "gray")
        shopkeeper_label.pack()

        marquee_label = None
        marquee_job:list[object]=[None]

        def _get_track_info(track_path):
            artist = None
            title = None
            length = None
            try:
                try:
                    sound = pygame.mixer.Sound(track_path)
                    length = float(sound.get_length())
                except Exception:
                    length = None
                try:
                    from mutagen._file import File as MutagenFile
                    mf = MutagenFile(track_path)
                    if mf is not None:
                        tags = getattr(mf, 'tags', {})or {}
                        def _get_tag(keys):
                            for k in keys:
                                v = tags.get(k)
                                if v:
                                    try:
                                        if isinstance(v, (list, tuple)):
                                            return str(v[0])
                                        return str(v)
                                    except Exception:
                                        return str(v)
                            return None
                        artist = _get_tag(["artist", "ARTIST", "TPE1", "IART"])
                        title = _get_tag(["title", "TITLE", "TIT2", "INAM"])
                except Exception:
                    pass
            except Exception:
                pass
            if not title:
                try:
                    title = os.path.basename(track_path or "")
                except Exception:
                    title = "Unknown"
            return {"artist":artist, "title":title, "length":length}

        def stop_ui_music():
            try:
                if marquee_job[0]:
                    try:
                        self.root.after_cancel(marquee_job[0])# type: ignore[arg-type]
                    except Exception:
                        pass
                    marquee_job[0]= None
            except Exception:
                pass
            try:
                self._stop_business_music(music_channel)
            except Exception:
                pass

        if music_channel and music_channel.get("track"):
            try:
                track_path = music_channel.get("track")
                info = _get_track_info(track_path)
                base_artist = info.get("artist")or ""
                base_title = info.get("title")or os.path.basename(track_path or "")
                track_len = info.get("length")or 0.0

                marquee_frame = customtkinter.CTkFrame(header_frame, fg_color = "black")

                marquee_frame.pack(pady =(6, 0))
                try:
                    marquee_frame.configure(width = 500)

                    try:
                        marquee_frame.pack_propagate(False)
                    except Exception:
                        pass
                except Exception:
                    pass
                try:

                    label_font = None
                    try:
                        import ctypes
                        import tkinter.font as tkfont
                        fp = os.path.join(os.path.dirname(__file__), "fonts", "Tims_8x5_LCD_Matrix.ttf")
                        if os.path.exists(fp)and hasattr(ctypes, 'windll'):
                            try:
                                FR_PRIVATE = 0x10
                                ctypes.windll.gdi32.AddFontResourceExW(fp, FR_PRIVATE, 0)
                            except Exception:
                                pass

                            try:
                                self.root.update_idletasks()
                                fams = list(tkfont.families())
                                for f in fams:
                                    if any(x in f.lower()for x in("tims", "8x5", "lcd")):
                                        label_font = customtkinter.CTkFont(size = 12, family = f)
                                        break
                            except Exception:
                                pass
                    except Exception:
                        pass
                    if not label_font:
                        label_font = customtkinter.CTkFont(size = 12)
                except Exception:
                    label_font = customtkinter.CTkFont(size = 12)
                marquee_label = customtkinter.CTkLabel(marquee_frame, text = "", anchor = "w", font = label_font, width = 480, height = 26, text_color = "#7CFC00")
                marquee_label.pack(anchor = "center", padx = 4)
                try:
                    marquee_debug_label = customtkinter.CTkLabel(marquee_frame, text = "", anchor = "w", font = customtkinter.CTkFont(size = 9), text_color = "white")
                    marquee_debug_label.pack(anchor = "center", padx = 4, pady =(2, 0))
                except Exception:
                    marquee_debug_label = None
                try:
                    self.root.update_idletasks()
                    lh = marquee_label.winfo_reqheight()or marquee_label.winfo_height()
                    if lh:
                        try:
                            marquee_frame.configure(height = lh)
                        except Exception:
                            pass
                except Exception:
                    pass

                pos =[0]
                prev_track =[music_channel.get('track')if(music_channel and music_channel.get('track'))else None]

                def _fmt_time(s):
                    try:
                        s = max(0, int(s))
                        return f"{s //60}:{s %60:02d}"
                    except Exception:
                        return "0:00"

                def _update_marquee():
                    try:

                        current = getattr(self, "_current_business_music", music_channel)
                        meta_info = None
                        if current:
                            meta_info = current.get("_meta")

                        try:
                            track_path =(current or {}).get('track')
                            if track_path !=prev_track[0]:
                                prev_track[0]= track_path
                                pos[0]= 0
                        except Exception:
                            track_path =(current or {}).get('track')

                        try:
                            if marquee_debug_label is not None:
                                dbg = f"meta={bool(meta_info)} id={id(current)}"
                                try:

                                    tt =(meta_info or {}).get('title')if meta_info else((current or {}).get('track')or '')
                                    if tt:
                                        dbg +=f" title={tt[:30]}"
                                except Exception:
                                    pass
                                marquee_debug_label.configure(text = dbg)
                        except Exception:
                            pass

                        if meta_info:
                            base_artist = meta_info.get("artist")or ""
                            base_title = meta_info.get("title")or os.path.basename(track_path or "")
                            total = meta_info.get("length")or 0.0
                        else:

                            base_artist = ""
                            base_title = os.path.basename(track_path or "")
                            total = 0.0
                            try:
                                if current and not current.get("_meta_loading"):
                                    current["_meta_loading"]= True
                                    def _bg_load():
                                        try:
                                            info = _get_track_info((current or {}).get("track"))
                                            def _apply():
                                                try:
                                                    try:
                                                        target = getattr(self, "_current_business_music", None)
                                                        if target is None:
                                                            target = current
                                                        if target is not None:
                                                                target.update({"_meta":info})
                                                                try:
                                                                    self.root.after(0, _update_marquee)
                                                                except Exception:
                                                                    pass
                                                    except Exception:
                                                        pass
                                                except Exception:
                                                    pass
                                            self.root.after(0, _apply)
                                        except Exception:
                                            pass
                                        finally:
                                            try:
                                                current.pop("_meta_loading", None)
                                            except Exception:
                                                pass
                                    import threading
                                    threading.Thread(target = _bg_load, daemon = True).start()
                            except Exception:
                                pass

                        started =(current or {}).get("started_at")or time.time()
                        start_offset =(current or {}).get("start_pos")or 0.0
                        elapsed =(time.time()-started)+float(start_offset)

                        elapsed_display = _fmt_time(elapsed)
                        total_fmt = _fmt_time(total)

                        meta = f"{base_artist} | {base_title} | {elapsed_display}/{total_fmt}"if(base_artist or base_title)else os.path.basename(track_path or "")

                        try:
                            self.root.update_idletasks()
                            label_px = marquee_label.winfo_width()or int(marquee_label.cget("width")or 480)
                        except Exception:
                            label_px = int(marquee_label.cget("width")or 480)

                        avg_char_px = 8
                        visible_chars = max(8, int(label_px /max(1, avg_char_px)))

                        scrollfull = " "+meta +" "
                        if len(scrollfull)<visible_chars:
                            scrollfull = scrollfull +(" "*(visible_chars -len(scrollfull)+2))

                        doubled =(scrollfull *3)
                        display = doubled[pos[0]:pos[0]+visible_chars]
                        marquee_label.configure(text = display)
                        pos[0]=(pos[0]+1)%max(1, len(scrollfull))
                        try:

                            len_scroll = max(1, len(scrollfull))
                            delay_ms = int(min(500, max(60, 80 +(len_scroll *4))))
                        except Exception:
                            delay_ms = 220
                        marquee_job[0]= self.root.after(delay_ms, _update_marquee)
                    except Exception:
                        try:
                            marquee_label.configure(text = os.path.basename((getattr(self, "_current_business_music", music_channel)or {}).get("track")or ""))
                        except Exception:
                            pass

                try:
                    import threading
                    def _load_meta():
                        try:
                            cur = getattr(self, "_current_business_music", music_channel)
                            if not cur:
                                return
                            info = _get_track_info(cur.get("track"))
                            def _apply():
                                try:

                                    cur.update({"_meta":info})
                                except Exception:
                                    pass
                            self.root.after(0, _apply)
                        except Exception:
                            pass
                    try:
                        import threading
                        threading.Thread(target = _load_meta, daemon = True).start()
                    except Exception:
                        pass
                except Exception:
                    pass

                _update_marquee()
            except Exception:
                pass

        save_path = os.path.join(saves_folder or "", (self.currentsave or "")+".sldsv")
        save_data = self._load_file((self.currentsave or "")+".sldsv")
        if save_data is None:
            self._popup_show_info("Error", "Failed to load character data.", sound = "error")
            try:
                stop_ui_music()
            except Exception:
                pass
            return

        player_money =[save_data.get("money", 0)]
        casino_name = store.get("name", "Unknown Casino")

        if "casino_stats"not in save_data:
            save_data["casino_stats"]= {}
        if casino_name not in save_data["casino_stats"]:
            save_data["casino_stats"][casino_name]= {
            "wins":0,
            "losses":0,
            "games_played":0,
            "net_profit":0,
            "profit_period_key":"",
            "profit_period":0,
            "ban_until":None
            }
        casino_stats =[save_data["casino_stats"][casino_name]]

        profit_limit = 0
        try:
            profit_limit = int(store.get("profit_limit", 0) or 0)
        except Exception:
            profit_limit = 0

        current_profit_key = _get_market_day_key()
        try:
            if casino_stats[0].get("profit_period_key") != current_profit_key:
                casino_stats[0]["profit_period_key"] = current_profit_key
                casino_stats[0]["profit_period"] = 0
        except Exception:
            casino_stats[0]["profit_period_key"] = current_profit_key
            casino_stats[0]["profit_period"] = 0

        def get_active_ban_until():
            try:
                ban_iso = casino_stats[0].get("ban_until")
                if not ban_iso:
                    return None
                ban_until = datetime.fromisoformat(str(ban_iso))
                if datetime.now() < ban_until:
                    return ban_until
                casino_stats[0]["ban_until"] = None
                return None
            except Exception:
                casino_stats[0]["ban_until"] = None
                return None

        active_ban_until = get_active_ban_until()
        if active_ban_until is not None:
            try:
                self._write_save_to_path(save_path, save_data)
            except Exception:
                pass
            self._popup_show_info(
                "Casino Ban",
                f"You have reached this casino's profit limit and are banned until {active_ban_until.strftime('%Y-%m-%d %I:%M %p')}.",
                sound = "error"
            )
            try:
                stop_ui_music()
            except Exception:
                pass
            self._clear_window()
            self._open_business_tool()
            return

        money_label = customtkinter.CTkLabel(header_frame, text = f"Your Money: {format_price(player_money[0])}", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = 5)

        stats_frame = customtkinter.CTkFrame(header_frame, fg_color = "transparent")
        stats_frame.pack(pady = 5)

        stats = casino_stats[0]
        net_color = "green"if stats["net_profit"]>=0 else "red"
        net_prefix = "+$"if stats["net_profit"]>=0 else "-$"
        net_display = f"{net_prefix}{abs(stats['net_profit'])}"

        stats_label = customtkinter.CTkLabel(
        stats_frame,
        text = f"Lifetime: {stats['wins']}W / {stats['losses']}L({stats['games_played']} games) | Net: {net_display}",
        font = customtkinter.CTkFont(size = 12),
        text_color = "gray"
        )
        stats_label.pack()

        def update_stats_display():
            try:
                s = casino_stats[0]
                nc = "green"if s["net_profit"]>=0 else "red"
                np = "+$"if s["net_profit"]>=0 else "-$"
                nd = f"{np}{abs(s['net_profit'])}"
                if profit_limit > 0:
                    period_profit = int(s.get("profit_period", 0) or 0)
                    stats_label.configure(text = f"Lifetime: {s['wins']}W / {s['losses']}L({s['games_played']} games) | Net: {nd} | Profit Window: {format_price(period_profit)}/{format_price(profit_limit)}")
                else:
                    stats_label.configure(text = f"Lifetime: {s['wins']}W / {s['losses']}L({s['games_played']} games) | Net: {nd}")
            except Exception:
                pass

        min_bet = store.get("min_bet", 10)
        max_bet = store.get("max_bet", 1000)

        def update_money_display():
            try:
                money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
            except Exception:
                pass

        def save_money():
            try:
                save_data["money"]= player_money[0]
                save_data["casino_stats"][casino_name]= casino_stats[0]
                self._write_save_to_path(save_path, save_data)
            except Exception as e:
                logging.error(f"Failed to save money: {e}")

        def record_game_result(winnings):
            casino_stats[0]["games_played"]+=1
            casino_stats[0]["net_profit"]+=winnings
            if winnings >0:
                casino_stats[0]["wins"]+=1
            elif winnings <0:
                casino_stats[0]["losses"]+=1

            if winnings > 0 and profit_limit > 0:
                try:
                    period_key = _get_market_day_key()
                    if casino_stats[0].get("profit_period_key") != period_key:
                        casino_stats[0]["profit_period_key"] = period_key
                        casino_stats[0]["profit_period"] = 0
                    casino_stats[0]["profit_period"] = int(casino_stats[0].get("profit_period", 0) or 0) + int(winnings)

                    if int(casino_stats[0].get("profit_period", 0) or 0) >= profit_limit:
                        ban_until = self._get_casino_ban_until_next_noon()
                        casino_stats[0]["ban_until"] = ban_until.isoformat()
                        self.root.after(
                            100,
                            lambda: self._popup_show_info(
                                "Casino Ban",
                                f"You reached the profit limit of {format_price(profit_limit)} and are banned from this casino until {ban_until.strftime('%Y-%m-%d %I:%M %p')}.",
                                sound = "error"
                            )
                        )
                except Exception:
                    pass

            update_stats_display()

        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)
        content_frame.grid_columnconfigure(0, weight = 1)
        content_frame.grid_rowconfigure(0, weight = 1)

        games_frame = customtkinter.CTkFrame(content_frame)
        games_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

        games_label = customtkinter.CTkLabel(games_frame, text = "Choose a Game", font = customtkinter.CTkFont(size = 18, weight = "bold"))
        games_label.pack(pady = 20)

        available_games = store.get("games", ["Blackjack"])

        def open_blackjack():
            self._open_blackjack_game(store, player_money, update_money_display, save_money, min_bet, max_bet, music_channel, table_data, record_game_result, casino_stats, save_data = save_data, save_path = save_path)

        def open_poker():
            self._open_poker_game(store, player_money, update_money_display, save_money, min_bet, max_bet, music_channel, table_data, record_game_result, casino_stats, save_data = save_data, save_path = save_path)

        def open_highlow():
            self._open_highlow_game(store, player_money, update_money_display, save_money, min_bet, max_bet, music_channel, table_data, record_game_result, casino_stats, save_data = save_data, save_path = save_path)

        def open_roulette():
            self._open_roulette_game(store, player_money, update_money_display, save_money, min_bet, max_bet, music_channel, table_data, record_game_result, casino_stats, save_data = save_data, save_path = save_path)

        def open_poker_lobby():
            self._open_poker_lobby(store, player_money, update_money_display, save_money, min_bet, max_bet, music_channel, table_data, record_game_result, casino_stats, save_data = save_data, save_path = save_path)

        def open_game_if_not_banned(opener):
            active_ban = get_active_ban_until()
            if active_ban is not None:
                self._popup_show_info(
                    "Casino Ban",
                    f"You are banned from this casino until {active_ban.strftime('%Y-%m-%d %I:%M %p')}.",
                    sound = "error"
                )
                return
            opener()

        if "Blackjack"in available_games:
            blackjack_btn = self._create_sound_button(games_frame, "Blackjack", lambda: open_game_if_not_banned(open_blackjack), width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
            blackjack_btn.pack(pady = 10)

        if "Poker"in available_games:
            poker_btn = self._create_sound_button(games_frame, "Poker", lambda: open_game_if_not_banned(open_poker_lobby), width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
            poker_btn.pack(pady = 10)

        if "High-Low"in available_games:
            highlow_btn = self._create_sound_button(games_frame, "High-Low", lambda: open_game_if_not_banned(open_highlow), width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
            highlow_btn.pack(pady = 10)

        if "Roulette"in available_games:
            roulette_btn = self._create_sound_button(games_frame, "Roulette", lambda: open_game_if_not_banned(open_roulette), width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
            roulette_btn.pack(pady = 10)

        def leave_casino():
            try:
                stop_ui_music()
            except Exception:
                pass
            save_money()
            self._clear_window()
            self._open_business_tool()

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        back_btn = self._create_sound_button(button_frame, "Leave Casino", leave_casino, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(pady = 10)

    def _open_blackjack_game(self, store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb = None, casino_stats = None, save_data = None, save_path = None):
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = "Blackjack", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        money_label = customtkinter.CTkLabel(header_frame, text = f"Your Money: {format_price(player_money[0])}", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = 5)

        bet_label = customtkinter.CTkLabel(header_frame, text = f"Bet Range: {format_price(min_bet)} - {format_price(max_bet)}", font = customtkinter.CTkFont(size = 12), text_color = "orange")
        bet_label.pack()

        game_frame = customtkinter.CTkFrame(main_frame)
        game_frame.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)
        game_frame.grid_columnconfigure(0, weight = 1)

        suits =["clubs", "diamonds", "hearts", "spades"]
        values =["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]

        deck =[{"suit":s, "value":v}for s in suits for v in values]
        game_state = {
        "deck":[],
        "player_hand":[],
        "dealer_hand":[],
        "current_bet":0,
        "game_active":False,
        "player_turn":False,
        "result":None,
        "ui_active":True
        }

        wagered_items =[]
        item_bet_value =[0]

        dealer_frame = customtkinter.CTkFrame(game_frame, fg_color = "transparent")
        dealer_frame.pack(pady = 10)
        dealer_label = customtkinter.CTkLabel(dealer_frame, text = "Dealer's Hand", font = customtkinter.CTkFont(size = 14, weight = "bold"))
        dealer_label.pack()
        dealer_cards_frame = customtkinter.CTkFrame(dealer_frame, fg_color = "transparent")
        dealer_cards_frame.pack(pady = 5)
        dealer_score_label = customtkinter.CTkLabel(dealer_frame, text = "", font = customtkinter.CTkFont(size = 12))
        dealer_score_label.pack()

        player_frame = customtkinter.CTkFrame(game_frame, fg_color = "transparent")
        player_frame.pack(pady = 10)
        player_label = customtkinter.CTkLabel(player_frame, text = "Your Hand", font = customtkinter.CTkFont(size = 14, weight = "bold"))
        player_label.pack()
        player_cards_frame = customtkinter.CTkFrame(player_frame, fg_color = "transparent")
        player_cards_frame.pack(pady = 5)
        player_score_label = customtkinter.CTkLabel(player_frame, text = "", font = customtkinter.CTkFont(size = 12))
        player_score_label.pack()

        result_label = customtkinter.CTkLabel(game_frame, text = "", font = customtkinter.CTkFont(size = 18, weight = "bold"))
        result_label.pack(pady = 10)

        def get_card_value(card):
            v = card["value"]
            if v in["jack", "queen", "king"]:
                return 10
            elif v =="ace":
                return 11
            else:
                return int(v)

        def calculate_hand(hand):
            total = sum(get_card_value(c)for c in hand)
            aces = sum(1 for c in hand if c["value"]=="ace")
            while total >21 and aces >0:
                total -=10
                aces -=1
            return total

        def shuffle_deck():
            game_state["deck"]= deck.copy()
            random.shuffle(game_state["deck"])
            self._play_card_sound("shuffle")

        def draw_card():
            if not game_state["deck"]:
                shuffle_deck()
            card = game_state["deck"].pop()
            self._play_card_sound("flip")
            return card

        def display_card(frame, card, hidden = False):
            if hidden:
                img = self._load_card_image(None, "back")
            else:
                img = self._load_card_image(card["suit"], card["value"])

            if img:
                card_label = customtkinter.CTkLabel(frame, image = img, text = "")
                card_label.image = img
                card_label.pack(side = "left", padx = 2)
            else:
                text = "??"if hidden else f"{card['value'][0].upper()}{card['suit'][0].upper()}"
                card_label = customtkinter.CTkLabel(frame, text = text, width = 60, height = 84, fg_color = "white", text_color = "black", corner_radius = 5)
                card_label.pack(side = "left", padx = 2)

        def clear_cards(frame):
            for widget in frame.winfo_children():
                widget.destroy()

        def place_card_back(frame):
            img = self._load_card_image(None, "back")
            if img:
                card_label = customtkinter.CTkLabel(frame, image = img, text = "")
                card_label.image = img
                card_label.pack(side = "left", padx = 2)
            else:
                card_label = customtkinter.CTkLabel(frame, text = "??", width = 60, height = 84, fg_color = "white", text_color = "black", corner_radius = 5)
                card_label.pack(side = "left", padx = 2)
            return card_label

        def place_card_face_up(frame, card):
            img = self._load_card_image(card["suit"], card["value"])
            if img:
                card_label = customtkinter.CTkLabel(frame, image = img, text = "")
                card_label.image = img
                card_label.pack(side = "left", padx = 2)
            else:
                text = f"{card['value'][0].upper()}{card['suit'][0].upper()}"
                card_label = customtkinter.CTkLabel(frame, text = text, width = 60, height = 84, fg_color = "white", text_color = "black", corner_radius = 5)
                card_label.pack(side = "left", padx = 2)
            return card_label

        def flip_card_label(card_label, card):
            img = self._load_card_image(card["suit"], card["value"])
            if img:
                card_label.configure(image = img)
                card_label.image = img
            else:
                card_label.configure(text = f"{card['value'][0].upper()}{card['suit'][0].upper()}")

        def update_display(reveal_dealer = False):
            clear_cards(dealer_cards_frame)
            clear_cards(player_cards_frame)

            for i, card in enumerate(game_state["dealer_hand"]):
                if i ==0 and not reveal_dealer and game_state["player_turn"]:
                    display_card(dealer_cards_frame, card, hidden = True)
                else:
                    display_card(dealer_cards_frame, card)

            for card in game_state["player_hand"]:
                display_card(player_cards_frame, card)

            player_total = calculate_hand(game_state["player_hand"])
            player_score_label.configure(text = f"Score: {player_total}")

            if reveal_dealer or not game_state["player_turn"]:
                dealer_total = calculate_hand(game_state["dealer_hand"])
                dealer_score_label.configure(text = f"Score: {dealer_total}")
            else:
                visible_card = game_state["dealer_hand"][1]if len(game_state["dealer_hand"])>1 else None
                if visible_card:
                    dealer_score_label.configure(text = f"Showing: {get_card_value(visible_card)}")
                else:
                    dealer_score_label.configure(text = "")

            money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
            update_money_cb()

        def end_game(result_text, winnings):
            if not game_state.get("ui_active", False):
                return
            if winnings > 0:
                winnings = self._apply_casino_house_edge(store, "blackjack", winnings)
            game_state["game_active"]= False
            game_state["player_turn"]= False
            game_state["result"]= result_text

            player_money[0]+=winnings
            if record_game_cb:
                record_game_cb(winnings)

            item_lost = False
            if winnings <0 and wagered_items:
                self._process_item_bet_loss(save_data, save_path, wagered_items)
                item_names =[e["item"].get("name", "Unknown")for e in wagered_items]
                item_lost = True
            elif winnings >0 and wagered_items:
                player_money[0]+=item_bet_value[0]

            save_money_cb()

            try:
                color = "green"if winnings >0 else("red"if winnings <0 else "orange")
                item_suffix = ""
                if item_lost:
                    item_suffix = f" | Lost {len(wagered_items)} item(s)"
                elif winnings >0 and item_bet_value[0]>0:
                    item_suffix = f" | +{format_price(item_bet_value[0])} from items"

                if winnings >0:
                    total_display = winnings +(item_bet_value[0]if wagered_items else 0)
                    result_label.configure(text = f"{result_text}(+{format_price(total_display)}){item_suffix}", text_color = color)
                elif winnings <0:
                    result_label.configure(text = f"{result_text}(-{format_price(abs(winnings))}){item_suffix}", text_color = color)
                else:
                    result_label.configure(text = result_text, text_color = color)

                wagered_items.clear()
                item_bet_value[0]= 0
                try:
                    item_wager_label.configure(text = "Items Wagered: None")
                except Exception:
                    pass

                update_display(reveal_dealer = True)
                update_buttons()
            except Exception:
                pass

        def dealer_turn():
            if not game_state.get("ui_active", False):
                return

            dealer_children = dealer_cards_frame.winfo_children()
            if dealer_children:
                first_label = dealer_children[0]
                self._play_card_sound("flip")
                flip_card_label(first_label, game_state["dealer_hand"][0])

            dealer_total = calculate_hand(game_state["dealer_hand"])
            dealer_score_label.configure(text = f"Score: {dealer_total}")

            def dealer_draw():
                nonlocal dealer_total
                if not game_state.get("ui_active", False):
                    return
                if dealer_total <17:
                    if not game_state["deck"]:
                        shuffle_deck()
                    card = game_state["deck"].pop()
                    game_state["dealer_hand"].append(card)
                    dealer_total = calculate_hand(game_state["dealer_hand"])

                    try:
                        self._play_card_sound("place")
                        place_card_face_up(dealer_cards_frame, card)
                        dealer_score_label.configure(text = f"Score: {dealer_total}")
                    except Exception:
                        return

                    self.root.after(600, dealer_draw)
                else:
                    player_total = calculate_hand(game_state["player_hand"])
                    bet = game_state["current_bet"]

                    if dealer_total >21:
                        end_game("Dealer Busts! You Win!", bet)
                    elif dealer_total >player_total:
                        end_game("Dealer Wins!", -bet)
                    elif player_total >dealer_total:
                        end_game("You Win!", bet)
                    else:
                        end_game("Push! It's a Tie!", 0)

            self.root.after(500, dealer_draw)

        def hit():
            if not game_state["player_turn"]:
                return

            if not game_state["deck"]:
                shuffle_deck()
            card = game_state["deck"].pop()
            game_state["player_hand"].append(card)

            self._play_card_sound("place")
            place_card_face_up(player_cards_frame, card)
            player_total = calculate_hand(game_state["player_hand"])
            player_score_label.configure(text = f"Score: {player_total}")
            if player_total >21:
                end_game("Bust! You Lose!", -game_state["current_bet"])

        def stand():
            if not game_state["player_turn"]:
                return
            game_state["player_turn"]= False
            update_buttons()
            dealer_turn()

        def double_down():
            if not game_state["player_turn"]or len(game_state["player_hand"])!=2:
                return
            if player_money[0]<game_state["current_bet"]:
                self._popup_show_info("Insufficient Funds", "You don't have enough money to double down.", sound = "error")
                return

            game_state["current_bet"]*=2

            if not game_state["deck"]:
                shuffle_deck()
            card = game_state["deck"].pop()
            game_state["player_hand"].append(card)

            self._play_card_sound("place")
            place_card_face_up(player_cards_frame, card)
            player_total = calculate_hand(game_state["player_hand"])
            player_score_label.configure(text = f"Score: {player_total}")
            if player_total >21:
                end_game("Bust! You Lose!", -game_state["current_bet"])
            else:
                game_state["player_turn"]= False
                update_buttons()
                dealer_turn()

        def start_new_game():
            bet_str = bet_entry.get()
            try:
                bet = parse_display_price_to_usd(bet_str, round_to_int = True)
            except ValueError:
                self._popup_show_info("Invalid Bet", "Please enter a valid money amount.", sound = "error")
                return

            if bet <min_bet or bet >max_bet:
                self._popup_show_info("Invalid Bet", f"Bet must be between {format_price(min_bet)} and {format_price(max_bet)}.", sound = "error")
                return

            if bet >player_money[0]:
                self._popup_show_info("Insufficient Funds", "You don't have enough money for that bet.", sound = "error")
                return

            game_state["current_bet"]= bet
            result_label.configure(text = "")

            shuffle_deck()
            game_state["player_hand"]=[]
            game_state["dealer_hand"]=[]

            clear_cards(dealer_cards_frame)
            clear_cards(player_cards_frame)
            player_score_label.configure(text = "")
            dealer_score_label.configure(text = "")

            deal_btn.configure(state = "disabled")
            hit_btn.configure(state = "disabled")
            stand_btn.configure(state = "disabled")
            double_btn.configure(state = "disabled")

            drawn_cards =[]
            for _ in range(4):
                if not game_state["deck"]:
                    shuffle_deck()
                drawn_cards.append(game_state["deck"].pop())

            deal_plan =[
            (player_cards_frame, drawn_cards[0], "player", True),
            (dealer_cards_frame, drawn_cards[1], "dealer", False),
            (player_cards_frame, drawn_cards[2], "player", True),
            (dealer_cards_frame, drawn_cards[3], "dealer", True),
            ]

            def animate_deal(step = 0):
                if not game_state.get("ui_active", False):
                    return
                if step >=len(deal_plan):
                    game_state["game_active"]= True
                    game_state["player_turn"]= True
                    game_state["result"]= None

                    player_total = calculate_hand(game_state["player_hand"])
                    player_score_label.configure(text = f"Score: {player_total}")
                    visible_card = game_state["dealer_hand"][1]if len(game_state["dealer_hand"])>1 else None
                    if visible_card:
                        dealer_score_label.configure(text = f"Showing: {get_card_value(visible_card)}")
                    money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
                    update_money_cb()
                    update_buttons()

                    if player_total ==21 and calculate_hand(game_state["dealer_hand"])==21:
                        end_game("Both Blackjack! Push!", 0)
                    elif player_total ==21:
                        end_game("Blackjack! You Win!", int(bet *1.5))
                    return

                frame, card, target, face_up = deal_plan[step]

                if target =="player":
                    game_state["player_hand"].append(card)
                else:
                    game_state["dealer_hand"].append(card)

                self._play_card_sound("place")
                if face_up:
                    place_card_face_up(frame, card)
                else:
                    place_card_back(frame)

                self.root.after(400, lambda:animate_deal(step +1))

            animate_deal(0)

        def update_buttons():
            if game_state["player_turn"]:
                hit_btn.configure(state = "normal")
                stand_btn.configure(state = "normal")
                double_btn.configure(state = "normal"if len(game_state["player_hand"])==2 and player_money[0]>=game_state["current_bet"]else "disabled")
                deal_btn.configure(state = "disabled")
            else:
                hit_btn.configure(state = "disabled")
                stand_btn.configure(state = "disabled")
                double_btn.configure(state = "disabled")
                deal_btn.configure(state = "normal")

        controls_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        controls_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        bet_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        bet_frame.pack(pady = 5)

        bet_label_entry = customtkinter.CTkLabel(bet_frame, text = "Bet Amount:", font = customtkinter.CTkFont(size = 14))
        bet_label_entry.pack(side = "left")

        bet_entry = customtkinter.CTkEntry(bet_frame, width = 140, placeholder_text = format_price(min_bet))
        bet_entry.pack(side = "left", padx = 5)
        bet_entry.insert(0, format_price(min_bet))

        if save_data and save_path:
            item_wager_label = customtkinter.CTkLabel(bet_frame, text = "Items Wagered: None", font = customtkinter.CTkFont(size = 11), text_color = "gray")
            item_wager_label.pack(side = "left", padx = 10)

            def update_item_wager_display():
                total = sum(int(e["item"].get("value", 0))for e in wagered_items)
                item_bet_value[0]= total
                if wagered_items:
                    item_wager_label.configure(text = f"Items Wagered: {len(wagered_items)}({format_price(total)})", text_color = "gold")
                else:
                    item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")

            def open_item_wager():
                if game_state["game_active"]:
                    self._popup_show_info("Game Active", "Cannot change item wager during a game.", sound = "popup")
                    return
                self._open_item_bet_dialog(save_data, wagered_items, update_item_wager_display)

            wager_btn = self._create_sound_button(bet_frame, "Wager Items", open_item_wager, width = 110, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = "#8B4513", hover_color = "#654321")
            wager_btn.pack(side = "left", padx = 5)

        action_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        action_frame.pack(pady = 10)

        deal_btn = self._create_sound_button(action_frame, "Deal", start_new_game, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
        deal_btn.pack(side = "left", padx = 5)

        hit_btn = self._create_sound_button(action_frame, "Hit", hit, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
        hit_btn.pack(side = "left", padx = 5)
        hit_btn.configure(state = "disabled")

        stand_btn = self._create_sound_button(action_frame, "Stand", stand, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
        stand_btn.pack(side = "left", padx = 5)
        stand_btn.configure(state = "disabled")

        double_btn = self._create_sound_button(action_frame, "Double", double_down, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
        double_btn.pack(side = "left", padx = 5)
        double_btn.configure(state = "disabled")

        def back_to_casino():
            game_state["ui_active"]= False
            self._open_casino_interface(store, table_data)

        back_btn = self._create_sound_button(controls_frame, "Back to Casino", back_to_casino, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(pady = 10)

    def _open_poker_game(self, store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb = None, casino_stats = None, variant = "five_card_draw", save_data = None, save_path = None):
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        variant_names = {
        "five_card_draw":"5 Card Draw",
        "five_card_stud":"5 Card Stud",
        "seven_card_stud":"7 Card Stud",
        "texas_holdem":"Texas Hold'em"
        }

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = f"Poker - {variant_names.get(variant, variant)}", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        money_label = customtkinter.CTkLabel(header_frame, text = f"Your Money: {format_price(player_money[0])}", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = 5)

        bet_label = customtkinter.CTkLabel(header_frame, text = f"Bet Range: {format_price(min_bet)} - {format_price(max_bet)}", font = customtkinter.CTkFont(size = 12), text_color = "orange")
        bet_label.pack()

        game_frame = customtkinter.CTkFrame(main_frame)
        game_frame.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)
        game_frame.grid_columnconfigure(0, weight = 1)

        suits =["clubs", "diamonds", "hearts", "spades"]
        values =["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]
        deck =[{"suit":s, "value":v}for s in suits for v in values]

        npc_personalities =["aggressive", "passive", "tight", "loose", "erratic"]

        def generate_random_npc_name():
            try:
                tables = table_data.get("tables", {})
                npc_names_data = tables.get("npc_names", {})
                if not npc_names_data:
                    return f"Player {random.randint(1, 999)}"
                nationalities = list(npc_names_data.keys())
                nationality = random.choice(nationalities)
                name_data = npc_names_data[nationality]
                first_names = name_data.get("first", ["Unknown"])
                last_names = name_data.get("last", ["Player"])
                first = random.choice(first_names)
                last = random.choice(last_names)
                return f"{first} {last}"
            except Exception:
                return f"Player {random.randint(1, 999)}"

        player_overrides = store.get("poker_player_override", [])
        generated_names = set()
        npc_names =[]
        npc_personality_map = {}

        for i in range(3):
            override = next((p for p in player_overrides if p.get("slot")==i +1), None)
            if override and override.get("name"):
                name_data = override["name"]
                if isinstance(name_data, dict):
                    name = f"{name_data.get('first', 'Player')} {name_data.get('last', str(i +1))}"
                else:
                    name = str(name_data)
                npc_names.append(name)
                generated_names.add(name)
            else:
                attempts = 0
                while attempts <50:
                    name = generate_random_npc_name()
                    if name not in generated_names:
                        generated_names.add(name)
                        npc_names.append(name)
                        break
                    attempts +=1
                else:
                    fallback = f"Player {i +1}"
                    npc_names.append(fallback)
                    generated_names.add(fallback)

            npc_personality_map[npc_names[-1]]= random.choice(npc_personalities)

        game_state = {
        "deck":[],
        "player_hand":[],
        "npc_hands":{name:[]for name in npc_names},
        "npc_held":{name:[False]*7 for name in npc_names},
        "held":[False]*7,
        "current_bet":0,
        "pot":0,
        "phase":"betting",
        "card_labels":[],
        "folded":{name:False for name in npc_names},
        "player_folded":False,
        "community_cards":[],
        "ui_valid":True
        }

        wagered_items =[]
        item_bet_value =[0]

        scroll_frame = customtkinter.CTkScrollableFrame(game_frame)
        scroll_frame.pack(fill = "both", expand = True, padx = 5, pady = 5)

        community_frame = None
        community_cards_frame = None
        if variant =="texas_holdem":
            community_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
            community_frame.pack(pady = 10, fill = "x")
            customtkinter.CTkLabel(community_frame, text = "Community Cards", font = customtkinter.CTkFont(size = 14, weight = "bold")).pack()
            community_cards_frame = customtkinter.CTkFrame(community_frame, fg_color = "transparent")
            community_cards_frame.pack(pady = 5)

        npc_frames = {}
        for npc_name in npc_names:
            personality = npc_personality_map.get(npc_name, "normal")
            npc_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
            npc_frame.pack(pady = 5, fill = "x")
            personality_emoji = {"aggressive":"🔥", "passive":"😌", "tight":"🎯", "loose":"🎲", "erratic":"🃏"}.get(personality, "")
            npc_label = customtkinter.CTkLabel(npc_frame, text = f"{npc_name} {personality_emoji}", font = customtkinter.CTkFont(size = 12, weight = "bold"))
            npc_label.pack()
            npc_cards_frame = customtkinter.CTkFrame(npc_frame, fg_color = "transparent")
            npc_cards_frame.pack()
            npc_status_label = customtkinter.CTkLabel(npc_frame, text = "", font = customtkinter.CTkFont(size = 10))
            npc_status_label.pack()
            npc_frames[npc_name]= {"frame":npc_frame, "cards":npc_cards_frame, "status":npc_status_label, "label":npc_label}

        separator = customtkinter.CTkLabel(scroll_frame, text = "─"*50, font = customtkinter.CTkFont(size = 10))
        separator.pack(pady = 5)

        player_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
        player_frame.pack(pady = 10)
        player_label = customtkinter.CTkLabel(player_frame, text = "Your Hand", font = customtkinter.CTkFont(size = 14, weight = "bold"))
        player_label.pack()
        player_cards_frame = customtkinter.CTkFrame(player_frame, fg_color = "transparent")
        player_cards_frame.pack(pady = 5)
        player_score_label = customtkinter.CTkLabel(player_frame, text = "", font = customtkinter.CTkFont(size = 12))
        player_score_label.pack()

        pot_label = customtkinter.CTkLabel(scroll_frame, text = "Pot: $0", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "gold")
        pot_label.pack(pady = 5)

        result_label = customtkinter.CTkLabel(scroll_frame, text = "", font = customtkinter.CTkFont(size = 18, weight = "bold"))
        result_label.pack(pady = 10)

        def get_card_value_num(card):
            v = card["value"]
            if v =="ace":return 14
            elif v =="king":return 13
            elif v =="queen":return 12
            elif v =="jack":return 11
            else:return int(v)

        def shuffle_deck():
            game_state["deck"]= deck.copy()
            random.shuffle(game_state["deck"])
            self._play_card_sound("shuffle")

        def draw_card():
            if not game_state["deck"]:
                shuffle_deck()
            card = game_state["deck"].pop()
            self._play_card_sound("flip")
            return card

        def evaluate_hand(hand):
            if len(hand)<5:
                return("Nothing", 0, [])

            from itertools import combinations
            best_eval =("Nothing", 0, [])

            for combo in combinations(hand, 5):
                combo_list = list(combo)
                vals = sorted([get_card_value_num(c)for c in combo_list], reverse = True)
                suits_list =[c["suit"]for c in combo_list]

                is_flush = len(set(suits_list))==1
                sorted_vals = sorted(vals)
                is_straight = sorted_vals ==list(range(sorted_vals[0], sorted_vals[0]+5))
                if sorted_vals ==[2, 3, 4, 5, 14]:
                    is_straight = True
                    vals =[5, 4, 3, 2, 1]

                val_counts = {}
                for v in vals:
                    val_counts[v]= val_counts.get(v, 0)+1
                counts = sorted(val_counts.values(), reverse = True)

                if is_straight and is_flush:
                    if sorted(vals)==[10, 11, 12, 13, 14]:
                        eval_result =("Royal Flush", 10, vals)
                    else:
                        eval_result =("Straight Flush", 9, vals)
                elif counts ==[4, 1]:
                    eval_result =("Four of a Kind", 8, vals)
                elif counts ==[3, 2]:
                    eval_result =("Full House", 7, vals)
                elif is_flush:
                    eval_result =("Flush", 6, vals)
                elif is_straight:
                    eval_result =("Straight", 5, vals)
                elif counts ==[3, 1, 1]:
                    eval_result =("Three of a Kind", 4, vals)
                elif counts ==[2, 2, 1]:
                    eval_result =("Two Pair", 3, vals)
                elif counts ==[2, 1, 1, 1]:
                    eval_result =("Pair", 2, vals)
                else:
                    eval_result =("High Card", 1, vals)

                if eval_result[1]>best_eval[1]or(eval_result[1]==best_eval[1]and eval_result[2]>best_eval[2]):
                    best_eval = eval_result

            return best_eval

        def npc_decide_hold(hand, npc_name):
            personality = npc_personality_map.get(npc_name, "normal")
            _, rank, _ = evaluate_hand(hand)
            held =[False]*len(hand)

            mistake_chance = 0.15
            if random.random()<mistake_chance:
                if random.random()<0.5:
                    random_idx = random.randint(0, len(hand)-1)
                    return[i ==random_idx for i in range(len(hand))]
                else:
                    return[True]*len(hand)

            vals =[get_card_value_num(c)for c in hand]
            val_counts = {}
            for i, v in enumerate(vals):
                if v not in val_counts:
                    val_counts[v]=[]
                val_counts[v].append(i)

            if personality =="aggressive":
                if rank >=3:
                    return[True]*len(hand)
            elif personality =="passive":
                if rank >=5:
                    return[True]*len(hand)
            elif personality =="erratic":
                if random.random()<0.3:
                    return[random.random()>0.5 for _ in range(len(hand))]

            if rank >=4:
                return[True]*len(hand)

            for v, indices in val_counts.items():
                if len(indices)>=2:
                    for idx in indices:
                        held[idx]= True

            if rank >=2:
                return held

            if personality =="tight":
                high_cards = sorted(enumerate(vals), key = lambda x:x[1], reverse = True)[:3]
            else:
                high_cards = sorted(enumerate(vals), key = lambda x:x[1], reverse = True)[:2]
            for idx, _ in high_cards:
                if idx <len(held):
                    held[idx]= True

            return held

        def npc_decide_fold(hand, bet, npc_name):
            personality = npc_personality_map.get(npc_name, "normal")
            _, rank, _ = evaluate_hand(hand)

            if random.random()<0.1:
                if rank >=4:
                    return True
                elif rank <=1:
                    return False

            if personality =="aggressive":
                if rank >=2:return False
                return random.random()<0.3
            elif personality =="passive":
                if rank >=4:return False
                if rank >=2:return random.random()<0.4
                return random.random()<0.7
            elif personality =="tight":
                if rank >=3:return False
                if rank >=2:return random.random()<0.5
                return random.random()<0.8
            elif personality =="loose":
                if rank >=1:return False
                return random.random()<0.2
            elif personality =="erratic":
                return random.random()<0.35
            else:
                if rank >=3:return False
                if rank ==2:return random.random()<0.2
                if rank ==1:return random.random()<0.5
                return random.random()<0.3

        def display_community_cards():
            if not community_cards_frame:
                return
            for widget in community_cards_frame.winfo_children():
                widget.destroy()
            for card in game_state["community_cards"]:
                img = self._load_card_image(card["suit"], card["value"], size =(60, 84))
                if img:
                    card_label = customtkinter.CTkLabel(community_cards_frame, image = img, text = "")
                    card_label.image = img
                else:
                    text = f"{card['value'][0].upper()}{card['suit'][0].upper()}"
                    card_label = customtkinter.CTkLabel(community_cards_frame, text = text, width = 50, height = 70, fg_color = "white", text_color = "black", corner_radius = 5)
                card_label.pack(side = "left", padx = 3)

        def display_npc_hand(npc_name, reveal = False, show_indices = None):
            if not game_state["ui_valid"]:
                return
            frame_info = npc_frames[npc_name]
            cards_frame = frame_info["cards"]
            status_label = frame_info["status"]

            for widget in cards_frame.winfo_children():
                widget.destroy()

            if game_state["folded"].get(npc_name, False):
                status_label.configure(text = "FOLDED", text_color = "red")
                return

            hand = game_state["npc_hands"].get(npc_name, [])
            for i, card in enumerate(hand):
                show_card = reveal
                if show_indices is not None and i in show_indices:
                    show_card = True

                if show_card:
                    img = self._load_card_image(card["suit"], card["value"], size =(50, 70))
                else:
                    img = self._load_card_image(None, "back", size =(50, 70))

                if img:
                    card_label = customtkinter.CTkLabel(cards_frame, image = img, text = "")
                    card_label.image = img
                else:
                    text = f"{card['value'][0].upper()}{card['suit'][0].upper()}"if show_card else "??"
                    card_label = customtkinter.CTkLabel(cards_frame, text = text, width = 40, height = 56, fg_color = "white", text_color = "black", corner_radius = 3)
                card_label.pack(side = "left", padx = 1)

            if reveal:
                full_hand = hand +game_state.get("community_cards", [])
                hand_name, _, _ = evaluate_hand(full_hand)
                status_label.configure(text = hand_name, text_color = "cyan")
            else:
                status_label.configure(text = "In Game", text_color = "green")

        def display_player_hand(can_hold = False, show_indices = None):
            if not game_state["ui_valid"]:
                return
            for widget in player_cards_frame.winfo_children():
                widget.destroy()

            game_state["card_labels"]=[]
            hand = game_state["player_hand"]

            for i, card in enumerate(hand):
                card_container = customtkinter.CTkFrame(player_cards_frame, fg_color = "transparent")
                card_container.pack(side = "left", padx = 3)

                show_card = True
                if show_indices is not None and i not in show_indices:
                    show_card = True

                if show_card:
                    img = self._load_card_image(card["suit"], card["value"])
                else:
                    img = self._load_card_image(None, "back")

                if img:
                    card_label = customtkinter.CTkLabel(card_container, image = img, text = "")
                    card_label.image = img
                else:
                    text = f"{card['value'][0].upper()}{card['suit'][0].upper()}"if show_card else "??"
                    card_label = customtkinter.CTkLabel(card_container, text = text, width = 60, height = 84, fg_color = "white", text_color = "black", corner_radius = 5)
                card_label.pack()
                game_state["card_labels"].append(card_label)

                if can_hold and variant =="five_card_draw":
                    held_text = "HELD"if game_state["held"][i]else ""
                    hold_label = customtkinter.CTkLabel(card_container, text = held_text, font = customtkinter.CTkFont(size = 10, weight = "bold"), text_color = "yellow")
                    hold_label.pack()

                    def toggle_hold(idx = i, lbl = hold_label):
                        if game_state["phase"]!="draw":
                            return
                        game_state["held"][idx]= not game_state["held"][idx]
                        lbl.configure(text = "HELD"if game_state["held"][idx]else "")
                        self._play_card_sound("place")

                    card_label.bind("<Button-1>", lambda e, idx = i, lbl = hold_label:toggle_hold(idx, lbl))

            full_hand = hand +game_state.get("community_cards", [])
            hand_name, _, _ = evaluate_hand(full_hand)
            player_score_label.configure(text = f"Current: {hand_name}")

            money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
            pot_label.configure(text = f"Pot: {format_price(game_state['pot'])}")
            update_money_cb()

        def deal_new_hand():
            if not game_state["ui_valid"]:
                return
            bet_str = bet_entry.get()
            try:
                bet = parse_display_price_to_usd(bet_str, round_to_int = True)
            except ValueError:
                self._popup_show_info("Invalid Bet", "Please enter a valid money amount.", sound = "error")
                return

            if bet <min_bet or bet >max_bet:
                self._popup_show_info("Invalid Bet", f"Bet must be between {format_price(min_bet)} and {format_price(max_bet)}.", sound = "error")
                return

            if bet >player_money[0]:
                self._popup_show_info("Insufficient Funds", "You don't have enough money for that bet.", sound = "error")
                return

            game_state["current_bet"]= bet
            game_state["held"]=[False]*7
            game_state["player_folded"]= False
            game_state["community_cards"]=[]
            for name in npc_names:
                game_state["folded"][name]= False
                game_state["npc_held"][name]=[False]*7
            result_label.configure(text = "")

            shuffle_deck()

            if variant =="five_card_draw":
                game_state["player_hand"]=[draw_card()for _ in range(5)]
                for npc_name in npc_names:
                    game_state["npc_hands"][npc_name]=[draw_card()for _ in range(5)]
            elif variant =="five_card_stud":
                game_state["player_hand"]=[draw_card()for _ in range(5)]
                for npc_name in npc_names:
                    game_state["npc_hands"][npc_name]=[draw_card()for _ in range(5)]
            elif variant =="seven_card_stud":
                game_state["player_hand"]=[draw_card()for _ in range(7)]
                for npc_name in npc_names:
                    game_state["npc_hands"][npc_name]=[draw_card()for _ in range(7)]
            elif variant =="texas_holdem":
                game_state["player_hand"]=[draw_card()for _ in range(2)]
                for npc_name in npc_names:
                    game_state["npc_hands"][npc_name]=[draw_card()for _ in range(2)]
                game_state["community_cards"]=[draw_card()for _ in range(5)]

            active_players = 1 +len(npc_names)
            game_state["pot"]= bet *active_players

            for npc_name in npc_names:
                full_hand = game_state["npc_hands"][npc_name]+game_state.get("community_cards", [])
                if npc_decide_fold(full_hand, bet, npc_name):
                    game_state["folded"][npc_name]= True
                    game_state["pot"]-=bet

            if variant =="five_card_draw":
                game_state["phase"]= "draw"
            else:
                game_state["phase"]= "showdown"

            deal_btn.configure(state = "disabled")
            if variant =="five_card_draw":
                if draw_btn:
                    draw_btn.configure(state = "disabled")
            else:
                if show_btn:
                    show_btn.configure(state = "disabled")
            fold_btn.configure(state = "disabled")

            if variant =="texas_holdem":
                display_community_cards()

            deal_order = list(npc_names)+["__player__"]

            def animate_poker_deal(step = 0):
                if not game_state["ui_valid"]:
                    return
                if step >=len(deal_order):
                    update_buttons()
                    if variant =="five_card_draw":
                        result_label.configure(text = "Click cards to hold, then Draw", text_color = "white")
                    else:
                        result_label.configure(text = "Press 'Show Cards' to reveal hands", text_color = "white")
                    return

                name = deal_order[step]
                self._play_card_sound("place")

                if name =="__player__":
                    can_hold = variant =="five_card_draw"
                    display_player_hand(can_hold = can_hold)
                else:
                    if variant =="five_card_stud":
                        display_npc_hand(name, reveal = False, show_indices =[1, 2, 3, 4])
                    elif variant =="seven_card_stud":
                        display_npc_hand(name, reveal = False, show_indices =[2, 3, 4, 5])
                    else:
                        display_npc_hand(name, reveal = False)

                self.root.after(400, lambda:animate_poker_deal(step +1))

            animate_poker_deal(0)

        def draw_new_cards():
            if not game_state["ui_valid"]:
                return
            if game_state["phase"]!="draw":
                return

            if variant =="five_card_draw":
                for i in range(5):
                    if not game_state["held"][i]:
                        game_state["player_hand"][i]= draw_card()

                for npc_name in npc_names:
                    if not game_state["folded"][npc_name]:
                        npc_held = npc_decide_hold(game_state["npc_hands"][npc_name], npc_name)
                        for i in range(5):
                            if not npc_held[i]:
                                game_state["npc_hands"][npc_name][i]= draw_card()

            game_state["phase"]= "showdown"
            display_player_hand(can_hold = False)

            if draw_btn:
                draw_btn.configure(state = "disabled")
            fold_btn.configure(state = "disabled")

            active_npcs =[n for n in npc_names if not game_state["folded"][n]]

            def reveal_after_draw(step = 0):
                if not game_state["ui_valid"]:
                    return
                if step >=len(active_npcs):
                    determine_winner()
                    update_buttons()
                    return
                self._play_card_sound("flip")
                display_npc_hand(active_npcs[step], reveal = True)
                self.root.after(400, lambda:reveal_after_draw(step +1))

            reveal_after_draw(0)

        def show_cards():
            if not game_state["ui_valid"]:
                return
            game_state["phase"]= "complete"
            display_player_hand(can_hold = False)

            if show_btn:
                show_btn.configure(state = "disabled")
            fold_btn.configure(state = "disabled")

            active_npcs =[n for n in npc_names if not game_state["folded"][n]]

            def reveal_step(step = 0):
                if not game_state["ui_valid"]:
                    return
                if step >=len(active_npcs):
                    determine_winner()
                    update_buttons()
                    return
                self._play_card_sound("flip")
                display_npc_hand(active_npcs[step], reveal = True)
                self.root.after(400, lambda:reveal_step(step +1))

            reveal_step(0)

        def fold_hand():
            if not game_state["ui_valid"]:
                return
            if game_state["phase"]not in["draw", "showdown"]:
                return
            game_state["player_folded"]= True
            game_state["phase"]= "complete"

            loss = -game_state["current_bet"]
            if record_game_cb:
                record_game_cb(loss)

            item_suffix = ""
            if wagered_items:
                self._process_item_bet_loss(save_data, save_path, wagered_items)
                item_suffix = f" | Lost {len(wagered_items)} item(s)"
                wagered_items.clear()
                item_bet_value[0]= 0
                try:
                    item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")
                except Exception:
                    pass

            save_money_cb()

            active_npcs =[n for n in npc_names if not game_state["folded"][n]]
            if active_npcs:
                for npc_name in npc_names:
                    display_npc_hand(npc_name, reveal = True)
                result_label.configure(text = f"You folded.{active_npcs[0]} wins the pot!{item_suffix}", text_color = "red")
            else:
                result_label.configure(text = f"Everyone folded!{item_suffix}", text_color = "orange")

            update_buttons()
            money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
            update_money_cb()

        def determine_winner():
            if not game_state["ui_valid"]:
                return
            player_full_hand = game_state["player_hand"]+game_state.get("community_cards", [])
            player_eval = evaluate_hand(player_full_hand)
            best_hand =("You", player_eval)

            for npc_name in npc_names:
                if not game_state["folded"][npc_name]:
                    npc_full_hand = game_state["npc_hands"][npc_name]+game_state.get("community_cards", [])
                    npc_eval = evaluate_hand(npc_full_hand)
                    if npc_eval[1]>best_hand[1][1]:
                        best_hand =(npc_name, npc_eval)
                    elif npc_eval[1]==best_hand[1][1]:
                        if npc_eval[2]>best_hand[1][2]:
                            best_hand =(npc_name, npc_eval)

            winner_name = best_hand[0]
            winner_hand = best_hand[1][0]
            pot = game_state["pot"]

            if winner_name =="You":
                winnings = pot -game_state["current_bet"]
                winnings = self._apply_casino_house_edge(store, "poker", winnings)
                player_money[0]+=winnings
                if wagered_items:
                    player_money[0]+=item_bet_value[0]
                if record_game_cb:
                    record_game_cb(winnings)
                item_suffix = ""
                if item_bet_value[0]>0 and wagered_items:
                    item_suffix = f" | +{format_price(item_bet_value[0])} from items"
                result_label.configure(text = f"You win with {winner_hand}! +{format_price(winnings +(item_bet_value[0]if wagered_items else 0))}{item_suffix}", text_color = "green")
            else:
                loss = -game_state["current_bet"]
                player_money[0]-=game_state["current_bet"]
                if record_game_cb:
                    record_game_cb(loss)
                item_suffix = ""
                if wagered_items:
                    self._process_item_bet_loss(save_data, save_path, wagered_items)
                    item_suffix = f" | Lost {len(wagered_items)} item(s)"
                result_label.configure(text = f"{winner_name} wins with {winner_hand}! -{format_price(game_state['current_bet'])}{item_suffix}", text_color = "red")

            wagered_items.clear()
            item_bet_value[0]= 0
            try:
                item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")
            except Exception:
                pass

            save_money_cb()
            game_state["phase"]= "complete"
            money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
            update_money_cb()

        def update_buttons():
            if not game_state["ui_valid"]:
                return
            try:
                if game_state["phase"]=="betting":
                    deal_btn.configure(state = "normal")
                    if variant =="five_card_draw":
                        draw_btn.configure(state = "disabled")
                    else:
                        show_btn.configure(state = "disabled")
                    fold_btn.configure(state = "disabled")
                elif game_state["phase"]=="draw":
                    deal_btn.configure(state = "disabled")
                    if variant =="five_card_draw":
                        draw_btn.configure(state = "normal")
                    fold_btn.configure(state = "normal")
                elif game_state["phase"]=="showdown":
                    deal_btn.configure(state = "disabled")
                    if variant !="five_card_draw":
                        show_btn.configure(state = "normal")
                    fold_btn.configure(state = "normal")
                else:
                    deal_btn.configure(state = "normal")
                    if variant =="five_card_draw":
                        draw_btn.configure(state = "disabled")
                    else:
                        show_btn.configure(state = "disabled")
                    fold_btn.configure(state = "disabled")
            except Exception:
                pass

        def show_hand_rankings():
            popup = customtkinter.CTkToplevel(self.root)
            popup.title("Poker Hand Rankings")
            popup.transient(self.root)
            popup.grab_set()
            popup.withdraw()

            scroll_frame = customtkinter.CTkScrollableFrame(popup, width = 500, height = 500)
            scroll_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

            title_lbl = customtkinter.CTkLabel(scroll_frame, text = "Poker Hand Rankings", font = customtkinter.CTkFont(size = 18, weight = "bold"))
            title_lbl.pack(pady =(5, 15))

            example_hands =[
            ("1.Royal Flush", "A, K, Q, J, 10 all same suit", [("hearts", "ace"), ("hearts", "king"), ("hearts", "queen"), ("hearts", "jack"), ("hearts", "10")]),
            ("2.Straight Flush", "Five sequential cards, same suit", [("spades", "9"), ("spades", "8"), ("spades", "7"), ("spades", "6"), ("spades", "5")]),
            ("3.Four of a Kind", "Four cards of same rank", [("hearts", "king"), ("diamonds", "king"), ("clubs", "king"), ("spades", "king"), ("hearts", "3")]),
            ("4.Full House", "Three of a kind + a pair", [("hearts", "queen"), ("diamonds", "queen"), ("clubs", "queen"), ("spades", "7"), ("hearts", "7")]),
            ("5.Flush", "Five cards of same suit", [("diamonds", "ace"), ("diamonds", "jack"), ("diamonds", "8"), ("diamonds", "5"), ("diamonds", "2")]),
            ("6.Straight", "Five sequential cards, any suit", [("hearts", "10"), ("diamonds", "9"), ("clubs", "8"), ("spades", "7"), ("hearts", "6")]),
            ("7.Three of a Kind", "Three cards of same rank", [("hearts", "8"), ("diamonds", "8"), ("clubs", "8"), ("spades", "king"), ("hearts", "4")]),
            ("8.Two Pair", "Two different pairs", [("hearts", "jack"), ("diamonds", "jack"), ("clubs", "5"), ("spades", "5"), ("hearts", "2")]),
            ("9.Pair", "Two cards of same rank", [("hearts", "ace"), ("diamonds", "ace"), ("clubs", "9"), ("spades", "6"), ("hearts", "3")]),
            ("10.High Card", "Highest card wins", [("hearts", "ace"), ("diamonds", "king"), ("clubs", "9"), ("spades", "5"), ("hearts", "2")]),
            ]

            for hand_name, description, cards in example_hands:
                hand_frame = customtkinter.CTkFrame(scroll_frame, fg_color = "transparent")
                hand_frame.pack(pady = 8, fill = "x")
                name_lbl = customtkinter.CTkLabel(hand_frame, text = hand_name, font = customtkinter.CTkFont(size = 14, weight = "bold"))
                name_lbl.pack(anchor = "w")
                desc_lbl = customtkinter.CTkLabel(hand_frame, text = description, font = customtkinter.CTkFont(size = 11), text_color = "gray")
                desc_lbl.pack(anchor = "w")
                cards_row = customtkinter.CTkFrame(hand_frame, fg_color = "transparent")
                cards_row.pack(anchor = "w", pady = 3)
                for suit, value in cards:
                    img = self._load_card_image(suit, value, size =(45, 63))
                    if img:
                        card_lbl = customtkinter.CTkLabel(cards_row, image = img, text = "")
                        card_lbl.image = img
                    else:
                        card_lbl = customtkinter.CTkLabel(cards_row, text = f"{value[0].upper()}{suit[0].upper()}", width = 35, height = 49, fg_color = "white", text_color = "black", corner_radius = 3)
                    card_lbl.pack(side = "left", padx = 1)

            close_btn = customtkinter.CTkButton(scroll_frame, text = "Close", command = popup.destroy, width = 100)
            close_btn.pack(pady = 15)
            self._play_ui_sound("click")
            popup.update_idletasks()
            w, h = 540, 600
            x = self.root.winfo_x()+(self.root.winfo_width()//2)-(w //2)
            y = self.root.winfo_y()+(self.root.winfo_height()//2)-(h //2)
            popup.geometry(f"{w}x{h}+{x}+{y}")
            popup.deiconify()

        controls_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        controls_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        bet_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        bet_frame.pack(pady = 5)

        bet_label_entry = customtkinter.CTkLabel(bet_frame, text = "Bet Amount:", font = customtkinter.CTkFont(size = 14))
        bet_label_entry.pack(side = "left")

        bet_entry = customtkinter.CTkEntry(bet_frame, width = 140, placeholder_text = format_price(min_bet))
        bet_entry.pack(side = "left", padx = 5)
        bet_entry.insert(0, format_price(min_bet))

        if save_data and save_path:
            item_wager_label = customtkinter.CTkLabel(bet_frame, text = "Items Wagered: None", font = customtkinter.CTkFont(size = 11), text_color = "gray")
            item_wager_label.pack(side = "left", padx = 10)

            def update_item_wager_display():
                total = sum(int(e["item"].get("value", 0))for e in wagered_items)
                item_bet_value[0]= total
                if wagered_items:
                    item_wager_label.configure(text = f"Items Wagered: {len(wagered_items)}({format_price(total)})", text_color = "gold")
                else:
                    item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")

            def open_item_wager():
                if game_state["phase"]not in["betting", "complete"]:
                    self._popup_show_info("Game Active", "Cannot change item wager during a game.", sound = "popup")
                    return
                self._open_item_bet_dialog(save_data, wagered_items, update_item_wager_display)

            wager_btn = self._create_sound_button(bet_frame, "Wager Items", open_item_wager, width = 110, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = "#8B4513", hover_color = "#654321")
            wager_btn.pack(side = "left", padx = 5)

        action_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        action_frame.pack(pady = 10)

        deal_btn = self._create_sound_button(action_frame, "Deal", deal_new_hand, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
        deal_btn.pack(side = "left", padx = 5)

        if variant =="five_card_draw":
            draw_btn = self._create_sound_button(action_frame, "Draw", draw_new_cards, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
            draw_btn.pack(side = "left", padx = 5)
            draw_btn.configure(state = "disabled")
            show_btn = None
        else:
            show_btn = self._create_sound_button(action_frame, "Show Cards", show_cards, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
            show_btn.pack(side = "left", padx = 5)
            show_btn.configure(state = "disabled")
            draw_btn = None

        fold_btn = self._create_sound_button(action_frame, "Fold", fold_hand, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
        fold_btn.pack(side = "left", padx = 5)
        fold_btn.configure(state = "disabled")

        hands_btn = self._create_sound_button(action_frame, "Hand Rankings", show_hand_rankings, width = 120, height = 40, font = customtkinter.CTkFont(size = 12))
        hands_btn.pack(side = "left", padx = 5)

        def back_to_poker_lobby():
            game_state["ui_valid"]= False
            self._open_poker_lobby(store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb, casino_stats, save_data = save_data, save_path = save_path)

        back_btn = self._create_sound_button(controls_frame, "Back to Poker Lobby", back_to_poker_lobby, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(pady = 10)

    def _open_highlow_game(self, store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb = None, casino_stats = None, save_data = None, save_path = None):
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = "High-Low", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        money_label = customtkinter.CTkLabel(header_frame, text = f"Your Money: {format_price(player_money[0])}", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = 5)

        bet_label = customtkinter.CTkLabel(header_frame, text = f"Bet Range: {format_price(min_bet)} - {format_price(max_bet)}", font = customtkinter.CTkFont(size = 12), text_color = "orange")
        bet_label.pack()

        game_frame = customtkinter.CTkFrame(main_frame)
        game_frame.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)
        game_frame.grid_columnconfigure(0, weight = 1)

        suits =["clubs", "diamonds", "hearts", "spades"]
        values =["2", "3", "4", "5", "6", "7", "8", "9", "10", "jack", "queen", "king", "ace"]

        deck =[{"suit":s, "value":v}for s in suits for v in values]
        game_state = {
        "deck":[],
        "current_card":None,
        "next_card":None,
        "current_bet":0,
        "streak":0,
        "winnings":0,
        "game_active":False,
        "ui_valid":True
        }

        wagered_items =[]
        item_bet_value =[0]

        instruction_label = customtkinter.CTkLabel(game_frame, text = "Guess if the next card will be Higher or Lower!", font = customtkinter.CTkFont(size = 14), text_color = "gray")
        instruction_label.pack(pady = 10)

        cards_frame = customtkinter.CTkFrame(game_frame, fg_color = "transparent")
        cards_frame.pack(pady = 20)

        current_card_frame = customtkinter.CTkFrame(cards_frame, fg_color = "transparent")
        current_card_frame.pack(side = "left", padx = 20)
        current_label = customtkinter.CTkLabel(current_card_frame, text = "Current Card", font = customtkinter.CTkFont(size = 12, weight = "bold"))
        current_label.pack()
        current_card_display = customtkinter.CTkLabel(current_card_frame, text = "", width = 80, height = 112)
        current_card_display.pack(pady = 5)

        arrow_label = customtkinter.CTkLabel(cards_frame, text = "→", font = customtkinter.CTkFont(size = 36, weight = "bold"))
        arrow_label.pack(side = "left", padx = 10)

        next_card_frame = customtkinter.CTkFrame(cards_frame, fg_color = "transparent")
        next_card_frame.pack(side = "left", padx = 20)
        next_label = customtkinter.CTkLabel(next_card_frame, text = "Next Card", font = customtkinter.CTkFont(size = 12, weight = "bold"))
        next_label.pack()
        next_card_display = customtkinter.CTkLabel(next_card_frame, text = "", width = 80, height = 112)
        next_card_display.pack(pady = 5)

        streak_label = customtkinter.CTkLabel(game_frame, text = "Streak: 0", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "cyan")
        streak_label.pack(pady = 5)

        winnings_label = customtkinter.CTkLabel(game_frame, text = "Current Winnings: $0", font = customtkinter.CTkFont(size = 14), text_color = "gold")
        winnings_label.pack(pady = 5)

        result_label = customtkinter.CTkLabel(game_frame, text = "", font = customtkinter.CTkFont(size = 18, weight = "bold"))
        result_label.pack(pady = 10)

        def get_card_rank(card):
            v = card["value"]
            if v =="ace":
                return 14
            elif v =="king":
                return 13
            elif v =="queen":
                return 12
            elif v =="jack":
                return 11
            else:
                return int(v)

        def shuffle_deck():
            game_state["deck"]= deck.copy()
            random.shuffle(game_state["deck"])
            self._play_card_sound("shuffle")

        def draw_card():
            if not game_state["deck"]:
                shuffle_deck()
            card = game_state["deck"].pop()
            self._play_card_sound("flip")
            return card

        def display_card(label, card, hidden = False):
            if not game_state["ui_valid"]:
                return
            if hidden:
                img = self._load_card_image(None, "back")
            elif card:
                img = self._load_card_image(card["suit"], card["value"])
            else:
                img = None

            if img:
                label.configure(image = img, text = "")
                label.image = img
            elif card and not hidden:
                text = f"{card['value'][0].upper()}{card['suit'][0].upper()}"
                label.configure(image = None, text = text, fg_color = "white", text_color = "black")
            else:
                label.configure(image = None, text = "??", fg_color = "gray30", text_color = "white")

        def update_display():
            if not game_state["ui_valid"]:
                return
            try:
                money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
                streak_label.configure(text = f"Streak: {game_state['streak']}")
                winnings_label.configure(text = f"Current Winnings: {format_price(game_state['winnings'])}")
                update_money_cb()
            except Exception:
                pass

        def start_game():
            bet_str = bet_entry.get()
            try:
                bet = parse_display_price_to_usd(bet_str, round_to_int = True)
            except ValueError:
                self._popup_show_info("Invalid Bet", "Please enter a valid money amount.", sound = "error")
                return

            if bet <min_bet or bet >max_bet:
                self._popup_show_info("Invalid Bet", f"Bet must be between {format_price(min_bet)} and {format_price(max_bet)}.", sound = "error")
                return

            if bet >player_money[0]:
                self._popup_show_info("Insufficient Funds", "You don't have enough money for that bet.", sound = "error")
                return

            game_state["current_bet"]= bet
            game_state["streak"]= 0
            game_state["winnings"]= 0
            game_state["game_active"]= True
            result_label.configure(text = "")

            shuffle_deck()
            game_state["current_card"]= draw_card()
            game_state["next_card"]= None

            display_card(current_card_display, game_state["current_card"])
            display_card(next_card_display, None, hidden = True)

            update_display()
            update_buttons()

        def guess_high():
            if not game_state["game_active"]:
                return
            make_guess("high")

        def guess_low():
            if not game_state["game_active"]:
                return
            make_guess("low")

        def make_guess(guess):
            if not game_state["ui_valid"]:
                return

            game_state["next_card"]= draw_card()
            display_card(next_card_display, game_state["next_card"])

            current_rank = get_card_rank(game_state["current_card"])
            next_rank = get_card_rank(game_state["next_card"])

            if next_rank ==current_rank:
                result_label.configure(text = "It's a Tie! Push - no win or loss.", text_color = "orange")
                game_state["current_card"]= game_state["next_card"]
                self.root.after(1500, continue_or_end)
            elif(guess =="high"and next_rank >current_rank)or(guess =="low"and next_rank <current_rank):
                game_state["streak"]+=1
                multiplier = 1 +(game_state["streak"]-1)*0.5
                round_win = int(game_state["current_bet"]*multiplier)
                game_state["winnings"]+=round_win
                result_label.configure(text = f"Correct! +{format_price(round_win)}(Streak: {game_state['streak']}x)", text_color = "green")
                game_state["current_card"]= game_state["next_card"]
                update_display()
                self.root.after(1500, continue_or_end)
            else:
                end_game_loss()

        def continue_or_end():
            if not game_state["ui_valid"]:
                return
            display_card(current_card_display, game_state["current_card"])
            display_card(next_card_display, None, hidden = True)
            result_label.configure(text = "Keep going or Cash Out!", text_color = "cyan")
            update_buttons()

        def cash_out():
            if not game_state["game_active"]or game_state["winnings"]<=0:
                return

            winnings = game_state["winnings"]
            winnings = self._apply_casino_house_edge(store, "high-low", winnings)
            player_money[0]+=winnings
            if wagered_items:
                player_money[0]+=item_bet_value[0]
            if record_game_cb:
                record_game_cb(winnings)
            save_money_cb()

            game_state["game_active"]= False
            item_suffix = ""
            if item_bet_value[0]>0 and wagered_items:
                item_suffix = f" | +{format_price(item_bet_value[0])} from items"
            result_label.configure(text = f"Cashed Out! +{format_price(winnings +(item_bet_value[0]if wagered_items else 0))}{item_suffix}", text_color = "green")
            wagered_items.clear()
            item_bet_value[0]= 0
            try:
                item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")
            except Exception:
                pass
            update_display()
            update_buttons()

        def end_game_loss():
            if not game_state["ui_valid"]:
                return

            loss = -game_state["current_bet"]
            player_money[0]+=loss
            if record_game_cb:
                record_game_cb(loss)

            item_suffix = ""
            if wagered_items:
                self._process_item_bet_loss(save_data, save_path, wagered_items)
                item_suffix = f" | Lost {len(wagered_items)} item(s)"
                wagered_items.clear()
                item_bet_value[0]= 0
                try:
                    item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")
                except Exception:
                    pass

            save_money_cb()

            game_state["game_active"]= False
            result_label.configure(text = f"Wrong! You lose {format_price(game_state['current_bet'])}{item_suffix}", text_color = "red")
            game_state["streak"]= 0
            game_state["winnings"]= 0
            update_display()
            update_buttons()

        def update_buttons():
            if not game_state["ui_valid"]:
                return
            try:
                if game_state["game_active"]:
                    start_btn.configure(state = "disabled")
                    high_btn.configure(state = "normal")
                    low_btn.configure(state = "normal")
                    cashout_btn.configure(state = "normal"if game_state["winnings"]>0 else "disabled")
                else:
                    start_btn.configure(state = "normal")
                    high_btn.configure(state = "disabled")
                    low_btn.configure(state = "disabled")
                    cashout_btn.configure(state = "disabled")
            except Exception:
                pass

        controls_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        controls_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        bet_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        bet_frame.pack(pady = 5)

        bet_label_entry = customtkinter.CTkLabel(bet_frame, text = "Bet Amount:", font = customtkinter.CTkFont(size = 14))
        bet_label_entry.pack(side = "left")

        bet_entry = customtkinter.CTkEntry(bet_frame, width = 140, placeholder_text = format_price(min_bet))
        bet_entry.pack(side = "left", padx = 5)
        bet_entry.insert(0, format_price(min_bet))

        if save_data and save_path:
            item_wager_label = customtkinter.CTkLabel(bet_frame, text = "Items Wagered: None", font = customtkinter.CTkFont(size = 11), text_color = "gray")
            item_wager_label.pack(side = "left", padx = 10)

            def update_item_wager_display():
                total = sum(int(e["item"].get("value", 0))for e in wagered_items)
                item_bet_value[0]= total
                if wagered_items:
                    item_wager_label.configure(text = f"Items Wagered: {len(wagered_items)}({format_price(total)})", text_color = "gold")
                else:
                    item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")

            def open_item_wager():
                if game_state["game_active"]:
                    self._popup_show_info("Game Active", "Cannot change item wager during a game.", sound = "popup")
                    return
                self._open_item_bet_dialog(save_data, wagered_items, update_item_wager_display)

            wager_btn = self._create_sound_button(bet_frame, "Wager Items", open_item_wager, width = 110, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = "#8B4513", hover_color = "#654321")
            wager_btn.pack(side = "left", padx = 5)

        action_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        action_frame.pack(pady = 10)

        start_btn = self._create_sound_button(action_frame, "Start", start_game, width = 100, height = 40, font = customtkinter.CTkFont(size = 14))
        start_btn.pack(side = "left", padx = 5)

        high_btn = self._create_sound_button(action_frame, "Higher", guess_high, width = 100, height = 40, font = customtkinter.CTkFont(size = 14), fg_color = "green", hover_color = "darkgreen")
        high_btn.pack(side = "left", padx = 5)
        high_btn.configure(state = "disabled")

        low_btn = self._create_sound_button(action_frame, "Lower", guess_low, width = 100, height = 40, font = customtkinter.CTkFont(size = 14), fg_color = "red", hover_color = "darkred")
        low_btn.pack(side = "left", padx = 5)
        low_btn.configure(state = "disabled")

        cashout_btn = self._create_sound_button(action_frame, "Cash Out", cash_out, width = 100, height = 40, font = customtkinter.CTkFont(size = 14), fg_color = "gold", hover_color = "darkgoldenrod", text_color = "black")
        cashout_btn.pack(side = "left", padx = 5)
        cashout_btn.configure(state = "disabled")

        def back_to_casino():
            game_state["ui_valid"]= False
            self._open_casino_interface(store, table_data)

        back_btn = self._create_sound_button(controls_frame, "Back to Casino", back_to_casino, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(pady = 10)

    def _open_roulette_game(self, store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb = None, casino_stats = None, save_data = None, save_path = None):
        import tkinter as _tk_roulette
        import math
        import time as _time_roulette

        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = "Roulette", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        money_label = customtkinter.CTkLabel(header_frame, text = f"Your Money: {format_price(player_money[0])}", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = 5)

        bet_label = customtkinter.CTkLabel(header_frame, text = f"Bet Range: {format_price(min_bet)} - {format_price(max_bet)}", font = customtkinter.CTkFont(size = 12), text_color = "orange")
        bet_label.pack()

        game_frame = customtkinter.CTkFrame(main_frame)
        game_frame.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)
        game_frame.grid_columnconfigure(0, weight = 1)

        roulette_numbers =[
        (0, "green"), (32, "red"), (15, "black"), (19, "red"), (4, "black"), (21, "red"), (2, "black"),
        (25, "red"), (17, "black"), (34, "red"), (6, "black"), (27, "red"), (13, "black"), (36, "red"),
        (11, "black"), (30, "red"), (8, "black"), (23, "red"), (10, "black"), (5, "red"), (24, "black"),
        (16, "red"), (33, "black"), (1, "red"), (20, "black"), (14, "red"), (31, "black"), (9, "red"),
        (22, "black"), (18, "red"), (29, "black"), (7, "red"), (28, "black"), (12, "red"), (35, "black"),
        (3, "red"), (26, "black")
        ]

        game_state = {
        "current_bet":0,
        "bet_type":None,
        "bet_value":None,
        "spinning":False,
        "ui_valid":True
        }

        wagered_items =[]
        item_bet_value =[0]

        wheel_bg = "#2b2b2b"
        try:
            _fg = game_frame.cget("fg_color")
            if isinstance(_fg, (tuple, list)) and _fg:
                wheel_bg = str(_fg[-1])
            elif isinstance(_fg, str) and _fg and _fg.lower() != "transparent":
                wheel_bg = _fg
        except Exception:
            pass

        wheel_container = customtkinter.CTkFrame(game_frame, fg_color = wheel_bg)
        wheel_container.pack(pady = 10)

        wheel_size = 340
        wheel_canvas = _tk_roulette.Canvas(wheel_container, width = wheel_size, height = wheel_size, bg = wheel_bg, highlightthickness = 0)
        wheel_canvas.pack(pady = (0, 8))

        wheel_number_label = customtkinter.CTkLabel(wheel_container, text = "Place Your Bet", font = customtkinter.CTkFont(size = 26, weight = "bold"))
        wheel_number_label.pack()

        def _roulette_color_code(col):
            if col == "red":
                return "#b00020"
            if col == "black":
                return "#1a1a1a"
            return "#0f8b3a"

        def draw_roulette_wheel(current_idx = 0.0):
            try:
                wheel_canvas.delete("all")
                center = wheel_size / 2
                outer_r = (wheel_size / 2) - 10
                inner_r = 96
                segment_deg = 360.0 / len(roulette_numbers)

                outer_box = (center - outer_r, center - outer_r, center + outer_r, center + outer_r)
                inner_box = (center - inner_r, center - inner_r, center + inner_r, center + inner_r)

                segment_centers = []

                # Pass 1: draw all slices with an explicit pocket-center angle.
                for i, (num, col) in enumerate(roulette_numbers):
                    # Baseline is bottom-center so the 0 pocket starts at the bottom.
                    pocket_center_deg = 90.0 - ((i - float(current_idx)) * segment_deg)
                    start_deg = pocket_center_deg - (segment_deg / 2.0)
                    fill_col = _roulette_color_code(col)
                    wheel_canvas.create_arc(
                        outer_box,
                        start = start_deg,
                        extent = segment_deg,
                        fill = fill_col,
                        outline = "#111111",
                        width = 1,
                        style = _tk_roulette.PIESLICE
                    )
                    segment_centers.append((pocket_center_deg, num, col))

                # Pass 2: draw all labels on top so they cannot be overpainted.
                for center_deg, num, col in segment_centers:
                    angle_rad = math.radians(center_deg)
                    text_radius = inner_r + ((outer_r - inner_r) * 0.55)
                    tx = center + (text_radius * math.cos(angle_rad))
                    # Tk arc angles and canvas Y axis are inverted relative to plain trig.
                    ty = center - (text_radius * math.sin(angle_rad))
                    text_col = "#ffffff" if col in ("red", "black") else "#000000"
                    text_angle = (center_deg + 90.0) % 360.0
                    if 90.0 < text_angle < 270.0:
                        text_angle = (text_angle + 180.0) % 360.0
                    wheel_canvas.create_text(tx, ty, text = str(num), fill = text_col, font = ("Arial", 9, "bold"), angle = text_angle)

                wheel_canvas.create_oval(inner_box, fill = "#2a2a2a", outline = "#777777", width = 2)

                pointer_x = center
                pointer_y = center - outer_r - 2
                wheel_canvas.create_polygon(
                    pointer_x, pointer_y,
                    pointer_x - 12, pointer_y + 22,
                    pointer_x + 12, pointer_y + 22,
                    fill = "#f5d442",
                    outline = "#222222",
                    width = 1
                )
            except Exception:
                pass

        draw_roulette_wheel(0)

        result_label = customtkinter.CTkLabel(game_frame, text = "", font = customtkinter.CTkFont(size = 18, weight = "bold"))
        result_label.pack(pady = 10)

        bet_types_frame = customtkinter.CTkFrame(game_frame, fg_color = "transparent")
        bet_types_frame.pack(pady = 10)

        selected_bet =[None, None]

        def select_bet_type(bet_type, bet_value, btn):
            if game_state["spinning"]:
                return
            selected_bet[0]= bet_type
            selected_bet[1]= bet_value
            result_label.configure(text = f"Selected: {bet_type} - {bet_value}", text_color = "cyan")
            self._play_ui_sound("click")

        color_frame = customtkinter.CTkFrame(bet_types_frame, fg_color = "transparent")
        color_frame.pack(pady = 5)
        customtkinter.CTkLabel(color_frame, text = "Color Bets(2x):", font = customtkinter.CTkFont(size = 12)).pack(side = "left", padx = 5)
        red_btn = self._create_sound_button(color_frame, "Red", lambda:select_bet_type("Color", "red", red_btn), width = 80, height = 35, fg_color = "#8B0000", hover_color = "#5C0000")
        red_btn.pack(side = "left", padx = 3)
        black_btn = self._create_sound_button(color_frame, "Black", lambda:select_bet_type("Color", "black", black_btn), width = 80, height = 35, fg_color = "#1a1a1a", hover_color = "#333333")
        black_btn.pack(side = "left", padx = 3)
        green_btn = self._create_sound_button(color_frame, "Green(0)", lambda:select_bet_type("Color", "green", green_btn), width = 80, height = 35, fg_color = "#006400", hover_color = "#004d00")
        green_btn.pack(side = "left", padx = 3)

        parity_frame = customtkinter.CTkFrame(bet_types_frame, fg_color = "transparent")
        parity_frame.pack(pady = 5)
        customtkinter.CTkLabel(parity_frame, text = "Parity Bets(2x):", font = customtkinter.CTkFont(size = 12)).pack(side = "left", padx = 5)
        odd_btn = self._create_sound_button(parity_frame, "Odd", lambda:select_bet_type("Parity", "odd", odd_btn), width = 80, height = 35)
        odd_btn.pack(side = "left", padx = 3)
        even_btn = self._create_sound_button(parity_frame, "Even", lambda:select_bet_type("Parity", "even", even_btn), width = 80, height = 35)
        even_btn.pack(side = "left", padx = 3)

        range_frame = customtkinter.CTkFrame(bet_types_frame, fg_color = "transparent")
        range_frame.pack(pady = 5)
        customtkinter.CTkLabel(range_frame, text = "Range Bets(2x):", font = customtkinter.CTkFont(size = 12)).pack(side = "left", padx = 5)
        low_btn = self._create_sound_button(range_frame, "1-18", lambda:select_bet_type("Range", "low", low_btn), width = 80, height = 35)
        low_btn.pack(side = "left", padx = 3)
        high_btn = self._create_sound_button(range_frame, "19-36", lambda:select_bet_type("Range", "high", high_btn), width = 80, height = 35)
        high_btn.pack(side = "left", padx = 3)

        dozen_frame = customtkinter.CTkFrame(bet_types_frame, fg_color = "transparent")
        dozen_frame.pack(pady = 5)
        customtkinter.CTkLabel(dozen_frame, text = "Dozen Bets(3x):", font = customtkinter.CTkFont(size = 12)).pack(side = "left", padx = 5)
        first_btn = self._create_sound_button(dozen_frame, "1-12", lambda:select_bet_type("Dozen", "first", first_btn), width = 70, height = 35)
        first_btn.pack(side = "left", padx = 3)
        second_btn = self._create_sound_button(dozen_frame, "13-24", lambda:select_bet_type("Dozen", "second", second_btn), width = 70, height = 35)
        second_btn.pack(side = "left", padx = 3)
        third_btn = self._create_sound_button(dozen_frame, "25-36", lambda:select_bet_type("Dozen", "third", third_btn), width = 70, height = 35)
        third_btn.pack(side = "left", padx = 3)

        number_frame = customtkinter.CTkFrame(bet_types_frame, fg_color = "transparent")
        number_frame.pack(pady = 5)
        customtkinter.CTkLabel(number_frame, text = "Straight(36x):", font = customtkinter.CTkFont(size = 12)).pack(side = "left", padx = 5)
        number_entry = customtkinter.CTkEntry(number_frame, width = 60, placeholder_text = "0-36")
        number_entry.pack(side = "left", padx = 3)
        def select_number():
            try:
                num = int(number_entry.get())
                if 0 <=num <=36:
                    select_bet_type("Straight", num, None)
                else:
                    self._popup_show_info("Invalid", "Enter a number 0-36", sound = "error")
            except:
                self._popup_show_info("Invalid", "Enter a number 0-36", sound = "error")
        num_btn = self._create_sound_button(number_frame, "Select", select_number, width = 60, height = 35)
        num_btn.pack(side = "left", padx = 3)

        def play_roulette_tick():
            try:
                tick_path = os.path.join(os.path.dirname(__file__), "sounds", "misc", "roulette", "roulettetick.ogg")
                if os.path.exists(tick_path):
                    sound = pygame.mixer.Sound(tick_path)
                    sound.set_volume(0.5)
                    sound.play()
            except Exception:
                pass

        def spin_wheel():
            if game_state["spinning"]:
                return

            if selected_bet[0]is None:
                self._popup_show_info("No Bet", "Please select a bet type first.", sound = "error")
                return

            bet_str = bet_entry.get()
            try:
                bet = parse_display_price_to_usd(bet_str, round_to_int = True)
            except ValueError:
                self._popup_show_info("Invalid Bet", "Please enter a valid money amount.", sound = "error")
                return

            if bet <min_bet or bet >max_bet:
                self._popup_show_info("Invalid Bet", f"Bet must be between {format_price(min_bet)} and {format_price(max_bet)}.", sound = "error")
                return

            if bet >player_money[0]:
                self._popup_show_info("Insufficient Funds", "You don't have enough money for that bet.", sound = "error")
                return

            game_state["current_bet"]= bet
            game_state["bet_type"]= selected_bet[0]
            game_state["bet_value"]= selected_bet[1]
            game_state["spinning"]= True
            spin_btn.configure(state = "disabled")

            winning_idx = random.randint(0, len(roulette_numbers)-1)
            winning_number, winning_color = roulette_numbers[winning_idx]

            # Smooth eased spin: interpolate index position over full integer turns,
            # so the wheel lands exactly on the chosen winning index.
            start_idx = 0.0
            total_turns = random.randint(4, 6)
            final_idx = winning_idx + (len(roulette_numbers) * total_turns)
            total_steps = random.randint(620, 780)
            step = [0]
            last_tick_bucket = [int(start_idx)]

            last_tick_time = [_time_roulette.monotonic()]

            def animate_spin():
                if not game_state["ui_valid"]:
                    return

                if step[0] > total_steps:
                    num, col = roulette_numbers[winning_idx]
                    draw_roulette_wheel(float(winning_idx))
                    color_code = "#ff4444"if col =="red"else("#e0e0e0"if col =="black"else "#66ff99")
                    wheel_number_label.configure(text = f"{num}", text_color = color_code)
                    determine_result(winning_number, winning_color)
                    return

                t = step[0] / float(total_steps)
                # Ease-out only: starts faster, then decelerates smoothly.
                ease_out = 1.0 - pow(1.0 - t, 3)
                current_idx = start_idx + ((final_idx - start_idx) * ease_out)

                bucket = int(current_idx)
                if bucket != last_tick_bucket[0]:
                    now_tick = _time_roulette.monotonic()
                    # Throttle tick SFX to avoid clipping when segment updates are too fast.
                    if now_tick - last_tick_time[0] >= 0.045:
                        play_roulette_tick()
                        last_tick_time[0] = now_tick
                    last_tick_bucket[0] = bucket

                draw_roulette_wheel(current_idx)

                visible_idx = int(round(current_idx)) % len(roulette_numbers)
                num, col = roulette_numbers[visible_idx]
                color_code = "#ff4444"if col =="red"else("#e0e0e0"if col =="black"else "#66ff99")
                wheel_number_label.configure(text = f"{num}", text_color = color_code)
                step[0]+=1

                delay = 26
                self.root.after(delay, animate_spin)

            animate_spin()

        def determine_result(number, color):
            bet_type = game_state["bet_type"]
            bet_value = game_state["bet_value"]
            bet = game_state["current_bet"]
            won = False
            multiplier = 0

            if bet_type =="Color":
                if bet_value ==color:
                    won = True
                    multiplier = 2 if color !="green"else 35

            elif bet_type =="Parity":
                if number !=0:
                    is_odd = number %2 ==1
                    if(bet_value =="odd"and is_odd)or(bet_value =="even"and not is_odd):
                        won = True
                        multiplier = 2

            elif bet_type =="Range":
                if number !=0:
                    if(bet_value =="low"and 1 <=number <=18)or(bet_value =="high"and 19 <=number <=36):
                        won = True
                        multiplier = 2

            elif bet_type =="Dozen":
                if bet_value =="first"and 1 <=number <=12:
                    won = True
                    multiplier = 3
                elif bet_value =="second"and 13 <=number <=24:
                    won = True
                    multiplier = 3
                elif bet_value =="third"and 25 <=number <=36:
                    won = True
                    multiplier = 3

            elif bet_type =="Straight":
                if number ==bet_value:
                    won = True
                    multiplier = 36

            if won:
                winnings = bet *(multiplier -1)
                winnings = self._apply_casino_house_edge(store, "roulette", winnings)
                player_money[0]+=winnings
                if wagered_items:
                    player_money[0]+=item_bet_value[0]
                if record_game_cb:
                    record_game_cb(winnings)
                item_suffix = ""
                if item_bet_value[0]>0 and wagered_items:
                    item_suffix = f" | +{format_price(item_bet_value[0])} from items"
                result_label.configure(text = f"Winner! {number}({color}) - +{format_price(winnings +(item_bet_value[0]if wagered_items else 0))}{item_suffix}", text_color = "green")
            else:
                player_money[0]-=bet
                if record_game_cb:
                    record_game_cb(-bet)
                item_suffix = ""
                if wagered_items:
                    self._process_item_bet_loss(save_data, save_path, wagered_items)
                    item_suffix = f" | Lost {len(wagered_items)} item(s)"
                result_label.configure(text = f"Lost! {number}({color}) - -{format_price(bet)}{item_suffix}", text_color = "red")

            wagered_items.clear()
            item_bet_value[0]= 0
            try:
                item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")
            except Exception:
                pass

            save_money_cb()
            money_label.configure(text = f"Your Money: {format_price(player_money[0])}")
            update_money_cb()
            game_state["spinning"]= False
            spin_btn.configure(state = "normal")

        controls_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        controls_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        bet_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        bet_frame.pack(pady = 5)

        bet_label_entry = customtkinter.CTkLabel(bet_frame, text = "Bet Amount:", font = customtkinter.CTkFont(size = 14))
        bet_label_entry.pack(side = "left")

        bet_entry = customtkinter.CTkEntry(bet_frame, width = 140, placeholder_text = format_price(min_bet))
        bet_entry.pack(side = "left", padx = 5)
        bet_entry.insert(0, format_price(min_bet))

        if save_data and save_path:
            item_wager_label = customtkinter.CTkLabel(bet_frame, text = "Items Wagered: None", font = customtkinter.CTkFont(size = 11), text_color = "gray")
            item_wager_label.pack(side = "left", padx = 10)

            def update_item_wager_display():
                total = sum(int(e["item"].get("value", 0))for e in wagered_items)
                item_bet_value[0]= total
                if wagered_items:
                    item_wager_label.configure(text = f"Items Wagered: {len(wagered_items)}({format_price(total)})", text_color = "gold")
                else:
                    item_wager_label.configure(text = "Items Wagered: None", text_color = "gray")

            def open_item_wager():
                if game_state["spinning"]:
                    self._popup_show_info("Game Active", "Cannot change item wager while spinning.", sound = "popup")
                    return
                self._open_item_bet_dialog(save_data, wagered_items, update_item_wager_display)

            wager_btn = self._create_sound_button(bet_frame, "Wager Items", open_item_wager, width = 110, height = 30, font = customtkinter.CTkFont(size = 11), fg_color = "#8B4513", hover_color = "#654321")
            wager_btn.pack(side = "left", padx = 5)

        action_frame = customtkinter.CTkFrame(controls_frame, fg_color = "transparent")
        action_frame.pack(pady = 10)

        spin_btn = self._create_sound_button(action_frame, "Spin!", spin_wheel, width = 150, height = 50, font = customtkinter.CTkFont(size = 18, weight = "bold"), fg_color = "#8B4513", hover_color = "#654321")
        spin_btn.pack(pady = 5)

        def back_to_casino():
            game_state["ui_valid"]= False
            self._open_casino_interface(store, table_data)

        back_btn = self._create_sound_button(controls_frame, "Back to Casino", back_to_casino, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(pady = 10)

    def _open_poker_lobby(self, store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb = None, casino_stats = None, save_data = None, save_path = None):
        self._clear_window()

        self.root.grid_rowconfigure(0, weight = 1)
        self.root.grid_columnconfigure(0, weight = 1)

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.grid(row = 0, column = 0, sticky = "nsew")
        main_frame.grid_columnconfigure(0, weight = 1)
        main_frame.grid_rowconfigure(1, weight = 1)

        header_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        header_frame.grid(row = 0, column = 0, sticky = "ew", padx = 20, pady = 10)

        title_label = customtkinter.CTkLabel(header_frame, text = "Poker Room", font = customtkinter.CTkFont(size = 24, weight = "bold"))
        title_label.pack(pady =(10, 5))

        money_label = customtkinter.CTkLabel(header_frame, text = f"Your Money: {format_price(player_money[0])}", font = customtkinter.CTkFont(size = 16, weight = "bold"), text_color = "green")
        money_label.pack(pady = 5)

        content_frame = customtkinter.CTkFrame(main_frame)
        content_frame.grid(row = 1, column = 0, sticky = "nsew", padx = 20, pady = 10)
        content_frame.grid_columnconfigure(0, weight = 1)

        games_label = customtkinter.CTkLabel(content_frame, text = "Select Poker Variant", font = customtkinter.CTkFont(size = 18, weight = "bold"))
        games_label.pack(pady = 20)

        def open_five_card_draw():
            self._open_poker_game(store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb, casino_stats, variant = "five_card_draw", save_data = save_data, save_path = save_path)

        def open_five_card_stud():
            self._open_poker_game(store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb, casino_stats, variant = "five_card_stud", save_data = save_data, save_path = save_path)

        def open_seven_card_stud():
            self._open_poker_game(store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb, casino_stats, variant = "seven_card_stud", save_data = save_data, save_path = save_path)

        def open_texas_holdem():
            self._open_poker_game(store, player_money, update_money_cb, save_money_cb, min_bet, max_bet, music_channel, table_data, record_game_cb, casino_stats, variant = "texas_holdem", save_data = save_data, save_path = save_path)

        fcd_btn = self._create_sound_button(content_frame, "5 Card Draw", open_five_card_draw, width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
        fcd_btn.pack(pady = 10)
        customtkinter.CTkLabel(content_frame, text = "Classic draw poker - draw to improve your hand", font = customtkinter.CTkFont(size = 10), text_color = "gray").pack()

        fcs_btn = self._create_sound_button(content_frame, "5 Card Stud", open_five_card_stud, width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
        fcs_btn.pack(pady = 10)
        customtkinter.CTkLabel(content_frame, text = "One hole card, four face-up cards", font = customtkinter.CTkFont(size = 10), text_color = "gray").pack()

        scs_btn = self._create_sound_button(content_frame, "7 Card Stud", open_seven_card_stud, width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
        scs_btn.pack(pady = 10)
        customtkinter.CTkLabel(content_frame, text = "Two hole cards, four face-up, one final hole card", font = customtkinter.CTkFont(size = 10), text_color = "gray").pack()

        th_btn = self._create_sound_button(content_frame, "Texas Hold'em", open_texas_holdem, width = 300, height = 50, font = customtkinter.CTkFont(size = 16))
        th_btn.pack(pady = 10)
        customtkinter.CTkLabel(content_frame, text = "Two hole cards + five community cards", font = customtkinter.CTkFont(size = 10), text_color = "gray").pack()

        button_frame = customtkinter.CTkFrame(main_frame, fg_color = "transparent")
        button_frame.grid(row = 2, column = 0, sticky = "ew", padx = 20, pady = 10)

        def back_to_casino():
            self._open_casino_interface(store, table_data)

        back_btn = self._create_sound_button(button_frame, "Back to Casino", back_to_casino, width = 200, height = 40, font = customtkinter.CTkFont(size = 14))
        back_btn.pack(pady = 10)

    def _roll_d20_dice(self, num_rolls):

        rolls =[secrets.randbelow(20)+1 for _ in range(num_rolls)]

        n = len(rolls)
        if n ==0:
            return rolls, 0
        avg = sum(rolls)/n
        rounded = int(math.floor(avg +0.5))

        return rolls, rounded
