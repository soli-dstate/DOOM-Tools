"""ReportsMixin — App methods for the "reports" feature area."""
from app.foundation import *


class ReportsMixin:

    def _init_combat_session_stats(self, save_data):

        try:
            ts = save_data.setdefault('tracked_stats', {})
            ts['_session_rounds_fired']= 0
            ts['_session_d20_rolls']=[]
            ts['_session_lead_rounds']= 0
            ts['_session_leadfree_rounds']= 0
            ts['_session_mags_loaded']= 0
            ts['_session_rounds_loaded']= 0
            ts['_session_start_time']= time.time()
            ts['_session_weapons_used']=[]
        except Exception:
            logging.exception('Failed to init combat session stats')

    def _update_session_fire_stats(self, save_data, rounds_fired, rolls, fired_round = None):

        try:
            ts = save_data.setdefault('tracked_stats', {})
            ts['_session_rounds_fired']= int(ts.get('_session_rounds_fired', 0))+int(rounds_fired)

            session_rolls = ts.setdefault('_session_d20_rolls', [])
            if isinstance(rolls, (list, tuple)):
                session_rolls.extend(rolls)

            is_lead_free = False
            if isinstance(fired_round, dict):
                is_lead_free = bool(fired_round.get('lead_free', False))

                if not is_lead_free:
                    variant_data = fired_round.get('variant')
                    if isinstance(variant_data, dict):
                        is_lead_free = bool(variant_data.get('lead_free', False))

                if not is_lead_free:
                    try:
                        variant_name = None
                        if isinstance(fired_round.get('variant'), str):
                            variant_name = fired_round.get('variant')
                        elif isinstance(fired_round.get('variant'), dict):
                            variant_name = fired_round['variant'].get('name')
                        if variant_name:
                            tbl_path = get_current_table_path()
                            if tbl_path and os.path.exists(tbl_path):
                                with open(tbl_path, 'r', encoding = 'utf-8')as tf:
                                    tdata = json.load(tf)
                                    ammo_arr = tdata.get('tables', {}).get('ammunition', [])
                                    for a in ammo_arr:
                                        for v in(a.get('variants')or[]):
                                            if isinstance(v, dict)and v.get('name')==variant_name:
                                                is_lead_free = bool(v.get('lead_free', False))
                                                break
                                        if is_lead_free:
                                            break
                    except Exception:
                        pass

            if is_lead_free:
                ts['_session_leadfree_rounds']= int(ts.get('_session_leadfree_rounds', 0))+int(rounds_fired)
            else:
                ts['_session_lead_rounds']= int(ts.get('_session_lead_rounds', 0))+int(rounds_fired)
        except Exception:
            logging.exception('Failed to update session fire stats')

    def _update_session_reload_stats(self, save_data, rounds_loaded):

        try:
            ts = save_data.setdefault('tracked_stats', {})
            ts['_session_mags_loaded']= int(ts.get('_session_mags_loaded', 0))+1
            ts['_session_rounds_loaded']= int(ts.get('_session_rounds_loaded', 0))+int(rounds_loaded)
        except Exception:
            logging.exception('Failed to update session reload stats')

    def _generate_combat_report_data(self, save_data):

        try:
            ts = save_data.get('tracked_stats', {})or {}
            character_name = save_data.get('charactername', 'Unknown')

            session_rolls = ts.get('_session_d20_rolls', [])or[]
            total_rolls = len(session_rolls)
            avg_roll =(sum(session_rolls)/total_rolls)if total_rolls >0 else 0.0
            nat20s = sum(1 for r in session_rolls if r ==20)
            nat1s = sum(1 for r in session_rolls if r ==1)

            lead_rounds = int(ts.get('_session_lead_rounds', 0))
            leadfree_rounds = int(ts.get('_session_leadfree_rounds', 0))
            total_fired = int(ts.get('_session_rounds_fired', 0))
            used_lead = lead_rounds >0

            mags_loaded = int(ts.get('_session_mags_loaded', 0))
            rounds_loaded = int(ts.get('_session_rounds_loaded', 0))

            lf_info = {}
            try:
                lf_path = os.path.join('remotedata', 'lfinfo.json')
                try:
                    remote_url = 'https://raw.githubusercontent.com/soli-dstate/DOOM-Tools/master/remotedata/lfinfo.json'
                    resp = requests.get(remote_url, timeout = 5)
                    if resp.status_code ==200:
                        lf_info = resp.json()
                        os.makedirs('remotedata', exist_ok = True)
                        with open(lf_path, 'w', encoding = 'utf-8')as f:
                            json.dump(lf_info, f, indent = 4)
                        logging.info('Pulled latest lfinfo.json from GitHub')
                except Exception:
                    logging.debug('Could not fetch lfinfo.json from GitHub, using local copy')
                if not lf_info and os.path.exists(lf_path):
                    with open(lf_path, 'r', encoding = 'utf-8')as f:
                        lf_info = json.load(f)
            except Exception:
                logging.exception('Failed to load lfinfo.json')

            lead_free_required = lf_info.get('lead_free_required', False)
            lead_fine = lf_info.get('fine_for_lead', 0)

            now = datetime.now()
            report = {
            'character':character_name,
            'date':now.strftime('%Y-%m-%d'),
            'time':now.strftime('%H:%M:%S'),
            'timestamp':now.strftime('%Y%m%d_%H%M%S'),
            'rounds_fired':total_fired,
            'lead_rounds_fired':lead_rounds,
            'leadfree_rounds_fired':leadfree_rounds,
            'used_lead':used_lead,
            'lead_free_required':lead_free_required,
            'lead_fine':lead_fine,
            'nat20s':nat20s,
            'nat1s':nat1s,
            'total_rolls':total_rolls,
            'average_roll':round(avg_roll, 2),
            'magazines_loaded':mags_loaded,
            'rounds_loaded':rounds_loaded,
            }

            try:
                if used_lead and lead_free_required and lead_fine:

                    try:
                        cur_money = save_data.get('money', 0)or 0
                        new_money = int(cur_money)-int(lead_fine)
                        save_data['money']= new_money

                        try:
                            self._save_file(save_data)
                        except Exception:
                            logging.exception('Failed to persist save after applying lead fine')
                        report['fine_applied']= True
                        report['money_after']= save_data['money']
                        logging.info('Applied lead fine of %s to %s; new balance: %s', lead_fine, character_name, save_data['money'])
                    except Exception:
                        logging.exception('Failed to apply lead fine')
                else:
                    report['fine_applied']= False
                    report['money_after']= save_data.get('money', 0)or 0
            except Exception:
                logging.exception('Error while checking/applying lead fine')
            return report
        except Exception:
            logging.exception('Failed to generate combat report data')
            return None

    def _format_combat_report_lines(self, report):

        if not report:
            return['COMBAT REPORT', '', 'No data available.']

        lines =[]
        lines.append('═══════════════════════════════════')
        lines.append(' COMBAT REPORT')
        lines.append('═══════════════════════════════════')
        lines.append(f" Operative: {report['character']}")
        lines.append(f" Date: {report['date']} Time: {report['time']}")
        lines.append('───────────────────────────────────')
        lines.append(f" Rounds Fired: {report['rounds_fired']}")

        if report.get('used_lead'):
            lines.append(f" ⚠ LEAD ROUNDS USED: {report['lead_rounds_fired']}")
            if report.get('lead_free_required'):
                lines.append(f" ⚠ LEAD-FREE REQUIRED — FINE: {format_price(report['lead_fine'])}")
        else:
            lines.append(' ✓ All rounds lead-free')

        lines.append(f" Lead-Free Rounds: {report['leadfree_rounds_fired']}")
        lines.append('───────────────────────────────────')
        lines.append(f" D20 Rolls: {report['total_rolls']}")
        lines.append(f" Natural 20s: {report['nat20s']}")
        lines.append(f" Natural 1s: {report['nat1s']}")
        lines.append(f" Average Roll: {report['average_roll']}")
        lines.append('───────────────────────────────────')
        lines.append(f" Magazines Loaded: {report['magazines_loaded']}")
        lines.append(f" Rounds Loaded: {report['rounds_loaded']}")
        lines.append('═══════════════════════════════════')
        return lines

    def _save_combat_report_to_file(self, report):

        try:
            os.makedirs('combatreports', exist_ok = True)
            safe_name = "".join(c if c.isalnum()or c in(' ', '-', '_')else '_'for c in report.get('character', 'Unknown'))
            filename = f"{safe_name} _ {report['date']} _ {report['time'].replace(':', '-')}.txt"
            filepath = os.path.join('combatreports', filename)

            lines = self._format_combat_report_lines(report)
            with open(filepath, 'w', encoding = 'utf-8')as f:
                f.write('\n'.join(lines))
                f.write('\n')

            logging.info(f"Combat report saved to {filepath}")
            return filepath
        except Exception:
            logging.exception('Failed to save combat report')
            return None

    def _show_combat_report_animation(self, report, on_dismiss = None):

        try:
            lines = self._format_combat_report_lines(report)

            saved_path = self._save_combat_report_to_file(report)

            overlay = customtkinter.CTkFrame(
            self.root,
            fg_color = '#1a1a1a',
            corner_radius = 0
            )
            overlay.place(relx = 0, rely = 0, relwidth = 1, relheight = 1)

            root_w = self.root.winfo_width()or 1920
            root_h = self.root.winfo_height()or 1080

            paper_w = min(520, root_w -80)
            paper_h = min(680, root_h -80)

            paper = customtkinter.CTkFrame(
            overlay,
            fg_color = '#f5f0e1',
            corner_radius = 4,
            border_width = 2,
            border_color = '#c8c0a8',
            width = paper_w,
            height = paper_h
            )

            paper_x =(root_w -paper_w)//2
            paper_start_y = -(paper_h +20)
            paper_mid_y =(root_h -paper_h)//2

            paper.place(x = paper_x, y = paper_start_y)

            content_frame = customtkinter.CTkFrame(paper, fg_color = '#f5f0e1', corner_radius = 0)
            content_frame.pack(fill = 'both', expand = True, padx = 20, pady = 20)

            dot_font = customtkinter.CTkFont(family = 'Courier New', size = 13, weight = 'bold')

            line_labels =[]
            for i, line_text in enumerate(lines):
                lbl = customtkinter.CTkLabel(
                content_frame,
                text = '',
                font = dot_font,
                text_color = '#1a1a1a',
                anchor = 'w',
                justify = 'left'
                )
                lbl.pack(anchor = 'w', pady = 1)

                words =[]
                pos = 0
                in_space = True
                for ci, ch in enumerate(line_text):
                    if ch ==' ':
                        if not in_space:
                            words.append(ci)
                        in_space = True
                    else:
                        in_space = False
                if line_text and(not words or words[-1]!=len(line_text)):
                    words.append(len(line_text))
                line_labels.append((lbl, line_text, words))

            dismiss_btn = self._create_sound_button(
            paper,
            text = 'Dismiss',
            command = lambda:None,
            width = 120,
            height = 32,
            fg_color = '#444444',
            hover_color = '#666666',
            font = customtkinter.CTkFont(size = 12)
            )

            saved_label = customtkinter.CTkLabel(
            paper,
            text = f'Saved: {os.path.basename(saved_path)}'if saved_path else '',
            font = customtkinter.CTkFont(size = 10),
            text_color = '#888888'
            )

            printer_sounds = {}
            sound_durations = {}
            try:
                for snd_name in('start', 'character', 'characterloop', 'nextline', 'paperprint'):
                    snd_path = os.path.join('sounds', 'misc', 'printer', f'{snd_name}.ogg')
                    if os.path.exists(snd_path):
                        snd = pygame.mixer.Sound(snd_path)
                        printer_sounds[snd_name]= snd
                        sound_durations[snd_name]= max(10, int(snd.get_length()*1000))
            except Exception:
                logging.debug('Failed to pre-load printer sounds')

            def _play_printer_sound(name):

                try:
                    snd = printer_sounds.get(name)
                    if snd:
                        channel = pygame.mixer.find_channel()
                        if channel:
                            channel.play(snd)
                except Exception:
                    logging.debug('Failed to play printer sound: %s', name)

            def _stop_all_printer_sounds():

                try:
                    for snd in printer_sounds.values():
                        snd.stop()
                except Exception:
                    pass

            def _sound_ms(name, fallback = 50):

                return sound_durations.get(name, fallback)

            num_lines = max(len(line_labels), 1)
            line_step =(paper_h -40)/num_lines

            initial_print_y = root_h -80
            anim_state = {
            'phase':'slide_in',
            'current_y':float(paper_start_y),
            'print_target_y':float(initial_print_y),
            'line_index':0,
            'word_index':0,
            'skipped':False,
            }

            def _dismiss():
                try:
                    overlay.destroy()
                except Exception:
                    pass
                if on_dismiss:
                    try:
                        on_dismiss()
                    except Exception:
                        pass

            def _skip():

                anim_state['skipped']= True
                _stop_all_printer_sounds()
                try:
                    for lbl, txt, _w in line_labels:
                        lbl.configure(text = txt)
                    paper.place(x = paper_x, y = int(paper_mid_y))
                    skip_btn.place_forget()
                    dismiss_btn.pack(side = 'bottom', pady =(0, 8))
                    saved_label.pack(side = 'bottom', pady =(0, 2))
                except Exception:
                    pass

            dismiss_btn.configure(command = _dismiss)

            skip_btn = self._create_sound_button(
            overlay,
            text = 'Skip',
            command = _skip,
            width = 80,
            height = 28,
            fg_color = '#555555',
            hover_color = '#777777',
            font = customtkinter.CTkFont(size = 11)
            )
            skip_btn.place(relx = 1.0, rely = 1.0, anchor = 'se', x = -20, y = -20)

            def _animate():
                try:
                    if anim_state['skipped']:
                        return

                    phase = anim_state['phase']

                    if phase =='slide_in':

                        cur = anim_state['current_y']
                        target = anim_state['print_target_y']
                        speed = max(12, abs(target -cur)*0.14)
                        new_y = cur +speed
                        if new_y >=target:
                            new_y = target
                            anim_state['phase']= 'start_sound'
                            anim_state['current_y']= new_y
                            paper.place(x = paper_x, y = int(new_y))
                            self.root.after(200, _animate)
                            return
                        anim_state['current_y']= new_y
                        paper.place(x = paper_x, y = int(new_y))
                        self.root.after(10, _animate)

                    elif phase =='start_sound':
                        _play_printer_sound('start')
                        anim_state['phase']= 'printing'
                        self.root.after(_sound_ms('start', 200), _animate)

                    elif phase =='printing':
                        idx = anim_state['line_index']
                        if idx >=len(line_labels):
                            anim_state['phase']= 'pre_final'
                            self.root.after(300, _animate)
                            return

                        lbl, full_text, words = line_labels[idx]
                        word_idx = anim_state['word_index']

                        if len(full_text)<=1:
                            lbl.configure(text = full_text)
                            anim_state['line_index']= idx +1
                            anim_state['word_index']= 0
                            anim_state['phase']= 'feed_paper'
                            self.root.after(10, _animate)
                            return

                        if word_idx >=len(words):

                            anim_state['line_index']= idx +1
                            anim_state['word_index']= 0
                            anim_state['phase']= 'feed_paper'
                            self.root.after(10, _animate)
                            return

                        if anim_state.get('current_line')!=idx:
                            anim_state['current_line']= idx
                            anim_state['char_pos']= 0

                            try:
                                lc = anim_state.pop('loop_channel', None)
                                if lc:
                                    lc.stop()
                            except Exception:
                                pass

                        end_pos = words[word_idx]
                        char_pos = anim_state['char_pos']

                        if char_pos <end_pos:

                            if not anim_state.get('loop_channel'):
                                try:
                                    loop_snd = printer_sounds.get('characterloop')
                                    if loop_snd:
                                        ch = pygame.mixer.find_channel()
                                        if ch:
                                            ch.play(loop_snd, loops = -1)
                                            anim_state['loop_channel']= ch
                                except Exception:
                                    pass

                            next_pos = char_pos +1
                            lbl.configure(text = full_text[:next_pos])
                            anim_state['char_pos']= next_pos
                            self.root.after(18, _animate)
                        else:

                            try:
                                lc = anim_state.pop('loop_channel', None)
                                if lc:
                                    lc.stop()
                            except Exception:
                                pass
                            _play_printer_sound('character')
                            anim_state['word_index']= word_idx +1

                            self.root.after(_sound_ms('character', 30)+40, _animate)

                    elif phase =='feed_paper':

                        _play_printer_sound('nextline')
                        feed_target = anim_state['current_y']-line_step
                        anim_state['feed_target']= feed_target
                        anim_state['phase']= 'feeding'
                        self.root.after(10, _animate)

                    elif phase =='feeding':

                        cur = anim_state['current_y']
                        feed_target = anim_state['feed_target']
                        speed = max(4, abs(cur -feed_target)*0.35)
                        new_y = cur -speed
                        if new_y <=feed_target:
                            new_y = feed_target
                            anim_state['current_y']= new_y
                            paper.place(x = paper_x, y = int(new_y))
                            anim_state['phase']= 'printing'
                            self.root.after(30, _animate)
                            return
                        anim_state['current_y']= new_y
                        paper.place(x = paper_x, y = int(new_y))
                        self.root.after(8, _animate)

                    elif phase =='pre_final':

                        _play_printer_sound('paperprint')
                        anim_state['phase']= 'final_slide'
                        self.root.after(10, _animate)

                    elif phase =='final_slide':

                        cur = anim_state['current_y']
                        target = float(paper_mid_y)

                        if 'final_start'not in anim_state:
                            anim_state['final_start']= time.time()
                            anim_state['final_start_y']= cur
                            anim_state['final_target_y']= target
                            anim_state['final_duration_ms']= 1360
                        elapsed =(time.time()-anim_state['final_start'])*1000.0
                        dur = anim_state.get('final_duration_ms', 400)
                        t = min(1.0, elapsed /float(dur))
                        new_y = anim_state['final_start_y']+(anim_state['final_target_y']-anim_state['final_start_y'])*t
                        anim_state['current_y']= new_y
                        paper.place(x = paper_x, y = int(new_y))
                        if t >=1.0:
                            anim_state['phase']= 'done'
                            skip_btn.place_forget()
                            try:
                                dismiss_btn.pack(side = 'bottom', pady =(0, 8))
                                saved_label.pack(side = 'bottom', pady =(0, 2))
                            except Exception:
                                pass
                            return
                        self.root.after(10, _animate)

                except Exception:
                    logging.exception('Combat report animation error')

                    try:
                        for lbl, txt, _w in line_labels:
                            lbl.configure(text = txt)
                        paper.place(x = paper_x, y = int(paper_mid_y))
                        skip_btn.place_forget()
                        dismiss_btn.pack(side = 'bottom', pady =(0, 8))
                        saved_label.pack(side = 'bottom', pady =(0, 2))
                    except Exception:
                        pass

            self.root.after(100, _animate)

        except Exception:
            logging.exception('Failed to show combat report animation')
            if on_dismiss:
                try:
                    on_dismiss()
                except Exception:
                    pass

    def _reprint_combat_report(self, filepath):

        try:
            if not os.path.exists(filepath):
                self._popup_show_info('Error', 'Combat report file not found.', sound = 'error')
                return

            with open(filepath, 'r', encoding = 'utf-8')as f:
                content = f.read()

            lines = content.strip().split('\n')

            report = {
            'character':'Unknown',
            'date':'',
            'time':'',
            'rounds_fired':0,
            'lead_rounds_fired':0,
            'leadfree_rounds_fired':0,
            'used_lead':False,
            'lead_free_required':False,
            'lead_fine':0,
            'nat20s':0,
            'nat1s':0,
            'total_rolls':0,
            'average_roll':0,
            'magazines_loaded':0,
            'rounds_loaded':0,
            }

            self._show_combat_report_reprint(lines)

        except Exception:
            logging.exception('Failed to reprint combat report')
            self._popup_show_info('Error', 'Failed to open combat report.', sound = 'error')

    def _show_combat_report_reprint(self, lines, on_dismiss = None):

        try:
            overlay = customtkinter.CTkFrame(
            self.root,
            fg_color = '#1a1a1a',
            corner_radius = 0
            )
            overlay.place(relx = 0, rely = 0, relwidth = 1, relheight = 1)

            root_w = self.root.winfo_width()or 1920
            root_h = self.root.winfo_height()or 1080

            paper_w = min(520, root_w -80)
            paper_h = min(680, root_h -80)

            paper = customtkinter.CTkFrame(
            overlay,
            fg_color = '#f5f0e1',
            corner_radius = 4,
            border_width = 2,
            border_color = '#c8c0a8',
            width = paper_w,
            height = paper_h
            )

            paper_x =(root_w -paper_w)//2
            paper_start_y = -(paper_h +20)
            paper_mid_y =(root_h -paper_h)//2

            paper.place(x = paper_x, y = paper_start_y)

            content_frame = customtkinter.CTkFrame(paper, fg_color = '#f5f0e1', corner_radius = 0)
            content_frame.pack(fill = 'both', expand = True, padx = 20, pady = 20)

            dot_font = customtkinter.CTkFont(family = 'Courier New', size = 13, weight = 'bold')

            line_labels =[]
            for line_text in lines:
                lbl = customtkinter.CTkLabel(
                content_frame,
                text = '',
                font = dot_font,
                text_color = '#1a1a1a',
                anchor = 'w',
                justify = 'left'
                )
                lbl.pack(anchor = 'w', pady = 1)
                words =[]
                pos = 0
                in_space = True
                for ci, ch in enumerate(line_text):
                    if ch ==' ':
                        if not in_space:
                            words.append(ci)
                        in_space = True
                    else:
                        in_space = False
                if line_text and(not words or words[-1]!=len(line_text)):
                    words.append(len(line_text))
                line_labels.append((lbl, line_text, words))

            dismiss_btn = self._create_sound_button(
            paper,
            text = 'Dismiss',
            command = lambda:None,
            width = 120,
            height = 32,
            fg_color = '#444444',
            hover_color = '#666666',
            font = customtkinter.CTkFont(size = 12)
            )

            printer_sounds = {}
            sound_durations = {}
            try:
                for snd_name in('start', 'character', 'characterloop', 'nextline', 'paperprint'):
                    snd_path = os.path.join('sounds', 'misc', 'printer', f'{snd_name}.ogg')
                    if os.path.exists(snd_path):
                        snd = pygame.mixer.Sound(snd_path)
                        printer_sounds[snd_name]= snd
                        sound_durations[snd_name]= max(10, int(snd.get_length()*1000))
            except Exception:
                logging.debug('Failed to pre-load printer sounds')

            def _play_printer_sound(name):

                try:
                    snd = printer_sounds.get(name)
                    if snd:
                        channel = pygame.mixer.find_channel()
                        if channel:
                            channel.play(snd)
                except Exception:
                    logging.debug('Failed to play printer sound: %s', name)

            def _stop_all_printer_sounds():

                try:
                    for snd in printer_sounds.values():
                        snd.stop()
                except Exception:
                    pass

            def _sound_ms(name, fallback = 50):

                return sound_durations.get(name, fallback)

            num_lines = max(len(line_labels), 1)
            line_step =(paper_h -40)/num_lines

            initial_print_y = root_h -80
            anim_state = {
            'phase':'slide_in',
            'current_y':float(paper_start_y),
            'print_target_y':float(initial_print_y),
            'line_index':0,
            'word_index':0,
            'skipped':False,
            }

            def _dismiss():
                try:
                    overlay.destroy()
                except Exception:
                    pass
                if on_dismiss:
                    try:
                        on_dismiss()
                    except Exception:
                        pass

            def _skip():

                anim_state['skipped']= True
                _stop_all_printer_sounds()
                try:
                    for lbl, txt, _w in line_labels:
                        lbl.configure(text = txt)
                    paper.place(x = paper_x, y = int(paper_mid_y))
                    skip_btn.place_forget()
                    dismiss_btn.pack(side = 'bottom', pady =(0, 8))
                except Exception:
                    pass

            dismiss_btn.configure(command = _dismiss)

            skip_btn = self._create_sound_button(
            overlay,
            text = 'Skip',
            command = _skip,
            width = 80,
            height = 28,
            fg_color = '#555555',
            hover_color = '#777777',
            font = customtkinter.CTkFont(size = 11)
            )
            skip_btn.place(relx = 1.0, rely = 1.0, anchor = 'se', x = -20, y = -20)

            def _animate():
                try:
                    if anim_state['skipped']:
                        return

                    phase = anim_state['phase']

                    if phase =='slide_in':

                        cur = anim_state['current_y']
                        target = anim_state['print_target_y']
                        speed = max(12, abs(target -cur)*0.14)
                        new_y = cur +speed
                        if new_y >=target:
                            new_y = target
                            anim_state['phase']= 'start_sound'
                            anim_state['current_y']= new_y
                            paper.place(x = paper_x, y = int(new_y))
                            self.root.after(200, _animate)
                            return
                        anim_state['current_y']= new_y
                        paper.place(x = paper_x, y = int(new_y))
                        self.root.after(10, _animate)

                    elif phase =='start_sound':
                        _play_printer_sound('start')
                        anim_state['phase']= 'printing'
                        self.root.after(_sound_ms('start', 200), _animate)

                    elif phase =='printing':
                        idx = anim_state['line_index']
                        if idx >=len(line_labels):
                            anim_state['phase']= 'pre_final'
                            self.root.after(300, _animate)
                            return

                        lbl, full_text, words = line_labels[idx]
                        word_idx = anim_state['word_index']

                        if len(full_text)<=1:
                            lbl.configure(text = full_text)
                            anim_state['line_index']= idx +1
                            anim_state['word_index']= 0
                            anim_state['phase']= 'feed_paper'
                            self.root.after(10, _animate)
                            return

                        if word_idx >=len(words):

                            anim_state['line_index']= idx +1
                            anim_state['word_index']= 0
                            anim_state['phase']= 'feed_paper'
                            self.root.after(10, _animate)
                            return

                        if anim_state.get('current_line')!=idx:
                            anim_state['current_line']= idx
                            anim_state['char_pos']= 0
                            try:
                                lc = anim_state.pop('loop_channel', None)
                                if lc:
                                    lc.stop()
                            except Exception:
                                pass

                        end_pos = words[word_idx]
                        char_pos = anim_state['char_pos']

                        if char_pos <end_pos:
                            if not anim_state.get('loop_channel'):
                                try:
                                    loop_snd = printer_sounds.get('characterloop')
                                    if loop_snd:
                                        ch = pygame.mixer.find_channel()
                                        if ch:
                                            ch.play(loop_snd, loops = -1)
                                            anim_state['loop_channel']= ch
                                except Exception:
                                    pass

                            next_pos = char_pos +1
                            lbl.configure(text = full_text[:next_pos])
                            anim_state['char_pos']= next_pos
                            self.root.after(18, _animate)
                        else:
                            try:
                                lc = anim_state.pop('loop_channel', None)
                                if lc:
                                    lc.stop()
                            except Exception:
                                pass
                            _play_printer_sound('character')
                            anim_state['word_index']= word_idx +1
                            self.root.after(_sound_ms('character', 30)+40, _animate)

                    elif phase =='feed_paper':
                        _play_printer_sound('nextline')
                        feed_target = anim_state['current_y']-line_step
                        anim_state['feed_target']= feed_target
                        anim_state['phase']= 'feeding'
                        self.root.after(10, _animate)

                    elif phase =='feeding':
                        cur = anim_state['current_y']
                        feed_target = anim_state['feed_target']
                        speed = max(4, abs(cur -feed_target)*0.35)
                        new_y = cur -speed
                        if new_y <=feed_target:
                            new_y = feed_target
                            anim_state['current_y']= new_y
                            paper.place(x = paper_x, y = int(new_y))
                            anim_state['phase']= 'printing'
                            self.root.after(30, _animate)
                            return
                        anim_state['current_y']= new_y
                        paper.place(x = paper_x, y = int(new_y))
                        self.root.after(8, _animate)

                    elif phase =='pre_final':
                        _play_printer_sound('paperprint')
                        anim_state['phase']= 'final_slide'
                        self.root.after(10, _animate)

                    elif phase =='final_slide':

                        cur = anim_state['current_y']
                        target = float(paper_mid_y)

                        if 'final_start'not in anim_state:
                            anim_state['final_start']= time.time()
                            anim_state['final_start_y']= cur
                            anim_state['final_target_y']= target
                            anim_state['final_duration_ms']= 1360
                        elapsed =(time.time()-anim_state['final_start'])*1000.0
                        dur = anim_state.get('final_duration_ms', 400)
                        t = min(1.0, elapsed /float(dur))
                        new_y = anim_state['final_start_y']+(anim_state['final_target_y']-anim_state['final_start_y'])*t
                        anim_state['current_y']= new_y
                        paper.place(x = paper_x, y = int(new_y))
                        if t >=1.0:
                            anim_state['phase']= 'done'
                            skip_btn.place_forget()
                            try:
                                dismiss_btn.pack(side = 'bottom', pady =(0, 8))
                            except Exception:
                                pass
                            return
                        self.root.after(10, _animate)

                except Exception:
                    logging.exception('Combat report reprint animation error')
                    try:
                        for lbl, txt, _w in line_labels:
                            lbl.configure(text = txt)
                        paper.place(x = paper_x, y = int(paper_mid_y))
                        skip_btn.place_forget()
                        dismiss_btn.pack(side = 'bottom', pady =(0, 8))
                    except Exception:
                        pass

            self.root.after(100, _animate)

        except Exception:
            logging.exception('Failed to show combat report reprint animation')

    def _open_combat_reports_menu(self):

        logging.info('Combat Reports menu opened')

        self._clear_window()
        self._play_ui_sound('whoosh1')

        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill = 'both', expand = True, padx = 20, pady = 20)

        title_label = customtkinter.CTkLabel(
        main_frame,
        text = 'Combat Reports',
        font = customtkinter.CTkFont(size = 24, weight = 'bold')
        )
        title_label.pack(pady =(0, 20))

        reports_dir = 'combatreports'
        os.makedirs(reports_dir, exist_ok = True)

        report_files = sorted(
        [f for f in os.listdir(reports_dir)if f.endswith('.txt')],
        reverse = True
        )

        if not report_files:
            empty_label = customtkinter.CTkLabel(
            main_frame,
            text = 'No combat reports found.',
            font = customtkinter.CTkFont(size = 14),
            text_color = 'gray'
            )
            empty_label.pack(pady = 40)
        else:
            scroll = customtkinter.CTkScrollableFrame(main_frame, fg_color = 'transparent')
            scroll.pack(fill = 'both', expand = True, padx = 10, pady = 10)

            for report_file in report_files:
                report_path = os.path.join(reports_dir, report_file)
                display_name = report_file.replace('.txt', '').replace('_', ' ')

                row_frame = customtkinter.CTkFrame(scroll, fg_color = 'transparent')
                row_frame.pack(fill = 'x', pady = 3, padx = 5)

                name_label = customtkinter.CTkLabel(
                row_frame,
                text = display_name,
                font = customtkinter.CTkFont(size = 12),
                anchor = 'w'
                )
                name_label.pack(side = 'left', fill = 'x', expand = True)

                reprint_btn = self._create_sound_button(
                row_frame,
                text = 'Re-Print',
                command = lambda p = report_path:self._reprint_combat_report(p),
                width = 100,
                height = 28,
                font = customtkinter.CTkFont(size = 11)
                )
                reprint_btn.pack(side = 'right', padx = 5)

                delete_btn = self._create_sound_button(
                row_frame,
                text = 'Delete',
                command = lambda p = report_path:self._delete_combat_report(p),
                width = 80,
                height = 28,
                fg_color = '#8B0000',
                hover_color = '#A52A2A',
                font = customtkinter.CTkFont(size = 11)
                )
                delete_btn.pack(side = 'right', padx = 2)

        back_button = self._create_sound_button(
        main_frame,
        'Back',
        lambda:[self._clear_window(), self._build_main_menu()],
        width = 200,
        height = 40
        )
        back_button.pack(pady = 10)

    def _delete_combat_report(self, filepath):

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logging.info(f'Deleted combat report: {filepath}')
            self._open_combat_reports_menu()
        except Exception:
            logging.exception('Failed to delete combat report')
            self._popup_show_info('Error', 'Failed to delete report.', sound = 'error')
