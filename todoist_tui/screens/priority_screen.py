from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label
from textual.containers import Horizontal


class PriorityScreen(ModalScreen[int | None]):
    """Slim bottom-bar prompt for picking a priority (1-4)."""

    CSS = """
    PriorityScreen {
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
    .priority-option {
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal(id="bar"):
            yield Label("Priority:")
            yield Label("[bold white]1[/bold white] Normal", classes="priority-option")
            yield Label("[bold yellow]2[/bold yellow] Medium", classes="priority-option")
            yield Label("[bold orange1]3[/bold orange1] High", classes="priority-option")
            yield Label("[bold red]4[/bold red] Urgent", classes="priority-option")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key in ("1", "2", "3", "4"):
            self.dismiss(int(event.key))
