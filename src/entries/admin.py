from __future__ import annotations

from django.contrib import admin

from .models import Entry


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "category",
        "due_date",
        "original_value",
        "received_value",
        "payment_date",
    )
    list_filter = ("category", "payment_date")
    search_fields = ("description", "category")
