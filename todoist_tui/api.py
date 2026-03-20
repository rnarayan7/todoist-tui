import uuid
import httpx
from typing import Optional
from .models import Collaborator, Project, Task

BASE_URL = "https://api.todoist.com/api/v1"
SYNC_URL = "https://api.todoist.com/api/v1/sync"


class TodoistClient:
    def __init__(self, api_token: str):
        self._token = api_token
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10.0,
        )

    async def get_projects(self) -> list[Project]:
        response = await self._client.get("/projects")
        response.raise_for_status()
        return [Project(**p) for p in response.json()["results"]]

    async def get_tasks(
        self,
        project_id: Optional[str] = None,
        filter_str: Optional[str] = None,
    ) -> list[Task]:
        params: dict = {}
        if filter_str:
            params["filter"] = filter_str
        elif project_id:
            params["project_id"] = project_id

        all_tasks: list[Task] = []
        cursor: str | None = None

        while True:
            if cursor:
                params["cursor"] = cursor
            response = await self._client.get("/tasks", params=params)
            response.raise_for_status()
            data = response.json()
            all_tasks.extend(Task(**t) for t in data["results"])
            cursor = data.get("next_cursor")
            if not cursor:
                break

        return all_tasks

    async def get_collaborators(self, project_id: str) -> list[Collaborator]:
        response = await self._client.get(f"/projects/{project_id}/collaborators")
        response.raise_for_status()
        return [Collaborator(**c) for c in response.json()["results"]]

    async def create_task(
        self,
        content: str,
        description: Optional[str] = None,
        due_string: Optional[str] = None,
        deadline_date: Optional[str] = None,
        priority: int = 1,
        project_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        labels: Optional[list] = None,
        duration: Optional[int] = None,
        duration_unit: Optional[str] = None,
        assignee_id: Optional[str] = None,
    ) -> Task:
        body: dict = {"content": content, "priority": priority}
        if description:
            body["description"] = description
        if due_string:
            body["due_string"] = due_string
        if deadline_date:
            body["deadline_date"] = deadline_date
        if project_id:
            body["project_id"] = project_id
        if parent_id:
            body["parent_id"] = parent_id
        if labels:
            body["labels"] = labels
        if duration and duration_unit:
            body["duration"] = duration
            body["duration_unit"] = duration_unit
        if assignee_id:
            body["assignee_id"] = assignee_id
        response = await self._client.post("/tasks", json=body)
        response.raise_for_status()
        return Task(**response.json())

    async def get_task(self, task_id: str) -> Task:
        response = await self._client.get(f"/tasks/{task_id}")
        response.raise_for_status()
        return Task(**response.json())

    async def update_task(self, task_id: str, **fields) -> Task:
        response = await self._client.post(f"/tasks/{task_id}", json=fields)
        response.raise_for_status()
        return Task(**response.json())

    async def set_due(self, task_id: str, due_string: str) -> Task:
        response = await self._client.post(
            f"/tasks/{task_id}", json={"due_string": due_string}
        )
        response.raise_for_status()
        return Task(**response.json())

    async def move_task(
        self,
        task_id: str,
        *,
        project_id: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> None:
        """Move a task to a different project or under a new parent via the Sync API."""
        args: dict = {"id": task_id}
        if parent_id is not None:
            args["parent_id"] = parent_id
        elif project_id is not None:
            args["project_id"] = project_id
        else:
            return
        command = {"type": "item_move", "uuid": str(uuid.uuid4()), "args": args}
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=10.0,
        ) as client:
            response = await client.post(SYNC_URL, json={"commands": [command]})
            response.raise_for_status()

    async def close_task(self, task_id: str) -> None:
        response = await self._client.post(f"/tasks/{task_id}/close")
        response.raise_for_status()

    async def delete_task(self, task_id: str) -> None:
        response = await self._client.delete(f"/tasks/{task_id}")
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
