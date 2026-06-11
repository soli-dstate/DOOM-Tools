"""WeaponsMixin — App methods for the "weapons" feature area."""
from app.foundation import *


class WeaponsMixin:

    def _get_ammo_table_data(self):
        try:
            tbl_path = get_current_table_path()
            if tbl_path and os.path.exists(tbl_path):
                with open(tbl_path, 'r', encoding = 'utf-8-sig')as f:
                    table_data = json.load(f)
                return table_data.get("tables", {}).get("ammunition", [])
        except Exception:
            pass
        return[]

    def _ensure_round_variant(self, round_data, ammo_table = None):
        if not isinstance(round_data, dict):
            return round_data

        if ammo_table is None:
            ammo_table = self._get_ammo_table_data()

        caliber = round_data.get("caliber")
        if not caliber:
            name = round_data.get("name", "")
            if " | "in name:
                parts = name.split(" | ", 1)
                caliber = parts[0]
                round_data["caliber"]= caliber

        if caliber:
            for ammo in ammo_table:
                ammo_cal = ammo.get("caliber")
                cal_match = False
                if isinstance(ammo_cal, list):
                    cal_match = caliber in ammo_cal
                else:
                    cal_match = ammo_cal ==caliber

                if cal_match:
                    variants = ammo.get("variants", [])
                    chosen_variant = None
                    existing_variant_name = round_data.get("variant")
                    if existing_variant_name and existing_variant_name not in["Unknown", "unknown", None, ""]:
                        for _v in variants:
                            if isinstance(_v, dict) and _v.get("name") == existing_variant_name:
                                chosen_variant = _v
                                break
                    if chosen_variant is None and variants:
                        chosen_variant = variants[0]

                    if chosen_variant:
                        round_data["variant"] = chosen_variant.get("name", existing_variant_name or "FMJ")
                        _apply_ammo_variant_data(round_data, ammo, chosen_variant)
                        return round_data
                    break

        if not round_data.get("variant"):
            round_data["variant"]= "FMJ"

        return round_data

    def _get_equipped_weapons(self, save_data, table_data):

        weapons =[]
        import copy

        def _resolve_table_item(tid):
            try:

                tables = table_data.get("tables", {})if isinstance(table_data, dict)else {}
                for tname, arr in tables.items():
                    if isinstance(arr, list):
                        for it in arr:
                            if isinstance(it, dict)and it.get("id")==tid:
                                return copy.deepcopy(it)
            except Exception:
                pass
            return None

        for slot_name, item in save_data.get("equipment", {}).items():
            if item and isinstance(item, dict)and item.get("firearm"):
                weapons.append({
                "item":item,
                "slot":slot_name,
                "display_name":item.get("name", "Unknown Weapon")
                })

            if item and isinstance(item, dict)and "subslots"in item:
                for subslot in item["subslots"]:
                    if subslot.get("current")and isinstance(subslot.get("current"), dict):
                        sub_cur = subslot["current"]
                        if sub_cur.get("firearm"):
                            weapons.append({
                            "item":sub_cur,
                            "slot":f"{slot_name} -> {subslot['name']}",
                            "display_name":sub_cur.get("name", "Unknown Weapon")
                            })
                        if sub_cur.get("holster_sling")and "subslots"in sub_cur:
                            for nested_ss in sub_cur["subslots"]:
                                if nested_ss.get("current")and isinstance(nested_ss.get("current"), dict)and nested_ss["current"].get("firearm"):
                                    weapons.append({
                                    "item":nested_ss["current"],
                                    "slot":f"{slot_name} -> {subslot['name']} -> {nested_ss['name']}",
                                    "display_name":nested_ss["current"].get("name", "Unknown Weapon")
                                    })

            try:
                if item and isinstance(item, dict)and item.get("accessories"):
                    for acc in(item.get("accessories")or[]):
                        cur = acc.get("current")
                        resolved = None
                        if cur and isinstance(cur, dict):
                            resolved = cur
                        else:

                            try:
                                if isinstance(cur, int)or(isinstance(cur, str)and cur.isdigit()):
                                    tid = int(cur)
                                    resolved = _resolve_table_item(tid)
                            except Exception:
                                resolved = None

                        if resolved and isinstance(resolved, dict)and resolved.get("underbarrel_weapon"):
                            weapons.append({
                            "item":resolved,
                            "slot":f"{slot_name} -> {acc.get('name', 'Underbarrel')}",
                            "display_name":resolved.get("name", "Underbarrel Weapon"),
                            "underbarrel":True,
                            "parent_slot":slot_name,
                            "underbarrel_platform":resolved.get("underbarrel_platform")or resolved.get("platform")
                            })
            except Exception:
                pass

        return weapons

    def _apply_item_overrides(self, weapon):

        import copy

        MISSING = object()

        applied = weapon.get("_applied_overrides", {})or {}
        if applied:
            try:
                logging.info("_apply_item_overrides: restoring previous applied overrides keys=%s for weapon id=%s", list(applied.keys()), weapon.get('id'))
            except Exception:
                pass
        for k, orig in list(applied.items()):
            try:
                if orig is MISSING:
                    if k in weapon:
                        del weapon[k]
                else:
                    weapon[k]= orig
            except Exception:

                pass

        weapon["_applied_overrides"]= {}

        def _resolve_table_current(cur_val):

            if cur_val and isinstance(cur_val, dict):
                return cur_val
            try:
                if isinstance(cur_val, int)or(isinstance(cur_val, str)and str(cur_val).isdigit()):
                    tid = int(cur_val)
                else:
                    return None
            except Exception:
                return None

            try:
                tdata = globals().get('table_data')
                if isinstance(tdata, dict):
                    tables = tdata.get('tables', {})
                    for arr in tables.values():
                        if isinstance(arr, list):
                            for it in arr:
                                if isinstance(it, dict)and it.get('id')==tid:
                                    return it
            except Exception:
                pass

            try:
                import json, os, glob
                table_files = sorted(glob.glob(os.path.join('tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
                for tf in table_files:
                    try:
                        with open(tf, 'r', encoding = 'utf-8')as fh:
                            td = json.load(fh)
                    except Exception:
                        continue
                    for arr in td.get('tables', {}).values():
                        if isinstance(arr, list):
                            for it in arr:
                                if isinstance(it, dict)and it.get('id')==tid:
                                    return it
            except Exception:
                pass

            return None

        for acc in weapon.get("accessories", [])or[]:
            cur_raw = acc.get("current")
            cur = _resolve_table_current(cur_raw)if cur_raw is not None else None

            if cur and isinstance(cur, dict):
                try:
                    logging.debug("_apply_item_overrides: found accessory for overrides: id=%s name=%s on weapon id=%s", cur.get('id'), cur.get('name'), weapon.get('id'))
                except Exception:
                    pass
                overrides = cur.get("overrides")or {}
                if isinstance(overrides, dict):
                    for k, v in overrides.items():

                        if k not in weapon.get("_applied_overrides", {}):
                            orig = weapon.get(k, MISSING)
                            weapon.setdefault("_applied_overrides", {})[k]= orig
                            try:
                                logging.debug("_apply_item_overrides: recording original value for key=%s orig=%s", k, orig)
                            except Exception:
                                pass

                        try:
                            weapon[k]= copy.deepcopy(v)
                        except Exception:
                            weapon[k]= v
                        try:
                            logging.debug("_apply_item_overrides: applied override key=%s value=%s from accessory id=%s", k, v, cur.get('id'))
                        except Exception:
                            pass

        try:
            agg = {"stats":{}}
            for acc in weapon.get("accessories", [])or[]:
                cur = _resolve_table_current(acc.get("current"))if acc.get("current")is not None else None

                def _wavelength_allows(item):
                    try:
                        if not item or not isinstance(item, dict):
                            return True
                        wl = item.get("wavelength")
                        if not wl:
                            return True
                        if isinstance(wl, str):
                            if wl.lower()in("infrared", "ir", "infra-red"):

                                try:
                                    cs = globals().get('combat_state')or {}
                                    return bool(cs.get('nvg_active'))
                                except Exception:
                                    return False

                            return True

                        return True
                    except Exception:
                        return True

                if cur and isinstance(cur, dict):
                    _elec_off = bool(cur.get("electronic")) and not cur.get("power_on")
                    mods = cur.get("modifiers")or {}
                    if isinstance(mods, dict) and not _elec_off:
                        stats = mods.get("stats")or {}
                        if isinstance(stats, dict):

                                if _wavelength_allows(cur):
                                    for sname, sval in stats.items():
                                        try:
                                            agg["stats"][sname]= agg["stats"].get(sname, 0)+(int(sval)if isinstance(sval, (int, float))else 0)
                                        except Exception:
                                            pass

                    try:
                        modes = cur.get("modes")or[]
                        if isinstance(modes, list)and modes and not _elec_off:
                            mode_index = acc.get("_mode_index")
                            if mode_index is None:

                                mode_index = acc.get("mode_index")
                            try:
                                mi = int(mode_index)if mode_index is not None else 0
                            except Exception:
                                mi = 0
                            mi = max(0, min(mi, len(modes)-1))
                            mode = modes[mi]
                            if isinstance(mode, dict):
                                mm = mode.get("modifiers")or {}
                                if isinstance(mm, dict):
                                    mstats = mm.get("stats")or {}
                                    if isinstance(mstats, dict):

                                                if _wavelength_allows(mode):
                                                    for sname, sval in mstats.items():
                                                        try:
                                                            agg["stats"][sname]= agg["stats"].get(sname, 0)+(int(sval)if isinstance(sval, (int, float))else 0)
                                                        except Exception:
                                                            pass

                                try:
                                    mode_overrides = mode.get("overrides")if isinstance(mode, dict)else None
                                    if isinstance(mode_overrides, dict):
                                        for k, v in mode_overrides.items():
                                            if k not in weapon.get("_applied_overrides", {}):
                                                orig = weapon.get(k, MISSING)
                                                weapon.setdefault("_applied_overrides", {})[k]= orig
                                                try:
                                                    logging.debug("_apply_item_overrides: recording original value for key=%s orig=%s(mode override)", k, orig)
                                                except Exception:
                                                    pass
                                            try:
                                                weapon[k]= copy.deepcopy(v)
                                            except Exception:
                                                weapon[k]= v
                                            try:
                                                logging.debug("_apply_item_overrides: applied mode override key=%s value=%s from accessory id=%s", k, v, cur.get('id'))
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                    except Exception:

                        pass
            weapon["_active_modifiers"]= agg
        except Exception:

            try:
                weapon["_active_modifiers"]= {"stats":{}}
            except Exception:
                pass

        try:
            wid = str(weapon.get("id"))
            act = weapon.get("action")
            acc_names =[]
            for a in weapon.get("accessories", [])or[]:
                try:
                    cur = a.get("current")
                    if cur and isinstance(cur, dict):
                        acc_names.append(cur.get("name")or str(cur.get("id")or "?"))
                except Exception:
                    pass
            logging.debug("_apply_item_overrides: weapon id=%s action=%s installed_attachments=%s", wid, act, acc_names)
        except Exception:
            pass

    def _display_weapon_details(self, parent, weapon, combat_state, save_data, table_data, current_weapon_state = None):

        detail_frame = customtkinter.CTkFrame(parent)
        detail_frame.pack(fill = "both", expand = True, padx = 10, pady = 10)

        name_label = customtkinter.CTkLabel(
        detail_frame,
        text = weapon.get("name", "Unknown Weapon"),
        font = customtkinter.CTkFont(size = 16, weight = "bold")
        )
        name_label.pack(pady = 5)

        stats_text = f"Platform: {weapon.get('platform', 'Unknown')}\n"
        stats_text +=f"Caliber: {', '.join(weapon.get('caliber') or weapon.get('musket_caliber') or ['Unknown'])}\n"
        stats_text +=f"Action: {', '.join(weapon.get('action', ['Unknown']))}\n"
        raw_cyclic = weapon.get('cyclic', 0)
        if isinstance(raw_cyclic, list) and raw_cyclic:
            effective_rpm = _resolve_effective_cyclic(weapon, combat_state)
            gas_settings = combat_state.get("gas_setting", {}) if combat_state else {}
            gas_idx = gas_settings.get(str(weapon.get("id", "")), 0)
            stats_text +=f"Cyclic Rate: {int(effective_rpm)} RPM (Gas Setting {gas_idx + 1}/{len(raw_cyclic)})\n"
        elif weapon.get("burst_cyclic"):
            stats_text +=f"Cyclic Rate: {raw_cyclic} RPM({weapon.get('burst_cyclic', 0)} RPM burst)\n"
        else:
            stats_text +=f"Cyclic Rate: {raw_cyclic} RPM\n"
        stats_text +=f"Magazine Type: {weapon.get('magazinetype', 'Unknown')}\n"
        if weapon.get("dualfeed") and weapon.get("submagazinetype"):
            stats_text +=f"Alt Magazine Type: {weapon.get('submagazinetype')}"
            if weapon.get("submagazinesystem"):
                stats_text +=f" ({weapon.get('submagazinesystem')})"
            stats_text +="\n"

        if weapon.get("magazinesystem"):
            stats_text +=f"Magazine System: {weapon.get('magazinesystem')}\n"

        if weapon.get("capacity"):
            stats_text +=f"Capacity: {weapon.get('capacity')}\n"

        customtkinter.CTkLabel(
        detail_frame,
        text = stats_text,
        font = customtkinter.CTkFont(size = 12),
        justify = "left"
        ).pack(pady = 5)

        try:
            def _resolve_current(cur):

                if isinstance(cur, dict):
                    return cur
                try:
                    if isinstance(cur, int)or(isinstance(cur, str)and cur.isdigit()):
                        tid = int(cur)
                        tables = table_data.get("tables", {})if isinstance(table_data, dict)else {}
                        for arr in tables.values():
                            if isinstance(arr, list):
                                for it in arr:
                                    if isinstance(it, dict)and it.get("id")==tid:
                                        return it
                except Exception:
                    pass
                return None

            active = combat_state.get("active_underbarrel")

            try:
                equipped_weapons = self._get_equipped_weapons(save_data, table_data)
            except Exception:
                equipped_weapons =[]
            is_displaying_ub = False
            resolved_acc_for_display = None
            if active and isinstance(active, dict)and active.get("parent_index")==combat_state.get("current_weapon_index"):

                aid = active.get("accessory_id")
                aname = active.get("accessory_name")
                parent_slot = equipped_weapons[combat_state.get("current_weapon_index")].get("slot", "")
                if "->"in parent_slot:
                    parent_slot = parent_slot.split("->")[0].strip()
                parent_item = save_data.get("equipment", {}).get(parent_slot)
                if parent_item and isinstance(parent_item, dict):
                    for acc_entry in parent_item.get("accessories", [])or[]:
                        cur = acc_entry.get("current")
                        if isinstance(cur, dict):
                            if aid is not None and cur.get("id")==aid:
                                resolved_acc_for_display = cur ;break
                            if aname and cur.get("name")==aname:
                                resolved_acc_for_display = cur ;break
                        else:
                            try:
                                if aid is not None and(isinstance(cur, int)or(isinstance(cur, str)and cur.isdigit()))and int(cur)==int(aid):
                                    tables = table_data.get("tables", {})if isinstance(table_data, dict)else {}
                                    for arr in tables.values():
                                        if isinstance(arr, list):
                                            for it in arr:
                                                if isinstance(it, dict)and it.get("id")==int(cur):
                                                    resolved_acc_for_display = it ;break
                                            if resolved_acc_for_display:break
                            except Exception:
                                pass

                if not resolved_acc_for_display:
                    for sub in parent_item.get("subslots", [])or[]:
                        try:
                            logging.info("Checking parent subslot '%s' for active accessory", sub.get("name"))
                        except Exception:
                            pass
                        sub_cur = sub.get("current")if isinstance(sub, dict)else None
                        if not sub_cur or not isinstance(sub_cur, dict):
                            continue
                        for acc_entry in sub_cur.get("accessories", [])or[]:
                            cur = acc_entry.get("current")
                            if isinstance(cur, dict):
                                if aid is not None and cur.get("id")==aid:
                                    resolved_acc_for_display = cur ;break
                                if aname and cur.get("name")==aname:
                                    resolved_acc_for_display = cur ;break
                            else:
                                try:
                                    if aid is not None and(isinstance(cur, int)or(isinstance(cur, str)and cur.isdigit()))and int(cur)==int(aid):
                                        tables = table_data.get("tables", {})if isinstance(table_data, dict)else {}
                                        for arr in tables.values():
                                            if isinstance(arr, list):
                                                for it in arr:
                                                    if isinstance(it, dict)and it.get("id")==int(cur):
                                                        resolved_acc_for_display = it ;break
                                                if resolved_acc_for_display:break
                                except Exception:
                                    pass
                if resolved_acc_for_display and isinstance(resolved_acc_for_display, dict):
                    try:
                        logging.info("Resolved active accessory for display: id=%s name=%s", resolved_acc_for_display.get("id"), resolved_acc_for_display.get("name"))
                    except Exception:
                        pass
                    is_displaying_ub = True

            try:
                logging.info("Underbarrel display decision: is_displaying_ub=%s resolved=%s active=%s", is_displaying_ub, getattr(resolved_acc_for_display, 'get', lambda k:None)('name')if isinstance(resolved_acc_for_display, dict)else resolved_acc_for_display, active)
            except Exception:
                pass

            if is_displaying_ub:
                def _switch_to_parent():
                    try:

                        ub = resolved_acc_for_display
                        ub_pf = ub.get("underbarrel_platform")or ub.get("platform")if isinstance(ub, dict)else None
                        if ub_pf:
                            wf = os.path.join("sounds", "firearms", "weaponsounds", str(ub_pf).lower().replace('/', '_'))
                            candidates = glob.glob(os.path.join(wf, "unselect*.ogg"))+glob.glob(os.path.join(wf, "holster*.ogg"))
                            if candidates:
                                self._safe_sound_play("", random.choice(candidates), block = True)

                        combat_state.pop("active_underbarrel", None)
                        try:
                            logging.info("Cleared active_underbarrel for parent_index=%s", combat_state.get("current_weapon_index"))
                        except Exception:
                            pass
                        try:
                            self._save_combat_state(save_data)
                        except Exception:
                            pass
                        try:
                            self._open_combat_mode_tool()
                        except Exception:
                            pass
                    except Exception:
                        pass

                customtkinter.CTkButton(detail_frame, text = "Switch to Parent", command = _switch_to_parent, width = 160).pack(pady = 6)
            else:

                ub_found = None
                try:
                    logging.debug("Underbarrel detection: weapon_id=%s accessories=%s", weapon.get("id"), weapon.get("accessories"))
                except Exception:
                    pass
                for acc in weapon.get("accessories", [])or[]:
                    cur = acc.get("current")
                    resolved = _resolve_current(cur)
                    try:
                        logging.debug("Resolving accessory current=%s -> resolved=%s", repr(cur), getattr(resolved, 'get', lambda k, d = None:None)('id', resolved))
                    except Exception:
                        logging.debug("Resolving accessory current=%s -> resolved=%s", repr(cur), str(resolved))
                    if resolved and isinstance(resolved, dict)and resolved.get("underbarrel_weapon"):
                        ub_found = resolved
                        break

                if ub_found:
                    def _switch_to_underbarrel():
                        try:

                            ub_pf = ub_found.get("underbarrel_platform")or ub_found.get("platform")
                            played = False
                            if ub_pf:
                                wf = os.path.join("sounds", "firearms", "weaponsounds", str(ub_pf).lower().replace('/', '_'))
                                candidates = glob.glob(os.path.join(wf, "select*.ogg"))+glob.glob(os.path.join(wf, "draw*.ogg"))
                                if candidates:
                                    self._safe_sound_play("", random.choice(candidates), block = False)
                                    played = True
                            if not played:
                                try:
                                    self._play_firearm_sound(ub_found, "equip")
                                except Exception:
                                    pass

                            combat_state["active_underbarrel"]= {
                            "parent_index":combat_state.get("current_weapon_index"),
                            "accessory_id":ub_found.get("id")if isinstance(ub_found, dict)else None,
                            "accessory_name":ub_found.get("name")if isinstance(ub_found, dict)else None
                            }
                            try:
                                logging.debug("Set active_underbarrel: parent_index=%s accessory_id=%s accessory_name=%s", combat_state.get("current_weapon_index"), ub_found.get("id"), ub_found.get("name"))
                            except Exception:
                                pass
                            try:
                                self._save_combat_state(save_data)
                            except Exception:
                                pass
                            try:
                                self._open_combat_mode_tool()
                            except Exception:
                                pass
                        except Exception:
                            pass

                    customtkinter.CTkButton(detail_frame, text = "Switch to Underbarrel", command = _switch_to_underbarrel, width = 160).pack(pady = 6)
        except Exception:
            pass

        weapon_id = weapon.get("id")
        temperature = combat_state.get("barrel_temperatures", {}).get(str(weapon_id), combat_state["ambient_temperature"])
        cleanliness = _get_weapon_cleanliness(combat_state, weapon, default = 100.0, cache_to_state = True)

        has_hud = self._check_for_hud(save_data)

        def _has_equipped_item(save_data, target_id):
            try:
                for slot_name, item in save_data.get("equipment", {}).items():
                    if not item or not isinstance(item, dict):
                        continue

                    if item.get("id")==target_id:
                        return True

                    for sub in(item.get("items")or[]):
                        try:
                            if sub and isinstance(sub, dict)and sub.get("id")==target_id:
                                return True
                        except Exception:
                            pass

                    for subslot in(item.get("subslots")or[]):
                        try:
                            curr = subslot.get("current")
                            if curr and isinstance(curr, dict):
                                if curr.get("id")==target_id:
                                    return True
                                for s in(curr.get("items")or[]):
                                    try:
                                        if s and isinstance(s, dict)and s.get("id")==target_id:
                                            return True
                                    except Exception:
                                        pass
                        except Exception:
                            pass
            except Exception:
                return False
            return False

        has_csad = _has_equipped_item(save_data, 37)

        gunlink_on_weapon = False
        try:
            for acc in(weapon.get("accessories")or[]):
                if not acc or not isinstance(acc, dict):
                    continue
                cur = acc.get("current")

                try:
                    if isinstance(cur, int)and cur in(85, 94):
                        gunlink_on_weapon = True
                        break
                except Exception:
                    pass

                try:
                    if isinstance(cur, dict):
                        cid = cur.get("id")
                        cname = str(cur.get("name")or "").lower()
                        if(isinstance(cid, int)and cid in(85, 94))or("gun link"in cname):
                            gunlink_on_weapon = True
                            break
                except Exception:
                    pass
        except Exception:
            gunlink_on_weapon = False

        temp_exact = bool(has_hud or has_csad)
        clean_exact = bool(has_hud or(has_csad and gunlink_on_weapon))
        ammo_exact = bool(has_hud or(has_csad and gunlink_on_weapon))

        is_hardcore = False
        try:
            tbl_hc = globals().get('table_data', {})
            if isinstance(tbl_hc, dict):
                is_hardcore = bool((tbl_hc.get('additional_settings') or {}).get('hardcore_mode'))
        except Exception:
            is_hardcore = False

        if is_hardcore:
            ammo_exact = bool(has_hud and (has_csad and gunlink_on_weapon))

        try:
            weapon_mods = weapon.get("_active_modifiers") or {}
            if isinstance(weapon_mods, dict):
                mod_stats = weapon_mods.get("stats") or {}
                if mod_stats.get("ammo_exact"):
                    ammo_exact = True
                if mod_stats.get("temp_exact"):
                    temp_exact = True
                if mod_stats.get("clean_exact"):
                    clean_exact = True
            for acc in (weapon.get("accessories") or []):
                cur = acc.get("current") if isinstance(acc, dict) else None
                if isinstance(cur, dict):
                    acc_mods = cur.get("modifiers") or {}
                    if isinstance(acc_mods, dict):
                        acc_stats = acc_mods.get("stats") or {}
                        if isinstance(acc_stats, dict):
                            if acc_stats.get("ammo_exact"):
                                ammo_exact = True
                            if acc_stats.get("temp_exact"):
                                temp_exact = True
                            if acc_stats.get("clean_exact"):
                                clean_exact = True
        except Exception:
            pass

        if appearance_settings["units"]=="metric":
            display_temp =(temperature -32)*5 /9
            temp_unit = "°C"
        else:
            display_temp = temperature
            temp_unit = "°F"

        if temperature >=1200:
            temp_color = "#FF5E00"
        elif temperature >=1000:
            temp_color = "#FF3000"
        elif temperature >=800:
            temp_color = "#CC0000"
        elif temperature >=700:
            temp_color = "#AA2200"
        elif temperature >=600:
            temp_color = "#A65A2E"
        elif temperature >=500:
            temp_color = "#8040A0"
        elif temperature >=400:
            temp_color = "#4060C0"
        elif temperature >=300:
            temp_color = "#00A0FF"
        elif temperature >=212:
            temp_color = "#00C878"
        elif temperature >=120:
            temp_color = "#00AA00"
        else:
            temp_color = "#007700"

        if temp_exact:
            temp_text = f"Barrel Temperature: {display_temp:.2f}{temp_unit}"
        else:

            try:
                _cookoff_t = float(combat_state.get("cookoff_temp", 1500))
            except Exception:
                _cookoff_t = 1500.0
            if temperature >= _cookoff_t:
                temp_desc = "Critical hot"
            elif temperature > 800:
                temp_desc = "Very hot"
            elif temperature > 500:
                temp_desc = "Hot"
            elif temperature > 250:
                temp_desc = "Warm"
            else:
                temp_desc = "Cool"
            temp_text = f"Barrel Temperature: {temp_desc}"

        _temp_label_kwargs = {"text": temp_text, "font": customtkinter.CTkFont(size = 14)}
        if temp_color:
            _temp_label_kwargs["text_color"] = temp_color
        customtkinter.CTkLabel(
        detail_frame,
        **_temp_label_kwargs
        ).pack(pady = 5)

        clean_color = "#00FF00"
        if cleanliness <30:
            clean_color = "#FF0000"
        elif cleanliness <50:
            clean_color = "#FFA500"
        elif cleanliness <70:
            clean_color = "#FFFF00"

        if not has_hud:
            clean_color = None

        if clean_exact:
            clean_text = f"Cleanliness: {cleanliness:.2f}%"
        else:
            if cleanliness < 30:
                clean_desc = "Very dirty"
            elif cleanliness < 50:
                clean_desc = "Dirty"
            elif cleanliness < 70:
                clean_desc = "Slightly dirty"
            else:
                clean_desc = "Clean"
            clean_text = f"Cleanliness: {clean_desc}"

        _clean_label_kwargs = {"text": clean_text, "font": customtkinter.CTkFont(size = 14)}
        if clean_color:
            _clean_label_kwargs["text_color"] = clean_color
        clean_label = customtkinter.CTkLabel(
        detail_frame,
        **_clean_label_kwargs
        )
        clean_label.pack(pady = 5)

        if current_weapon_state is not None:
            current_weapon_state["clean_label_ref"]= clean_label

        mag_checked = current_weapon_state.get("mag_checked", False)if current_weapon_state else False
        mag_windowed = False
        try:
            loaded_mag_local = weapon.get("loaded")
            if isinstance(loaded_mag_local, dict)and(loaded_mag_local.get("windowed_magazine")or loaded_mag_local.get("window")):
                mag_windowed = True
            elif weapon.get("windowed_magazine")or weapon.get("window"):
                mag_windowed = True
        except Exception:
            mag_windowed = False
        show_variant = bool(ammo_exact)and(mag_checked or mag_windowed or(has_csad and gunlink_on_weapon))
        ammo_text = self._get_ammo_display(weapon, bool(ammo_exact), show_variant = show_variant)

        _ammo_color = None
        if has_hud and ammo_exact:
            try:
                _total_rds = 0
                if weapon.get("chambered"):
                    _total_rds += 1
                _mag_type_ammo = (weapon.get("magazinetype") or "").lower()
                _is_int_ammo = "internal" in _mag_type_ammo or "tube" in _mag_type_ammo
                _is_rev_ammo = "revolver" in (weapon.get("platform", "") or "").lower()
                _is_dualfeed_mag = weapon.get("dualfeed") and isinstance(weapon.get("loaded"), dict)
                if (_is_int_ammo or _is_rev_ammo) and not _is_dualfeed_mag:
                    _total_rds += len(weapon.get("rounds", []) or [])
                else:
                    _ld_mag = weapon.get("loaded")
                    if isinstance(_ld_mag, dict):
                        _total_rds += len(_ld_mag.get("rounds", []) or [])
                if _total_rds <= 5:
                    _ammo_color = "#FF0000"
            except Exception:
                pass

        _ammo_label_kwargs = {"text": ammo_text, "font": customtkinter.CTkFont(size = 14)}
        if _ammo_color:
            _ammo_label_kwargs["text_color"] = _ammo_color
        ammo_label = customtkinter.CTkLabel(
        detail_frame,
        **_ammo_label_kwargs
        )
        ammo_label.pack(pady = 5)

        if current_weapon_state is not None:
            current_weapon_state["ammo_label_ref"]= ammo_label
            current_weapon_state["original_ammo_text"]= ammo_text

        try:
            loaded_marking_mag = weapon.get("loaded")
            if isinstance(loaded_marking_mag, dict) and loaded_marking_mag.get("marking_text"):
                self._render_magazine_marking_widget(detail_frame, loaded_marking_mag, weapon)
        except Exception:
            pass

        if weapon.get("accessories"):
            customtkinter.CTkLabel(
            detail_frame,
            text = "Attachments:",
            font = customtkinter.CTkFont(size = 14, weight = "bold")
            ).pack(pady =(10, 5))

            for accessory in weapon["accessories"]:
                batt_color = None
                if accessory.get("current"):
                    cur_att = accessory["current"]
                    att_text = f"• {accessory['name']}: {cur_att.get('name', 'Unknown')}"
                    batt_pct = _get_battery_percentage(cur_att)
                    if batt_pct is not None:
                        power_state = "ON" if cur_att.get("power_on") else "OFF"
                        if batt_pct <= 10:
                            batt_color = "#FF3333"
                        elif batt_pct <= 30:
                            batt_color = "#FFA500"
                        else:
                            batt_color = "#33FF33"
                        att_text += f"  [{power_state} | {batt_pct:.0f}%]"
                else:
                    att_text = f"• {accessory['name']}: Empty"

                att_label = customtkinter.CTkLabel(
                detail_frame,
                text = att_text,
                font = customtkinter.CTkFont(size = 12),
                text_color = batt_color if batt_color else None
                )
                att_label.pack(pady = 1)

        try:
            _is_hc_parts = False
            _tbl_hc_parts = globals().get('table_data', {})
            if isinstance(_tbl_hc_parts, dict):
                _is_hc_parts = bool((_tbl_hc_parts.get('additional_settings') or {}).get('hardcore_mode'))
            if _is_hc_parts and weapon.get("parts") and isinstance(weapon["parts"], list):
                _parts_frame = customtkinter.CTkFrame(detail_frame, corner_radius = 6)
                _parts_frame.place(relx = 1.0, y = 4, anchor = "ne", x = -4)

                customtkinter.CTkLabel(
                    _parts_frame,
                    text = "Parts",
                    font = customtkinter.CTkFont(size = 11, weight = "bold")
                ).pack(pady = (4, 2), padx = 8)

                _cal_mismatched_ids = _get_caliber_mismatched_parts(weapon)
                _flash_labels = []

                for _p in weapon["parts"]:
                    if not isinstance(_p, dict):
                        continue
                    _pname = _p.get("name") or _p.get("type") or "Unknown"
                    _p_is_mismatched = id(_p) in _cal_mismatched_ids
                    _pdur = _p.get("current_durability")
                    _pcolor = "#888888"
                    _pstatus = ""
                    if _p_is_mismatched:
                        _pstatus = "Incompatible"
                        _pcolor = "#ff0000"
                    elif _pdur is not None and str(_pdur).strip().lower() not in ("null", "set_by_looting"):
                        try:
                            _pdur_val = float(_pdur)
                            _ppct = max(0.0, min(100.0, (_pdur_val / PART_DURABILITY_MAX) * 100))
                            if _pdur_val <= 0:
                                _pstatus = "Worn Out"
                                _pcolor = "#ff4444"
                            elif _ppct < 25:
                                _pstatus = "Poor"
                                _pcolor = "#ff6644"
                            elif _ppct < 50:
                                _pstatus = "Fair"
                                _pcolor = "#ffaa44"
                            elif _ppct < 75:
                                _pstatus = "Good"
                                _pcolor = "#aacc44"
                            else:
                                _pstatus = "Excellent"
                                _pcolor = "#44cc44"
                        except (ValueError, TypeError):
                            _pstatus = "?"
                    else:
                        _pstatus = "N/A"

                    _plbl = customtkinter.CTkLabel(
                        _parts_frame,
                        text = f"{_pname}: {_pstatus}",
                        font = customtkinter.CTkFont(size = 10),
                        text_color = _pcolor
                    )
                    _plbl.pack(pady = 1, padx = 8, anchor = "w")

                    if _p_is_mismatched:
                        _flash_labels.append(_plbl)

                if _flash_labels:
                    def _flash_incompatible_parts(_labels=_flash_labels, _frame=_parts_frame, _on=True):
                        try:
                            if not _frame.winfo_exists():
                                return
                            for _fl in _labels:
                                if _fl.winfo_exists():
                                    _fl.configure(text_color="#ff0000" if _on else "#661111")
                            _frame.after(500, lambda: _flash_incompatible_parts(_labels, _frame, not _on))
                        except Exception:
                            pass
                    _parts_frame.after(500, lambda: _flash_incompatible_parts())

                _parts_frame_spacer = customtkinter.CTkLabel(_parts_frame, text = "", height = 2)
                _parts_frame_spacer.pack()
        except Exception:
            logging.exception("Failed to render parts status box in combat mode")

    def _check_for_hud(self, save_data):

        for slot_name, item in save_data.get("equipment", {}).items():
            if item and isinstance(item, dict)and item.get("hud"):
                return True
        return False

    def _get_ammo_display(self, weapon, has_hud, show_variant = False):

        loaded_mag = weapon.get("loaded")
        chambered = weapon.get("chambered")
        magazine_type = weapon.get("magazinetype", "").lower()

        is_dualfeed_belt = weapon.get("dualfeed") and ("belt" in magazine_type or "m249" in (weapon.get("platform", "") or "").lower()) and not isinstance(loaded_mag, dict)
        is_internal = "internal"in magazine_type or "tube"in magazine_type or is_dualfeed_belt
        is_revolver = "revolver"in weapon.get("platform", "").lower()

        def _resolve_ref(obj):
            if isinstance(obj, dict):
                return obj
            try:
                td = globals().get('table_data')or {}
                tables = td.get('tables', {})if isinstance(td, dict)else {}
                iid = None
                if isinstance(obj, (int, float)):
                    iid = int(obj)
                elif isinstance(obj, str)and str(obj).isdigit():
                    iid = int(obj)
                if iid is None:
                    return None
                for arr in tables.values():
                    if isinstance(arr, list):
                        for cand in arr:
                            try:
                                if isinstance(cand, dict)and cand.get('id')==iid:
                                    return cand
                            except Exception:
                                pass
            except Exception:
                pass

            try:
                iid_local = iid if 'iid'in locals()else None
                if iid_local is not None:
                    seen = set()
                    def _search(obj):
                        try:
                            oid = id(obj)
                            if oid in seen:
                                return None
                            seen.add(oid)
                        except Exception:
                            pass
                        if isinstance(obj, dict):
                            try:
                                if obj.get('id')==iid_local:
                                    return obj
                            except Exception:
                                pass
                            for v in obj.values():
                                try:
                                    res = _search(v)
                                    if res:
                                        return res
                                except Exception:
                                    pass
                        elif isinstance(obj, list):
                            for it in obj:
                                try:
                                    res = _search(it)
                                    if res:
                                        return res
                                except Exception:
                                    pass
                        return None

                    sd = globals().get('save_data')or getattr(self, '_current_save_data', None)
                    if isinstance(sd, dict):

                        for root_key in('storage', 'hands', 'equipment'):
                            try:
                                root = sd.get(root_key)
                                if root:
                                    found = _search(root)
                                    if found:
                                        return found
                            except Exception:
                                pass

                    if isinstance(sd, dict):
                        found = _search(sd)
                        if found:
                            return found
            except Exception:
                pass

            return None

        loaded_mag_obj = _resolve_ref(loaded_mag)or(loaded_mag if isinstance(loaded_mag, dict)else None)
        chambered_obj = _resolve_ref(chambered)or(chambered if isinstance(chambered, dict)else None)

        try:
            mag_windowed = False
            if loaded_mag_obj and isinstance(loaded_mag_obj, dict)and(loaded_mag_obj.get('windowed_magazine')or loaded_mag_obj.get('window')):
                mag_windowed = True
            elif chambered_obj and isinstance(chambered_obj, dict)and(chambered_obj.get('windowed_magazine')or chambered_obj.get('window')):
                mag_windowed = True
            elif isinstance(weapon, dict)and(weapon.get('windowed_magazine')or weapon.get('window')):
                mag_windowed = True
        except Exception:
            mag_windowed = False

        try:
            logging.debug("_get_ammo_display: loaded_mag_raw=%s loaded_mag_resolved=%s chambered_resolved=%s mag_windowed=%s has_hud=%s", repr(loaded_mag), repr(loaded_mag_obj), repr(chambered_obj), mag_windowed, has_hud)
        except Exception:
            pass

        effective_has_hud = bool(has_hud)or bool(mag_windowed)

        is_hardcore_ammo = False
        try:
            tbl_hc2 = globals().get('table_data', {})
            if isinstance(tbl_hc2, dict):
                is_hardcore_ammo = bool((tbl_hc2.get('additional_settings') or {}).get('hardcore_mode'))
        except Exception:
            is_hardcore_ammo = False

        if is_hardcore_ammo:
            effective_has_hud = bool(has_hud)

        next_variant = None
        if show_variant:
            try:
                if chambered_obj and isinstance(chambered_obj, dict):
                    next_variant = chambered_obj.get("variant")or chambered_obj.get("name")
                if not next_variant:
                    if is_internal or is_revolver:
                        _int_rounds = weapon.get("rounds", [])
                        if _int_rounds and isinstance(_int_rounds, list)and len(_int_rounds)>0:
                            _nr = _int_rounds[0]
                            if isinstance(_nr, dict):
                                next_variant = _nr.get("variant")or _nr.get("name")
                    else:
                        _mag_obj = loaded_mag_obj or(loaded_mag if isinstance(loaded_mag, dict)else None)
                        if _mag_obj and isinstance(_mag_obj, dict):
                            _mag_rounds = _mag_obj.get("rounds", [])
                            if _mag_rounds and isinstance(_mag_rounds, list)and len(_mag_rounds)>0:
                                _nr = _mag_rounds[0]
                                if isinstance(_nr, dict):
                                    next_variant = _nr.get("variant")or _nr.get("name")
            except Exception:
                next_variant = None
        variant_text = f"[{next_variant}]"if next_variant else ""

        if is_internal or is_revolver:

            internal_rounds = weapon.get("rounds", [])
            total_rounds = len(internal_rounds)
            if chambered:
                total_rounds +=1

            if effective_has_hud:
                chamber_text = "(+1 chambered)"if chambered else ""
                capacity = weapon.get("capacity", 0)
                return f"Ammo: {total_rounds}/{capacity} rounds{chamber_text}{variant_text}"
            else:
                if total_rounds ==0:
                    return "Ammo: Empty(no rounds)"
                return f"Ammo: Loaded(exact count unknown){variant_text}"

        if not loaded_mag and not chambered:
            return "Ammo: Empty(no magazine)"

        total_rounds = 0
        if chambered:
            total_rounds +=1

        if loaded_mag:
            rounds_in_mag = len(loaded_mag.get("rounds", []))
            total_rounds +=rounds_in_mag

        if effective_has_hud:

            chamber_text = "(+1 chambered)"if chambered else ""
            if loaded_mag and not loaded_mag.get("rounds"):
                return f"Ammo: 0 rounds(empty magazine loaded){chamber_text}{variant_text}"
            return f"Ammo: {total_rounds} rounds{chamber_text}{variant_text}"
        else:

            if not loaded_mag and chambered:
                return f"Ammo: Unknown(mag out, round chambered){variant_text}"
            if not loaded_mag:
                return "Ammo: No magazine"
            if not loaded_mag.get("rounds"):
                return "Ammo: Empty magazine loaded(check/reload)"
            return f"Ammo: Unknown(remove mag to check){variant_text}"
