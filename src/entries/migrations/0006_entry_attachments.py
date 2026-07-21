from django.core.validators import FileExtensionValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("entries", "0005_move_category_to_core"),
    ]

    operations = [
        migrations.AddField(
            model_name="entry",
            name="comprovante",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="entries/comprovantes/",
                validators=[FileExtensionValidator(["pdf", "png", "jpg", "jpeg"])],
                verbose_name="Comprovante",
            ),
        ),
        migrations.AddField(
            model_name="entry",
            name="fatura",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="entries/faturas/",
                validators=[FileExtensionValidator(["pdf", "png", "jpg", "jpeg"])],
                verbose_name="Fatura",
            ),
        ),
    ]
