from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


def _forwards(apps, schema_editor):
    Entry = apps.get_model("entries", "Entry")
    Category = apps.get_model("entries", "Category")

    category_map = {}
    default_category = None

    for category_name in (
        Entry.objects.values_list("category", flat=True)
        .exclude(category__isnull=True)
        .distinct()
    ):
        normalized = category_name.strip()
        if not normalized:
            continue
        category_map[normalized], _ = Category.objects.get_or_create(description=normalized)

    for entry in Entry.objects.all().only("pk", "category"):
        normalized = (entry.category or "").strip()
        if normalized:
            chosen_category = category_map[normalized]
        else:
            if default_category is None:
                default_category, _ = Category.objects.get_or_create(description="Sem categoria")
            chosen_category = default_category
        entry.category_fk_id = chosen_category.pk
        entry.save(update_fields=["category_fk"])


def _backwards(apps, schema_editor):
    Entry = apps.get_model("entries", "Entry")
    Category = apps.get_model("entries", "Category")

    categories = {category.pk: category.description for category in Category.objects.all()}
    for entry in Entry.objects.all().only("pk", "category_id"):
        entry.category = categories.get(entry.category_id, "")
        entry.save(update_fields=["category"])


class Migration(migrations.Migration):
    dependencies = [
        ("entries", "0003_costcenter_entry_cost_center"),
    ]

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
                    models.CharField(max_length=100, unique=True, verbose_name="Descrição"),
                ),
            ],
            options={
                "verbose_name": "categoria",
                "verbose_name_plural": "categorias",
                "ordering": ["description"],
            },
        ),
        migrations.AddField(
            model_name="entry",
            name="category_fk",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="entries.category",
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
            old_name="category_fk",
            new_name="category",
        ),
        migrations.AlterField(
            model_name="entry",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entries",
                to="entries.category",
                verbose_name="Categoria",
            ),
        ),
    ]
