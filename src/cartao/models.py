from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from core.models import Category
from entries.models import CostCenter

CENT = Decimal("0.01")


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _clamp_day(year: int, month: int, day: int) -> int:
    return min(day, _last_day_of_month(year, month))


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    zero_index = (year * 12) + (month - 1) + offset
    return zero_index // 12, (zero_index % 12) + 1


@dataclass(frozen=True)
class CompetenciaFatura:
    ano: int
    mes: int

    @property
    def label(self) -> str:
        return f"{self.mes:02d}/{self.ano}"

    @classmethod
    def from_label(cls, value: str) -> CompetenciaFatura:
        mes, ano = value.split("/", maxsplit=1)
        return cls(ano=int(ano), mes=int(mes))


@dataclass(frozen=True)
class ItemFatura:
    gasto: Gasto
    numero_parcela: int
    competencia: CompetenciaFatura
    valor: Decimal


@dataclass(frozen=True)
class ResumoFatura:
    cartao: Cartao
    competencia: CompetenciaFatura
    data_inicio: date
    data_fechamento: date
    data_vencimento: date
    itens: list[ItemFatura]

    @property
    def total(self) -> Decimal:
        return sum((item.valor for item in self.itens), Decimal("0.00")).quantize(CENT)


class Cartao(models.Model):
    nome_apelido = models.CharField("Nome/apelido", max_length=120, unique=True)
    dia_fechamento = models.PositiveSmallIntegerField("Dia de fechamento")
    dia_vencimento = models.PositiveSmallIntegerField("Dia de vencimento")
    limite_total = models.DecimalField("Limite total", max_digits=12, decimal_places=2)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["nome_apelido"]
        verbose_name = "cartão"
        verbose_name_plural = "cartões"

    def __str__(self) -> str:  # pragma: no cover - human readable
        return self.nome_apelido

    def clean(self) -> None:
        super().clean()
        for field_name in ("dia_fechamento", "dia_vencimento"):
            day = getattr(self, field_name)
            if not 1 <= day <= 31:
                raise ValidationError({field_name: "Informe um dia entre 1 e 31."})
        if self.limite_total <= 0:
            raise ValidationError(
                {"limite_total": "O limite total deve ser maior que zero."}
            )

    def fechamento_para_competencia(self, ano: int, mes: int) -> datetime.date:
        return datetime(
            year=ano,
            month=mes,
            day=_clamp_day(ano, mes, self.dia_fechamento),
            tzinfo=timezone.get_current_timezone(),
        ).date()

    def vencimento_para_competencia(self, ano: int, mes: int) -> datetime.date:
        return datetime(
            year=ano,
            month=mes,
            day=_clamp_day(ano, mes, self.dia_vencimento),
            tzinfo=timezone.get_current_timezone(),
        ).date()

    def janela_fatura(self, ano: int, mes: int) -> tuple[date, date]:
        fechamento_atual = self.fechamento_para_competencia(ano, mes)
        ano_anterior, mes_anterior = _shift_month(ano, mes, -1)
        fechamento_anterior = self.fechamento_para_competencia(ano_anterior, mes_anterior)
        inicio = fechamento_anterior + timedelta(days=1)
        return inicio, fechamento_atual

    def limite_utilizado(self) -> Decimal:
        total = self.gastos.aggregate(total=Sum("valor_total"))["total"] or Decimal(
            "0.00"
        )
        return total.quantize(CENT)

    def limite_disponivel(self) -> Decimal:
        available = self.limite_total - self.limite_utilizado()
        return available.quantize(CENT)

    def itens_fatura(self, ano: int, mes: int) -> list[ItemFatura]:
        competencia = CompetenciaFatura(ano=ano, mes=mes)
        itens = []
        for gasto in self.gastos.select_related("categoria").all():
            for parcela in gasto.parcelas_projetadas():
                if parcela["competencia"] == competencia.label:
                    itens.append(
                        ItemFatura(
                            gasto=gasto,
                            numero_parcela=int(parcela["parcela"]),
                            competencia=competencia,
                            valor=Decimal(str(parcela["valor"])).quantize(CENT),
                        )
                    )
        itens.sort(
            key=lambda item: (item.gasto.data_compra, item.numero_parcela, item.gasto.pk)
        )
        return itens

    def total_fatura(self, ano: int, mes: int) -> Decimal:
        return sum(
            (item.valor for item in self.itens_fatura(ano, mes)),
            Decimal("0.00"),
        ).quantize(CENT)

    def fatura(self, ano: int, mes: int) -> ResumoFatura:
        competencia = CompetenciaFatura(ano=ano, mes=mes)
        data_inicio, data_fechamento = self.janela_fatura(ano, mes)
        return ResumoFatura(
            cartao=self,
            competencia=competencia,
            data_inicio=data_inicio,
            data_fechamento=data_fechamento,
            data_vencimento=self.vencimento_para_competencia(ano, mes),
            itens=self.itens_fatura(ano, mes),
        )


class Gasto(models.Model):
    cartao = models.ForeignKey(
        Cartao,
        on_delete=models.PROTECT,
        related_name="gastos",
        verbose_name="Cartão",
    )
    categoria = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="gastos_cartao",
        verbose_name="Categoria",
    )
    cost_center = models.ForeignKey(
        CostCenter,
        on_delete=models.PROTECT,
        related_name="gastos_cartao",
        verbose_name="Centro de custo",
        null=True,
        blank=True,
    )
    data_compra = models.DateTimeField("Data da compra")
    descricao = models.CharField("Descrição", max_length=255)
    valor_total = models.DecimalField("Valor total", max_digits=12, decimal_places=2)
    parcela_atual = models.PositiveIntegerField("Parcela atual", default=1)
    total_parcelas = models.PositiveIntegerField("Total de parcelas", default=1)
    observacao = models.TextField("Observação", blank=True, default="")
    created_at = models.DateTimeField("Criado em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["-data_compra", "-created_at"]
        verbose_name = "gasto"
        verbose_name_plural = "gastos"

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"{self.descricao} ({self.cartao.nome_apelido})"

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.valor_total <= 0:
            errors["valor_total"] = "O valor total deve ser maior que zero."
        if self.total_parcelas < 1:
            errors["total_parcelas"] = "Informe ao menos uma parcela."
        if self.parcela_atual < 1:
            errors["parcela_atual"] = "A parcela atual deve ser maior ou igual a 1."
        if self.parcela_atual > self.total_parcelas:
            errors["parcela_atual"] = (
                "A parcela atual não pode ser maior que o total de parcelas."
            )
        if errors:
            raise ValidationError(errors)

    @property
    def valor_parcela(self) -> Decimal:
        return (self.valor_total / self.total_parcelas).quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )

    @property
    def competencia_inicial(self) -> CompetenciaFatura:
        purchase_date = timezone.localtime(self.data_compra).date()
        year = purchase_date.year
        month = purchase_date.month
        if purchase_date.day > self.cartao.dia_fechamento:
            year, month = _shift_month(year, month, 1)
        return CompetenciaFatura(ano=year, mes=month)

    def competencia_da_parcela(self, numero_parcela: int) -> CompetenciaFatura:
        if not 1 <= numero_parcela <= self.total_parcelas:
            raise ValueError("Parcela fora do intervalo válido.")
        base_year = self.competencia_inicial.ano
        base_month = self.competencia_inicial.mes
        target_year, target_month = _shift_month(
            base_year,
            base_month,
            numero_parcela - 1,
        )
        return CompetenciaFatura(ano=target_year, mes=target_month)

    def parcelas_projetadas(self) -> list[dict[str, Any]]:
        parcelas = []
        for parcela in range(self.parcela_atual, self.total_parcelas + 1):
            competencia = self.competencia_da_parcela(parcela)
            parcelas.append(
                {
                    "parcela": parcela,
                    "competencia": competencia.label,
                    "valor": self.valor_parcela,
                }
            )
        return parcelas

    def competencias_futuras(self) -> list[dict[str, Any]]:
        return self.parcelas_projetadas()

    @property
    def competencia_label(self) -> str:
        return self.competencia_da_parcela(self.parcela_atual).label
