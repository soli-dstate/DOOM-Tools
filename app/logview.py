"""Textual-based log viewer that replaces the raw console + the old dev
console input() loop. Ported from world-rts's app/logview.py; see
.claude/logviewer.md for the full design writeup and porting notes.
"""
import json
import logging
import queue
import sys
import threading
import time
from dataclasses import dataclass

from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, OptionList, RichLog, Select, Static
from textual.widgets.option_list import Option

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_LEVEL_STYLES = {
    "DEBUG": "dim cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold white on red",
}


@dataclass
class LogLine:
    level: str
    time: str
    source: str
    message: str


class _QueueLogHandler(logging.Handler):
    """emit() only ever does a non-blocking queue.put — safe to log from any
    thread (worker pools, Tk callbacks, whatever) without touching the UI."""

    def __init__(self, line_queue):
        super().__init__()
        self._queue = line_queue
        self._fmt = logging.Formatter()

    def emit(self, record):
        try:
            message = record.getMessage()
            if record.exc_info:
                message += "\n" + self._fmt.formatException(record.exc_info)
            self._queue.put(LogLine(
                level=record.levelname,
                time=self._fmt.formatTime(record, "%H:%M:%S"),
                source=f"{record.name}.{record.funcName}",
                message=message,
            ))
        except Exception:
            self.handleError(record)


def _render_line(line: LogLine) -> Text:
    style = _LEVEL_STYLES.get(line.level, "white")
    text = Text()
    text.append(f"{line.time} ", style="dim")
    text.append(f"{line.level:<8} ", style=style)
    text.append(f"{line.source} ", style="dim italic")
    text.append(line.message)
    return text


class LogViewApp(App):
    CSS = """
    Screen { background: $surface; }
    #log-row { height: 1fr; }
    #log { width: 1fr; border: round $accent; padding: 0 1; }
    #sidebar { width: 26; border: round $accent; padding: 1 2; }
    #devtools-box { width: 32; border: round $accent; padding: 1 2; display: none; }
    #devtools-box Button { width: 100%; margin-top: 1; }
    #command-input { border: round $accent; }
    """
    BINDINGS = [Binding("ctrl+q", "quit", "Quit", show=True)]
    # Default (AUTO_FOCUS = "*") lands on RichLog since it's first in compose()
    # order -- force the command box instead so typing works immediately.
    AUTO_FOCUS = "#command-input"

    def __init__(self, line_queue, log_path, command_handler=None):
        super().__init__()
        self._queue = line_queue
        self._log_path = log_path
        self._command_handler = command_handler
        self._counts = {lvl: 0 for lvl in LEVELS}
        self.shutdown_event = threading.Event()
        # Set via install()'s returned set_dev_stats_provider() once devmode's
        # stats worker is up (see app/mixins/dev.py _start_dev_stats_worker)
        # — None means devmode is off and #devtools-box stays hidden.
        self._dev_stats_provider = None

    def compose(self):
        yield Header()
        with Horizontal(id="log-row"):
            yield RichLog(id="log", max_lines=5000, wrap=True)
            yield Static(id="sidebar")
            with Vertical(id="devtools-box"):
                yield Static(id="devtools-stats")
                yield Button("Inspect Tables/Strings", id="devtools-inspect-btn")
        yield Input(placeholder="Type a command, type help for list of commands...", id="command-input")

    def on_mount(self):
        self.title = "DOOM Tools"
        self.sub_title = str(self._log_path)
        self._update_sidebar()
        self.set_interval(0.1, self._drain_queue)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "devtools-inspect-btn" and self._command_handler is not None:
            # Same path as typing "inspect" -- off the UI thread since the
            # command handler isn't guaranteed to be quick.
            threading.Thread(target=self._command_handler, args=("inspect",), daemon=True).start()

    def on_unmount(self):
        # Fires whichever way the app exits (user quit or install()'s stop()
        # calling app.exit() programmatically) — the one reliable place to
        # signal the GUI side that the terminal is no longer owned by us.
        self.shutdown_event.set()

    def _drain_queue(self):
        if not self.is_running or self._queue.empty():
            return
        log = self.query_one("#log", RichLog)
        while not self._queue.empty():
            line = self._queue.get_nowait()
            log.write(_render_line(line))
            if line.level in self._counts:
                self._counts[line.level] += 1
        self._update_sidebar()

    def _update_sidebar(self):
        table = Table.grid(padding=(0, 1))
        table.add_column(justify="left")
        table.add_column(justify="right")
        for lvl in LEVELS:
            table.add_row(Text(lvl, style=_LEVEL_STYLES.get(lvl, "white")), str(self._counts[lvl]))
        errors = self._counts["ERROR"] + self._counts["CRITICAL"]
        table.add_row("", "")
        table.add_row(Text("Errors", style="bold"), Text(str(errors), style="bold red" if errors else "bold"))
        self.query_one("#sidebar", Static).update(table)

    def _update_devtools_box(self):
        if self._dev_stats_provider is None:
            return
        try:
            snap = self._dev_stats_provider()
        except Exception:
            snap = None
        table = Table.grid(padding=(0, 1))
        table.add_column(justify="left")
        table.add_column(justify="right")
        if snap:
            table.add_row("CPU sys/app", f"{int(snap.get('sys_cpu', 0))}%/{int(snap.get('app_cpu', 0))}%")
            table.add_row("MEM sys/app", f"{int(snap.get('sys_mem_pct', 0))}%/{snap.get('app_rss_mb', 0)}MB")
            table.add_row("GPU", str(snap.get('gpu_str', 'N/A'))[:20])
            table.add_row("Threads", str(snap.get('threads', 0)))
            table.add_row("Tables/Items", f"{snap.get('tbl_count', 0)}/{snap.get('total_items', 0)}")
            dup = snap.get('duplicate_ids', 0)
            table.add_row("IDs/Dup", Text(f"{snap.get('total_ids', 0)}/{dup}", style="bold red" if dup else None))
        else:
            table.add_row(Text("(warming up...)", style="dim"), "")
        self.query_one("#devtools-stats", Static).update(table)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = (event.value or "").strip()
        event.input.value = ""
        if not cmd:
            return
        log = self.query_one("#log", RichLog)
        if cmd.startswith("/"):
            name, _, args = cmd.partition(" ")
            handler = self.COMMANDS.get(name.lower())
            if handler:
                handler(self, args.strip())
            else:
                log.write(Text(f"Unknown command: {name}", style="yellow"))
            return
        if self._command_handler is None:
            log.write(Text(f"No command handler installed for: {cmd}", style="yellow"))
            return
        # Run off the UI thread: some dev-console commands (pause/eval) block
        # for real, and blocking here would freeze the whole TUI.
        threading.Thread(target=self._command_handler, args=(cmd,), daemon=True).start()

    def _cmd_clear(self, args: str) -> None:
        self.query_one("#log", RichLog).clear()

    def _cmd_test_log(self, args: str) -> None:
        level_name = (args.split()[0] if args else "info").upper()
        level = getattr(logging, level_name, None)
        if level_name not in LEVELS or not isinstance(level, int):
            self.query_one("#log", RichLog).write(Text(f"Usage: /test-log [{'|'.join(l.lower() for l in LEVELS)}]"))
            return
        logging.getLogger("logview.test_log").log(level, "Test log message at %s level", level_name)

    COMMANDS = {}


LogViewApp.COMMANDS = {"/clear": LogViewApp._cmd_clear, "/test-log": LogViewApp._cmd_test_log}


class StringsScreen(Screen):
    """Full-screen list of every string reachable from the inspector's
    entries -- terminal port of the old Tk "Show Strings" popup."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]
    CSS = """
    StringsScreen { layout: horizontal; }
    #strings-list { width: 46; border: round $accent; }
    #strings-body { width: 1fr; border: round $accent; padding: 0 1; }
    """
    MAX_SHOWN = 500

    def __init__(self, strings):
        super().__init__()
        self._strings = strings

    def compose(self):
        yield OptionList(id="strings-list")
        with VerticalScroll():
            yield Static(id="strings-body")
        yield Footer()

    def on_mount(self):
        opt_list = self.query_one("#strings-list", OptionList)
        for s in self._strings[:self.MAX_SHOWN]:
            opt_list.add_option(Option((s or "(empty)")[:120]))
        if len(self._strings) > self.MAX_SHOWN:
            opt_list.add_option(Option(f"... truncated, showing {self.MAX_SHOWN} of {len(self._strings)}", disabled=True))
        if self._strings:
            self.query_one("#strings-body", Static).update(self._strings[0])
        opt_list.focus()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_index < len(self._strings):
            self.query_one("#strings-body", Static).update(self._strings[event.option_index])


class InspectScreen(Screen):
    """Terminal port of the old Tk "Dev Data Explorer": browse DOOM-Tools'
    in-memory data structures (tables, save data, settings, ...) full-screen
    inside the console instead of a separate GUI window."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
        Binding("s", "show_strings", "Strings"),
    ]
    CSS = """
    InspectScreen { layout: horizontal; }
    #inspect-list { width: 34; border: round $accent; }
    #inspect-right { width: 1fr; }
    #inspect-top { height: auto; }
    #inspect-content { border: round $accent; }
    """
    MAX_RENDER_CHARS = 200_000

    def __init__(self, entries_provider, strings_provider):
        super().__init__()
        self._entries_provider = entries_provider
        self._strings_provider = strings_provider
        self._entries = []
        self._current_idx = None

    def compose(self):
        yield OptionList(id="inspect-list")
        with Vertical(id="inspect-right"):
            with Horizontal(id="inspect-top"):
                yield Select([], id="inspect-subtable", allow_blank=True, prompt="(none)")
                yield Static(id="inspect-notice")
            with VerticalScroll(id="inspect-content"):
                yield Static(id="inspect-json")
        yield Footer()

    def on_mount(self):
        try:
            self._entries = self._entries_provider() or []
        except Exception:
            logging.exception("Failed to load inspector entries")
            self._entries = []
        opt_list = self.query_one("#inspect-list", OptionList)
        for name, _obj in self._entries:
            opt_list.add_option(Option(name))
        if self._entries:
            opt_list.focus()

    def action_show_strings(self) -> None:
        try:
            strings = self._strings_provider(self._entries) or []
        except Exception:
            logging.exception("Failed to collect strings")
            strings = []
        self.app.push_screen(StringsScreen(strings))

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self._current_idx = event.option_index
        self._populate_submenu()
        self._show_content()

    def _current(self):
        if self._current_idx is None or self._current_idx >= len(self._entries):
            return None, None
        return self._entries[self._current_idx]

    def _populate_submenu(self):
        _name, data = self._current()
        keys = []
        if isinstance(data, dict):
            if 'tables' in data and isinstance(data['tables'], dict):
                keys = sorted(data['tables'].keys())
            else:
                keys = sorted(str(k) for k in data.keys())
        sub = self.query_one("#inspect-subtable", Select)
        sub.set_options([(k, k) for k in keys])

    def _show_content(self):
        name, data = self._current()
        choice = self.query_one("#inspect-subtable", Select).value
        has_choice = choice is not Select.NULL and choice is not None
        content = data
        if isinstance(data, dict):
            if name == 'global_table_data' or (name or '').startswith('current_table'):
                content = data.get('tables', data)
                if has_choice:
                    content = content.get(choice, {})
            elif has_choice:
                content = data.get('tables', {}).get(choice, data.get(choice, {}))
        self._render_json(content)

    def _render_json(self, content):
        try:
            rendered = json.dumps(content, indent=2, ensure_ascii=False, default=str)
        except Exception:
            rendered = str(content)
        notice = self.query_one("#inspect-notice", Static)
        if len(rendered) > self.MAX_RENDER_CHARS:
            notice.update(Text(f"{len(rendered):,} chars — truncated, pick a subtable to narrow it down", style="yellow"))
            rendered = rendered[: self.MAX_RENDER_CHARS]
        else:
            notice.update("")
        body = self.query_one("#inspect-json", Static)
        try:
            body.update(Syntax(rendered, "json", theme="ansi_dark", word_wrap=True))
        except Exception:
            body.update(rendered)

    def on_select_changed(self, event: Select.Changed) -> None:
        self._show_content()


def install(file_handler, level=logging.INFO, command_handler=None):
    """Swap the root logger's console output for this Textual TUI, keeping
    the existing file handler untouched. Returns (shutdown_event, stop):
    shutdown_event is set once the log view's own thread has actually exited
    (user hit ctrl+q, or stop() below finished tearing it down) so the GUI
    side can watch it and close in turn. stop() is what the GUI calls when
    IT closes first, to tear the log view down from outside its thread.
    """
    line_queue = queue.Queue()

    queue_handler = _QueueLogHandler(line_queue)
    root_logger = logging.getLogger()
    # Only ever ADD a handler here — never touch root_logger.handlers wholesale.
    # By the time this runs there's nothing console-shaped to remove (the
    # caller never attaches a StreamHandler in the success path), and other
    # handlers already in place (e.g. a dev-mode log counter) must survive.
    root_logger.addHandler(queue_handler)
    if file_handler not in root_logger.handlers:
        root_logger.addHandler(file_handler)
    root_logger.setLevel(level)

    # Windows' legacy console codepage (cp1252 etc.) can't encode the Unicode
    # border/glyph characters Textual writes by default, which kills its
    # writer thread with a UnicodeEncodeError. Force UTF-8 on the actual
    # streams the writer thread uses, not just this process's default.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            pass

    log_path = getattr(file_handler, "baseFilename", "")
    app = LogViewApp(line_queue, log_path, command_handler=command_handler)
    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()

    def stop():
        # app.call_from_thread() raises RuntimeError if Textual's asyncio loop
        # hasn't attached yet — happens in practice if the GUI window is
        # closed almost immediately after launch. Retry instead of giving up
        # on the first RuntimeError, otherwise the background thread (and the
        # real terminal, stuck in alt-screen/raw mode) is left running forever.
        if app.shutdown_event.is_set():
            return
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and thread.is_alive():
            try:
                app.call_from_thread(app.exit)
                break
            except RuntimeError:
                time.sleep(0.05)
        thread.join(timeout=5.0)
        if thread.is_alive():
            # Textual never got to run its own shutdown, which is what
            # normally disables everything it enabled at startup (mouse
            # tracking, focus reporting, bracketed paste, ...). Without this,
            # the terminal keeps reporting raw mouse-move escape codes as
            # input forever after the process is gone, spamming the prompt.
            sys.stdout.write(
                "\x1b[?1000l\x1b[?1003l\x1b[?1015l\x1b[?1006l"  # disable mouse tracking (basic/any-motion/urxvt/SGR)
                "\x1b[?1004l"  # disable focus reporting
                "\x1b[?2004l"  # disable bracketed paste
                "\x1b[?1049l"  # leave alt screen
                "\x1b[?25h"  # show cursor
                "\x1b[0m"  # reset attributes
            )
            sys.stdout.flush()

    def set_dev_stats_provider(provider):
        # Setting the attribute itself is thread-safe (plain reference swap,
        # no Tk/asyncio state), but revealing the box and starting the timer
        # touch the widget tree, which only the app's own thread may do.
        app._dev_stats_provider = provider
        if not getattr(app, "_dev_stats_timer_started", False):
            app._dev_stats_timer_started = True

            def _reveal_devtools_box():
                app.query_one("#devtools-box").display = True
                app._update_devtools_box()
                app.set_interval(1.0, app._update_devtools_box)

            app.call_from_thread(_reveal_devtools_box)

    def open_inspector(entries_provider, strings_provider):
        # push_screen touches the app's widget tree, so this must run on the
        # app's own thread, same reasoning as app.exit() above.
        try:
            app.call_from_thread(app.push_screen, InspectScreen(entries_provider, strings_provider))
        except RuntimeError:
            logging.exception("Log view isn't running yet; can't open the inspector")

    return app.shutdown_event, stop, set_dev_stats_provider, open_inspector
