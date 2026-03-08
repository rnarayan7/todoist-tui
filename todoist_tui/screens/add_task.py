from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual._work_decorator import work

# Sentinel used when the user leaves Project set to "Inbox (default)"
_INBOX = "__inbox__"

_PRIORITY_OPTIONS = [
    ("1 — Normal", "1"),
    ("2 — Medium", "2"),
    ("3 — High", "3"),
    ("4 — Urgent", "4"),
]

_DURATION_UNIT_OPTIONS = [
    ("minutes", "minute"),
    ("days", "day"),
]


class AddTaskScreen(ModalScreen[dict | None]):
    """Modal form for creating a new Todoist task."""

    CSS = """
    AddTaskScreen {
        align: center middle;
    }
    #dialog {
        width: 72;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #form-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #form-body {
        height: auto;
        max-height: 28;
    }
    .field-label {
        color: $text-muted;
        height: 1;
        margin-top: 1;
    }
    #duration-row {
        height: 3;
    }
    #duration {
        width: 10;
    }
    #duration-unit {
        width: 1fr;
        margin-left: 1;
    }
    #buttons {
        margin-top: 1;
        height: 3;
        align: right middle;
    }
    Button {
        margin-left: 1;
    }
    """

    def __init__(self, default_project_id: str | None = None) -> None:
        super().__init__()
        self._default_project_id = default_project_id

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("Add Task", id="form-title")
            with VerticalScroll(id="form-body"):
                yield Label("Content *", classes="field-label")
                yield Input(placeholder="Task name", id="content")

                yield Label("Description", classes="field-label")
                yield Input(placeholder="Optional description", id="description")

                yield Label("Due date", classes="field-label")
                yield Input(
                    placeholder="e.g. today, tomorrow, next monday", id="due"
                )

                yield Label("Deadline", classes="field-label")
                yield Input(placeholder="YYYY-MM-DD", id="deadline")

                yield Label("Priority", classes="field-label")
                yield Select(
                    [(lbl, val) for lbl, val in _PRIORITY_OPTIONS],
                    value="1",
                    id="priority",
                )

                yield Label("Labels", classes="field-label")
                yield Input(
                    placeholder="label1, label2 (comma-separated)", id="labels"
                )

                yield Label("Project", classes="field-label")
                yield Select(
                    [("Inbox (default)", _INBOX)],
                    value=_INBOX,
                    id="project",
                )

                yield Label("Duration", classes="field-label")
                with Horizontal(id="duration-row"):
                    yield Input(placeholder="0", id="duration")
                    yield Select(
                        [(lbl, val) for lbl, val in _DURATION_UNIT_OPTIONS],
                        value="minute",
                        id="duration-unit",
                    )

            with Horizontal(id="buttons"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#content", Input).focus()
        self._load_projects()

    @work
    async def _load_projects(self) -> None:
        try:
            projects = await self.app.client.get_projects()  # type: ignore[attr-defined]
            select = self.query_one("#project", Select)
            options = [("Inbox (default)", _INBOX)] + [
                (p.name, p.id) for p in projects
            ]
            select.set_options(options)
            if self._default_project_id:
                select.value = self._default_project_id
        except Exception:
            pass  # leave with the "Inbox" default

    # ── keyboard navigation ─────────────────────────────────────────────────

    def on_key(self, event) -> None:
        key = event.key
        if key == "escape":
            self.dismiss(None)
        elif key == "down":
            self.focus_next()
        elif key == "up":
            self.focus_previous()
        elif key == "enter":
            focused = self.focused
            if isinstance(focused, Button):
                if focused.id == "btn-add":
                    self._submit()
                elif focused.id == "btn-cancel":
                    self.dismiss(None)
            elif isinstance(focused, Input):
                # Enter in a text field moves to the next field
                self.focus_next()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-add":
            self._submit()

    # ── submission ──────────────────────────────────────────────────────────

    def _submit(self) -> None:
        content = self.query_one("#content", Input).value.strip()
        if not content:
            self.app.notify("Task content cannot be empty.", severity="warning")
            return

        description = self.query_one("#description", Input).value.strip() or None
        due = self.query_one("#due", Input).value.strip() or None
        deadline = self.query_one("#deadline", Input).value.strip() or None

        priority_val = self.query_one("#priority", Select).value
        try:
            priority = int(str(priority_val)) if priority_val else 1
        except (ValueError, TypeError):
            priority = 1

        labels_raw = self.query_one("#labels", Input).value.strip()
        labels = [lbl.strip() for lbl in labels_raw.split(",") if lbl.strip()] or None

        project_raw = self.query_one("#project", Select).value
        project_id = None if (not project_raw or project_raw == _INBOX) else str(project_raw)

        duration_raw = self.query_one("#duration", Input).value.strip()
        try:
            duration = int(duration_raw) if duration_raw else None
            if duration == 0:
                duration = None
        except ValueError:
            duration = None

        duration_unit_raw = self.query_one("#duration-unit", Select).value
        duration_unit = str(duration_unit_raw) if duration and duration_unit_raw else None

        self.dismiss(
            {
                "content": content,
                "description": description,
                "due_string": due,
                "deadline_date": deadline,
                "priority": priority,
                "labels": labels,
                "project_id": project_id,
                "duration": duration,
                "duration_unit": duration_unit,
            }
        )
