import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Label
from textual.containers import Vertical

from .api import TodoistClient
from .widgets.project_sidebar import ProjectSidebar
from .widgets.task_list import TaskList
from .screens.add_task import AddTaskScreen


class TodoistApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "Todoist"

    BINDINGS = [
        Binding("a", "add_task", "Add"),
        Binding("c", "complete_task", "Complete"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, api_token: str):
        super().__init__()
        self._api_token = api_token
        self.client: TodoistClient
        self._current_project_id: str | None = None
        self._current_filter: str | None = "today"
        self._current_title: str = "Today"

    def compose(self) -> ComposeResult:
        yield Header()
        from textual.containers import Horizontal
        with Horizontal(id="main-content"):
            yield ProjectSidebar()
            with Vertical(id="task-panel"):
                yield Label("Today", id="panel-title")
                yield TaskList()
        yield Footer()

    async def on_mount(self) -> None:
        self.client = TodoistClient(self._api_token)
        task_list = self.query_one(TaskList)
        task_list.load(project_id=None, filter_str="today")

    async def on_unmount(self) -> None:
        await self.client.aclose()

    def on_project_sidebar_project_selected(
        self, message: ProjectSidebar.ProjectSelected
    ) -> None:
        self._current_title = message.project_name
        title_label = self.query_one("#panel-title", Label)
        title_label.update(message.project_name)

        if message.project_id is None:
            # "Today" selected
            self._current_project_id = None
            self._current_filter = "today"
            self.query_one(TaskList).load(project_id=None, filter_str="today")
        else:
            self._current_project_id = message.project_id
            self._current_filter = None
            self.query_one(TaskList).load(
                project_id=message.project_id, filter_str=None
            )

    def action_add_task(self) -> None:
        def handle_result(result: dict | None) -> None:
            if result is None:
                return
            self._create_task(result)

        self.push_screen(AddTaskScreen(), handle_result)

    async def _create_task(self, data: dict) -> None:
        try:
            await self.client.create_task(
                content=data["content"],
                due_string=data.get("due_string"),
                priority=data.get("priority", 1),
                project_id=self._current_project_id,
            )
            self.notify("Task added.")
            self._refresh_tasks()
        except httpx.HTTPError as exc:
            self.notify(f"Failed to create task: {exc}", severity="error")

    async def action_complete_task(self) -> None:
        task_list = self.query_one(TaskList)
        task_id = task_list.focused_task_id
        if not task_id:
            self.notify("No task selected.", severity="warning")
            return
        try:
            await self.client.close_task(task_id)
            self.notify("Task completed.")
            self._refresh_tasks()
        except httpx.HTTPError as exc:
            self.notify(f"Failed to complete task: {exc}", severity="error")

    def action_refresh(self) -> None:
        sidebar = self.query_one(ProjectSidebar)
        sidebar.load_projects()
        self._refresh_tasks()

    def _refresh_tasks(self) -> None:
        task_list = self.query_one(TaskList)
        task_list.load(
            project_id=self._current_project_id,
            filter_str=self._current_filter,
        )
