from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("entries", "0002_entry_forma_pagamento"),
    ]

    operations = [
        migrations.CreateModel(
            name="CostCenter",
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
                ("description", models.CharField(max_length=255, unique=True, verbose_name="Descrição")),
            ],
            options={
                "verbose_name": "centro de custo",
                "verbose_name_plural": "centros de custo",
                "ordering": ["description"],
            },
        ),
        migrations.AddField(
            model_name="entry",
            name="cost_center",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entries",
                to="entries.costcenter",
                verbose_name="Centro de custo",
            ),
        ),
    ]
