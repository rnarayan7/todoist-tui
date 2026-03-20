import httpx
from rich.text import Text
from textual.binding import Binding
from textual.widgets import Tree
from textual._work_decorator import work

from ..models import Collaborator, Task

PRIORITY_COLORS = {4: "red", 3: "orange1", 2: "yellow", 1: "white"}

# Module-level name cache used by _task_label
_collaborator_names: dict[str, str] = {}
_fetched_projects: set[str] = set()


def _task_label(task: Task, selected: bool = False) -> str:
    color = PRIORITY_COLORS.get(task.priority, "white")
    due_str = ""
    if task.due:
        due_str = f"  [dim cyan]due:{task.due.date}[/dim cyan]"
    assignee_str = ""
    if task.assignee_id:
        name = _collaborator_names.get(task.assignee_id, "assigned")
        assignee_str = f"  [orchid]@{name}[/orchid]"
    priority_badge = (
        f" [bold {color}]p{task.priority}[/bold {color}]"
        if task.priority > 1
        else ""
    )
    checkbox = "[bold green]\\[✓][/bold green]" if selected else "[ ]"
    return f"{checkbox} {task.content}{priority_badge}{due_str}{assignee_str}"


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

    def set_collaborators(self, collaborators: list[Collaborator], project_id: str | None = None) -> None:
        """Update the collaborator name cache used for task labels."""
        _collaborator_names.update({c.id: c.name for c in collaborators})
        if project_id:
            _fetched_projects.add(project_id)
        # Re-render labels for tasks with assignees so names appear
        for node in self._iter_all_nodes(self.root):
            if node.data and node.data.assignee_id:
                selected = node.data.id in self._selected_ids
                node.set_label(Text.from_markup(_task_label(node.data, selected=selected)))

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

    def action_expand_all_nodes(self) -> None:
        """Toggle: expand all if any are collapsed, otherwise collapse all."""
        expandable = [
            node for node in self._iter_all_nodes(self.root)
            if node.allow_expand
        ]
        if not expandable:
            return
        if all(node.is_expanded for node in expandable):
            for node in expandable:
                node.collapse()
        else:
            for node in expandable:
                node.expand()

    def _iter_all_nodes(self, node):
        for child in node.children:
            yield child
            yield from self._iter_all_nodes(child)

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

            # Fetch collaborators for any projects we haven't seen yet
            needed = {
                t.project_id
                for t in tasks
                if t.assignee_id and t.project_id not in _fetched_projects
            }
            for pid in needed:
                try:
                    collabs = await self.app.client.get_collaborators(pid)  # type: ignore[attr-defined]
                    _collaborator_names.update({c.id: c.name for c in collabs})
                    _fetched_projects.add(pid)
                except Exception:
                    _fetched_projects.add(pid)  # don't retry on failure

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

    # ── Granular tree operations ──────────────────────────────────────────

    def remove_tasks(self, task_ids: set[str]) -> None:
        """Remove tasks by id without a full reload."""
        # Before removing, find a neighbor for the cursor if the focused task will be removed
        next_focus_node = None
        if self.focused_task_id and self.focused_task_id in task_ids:
            focused_node = self._nodes_by_id.get(self.focused_task_id)
            if focused_node and focused_node.parent:
                siblings = [s for s in focused_node.parent.children if s.data and s.data.id not in task_ids]
                if siblings:
                    # Find the nearest sibling: prefer next, then previous
                    idx = list(focused_node.parent.children).index(focused_node)
                    after = [s for s in siblings if list(focused_node.parent.children).index(s) > idx]
                    before = [s for s in siblings if list(focused_node.parent.children).index(s) < idx]
                    next_focus_node = after[0] if after else (before[-1] if before else None)

        for task_id in task_ids:
            node = self._nodes_by_id.pop(task_id, None)
            if node is None:
                continue
            # Clean up descendants from bookkeeping
            for desc in self._iter_all_nodes(node):
                if desc.data:
                    self._nodes_by_id.pop(desc.data.id, None)
                    self._selected_ids.discard(desc.data.id)
            self._selected_ids.discard(task_id)
            node.remove()

        # If tree is now empty, show placeholder
        if not list(self.root.children):
            self.root.add_leaf("[dim]No tasks[/dim]")
            self.focused_task_id = None
        elif self.focused_task_id in task_ids:
            if next_focus_node:
                self.focused_task_id = next_focus_node.data.id
                self.move_cursor(next_focus_node)
            else:
                # Fallback: first task in tree
                first = next(
                    (n for n in self._iter_all_nodes(self.root) if n.data and n.data.id not in task_ids), None
                )
                if first:
                    self.focused_task_id = first.data.id
                    self.move_cursor(first)
                else:
                    self.focused_task_id = None

    def insert_task(self, task: Task) -> None:
        """Insert a single task into the tree without a full reload."""
        # Remove "No tasks" placeholder
        for child in list(self.root.children):
            if child.data is None:
                child.remove()

        label = _task_label(task)
        if task.parent_id and task.parent_id in self._nodes_by_id:
            parent_node = self._nodes_by_id[task.parent_id]
            new_node = parent_node.add_leaf(label, data=task)
            # Make parent expandable if it wasn't already
            parent_node.allow_expand = True
            parent_node.expand()
        else:
            new_node = self.root.add_leaf(label, data=task)

        self._nodes_by_id[task.id] = new_node
        # Only move cursor to new task if the list was previously empty
        if not self.focused_task_id:
            self.move_cursor(new_node)
            self.focused_task_id = task.id

    def update_task(self, task: Task) -> None:
        """Update a task's data and label in place."""
        node = self._nodes_by_id.get(task.id)
        if node is None:
            return
        node.data = task
        selected = task.id in self._selected_ids
        node.set_label(Text.from_markup(_task_label(task, selected=selected)))

    def reparent_tasks(self, task_ids: set[str], new_parent_id: str) -> None:
        """Move tasks under a new parent node in the tree."""
        parent_node = self._nodes_by_id.get(new_parent_id)
        if parent_node is None:
            return

        saved_focus = self.focused_task_id

        for task_id in task_ids:
            self._detach_and_readd(task_id, parent_node)

        parent_node.allow_expand = True
        parent_node.expand()

        # Restore cursor
        if saved_focus and saved_focus in self._nodes_by_id:
            self.move_cursor(self._nodes_by_id[saved_focus])

    def reparent_to_root(self, task_ids: set[str]) -> None:
        """Move tasks to the tree root (un-parent them)."""
        saved_focus = self.focused_task_id

        for task_id in task_ids:
            self._detach_and_readd(task_id, self.root)
            # Update the old parent: if it has no children left, make it a leaf
            # (the old parent's allow_expand is handled by Textual automatically)

        # Restore cursor
        if saved_focus and saved_focus in self._nodes_by_id:
            self.move_cursor(self._nodes_by_id[saved_focus])

    def _detach_and_readd(self, task_id: str, target_node) -> None:
        """Remove a task node and re-add its subtree under target_node."""
        node = self._nodes_by_id.get(task_id)
        if node is None:
            return

        # Remember old parent to fix up after removal
        old_parent = node.parent

        # Collect subtree data before removal
        subtree = self._collect_subtree(node)

        # Clean up bookkeeping for node and descendants
        for desc in self._iter_all_nodes(node):
            if desc.data:
                self._nodes_by_id.pop(desc.data.id, None)
        self._nodes_by_id.pop(task_id, None)
        self._selected_ids.discard(task_id)
        node.remove()

        # If old parent has no children left, disable expand
        if old_parent and old_parent is not self.root and not list(old_parent.children):
            old_parent.allow_expand = False

        # Re-add under target
        self._readd_subtree(target_node, subtree)

    def _collect_subtree(self, node) -> dict:
        """Collect task data and children recursively."""
        children = []
        for child in node.children:
            if child.data:
                children.append(self._collect_subtree(child))
        return {"task": node.data, "children": children}

    def _readd_subtree(self, parent_node, subtree: dict) -> None:
        """Re-add a subtree under a parent node."""
        task = subtree["task"]
        if not task:
            return
        label = _task_label(task)
        if subtree["children"]:
            new_node = parent_node.add(label, data=task, expand=True)
        else:
            new_node = parent_node.add_leaf(label, data=task)
        self._nodes_by_id[task.id] = new_node
        for child_data in subtree["children"]:
            self._readd_subtree(new_node, child_data)

    # ── Events ─────────────────────────────────────────────────────────────

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        node = event.node
        self.focused_task_id = node.data.id if node.data else None
