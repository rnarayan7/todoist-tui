from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label
from textual.containers import Vertical


class AssigneeScreen(ModalScreen[str | None]):
    """Slim bottom-bar prompt for picking an assignee by number."""

    CSS = """
    AssigneeScreen {
        align: left bottom;
        background: transparent;
    }
    #bar {
        width: 100%;
        height: auto;
        max-height: 10;
        background: $surface;
        border-top: solid $primary;
        padding: 0 1;
    }
    #bar Label {
        width: auto;
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }
    .assignee-option {
        color: $text;
    }
    """

    # Sentinel for "unassign"
    UNASSIGN = "__unassign__"

    def __init__(self, collaborators: list[tuple[str, str]]) -> None:
        """collaborators: list of (name, id) tuples."""
        super().__init__()
        self._collaborators = collaborators

    def compose(self) -> ComposeResult:
        with Vertical(id="bar"):
            yield Label("Assign to:")
            yield Label("[bold white]0[/bold white] Unassigned", classes="assignee-option")
            for i, (name, _) in enumerate(self._collaborators, start=1):
                if i > 9:
                    break
                yield Label(f"[bold white]{i}[/bold white] {name}", classes="assignee-option")

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
        elif event.key == "0":
            self.dismiss(self.UNASSIGN)
        elif event.key.isdigit():
            idx = int(event.key) - 1
            if 0 <= idx < len(self._collaborators):
                self.dismiss(self._collaborators[idx][1])
