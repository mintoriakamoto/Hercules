"""In-process multi-pane War Room UI for Hercules.

Keyboard-switchable (and mouse-clickable) panes rendered with
prompt_toolkit. Launched by ``hercules warroom`` instead of shelling
out to an external TUI.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.mouse_events import MouseEvent, MouseEventType
from prompt_toolkit.widgets import Frame


@dataclass
class Pane:
    title: str
    body: Callable[[], str]
    focused: bool = False


class WarRoomUI:
    """Multi-pane view that owns the screen while running."""

    def __init__(self) -> None:
        self.panes: list[Pane] = [
            Pane("Status", self._status_body),
            Pane("Logs", self._logs_body),
            Pane("Commands", self._commands_body),
            Pane("Output", self._output_body),
        ]
        self.focus = 0
        self.output_lines: list[str] = ["War Room ready. Tab / number keys to switch panes."]
        self._app: Application | None = None

    # ----- pane content -------------------------------------------------
    def _status_body(self) -> str:
        home = os.environ.get("HERCULES_HOME", "~/.hercules")
        t3 = os.environ.get("HERCULES_T3MP3ST_HOME", f"{home}/t3mp3st")
        return (
            f"HERCULES_HOME: {home}\n"
            f"T3MP3ST:       {t3}\n"
            f"Port:          {os.environ.get('T3MP3ST_PORT', '3333')}\n"
            f"\n"
            f"Panes: {len(self.panes)}  Focus: {self.focus + 1}\n"
        )

    def _logs_body(self) -> str:
        return (
            "(gateway / warroom logs would stream here)\n"
            "Use the Commands pane to start the server.\n"
        )

    def _commands_body(self) -> str:
        return (
            "1  status     — refresh status\n"
            "2  logs       — focus logs\n"
            "3  server     — start War Room server\n"
            "4  open       — open UI in browser\n"
            "q  quit\n"
            "\n"
            "Tab / Shift-Tab or click a pane to focus.\n"
        )

    def _output_body(self) -> str:
        return "\n".join(self.output_lines[-12:])

    # ----- actions ------------------------------------------------------
    def _run_action(self, name: str) -> None:
        if name == "status":
            self.output_lines.append("status: ok")
        elif name == "server":
            self.output_lines.append("starting War Room server…")
            # Fire-and-forget; real impl would track the process
            self.output_lines.append("(server launch is a stub in this UI)")
        elif name == "open":
            url = "http://127.0.0.1:3333/ui/"
            self.output_lines.append(f"open {url}")
            try:
                if sys.platform == "darwin":
                    subprocess.Popen(["open", url])
                elif sys.platform.startswith("linux"):
                    subprocess.Popen(["xdg-open", url])
                else:
                    subprocess.Popen(["cmd", "/c", "start", url])
            except Exception as exc:
                self.output_lines.append(f"open failed: {exc}")
        else:
            self.output_lines.append(f"unknown: {name}")
        if self._app:
            self._app.invalidate()

    # ----- rendering ----------------------------------------------------
    def _pane_control(self, idx: int) -> FormattedTextControl:
        def get_text() -> list[tuple[str, str]]:
            pane = self.panes[idx]
            style = "class:focused" if idx == self.focus else ""
            body = pane.body()
            lines = [("", f"{pane.title}\n"), (style, body)]
            return lines

        def mouse_handler(mouse_event: MouseEvent) -> None:
            if mouse_event.event_type == MouseEventType.MOUSE_UP:
                self.focus = idx
                if self._app:
                    self._app.invalidate()

        return FormattedTextControl(get_text, focusable=True, mouse_handler=mouse_handler)

    def _make_layout(self) -> Layout:
        frames = []
        for i, pane in enumerate(self.panes):
            title = f"[{i + 1}] {pane.title}" + (" *" if i == self.focus else "")
            frames.append(
                Frame(
                    Window(self._pane_control(i), wrap_lines=True),
                    title=title,
                )
            )
        # 2x2 grid
        top = VSplit(frames[:2])
        bottom = VSplit(frames[2:])
        return Layout(HSplit([top, bottom]), focused_element=frames[self.focus])

    def _keys(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("tab")
        def _(event):
            self.focus = (self.focus + 1) % len(self.panes)
            event.app.layout = self._make_layout()
            event.app.invalidate()

        @kb.add("s-tab")
        def _(event):
            self.focus = (self.focus - 1) % len(self.panes)
            event.app.layout = self._make_layout()
            event.app.invalidate()

        @kb.add("q")
        @kb.add("c-c")
        def _(event):
            event.app.exit()

        for n in range(1, 5):
            @kb.add(str(n))
            def _(event, n=n):
                self.focus = n - 1
                event.app.layout = self._make_layout()
                event.app.invalidate()

        @kb.add("enter")
        def _(event):
            titles = ["status", "logs", "server", "open"]
            self._run_action(titles[self.focus])

        return kb

    def run(self) -> None:
        layout = self._make_layout()
        self._app = Application(
            layout=layout,
            key_bindings=self._keys(),
            full_screen=True,
            mouse_support=True,
        )
        self._app.run()


def launch() -> int:
    """Entry point used by ``hercules warroom``."""
    try:
        WarRoomUI().run()
        return 0
    except Exception as exc:
        print(f"War Room UI failed: {exc}", file=sys.stderr)
        return 1
