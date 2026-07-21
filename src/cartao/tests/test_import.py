from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from cartao.models import Cartao, Gasto
from cartao.services import (
    DEFAULT_FALLBACK_LABEL,
    ExtractedTransaction,
    InvoiceImportService,
)
from core.models import Category
from entries.models import CostCenter


class _FakeExtractor:
    def __init__(self, transactions: list[ExtractedTransaction]):
        self.transactions = transactions

    def extract_transactions(self, **kwargs):
        return self.transactions


class InvoiceImportServiceTests(TestCase):
    def setUp(self) -> None:
        self.cartao = Cartao.objects.create(
            nome_apelido="Nubank",
            dia_fechamento=15,
            dia_vencimento=22,
            limite_total=Decimal("3000.00"),
        )

    def test_import_creates_gasto_with_fallback_category_and_cost_center(self) -> None:
        transaction = ExtractedTransaction(
            data_compra=timezone.make_aware(datetime(2026, 2, 10, 0, 0)),
            descricao="Mercado Central",
            valor_total=Decimal("120.00"),
            categoria="Categoria inexistente",
            centro_custo="Centro inexistente",
            parcela_atual=1,
            total_parcelas=1,
            observacao="Importado pelo teste",
        )
        service = InvoiceImportService(extractor=_FakeExtractor([transaction]))
        service._prepare_pdf = lambda uploaded_file: b"fake-pdf"  # type: ignore[method-assign]

        result = service.import_pdf(
            cartao=self.cartao,
            uploaded_file=SimpleUploadedFile("fatura.pdf", b"fake"),
            filename="fatura.pdf",
        )

        self.assertEqual(result.imported_count, 1)
        gasto = Gasto.objects.get(pk=result.created_ids[0])
        self.assertEqual(gasto.categoria.description, DEFAULT_FALLBACK_LABEL)
        self.assertEqual(gasto.cost_center.description, DEFAULT_FALLBACK_LABEL)
        self.assertEqual(gasto.observacao, "Importado pelo teste")

    def test_import_ignores_duplicate_gasto(self) -> None:
        categoria = Category.objects.create(description="Alimentação")
        centro = CostCenter.objects.create(description="Casa")
        data_compra = timezone.make_aware(datetime(2026, 2, 10, 0, 0))
        Gasto.objects.create(
            cartao=self.cartao,
            categoria=categoria,
            cost_center=centro,
            data_compra=data_compra,
            descricao="Mercado Central",
            valor_total=Decimal("120.00"),
            parcela_atual=1,
            total_parcelas=1,
        )
        transaction = ExtractedTransaction(
            data_compra=data_compra,
            descricao="Mercado Central",
            valor_total=Decimal("120.00"),
            categoria="Alimentação",
            centro_custo="Casa",
            parcela_atual=1,
            total_parcelas=1,
            observacao="",
        )
        service = InvoiceImportService(extractor=_FakeExtractor([transaction]))
        service._prepare_pdf = lambda uploaded_file: b"fake-pdf"  # type: ignore[method-assign]

        result = service.import_pdf(
            cartao=self.cartao,
            uploaded_file=SimpleUploadedFile("fatura.pdf", b"fake"),
            filename="fatura.pdf",
        )

        self.assertEqual(result.imported_count, 0)
        self.assertEqual(result.ignored_count, 1)
        self.assertEqual(Gasto.objects.count(), 1)
