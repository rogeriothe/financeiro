from django.urls import path
from .views import tarefas_board_view

app_name = "tarefas"

urlpatterns = [
    path("", tarefas_board_view, name="board"),
]
