from __future__ import annotations

from django.urls import path

from . import views

app_name = "cartao"

urlpatterns = [
    path("cartoes/", views.cartao_list, name="cartao_list"),
    path("cartoes/create/", views.cartao_create, name="cartao_create"),
    path("cartoes/<int:pk>/edit/", views.cartao_edit, name="cartao_edit"),
    path("cartoes/<int:pk>/delete/", views.cartao_delete, name="cartao_delete"),
    path("faturas/", views.fatura_list, name="fatura_list"),
    path("gastos/", views.gasto_list, name="gasto_list"),
    path("gastos/create/", views.gasto_create, name="gasto_create"),
    path("gastos/import/", views.gasto_import, name="gasto_import"),
    path("gastos/<int:pk>/edit/", views.gasto_edit, name="gasto_edit"),
    path("gastos/<int:pk>/delete/", views.gasto_delete, name="gasto_delete"),
]
