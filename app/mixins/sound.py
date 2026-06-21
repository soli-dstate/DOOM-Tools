"""SoundMixin — App methods for the "sound" feature area."""
from app.foundation import *
import logging


class SoundMixin:

    def _play_ui_sound(self, sound_filename):
        sound_path = os.path.join("sounds", "ui", sound_filename +".ogg")
        if os.path.exists(sound_path):
            try:
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
                logging.debug(f"Played UI sound: {sound_filename}")
            except Exception as e:
                logging.warning(f"Failed to play sound '{sound_filename}': {e}")
    def _create_sound_button(self, parent, text, command, **kwargs):
        def safe_command():
            try:
                self._play_ui_sound("click")
                command()
            except Exception as e:
                try:
                    safe_text = str(text).encode("ascii", errors = "backslashreplace").decode("ascii")
                    safe_err = str(e).encode("ascii", errors = "backslashreplace").decode("ascii")
                except Exception:
                    safe_text = "<unprintable>"
                    safe_err = "<unprintable>"
                logging.exception("Button command failed for '%s': %s", safe_text, safe_err)
        button = customtkinter.CTkButton(
        parent, text = text, command = safe_command, **kwargs
        )
        def on_hover(e):
            if button.cget("state")!="disabled":
                self._play_ui_sound("hover")
        button.bind("<Enter>", on_hover)
        return button
    def _safe_sound_play(self, directory, sound_filename, block = False):

        if os.path.isabs(sound_filename)or sound_filename.endswith((".wav", ".ogg")):
            sound_path = sound_filename
        else:
            sound_path = os.path.join("sounds", directory, sound_filename +".ogg")

        try:
            exists = os.path.exists(sound_path)
        except Exception:
            exists = False
        logging.debug(f"_safe_sound_play: resolved '{sound_filename}' -> '{sound_path}', exists={exists}, block={block}")

        if os.path.exists(sound_path):
            try:

                if not hasattr(self, "_sound_cache"):
                    self._sound_cache = {}
                cache = self._sound_cache
                sound = cache.get(sound_path)
                if sound is None:
                    try:
                        sound = pygame.mixer.Sound(sound_path)
                    except Exception as e:
                        logging.warning(f"Failed to load sound '{sound_path}': {e}")
                        return
                    cache[sound_path]= sound

                if not hasattr(self, '_muffled_sound_cache'):
                    try:
                        self._muffled_sound_cache = {}
                    except Exception:
                        self._muffled_sound_cache = {}

                try:
                    vol = 1.0

                    if getattr(self, '_flashbang_mute', False):
                        base = os.path.basename(sound_path).lower()

                        if('ring'in base)or('explosion'in base)or('flashbang'in base):
                            vol = 1.0
                        else:
                            vol = float(getattr(self, '_flashbang_volume', 0.0))

                    try:
                        if getattr(self, '_bang_muffle', False):
                            base = os.path.basename(sound_path).lower()
                            is_bang =('explosion'in base)or('flashbang'in base)or('bang'in base)
                            logging.debug(f"_safe_sound_play: bang_muffle active, filename='{base}', is_bang={is_bang}")
                            if is_bang:
                                muffled = None
                                try:
                                    mcache = getattr(self, '_muffled_sound_cache', {})
                                    muffled = mcache.get(sound_path)
                                except Exception:
                                    muffled = None

                                if muffled is None:
                                    try:
                                        import numpy as _np
                                        from numpy.fft import rfft, irfft, fftfreq
                                        snd_arr = None
                                        try:
                                            snd_arr = pygame.sndarray.array(sound)
                                        except Exception:
                                            snd_arr = None

                                        if snd_arr is None:
                                            muffled = None
                                        else:
                                            try:
                                                mixer_info = pygame.mixer.get_init()
                                                sr = int(mixer_info[0])if mixer_info and mixer_info[0]else 44100
                                            except Exception:
                                                sr = 44100

                                            orig_dtype = snd_arr.dtype
                                            snd_float = snd_arr.astype(_np.float32)
                                            if snd_float.ndim ==1:
                                                channels = 1
                                                channels_data =[snd_float]
                                            else:
                                                channels = snd_float.shape[1]
                                                channels_data =[snd_float[:, c]for c in range(channels)]

                                            processed =[]
                                            cutoff = float(getattr(self, '_bang_muffle_cutoff', 3000.0))
                                            for chdata in channels_data:
                                                n = chdata.size
                                                spec = rfft(chdata)
                                                freqs = fftfreq(n, 1.0 /sr)[:spec.size]
                                                spec[freqs >cutoff]= 0
                                                proc = irfft(spec)
                                                ir_len = int(0.03 *sr)
                                                if ir_len >1:
                                                    ir = _np.exp(-_np.linspace(0, 4, ir_len))
                                                    ir = ir /(ir.sum()+1e-9)
                                                    try:
                                                        proc = _np.convolve(proc, ir, mode = 'same')
                                                    except Exception:
                                                        logging.exception("Suppressed exception")
                                                processed.append(proc)

                                            if channels ==1:
                                                proc_arr = processed[0]
                                            else:
                                                proc_arr = _np.vstack(processed).T

                                            try:
                                                if _np.issubdtype(orig_dtype, _np.integer):
                                                    info = _np.iinfo(orig_dtype)
                                                    proc_arr = _np.clip(proc_arr, info.min, info.max)
                                                else:
                                                    proc_arr = _np.clip(proc_arr, -1.0, 1.0)
                                                proc_arr = proc_arr.astype(orig_dtype)
                                            except Exception:
                                                try:
                                                    proc_arr = proc_arr.astype(orig_dtype)
                                                except Exception:
                                                    logging.exception("Suppressed exception")

                                            try:
                                                muffled_sound = pygame.sndarray.make_sound(proc_arr)
                                                try:
                                                    self._muffled_sound_cache[sound_path]= muffled_sound
                                                except Exception:
                                                    logging.exception("Suppressed exception")
                                                muffled = muffled_sound
                                            except Exception:
                                                muffled = None
                                    except Exception:
                                        muffled = None

                                if muffled is not None:
                                    sound = muffled
                                    logging.debug(f"_safe_sound_play: using synthesized muffled sound for {sound_path}")
                                else:
                                    mv = float(getattr(self, '_bang_muffle_volume', 0.45))
                                    vol = min(vol, mv)
                                    logging.debug(f"_safe_sound_play: no synthesized muffled sound, capping vol to {vol}")
                    except Exception:
                        logging.exception('_safe_sound_play: error during muffle handling')
                        pass
                    final_vol = max(0.0, min(1.0, vol))
                    try:
                        sound.set_volume(final_vol)
                    except Exception:
                        logging.debug('_safe_sound_play: failed to set volume on sound object')
                    logging.debug(f"_safe_sound_play: final volume set to {final_vol} for '{sound_path}'(flashbang_mute={getattr(self, '_flashbang_mute', False)}, bang_muffle={getattr(self, '_bang_muffle', False)})")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    weather_ch = getattr(self, '_weather_ambient_channel', None)
                    ch = None
                    if weather_ch is not None:
                        ch = pygame.mixer.find_channel()
                        if ch is None or ch == weather_ch:
                            ch = None
                            for i in range(pygame.mixer.get_num_channels() - 2, -1, -1):
                                try:
                                    alt = pygame.mixer.Channel(i)
                                    if not alt.get_busy() and alt != weather_ch:
                                        ch = alt
                                        break
                                except Exception:
                                    logging.exception("Suppressed exception")
                                    continue
                            if ch is None:
                                for i in range(pygame.mixer.get_num_channels() - 2, -1, -1):
                                    try:
                                        alt = pygame.mixer.Channel(i)
                                        if alt != weather_ch:
                                            ch = alt
                                            break
                                    except Exception:
                                        logging.exception("Suppressed exception")
                                        continue
                        if ch:
                            ch.play(sound)
                            logging.debug(f"Played sound(reserved-safe channel) file: {sound_path}")
                        else:
                            logging.warning(f"No channel available to play sound: {sound_path}")
                    else:
                        ch = sound.play()
                        if ch is None:
                            ch = pygame.mixer.find_channel(True)
                            if ch:
                                ch.play(sound)
                                logging.debug(f"Played sound(forced channel) file: {sound_path}")
                            else:
                                logging.warning(f"No channel available to play sound: {sound_path}")
                        else:
                            logging.debug(f"Played sound file: {sound_path}")

                    if block:
                        try:
                            length = sound.get_length()
                        except Exception:
                            length = None
                        if length and length >0:
                            time.sleep(length)
                        else:

                            try:
                                if ch:
                                    while ch.get_busy():
                                        time.sleep(0.01)
                            except Exception:
                                logging.exception("Suppressed exception")
                except Exception as e:
                    logging.warning(f"Failed to play sound '{sound_path}': {e}")
            except Exception as e:
                logging.warning(f"Failed to play sound '{sound_path}': {e}")

    def _play_pitched_sound(self, sound_path, *, volume = 1.0, pitch = 1.0):

        try:
            if not os.path.exists(sound_path):
                return False

            base_sound = pygame.mixer.Sound(sound_path)
            try:
                base_sound.set_volume(max(0.0, min(1.0, float(volume))))
            except Exception:
                logging.exception("Suppressed exception")

            play_sound = base_sound
            try:
                pitch = float(pitch)
            except Exception:
                pitch = 1.0

            if abs(pitch - 1.0) > 0.001:
                try:
                    sound_array = pygame.sndarray.array(base_sound)
                    if sound_array.ndim == 1:
                        source = sound_array.astype(np.float32)
                        source_len = int(source.shape[0])
                        target_len = max(1, int(round(source_len / pitch)))
                        x_old = np.arange(source_len, dtype = np.float32)
                        x_new = np.linspace(0, source_len - 1, target_len, dtype = np.float32)
                        pitched = np.interp(x_new, x_old, source).astype(sound_array.dtype)
                        play_sound = pygame.sndarray.make_sound(np.ascontiguousarray(pitched))
                    else:
                        source_len = int(sound_array.shape[0])
                        target_len = max(1, int(round(source_len / pitch)))
                        x_old = np.arange(source_len, dtype = np.float32)
                        x_new = np.linspace(0, source_len - 1, target_len, dtype = np.float32)
                        channels = []
                        for ch_idx in range(sound_array.shape[1]):
                            source = sound_array[:, ch_idx].astype(np.float32)
                            channels.append(np.interp(x_new, x_old, source))
                        pitched = np.stack(channels, axis = 1).astype(sound_array.dtype)
                        play_sound = pygame.sndarray.make_sound(np.ascontiguousarray(pitched))
                    try:
                        play_sound.set_volume(max(0.0, min(1.0, float(volume))))
                    except Exception:
                        logging.exception("Suppressed exception")
                except Exception:
                    play_sound = base_sound

            channel = pygame.mixer.find_channel(True)
            if channel:
                channel.play(play_sound)
            else:
                play_sound.play()
            return True
        except Exception:
            logging.exception("Failed to play pitched sound: %s", sound_path)
            return False

    def _get_firearm_sound_folder(self, weapon):

        try:
            if isinstance(weapon, dict):
                sf = weapon.get("sounds")or weapon.get("sound_folder")or weapon.get("fire_sounds")or weapon.get("fire_sound")
                if sf:
                    if isinstance(sf, (list, tuple)):
                        sf = sf[0]if sf else None
                    if sf:
                        return sf
        except Exception:
            logging.exception("Suppressed exception")

        caliber = weapon.get("caliber", [])[0]if weapon.get("caliber")else None

        if not caliber:
            return None

        caliber_map = {
        "5.56x45mm NATO":"556",
        ".45 ACP":"45acp",
        "9x19mm Parabellum":"9x19",
        "12 Gauge":"12gauge",
        "7.62x51mm NATO":"762_51",
        "7.62x39mm":"762_39",
        "7.62x54mmR":"762_54",
        ".308 Winchester":"308",
        ".223 Remington":"223",
        ".380 ACP":"380acp",
        "5.45x39mm":"545_39",
        "9x18mm Makarov":"9x18",
        ".357 Magnum":"357mag",
        ".44 Magnum":"44mag",
        ".38 Special":"38special",
        ".50 AE":"50ae",
        "20 Gauge":"20gauge",
        ".410 Bore":"410bore",
        ".45-70 Government":"45_70",
        ".30-06 Springfield":"30_06",
        ".30-30 Winchester":"30_30",
        ".277 Wolverine":"277baker",
        ".224 Valkyrie":"224baker",
        ".303 British":"303"
        }

        caliber_map.update({
        "6.5x45mm":"277baker",
        "6.5x45mm Colt":"277baker",
        "6.5x45 Colt":"277baker",
        "6.5x45":"277baker",
        "5.7x28mm":"224baker",
        "5.7x28mm NATO":"224baker",
        "5.7x28":"224baker",
        })

        extra_map = {
        "10mm Auto":"45acp",
        "10mm":"45acp",
        ".10mm":"45acp"
        }

        return caliber_map.get(caliber)or extra_map.get(caliber)

    def _caliber_to_sound_folder(self, caliber):

        if not caliber or not isinstance(caliber, str):
            return None

        try:
            td = globals().get('table_data')or {}
            ammo_tables = td.get('tables', {}).get('ammunition', [])if isinstance(td, dict)else[]
            if isinstance(ammo_tables, list):
                cal_lower = caliber.strip().lower()
                for ammo_entry in ammo_tables:
                    if not isinstance(ammo_entry, dict):
                        continue
                    a_cal = ammo_entry.get('caliber')
                    if not a_cal:
                        continue
                    if isinstance(a_cal, (list, tuple)):
                        match = any(str(x).strip().lower()==cal_lower for x in a_cal)
                    else:
                        match = str(a_cal).strip().lower()==cal_lower
                    if match and ammo_entry.get('sounds'):
                        return str(ammo_entry.get('sounds'))
        except Exception:
            logging.exception("Suppressed exception")

        caliber_map = {
        "5.56x45mm NATO":"556",
        ".45 ACP":"45acp",
        "9x19mm Parabellum":"9x19",
        "12 Gauge":"12gauge",
        "7.62x51mm NATO":"762_51",
        "7.62x39mm":"762_39",
        "7.62x39mm Soviet":"762_39",
        "7.62x54mmR":"762_54",
        ".308 Winchester":"308",
        ".223 Remington":"223",
        ".380 ACP":"380acp",
        "5.45x39mm":"545_39",
        "5.45x39mm Soviet":"545_39",
        "9x18mm Makarov":"9x18",
        ".357 Magnum":"357mag",
        ".44 Magnum":"44mag",
        ".38 Special":"38special",
        ".50 AE":"50ae",
        "20 Gauge":"20gauge",
        ".410 Bore":"410bore",
        ".45-70 Government":"45_70",
        ".30-06 Springfield":"30_06",
        ".30-30 Winchester":"30_30",
        ".277 Wolverine":"277baker",
        ".224 Valkyrie":"224baker",
        ".303 British":"303",
        "6.5x45mm":"308",
        "6.5x45mm Colt":"308",
        "6.5x45 Colt":"308",
        "6.5x45":"308",
        "5.7x28mm":"223",
        "5.7x28mm NATO":"223",
        "5.7x28":"223",
        "10mm Auto":"45acp",
        "10mm":"45acp",
        ".10mm":"45acp",
        ".40 S&W":"45acp",
        ".30 Carbine":"30_30",
        }

        return caliber_map.get(caliber)

    def _play_firearm_sound(self, weapon, sound_type = "fire", fired_round = None):

        try:

            try:
                if isinstance(weapon, dict):

                    sf = weapon.get("sounds")or weapon.get("sound_folder")or weapon.get("ammo_type")
                    if isinstance(sf, str)and sf:

                        if sf.lower()in("40mm_grenade", "40mm"):
                            weapon_platform_hack = "40mm_grenade"

                            weapon.setdefault("platform", weapon_platform_hack)

                            weapon.setdefault("sound_folder", "40mm_grenade")
                            weapon.setdefault("sounds", "40mm_grenade")
                    else:

                        name =(weapon.get("name")or "").lower()
                        calib = weapon.get("caliber")
                        calib_ok = False
                        if isinstance(calib, (list, tuple)):
                            for c in calib:
                                if isinstance(c, str)and "40"in c and "mm"in c:
                                    calib_ok = True
                                    break
                        elif isinstance(calib, str)and "40"in calib and "mm"in calib:
                            calib_ok = True
                        if calib_ok or "40mm"in name or "40x46"in name or "40 x 46"in name:
                            weapon.setdefault("platform", "40mm_grenade")
                            weapon.setdefault("sound_folder", "40mm_grenade")
                            weapon.setdefault("sounds", "40mm_grenade")
            except Exception:
                logging.exception("Suppressed exception")

            if sound_type =="equip"and weapon.get("custom_equip_sound"):
                sound_path = weapon["custom_equip_sound"]
                if os.path.exists(sound_path):
                    self._safe_sound_play("", sound_path)
                    return

            sound_folder = self._get_firearm_sound_folder(weapon)

            raw_platform = weapon.get("platform", "")or ""
            if isinstance(raw_platform, (list, tuple)):
                raw_platform = raw_platform[0]if raw_platform else ""

            platform_folder = str(raw_platform).lower().replace('/', '_')if raw_platform else None

            try:
                pf_key =(weapon.get("platform")or weapon.get("underbarrel_platform")or "")
                if isinstance(pf_key, (list, tuple)):
                    pf_key = pf_key[0]if pf_key else ""
                if pf_key and pf_key in self.PLATFORM_DEFAULTS:
                    mapped_folder = self.PLATFORM_DEFAULTS[pf_key].get("reload_sound_folder")
                    if mapped_folder:
                        wf_map = os.path.join("sounds", "firearms", "weaponsounds", str(mapped_folder).lower().replace('/', '_'))
                        candidates =[]
                        if sound_type =="equip":
                            candidates = glob.glob(os.path.join(wf_map, "equip*.ogg"))+glob.glob(os.path.join(wf_map, "draw*.ogg"))
                        elif sound_type =="reload":
                            candidates = glob.glob(os.path.join(wf_map, "reload*.ogg"))+glob.glob(os.path.join(wf_map, "load*.ogg"))+glob.glob(os.path.join(wf_map, "pump*.ogg"))
                        else:

                            candidates = glob.glob(os.path.join(wf_map, f"{sound_type}*.ogg"))
                        if candidates:
                            self._safe_sound_play("", random.choice(candidates), block =(sound_type in("reload", "unselect", "holster")))
                            return
            except Exception:
                logging.exception("Suppressed exception")

            if not sound_folder:

                if platform_folder:
                    wf_rel = os.path.join("weaponsounds", platform_folder)
                    wf_path = os.path.join("sounds", "firearms", wf_rel)
                    if os.path.isdir(wf_path):
                        sound_folder = wf_rel
                    else:

                        direct_pf = os.path.join("sounds", "firearms", platform_folder)
                        if os.path.isdir(direct_pf):
                            sound_folder = platform_folder

            if sound_type =="equip":

                tried = False
                if platform_folder:
                    wf = os.path.join("sounds", "firearms", "weaponsounds", platform_folder)
                    candidates = glob.glob(os.path.join(wf, "equip*.ogg"))+glob.glob(os.path.join(wf, "draw*.ogg"))
                    if candidates:
                        sound_file = random.choice(candidates)
                        self._safe_sound_play("", sound_file)
                        return
                    tried = True

                if sound_folder:
                    base_equip_candidates = glob.glob(os.path.join("sounds", "firearms", sound_folder, "equip*.ogg"))+glob.glob(os.path.join("sounds", "firearms", sound_folder, "draw*.ogg"))
                    if base_equip_candidates:
                        sound_file = random.choice(base_equip_candidates)
                        self._safe_sound_play("", sound_file)
                        return

                uni_candidates = glob.glob(os.path.join("sounds", "firearms", "universal", "equip*.ogg"))+glob.glob(os.path.join("sounds", "firearms", "universal", "draw*.ogg"))
                if uni_candidates:
                    sound_file = random.choice(uni_candidates)
                    self._safe_sound_play("", sound_file)
                    return

                logging.info(f"No equip/draw sound found for {weapon.get('name')}(checked platform, {sound_folder}, and universal)")
                return

            is_suppressed = self._check_weapon_suppressed(weapon)

            base_path = f"sounds/firearms/{sound_folder}"if sound_folder else None
            wf_platform = None
            if platform_folder:
                wf_platform = os.path.join("sounds", "firearms", "weaponsounds", platform_folder)

            def _dbg(msg, *args):
                try:
                    gv = globals().get('global_variables')or {}
                    if gv.get('debugmode', {}).get('value'):
                        logging.debug(msg, *args)
                except Exception:
                    logging.debug(msg, *args)

            def _select_from_folder(folder):
                try:
                    if not folder or not os.path.isdir(folder):
                        _dbg("_select_from_folder: missing folder %s", folder)
                        return None
                    _dbg("_select_from_folder: scanning folder %s(suppressed=%s)", folder, is_suppressed)
                    if is_suppressed:
                        cands = glob.glob(os.path.join(folder, "fire*_suppressed.wav"))+glob.glob(os.path.join(folder, "fire*_suppressed.ogg"))
                        _dbg("_select_from_folder: found %d suppressed candidates in %s", len(cands), folder)
                        if cands:
                            sel = random.choice(cands)
                            _dbg("_select_from_folder: selected %s", sel)
                            return sel
                        _dbg("_select_from_folder: no suppressed candidates in %s", folder)
                        return None
                    else:
                        cands = glob.glob(os.path.join(folder, "fire*.wav"))+glob.glob(os.path.join(folder, "fire*.ogg"))

                        cands =[f for f in cands if "_suppressed"not in os.path.basename(f)]
                        _dbg("_select_from_folder: found %d non-suppressed candidates in %s", len(cands), folder)
                        if cands:
                            sel = random.choice(cands)
                            _dbg("_select_from_folder: selected %s", sel)
                            return sel
                        _dbg("_select_from_folder: no non-suppressed candidates in %s", folder)
                        return None
                except Exception:
                    _dbg("_select_from_folder: exception scanning %s", folder)
                    return None

            if sound_type =="fire"and wf_platform:
                sel = _select_from_folder(wf_platform)
                if sel:
                    self._safe_sound_play("", sel)
                    return

            ammo_folder = None
            try:

                if fired_round and isinstance(fired_round, dict):
                    if fired_round.get("sounds"):
                        ammo_folder = fired_round.get("sounds")
                    elif fired_round.get("caliber"):

                        round_cal = fired_round.get("caliber")
                        if isinstance(round_cal, (list, tuple)):
                            round_cal = round_cal[0]if round_cal else None
                        if round_cal:
                            ammo_folder = self._caliber_to_sound_folder(round_cal)

                if not ammo_folder:
                    ch = weapon.get("chambered")if isinstance(weapon, dict)else None
                    if isinstance(ch, dict):
                        if ch.get("sounds"):
                            ammo_folder = ch.get("sounds")
                        elif ch.get("caliber"):
                            ch_cal = ch.get("caliber")
                            if isinstance(ch_cal, (list, tuple)):
                                ch_cal = ch_cal[0]if ch_cal else None
                            if ch_cal:
                                ammo_folder = self._caliber_to_sound_folder(ch_cal)

                if not ammo_folder:
                    loaded = weapon.get("loaded")if isinstance(weapon, dict)else None
                    if isinstance(loaded, dict):
                        rds = loaded.get("rounds")or[]
                        if isinstance(rds, list)and rds:
                            first = rds[0]
                            if isinstance(first, dict):
                                if first.get("sounds"):
                                    ammo_folder = first.get("sounds")
                                elif first.get("caliber"):
                                    first_cal = first.get("caliber")
                                    if isinstance(first_cal, (list, tuple)):
                                        first_cal = first_cal[0]if first_cal else None
                                    if first_cal:
                                        ammo_folder = self._caliber_to_sound_folder(first_cal)

                if not ammo_folder:
                    at = weapon.get("ammo_type")or weapon.get("ammo")
                    if isinstance(at, str)and at:
                        ammo_folder = at
            except Exception:
                ammo_folder = None

            if ammo_folder:

                wf_ammo_map = os.path.join("sounds", "firearms", "weaponsounds", str(ammo_folder).lower().replace('/', '_'))
                sel = _select_from_folder(wf_ammo_map)
                if sel:
                    self._safe_sound_play("", sel)
                    return
                wf_ammo = os.path.join("sounds", "firearms", str(ammo_folder))
                sel = _select_from_folder(wf_ammo)
                if sel:
                    self._safe_sound_play("", sel)
                    return

            try:
                if not ammo_folder:
                    td = globals().get('table_data')or {}
                    ammo_tables = td.get('tables', {}).get('ammunition', [])if isinstance(td, dict)else[]

                    cal_list = weapon.get('caliber')if isinstance(weapon, dict)else None
                    if cal_list and isinstance(ammo_tables, list):
                        for ammo_entry in ammo_tables:
                            try:
                                if not isinstance(ammo_entry, dict):
                                    continue
                                a_cal = ammo_entry.get('caliber')
                                if not a_cal:
                                    continue

                                if isinstance(a_cal, (list, tuple)):
                                    match = any(str(x).strip().lower()in[str(c).strip().lower()for c in(cal_list or[])]for x in a_cal)
                                else:
                                    match = any(str(a_cal).strip().lower()==str(c).strip().lower()for c in(cal_list or[]))
                                if match and ammo_entry.get('sounds'):

                                    af = str(ammo_entry.get('sounds'))
                                    wf_ammo_map = os.path.join('sounds', 'firearms', 'weaponsounds', af.lower().replace('/', '_'))
                                    sel = _select_from_folder(wf_ammo_map)
                                    if sel:
                                        self._safe_sound_play('', sel)
                                        return
                                    wf_ammo2 = os.path.join('sounds', 'firearms', af.lower())
                                    sel = _select_from_folder(wf_ammo2)
                                    if sel:
                                        self._safe_sound_play('', sel)
                                        return
                            except Exception:
                                logging.exception("Suppressed exception")
            except Exception:
                logging.exception("Suppressed exception")

            try:
                if weapon.get("has_ammo_in_pool")is False:
                    fs = weapon.get("fire_sounds")or weapon.get("fire_sound")
                    if fs:

                        wf = os.path.join("sounds", "firearms", "weaponsounds", str(fs).lower().replace('/', '_'))
                        sel = _select_from_folder(wf)
                        if sel:
                            logging.debug("Fire sound selected(weapon.fire_sounds): %s", sel)
                            self._safe_sound_play("", sel)
                            return
                        wf2 = os.path.join("sounds", "firearms", str(fs).lower())
                        sel = _select_from_folder(wf2)
                        if sel:
                            logging.debug("Fire sound selected(weapon.fire_sounds): %s", sel)
                            self._safe_sound_play("", sel)
                            return
            except Exception:
                logging.exception("Suppressed exception")

            if base_path:
                sel = _select_from_folder(base_path)
                if sel:
                    self._safe_sound_play("", sel)
                    return

            subtype = weapon.get("subtype", "")

            if is_suppressed:

                if subtype =="shotgun":
                    shotgun_supp = glob.glob("sounds/firearms/universal/shotgunfire_suppressed.wav")+glob.glob("sounds/firearms/universal/shotgunfire_suppressed.ogg")
                    if shotgun_supp:
                        self._safe_sound_play("", random.choice(shotgun_supp))
                        return

                    rifle_supp = glob.glob("sounds/firearms/universal/riflefire_suppressed.wav")+glob.glob("sounds/firearms/universal/riflefire_suppressed.ogg")
                    if rifle_supp:
                        self._safe_sound_play("", random.choice(rifle_supp))
                        return
                elif subtype in["rifle", "mg"]:
                    rifle_supp = glob.glob("sounds/firearms/universal/riflefire_suppressed.wav")+glob.glob("sounds/firearms/universal/riflefire_suppressed.ogg")
                    if rifle_supp:
                        self._safe_sound_play("", random.choice(rifle_supp))
                        return
                elif subtype in["pistol", "smg"]:
                    pistol_supp = glob.glob("sounds/firearms/universal/pistolfire_suppressed.wav")+glob.glob("sounds/firearms/universal/pistolfire_suppressed.ogg")
                    if pistol_supp:
                        self._safe_sound_play("", random.choice(pistol_supp))
                        return
            else:

                if subtype =="shotgun":
                    shot = glob.glob("sounds/firearms/universal/shotgunfire.wav")
                    if shot:
                        self._safe_sound_play("", random.choice(shot))
                        return

                    rifle = glob.glob("sounds/firearms/universal/riflefire.wav")
                    if rifle:
                        self._safe_sound_play("", random.choice(rifle))
                        return
                elif subtype in["rifle", "mg"]:
                    rifle = glob.glob("sounds/firearms/universal/riflefire.wav")
                    if rifle:
                        self._safe_sound_play("", random.choice(rifle))
                        return
                elif subtype in["pistol", "smg"]:
                    pistol = glob.glob("sounds/firearms/universal/pistolfire.wav")
                    if pistol:
                        self._safe_sound_play("", random.choice(pistol))
                        return

            logging.warning(f"No fire sounds found for platform_folder={platform_folder} sound_folder={sound_folder} ammo_folder={ammo_folder}")

        except Exception as e:
            logging.error(f"Error playing firearm sound: {e}")

    def _play_weapon_action_sound(self, weapon, action_type, block = False):

        try:
            platform = weapon.get("platform", "").lower()
            mag_type = weapon.get("magazinetype", "").lower()

            platform_folder = platform.replace('/', '_') if platform else None

            _df_mag_snd = weapon.get("dualfeed") and isinstance(weapon.get("loaded"), dict) and weapon.get("loaded")
            is_belt =(("belt"in mag_type)or("belt"in(platform or ""))or("m249"in(platform or ""))) and not _df_mag_snd

            should_block = bool(block)

            try:
                weapon_type = str(weapon.get("type")or "").lower()
                if weapon_type =="caseless":

                    if any(k in action_type.lower()for k in("eject", "shelleject", "caseeject")):
                        logging.debug("Skipping ejection sound for caseless weapon: %s", weapon.get("name"))
                        return
            except Exception:
                logging.exception("Suppressed exception")

            try:
                reload_actions =("reload", "magin", "magout", "magdrop", "pouchout", "pouchin", "boxin", "boxout", "coveropen", "coverclose")
                if action_type in reload_actions:

                    fs = weapon.get("fire_sounds")or weapon.get("sounds")or weapon.get("sound_folder")or weapon.get("reload_sounds")
                    candidates =[]

                    if fs:
                        wf = os.path.join("sounds", "firearms", str(fs).lower())
                        candidates = glob.glob(os.path.join(wf, f"{action_type}*.ogg"))+glob.glob(os.path.join(wf, f"{action_type}*.wav"))
                        if not candidates:

                            wf2 = os.path.join("sounds", "firearms", "weaponsounds", str(fs).lower().replace('/', '_'))
                            candidates = glob.glob(os.path.join(wf2, f"{action_type}*.ogg"))+glob.glob(os.path.join(wf2, f"{action_type}*.wav"))

                    if not candidates and platform_folder:
                        wf = os.path.join("sounds", "firearms", "weaponsounds", platform_folder)
                        candidates = glob.glob(os.path.join(wf, f"{action_type}*.ogg"))+glob.glob(os.path.join(wf, f"{action_type}*.wav"))

                    if not candidates:
                        uni = os.path.join("sounds", "firearms", "universal")

                        action_map = {
                        "magin":["riflemagin*.ogg", "pistolmagin*.ogg", "magin*.ogg"],
                        "magout":["riflemagout*.ogg", "pistolmagout*.ogg", "magout*.ogg"],
                        "magdrop":["magdrop*.ogg"],
                        "pouchout":["pouchout*.ogg"],
                        "pouchin":["pouchin*.ogg"],
                        "reload":["reload*.ogg", "riflemagin*.ogg"],
                        }
                        patterns = action_map.get(action_type, [f"{action_type}*.ogg"])
                        for pat in patterns:
                            candidates +=glob.glob(os.path.join(uni, pat))
                    if candidates:
                        sound_file = random.choice(candidates)
                        logging.debug("Reload action sound: %s -> %s", action_type, sound_file)

                        if action_type =="magin":

                            try:
                                self._safe_sound_play("", sound_file, block = True)
                            except Exception:
                                try:
                                    self._safe_sound_play("", sound_file, block = should_block)
                                except Exception:
                                    logging.exception("Suppressed exception")

                            try:
                                if should_block:
                                    time.sleep(random.uniform(0.15, 0.35))
                                else:
                                    time.sleep(random.uniform(0.05, 0.12))
                            except Exception:
                                logging.exception("Suppressed exception")
                        else:
                            self._safe_sound_play("", sound_file, block = should_block)
                        return
            except Exception:
                logging.exception("Error in reload action sound lookup")
                pass

            try:
                if weapon.get("has_ammo_in_pool")is False:
                    fs = weapon.get("reload_sounds")or weapon.get("action_sounds")or weapon.get("sounds")or weapon.get("sound_folder")or weapon.get("fire_sounds")
                    if fs:
                        wf = os.path.join("sounds", "firearms", "weaponsounds", str(fs).lower().replace('/', '_'))
                        candidates = glob.glob(os.path.join(wf, f"{action_type}*.ogg"))+glob.glob(os.path.join(wf, f"{action_type}*.wav"))
                        if candidates:
                            import random as _r
                            sound_file = _r.choice(candidates)
                            self._safe_sound_play("", sound_file, block = should_block)
                            return
            except Exception:
                logging.exception("Suppressed exception")

            if platform_folder:
                wf = os.path.join("sounds", "firearms", "weaponsounds", platform_folder)
                candidates =[]
                if action_type.startswith("tubeinsert")or action_type =="tubeinsert":
                    candidates = glob.glob(os.path.join(wf, "tubeinsert*.ogg"))
                elif action_type.startswith("bulletinsert"):
                    candidates = glob.glob(os.path.join(wf, "bulletinsert*.ogg"))
                else:

                    pattern_candidates = glob.glob(os.path.join(wf, f"{action_type}*.ogg"))+glob.glob(os.path.join(wf, f"{action_type}*.wav"))
                    if pattern_candidates:
                        candidates = pattern_candidates
                    else:

                        exact_ogg = os.path.join(wf, f"{action_type}.ogg")
                        exact_wav = os.path.join(wf, f"{action_type}.wav")
                        if os.path.exists(exact_ogg):
                            candidates =[exact_ogg]
                        elif os.path.exists(exact_wav):
                            candidates =[exact_wav]

                if candidates:
                    sound_file = random.choice(candidates)
                    logging.debug("_play_weapon_action_sound: platform-specific %s -> %s", action_type, sound_file)
                    self._safe_sound_play("", sound_file, block = should_block)
                    return

                if action_type == 'boltactionback':
                    _ba_fallback = glob.glob(os.path.join(wf, "boltback*.ogg")) + glob.glob(os.path.join(wf, "boltback*.wav"))
                    if _ba_fallback:
                        sound_file = random.choice(_ba_fallback)
                        logging.debug("_play_weapon_action_sound: platform boltback fallback for boltactionback -> %s", sound_file)
                        self._safe_sound_play("", sound_file, block=should_block)
                        return
                elif action_type == 'boltactionforward':
                    _bf_fallback = glob.glob(os.path.join(wf, "boltforward*.ogg")) + glob.glob(os.path.join(wf, "boltforward*.wav"))
                    if _bf_fallback:
                        sound_file = random.choice(_bf_fallback)
                        logging.debug("_play_weapon_action_sound: platform boltforward fallback for boltactionforward -> %s", sound_file)
                        self._safe_sound_play("", sound_file, block=should_block)
                        return

            internal_sounds = {
            "tubeinsert":"sounds/firearms/universal/tubeinsert.ogg",
            "bulletinsert0":"sounds/firearms/universal/bulletinsert0.ogg",
            "bulletinsert1":"sounds/firearms/universal/bulletinsert1.ogg",
            "cylinderopen":"sounds/firearms/universal/cylinderopen.ogg",
            "cylinderclose":"sounds/firearms/universal/cylinderclose.ogg",
            "cylinderrelease":"sounds/firearms/universal/cylinderrelease.ogg",
            }

            if action_type.startswith("tubeinsert")or action_type =="tubeinsert":

                uni_folder = os.path.join("sounds", "firearms", "universal")
                tube_candidates = glob.glob(os.path.join(uni_folder, "tubeinsert*.ogg"))
                if tube_candidates:
                    sound_file = random.choice(tube_candidates)
                    logging.debug("_play_weapon_action_sound: tubeinsert -> %s", sound_file)
                    self._safe_sound_play("", sound_file, block = should_block)
                    return

                if os.path.exists(internal_sounds["tubeinsert"]):
                    self._safe_sound_play("", internal_sounds["tubeinsert"], block = should_block)
                    return

            if action_type.startswith("bulletinsert"):

                uni_folder = os.path.join("sounds", "firearms", "universal")
                bullet_candidates = glob.glob(os.path.join(uni_folder, "bulletinsert*.ogg"))
                if bullet_candidates:
                    sound_file = random.choice(bullet_candidates)
                    logging.debug("_play_weapon_action_sound: bulletinsert -> %s", sound_file)
                    self._safe_sound_play("", sound_file, block = should_block)
                    return

                sound_file = internal_sounds.get(action_type)
                if sound_file and os.path.exists(sound_file):
                    self._safe_sound_play("", sound_file, block = should_block)
                    return

            if "revolver"in platform.lower()or "cylinder"in action_type:
                if action_type =="cylinderopen"and os.path.exists(internal_sounds["cylinderopen"]):
                    logging.debug("_play_weapon_action_sound: revolver cylinderopen -> %s", internal_sounds["cylinderopen"])
                    self._safe_sound_play("", internal_sounds["cylinderopen"], block = should_block)
                    return
                elif action_type =="cylinderclose"and os.path.exists(internal_sounds["cylinderclose"]):
                    logging.debug("_play_weapon_action_sound: revolver cylinderclose -> %s", internal_sounds["cylinderclose"])
                    self._safe_sound_play("", internal_sounds["cylinderclose"], block = should_block)
                    return
                elif action_type =="cylinderrelease"and os.path.exists(internal_sounds["cylinderrelease"]):
                    logging.debug("_play_weapon_action_sound: revolver cylinderrelease -> %s", internal_sounds["cylinderrelease"])
                    self._safe_sound_play("", internal_sounds["cylinderrelease"], block = should_block)
                    return
                elif action_type in("bulletinsert0", "bulletinsert1")and os.path.exists(internal_sounds[action_type]):
                    logging.debug("_play_weapon_action_sound: revolver bulletinsert -> %s", internal_sounds[action_type])
                    self._safe_sound_play("", internal_sounds[action_type], block = should_block)
                    return

            if action_type =="magin":
                mag_type = weapon.get("magazinetype", "").lower()
                if any(k in mag_type for k in("internal", "tube", "cylinder"))or "revolver"in platform.lower()or is_belt:
                    return

            if action_type in("coveropen", "coverclose", "boxout", "boxin"):
                preferred_map = {
                "coveropen":["pouchout"],
                "coverclose":["pouchin"],
                "boxout":["magdrop0", "magdrop1"],
                "boxin":["riflemagin", "pistolmagin"]
                }
                pf = platform_folder
                names = preferred_map.get(action_type, [action_type])

                if pf:
                    wf = os.path.join("sounds", "firearms", "weaponsounds", pf)
                    for nm in names:
                        for ext in(".ogg", ".wav"):
                            cand = os.path.join(wf, nm +ext)
                            if os.path.exists(cand):
                                logging.debug("_play_weapon_action_sound: platform preferred %s -> %s", action_type, cand)
                                self._safe_sound_play("", cand, block = should_block)
                                return

                uni_folder = os.path.join("sounds", "firearms", "universal")
                for nm in names:
                    for ext in(".ogg", ".wav"):
                        cand = os.path.join(uni_folder, nm +ext)
                        if os.path.exists(cand):
                            logging.debug("_play_weapon_action_sound: universal preferred %s -> %s", action_type, cand)
                            self._safe_sound_play("", cand, block = should_block)
                            return

            universal_sounds = {
            "magin":["riflemagin", "pistolmagin"],
            "magout":["riflemagout", "pistolmagout"],
            "boltactionback":["boltactionback"],
            "boltactionforward":["boltactionforward"],
            "boltback":["rifleboltback", "pistolslideback", "boltactionback"],
            "boltforward":["rifleboltforward", "pistolslideforward", "boltactionforward"],
            "pumpback":["pumpback", "shotgunpumpback"],
            "pumpforward":["pumpforward", "shotgunpumpforward"],
            "cleaning":["cleaning"],

            "coveropen":["pouchout", "magdrop0"],
            "coverclose":["pouchin"],
            "boxout":["magdrop0", "magdrop1"],
            "boxin":["magin", "riflemagin"]
            }

            if action_type in universal_sounds:
                for sound_name in universal_sounds[action_type]:
                    sound_path = f"sounds/firearms/universal/{sound_name}.ogg"
                    if os.path.exists(sound_path):
                        logging.debug("_play_weapon_action_sound: universal %s -> %s", action_type, sound_path)

                        if action_type =="magin":
                            try:
                                self._safe_sound_play("", sound_path, block = True)
                            except Exception:
                                try:
                                    self._safe_sound_play("", sound_path, block = should_block)
                                except Exception:
                                    logging.exception("Suppressed exception")
                            try:
                                if should_block:
                                    time.sleep(random.uniform(0.15, 0.35))
                                else:
                                    time.sleep(random.uniform(0.05, 0.12))
                            except Exception:
                                logging.exception("Suppressed exception")
                        else:
                            self._safe_sound_play("", sound_path, block = should_block)
                        break

        except Exception as e:
            logging.error(f"Error playing weapon action sound: {e}")

    def _play_weapon_action_sound_strict(self, weapon, action_type, block = False):

        try:
            platform = weapon.get("platform", "").lower()
            platform_folder = platform.replace('/', '_') if platform else None

            equivalents = {
            "boltback":["rifleboltback", "pistolslideback", "boltactionback"],
            "boltforward":["rifleboltforward", "pistolslideforward", "boltactionforward"],
            "coveropen":["pouchout"],
            "coverclose":["pouchin"],
            "boxout":["magdrop0", "magdrop1"],
            "boxin":["riflemagin", "pistolmagin"],
            "magout":["riflemagout", "pistolmagout", "magdrop0", "magdrop1"],
            "magin":["riflemagin", "pistolmagin"],
            "pouchout":["pouchout"],
            "pouchin":["pouchin"]
            }

            names = equivalents.get(action_type, [action_type])

            if platform_folder:
                wf = os.path.join("sounds", "firearms", "weaponsounds", platform_folder)
                exact = os.path.join(wf, action_type +".ogg")
                if os.path.exists(exact):
                    logging.debug("_play_weapon_action_sound_strict: platform exact %s -> %s", action_type, exact)
                    self._safe_sound_play("", exact, block = block)
                    return True

            uni = os.path.join("sounds", "firearms", "universal")
            for nm in names:
                cand = os.path.join(uni, nm +".ogg")
                if os.path.exists(cand):
                    logging.debug("_play_weapon_action_sound_strict: universal exact %s -> %s", action_type, cand)
                    self._safe_sound_play("", cand, block = block)
                    return True

            logging.debug("_play_weapon_action_sound_strict: no file for action '%s'(platform=%s)", action_type, platform_folder)
            return False
        except Exception as e:
            logging.error(f"_play_weapon_action_sound_strict error: {e}")
            return False
