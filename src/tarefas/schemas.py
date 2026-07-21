from typing import List, Optional
from ninja import Schema, ModelSchema
from .models import Task, TaskList

class TaskListSchema(ModelSchema):
    class Meta:
        model = TaskList
        fields = ["id", "name"]

class TaskSchema(ModelSchema):
    class Meta:
        model = Task
        fields = ["id", "task_list", "title", "description", "is_completed", "order"]

class TaskListUpdateSchema(Schema):
    name: str

class TaskCreateSchema(Schema):
    task_list_id: int
    title: str
    description: str = ""

class TaskUpdateSchema(Schema):
    title: Optional[str] = None
    description: Optional[str] = None
    is_completed: Optional[bool] = None

class TaskReorderSchema(Schema):
    task_list_id: int
    task_id: int
    new_order: int
