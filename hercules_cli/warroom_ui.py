"""In-process multi-pane War Room UI.

Sleek, keyboard- and mouse-driven full-screen view using prompt_toolkit.
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
    def __init__(self) -> None:
        self.panes = [
            Pane("1", "STATUS", self._status),
            Pane("2", "ACTIVITY", self._activity),
            Pane("3", "COMMANDS", self._commands),
            Pane("4", "OUTPUT", self._output),
        ]
        self.focus = 0
        self.lines: list[str] = []
        self.started = time.monotonic()
        self._app: Application | None = None
        self._log("war room online")

    def _log(self, msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        self.lines.append(f"  {ts}  {msg}")
        self.lines = self.lines[-20:]

    def _status(self) -> str:
        up = int(time.monotonic() - self.started)
        home = os.environ.get("HERCULES_HOME", "~/.hercules")
        port = os.environ.get("T3MP3ST_PORT", "3333")
        return (
            f"  uptime     {up:>4}s\n"
            f"  home       {home}\n"
            f"  port       {port}\n"
            f"  focus      {self.panes[self.focus].title.lower()}\n"
        )

    def _activity(self) -> str:
        if not self.lines:
            return "  (quiet)\n"
        return "\n".join(self.lines[-8:]) + "\n"

    def _commands(self) -> str:
        items = [
            ("1", "status", "refresh"),
            ("2", "activity", "focus log"),
            ("3", "server", "start node"),
            ("4", "open", "browser ui"),
        ]
        out = []
        for key, name, hint in items:
            mark = "▸" if self.panes[self.focus].key == key else " "
            out.append(f"  {mark} {key}  {name:<10} {hint}")
        return "\n".join(out) + "\n"

    def _output(self) -> str:
        return "\n".join(self.lines[-6:]) + "\n" if self.lines else "  —\n"

    def _action(self, name: str) -> None:
        if name == "status":
            self._log("status ok")
        elif name == "server":
            self._log("server start requested")
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
            p = self.panes[idx]
            focused = idx == self.focus
            title_style = "fg:#7dd3fc bold" if focused else "fg:#64748b"
            body = p.body().replace("&", "&").replace("<", "<")
            return HTML(f'<style fg="#94a3b8">{body}</style>')

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
            title = f" {p.key}  {p.title} " + ("●" if focused else "○")
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
            names = ["status", "activity", "server", "open"]
            self._action(names[self.focus])

        @kb.add("r")
        def _(e):
            self._log("refresh")
            e.app.invalidate()

        return kb

    def run(self) -> None:
        style = Style.from_dict({
            "frame.border": "#334155",
            "frame.label": "#e2e8f0 bold",
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
