from typing import Callable, Optional

from textual.widgets import Label

_TOTAL_TICKS = 50  # 5 s at 100 ms / tick


class UndoBar(Label):
    """One-row countdown bar shown before a destructive action fires.

    Call show_action() to start the bar. Press u → cancel() to abort.
    """

    def __init__(self) -> None:
        super().__init__("", id="undo-bar", markup=True)
        self._label: str = ""
        self._callback: Optional[Callable] = None
        self._ticks: int = 0
        self._timer = None
        self.display = False

    # ── public API ─────────────────────────────────────────────────────────

    def show_action(self, label: str, callback: Callable) -> None:
        """Start a new countdown (replaces any previous one)."""
        self._stop()
        self._label = label
        self._callback = callback
        self._ticks = 0
        self.display = True
        self._redraw()
        self._timer = self.set_interval(0.1, self._tick)

    def cancel(self) -> None:
        """Abort the pending action (called by the u keybinding)."""
        if self._callback is None:
            return
        self._stop()
        self._callback = None
        self.display = False
        self.app.notify("Action cancelled.")

    # ── internals ──────────────────────────────────────────────────────────

    def _stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _tick(self) -> None:
        self._ticks += 1
        if self._ticks >= _TOTAL_TICKS:
            self._fire()
        else:
            self._redraw()

    def _fire(self) -> None:
        cb = self._callback
        self._stop()
        self._callback = None
        self.display = False
        if cb is not None:
            self.call_later(cb)

    def _redraw(self) -> None:
        filled = "█" * self._ticks
        empty = "░" * (_TOTAL_TICKS - self._ticks)
        self.update(f"[{filled}{empty}] {self._label}  [dim]u = undo[/dim]")
