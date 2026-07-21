from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("entries", "0005_move_category_to_core"),
        ("cartao", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="gasto",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="gastos_cartao",
                to="entries.costcenter",
                verbose_name="Centro de custo",
            ),
        ),
        migrations.AddField(
            model_name="gasto",
            name="observacao",
            field=models.TextField(
                blank=True,
                default="",
                verbose_name="Observação",
            ),
        ),
    ]
