"""SavesMixin — App methods for the "saves" feature area."""
from app.foundation import *


class SavesMixin:

    def _save_persistent_data(self):

        try:
            persistent_path = os.path.join(saves_folder or "saves", "persistent_data.sldsv")
            _signed_json_write(persistent_path, persistentdata)
            logging.info(f"Persistent data saved to {persistent_path}")
        except Exception as e:
            logging.error(f"Failed to save persistent data: {e}")
    def _write_save_to_path(self, path, data):
        try:
            if not path.endswith(global_variables.get("save_extension", ".sldsv")):
                path +=global_variables.get("save_extension", ".sldsv")

            filename = os.path.basename(path)
            excluded_from_backup = {"persistent_data.sldsv", "settings.sldsv", "appearance_settings.sldsv", "dm_settings.sldsv"}
            if filename not in excluded_from_backup and isinstance(data, dict):
                try:
                    char_name = data.get("charactername", "Unknown")
                    safe_char_name = "".join(c if c.isalnum()or c in " _-"else "_"for c in char_name).strip()
                    if not safe_char_name:
                        safe_char_name = "Unknown"

                    backup_folder = os.path.join(saves_folder or "saves", "backups", safe_char_name)
                    archive_folder = os.path.join(backup_folder, "archive")
                    os.makedirs(backup_folder, exist_ok = True)
                    os.makedirs(archive_folder, exist_ok = True)

                    backup_files = sorted(glob.glob(os.path.join(backup_folder, "*.sldsv")))
                    if len(backup_files)>=50:
                        archive_name = os.path.join(archive_folder, f"backups_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
                        with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED)as zipf:
                            for backup_file in backup_files:
                                zipf.write(backup_file, os.path.basename(backup_file))
                                os.remove(backup_file)
                        logging.info(f"Archived {len(backup_files)} backups to {archive_name}")

                    backup_filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.sldsv"
                    backup_path = os.path.join(backup_folder, backup_filename)

                    if os.path.exists(path):
                        try:
                            import shutil
                            shutil.copy2(path, backup_path)
                            logging.info(f"Created backup at {backup_path}")
                        except Exception as backup_err:
                            logging.warning(f"Failed to create backup copy: {backup_err}")
                    else:
                        _signed_json_write(backup_path, data)
                        logging.info(f"Created backup at {backup_path}")
                except Exception as backup_err:
                    logging.warning(f"Failed to create backup: {backup_err}")

            comment_lines =[]
            if isinstance(data, dict):
                comment_lines = data.pop("_save_comments", [])

            _signed_json_write(path, data, comment_lines = comment_lines or None)
            logging.info(f"Data written to {path}")
        except Exception as e:
            logging.error(f"Failed to write save to {path}: {e}")

    def _read_save_from_path(self, path):
        try:
            if not path.endswith(global_variables.get("save_extension", ".sldsv")):
                path +=global_variables.get("save_extension", ".sldsv")
            if not os.path.exists(path):
                logging.error(f"Save file '{path}' does not exist.")
                return None

            data, comment_lines, status = _signed_json_read(path, allow_unsigned = False)

            if status == "ok":
                if isinstance(data, dict):
                    if comment_lines:
                        data["_save_comments"]= comment_lines
                    logging.info(f"Loaded save from {path}")
                    return data
            elif status == "tampered":
                logging.error(f"Save file '{path}' has been tampered with — signature verification failed.")
                return None
            elif status == "unsigned":
                logging.error(f"Save file '{path}' is unsigned. Download and run convert_legacy_saves.py from github and run with --resign flag to convert.")
                return None
            elif status == "incompatible_format":
                logging.error(f"Save file '{path}' uses an incompatible legacy format. Download and run convert_legacy_saves.py from github to convert it.")
                return None

            logging.error(f"Failed to parse save file: {path}")
            return None
        except Exception as e:
            logging.error(f"Failed to read save from {path}: {e}")
    def _save_file(self, data):
        if self.currentsave is None:
            logging.error("No current save file to save data to.")
            return
        else:

            try:
                if isinstance(data, dict):
                    tbl = None

                    ct = global_variables.get('current_table')
                    if ct:
                        tbl = ct
                    else:

                        tfiles = sorted(glob.glob(os.path.join('tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
                        if tfiles:
                            tbl = os.path.basename(tfiles[0])
                    if tbl:
                        data.setdefault('_table', tbl)
            except Exception:
                pass

            if os.path.isabs(self.currentsave):
                save_path = self.currentsave
            else:
                save_path = os.path.join(saves_folder or "saves", self.currentsave or "")
            try:

                try:
                    if isinstance(data, dict):
                        if 'save_data'in globals():
                            outer = globals().get('save_data')
                            if isinstance(outer, dict)and outer is not data:
                                try:
                                    outer.clear()
                                    outer.update(data)
                                    globals()['save_data']= outer
                                except Exception:
                                    globals()['save_data']= data
                            else:
                                globals()['save_data']= data
                        else:
                            globals()['save_data']= data
                except Exception:
                    pass
                try:
                    setattr(self, '_current_save_data', data)
                except Exception:
                    pass

                try:
                    if isinstance(data, dict):
                        self._cleanup_temporary_effects(data)
                except Exception:
                    logging.exception('Failed to clean temporary effects before save')

                self._write_save_to_path(save_path, data)
            except Exception as e:
                logging.error(f"Failed to save data to {self.currentsave}: {e}")
        self._save_persistent_data()
    def _load_file(self, save_filename):

        try:
            persistent_path = os.path.join(saves_folder or "saves", "persistent_data.sldsv")
            if os.path.exists(persistent_path):
                loaded_persistent, _, p_status = _signed_json_read(persistent_path, allow_unsigned = False)
                if p_status == "tampered":
                    logging.error(f"Persistent data file '{persistent_path}' has been tampered with.")
                    loaded_persistent = None
                elif p_status == "unsigned":
                    logging.error(f"Persistent data file '{persistent_path}' is unsigned. Download and run convert_legacy_saves.py from github and run with --resign flag to sign it.")
                    loaded_persistent = None
                elif p_status == "incompatible_format":
                    logging.error(f"Persistent data file '{persistent_path}' uses an incompatible legacy format. Download and run convert_legacy_saves.py from github to convert it.")
                    loaded_persistent = None
                if isinstance(loaded_persistent, dict):
                    persistentdata.update(loaded_persistent)
                    logging.info(f"Persistent data loaded from {persistent_path}")
                else:
                    logging.warning(f"Persistent data in {persistent_path} is not a dict; got {type(loaded_persistent)}")
            else:
                logging.info("No persistent data file found, using defaults")
        except Exception as e:
            logging.warning(f"Failed to load persistent data: {e}")

        if save_filename is None:
            return None

        if os.path.isabs(save_filename):
            save_path = save_filename
        else:
            save_path = os.path.join(saves_folder or "saves", save_filename)
        if not save_path.endswith('.sldsv'):
            save_path +='.sldsv'
        if not os.path.exists(save_path):
            logging.error(f"Save file '{save_path}' does not exist.")
            return None

        try:

            data = self._read_save_from_path(save_path)
            if data is None:
                logging.error(f"Failed to load data from {save_path}")
                return None
            if not isinstance(data, dict):
                logging.error(f"Loaded data from {save_path} is not a dict; got {type(data)}")
                return None
            logging.info(f"Data loaded from {save_path}")

            try:
                table_from_save = None
                if isinstance(data, dict):
                    table_from_save = data.get('_table')or data.get('table')

                current_table = global_variables.get('current_table')

                if table_from_save and current_table:
                    current_table_base = os.path.splitext(current_table)[0]
                    save_table_base = os.path.splitext(table_from_save)[0]
                    if current_table_base !=save_table_base and current_table !=table_from_save:
                        logging.error(f"Save '{save_path}' was created with table '{table_from_save}' but current table is '{current_table}'.Load aborted.")
                        return None

                if table_from_save:

                    matches = sorted(glob.glob(os.path.join('tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
                    found = None
                    for fpath in matches:
                        try:
                            b = os.path.basename(fpath)
                            name_no_ext = os.path.splitext(b)[0]
                            absf = os.path.abspath(fpath)

                            if(
                            b ==table_from_save
                            or name_no_ext ==table_from_save
                            or absf.endswith(table_from_save)
                            or absf.endswith(table_from_save +global_variables.get('table_extension', '.sldtbl'))
                            ):
                                found = fpath
                                break
                        except Exception:
                            continue
                    if not found:
                        logging.error(f"Save '{save_path}' requires table '{table_from_save}' which is not present locally.Load aborted.")
                        return None
                else:

                    try:
                        cur_tbl = global_variables.get('current_table')
                        if not cur_tbl:
                            tfiles = sorted(glob.glob(os.path.join('tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
                            if tfiles:
                                cur_tbl = os.path.basename(tfiles[0])
                                global_variables['current_table']= cur_tbl
                                try:
                                    with open(tfiles[0], 'r', encoding = 'utf-8')as tf:
                                        globals()['table_data']= json.load(tf)
                                except Exception:
                                    pass

                        if isinstance(data, dict)and cur_tbl:
                            data.setdefault('_table', cur_tbl)
                    except Exception:
                        pass
            except Exception:
                logging.debug('Table metadata handling failed during load, continuing')
            if save_path.endswith('.sldsv'):
                parts = os.path.basename(save_path).rsplit('_', 1)
                if len(parts)==2:
                    uuid_part = parts[1].replace('.sldsv', '')
                    persistentdata["last_loaded_save"]= uuid_part
                    logging.debug(f"Updated last_loaded_save to UUID: {uuid_part}")

            data = populate_equipment_with_subslots(data, secondary_platform=_secondary_platform)

            try:
                data = self._fix_save_item_references(data)
            except Exception:
                logging.exception("Failed to fix save item references")

            data = update_item_keys_from_table(data)

            try:
                data = self._normalize_save_data(data)
                try:
                    data = self._sync_equipment_slots(data)
                except Exception:
                    logging.exception("Failed to sync equipment slots after normalization")
            except Exception as e:
                logging.warning(f"Failed to normalize save data: {e}")
            try:
                data = data if isinstance(data, dict) else {}
                self._cleanup_temporary_effects(data)
            except Exception:
                logging.exception('Failed to clean temporary effects after load')
            try:
                data = _resolve_unset_durability(data)
            except Exception:
                logging.exception("Failed to resolve unset durability values")
            try:

                try:
                    self._award_paychecks_for_save(data, save_path)
                except Exception:
                    pass
            except Exception:
                pass
            return data
        except Exception as e:
            logging.error(f"Failed to load data from '{save_path}': {e}")
            return None

    def _normalize_save_data(self, data):

        ammo_table = self._get_ammo_table_data()

        def normalize_round(r):
            if isinstance(r, dict):
                return self._ensure_round_variant(r, ammo_table)
            if isinstance(r, str):
                parts = r.split(" | ", 1)
                if len(parts)==2:
                    caliber, variant = parts
                    return {"name":r, "caliber":caliber, "variant":variant}
                round_data = {"name":r}
                return self._ensure_round_variant(round_data, ammo_table)
            round_data = {"name":str(r)}
            return self._ensure_round_variant(round_data, ammo_table)

        def normalize_mag(mag):
            if not isinstance(mag, dict):
                return {"name":str(mag), "rounds":[]}
            if "rounds"in mag and isinstance(mag["rounds"], list):
                mag["rounds"]=[normalize_round(rr)for rr in mag["rounds"]]
            return mag

        for slot_name, item in(data.get("equipment")or {}).items():

            if isinstance(item, dict):
                items_iter =[item]
            elif isinstance(item, list):
                items_iter =[it for it in item if isinstance(it, dict)]
            else:
                items_iter =[]

            for it in items_iter:
                if it.get("loaded"):
                    it["loaded"]= normalize_mag(it["loaded"])

                if it.get("rounds")and isinstance(it.get("rounds"), list):
                    it["rounds"]=[normalize_round(rr)for rr in it.get("rounds", [])]

                if it.get("chambered")and isinstance(it.get("chambered"), str):
                    it["chambered"]= normalize_round(it.get("chambered"))

                if "subslots"in it and isinstance(it["subslots"], list):
                    for sub in it["subslots"]:
                        curr = sub.get("current")
                        if isinstance(curr, dict):
                            if curr.get("loaded"):
                                curr["loaded"]= normalize_mag(curr["loaded"])
                            if curr.get("rounds")and isinstance(curr.get("rounds"), list):
                                curr["rounds"]=[normalize_round(rr)for rr in curr.get("rounds", [])]
                            if curr.get("chambered")and isinstance(curr.get("chambered"), str):
                                curr["chambered"]= normalize_round(curr.get("chambered"))

        hands = data.get("hands")or {}
        if isinstance(hands, dict)and isinstance(hands.get("items"), list):
            new_items =[]
            for it in hands.get("items", []):
                if isinstance(it, dict):
                    if it.get("rounds")and isinstance(it.get("rounds"), list):
                        it["rounds"]=[normalize_round(rr)for rr in it.get("rounds", [])]
                    new_items.append(it)
                elif isinstance(it, str):
                    new_items.append({"name":it})
                else:
                    new_items.append({"name":str(it)})
            hands["items"]= new_items

        for slot_name, item in(data.get("equipment")or {}).items():

            items_iter =[]
            if isinstance(item, dict):
                items_iter =[item]
            elif isinstance(item, list):
                items_iter =[it for it in item if isinstance(it, dict)]

            for it in items_iter:
                if "items"in it and isinstance(it["items"], list):
                    new_items =[]
                    for subit in it["items"]:
                        if isinstance(subit, dict):
                            if subit.get("rounds")and isinstance(subit.get("rounds"), list):
                                subit["rounds"]=[normalize_round(rr)for rr in subit.get("rounds", [])]
                            new_items.append(subit)
                        elif isinstance(subit, str):
                            new_items.append({"name":subit})
                        else:
                            new_items.append({"name":str(subit)})
                    it["items"]= new_items

        storage = data.get("storage")or {}
        if isinstance(storage, dict):
            for k, v in storage.items():
                if isinstance(v, list):
                    new_items =[]
                    for it in v:
                        if isinstance(it, dict):
                            if it.get("rounds")and isinstance(it.get("rounds"), list):
                                it["rounds"]=[normalize_round(rr)for rr in it.get("rounds", [])]
                            new_items.append(it)
                        elif isinstance(it, str):
                            new_items.append({"name":it})
                        else:
                            new_items.append({"name":str(it)})
                    storage[k]= new_items

        return data

    def _award_paychecks_for_save(self, save_data, save_path):
        try:
            if not isinstance(save_data, dict):
                return
            tbl_name =(save_data.get('_table')or save_data.get('table'))

            table_path = None
            if tbl_name:
                matches = sorted(glob.glob(os.path.join('tables', f"*{global_variables.get('table_extension', '.sldtbl')}")))
                for fpath in matches:
                    try:
                        b = os.path.basename(fpath)
                        name_no_ext = os.path.splitext(b)[0]
                        absf = os.path.abspath(fpath)
                        if(
                        b ==tbl_name
                        or name_no_ext ==tbl_name
                        or absf.endswith(tbl_name)
                        or absf.endswith(tbl_name +global_variables.get('table_extension', '.sldtbl'))
                        ):
                            table_path = fpath
                            break
                    except Exception:
                        continue
            table_data = None
            if table_path and os.path.exists(table_path):
                try:
                    with open(table_path, 'r', encoding = 'utf-8')as tf:
                        table_data = json.load(tf)
                except Exception:
                    table_data = None

            addl =(table_data or {}).get('additional_settings', {})
            if not addl.get('paycheck'):
                return

            pay_amount = int(addl.get('paycheck_amount', 0)or 0)
            period =(addl.get('pay_period')or '').lower()
            if pay_amount <=0 or period not in('daily', 'weekly', 'biweekly', 'monthly'):
                return

            tz = self._get_local_central_tz()or timezone.utc
            now = datetime.now(tz)

            uuid_val = None
            try:
                if save_path and os.path.exists(save_path):
                    parts = os.path.basename(save_path).rsplit('_', 1)
                    if len(parts)==2:
                        uuid_val = parts[1].replace('.sldsv', '')
            except Exception:
                uuid_val = None
            if not uuid_val:
                uuid_val = save_data.get('uuid')or save_data.get('id')or save_data.get('charactername')

            persistentdata.setdefault('paychecks', {})
            last_paid_iso = persistentdata['paychecks'].get(uuid_val)
            last_paid = None
            if last_paid_iso:
                try:
                    last_paid = datetime.fromisoformat(last_paid_iso)
                    if last_paid.tzinfo is None:
                        last_paid = last_paid.replace(tzinfo = tz)
                except Exception:
                    last_paid = None

            def make_dt(year, month, day, hour = 19, minute = 0):
                try:
                    return datetime(year, month, day, hour, minute, tzinfo = tz)
                except Exception:
                    return None

            awarded = 0

            def _apply_payment(dt_when):
                nonlocal awarded, save_data, save_path, pay_amount, uuid_val
                try:
                    save_data['money']= int(save_data.get('money', 0))+pay_amount
                except Exception:
                    save_data['money']=(save_data.get('money', 0)or 0)+pay_amount
                awarded +=1
                persistentdata['paychecks'][uuid_val]= dt_when.isoformat()
                try:
                    self._write_save_to_path(save_path, save_data)
                except Exception:
                    try:

                        if self.currentsave and os.path.basename(save_path).startswith(self.currentsave):
                            self._save_file(save_data)
                    except Exception:
                        pass
                try:
                    title = "Paycheck Received"
                    charname = save_data.get('charactername')or save_data.get('character_name')or 'Character'
                    message = f"{charname} received {format_price(pay_amount)}."
                    try:
                        self._popup_show_info(title, message, sound = 'success')
                    except Exception:
                        pass
                    try:
                        send_windows_notification(title, message)
                    except Exception:
                        pass
                except Exception:
                    pass

            if last_paid is None:

                if period =='daily':
                    cand = now.replace(hour = 19, minute = 0, second = 0, microsecond = 0)
                    if cand >now:
                        cand = cand -timedelta(days = 1)
                    if cand <=now:
                        _apply_payment(cand)
                elif period =='weekly':

                    days_back =(now.weekday()-4)%7
                    cand =(now -timedelta(days = days_back)).replace(hour = 19, minute = 0, second = 0, microsecond = 0)
                    if cand >now:
                        cand -=timedelta(weeks = 1)
                    if cand <=now:
                        _apply_payment(cand)
                elif period =='biweekly':

                    days_back =(now.weekday()-4)%7
                    cand =(now -timedelta(days = days_back)).replace(hour = 19, minute = 0, second = 0, microsecond = 0)
                    if cand >now:
                        cand -=timedelta(weeks = 1)
                    if cand <=now:
                        _apply_payment(cand)
                elif period =='monthly':

                    cand = make_dt(now.year, now.month, 1)
                    if cand and cand >now:

                        prev_month = now.month -1 or 12
                        year = now.year if now.month !=1 else now.year -1
                        cand = make_dt(year, prev_month, 1)
                    if cand and cand <=now:
                        _apply_payment(cand)
            else:

                cursor = last_paid

                if cursor.tzinfo is None:
                    cursor = cursor.replace(tzinfo = tz)

                if period =='daily':
                    next_due = cursor +timedelta(days = 1)
                    next_due = next_due.replace(hour = 19, minute = 0, second = 0, microsecond = 0)
                    while next_due <=now:
                        _apply_payment(next_due)
                        next_due = next_due +timedelta(days = 1)
                elif period =='weekly':

                    next_due = cursor

                    next_due = next_due +timedelta(days =((4 -next_due.weekday())%7))
                    next_due = next_due.replace(hour = 19, minute = 0, second = 0, microsecond = 0)
                    if next_due <=cursor:
                        next_due +=timedelta(weeks = 1)
                    while next_due <=now:
                        _apply_payment(next_due)
                        next_due +=timedelta(weeks = 1)
                elif period =='biweekly':

                    next_due = cursor

                    next_due = next_due +timedelta(days =((4 -next_due.weekday())%7))
                    next_due = next_due.replace(hour = 19, minute = 0, second = 0, microsecond = 0)
                    if next_due <=cursor:
                        next_due +=timedelta(weeks = 2)
                    while next_due <=now:
                        _apply_payment(next_due)
                        next_due +=timedelta(weeks = 2)
                elif period =='monthly':

                    def add_month(dt):
                        y = dt.year +(dt.month //12)
                        m = dt.month %12 +1
                        try:
                            return dt.replace(year = y, month = m, day = 1, hour = 19, minute = 0, second = 0, microsecond = 0)
                        except Exception:
                            return None

                    next_due = cursor.replace(day = 1, hour = 19, minute = 0, second = 0, microsecond = 0)
                    if next_due <=cursor:
                        nd = add_month(next_due)
                        if nd:
                            next_due = nd
                    while next_due and next_due <=now:
                        _apply_payment(next_due)
                        next_due = add_month(next_due)

            if awarded:
                try:
                    self._save_persistent_data()
                except Exception:
                    pass
        except Exception:
            logging.exception('Paycheck processing failed')

    def _get_all_player_items_from_save(self, save_data):
        all_items =[]
        if not save_data or not isinstance(save_data, dict):
            return all_items

        hands_items = save_data.get("hands", {}).get("items", [])
        for idx, item in enumerate(hands_items):
            if isinstance(item, dict):
                all_items.append({"item":item, "location":"hands", "index":idx})

        equipment = save_data.get("equipment", {})
        for slot_name, slot_item in equipment.items():
            if slot_item and isinstance(slot_item, dict):
                if "items"in slot_item and "capacity"in slot_item:
                    for idx, item in enumerate(slot_item.get("items", [])):
                        if isinstance(item, dict):
                            all_items.append({"item":item, "location":f"equipment.{slot_name}", "index":idx})
                if "subslots"in slot_item:
                    for subslot_idx, subslot_data in enumerate(slot_item.get("subslots", [])):
                        subslot_item = subslot_data.get("current")
                        if subslot_item and isinstance(subslot_item, dict)and "items"in subslot_item:
                            for idx, item in enumerate(subslot_item.get("items", [])):
                                if isinstance(item, dict):
                                    all_items.append({"item":item, "location":f"equipment.{slot_name}.subslot.{subslot_idx}", "index":idx})
            elif isinstance(slot_item, list):
                for list_idx, list_item in enumerate(slot_item):
                    if list_item and isinstance(list_item, dict):
                        if "items"in list_item and "capacity"in list_item:
                            for idx, item in enumerate(list_item.get("items", [])):
                                if isinstance(item, dict):
                                    all_items.append({"item":item, "location":f"equipment.{slot_name}.list.{list_idx}", "index":idx})
                        if "subslots"in list_item:
                            for subslot_idx, subslot_data in enumerate(list_item.get("subslots", [])):
                                subslot_item = subslot_data.get("current")
                                if subslot_item and isinstance(subslot_item, dict)and "items"in subslot_item:
                                    for idx, item in enumerate(subslot_item.get("items", [])):
                                        if isinstance(item, dict):
                                            all_items.append({"item":item, "location":f"equipment.{slot_name}.list.{list_idx}.subslot.{subslot_idx}", "index":idx})
        return all_items

    def _remove_item_from_save_location(self, save_data, location, index):
        if location =="hands":
            items = save_data.get("hands", {}).get("items", [])
            if 0 <=index <len(items):
                items.pop(index)
        elif location.startswith("equipment."):
            parts = location.split(".")
            slot = parts[1]
            slot_item = save_data.get("equipment", {}).get(slot)

            if len(parts)==2:
                if slot_item and isinstance(slot_item, dict)and "items"in slot_item:
                    items = slot_item.get("items", [])
                    if 0 <=index <len(items):
                        items.pop(index)
            elif len(parts)>=4 and parts[2]=="subslot":
                subslot_idx = int(parts[3])
                if slot_item and isinstance(slot_item, dict)and "subslots"in slot_item:
                    subslot_item = slot_item["subslots"][subslot_idx].get("current")
                    if subslot_item and "items"in subslot_item:
                        items = subslot_item.get("items", [])
                        if 0 <=index <len(items):
                            items.pop(index)
            elif len(parts)>=4 and parts[2]=="list":
                list_idx = int(parts[3])
                if isinstance(slot_item, list)and 0 <=list_idx <len(slot_item):
                    list_item = slot_item[list_idx]
                    if len(parts)==4:
                        if list_item and isinstance(list_item, dict)and "items"in list_item:
                            items = list_item.get("items", [])
                            if 0 <=index <len(items):
                                items.pop(index)
                    elif len(parts)>=6 and parts[4]=="subslot":
                        subslot_idx = int(parts[5])
                        if list_item and isinstance(list_item, dict)and "subslots"in list_item:
                            subslot_item = list_item["subslots"][subslot_idx].get("current")
                            if subslot_item and "items"in subslot_item:
                                items = subslot_item.get("items", [])
                                if 0 <=index <len(items):
                                    items.pop(index)

    def _fix_save_item_references(self, save_data):
        import copy as _copy
        if not isinstance(save_data, dict):
            return save_data

        try:
            tbl_path = get_current_table_path()
            if not tbl_path or not os.path.exists(tbl_path):
                return save_data
            with open(tbl_path, 'r', encoding = 'utf-8')as f:
                table_data = json.load(f)
        except Exception:
            return save_data

        tables = table_data.get('tables', {})
        if not isinstance(tables, dict):
            return save_data

        id_to_item = {}
        for subtable_items in tables.values():
            if not isinstance(subtable_items, list):
                continue
            for it in subtable_items:
                if isinstance(it, dict)and 'id'in it:
                    id_to_item[it['id']]= it

        if not id_to_item:
            return save_data

        fixed_count =[0]

        def _is_unresolved(cur):
            if isinstance(cur, int):
                return True
            if isinstance(cur, dict)and 'id'in cur and 'name'not in cur:
                return True
            return False

        def _resolve_current(obj):
            if not isinstance(obj, dict):
                return
            for acc in(obj.get('accessories')or[]):
                try:
                    cur = acc.get('current')
                    if cur is None:
                        continue
                    target_id = None
                    sub_attachment = None
                    overrides = {}
                    if isinstance(cur, int):
                        target_id = cur
                    elif isinstance(cur, dict)and 'id'in cur and 'name'not in cur:
                        target_id = cur.get('id')
                        sub_attachment = cur.get('sub_attachment')
                        for k, v in cur.items():
                            if k not in('id', 'sub_attachment'):
                                overrides[k]= v
                    if target_id is None:
                        if isinstance(cur, dict):
                            _resolve_current(cur)
                        continue
                    target = id_to_item.get(target_id)
                    if not target:
                        continue
                    new_installed = _copy.deepcopy(target)
                    for k, v in overrides.items():
                        try:
                            new_installed[k]= v
                        except Exception:
                            pass
                    acc['current']= new_installed
                    fixed_count[0]+=1
                    if sub_attachment:
                        sub_target = id_to_item.get(sub_attachment)
                        if sub_target and isinstance(new_installed.get('subslots'), list):
                            placed = False
                            for ss in new_installed['subslots']:
                                try:
                                    if ss.get('slot')==sub_target.get('slot')or ss.get('current')is None:
                                        ss['current']= _copy.deepcopy(sub_target)
                                        placed = True
                                        break
                                except Exception:
                                    pass
                            if not placed:
                                try:
                                    new_installed['subslots'][0]['current']= _copy.deepcopy(sub_target)
                                except Exception:
                                    pass
                    try:
                        _resolve_current(new_installed)
                    except Exception:
                        pass
                except Exception:
                    pass
            for s in(obj.get('subslots')or[]):
                try:
                    cur = s.get('current')
                    if cur is None:
                        continue
                    if _is_unresolved(cur):
                        tmp = {'accessories':[{'current':cur}]}
                        _resolve_current(tmp)
                        try:
                            s['current']= tmp['accessories'][0].get('current')
                        except Exception:
                            pass
                    elif isinstance(cur, dict):
                        _resolve_current(cur)
                except Exception:
                    pass
            for p in(obj.get('parts')or[]):
                try:
                    if not isinstance(p, dict):
                        continue
                    cur = p.get('current')
                    if cur is None:
                        continue
                    if _is_unresolved(cur):
                        target_id = None
                        overrides = {}
                        if isinstance(cur, int):
                            target_id = cur
                        elif isinstance(cur, dict)and 'id'in cur:
                            target_id = cur.get('id')
                            for k, v in cur.items():
                                if k != 'id':
                                    overrides[k]= v
                        if target_id is None:
                            continue
                        target = id_to_item.get(target_id)
                        if not target:
                            continue
                        new_part = _copy.deepcopy(target)
                        for k, v in overrides.items():
                            try:
                                new_part[k]= v
                            except Exception:
                                pass
                        p['current']= new_part
                        fixed_count[0]+=1
                except Exception:
                    pass

        def _process_item(item):
            if not isinstance(item, dict):
                return
            _resolve_current(item)

        for slot_name, equipped_item in save_data.get('equipment', {}).items():
            if isinstance(equipped_item, dict):
                _process_item(equipped_item)
                for sub in(equipped_item.get('subslots')or[]):
                    cur = sub.get('current')if isinstance(sub, dict)else None
                    if isinstance(cur, dict):
                        _process_item(cur)
                if isinstance(equipped_item.get('items'), list):
                    for it in equipped_item['items']:
                        _process_item(it)
            elif isinstance(equipped_item, list):
                for list_item in equipped_item:
                    if isinstance(list_item, dict):
                        _process_item(list_item)

        for item in save_data.get('hands', {}).get('items', []):
            _process_item(item)

        for item in save_data.get('storage', []):
            _process_item(item)

        if fixed_count[0]>0:
            logging.info(f"Fixed {fixed_count[0]} unresolved attachment reference(s) in save data")

        return save_data

    def _save_combat_state(self, save_data):

        try:

            self._save_file(save_data)
            logging.info("Combat state saved for %s", (self.currentsave or "<unknown>"))
        except Exception as e:
            logging.error(f"Failed to save combat state: {e}")
    def _open_modify_save_data_tool(self):
        logging.info("Modify Save Data definition called")
        self._clear_window()
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)
        add_item_button = self._create_sound_button(main_frame, "Add Item to Inventory By ID", self._open_add_item_by_id_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        add_item_button.pack(pady = 10)
        back_button = self._create_sound_button(
        main_frame,
        "Back",
        lambda:[self._clear_window(), self._open_dev_tools()],
        width = 200,
        height = 40
        )
        back_button.pack(pady = 10)

    def _save_enemy_loot_transfer(self, enemy_name, loot_items):

        try:

            transfer_data = {
            "type":"enemyloot",
            "enemy_name":enemy_name,
            "items":loot_items,
            "timestamp":datetime.now().isoformat()
            }

            safe_name = enemy_name.replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"enemyloot_{safe_name}_{timestamp}.sldenlt"
            filepath = os.path.join("enemyloot", filename)

            os.makedirs("enemyloot", exist_ok = True)

            _signed_json_write(filepath, transfer_data, binary_mode = True, portable = True)

            logging.info(f"Saved enemy loot transfer: {filepath}")
            self._popup_show_info("Success", f"Enemy loot saved as:\n{filename}", sound = "success")

        except Exception as e:
            logging.error(f"Failed to save enemy loot transfer: {e}")
            self._popup_show_info("Error", f"Failed to save: {e}", sound = "error")

    def _save_enemy_loot_transfer_silent(self, enemy_name, loot_items):

        try:
            transfer_data = {
            "type":"enemyloot",
            "enemy_name":enemy_name,
            "items":loot_items,
            "timestamp":datetime.now().isoformat()
            }

            safe_name = enemy_name.replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"enemyloot_{safe_name}_{timestamp}.sldenlt"
            filepath = os.path.join("enemyloot", filename)

            os.makedirs("enemyloot", exist_ok = True)

            _signed_json_write(filepath, transfer_data, binary_mode = True, portable = True)

            logging.info(f"Saved enemy loot transfer: {filepath}")
            return filename

        except Exception as e:
            logging.error(f"Failed to save enemy loot transfer: {e}")
            return None

    def _save_lootcrate_transfer_silent(self, crate_name, loot_items):

        try:
            transfer_data = {
            "type":"lootcrate",
            "crate_name":crate_name,
            "items":loot_items,
            "timestamp":datetime.now().isoformat()
            }

            safe_name = crate_name.replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"lootcrate_{safe_name}_{timestamp}.sldlct"
            filepath = os.path.join("lootcrates", filename)

            os.makedirs("lootcrates", exist_ok = True)

            _signed_json_write(filepath, transfer_data, binary_mode = True, portable = True)

            logging.info(f"Saved lootcrate transfer: {filepath}")
            return filename

        except Exception as e:
            logging.error(f"Failed to save lootcrate transfer: {e}")
            return None

    def _save_magazine_transfer(self, magazines):

        try:
            transfer_data = {
            "type":"magazines",
            "items":magazines,
            "timestamp":datetime.now().isoformat()
            }

            mag_name = magazines[0].get("name", "magazine").replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mag_{mag_name}_{len(magazines)}x_{timestamp}.sldtrf"
            filepath = os.path.join("transfers", filename)

            os.makedirs("transfers", exist_ok = True)

            _signed_json_write(filepath, transfer_data, binary_mode = True, portable = True)

            logging.info(f"Saved magazine transfer: {filepath}")
            self._popup_show_info("Success", f"Magazine transfer saved as:\n{filename}", sound = "success")

        except Exception as e:
            logging.error(f"Failed to save magazine transfer: {e}")
            self._popup_show_info("Error", f"Failed to save: {e}", sound = "error")

    def _save_belt_transfer(self, belt, round_count):

        try:
            transfer_data = {
            "type":"belt",
            "items":[belt],
            "timestamp":datetime.now().isoformat()
            }

            belt_name = belt.get("beltlink", "belt").replace(" ", "_").lower()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"belt_{belt_name}_{round_count}rds_{timestamp}.sldtrf"
            filepath = os.path.join("transfers", filename)

            os.makedirs("transfers", exist_ok = True)

            _signed_json_write(filepath, transfer_data, binary_mode = True, portable = True)

            logging.info(f"Saved belt transfer: {filepath}")
            self._popup_show_info("Success", f"Belt transfer saved as:\n{filename}", sound = "success")

        except Exception as e:
            logging.error(f"Failed to save belt transfer: {e}")
            self._popup_show_info("Error", f"Failed to save: {e}", sound = "error")
