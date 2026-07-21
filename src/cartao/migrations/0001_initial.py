from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Cartao",
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
                ("nome_apelido", models.CharField(max_length=120, unique=True, verbose_name="Nome/apelido")),
                ("dia_fechamento", models.PositiveSmallIntegerField(verbose_name="Dia de fechamento")),
                ("dia_vencimento", models.PositiveSmallIntegerField(verbose_name="Dia de vencimento")),
                ("limite_total", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Limite total")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
            ],
            options={
                "ordering": ["nome_apelido"],
                "verbose_name": "cartão",
                "verbose_name_plural": "cartões",
            },
        ),
        migrations.CreateModel(
            name="Gasto",
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
                ("data_compra", models.DateTimeField(verbose_name="Data da compra")),
                ("descricao", models.CharField(max_length=255, verbose_name="Descrição")),
                ("valor_total", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="Valor total")),
                ("parcela_atual", models.PositiveIntegerField(default=1, verbose_name="Parcela atual")),
                ("total_parcelas", models.PositiveIntegerField(default=1, verbose_name="Total de parcelas")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                (
                    "cartao",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="gastos",
                        to="cartao.cartao",
                        verbose_name="Cartão",
                    ),
                ),
                (
                    "categoria",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="gastos_cartao",
                        to="core.category",
                        verbose_name="Categoria",
                    ),
                ),
            ],
            options={
                "ordering": ["-data_compra", "-created_at"],
                "verbose_name": "gasto",
                "verbose_name_plural": "gastos",
            },
        ),
    ]
