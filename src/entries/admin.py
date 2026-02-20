from __future__ import annotations

from django.contrib import admin

from .models import Category, CostCenter, Entry


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("description",)
    search_fields = ("description",)


@admin.register(CostCenter)
class CostCenterAdmin(admin.ModelAdmin):
    list_display = ("description",)
    search_fields = ("description",)


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "category",
        "cost_center",
        "due_date",
        "original_value",
        "received_value",
        "payment_date",
    )
    list_filter = ("category", "cost_center", "payment_date")
    search_fields = ("description", "category__description", "cost_center__description")
