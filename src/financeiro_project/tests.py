from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Category
from entries.models import CostCenter, Entry


@override_settings(
    STORAGES={
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class DashboardViewTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="dashboard",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        self.category = Category.objects.create(description="Serviços")
        self.center_a = CostCenter.objects.create(description="Operação")
        self.center_b = CostCenter.objects.create(description="Marketing")
        Entry.objects.create(
            description="Recebimento janeiro",
            category=self.category,
            cost_center=self.center_a,
            due_date=date(2026, 1, 10),
            original_value=Decimal("500.00"),
            received_value=Decimal("500.00"),
            payment_date=date(2026, 1, 12),
        )
        Entry.objects.create(
            description="Pagamento janeiro",
            category=self.category,
            cost_center=self.center_a,
            due_date=date(2026, 1, 11),
            original_value=Decimal("-120.00"),
            received_value=Decimal("-120.00"),
            payment_date=date(2026, 1, 14),
        )
        Entry.objects.create(
            description="Pagamento outro centro",
            category=self.category,
            cost_center=self.center_b,
            due_date=date(2026, 1, 15),
            original_value=Decimal("-80.00"),
            received_value=Decimal("-80.00"),
            payment_date=date(2026, 1, 16),
        )

    def test_dashboard_renders_home(self) -> None:
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard financeiro")
        self.assertContains(response, "Recebido x pago mês a mês")

    def test_dashboard_filters_by_cost_center(self) -> None:
        response = self.client.get(
            reverse("dashboard"),
            {"cost_center": self.center_a.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "500.0")
        self.assertContains(response, "120.0")
        self.assertNotContains(response, "80.0")
