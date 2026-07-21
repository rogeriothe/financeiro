from typing import List
from django.shortcuts import get_object_or_404
from ninja import Router
from .models import Task, TaskList
from .schemas import (
    TaskListSchema,
    TaskSchema,
    TaskCreateSchema,
    TaskUpdateSchema,
    TaskReorderSchema,
    TaskListUpdateSchema
)

router = Router()

@router.get("/lists", response=List[TaskListSchema])
def get_lists(request):
    return TaskList.objects.all().order_by("created_at")

@router.post("/lists", response=TaskListSchema)
def create_list(request, name: str):
    task_list = TaskList.objects.create(name=name)
    return task_list

@router.put("/lists/{int:list_id}", response=TaskListSchema)
def update_list(request, list_id: int, data: TaskListUpdateSchema):
    task_list = get_object_or_404(TaskList, id=list_id)
    task_list.name = data.name
    task_list.save()
    return task_list

@router.delete("/lists/{int:list_id}")
def delete_list(request, list_id: int):
    task_list = get_object_or_404(TaskList, id=list_id)
    task_list.delete()
    return {"success": True}

@router.get("/tasks", response=List[TaskSchema])
def get_tasks(request):
    return Task.objects.all()

@router.post("/tasks", response=TaskSchema)
def create_task(request, data: TaskCreateSchema):
    task_list = get_object_or_404(TaskList, id=data.task_list_id)
    # Put natural order at the bottom
    last_task = Task.objects.filter(task_list=task_list).order_by("-order").first()
    new_order = last_task.order + 1 if last_task else 0
    task = Task.objects.create(
        task_list=task_list,
        title=data.title,
        description=data.description,
        order=new_order
    )
    return task

@router.put("/tasks/{int:task_id}", response=TaskSchema)
def update_task(request, task_id: int, data: TaskUpdateSchema):
    task = get_object_or_404(Task, id=task_id)
    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.is_completed is not None:
        task.is_completed = data.is_completed
    task.save()
    return task

@router.delete("/tasks/{int:task_id}")
def delete_task(request, task_id: int):
    task = get_object_or_404(Task, id=task_id)
    task.delete()
    return {"success": True}

@router.post("/tasks/reorder")
def reorder_task(request, data: TaskReorderSchema):
    task = get_object_or_404(Task, id=data.task_id)
    new_list = get_object_or_404(TaskList, id=data.task_list_id)
    
    # Simple reorder logic: 
    # Just setting the new order. In a complex system we'd shift other task orders.
    # For now, assigning the exact new order. Wait, if multiple items have the same order,
    # the client might pass sequential orders. 
    # To keep it simple, we listen to what the client tells us is the new order.
    # But usually a client sends a full list array.
    # Let's adjust reorder logic: receive array of objects {id, order, list_id} instead.
