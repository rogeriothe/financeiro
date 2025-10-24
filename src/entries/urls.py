from __future__ import annotations

from django.urls import path

from . import views

app_name = "entries"

urlpatterns = [
    path("", views.entry_list, name="list"),
    path("summary/", views.entry_summary, name="summary"),
    path("create/", views.entry_create, name="create"),
    path("<int:pk>/edit/", views.entry_edit, name="edit"),
    path("<int:pk>/clone/", views.entry_clone, name="clone"),
    path("<int:pk>/delete/", views.entry_delete, name="delete"),
]
