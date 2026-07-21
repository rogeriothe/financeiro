from __future__ import annotations

from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CategoryMigrationTests(TransactionTestCase):
    available_apps = ["core", "entries"]
    migrate_from = ("entries", "0004_category_entry_category_fk")
    migrate_to = ("entries", "0005_move_category_to_core")

    def setUp(self) -> None:
        super().setUp()
        self.executor = MigrationExecutor(connection)
        self.executor.migrate([self.migrate_from])

        Entry = self.executor.loader.project_state([self.migrate_from]).apps.get_model(
            "entries", "Entry"
        )
        Category = self.executor.loader.project_state([self.migrate_from]).apps.get_model(
            "entries", "Category"
        )
        category = Category.objects.create(description="Serviços")
        Entry.objects.create(
            description="Internet",
            category_id=category.pk,
            due_date="2026-02-10",
            original_value=Decimal("-120.00"),
        )

    def test_category_data_is_moved_to_core(self) -> None:
        self.executor.loader.build_graph()
        self.executor.migrate([self.migrate_to])
        apps = self.executor.loader.project_state([self.migrate_to]).apps
        Entry = apps.get_model("entries", "Entry")
        Category = apps.get_model("core", "Category")

        category = Category.objects.get(description="Serviços")
        entry = Entry.objects.get(description="Internet")

        self.assertEqual(entry.category_id, category.pk)
