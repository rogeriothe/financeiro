from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Category
from entries.forms import EntryForm
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


class EntryFormTests(TestCase):
    def setUp(self) -> None:
        self.category = Category.objects.create(description="Serviços")
        self.form_data = {
            "description": "Internet",
            "category": self.category.pk,
            "forma_pagamento": "PIX",
            "due_date": date(2026, 7, 31),
            "tipo_lancamento": EntryForm.PAY,
            "original_value": Decimal("100.00"),
        }

    def test_attachments_are_optional_and_payment_gets_negative_sign(self) -> None:
        form = EntryForm(data=self.form_data)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().original_value, Decimal("-100.00"))

    def test_receive_keeps_values_positive(self) -> None:
        data = {
            **self.form_data,
            "tipo_lancamento": EntryForm.RECEIVE,
            "received_value": Decimal("75.00"),
        }

        form = EntryForm(data=data)

        self.assertTrue(form.is_valid(), form.errors)
        entry = form.save()
        self.assertEqual(entry.original_value, Decimal("100.00"))
        self.assertEqual(entry.received_value, Decimal("75.00"))

    def test_edit_displays_payment_values_without_sign(self) -> None:
        entry = Entry.objects.create(
            description="Internet",
            category=self.category,
            due_date=date(2026, 7, 31),
            original_value=Decimal("-100.00"),
            received_value=Decimal("-75.00"),
        )

        form = EntryForm(instance=entry)

        self.assertEqual(form.initial["tipo_lancamento"], EntryForm.PAY)
        self.assertEqual(form.initial["original_value"], Decimal("100.00"))
        self.assertEqual(form.initial["received_value"], Decimal("75.00"))

    def test_accepts_pdf_and_jpg_attachments(self) -> None:
        files = {
            "fatura": SimpleUploadedFile(
                "fatura.pdf",
                b"%PDF-1.7\n",
                content_type="application/pdf",
            ),
            "comprovante": SimpleUploadedFile(
                "comprovante.jpg",
                b"\xff\xd8\xff\xe0imagem",
                content_type="image/jpeg",
            ),
        }

        form = EntryForm(data=self.form_data, files=files)

        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_file_with_disguised_extension(self) -> None:
        files = {
            "fatura": SimpleUploadedFile(
                "fatura.pdf",
                b"arquivo de texto",
                content_type="application/pdf",
            )
        }

        form = EntryForm(data=self.form_data, files=files)

        self.assertFalse(form.is_valid())
        self.assertIn("fatura", form.errors)


class EntryAttachmentViewTests(TestCase):
    def setUp(self) -> None:
        self.media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_directory.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        media_override.enable()
        self.addCleanup(media_override.disable)

        user = get_user_model().objects.create_user(
            username="financeiro",
            password="senha-forte-123",
        )
        self.client.force_login(user)
        self.category = Category.objects.create(description="Serviços")

    def test_create_entry_with_attachments(self) -> None:
        response = self.client.post(
            reverse("entries:create"),
            {
                "description": "Internet",
                "category": self.category.pk,
                "forma_pagamento": "PIX",
                "due_date": "2026-07-31",
                "tipo_lancamento": EntryForm.PAY,
                "original_value": "100.00",
                "fatura": SimpleUploadedFile(
                    "fatura.pdf",
                    b"%PDF-1.7\n",
                    content_type="application/pdf",
                ),
                "comprovante": SimpleUploadedFile(
                    "comprovante.png",
                    b"\x89PNG\r\n\x1a\nimagem",
                    content_type="image/png",
                ),
            },
        )

        self.assertRedirects(
            response,
            reverse("entries:list"),
            fetch_redirect_response=False,
        )
        entry = Entry.objects.get()
        self.assertEqual(entry.original_value, Decimal("-100.00"))
        self.assertTrue(entry.fatura.name.startswith("entries/faturas/"))
        self.assertTrue(entry.comprovante.name.startswith("entries/comprovantes/"))
