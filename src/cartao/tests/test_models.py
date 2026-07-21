from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from cartao.models import Cartao, CompetenciaFatura, Gasto
from core.models import Category


class CartaoModelTests(TestCase):
    def setUp(self) -> None:
        self.categoria = Category.objects.create(description="Lazer")
        self.cartao = Cartao.objects.create(
            nome_apelido="Nubank",
            dia_fechamento=15,
            dia_vencimento=22,
            limite_total=Decimal("5000.00"),
        )

    def test_cartao_requires_positive_limit(self) -> None:
        invalid = Cartao(
            nome_apelido="Sem limite",
            dia_fechamento=10,
            dia_vencimento=20,
            limite_total=Decimal("0.00"),
        )
        with self.assertRaises(ValidationError):
            invalid.full_clean()

    def test_competencia_uses_same_month_before_closing(self) -> None:
        gasto = Gasto(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Cinema",
            data_compra=timezone.make_aware(datetime(2026, 1, 10, 12, 0)),
            valor_total=Decimal("300.00"),
            parcela_atual=1,
            total_parcelas=3,
        )
        self.assertEqual(gasto.competencia_inicial.label, "01/2026")
        self.assertEqual(gasto.competencia_da_parcela(2).label, "02/2026")

    def test_competencia_moves_to_next_month_after_closing(self) -> None:
        gasto = Gasto(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Passagem",
            data_compra=timezone.make_aware(datetime(2026, 1, 20, 12, 0)),
            valor_total=Decimal("600.00"),
            parcela_atual=1,
            total_parcelas=2,
        )
        self.assertEqual(gasto.competencia_inicial.label, "02/2026")
        self.assertEqual(gasto.competencia_da_parcela(2).label, "03/2026")

    def test_short_month_clamps_closing_and_due_dates(self) -> None:
        cartao = Cartao.objects.create(
            nome_apelido="Inter",
            dia_fechamento=31,
            dia_vencimento=31,
            limite_total=Decimal("3000.00"),
        )
        self.assertEqual(cartao.fechamento_para_competencia(2026, 2).day, 28)
        self.assertEqual(cartao.vencimento_para_competencia(2026, 2).day, 28)

    def test_installment_value_rounds_half_up(self) -> None:
        gasto = Gasto(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Curso",
            data_compra=timezone.now(),
            valor_total=Decimal("100.00"),
            parcela_atual=1,
            total_parcelas=3,
        )
        self.assertEqual(gasto.valor_parcela, Decimal("33.33"))

    def test_available_limit_uses_registered_spend(self) -> None:
        Gasto.objects.create(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Mercado",
            data_compra=timezone.now(),
            valor_total=Decimal("450.00"),
            parcela_atual=1,
            total_parcelas=1,
        )
        self.assertEqual(self.cartao.limite_utilizado(), Decimal("450.00"))
        self.assertEqual(self.cartao.limite_disponivel(), Decimal("4550.00"))

    def test_gasto_validates_installment_range(self) -> None:
        gasto = Gasto(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Assinatura",
            data_compra=timezone.now(),
            valor_total=Decimal("100.00"),
            parcela_atual=4,
            total_parcelas=3,
        )
        with self.assertRaises(ValidationError):
            gasto.full_clean()

    def test_fatura_uses_closing_window_and_installments(self) -> None:
        anterior = Gasto.objects.create(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Streaming",
            data_compra=timezone.make_aware(datetime(2026, 1, 14, 10, 0)),
            valor_total=Decimal("90.00"),
            parcela_atual=1,
            total_parcelas=3,
        )
        Gasto.objects.create(
            cartao=self.cartao,
            categoria=self.categoria,
            descricao="Mercado",
            data_compra=timezone.make_aware(datetime(2026, 1, 20, 10, 0)),
            valor_total=Decimal("120.00"),
            parcela_atual=1,
            total_parcelas=1,
        )

        fatura = self.cartao.fatura(2026, 2)

        self.assertEqual(fatura.data_inicio.isoformat(), "2026-01-16")
        self.assertEqual(fatura.data_fechamento.isoformat(), "2026-02-15")
        self.assertEqual(fatura.data_vencimento.isoformat(), "2026-02-22")
        self.assertEqual(fatura.total, Decimal("150.00"))
        self.assertEqual(len(fatura.itens), 2)
        self.assertEqual(fatura.itens[0].gasto, anterior)

    def test_competencia_from_label(self) -> None:
        competencia = CompetenciaFatura.from_label("03/2026")
        self.assertEqual((competencia.mes, competencia.ano), (3, 2026))
