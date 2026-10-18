"""In-process War Room UI matching T3MP3ST's storm aesthetic.

Dark command center with teal/cyan accents, sidebar nav, and
keyboard/mouse switchable panes. Uses prompt_toolkit.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame


@dataclass
class Pane:
    key: str
    title: str
    body: Callable[[], str]


class WarRoomUI:
    """T3MP3ST-style command center inside Hercules."""

    def __init__(self) -> None:
        self.panes = [
            Pane("1", "STATUS", self._status),
            Pane("2", "SITREP", self._sitrep),
            Pane("3", "ARSENAL", self._arsenal),
            Pane("4", "OUTPUT", self._output),
        ]
        self.focus = 0
        self.lines: list[str] = []
        self.started = time.monotonic()
        self._app: Application | None = None
        self._log("storm online — authorized targets only")

    def _log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.lines.append(f"  {ts}  {msg}")
        self.lines = self.lines[-24:]

    def _status(self) -> str:
        up = int(time.monotonic() - self.started)
        home = os.environ.get("HERCULES_HOME", "~/.hercules")
        port = os.environ.get("T3MP3ST_PORT", "3333")
        return (
            f"  ⚕ HERCULES / T3MP3ST\n"
            f"  uptime     {up:>4}s\n"
            f"  home       {home}\n"
            f"  port       {port}\n"
            f"  theme      storm\n"
            f"  focus      {self.panes[self.focus].title.lower()}\n"
            f"\n"
            f"  [authorized testing only]\n"
        )

    def _sitrep(self) -> str:
        if not self.lines:
            return "  (quiet)\n"
        return "\n".join(self.lines[-10:]) + "\n"

    def _arsenal(self) -> str:
        items = [
            ("1", "preflight", "check readiness"),
            ("2", "arsenal", "sync tools"),
            ("3", "server", "start war room"),
            ("4", "open", "browser ui"),
        ]
        out = ["  ARSENAL / ACTIONS"]
        for key, name, hint in items:
            mark = "▸" if self.panes[self.focus].key == key else " "
            out.append(f"  {mark} {key}  {name:<12} {hint}")
        out.append("")
        out.append("  Tab / click to focus")
        return "\n".join(out) + "\n"

    def _output(self) -> str:
        return "\n".join(self.lines[-8:]) + "\n" if self.lines else "  —\n"

    def _action(self, name: str) -> None:
        if name == "preflight":
            self._log("preflight: local surface only")
        elif name == "arsenal":
            self._log("arsenal sync requested")
        elif name == "server":
            self._log("server start requested (npm run server)")
        elif name == "open":
            url = f"http://127.0.0.1:{os.environ.get('T3MP3ST_PORT', '3333')}/ui/"
            self._log(f"open {url}")
            try:
                cmd = ["open", url] if sys.platform == "darwin" else ["xdg-open", url]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as exc:
                self._log(f"open failed: {exc}")
        else:
            self._log(f"unknown {name}")
        if self._app:
            self._app.invalidate()

    def _control(self, idx: int) -> FormattedTextControl:
        def text() -> HTML:
            body = self.panes[idx].body().replace("&", "&").replace("<", "<")
            return HTML(f'<style fg="#d0f0e8">{body}</style>')

        def mouse(ev: MouseEvent) -> None:
            if ev.event_type == MouseEventType.MOUSE_UP:
                self.focus = idx
                self._log(f"focus → {self.panes[idx].title.lower()}")
                if self._app:
                    self._app.invalidate()

        return FormattedTextControl(text, focusable=True, mouse_handler=mouse)

    def _layout(self) -> Layout:
        frames = []
        for i, p in enumerate(self.panes):
            focused = i == self.focus
            marker = "●" if focused else "○"
            title = f" {p.key}  {p.title} {marker}"
            frames.append(Frame(Window(self._control(i), wrap_lines=True), title=title))
        return Layout(HSplit([VSplit(frames[:2]), VSplit(frames[2:])]))

    def _keys(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("tab")
        def _(e):
            self.focus = (self.focus + 1) % 4
            e.app.layout = self._layout()

        @kb.add("s-tab")
        def _(e):
            self.focus = (self.focus - 1) % 4
            e.app.layout = self._layout()

        @kb.add("q")
        @kb.add("c-c")
        def _(e):
            e.app.exit()

        for i in range(4):
            @kb.add(str(i + 1))
            def _(e, i=i):
                self.focus = i
                e.app.layout = self._layout()

        @kb.add("enter")
        def _(e):
            names = ["preflight", "arsenal", "server", "open"]
            self._action(names[self.focus])

        @kb.add("r")
        def _(e):
            self._log("refresh")
            e.app.invalidate()

        return kb

    def run(self) -> None:
        style = Style.from_dict({
            "frame.border": "#1a3a4a",
            "frame.label": "#2fffd2 bold",
            "frame.label.focused": "#00ff88 bold",
        })
        self._app = Application(
            layout=self._layout(),
            key_bindings=self._keys(),
            full_screen=True,
            mouse_support=True,
            style=style,
            refresh_interval=1.0,
        )
        self._app.run()


def launch() -> int:
    try:
        WarRoomUI().run()
        return 0
    except Exception as exc:
        print(f"war room: {exc}", file=sys.stderr)
        return 1
