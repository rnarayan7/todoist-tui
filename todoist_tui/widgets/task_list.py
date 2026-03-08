import httpx
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import ListView, ListItem, Label
from textual.worker import work

from ..models import Task

PRIORITY_COLORS = {4: "red", 3: "orange1", 2: "yellow", 1: "white"}


class TaskItem(ListItem):
    """A single task row."""

    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task = task

    def compose(self) -> ComposeResult:
        color = PRIORITY_COLORS.get(self.task.priority, "white")
        due_str = ""
        if self.task.due:
            due_str = f"  [dim]due:{self.task.due.date}[/dim]"
        priority_badge = (
            f" [bold {color}]p{self.task.priority}[/bold {color}]"
            if self.task.priority > 1
            else ""
        )
        yield Label(
            f"[ ] {self.task.content}{priority_badge}{due_str}",
            markup=True,
        )


class TaskList(ListView):
    """Main task panel."""

    focused_task_id: str | None = None

    def load(self, project_id: str | None, filter_str: str | None = None) -> None:
        self._load_tasks(project_id, filter_str)

    @work(exclusive=True)
    async def _load_tasks(
        self, project_id: str | None, filter_str: str | None
    ) -> None:
        self.clear()
        try:
            tasks: list[Task] = await self.app.client.get_tasks(  # type: ignore[attr-defined]
                project_id=project_id, filter_str=filter_str
            )
            if not tasks:
                await self.append(ListItem(Label("[dim]No tasks[/dim]", markup=True)))
                self.focused_task_id = None
                return
            for task in tasks:
                await self.append(TaskItem(task))
            # Focus first item
            self.index = 0
            first = self.query_one(TaskItem)
            self.focused_task_id = first.task.id
        except httpx.HTTPError as exc:
            self.app.notify(f"Failed to load tasks: {exc}", severity="error")

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, TaskItem):
            self.focused_task_id = item.task.id
        else:
            self.focused_task_id = None
