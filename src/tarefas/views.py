from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def tarefas_board_view(request):
    return render(request, "tarefas/tarefas_board.html")
