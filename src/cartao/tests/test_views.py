from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cartao.models import Cartao, Gasto
from core.models import Category


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
class FaturaViewTests(TestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="senha-forte-123",
        )
        self.client.force_login(self.user)
        self.categoria = Category.objects.create(description="Transporte")
        self.cartao = Cartao.objects.create(
            nome_apelido="Inter",
            dia_fechamento=15,
            dia_vencimento=22,
            limite_total=Decimal("4000.00"),
        )
        Gasto.objects.create(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Uber",
            data_compra=timezone.make_aware(datetime(2026, 1, 20, 9, 0)),
            valor_total=Decimal("60.00"),
            parcela_atual=1,
            total_parcelas=2,
        )

    def test_fatura_view_renders_total_for_selected_competencia(self) -> None:
        response = self.client.get(
            reverse("cartao:fatura_list"),
            {"cartao": self.cartao.pk, "competencia": "02/2026"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Uber")
        self.assertContains(response, "02/2026")
        self.assertContains(response, "30,00")
