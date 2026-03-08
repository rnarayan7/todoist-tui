import httpx
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Label
from textual.containers import Vertical
from textual._work_decorator import work

from .api import TodoistClient
from .widgets.project_sidebar import ProjectSidebar
from .widgets.task_list import TaskList
from .widgets.undo_bar import UndoBar
from .screens.add_task import AddTaskScreen


class TodoistApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "Todoist"

    BINDINGS = [
        Binding("a", "add_task", "Add"),
        Binding("c", "complete_task", "Complete"),
        Binding("r", "refresh", "Refresh"),
        Binding("u", "cancel_pending", "Undo", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, api_token: str):
        super().__init__()
        self.client = TodoistClient(api_token)
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
        yield UndoBar()
        yield Footer()

    async def on_mount(self) -> None:
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
            self._current_project_id = None
            self._current_filter = "today"
            self.query_one(TaskList).load(project_id=None, filter_str="today")
        else:
            self._current_project_id = message.project_id
            self._current_filter = None
            self.query_one(TaskList).load(
                project_id=message.project_id, filter_str=None
            )

    # ── actions ─────────────────────────────────────────────────────────────

    def action_add_task(self) -> None:
        def handle_result(result: dict | None) -> None:
            if result is None:
                return
            self._create_task(result)

        self.push_screen(
            AddTaskScreen(default_project_id=self._current_project_id),
            handle_result,
        )

    def action_complete_task(self) -> None:
        task_list = self.query_one(TaskList)
        selected = frozenset(task_list._selected_ids)
        if selected:
            n = len(selected)
            label = f"Completing {n} task{'s' if n > 1 else ''}…"
            self.query_one(UndoBar).show_action(
                label,
                lambda: self._do_complete_tasks(selected),
            )
        else:
            task_id = task_list.focused_task_id
            if not task_id:
                self.notify("No task selected.", severity="warning")
                return
            self.query_one(UndoBar).show_action(
                "Completing task…",
                lambda: self._do_complete_tasks(frozenset({task_id})),
            )

    def action_quit(self) -> None:
        self.exit()

    def action_cancel_pending(self) -> None:
        self.query_one(UndoBar).cancel()

    def action_refresh(self) -> None:
        sidebar = self.query_one(ProjectSidebar)
        sidebar.load_projects()
        self._refresh_tasks()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _do_complete_tasks(self, task_ids: frozenset) -> None:
        self._complete_tasks_worker(task_ids)

    @work
    async def _complete_tasks_worker(self, task_ids: frozenset) -> None:
        errors = 0
        for task_id in task_ids:
            try:
                await self.client.close_task(task_id)
            except httpx.HTTPError:
                errors += 1
        n = len(task_ids)
        if errors:
            self.notify(f"Failed to complete {errors}/{n} task(s).", severity="error")
        else:
            self.notify(f"Completed {n} task{'s' if n > 1 else ''}.")
        self._refresh_tasks()

    def _create_task(self, data: dict) -> None:
        self._create_task_worker(data)

    @work
    async def _create_task_worker(self, data: dict) -> None:
        try:
            await self.client.create_task(
                content=data["content"],
                description=data.get("description"),
                due_string=data.get("due_string"),
                deadline_date=data.get("deadline_date"),
                priority=data.get("priority", 1),
                project_id=data.get("project_id"),
                labels=data.get("labels"),
                duration=data.get("duration"),
                duration_unit=data.get("duration_unit"),
            )
            self.notify("Task added.")
            self._refresh_tasks()
        except httpx.HTTPError as exc:
            self.notify(f"Failed to create task: {exc}", severity="error")

    def _refresh_tasks(self) -> None:
        task_list = self.query_one(TaskList)
        task_list.load(
            project_id=self._current_project_id,
            filter_str=self._current_filter,
        )
