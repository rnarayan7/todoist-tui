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
class Task:
    id: str
    content: str
    priority: int
    project_id: Optional[str]
    due: Optional[DueDate]
    parent_id: Optional[str]

    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "")
        self.content = kwargs.get("content", "")
        self.priority = kwargs.get("priority", 1)
        self.project_id = kwargs.get("project_id")
        due_raw = kwargs.get("due")
        self.due = DueDate(**due_raw) if due_raw else None
        self.parent_id = kwargs.get("parent_id")
