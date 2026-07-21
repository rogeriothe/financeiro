from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        max_length=100,
                        unique=True,
                        verbose_name="Descrição",
                    ),
                ),
            ],
            options={
                "ordering": ["description"],
                "verbose_name": "categoria",
                "verbose_name_plural": "categorias",
            },
        ),
    ]
