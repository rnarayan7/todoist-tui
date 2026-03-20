from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DueDate:
    date: str
    string: Optional[str] = None
    is_recurring: bool = False
    datetime: Optional[str] = None
    timezone: Optional[str] = None

    def __init__(self, **kwargs):
        self.date = kwargs.get("date", "")
        self.string = kwargs.get("string")
        self.is_recurring = kwargs.get("is_recurring", False)
        self.datetime = kwargs.get("datetime")
        self.timezone = kwargs.get("timezone")


@dataclass
class Project:
    id: str
    name: str

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "")
        self.name = kwargs.get("name", "Unnamed")


@dataclass
class Collaborator:
    id: str
    name: str
    email: str

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "")
        self.name = kwargs.get("name", "")
        self.email = kwargs.get("email", "")


@dataclass
class Task:
    id: str
    content: str
    priority: int
    project_id: Optional[str]
    due: Optional[DueDate]
    parent_id: Optional[str]
    description: Optional[str] = None
    labels: list = field(default_factory=list)
    duration: Optional[int] = None
    duration_unit: Optional[str] = None
    deadline: Optional[dict] = None
    assignee_id: Optional[str] = None

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "")
        self.content = kwargs.get("content", "")
        self.priority = kwargs.get("priority", 1)
        self.project_id = kwargs.get("project_id")
        due_raw = kwargs.get("due")
        self.due = DueDate(**due_raw) if due_raw else None
        self.parent_id = kwargs.get("parent_id")
        self.description = kwargs.get("description")
        self.labels = kwargs.get("labels", [])
        self.duration = kwargs.get("duration")
        self.duration_unit = kwargs.get("duration_unit")
        self.deadline = kwargs.get("deadline")
        self.assignee_id = kwargs.get("assignee_id")
