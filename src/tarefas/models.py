from django.db import models
from django.utils import timezone

class TaskList(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class Task(models.Model):
    task_list = models.ForeignKey(TaskList, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["order", "-created_at"]

    def __str__(self):
        return self.title
