"""Claude-powered task assistant with Todoist tool use."""

import os
from anthropic import AsyncAnthropic

from .api import TodoistClient
from .models import Task

TOOLS = [
    {
        "name": "list_tasks",
        "description": "List all tasks currently visible in the TUI. Returns task details including id, content, due date, priority, labels, and parent relationships.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_projects",
        "description": "List all projects in the user's Todoist account.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "create_task",
        "description": "Create a new task in Todoist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Task name/content"},
                "description": {"type": "string", "description": "Optional description"},
                "due_string": {
                    "type": "string",
                    "description": "Natural language due date, e.g. 'today', 'tomorrow', 'next monday', '2026-04-01'",
                },
                "priority": {
                    "type": "integer",
                    "enum": [1, 2, 3, 4],
                    "description": "Priority: 1=normal, 2=medium, 3=high, 4=urgent",
                },
                "project_id": {"type": "string", "description": "Project ID to add the task to"},
                "parent_id": {"type": "string", "description": "Parent task ID to make this a subtask"},
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to apply",
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "update_task",
        "description": "Update an existing task's content, description, priority, or labels.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID of the task to update"},
                "content": {"type": "string", "description": "New task name/content"},
                "description": {"type": "string", "description": "New description"},
                "priority": {
                    "type": "integer",
                    "enum": [1, 2, 3, 4],
                    "description": "Priority: 1=normal, 2=medium, 3=high, 4=urgent",
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Labels to set",
                },
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "set_due",
        "description": "Set or change the due date on a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID of the task"},
                "due_string": {
                    "type": "string",
                    "description": "Natural language due date, e.g. 'today', 'tomorrow', 'next monday'",
                },
            },
            "required": ["task_id", "due_string"],
        },
    },
    {
        "name": "complete_task",
        "description": "Mark a task as complete.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID of the task to complete"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "delete_task",
        "description": "Permanently delete a task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID of the task to delete"},
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "move_task",
        "description": "Move a task to a different project or under a different parent task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "ID of the task to move"},
                "project_id": {"type": "string", "description": "Target project ID"},
                "parent_id": {"type": "string", "description": "Target parent task ID"},
            },
            "required": ["task_id"],
        },
    },
]

SYSTEM_PROMPT = """\
You are a helpful Todoist assistant embedded in a terminal UI. You help the user manage their tasks.

You can view, create, update, schedule, complete, delete, and move tasks using the provided tools.

Guidelines:
- Be concise — the user is in a terminal, keep responses short.
- When the user asks to change multiple tasks, make all the tool calls needed.
- When referring to tasks, use their content/name, not their IDs.
- Always use list_tasks first if you need to know what tasks exist before making changes.
- Today's date is {today}.
"""


def _serialize_task(task: Task) -> dict:
    """Serialize a Task to a plain dict for Claude context."""
    d = {
        "id": task.id,
        "content": task.content,
        "priority": task.priority,
    }
    if task.due:
        d["due"] = task.due.date
    if task.parent_id:
        d["parent_id"] = task.parent_id
    if task.project_id:
        d["project_id"] = task.project_id
    if task.labels:
        d["labels"] = task.labels
    if task.description:
        d["description"] = task.description
    return d


class TaskAssistant:
    """Runs a Claude tool-use loop against the Todoist API."""

    def __init__(self, client: TodoistClient):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or export it in your shell."
            )
        self._anthropic = AsyncAnthropic(api_key=api_key)
        self._client = client
        self._messages: list[dict] = []

    def _get_system_prompt(self) -> str:
        from datetime import date
        return SYSTEM_PROMPT.format(today=date.today().isoformat())

    async def _execute_tool(self, name: str, input: dict) -> str:
        """Execute a tool call and return the result as a string."""
        try:
            if name == "list_tasks":
                tasks = await self._client.get_tasks()
                serialized = [_serialize_task(t) for t in tasks]
                return str(serialized) if serialized else "No tasks found."

            elif name == "list_projects":
                projects = await self._client.get_projects()
                return str([{"id": p.id, "name": p.name} for p in projects])

            elif name == "create_task":
                task = await self._client.create_task(**input)
                return f"Created task: {task.content} (id: {task.id})"

            elif name == "update_task":
                task_id = input.pop("task_id")
                task = await self._client.update_task(task_id, **input)
                return f"Updated task: {task.content}"

            elif name == "set_due":
                task = await self._client.set_due(input["task_id"], input["due_string"])
                return f"Set due date on '{task.content}' to {task.due.date if task.due else 'none'}"

            elif name == "complete_task":
                await self._client.close_task(input["task_id"])
                return f"Completed task {input['task_id']}"

            elif name == "delete_task":
                await self._client.delete_task(input["task_id"])
                return f"Deleted task {input['task_id']}"

            elif name == "move_task":
                task_id = input["task_id"]
                await self._client.move_task(
                    task_id,
                    project_id=input.get("project_id"),
                    parent_id=input.get("parent_id"),
                )
                return f"Moved task {task_id}"

            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error: {e}"

    async def send(self, user_message: str) -> str:
        """Send a user message and run the tool loop. Returns Claude's final text."""
        self._messages.append({"role": "user", "content": user_message})

        while True:
            response = await self._anthropic.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=self._get_system_prompt(),
                tools=TOOLS,
                messages=self._messages,
            )

            # Collect the full assistant response
            self._messages.append({"role": "assistant", "content": response.content})

            # If no tool use, extract text and return
            if response.stop_reason == "end_turn":
                text_parts = [
                    block.text for block in response.content if block.type == "text"
                ]
                return "\n".join(text_parts) if text_parts else "(no response)"

            # Process tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            if not tool_results:
                # No tool calls and no end_turn — shouldn't happen, but bail
                text_parts = [
                    block.text for block in response.content if block.type == "text"
                ]
                return "\n".join(text_parts) if text_parts else "(no response)"

            self._messages.append({"role": "user", "content": tool_results})

    def reset(self) -> None:
        """Clear conversation history."""
        self._messages.clear()
