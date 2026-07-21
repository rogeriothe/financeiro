from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import BinaryIO

import fitz
from django.db.models import QuerySet
from django.utils import timezone
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from core.models import Category
from entries.models import CostCenter

from .models import Cartao, Gasto

DEFAULT_FALLBACK_LABEL = "-- definir depois --"


class InvoiceImportError(Exception):
    pass


@dataclass(frozen=True)
class ExtractedTransaction:
    data_compra: datetime
    descricao: str
    valor_total: Decimal
    categoria: str
    centro_custo: str
    parcela_atual: int
    total_parcelas: int
    observacao: str


@dataclass(frozen=True)
class InvoiceImportResult:
    imported_count: int
    ignored_count: int
    created_ids: list[int]


class GeminiInvoiceExtractor:
    def __init__(self, api_key: str):
        if not api_key:
            raise InvoiceImportError("Configure a chave do Gemini para importar a fatura.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"

    def extract_transactions(
        self,
        *,
        pdf_bytes: bytes,
        categories: list[str],
        cost_centers: list[str],
        current_year: int,
    ) -> list[ExtractedTransaction]:
        prompt = f"""
Analise esta fatura de cartão de crédito e extraia os lançamentos de compra em JSON.

Regras:
- Responda apenas JSON válido, sem markdown.
- Retorne uma lista de objetos.
- Cada objeto deve conter exatamente:
  - "date": string no formato YYYY-MM-DD
  - "description": texto da compra
  - "value": número decimal positivo
  - "category": categoria em português
  - "cost_center": centro de custo em português
  - "installment_current": número inteiro da parcela atual
  - "installment_total": número inteiro do total de parcelas
  - "observation": texto curto opcional
- Se a fatura não informar o ano da compra, infira pelo contexto da própria fatura; se ainda assim não for possível, use {current_year}.
- Se a compra for à vista, use 1 e 1 para as parcelas.
- Use estas categorias quando houver correspondência clara: {json.dumps(categories, ensure_ascii=False)}.
- Use estes centros de custo quando houver correspondência clara: {json.dumps(cost_centers, ensure_ascii=False)}.
- Se não localizar categoria ou centro de custo com segurança, retorne exatamente "{DEFAULT_FALLBACK_LABEL}".
- Ignore totais, pagamentos, encargos globais e resumos; extraia somente as linhas de compra/transação.
"""
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                types.Part.from_text(text=prompt),
            ],
        )
        raw_text = (response.text or "").replace("```json", "").replace("```", "").strip()
        if not raw_text:
            raise InvoiceImportError("O Gemini não retornou conteúdo para a fatura.")
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise InvoiceImportError("O Gemini retornou JSON inválido para a fatura.") from exc
        if isinstance(payload, dict):
            payload = [payload]
        return [self._normalize_item(item, current_year=current_year) for item in payload]

    def _normalize_item(
        self,
        item: dict[str, object],
        *,
        current_year: int,
    ) -> ExtractedTransaction:
        raw_date = str(item.get("date", "")).strip()
        if not raw_date:
            raise InvoiceImportError("Um lançamento retornado pelo Gemini veio sem data.")
        parsed_date = date.fromisoformat(raw_date)
        if parsed_date.year < 1900:
            parsed_date = parsed_date.replace(year=current_year)
        aware_datetime = timezone.make_aware(datetime.combine(parsed_date, time.min))
        value = Decimal(str(item.get("value", "0"))).copy_abs()
        parcela_atual = max(int(item.get("installment_current", 1) or 1), 1)
        total_parcelas = max(int(item.get("installment_total", 1) or 1), 1)
        if parcela_atual > total_parcelas:
            parcela_atual = total_parcelas
        return ExtractedTransaction(
            data_compra=aware_datetime,
            descricao=str(item.get("description", "")).strip(),
            valor_total=value,
            categoria=str(item.get("category", DEFAULT_FALLBACK_LABEL)).strip()
            or DEFAULT_FALLBACK_LABEL,
            centro_custo=str(item.get("cost_center", DEFAULT_FALLBACK_LABEL)).strip()
            or DEFAULT_FALLBACK_LABEL,
            parcela_atual=parcela_atual,
            total_parcelas=total_parcelas,
            observacao=str(item.get("observation", "")).strip(),
        )


class InvoiceImportService:
    def __init__(self, extractor: GeminiInvoiceExtractor | None = None):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
        self.extractor = extractor or GeminiInvoiceExtractor(api_key)

    def import_pdf(self, *, cartao: Cartao, uploaded_file: BinaryIO, filename: str) -> InvoiceImportResult:
        pdf_bytes = self._prepare_pdf(uploaded_file)
        try:
            transactions = self.extractor.extract_transactions(
                pdf_bytes=pdf_bytes,
                categories=list(
                    Category.objects.order_by("description").values_list(
                        "description",
                        flat=True,
                    )
                ),
                cost_centers=list(
                    CostCenter.objects.order_by("description").values_list(
                        "description",
                        flat=True,
                    )
                ),
                current_year=timezone.localdate().year,
            )
        except genai_errors.ServerError as exc:
            error_text = str(exc)
            if "503" in error_text and "UNAVAILABLE" in error_text:
                raise InvoiceImportError("API Gemini indisponivel, aguarde ...") from exc
            raise
        fallback_category = self._ensure_category(DEFAULT_FALLBACK_LABEL)
        fallback_cost_center = self._ensure_cost_center(DEFAULT_FALLBACK_LABEL)
        imported_count = 0
        ignored_count = 0
        created_ids: list[int] = []
        for transaction in transactions:
            if not transaction.descricao or transaction.valor_total <= 0:
                ignored_count += 1
                continue
            if self._is_duplicate(cartao=cartao, transaction=transaction):
                ignored_count += 1
                continue
            category = self._resolve_by_description(
                queryset=Category.objects.all(),
                description=transaction.categoria,
            ) or fallback_category
            cost_center = self._resolve_by_description(
                queryset=CostCenter.objects.all(),
                description=transaction.centro_custo,
            ) or fallback_cost_center
            observacao = transaction.observacao or f"Importado da fatura PDF: {filename}"
            gasto = Gasto.objects.create(
                cartao=cartao,
                categoria=category,
                cost_center=cost_center,
                data_compra=transaction.data_compra,
                descricao=transaction.descricao,
                valor_total=transaction.valor_total,
                parcela_atual=transaction.parcela_atual,
                total_parcelas=transaction.total_parcelas,
                observacao=observacao,
            )
            created_ids.append(gasto.pk)
            imported_count += 1
        return InvoiceImportResult(
            imported_count=imported_count,
            ignored_count=ignored_count,
            created_ids=created_ids,
        )

    def _prepare_pdf(self, uploaded_file: BinaryIO) -> bytes:
        pdf_bytes = uploaded_file.read()
        if not pdf_bytes:
            raise InvoiceImportError("O PDF enviado está vazio.")
        try:
            document = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:  # pragma: no cover - library-specific errors
            raise InvoiceImportError("Não foi possível abrir o PDF enviado.") from exc
        return document.tobytes()

    def _resolve_by_description(
        self,
        *,
        queryset: QuerySet,
        description: str,
    ):
        if not description:
            return None
        return queryset.filter(description__iexact=description.strip()).first()

    def _ensure_category(self, description: str) -> Category:
        category, _ = Category.objects.get_or_create(description=description)
        return category

    def _ensure_cost_center(self, description: str) -> CostCenter:
        cost_center, _ = CostCenter.objects.get_or_create(description=description)
        return cost_center

    def _is_duplicate(
        self,
        *,
        cartao: Cartao,
        transaction: ExtractedTransaction,
    ) -> bool:
        return Gasto.objects.filter(
            cartao=cartao,
            data_compra__date=transaction.data_compra.date(),
            valor_total=transaction.valor_total,
            descricao__iexact=transaction.descricao,
        ).exists()
