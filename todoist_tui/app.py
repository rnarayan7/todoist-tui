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
from .screens.due_date_screen import DueDateScreen
from .screens.priority_screen import PriorityScreen
from .screens.assignee_screen import AssigneeScreen
from .widgets.chat_pane import ChatPane


class TodoistApp(App):
    CSS_PATH = "app.tcss"
    TITLE = "Todoist"

    BINDINGS = [
        Binding("a", "add_task", "Add"),
        Binding("c", "complete_task", "Complete"),
        Binding("d", "delete_task", "Delete"),
        Binding("m", "move_task", "Move"),
        Binding("p", "set_priority", "Priority"),
        Binding("s", "set_due", "Schedule"),
        Binding("i", "set_assignee", "Assign"),
        Binding("e", "edit_task", "Edit"),
        Binding("w", "expand_all", "Expand/Collapse all"),
        Binding("r", "reload", "Refresh"),
        Binding("slash", "open_chat", "Ask Claude"),
        Binding("u", "cancel_pending", "Undo", show=False),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, api_token: str):
        super().__init__()
        self.client = TodoistClient(api_token)
        self._current_project_id: str | None = None
        self._current_filter: str | None = "today"
        self._current_title: str = "Today"
        self._assistant = None  # lazy-init on first chat open
        self._collaborators: list = []

    def compose(self) -> ComposeResult:
        yield Header()
        from textual.containers import Horizontal
        with Horizontal(id="main-content"):
            yield ProjectSidebar()
            with Vertical(id="task-panel"):
                yield Label("Today", id="panel-title")
                yield TaskList()
        yield ChatPane(id="chat-pane")
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
            self._load_collaborators(message.project_id)

    # ── actions ─────────────────────────────────────────────────────────────

    def action_add_task(self) -> None:
        def handle_result(result: dict | None) -> None:
            if result is None:
                return
            self._create_task(result)

        task_list = self.query_one(TaskList)
        # Only pre-select a parent task when the task list has focus
        focused_id: str | None = None
        focused_name: str | None = None
        if task_list.has_focus:
            focused_id = task_list.focused_task_id
            if focused_id:
                node = task_list._nodes_by_id.get(focused_id)
                if node and node.data:
                    focused_name = node.data.content

        self.push_screen(
            AddTaskScreen(
                default_project_id=self._current_project_id,
                default_parent_id=focused_id,
                default_parent_name=focused_name,
            ),
            handle_result,
        )

    def action_edit_task(self) -> None:
        task_list = self.query_one(TaskList)
        task_id = task_list.focused_task_id
        if not task_id:
            self.notify("No task selected.", severity="warning")
            return
        node = task_list._nodes_by_id.get(task_id)
        if not node or not node.data:
            return
        task = node.data

        def handle_result(result: dict | None) -> None:
            if result is None:
                return
            if "task_id" in result:
                self._edit_task(result)
            else:
                self._create_task(result)

        self.push_screen(
            AddTaskScreen(
                default_project_id=task.project_id,
                default_parent_id=task.parent_id,
                edit_task=task,
            ),
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

    def action_delete_task(self) -> None:
        task_list = self.query_one(TaskList)
        selected = frozenset(task_list._selected_ids)
        if selected:
            n = len(selected)
            label = f"Deleting {n} task{'s' if n > 1 else ''}…"
            self.query_one(UndoBar).show_action(
                label,
                lambda: self._do_delete_tasks(selected),
            )
        else:
            task_id = task_list.focused_task_id
            if not task_id:
                self.notify("No task selected.", severity="warning")
                return
            self.query_one(UndoBar).show_action(
                "Deleting task…",
                lambda: self._do_delete_tasks(frozenset({task_id})),
            )

    def action_move_task(self) -> None:
        task_list = self.query_one(TaskList)
        selected = frozenset(task_list._selected_ids)
        if not selected:
            self.notify(
                "Mark tasks for moving with Enter or click first.", severity="warning"
            )
            return

        sidebar = self.query_one(ProjectSidebar)

        if sidebar.has_focus:
            # Move selected tasks to the highlighted project
            item = sidebar.highlighted_child
            if item is None:
                self.notify("No project highlighted.", severity="warning")
                return
            if getattr(item, "_is_today", False):
                self.notify("Cannot move tasks to the Today filter.", severity="warning")
                return
            project_id = getattr(item, "_project_id", None)
            project_name = getattr(item, "_project_name", "")
            self._do_move_tasks(
                selected,
                {"mode": "project", "target_id": project_id, "target_name": project_name},
            )
        else:
            # Move selected tasks under the currently focused task
            target_id = task_list.focused_task_id
            if not target_id:
                self.notify("No target task highlighted.", severity="warning")
                return
            if target_id in selected:
                self.notify("Cannot move a task under itself.", severity="warning")
                return
            node = task_list._nodes_by_id.get(target_id)
            target_name = (
                node.data.content if node and node.data else target_id
            )
            self._do_move_tasks(
                selected,
                {"mode": "parent", "target_id": target_id, "target_name": target_name},
            )

    def action_set_due(self) -> None:
        task_list = self.query_one(TaskList)
        selected = frozenset(task_list._selected_ids)
        if not selected:
            task_id = task_list.focused_task_id
            if not task_id:
                self.notify("No task selected.", severity="warning")
                return
            selected = frozenset({task_id})

        def handle_result(due_string: str | None) -> None:
            if due_string is None:
                return
            self._do_set_due(selected, due_string)

        self.push_screen(DueDateScreen(), handle_result)

    def action_set_priority(self) -> None:
        task_list = self.query_one(TaskList)
        selected = frozenset(task_list._selected_ids)
        if not selected:
            task_id = task_list.focused_task_id
            if not task_id:
                self.notify("No task selected.", severity="warning")
                return
            selected = frozenset({task_id})

        def handle_result(priority: int | None) -> None:
            if priority is None:
                return
            self._do_set_priority(selected, priority)

        self.push_screen(PriorityScreen(), handle_result)

    def action_set_assignee(self) -> None:
        if not self._collaborators:
            self.notify("No collaborators in this project.", severity="warning")
            return

        task_list = self.query_one(TaskList)
        selected = frozenset(task_list._selected_ids)
        if not selected:
            task_id = task_list.focused_task_id
            if not task_id:
                self.notify("No task selected.", severity="warning")
                return
            selected = frozenset({task_id})

        collabs = [(c.name, c.id) for c in self._collaborators]

        def handle_result(assignee_id: str | None) -> None:
            if assignee_id is None:
                return
            real_id = None if assignee_id == AssigneeScreen.UNASSIGN else assignee_id
            self._do_set_assignee(selected, real_id)

        self.push_screen(AssigneeScreen(collabs), handle_result)

    def action_open_chat(self) -> None:
        if self._assistant is None:
            try:
                from .assistant import TaskAssistant
                self._assistant = TaskAssistant(self.client)
            except RuntimeError as e:
                self.notify(str(e), severity="error")
                return
        self.query_one(ChatPane).focus_input()

    def action_expand_all(self) -> None:
        self.query_one(TaskList).action_expand_all_nodes()

    def action_quit(self) -> None:
        self.exit()

    def action_cancel_pending(self) -> None:
        self.query_one(UndoBar).cancel()

    def action_reload(self) -> None:
        sidebar = self.query_one(ProjectSidebar)
        sidebar.load_projects()
        self._refresh_tasks()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _do_complete_tasks(self, task_ids: frozenset) -> None:
        self._complete_tasks_worker(task_ids)

    @work
    async def _complete_tasks_worker(self, task_ids: frozenset) -> None:
        succeeded = set()
        for task_id in task_ids:
            try:
                await self.client.close_task(task_id)
                succeeded.add(task_id)
            except httpx.HTTPError:
                pass
        n = len(task_ids)
        errors = n - len(succeeded)
        if errors:
            self.notify(f"Failed to complete {errors}/{n} task(s).", severity="error")
        else:
            self.notify(f"Completed {n} task{'s' if n > 1 else ''}.")
        if succeeded:
            self.query_one(TaskList).remove_tasks(succeeded)

    def _do_delete_tasks(self, task_ids: frozenset) -> None:
        self._delete_tasks_worker(task_ids)

    @work
    async def _delete_tasks_worker(self, task_ids: frozenset) -> None:
        succeeded = set()
        for task_id in task_ids:
            try:
                await self.client.delete_task(task_id)
                succeeded.add(task_id)
            except httpx.HTTPError:
                pass
        n = len(task_ids)
        errors = n - len(succeeded)
        if errors:
            self.notify(f"Failed to delete {errors}/{n} task(s).", severity="error")
        else:
            self.notify(f"Deleted {n} task{'s' if n > 1 else ''}.")
        if succeeded:
            self.query_one(TaskList).remove_tasks(succeeded)

    def _do_move_tasks(self, task_ids: frozenset, result: dict) -> None:
        self._move_tasks_worker(task_ids, result)

    @work
    async def _move_tasks_worker(self, task_ids: frozenset, result: dict) -> None:
        mode = result["mode"]
        target_id = result["target_id"]
        target_name = result["target_name"]
        succeeded = set()
        for task_id in task_ids:
            try:
                if mode == "project":
                    await self.client.move_task(task_id, project_id=target_id)
                else:
                    await self.client.move_task(task_id, parent_id=target_id)
                succeeded.add(task_id)
            except httpx.HTTPError as exc:
                self.notify(f"Move error: {exc}", severity="error")
        n = len(task_ids)
        errors = n - len(succeeded)
        if errors:
            self.notify(f"Failed to move {errors}/{n} task(s).", severity="error")
        else:
            verb = "under" if mode == "parent" else "to"
            self.notify(
                f"Moved {n} task{'s' if n > 1 else ''} {verb} \"{target_name}\"."
            )
        task_list = self.query_one(TaskList)
        if succeeded:
            if mode == "parent":
                task_list.reparent_tasks(succeeded, target_id)
            elif mode == "project":
                if target_id == self._current_project_id:
                    # Same project — tasks are being un-parented to root level
                    task_list.reparent_to_root(succeeded)
                elif self._current_project_id is not None:
                    # Different project — tasks leave this view
                    task_list.remove_tasks(succeeded)
                else:
                    # "today" filter view — tasks still match, just clear selection
                    task_list._selected_ids -= succeeded

    def _do_set_due(self, task_ids: frozenset, due_string: str) -> None:
        self._set_due_worker(task_ids, due_string)

    @work
    async def _set_due_worker(self, task_ids: frozenset, due_string: str) -> None:
        errors = 0
        updated_tasks = []
        for task_id in task_ids:
            try:
                updated = await self.client.set_due(task_id, due_string)
                updated_tasks.append(updated)
            except httpx.HTTPError:
                errors += 1
        n = len(task_ids)
        if errors:
            self.notify(f"Failed to set due date on {errors}/{n} task(s).", severity="error")
        else:
            self.notify(f"Due date set to \"{due_string}\" on {n} task{'s' if n > 1 else ''}.")
        task_list = self.query_one(TaskList)
        for task in updated_tasks:
            task_list.update_task(task)

    def _do_set_priority(self, task_ids: frozenset, priority: int) -> None:
        self._set_priority_worker(task_ids, priority)

    @work
    async def _set_priority_worker(self, task_ids: frozenset, priority: int) -> None:
        errors = 0
        updated_tasks = []
        for task_id in task_ids:
            try:
                updated = await self.client.update_task(task_id, priority=priority)
                updated_tasks.append(updated)
            except httpx.HTTPError:
                errors += 1
        n = len(task_ids)
        labels = {1: "Normal", 2: "Medium", 3: "High", 4: "Urgent"}
        if errors:
            self.notify(f"Failed to set priority on {errors}/{n} task(s).", severity="error")
        else:
            self.notify(f"Priority set to {labels[priority]} on {n} task{'s' if n > 1 else ''}.")
        task_list = self.query_one(TaskList)
        for task in updated_tasks:
            task_list.update_task(task)

    def _do_set_assignee(self, task_ids: frozenset, assignee_id: str | None) -> None:
        self._set_assignee_worker(task_ids, assignee_id)

    @work
    async def _set_assignee_worker(self, task_ids: frozenset, assignee_id: str | None) -> None:
        errors = 0
        updated_tasks = []
        for task_id in task_ids:
            try:
                updated = await self.client.update_task(task_id, assignee_id=assignee_id)
                updated_tasks.append(updated)
            except httpx.HTTPError:
                errors += 1
        n = len(task_ids)
        if errors:
            self.notify(f"Failed to set assignee on {errors}/{n} task(s).", severity="error")
        else:
            if assignee_id:
                name = next((c.name for c in self._collaborators if c.id == assignee_id), "someone")
                self.notify(f"Assigned {n} task{'s' if n > 1 else ''} to {name}.")
            else:
                self.notify(f"Unassigned {n} task{'s' if n > 1 else ''}.")
        task_list = self.query_one(TaskList)
        for task in updated_tasks:
            task_list.update_task(task)

    def _create_task(self, data: dict) -> None:
        self._create_task_worker(data)

    @work
    async def _create_task_worker(self, data: dict) -> None:
        try:
            task = await self.client.create_task(
                content=data["content"],
                description=data.get("description"),
                due_string=data.get("due_string"),
                deadline_date=data.get("deadline_date"),
                priority=data.get("priority", 1),
                project_id=data.get("project_id"),
                parent_id=data.get("parent_id"),
                labels=data.get("labels"),
                duration=data.get("duration"),
                duration_unit=data.get("duration_unit"),
                assignee_id=data.get("assignee_id"),
            )
            self.notify("Task added.")
            self.query_one(TaskList).insert_task(task)
        except httpx.HTTPError as exc:
            self.notify(f"Failed to create task: {exc}", severity="error")

    def _edit_task(self, data: dict) -> None:
        self._edit_task_worker(data)

    @work
    async def _edit_task_worker(self, data: dict) -> None:
        task_id = data.pop("task_id")
        # Build the update fields, filtering out None values
        fields: dict = {}
        fields["content"] = data["content"]
        fields["priority"] = data.get("priority", 1)
        if data.get("description") is not None:
            fields["description"] = data["description"]
        else:
            fields["description"] = ""
        if data.get("due_string"):
            fields["due_string"] = data["due_string"]
        if data.get("deadline_date"):
            fields["deadline_date"] = data["deadline_date"]
        if data.get("labels"):
            fields["labels"] = data["labels"]
        else:
            fields["labels"] = []
        if data.get("duration") and data.get("duration_unit"):
            fields["duration"] = data["duration"]
            fields["duration_unit"] = data["duration_unit"]
        if data.get("assignee_id"):
            fields["assignee_id"] = data["assignee_id"]
        else:
            fields["assignee_id"] = None
        try:
            updated = await self.client.update_task(task_id, **fields)
            self.notify("Task updated.")
            self.query_one(TaskList).update_task(updated)
        except httpx.HTTPError as exc:
            self.notify(f"Failed to update task: {exc}", severity="error")

    @work
    async def _load_collaborators(self, project_id: str) -> None:
        try:
            collaborators = await self.client.get_collaborators(project_id)
            self._collaborators = collaborators
            self.query_one(TaskList).set_collaborators(collaborators, project_id=project_id)
        except Exception:
            pass  # non-shared projects may not have collaborators

    def _refresh_tasks(self) -> None:
        task_list = self.query_one(TaskList)
        task_list.load(
            project_id=self._current_project_id,
            filter_str=self._current_filter,
        )
