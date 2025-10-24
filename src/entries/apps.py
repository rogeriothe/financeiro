from __future__ import annotations

from django.apps import AppConfig


class EntriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "entries"
    verbose_name = "Lançamentos financeiros"
