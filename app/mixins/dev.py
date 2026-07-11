"""DevMixin — App methods for the "dev" feature area."""
from app.foundation import *
import logging


class DevMixin:

    def _start_dev_stats_worker(self):
        """Starts the CPU/MEM/GPU/thread/table snapshot worker (_dev_toolbar_worker
        below) and registers it with the console (app/logview.py) sidebar, which
        is where devtools now lives instead of a separate floating window."""
        try:
            if getattr(self, '_dev_worker_thread', None)is not None:
                return

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
            self._dev_last_snapshot = None
            self._dev_worker_running = True
            self._dev_worker_stop = threading.Event()

            self._dev_worker_thread = threading.Thread(target = self._dev_toolbar_worker, name = 'DevToolbarWorker', daemon = True)
            self._dev_worker_thread.start()

            set_devtools_provider(self._dev_stats_provider)
        except Exception:
            logging.exception("Failed to start dev stats worker")

    def _dev_stats_provider(self):
        # Called from the console's own thread on a 1s timer. The worker
        # above refills a single-slot queue every second; drain it into a
        # cached snapshot so a quiet tick still has something to show.
        try:
            q = getattr(self, '_dev_queue', None)
            if q is not None:
                while not q.empty():
                    self._dev_last_snapshot = q.get_nowait()
        except Exception:
            logging.exception("Suppressed exception")
        return getattr(self, '_dev_last_snapshot', None)

    def _dev_inspect_entries(self):
        """(name, obj) pairs for the tables/strings inspector -- the same
        in-memory data the old Tk "Dev Data Explorer" browsed, now rendered
        by app/logview.py's InspectScreen instead of a CTkToplevel."""
        def _resolve(obj):
            if isinstance(obj, str)and os.path.isfile(obj):
                try:
                    with open(obj, 'r', encoding = 'utf-8')as f:
                        return json.load(f)
                except Exception as e:
                    return {"__error__": f"Failed to load file: {e}"}
            return obj

        tbl_map =[]
        try:
            if globals().get('table_data')is not None:
                tbl_map.append(("global_table_data", _resolve(globals().get('table_data'))))
        except Exception:
            logging.exception("Suppressed exception")
        try:
            if globals().get('all_table_items')is not None:
                tbl_map.append(("all_table_items", _resolve(globals().get('all_table_items'))))
        except Exception:
            logging.exception("Suppressed exception")
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
                        tbl_map.append((name, _resolve(val)))
                except Exception:
                    logging.exception("Suppressed exception")
        except Exception:
            logging.exception("Suppressed exception")
        try:
            cur = global_variables.get('current_table')
            if cur:
                tbl_map.append((f"current_table: {cur}", _resolve(globals().get('table_data'))))
        except Exception:
            logging.exception("Suppressed exception")
        return tbl_map

    def _dev_collect_strings(self, entries):
        """Every string value reachable from `entries` (as returned by
        _dev_inspect_entries), excluding ones that look like table filenames
        -- same filter the old Tk "Show Strings" window used."""
        try:
            ext = str(global_variables.get('table_extension', '.sldtbl')).lower()
        except Exception:
            ext = '.sldtbl'

        found =[]

        def _collect(o):
            try:
                if isinstance(o, str):
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
                logging.exception("Suppressed exception")

        for _name, obj in entries:
            _collect(obj)

        uniq =[]
        seen = set()
        for s in found:
            if s and s not in seen:
                seen.add(s)
                uniq.append(s)
        return uniq

    def _collect_thread_info(self):
        """One line per thread: live CPU% (vs the previous sample) and the
        function it's currently executing, via sys._current_frames()."""
        lines =[]
        try:
            now = time.time()
            frames = sys._current_frames()
            try:
                cpu_times ={pt.id: pt.user_time +pt.system_time for pt in psutil.Process().threads()}
            except Exception:
                cpu_times = {}
            prev = getattr(self, '_dev_prev_thread_cpu', None)or {}
            new_prev = {}
            for t in threading.enumerate()[:30]:
                frame = frames.get(t.ident)
                if frame:
                    func = f"{frame.f_code.co_name}() @ {os.path.basename(frame.f_code.co_filename)}:{frame.f_lineno}"
                else:
                    func = "?"

                cpu_total = cpu_times.get(t.ident)
                if cpu_total is None:
                    cpu_str = "  n/a"
                else:
                    new_prev[t.ident]=(cpu_total, now)
                    prev_entry = prev.get(t.ident)
                    if prev_entry:
                        prev_cpu, prev_time = prev_entry
                        dt = now -prev_time
                        pct = max(0.0,(cpu_total -prev_cpu)/dt *100)if dt >0 else 0.0
                        cpu_str = f"{pct:5.1f}%"
                    else:
                        cpu_str = "  ..."

                lines.append(f"{cpu_str}  {t.name[:24]:<24} {func}")
            self._dev_prev_thread_cpu = new_prev
        except Exception:
            logging.exception("Suppressed exception")
        return lines

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
                            logging.exception("Suppressed exception")
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
                            logging.exception("Suppressed exception")
                            continue
                    snap['total_items']= total_items
                    snap['duplicate_ids']= sum(1 for k, v in id_map.items()if v >1)
                    snap['total_ids']= len(id_map)
                    snap['id_map']= id_map
                except Exception:
                    snap['tbl_count']= snap['total_items']= snap['duplicate_ids']= snap['total_ids']= 0
                    snap['id_map']= {}

                try:
                    snap['thread_lines']= self._collect_thread_info()
                except Exception:
                    snap['thread_lines']=[]

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
                            logging.exception("Suppressed exception")
                except Exception:
                    logging.exception("Suppressed exception")

                try:
                    # Use Event.wait() not time.sleep(): Python 3.13 free-threaded
                    # GC stop-the-world crashes time.sleep() via PyEval_RestoreThread.
                    getattr(self, '_dev_worker_stop', threading.Event()).wait(1.0)
                except BaseException:
                    break
        except BaseException:
            logging.exception("Suppressed exception")

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
