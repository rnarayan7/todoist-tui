from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual._work_decorator import work

from ..models import Task

# Sentinel used when the user leaves Project set to "Inbox (default)"
_INBOX = "__inbox__"

# Sentinel used when no parent task is selected
_NO_PARENT = "__no_parent__"

# Sentinel used when no assignee is selected
_NO_ASSIGNEE = "__no_assignee__"

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

    def __init__(
        self,
        default_project_id: str | None = None,
        default_parent_id: str | None = None,
        default_parent_name: str | None = None,
        edit_task: Task | None = None,
    ) -> None:
        super().__init__()
        self._default_project_id = default_project_id
        self._default_parent_id = default_parent_id
        self._default_parent_name = default_parent_name
        self._edit_task = edit_task

    def compose(self) -> ComposeResult:
        is_edit = self._edit_task is not None
        with Vertical(id="dialog"):
            yield Label("Edit Task" if is_edit else "Add Task", id="form-title")
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

                yield Label("Parent task", classes="field-label")
                yield Select(
                    [("None", _NO_PARENT)],
                    value=_NO_PARENT,
                    id="parent-task",
                )

                yield Label("Assignee", classes="field-label")
                yield Select(
                    [("Unassigned", _NO_ASSIGNEE)],
                    value=_NO_ASSIGNEE,
                    id="assignee",
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
                yield Button("Save" if is_edit else "Add", variant="primary", id="btn-add")
                yield Button("Cancel", id="btn-cancel")

    def on_mount(self) -> None:
        task = self._edit_task
        if task:
            self.query_one("#content", Input).value = task.content
            self.query_one("#description", Input).value = task.description or ""
            self.query_one("#due", Input).value = task.due.date if task.due else ""
            self.query_one("#deadline", Input).value = (
                task.deadline["date"] if task.deadline else ""
            )
            self.query_one("#priority", Select).value = str(task.priority)
            self.query_one("#labels", Input).value = ", ".join(task.labels)
            self.query_one("#duration", Input).value = (
                str(task.duration) if task.duration else ""
            )
            self.query_one("#duration-unit", Select).value = task.duration_unit or "minute"
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
        # Load parent tasks and collaborators for the initial project selection
        self._load_parent_tasks(self._default_project_id)
        self._load_collaborators(self._default_project_id)

    @work
    async def _load_parent_tasks(self, project_id: str | None) -> None:
        """Populate the parent-task dropdown with tasks from *project_id*."""
        select = self.query_one("#parent-task", Select)
        if not project_id:
            # Inbox or no project — just offer "no parent"
            select.set_options([("None", _NO_PARENT)])
            select.value = _NO_PARENT
            return
        try:
            tasks = await self.app.client.get_tasks(project_id=project_id)  # type: ignore[attr-defined]
            options = [("None", _NO_PARENT)] + [
                (t.content, t.id) for t in tasks
            ]
            select.set_options(options)
            # Pre-select the default parent if it exists in this project
            if self._default_parent_id and any(
                t.id == self._default_parent_id for t in tasks
            ):
                select.value = self._default_parent_id
            else:
                select.value = _NO_PARENT
        except Exception:
            select.set_options([("None", _NO_PARENT)])
            select.value = _NO_PARENT

    @work
    async def _load_collaborators(self, project_id: str | None) -> None:
        """Populate the assignee dropdown with collaborators from *project_id*."""
        select = self.query_one("#assignee", Select)
        if not project_id:
            select.set_options([("Unassigned", _NO_ASSIGNEE)])
            select.value = _NO_ASSIGNEE
            return
        try:
            collaborators = await self.app.client.get_collaborators(project_id)  # type: ignore[attr-defined]
            options = [("Unassigned", _NO_ASSIGNEE)] + [
                (c.name, c.id) for c in collaborators
            ]
            select.set_options(options)
            select.value = _NO_ASSIGNEE
        except Exception:
            select.set_options([("Unassigned", _NO_ASSIGNEE)])
            select.value = _NO_ASSIGNEE

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "project":
            project_val = event.value
            project_id = (
                None if (not project_val or project_val == _INBOX) else str(project_val)
            )
            self._load_parent_tasks(project_id)
            self._load_collaborators(project_id)

    # ── keyboard navigation ─────────────────────────────────────────────────

    def _any_select_expanded(self) -> Select | None:
        """Return the expanded Select, if any."""
        for s in self.query(Select):
            if s.expanded:
                return s
        return None

    def on_key(self, event) -> None:
        key = event.key
        expanded = self._any_select_expanded()
        if expanded:
            # Let the overlay handle most keys while a dropdown is open
            if key == "left":
                event.stop()
                expanded.expanded = False
                expanded.focus()
            elif key == "escape":
                event.stop()
                expanded.expanded = False
                expanded.focus()
            # All other keys (up, down, enter, etc.) pass through to the overlay
            return
        if key == "escape":
            event.stop()
            self.dismiss(None)
        elif key == "down":
            event.stop()
            self.focus_next()
        elif key == "up":
            event.stop()
            self.focus_previous()
        elif key == "right":
            focused = self.focused
            if isinstance(focused, Select):
                event.stop()
                focused.action_show_overlay()
        elif key == "ctrl+s":
            event.stop()
            self._submit()
        elif key == "enter":
            event.stop()
            focused = self.focused
            if isinstance(focused, Button):
                if focused.id == "btn-add":
                    self._submit()
                elif focused.id == "btn-cancel":
                    self.dismiss(None)
            elif isinstance(focused, Select):
                focused.action_show_overlay()
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

        parent_raw = self.query_one("#parent-task", Select).value
        parent_id = (
            None if (not parent_raw or parent_raw == _NO_PARENT) else str(parent_raw)
        )

        assignee_raw = self.query_one("#assignee", Select).value
        assignee_id = (
            None if (not assignee_raw or assignee_raw == _NO_ASSIGNEE) else str(assignee_raw)
        )

        result = {
            "content": content,
            "description": description,
            "due_string": due,
            "deadline_date": deadline,
            "priority": priority,
            "labels": labels,
            "project_id": project_id,
            "parent_id": parent_id,
            "duration": duration,
            "duration_unit": duration_unit,
            "assignee_id": assignee_id,
        }
        if self._edit_task is not None:
            result["task_id"] = self._edit_task.id
        self.dismiss(result)
