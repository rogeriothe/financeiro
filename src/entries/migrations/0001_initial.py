from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Entry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(max_length=255, verbose_name="Descrição")),
                ("category", models.CharField(max_length=100, verbose_name="Categoria")),
                ("due_date", models.DateField(verbose_name="Data de vencimento")),
                (
                    "original_value",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Use valores positivos para recebimentos e negativos para pagamentos.",
                        max_digits=12,
                        verbose_name="Valor original",
                    ),
                ),
                (
                    "received_value",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Preencha quando o valor for liquidado. Use o mesmo sinal do valor original.",
                        max_digits=12,
                        null=True,
                        verbose_name="Valor recebido/pago",
                    ),
                ),
                ("payment_date", models.DateField(blank=True, null=True, verbose_name="Data de pagamento")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
            ],
            options={
                "verbose_name": "lançamento",
                "verbose_name_plural": "lançamentos",
                "ordering": ["-due_date", "-created_at"],
            },
        ),
    ]
