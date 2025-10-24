from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils import timezone


class EntryQuerySet(models.QuerySet):
    def receivables(self) -> models.QuerySet["Entry"]:
        return self.filter(original_value__gt=0)

    def payables(self) -> models.QuerySet["Entry"]:
        return self.filter(original_value__lt=0)

    def open(self) -> models.QuerySet["Entry"]:
        return self.filter(payment_date__isnull=True)

    def settled(self) -> models.QuerySet["Entry"]:
        return self.filter(payment_date__isnull=False)


class Entry(models.Model):
    description = models.CharField("Descrição", max_length=255)
    category = models.CharField("Categoria", max_length=100)
    due_date = models.DateField("Data de vencimento")
    original_value = models.DecimalField(
        "Valor original",
        max_digits=12,
        decimal_places=2,
        help_text="Use valores positivos para recebimentos e negativos para pagamentos.",
    )
    received_value = models.DecimalField(
        "Valor recebido/pago",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Preencha quando o valor for liquidado. Use o mesmo sinal do valor original.",
    )
    payment_date = models.DateField("Data de pagamento", null=True, blank=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    objects = EntryQuerySet.as_manager()

    class Meta:
        ordering = ["-due_date", "-created_at"]
        verbose_name = "lançamento"
        verbose_name_plural = "lançamentos"

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"{self.description} ({self.due_date:%d/%m/%Y})"

    @property
    def kind(self) -> str:
        return "Recebimento" if self.original_value >= 0 else "Pagamento"

    @property
    def status(self) -> str:
        return "Liquidado" if self.payment_date else "Em aberto"

    @property
    def original_value_abs(self) -> Decimal:
        return abs(self.original_value)

    @property
    def received_value_abs(self) -> Decimal:
        return abs(self.received_value or Decimal("0.00"))

    @property
    def outstanding_value(self) -> Decimal:
        received = self.received_value or Decimal("0.00")
        return self.original_value - received

    def mark_as_paid(self, amount: Decimal | None = None, date=None) -> None:
        """Helper to settle the launch programmatically."""
        self.received_value = amount if amount is not None else self.original_value
        self.payment_date = date or timezone.now().date()
        self.save(update_fields=["received_value", "payment_date", "updated_at"])
