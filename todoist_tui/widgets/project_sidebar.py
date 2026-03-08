import httpx
from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import ListView, ListItem, Label
from textual.worker import work

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
        await self.append(ListItem(Label("Today"), id="project-today"))
        try:
            projects: list[Project] = await self.app.client.get_projects()  # type: ignore[attr-defined]
            for project in projects:
                await self.append(
                    ListItem(Label(project.name), id=f"project-{project.id}")
                )
        except httpx.HTTPError as exc:
            self.app.notify(f"Failed to load projects: {exc}", severity="error")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        item_id = item.id or ""
        if item_id == "project-today":
            self.post_message(self.ProjectSelected(None, "Today"))
        elif item_id.startswith("project-"):
            project_id = item_id.removeprefix("project-")
            label = item.query_one(Label)
            self.post_message(self.ProjectSelected(project_id, str(label.renderable)))
