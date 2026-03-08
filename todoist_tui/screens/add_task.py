from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label
from textual.containers import Vertical, Horizontal


class AddTaskScreen(ModalScreen[dict | None]):
    """Modal for adding a new task."""

    CSS = """
    AddTaskScreen {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #dialog Label {
        margin-bottom: 1;
    }
    Input {
        margin-bottom: 1;
    }
    #buttons {
        margin-top: 1;
        align: right middle;
    }
    Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Add Task", id="title")
            yield Label("Content:")
            yield Input(placeholder="Task description", id="content")
            yield Label("Due date (optional):")
            yield Input(placeholder="e.g. today, tomorrow, next monday", id="due")
            yield Label("Priority (1-4, 4=urgent):")
            yield Input(placeholder="1", id="priority", value="1")
            with Horizontal(id="buttons"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
            return

        content = self.query_one("#content", Input).value.strip()
        if not content:
            self.app.notify("Task content cannot be empty.", severity="warning")
            return

        due = self.query_one("#due", Input).value.strip() or None

        priority_raw = self.query_one("#priority", Input).value.strip()
        try:
            priority = max(1, min(4, int(priority_raw)))
        except ValueError:
            priority = 1

        self.dismiss({"content": content, "due_string": due, "priority": priority})

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
