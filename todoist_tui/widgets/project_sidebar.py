import httpx
from textual.app import ComposeResult
from textual.events import Key
from textual.message import Message
from textual.widgets import ListView, ListItem, Label
from textual._work_decorator import work

from ..models import Project


class ProjectSidebar(ListView):
    """Sidebar listing 'Today' plus all Todoist projects."""

    class ProjectSelected(Message):
        def __init__(self, project_id: str | None, project_name: str) -> None:
            super().__init__()
            self.project_id = project_id  # None means "Today"
            self.project_name = project_name

    def on_mount(self) -> None:
        self.load_projects()

    @work(exclusive=True)
    async def load_projects(self) -> None:
        self.clear()
        today_item = ListItem(Label("Today"))
        today_item._is_today = True  # type: ignore[attr-defined]
        await self.append(today_item)
        try:
            projects: list[Project] = await self.app.client.get_projects()  # type: ignore[attr-defined]
            for project in projects:
                item = ListItem(Label(project.name))
                item._project_id = project.id  # type: ignore[attr-defined]
                item._project_name = project.name  # type: ignore[attr-defined]
                await self.append(item)
        except httpx.HTTPError as exc:
            self.app.notify(f"Failed to load projects: {exc}", severity="error")

    def on_key(self, event: Key) -> None:
        if event.key == "right":
            event.prevent_default()
            from .task_list import TaskList
            self.app.query_one(TaskList).focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if item is None:
            return
        if getattr(item, "_is_today", False):
            self.post_message(self.ProjectSelected(None, "Today"))
        elif hasattr(item, "_project_id"):
            self.post_message(
                self.ProjectSelected(item._project_id, item._project_name)  # type: ignore[attr-defined]
            )
