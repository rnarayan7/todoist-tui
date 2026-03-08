import httpx
from typing import Optional
from .models import Project, Task

BASE_URL = "https://api.todoist.com/rest/v2"


class TodoistClient:
    def __init__(self, api_token: str):
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10.0,
        )

    async def get_projects(self) -> list[Project]:
        response = await self._client.get("/projects")
        response.raise_for_status()
        return [Project(**p) for p in response.json()]

    async def get_tasks(
        self,
        project_id: Optional[str] = None,
        filter_str: Optional[str] = None,
    ) -> list[Task]:
        params: dict = {}
        if project_id:
            params["project_id"] = project_id
        if filter_str:
            params["filter"] = filter_str
        response = await self._client.get("/tasks", params=params)
        response.raise_for_status()
        return [Task(**t) for t in response.json()]

    async def create_task(
        self,
        content: str,
        due_string: Optional[str] = None,
        priority: int = 1,
        project_id: Optional[str] = None,
    ) -> Task:
        body: dict = {"content": content, "priority": priority}
        if due_string:
            body["due_string"] = due_string
        if project_id:
            body["project_id"] = project_id
        response = await self._client.post("/tasks", json=body)
        response.raise_for_status()
        return Task(**response.json())

    async def close_task(self, task_id: str) -> None:
        response = await self._client.post(f"/tasks/{task_id}/close")
        response.raise_for_status()

    async def aclose(self) -> None:
        await self._client.aclose()
