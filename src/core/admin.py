from __future__ import annotations

from django.contrib import admin

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("description",)
    search_fields = ("description",)
