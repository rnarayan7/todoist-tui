from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Horizontal


class DueDateScreen(ModalScreen[str | None]):
    """Slim bottom-bar prompt for entering a due date."""

    CSS = """
    DueDateScreen {
        align: left bottom;
        background: transparent;
    }
    #bar {
        width: 100%;
        height: 3;
        background: $surface;
        border-top: solid $primary;
        padding: 0 1;
    }
    #bar Label {
        width: auto;
        content-align: left middle;
        height: 3;
        padding: 0 1;
        color: $text-muted;
    }
    #bar Input {
        width: 1fr;
        border: none;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="bar"):
            yield Label("Due date:")
            yield Input(
                placeholder="e.g. today, tomorrow, next monday, 2026-04-01",
                id="input",
            )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)
