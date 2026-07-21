from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


def _forwards(apps, schema_editor):
    Entry = apps.get_model("entries", "Entry")
    LegacyCategory = apps.get_model("entries", "Category")
    CoreCategory = apps.get_model("core", "Category")

    category_map = {}
    for legacy_category in LegacyCategory.objects.all().iterator():
        core_category, _ = CoreCategory.objects.get_or_create(
            description=legacy_category.description
        )
        category_map[legacy_category.pk] = core_category.pk

    for entry in Entry.objects.all().only("pk", "category_id").iterator():
        entry.core_category_id = category_map[entry.category_id]
        entry.save(update_fields=["core_category"])


def _backwards(apps, schema_editor):
    Entry = apps.get_model("entries", "Entry")
    LegacyCategory = apps.get_model("entries", "Category")
    CoreCategory = apps.get_model("core", "Category")

    category_map = {}
    for core_category in CoreCategory.objects.all().iterator():
        legacy_category, _ = LegacyCategory.objects.get_or_create(
            description=core_category.description
        )
        category_map[core_category.pk] = legacy_category.pk

    for entry in Entry.objects.all().only("pk", "core_category_id").iterator():
        entry.category_id = category_map[entry.core_category_id]
        entry.save(update_fields=["category"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("entries", "0004_category_entry_category_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="entry",
            name="core_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core.category",
                verbose_name="Categoria",
            ),
        ),
        migrations.RunPython(_forwards, _backwards),
        migrations.RemoveField(
            model_name="entry",
            name="category",
        ),
        migrations.RenameField(
            model_name="entry",
            old_name="core_category",
            new_name="category",
        ),
        migrations.AlterField(
            model_name="entry",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entries",
                to="core.category",
                verbose_name="Categoria",
            ),
        ),
        migrations.DeleteModel(
            name="Category",
        ),
    ]
