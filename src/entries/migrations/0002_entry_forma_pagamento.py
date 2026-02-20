from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("entries", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="entry",
            name="forma_pagamento",
            field=models.CharField(
                choices=[
                    ("PIX", "PIX"),
                    ("Espécie", "Espécie"),
                    ("Crédito", "Crédito"),
                    ("Débito", "Débito"),
                ],
                default="PIX",
                max_length=20,
                verbose_name="Forma de pagamento",
            ),
        ),
    ]
