from __future__ import annotations

from django.db import models


class Category(models.Model):
    description = models.CharField("Descrição", max_length=100, unique=True)

    class Meta:
        ordering = ["description"]
        verbose_name = "categoria"
        verbose_name_plural = "categorias"

    def __str__(self) -> str:  # pragma: no cover - human readable
        return self.description
