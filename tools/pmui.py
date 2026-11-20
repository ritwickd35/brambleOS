"""Shared terminal UI and logging for the Pocket Master toolkit.

Design rules (so it behaves in WezTerm, Terminal, iTerm, VS Code and when piped to a file):
  * Interactive terminal: one live progress bar per task (rich), redrawn in place a few times per second.
    Never prints a new line per update, so scrollback is not flooded.
  * Not a terminal (piped, nohup, CI): no bars, no carriage returns, no colour codes. Progress is logged as
    plain lines at most every 10 % or every 30 s.
  * Every message also goes to a plain-text log file (re/logs/<date>-<tool>.log) without colour codes.
"""
import os, sys, time

try:
    from rich.console import Console
    from rich.progress import (BarColumn, Progress, TaskProgressColumn, TextColumn, TimeElapsedColumn,
                               TimeRemainingColumn)
    _HAVE_RICH = True
except ImportError:                                   # still works without rich, just plainer
    _HAVE_RICH = False

RE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(RE, "logs")
INTERACTIVE = sys.stdout.isatty() and os.environ.get("TERM") != "dumb" and _HAVE_RICH
_console = Console(highlight=False) if INTERACTIVE else None
_logfile = None


def start_log(tool):
    """Open the plain log file for this run; returns its path."""
    global _logfile
    os.makedirs(LOGDIR, exist_ok=True)
    path = os.path.join(LOGDIR, time.strftime("%Y%m%d-%H%M%S") + f"-{tool}.log")
    _logfile = open(path, "a", buffering=1)
    return path


def _write_log(level, msg):
    if _logfile:
        _logfile.write(time.strftime("%H:%M:%S ") + f"[{level}] {msg}\n")


def _out(style, prefix, msg, level):
    _write_log(level, msg)
    if INTERACTIVE:
        _console.print(f"[{style}]{prefix}[/] {msg}")
    else:
        print(time.strftime("%H:%M:%S ") + f"{prefix} {msg}", flush=True)


def info(msg):  _out("cyan", "•", msg, "info")
def ok(msg):    _out("green", "✓", msg, "ok")
def warn(msg):  _out("yellow", "!", msg, "warn")
def error(msg): _out("bold red", "✗", msg, "error")
def step(msg):  _out("bold", "»", msg, "step")


class Bar:
    """Progress bar: `with Bar("Flashing", total) as b: b.update(done, note)`."""

    def __init__(self, title, total, unit="frames"):
        self.title, self.total, self.unit = title, max(1, total), unit
        self._last_pct, self._last_t = -100, 0.0
        self._prog = None

    def __enter__(self):
        _write_log("step", f"{self.title}: started ({self.total} {self.unit})")
        if INTERACTIVE:
            self._prog = Progress(TextColumn("[bold]{task.description}"), BarColumn(bar_width=None),
                                  TaskProgressColumn(), TextColumn("{task.fields[note]}"),
                                  TimeElapsedColumn(), TextColumn("left"), TimeRemainingColumn(),
                                  console=_console, transient=False, refresh_per_second=4)
            self._prog.start()
            self._task = self._prog.add_task(self.title, total=self.total, note="")
        return self

    def update(self, done, note=""):
        if self._prog:
            self._prog.update(self._task, completed=done, note=note)
            return
        pct = 100.0 * done / self.total
        now = time.time()
        if pct - self._last_pct >= 10 or now - self._last_t >= 30 or done >= self.total:
            print(time.strftime("%H:%M:%S ") + f"  {self.title}: {pct:5.1f}%  {note}", flush=True)
            _write_log("progress", f"{self.title}: {pct:.1f}% {note}")
            self._last_pct, self._last_t = pct, now

    def __exit__(self, *exc):
        if self._prog:
            self._prog.stop()
        _write_log("step", f"{self.title}: {'finished' if exc[0] is None else 'stopped'}")
        return False


def countdown(title, seconds, note_fn=None):
    """Bar for a fixed-duration wait (e.g. a recording); note_fn() may return a short status text."""
    with Bar(title, int(seconds), unit="s") as b:
        t0 = time.time()
        while True:
            el = time.time() - t0
            b.update(min(int(el), int(seconds)), note_fn() if note_fn else "")
            if el >= seconds:
                break
            time.sleep(0.25)


def table(title, rows, headers):
    """Small result table (rich in a terminal, aligned text otherwise)."""
    _write_log("result", title + ": " + "; ".join(", ".join(str(c) for c in r) for r in rows))
    if INTERACTIVE:
        from rich.table import Table
        t = Table(title=title, title_justify="left")
        for h in headers:
            t.add_column(h)
        for r in rows:
            t.add_row(*[str(c) for c in r])
        _console.print(t)
    else:
        print(title)
        w = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
        for r in [headers] + [list(map(str, r)) for r in rows]:
            print("  " + "  ".join(str(c).ljust(n) for c, n in zip(r, w)))
