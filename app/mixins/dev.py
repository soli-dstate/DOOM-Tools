"""DevMixin — App methods for the "dev" feature area."""
from app.foundation import *


class DevMixin:

    def _create_dev_toolbar(self):
        try:

            if not getattr(self, "_dev_toolbar_frame", None):

                top = customtkinter.CTkToplevel()

                try:
                    top._is_dev_toolbar = True
                except Exception:
                    pass
                top.title("devtools")
                top.resizable(True, True)

                try:
                    top.configure(fg_color = "#1f1f1f")
                except Exception:
                    pass

                font_large = customtkinter.CTkFont(size = 16)
                content = customtkinter.CTkFrame(top, fg_color = "#1f1f1f")
                try:
                    content.pack(fill = "both", expand = True, padx = 8, pady = 8)
                except Exception:
                    content.grid(row = 0, column = 0, sticky = "nsew", padx = 8, pady = 8)

                cpu_row = customtkinter.CTkFrame(content, fg_color = "transparent")
                cpu_row.pack(anchor = "w")
                self._dev_cpu_text = customtkinter.CTkLabel(cpu_row, text = "CPU/MEM:", font = customtkinter.CTkFont(size = 13), anchor = "w")
                self._dev_cpu_text.pack(side = "left")
                self._dev_cpu_value = customtkinter.CTkLabel(cpu_row, text = "initializing", font = font_large, text_color = "cyan", anchor = "w")
                self._dev_cpu_value.pack(side = "left", padx =(6, 0))

                gpu_row = customtkinter.CTkFrame(content, fg_color = "transparent")
                gpu_row.pack(anchor = "w", pady =(2, 0))
                self._dev_gpu_text = customtkinter.CTkLabel(gpu_row, text = "GPU:", font = customtkinter.CTkFont(size = 13), anchor = "w")
                self._dev_gpu_text.pack(side = "left")
                self._dev_gpu_value = customtkinter.CTkLabel(gpu_row, text = "N/A", font = font_large, text_color = "cyan", anchor = "w")
                self._dev_gpu_value.pack(side = "left", padx =(6, 0))

                self._dev_thread_lbl = customtkinter.CTkLabel(content, text = "Threads: N/A", font = font_large, anchor = "w")
                self._dev_thread_lbl.pack(anchor = "w", pady =(4, 0))

                logs_row = customtkinter.CTkFrame(content, fg_color = "transparent")
                logs_row.pack(anchor = "w", pady =(6, 0))
                small_font = customtkinter.CTkFont(size = 14)

                def _make_counter(parent, text, color):
                    t = customtkinter.CTkLabel(parent, text = text, font = small_font)
                    v = customtkinter.CTkLabel(parent, text = "0", font = small_font, text_color = color)
                    container = customtkinter.CTkFrame(parent, fg_color = "transparent")
                    t.pack(in_ = container, side = "left")
                    v.pack(in_ = container, side = "left", padx =(4, 8))
                    container.pack(side = "left")
                    return t, v

                _, self._dev_log_info_lbl = _make_counter(logs_row, "INFO:", "green")
                _, self._dev_log_warn_lbl = _make_counter(logs_row, "WARN:", "yellow")
                _, self._dev_log_err_lbl = _make_counter(logs_row, "ERR:", "red")
                _, self._dev_log_dbg_lbl = _make_counter(logs_row, "DBG:", "cyan")
                _, self._dev_log_crit_lbl = _make_counter(logs_row, "CRIT:", "magenta")

                table_row = customtkinter.CTkFrame(content, fg_color = "transparent")
                table_row.pack(anchor = "w", pady =(6, 0))
                self._dev_tables_lbl = customtkinter.CTkLabel(table_row, text = "Tables: 0 Items: 0 IDs: 0 Dups: 0", font = small_font, anchor = "w")
                self._dev_tables_lbl.pack(side = "left")
                nid_text = customtkinter.CTkLabel(table_row, text = "Next ID:", font = small_font)
                nid_text.pack(side = "left", padx =(12, 2))
                self._dev_nextid_lbl = customtkinter.CTkLabel(table_row, text = "N/A", font = small_font, text_color = "#7EC8FF")
                self._dev_nextid_lbl.pack(side = "left")

                defs_frame = customtkinter.CTkScrollableFrame(content, height = 220)
                defs_frame.pack(fill = "both", expand = False, pady =(8, 0))
                defs_label_title = customtkinter.CTkLabel(defs_frame, text = "Loaded Definitions:", font = small_font, anchor = "w")
                defs_label_title.pack(anchor = "w", pady =(4, 2), padx = 4)
                self._dev_defs_lbl = customtkinter.CTkLabel(defs_frame, text = "(refreshing...)", font = customtkinter.CTkFont(size = 13), anchor = "w", justify = "left")
                self._dev_defs_lbl.pack(fill = "both", expand = True, padx = 4, pady =(0, 4))

                try:
                    inspect_btn = customtkinter.CTkButton(content, text = "Inspect Tables/Strings", command = self._open_dev_data_viewer, width = 240, height = 36, fg_color = "#2f2f2f")
                    inspect_btn.pack(anchor = "w", pady =(8, 0))
                except Exception:
                    pass

                try:
                    self._dev_logs_summary = customtkinter.CTkLabel(content, text = "", font = small_font, anchor = "w")
                    self._dev_logs_summary.pack(anchor = "w", pady =(4, 0))
                except Exception:
                    self._dev_logs_summary = None

                try:
                    try:
                        content.update_idletasks()
                    except Exception:
                        top.update_idletasks()

                    try:
                        req_w = content.winfo_reqwidth()+16
                        req_h = content.winfo_reqheight()+16
                    except Exception:
                        req_w = top.winfo_reqwidth()
                        req_h = top.winfo_reqheight()
                    req_w = max(req_w, 320)
                    req_h = max(req_h, 240)
                    try:
                        top.minsize(req_w, req_h)
                        top.geometry(f"{req_w}x{req_h}")
                    except Exception:
                        pass
                except Exception:
                    pass

                self._dev_toolbar_frame = top

                try:
                    import GPUtil
                    self._gputil = GPUtil
                except Exception:
                    self._gputil = None

                try:
                    self._dev_proc = psutil.Process()
                except Exception:
                    self._dev_proc = None

                try:
                    self._dev_queue = queue.Queue(maxsize = 1)
                except Exception:
                    self._dev_queue = None
                try:
                    self._dev_worker_running = True
                    self._dev_worker_stop = threading.Event()
                except Exception:
                    self._dev_worker_running = False
                    self._dev_worker_stop = threading.Event()

                try:
                    def _on_dev_close():
                        try:
                            self._dev_worker_running = False
                        except Exception:
                            pass
                        try:
                            if getattr(top, 'destroy', None):
                                top.destroy()
                        except Exception:
                            pass
                        try:
                            self._dev_toolbar_frame = None
                        except Exception:
                            pass
                    top.protocol("WM_DELETE_WINDOW", _on_dev_close)
                except Exception:
                    pass

                try:
                    if getattr(self, '_dev_worker_thread', None)is None:
                        self._dev_worker_thread = threading.Thread(target = self._dev_toolbar_worker, name = 'DevToolbarWorker', daemon = True)
                        self._dev_worker_thread.start()
                except Exception:
                    pass

                try:
                    self._update_dev_toolbar()
                except Exception:
                    pass
        except Exception:
            logging.exception("Failed to create dev toolbar")

    def _open_dev_data_viewer(self):
        try:
            top = customtkinter.CTkToplevel()
            top.title("Dev Data Explorer")
            top.transient(self.root)
            self._center_popup_on_window(top, 1000, 600)
            try:
                top.configure(fg_color = "#1f1f1f")
            except Exception:
                pass

            left = customtkinter.CTkFrame(top, width = 300)
            left.pack(side = "left", fill = "y", padx = 6, pady = 6)
            right = customtkinter.CTkFrame(top)
            right.pack(side = "right", fill = "both", expand = True, padx = 6, pady = 6)

            lbl = customtkinter.CTkLabel(left, text = "In-memory data:", anchor = "w")
            lbl.pack(anchor = "w", pady =(4, 2))

            listbox_frame = customtkinter.CTkFrame(left, fg_color = "transparent")
            listbox_frame.pack(fill = "both", expand = True)

            lb = _tk.Listbox(listbox_frame, width = 48, exportselection = False)
            sb = _tk.Scrollbar(listbox_frame, command = lb.yview)
            lb.config(yscrollcommand = sb.set)
            lb.pack(side = "left", fill = "both", expand = True)
            sb.pack(side = "right", fill = "y")

            tbl_map =[]
            try:
                if globals().get('table_data')is not None:
                    lb.insert(_tk.END, "global_table_data")
                    tbl_map.append(("global_table_data", globals().get('table_data')))
            except Exception:
                pass
            try:
                if globals().get('all_table_items')is not None:
                    lb.insert(_tk.END, "all_table_items")
                    tbl_map.append(("all_table_items", globals().get('all_table_items')))
            except Exception:
                pass

            try:
                extras =[
                ("currentsave", globals().get('currentsave')),
                ("save_data", globals().get('save_data')),
                ("self._current_save_data", getattr(self, '_current_save_data', None)),
                ("global_variables", globals().get('global_variables')),
                ("appearance_settings", globals().get('appearance_settings')),
                ("folders", globals().get('folders')),
                ]
                for name, val in extras:
                    try:
                        if val is not None:
                            lb.insert(_tk.END, name)
                            tbl_map.append((name, val))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                cur = global_variables.get('current_table')
                if cur:
                    lb.insert(_tk.END, f"current_table: {cur}")

                    tbl_map.append((f"current_table: {cur}", globals().get('table_data')))
            except Exception:
                pass

            top_row = customtkinter.CTkFrame(right, fg_color = "transparent")
            top_row.pack(fill = "x")

            sub_lbl = customtkinter.CTkLabel(top_row, text = "Subtable:")
            sub_lbl.pack(side = "left", padx =(4, 8))

            sub_var = customtkinter.StringVar(value = "(none)")
            sub_menu = customtkinter.CTkOptionMenu(top_row, values =["(none)"], variable = sub_var, width = 240)
            sub_menu.pack(side = "left")

            def _show_content_from_selection():
                try:
                    sel = lb.curselection()
                    if not sel:
                        return
                    idx = sel[0]
                    name, obj = tbl_map[idx]

                    data = None
                    if isinstance(obj, str)and os.path.isfile(obj):
                        try:
                            with open(obj, 'r', encoding = 'utf-8')as f:
                                data = json.load(f)
                        except Exception as e:
                            txt.delete('1.0', _tk.END)
                            txt.insert(_tk.END, f"Failed to load file: {e}")
                            return
                    else:
                        data = obj

                    choice = sub_var.get()

                    if isinstance(data, dict):
                        if name =='global_table_data'or name.startswith('current_table'):

                            content = data.get('tables', data)

                            if choice and choice !='(none)':
                                content = content.get(choice, {})
                        else:
                            if choice and choice !="(none)":
                                content = data.get('tables', {}).get(choice, data.get(choice, {}))
                            else:
                                content = data
                    else:
                        content = data

                    txt.delete('1.0', _tk.END)
                    try:
                        txt.insert(_tk.END, json.dumps(content, indent = 2, ensure_ascii = False, default = str))
                    except Exception:
                        txt.insert(_tk.END, str(content))
                except Exception as e:
                    txt.delete('1.0', _tk.END)
                    txt.insert(_tk.END, f"Failed to load: {e}")

            view_btn = customtkinter.CTkButton(top_row, text = "Refresh / Show", command = lambda:(_populate_submenu(), _show_content_from_selection()), width = 140)
            view_btn.pack(side = "left", padx = 8)

            def _open_strings_window():
                try:
                    found =[]
                    def _collect(o):
                        try:
                            if isinstance(o, str):

                                try:
                                    ext = str(global_variables.get('table_extension', '.sldtbl')).lower()
                                except Exception:
                                    ext = '.sldtbl'
                                low = o.lower()
                                if ext and ext in low:
                                    return
                                if re.search(r"\.sldtbl\b", low):
                                    return
                                found.append(o)
                            elif isinstance(o, dict):
                                for v in o.values():
                                    _collect(v)
                            elif isinstance(o, list)or isinstance(o, tuple):
                                for v in o:
                                    _collect(v)
                        except Exception:
                            pass

                    for name, obj in tbl_map:
                        _collect(obj)

                    uniq =[]
                    seen = set()
                    for s in found:
                        if s and s not in seen:
                            seen.add(s)
                            uniq.append(s)

                    sw = customtkinter.CTkToplevel()
                    sw.title('Strings Explorer')
                    sw.geometry('700x500')
                    lf = customtkinter.CTkFrame(sw)
                    lf.pack(fill = 'both', expand = True, padx = 6, pady = 6)
                    lbox = _tk.Listbox(lf)
                    lbox.pack(side = 'left', fill = 'y')
                    scr = _tk.Scrollbar(lf, command = lbox.yview)
                    scr.pack(side = 'left', fill = 'y')
                    lbox.config(yscrollcommand = scr.set)
                    txtw = _tk.Text(sw)
                    txtw.pack(side = 'right', fill = 'both', expand = True)
                    for s in uniq:
                        try:
                            lbox.insert(_tk.END, s[:120])
                        except Exception:
                            lbox.insert(_tk.END, str(s))

                    def _on_string_select(evt = None):
                        try:
                            sel = lbox.curselection()
                            if not sel:
                                return
                            idx = sel[0]
                            s = uniq[idx]
                            txtw.delete('1.0', _tk.END)
                            txtw.insert(_tk.END, s)
                        except Exception:
                            pass

                    lbox.bind('<<ListboxSelect>>', _on_string_select)
                except Exception:
                    logging.exception('Failed opening strings window')

            strings_btn = customtkinter.CTkButton(top_row, text = "Show Strings", command = _open_strings_window, width = 140)
            strings_btn.pack(side = "right", padx = 8)

            txt = _tk.Text(right)
            txt.pack(fill = "both", expand = True)

            def _populate_submenu():
                try:
                    sel = lb.curselection()
                    if not sel:
                        sub_menu.configure(values =["(none)"], variable = sub_var)
                        return
                    idx = sel[0]
                    _, path = tbl_map[idx]

                    data = None
                    if isinstance(path, str)and os.path.isfile(path):
                        try:
                            with open(path, 'r', encoding = 'utf-8')as f:
                                data = json.load(f)
                        except Exception:
                            data = None
                    else:
                        data = path
                    keys =[]
                    if isinstance(data, dict):

                        if 'tables'in data and isinstance(data['tables'], dict):
                            keys = sorted(list(data['tables'].keys()))
                        else:
                            keys = sorted(list(data.keys()))
                    if not keys:
                        keys =["(none)"]
                    sub_menu.configure(values =["(none)"]+keys)
                except Exception:
                    sub_menu.configure(values =["(none)"])

            lb.bind('<<ListboxSelect>>', lambda evt:(_populate_submenu(), _show_content_from_selection()))

            try:
                if tbl_map:
                    lb.selection_set(0)
                    _populate_submenu()
                    _show_content_from_selection()
            except Exception:
                pass

        except Exception:
            logging.exception('Failed opening Dev Data Explorer')

    def _dev_toolbar_worker(self):

        try:
            while getattr(self, '_dev_worker_running', False):
                snap = {}
                try:
                    snap['sys_cpu']= psutil.cpu_percent(interval = None)
                except Exception:
                    snap['sys_cpu']= 0.0
                try:
                    proc = getattr(self, "_dev_proc", None)or psutil.Process()
                    snap['app_cpu']= proc.cpu_percent(interval = None)
                except Exception:
                    snap['app_cpu']= 0.0
                try:
                    vm = psutil.virtual_memory()
                    snap['sys_mem_pct']= vm.percent
                    snap['sys_total_mb']= int(vm.total /(1024 *1024))
                except Exception:
                    snap['sys_mem_pct']= 0.0
                    snap['sys_total_mb']= 0
                try:
                    app_rss = proc.memory_info().rss if proc else 0
                    snap['app_rss_mb']= int(app_rss /(1024 *1024))
                except Exception:
                    snap['app_rss_mb']= 0
                try:
                    snap['app_mem_pct']= round((snap.get('app_rss_mb', 0)/snap.get('sys_total_mb', 1))*100, 1)if snap.get('sys_total_mb')else 0.0
                except Exception:
                    snap['app_mem_pct']= 0.0
                try:
                    snap['threads']= proc.num_threads()if proc else threading.active_count()
                except Exception:
                    snap['threads']= threading.active_count()

                try:
                    gput = getattr(self, "_gputil", None)
                    got = False
                    gpu_str = "N/A"
                    if gput:
                        try:
                            gpus = gput.getGPUs()
                            if gpus:
                                g = gpus[0]
                                gpu_str = f"GPU {g.id}: {int(g.load *100)}% {int(g.memoryUsed)}/{int(g.memoryTotal)}MB"
                                got = True
                        except Exception:
                            got = False
                    if not got:
                        try:
                            if shutil.which("nvidia-smi"):
                                out = subprocess.check_output([
                                "nvidia-smi",
                                "--query-gpu=utilization.gpu, memory.used, memory.total",
                                "--format=csv, noheader, nounits"
                                ], text = True, stderr = subprocess.DEVNULL)
                                line = out.strip().splitlines()[0]
                                parts =[p.strip()for p in line.split(', ')]
                                if len(parts)>=3:
                                    util, used, total = parts[0], parts[1], parts[2]
                                    gpu_str = f"GPU 0: {util}% {used}/{total}MB"
                        except Exception:
                            pass
                    snap['gpu_str']= gpu_str
                except Exception:
                    snap['gpu_str']= 'N/A'

                try:
                    snap['info_ct']= dev_log_counters.get('INFO', 0)
                    snap['warn_ct']= dev_log_counters.get('WARNING', 0)
                    snap['err_ct']= dev_log_counters.get('ERROR', 0)
                    snap['dbg_ct']= dev_log_counters.get('DEBUG', 0)
                    snap['crt_ct']= dev_log_counters.get('CRITICAL', 0)
                except Exception:
                    snap['info_ct']= snap['warn_ct']= snap['err_ct']= snap['dbg_ct']= snap['crt_ct']= 0

                try:
                    table_files = glob.glob(os.path.join('tables', '*.sldtbl'))
                    snap['tbl_count']= len(table_files)
                    total_items = 0
                    id_map = {}
                    for tf in table_files:
                        try:
                            with open(tf, 'r', encoding = 'utf-8')as fh:
                                td = json.load(fh)
                            tables = td.get('tables', {})
                            for sub, items in tables.items():
                                if isinstance(items, list):
                                    for it in items:
                                        total_items +=1
                                        if isinstance(it, dict)and 'id'in it:
                                            iid = it.get('id')
                                            id_map[iid]= id_map.get(iid, 0)+1
                        except Exception:
                            continue
                    snap['total_items']= total_items
                    snap['duplicate_ids']= sum(1 for k, v in id_map.items()if v >1)
                    snap['total_ids']= len(id_map)
                    snap['id_map']= id_map
                except Exception:
                    snap['tbl_count']= snap['total_items']= snap['duplicate_ids']= snap['total_ids']= 0
                    snap['id_map']= {}

                try:
                    ths = threading.enumerate()
                    snap['thread_names']=[t.name for t in ths][:8]
                except Exception:
                    snap['thread_names']=[]

                try:
                    defs_list =[]
                    repo_root = os.path.abspath(os.getcwd())
                    main_mod = sys.modules.get('__main__')
                    if main_mod:
                        for n, o in inspect.getmembers(main_mod):
                            try:
                                if inspect.isfunction(o):
                                    defs_list.append(f"fn: {n}")
                                elif inspect.isclass(o):
                                    defs_list.append(f"class: {n}")
                            except Exception:
                                continue
                    for mname, mod in list(sys.modules.items()):
                        try:
                            mf = getattr(mod, '__file__', None)
                            if not mf:
                                continue
                            mf_abs = os.path.abspath(mf)
                            if not mf_abs.startswith(repo_root):
                                continue
                            for n, o in inspect.getmembers(mod):
                                try:
                                    if inspect.isfunction(o):
                                        defs_list.append(f"{mname}.fn:{n}")
                                    elif inspect.isclass(o):
                                        defs_list.append(f"{mname}.class:{n}")
                                except Exception:
                                    continue
                        except Exception:
                            continue
                    defs_list = sorted(set(defs_list))[:400]
                    snap['defs_text']= "\n".join(defs_list)if defs_list else '(no definitions found)'
                except Exception:
                    snap['defs_text']= '(error collecting definitions)'

                try:
                    q = getattr(self, '_dev_queue', None)
                    if q is not None:
                        try:

                            while not q.empty():
                                try:
                                    q.get_nowait()
                                except Exception:
                                    break
                            q.put_nowait(snap)
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    # Use Event.wait() not time.sleep(): Python 3.13 free-threaded
                    # GC stop-the-world crashes time.sleep() via PyEval_RestoreThread.
                    getattr(self, '_dev_worker_stop', threading.Event()).wait(1.0)
                except BaseException:
                    break
        except BaseException:
            pass

    def _update_dev_toolbar(self):
        try:

            try:
                if global_variables.get("devmode", {}).get("value")and not getattr(self, "_dev_toolbar_frame", None):
                    try:
                        self._create_dev_toolbar()
                    except Exception:
                        pass
                elif getattr(self, "_dev_toolbar_frame", None):
                    try:
                        if not getattr(self._dev_toolbar_frame, 'winfo_exists', lambda:True)():

                            self._create_dev_toolbar()
                    except Exception:
                        pass
            except Exception:
                pass

            snap = None
            try:
                if getattr(self, '_dev_queue', None):
                    try:
                        snap = self._dev_queue.get_nowait()
                    except Exception:
                        snap = None
            except Exception:
                snap = None

            if snap:

                sys_cpu = snap.get('sys_cpu', 0.0)
                app_cpu = snap.get('app_cpu', 0.0)
                sys_mem_pct = snap.get('sys_mem_pct', 0.0)
                sys_total_mb = snap.get('sys_total_mb', 0)
                app_rss_mb = snap.get('app_rss_mb', 0)
                app_mem_pct = snap.get('app_mem_pct', 0.0)
                threads = snap.get('threads', 0)
                gpu_str = snap.get('gpu_str', 'N/A')
                info_ct = snap.get('info_ct', 0)
                warn_ct = snap.get('warn_ct', 0)
                err_ct = snap.get('err_ct', 0)
                dbg_ct = snap.get('dbg_ct', 0)
                crt_ct = snap.get('crt_ct', 0)
                tbl_count = snap.get('tbl_count', 0)
                total_items = snap.get('total_items', 0)
                duplicate_ids = snap.get('duplicate_ids', 0)
                total_ids = snap.get('total_ids', 0)
                thread_names = snap.get('thread_names', [])
                defs_text = snap.get('defs_text', '(no definitions found)')
                id_map = snap.get('id_map', {})
            else:

                try:
                    sys_cpu = psutil.cpu_percent(interval = None)
                except Exception:
                    sys_cpu = 0.0
                try:
                    proc = getattr(self, "_dev_proc", None)or psutil.Process()
                    app_cpu = proc.cpu_percent(interval = None)
                except Exception:
                    app_cpu = 0.0
                try:
                    vm = psutil.virtual_memory()
                    sys_mem_pct = vm.percent
                    sys_total_mb = int(vm.total /(1024 *1024))
                except Exception:
                    vm = None
                    sys_mem_pct = 0.0
                    sys_total_mb = 0
                try:
                    app_rss = proc.memory_info().rss if proc else 0
                    app_rss_mb = int(app_rss /(1024 *1024))
                except Exception:
                    app_rss_mb = 0
                try:
                    app_mem_pct = round((app_rss_mb /sys_total_mb)*100, 1)if sys_total_mb else 0.0
                except Exception:
                    app_mem_pct = 0.0
                try:
                    threads = proc.num_threads()if proc else threading.active_count()
                except Exception:
                    threads = threading.active_count()
                gpu_str = "N/A"
                try:
                    gput = getattr(self, "_gputil", None)
                    got = False
                    if gput:
                        try:
                            gpus = gput.getGPUs()
                            if gpus:
                                g = gpus[0]
                                gpu_str = f"GPU {g.id}: {int(g.load *100)}% {int(g.memoryUsed)}/{int(g.memoryTotal)}MB"
                                got = True
                        except Exception:
                            got = False
                    if not got:
                        try:
                            if shutil.which("nvidia-smi"):
                                out = subprocess.check_output([
                                "nvidia-smi",
                                "--query-gpu=utilization.gpu, memory.used, memory.total",
                                "--format=csv, noheader, nounits"
                                ], text = True, stderr = subprocess.DEVNULL)
                                line = out.strip().splitlines()[0]
                                parts =[p.strip()for p in line.split(', ')]
                                if len(parts)>=3:
                                    util, used, total = parts[0], parts[1], parts[2]
                                    gpu_str = f"GPU 0: {util}% {used}/{total}MB"
                                    got = True
                        except Exception:
                            pass
                except Exception:
                    gpu_str = "N/A"
                try:
                    info_ct = dev_log_counters.get('INFO', 0)
                    warn_ct = dev_log_counters.get('WARNING', 0)
                    err_ct = dev_log_counters.get('ERROR', 0)
                    dbg_ct = dev_log_counters.get('DEBUG', 0)
                    crt_ct = dev_log_counters.get('CRITICAL', 0)
                except Exception:
                    info_ct = warn_ct = err_ct = dbg_ct = crt_ct = 0
                try:
                    table_files = glob.glob(os.path.join('tables', '*.sldtbl'))
                    tbl_count = len(table_files)
                    total_items = 0
                    id_map = {}
                    for tf in table_files:
                        try:
                            with open(tf, 'r', encoding = 'utf-8')as fh:
                                td = json.load(fh)
                            tables = td.get('tables', {})
                            for sub, items in tables.items():
                                if isinstance(items, list):
                                    for it in items:
                                        total_items +=1
                                        if isinstance(it, dict)and 'id'in it:
                                            iid = it.get('id')
                                            id_map[iid]= id_map.get(iid, 0)+1
                        except Exception:
                            continue
                    duplicate_ids = sum(1 for k, v in id_map.items()if v >1)
                    total_ids = len(id_map)
                except Exception:
                    tbl_count = total_items = duplicate_ids = total_ids = 0
                try:
                    ths = threading.enumerate()
                    thread_names =[t.name for t in ths][:8]
                except Exception:
                    thread_names =[]
                try:

                    defs_list =[]
                    main_mod = sys.modules.get('__main__')
                    if main_mod:
                        for n, o in inspect.getmembers(main_mod):
                            try:
                                if inspect.isfunction(o):
                                    defs_list.append(f"fn: {n}")
                                elif inspect.isclass(o):
                                    defs_list.append(f"class: {n}")
                            except Exception:
                                continue
                    defs_list = sorted(set(defs_list))[:400]
                    defs_text = "\n".join(defs_list)if defs_list else "(no definitions found)"
                except Exception:
                    defs_text = "(error collecting definitions)"

            try:

                if getattr(self, "_dev_cpu_value", None):

                    try:
                        if sys_total_mb >=1024:
                            sys_gb = math.ceil(sys_total_mb /1024)
                            sys_mem_repr = f"{sys_total_mb}MB({sys_gb}GB) {int(sys_mem_pct)}%"
                        else:
                            sys_mem_repr = f"{sys_total_mb}MB {int(sys_mem_pct)}%"
                    except Exception:
                        sys_mem_repr = f"{int(sys_mem_pct)}%"

                    try:
                        if app_rss_mb >=1024:
                            app_gb = math.ceil(app_rss_mb /1024)
                            app_mem_repr = f"{app_rss_mb}MB({app_gb}GB) {app_mem_pct}%"
                        else:
                            app_mem_repr = f"{app_rss_mb}MB {app_mem_pct}%"
                    except Exception:
                        app_mem_repr = f"{app_rss_mb}MB"

                    self._dev_cpu_value.configure(text = f"SYS CPU: {int(sys_cpu)}% APP CPU: {int(app_cpu)}% SYS MEM: {sys_mem_repr} APP MEM: {app_mem_repr}")
            except Exception:
                pass
            try:

                if getattr(self, "_dev_gpu_value", None):
                    self._dev_gpu_value.configure(text = f"{gpu_str}")
            except Exception:
                pass
            try:

                if getattr(self, "_dev_thread_lbl", None):
                    self._dev_thread_lbl.configure(text = f"Threads: {threads} Names: {', '.join(thread_names)if thread_names else 'N/A'}")
            except Exception:
                pass
            try:

                if getattr(self, "_dev_log_info_lbl", None):
                    self._dev_log_info_lbl.configure(text = f"{info_ct}")
                if getattr(self, "_dev_log_warn_lbl", None):
                    self._dev_log_warn_lbl.configure(text = f"{warn_ct}")
                if getattr(self, "_dev_log_err_lbl", None):
                    self._dev_log_err_lbl.configure(text = f"{err_ct}")
                if getattr(self, "_dev_log_dbg_lbl", None):
                    self._dev_log_dbg_lbl.configure(text = f"{dbg_ct}")
                if getattr(self, "_dev_log_crit_lbl", None):
                    self._dev_log_crit_lbl.configure(text = f"{crt_ct}")

                if getattr(self, "_dev_logs_summary", None):
                    try:
                        self._dev_logs_summary.configure(text = f"INFO:{info_ct} WARN:{warn_ct} ERR:{err_ct} DBG:{dbg_ct} CRIT:{crt_ct}")
                    except Exception:
                        pass
            except Exception:
                pass
            try:

                if getattr(self, "_dev_tables_lbl", None):
                    self._dev_tables_lbl.configure(text = f"Tables: {tbl_count} Items: {total_items} IDs: {total_ids} Duplicate IDs: {duplicate_ids}")
                if getattr(self, "_dev_nextid_lbl", None):
                    try:
                        next_id_val =(max(id_map.keys())+1)if id_map else 0
                    except Exception:
                        next_id_val = 0
                    self._dev_nextid_lbl.configure(text = f"{next_id_val}")

                if getattr(self, "_dev_defs_lbl", None):
                    try:
                        self._dev_defs_lbl.configure(text = defs_text)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            logging.exception("Failed to update dev toolbar stats")
        finally:
            try:

                if getattr(self, "_dev_toolbar_frame", None):
                    try:
                        self._dev_toolbar_frame.after(1000, self._update_dev_toolbar)
                    except Exception:

                        try:
                            self.root.after(1000, self._update_dev_toolbar)
                        except Exception:
                            pass
                else:
                    try:
                        self.root.after(1000, self._update_dev_toolbar)
                    except Exception:
                        pass
            except Exception:
                pass
    def _open_dev_tools(self):
        logging.info("Developer Tools definition called")
        self._clear_window()
        main_frame = customtkinter.CTkFrame(self.root)
        main_frame.pack(fill = "both", expand = True, padx = 20, pady = 20)
        title_label = customtkinter.CTkLabel(main_frame, text = "Developer Tools", font = customtkinter.CTkFont(size = 20, weight = "bold"))
        title_label.pack(pady = 20)
        modify_data = self._create_sound_button(main_frame, "Modify Data", self._open_modify_save_data_tool, width = 500, height = 50, font = customtkinter.CTkFont(size = 16))
        modify_data.pack(pady = 10)
        back_button = self._create_sound_button(
        main_frame,
        "Back",
        lambda:[self._clear_window(), self._build_main_menu()],
        width = 500,
        height = 50,
        font = customtkinter.CTkFont(size = 16)
        )
        back_button.pack(pady = 10)
