import httpx
from rich.text import Text
from textual.binding import Binding
from textual.widgets import Tree
from textual._work_decorator import work

from ..models import Task

PRIORITY_COLORS = {4: "red", 3: "orange1", 2: "yellow", 1: "white"}


def _task_label(task: Task, selected: bool = False) -> str:
    color = PRIORITY_COLORS.get(task.priority, "white")
    due_str = ""
    if task.due:
        due_str = f"  [dim]due:{task.due.date}[/dim]"
    priority_badge = (
        f" [bold {color}]p{task.priority}[/bold {color}]"
        if task.priority > 1
        else ""
    )
    checkbox = "[bold green]\\[✓][/bold green]" if selected else "[ ]"
    return f"{checkbox} {task.content}{priority_badge}{due_str}"


class TaskList(Tree):
    """Main task panel rendered as a collapsible tree."""

    COMPONENT_CLASSES = {"task-list--item"}
    focused_task_id: str | None = None

    BINDINGS = [
        Binding("right", "expand_node", "Expand", show=False),
        Binding("left", "collapse_or_sidebar", "Collapse", show=False),
    ]

    def __init__(self) -> None:
        super().__init__("", id="task-list")
        self.show_root = False
        self._selected_ids: set[str] = set()
        self._nodes_by_id: dict = {}

    def action_select_cursor(self) -> None:
        """Click or Enter toggles the selection checkmark on a task node."""
        node = self.cursor_node
        if node is None or node.data is None:
            return
        task: Task = node.data
        if task.id in self._selected_ids:
            self._selected_ids.discard(task.id)
        else:
            self._selected_ids.add(task.id)
        node.label = Text.from_markup(
            _task_label(task, selected=task.id in self._selected_ids)
        )

    def action_expand_node(self) -> None:
        node = self.cursor_node
        if node and node.allow_expand and not node.is_expanded:
            node.expand()

    def action_collapse_or_sidebar(self) -> None:
        node = self.cursor_node
        if node and node.is_expanded:
            node.collapse()
        else:
            from .project_sidebar import ProjectSidebar
            self.app.query_one(ProjectSidebar).focus()

    def load(self, project_id: str | None, filter_str: str | None = None) -> None:
        self._load_tasks(project_id, filter_str)

    @work(exclusive=True)
    async def _load_tasks(
        self, project_id: str | None, filter_str: str | None
    ) -> None:
        self.clear()
        self.root.expand()
        self._selected_ids.clear()
        self._nodes_by_id.clear()
        try:
            tasks: list[Task] = await self.app.client.get_tasks(  # type: ignore[attr-defined]
                project_id=project_id, filter_str=filter_str
            )
            if not tasks:
                self.root.add_leaf("[dim]No tasks[/dim]")
                self.focused_task_id = None
                return

            task_ids = {t.id for t in tasks}

            # Group tasks by parent_id; treat tasks whose parent is filtered out as roots
            by_parent: dict[str | None, list[Task]] = {}
            for task in tasks:
                key = task.parent_id if (task.parent_id and task.parent_id in task_ids) else None
                by_parent.setdefault(key, []).append(task)

            def add_children(parent_node, parent_id: str | None) -> None:
                for task in by_parent.get(parent_id, []):
                    label = _task_label(task)
                    if task.id in by_parent:
                        child_node = parent_node.add(label, data=task, expand=False)
                    else:
                        child_node = parent_node.add_leaf(label, data=task)
                    self._nodes_by_id[task.id] = child_node
                    add_children(child_node, task.id)

            add_children(self.root, None)

            first_node = next(
                (node for node in self.root.children if node.data),
                None,
            )
            if first_node:
                self.focused_task_id = first_node.data.id
                self.move_cursor(first_node)

        except httpx.HTTPError as exc:
            self.app.notify(f"Failed to load tasks: {exc}", severity="error")

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node = event.node
        self.focused_task_id = node.data.id if node.data else None
