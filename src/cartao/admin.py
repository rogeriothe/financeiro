from __future__ import annotations

from django.contrib import admin

from .models import Cartao, Gasto


@admin.register(Cartao)
class CartaoAdmin(admin.ModelAdmin):
    list_display = (
        "nome_apelido",
        "dia_fechamento",
        "dia_vencimento",
        "limite_total",
    )
    search_fields = ("nome_apelido",)


@admin.register(Gasto)
class GastoAdmin(admin.ModelAdmin):
    list_display = (
        "descricao",
        "cartao",
        "categoria",
        "cost_center",
        "data_compra",
        "valor_total",
        "parcela_atual",
        "total_parcelas",
    )
    list_filter = ("cartao", "categoria", "cost_center", "data_compra")
    search_fields = (
        "descricao",
        "cartao__nome_apelido",
        "categoria__description",
        "cost_center__description",
        "observacao",
    )
