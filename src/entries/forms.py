from __future__ import annotations

from decimal import Decimal

from django import forms
from django.core.files.uploadedfile import UploadedFile

from .models import Entry


class EntryForm(forms.ModelForm):
    PAY = "pagar"
    RECEIVE = "receber"
    tipo_lancamento = forms.ChoiceField(
        label="Tipo de lançamento",
        choices=((PAY, "Pagar"), (RECEIVE, "Receber")),
        initial=PAY,
        widget=forms.RadioSelect(attrs={"class": "btn-check"}),
    )
    attachment_signatures = {
        ".pdf": (b"%PDF-",),
        ".png": (b"\x89PNG\r\n\x1a\n",),
        ".jpg": (b"\xff\xd8\xff",),
        ".jpeg": (b"\xff\xd8\xff",),
    }

    class Meta:
        model = Entry
        fields = [
            "description",
            "category",
            "cost_center",
            "forma_pagamento",
            "due_date",
            "tipo_lancamento",
            "original_value",
            "received_value",
            "payment_date",
            "fatura",
            "comprovante",
        ]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Mensalidade de agosto"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "forma_pagamento": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "original_value": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "received_value": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "payment_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "fatura": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg",
                }
            ),
            "comprovante": forms.ClearableFileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg",
                }
            ),
        }
        help_texts = {
            "original_value": "Informe o valor sem sinal; o tipo define pagar ou receber.",
            "received_value": "Opcional. Informe o valor sem sinal.",
            "fatura": "Opcional. Formatos aceitos: PDF, PNG ou JPG.",
            "comprovante": "Opcional. Formatos aceitos: PDF, PNG ou JPG.",
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if self.is_bound or not self.instance or not self.instance.pk:
            return

        self.initial["tipo_lancamento"] = (
            self.RECEIVE if self.instance.original_value >= 0 else self.PAY
        )
        self.initial["original_value"] = abs(self.instance.original_value)
        if self.instance.received_value is not None:
            self.initial["received_value"] = abs(self.instance.received_value)

    def _clean_attachment(self, field_name: str):
        attachment = self.cleaned_data.get(field_name)
        if not isinstance(attachment, UploadedFile):
            return attachment

        extension = f".{attachment.name.rsplit('.', 1)[-1].lower()}"
        signatures = self.attachment_signatures.get(extension, ())
        header = attachment.read(8)
        attachment.seek(0)
        if not signatures or not any(header.startswith(value) for value in signatures):
            raise forms.ValidationError("Envie um arquivo PDF, PNG ou JPG válido.")
        return attachment

    def clean_fatura(self):
        return self._clean_attachment("fatura")

    def clean_comprovante(self):
        return self._clean_attachment("comprovante")

    def clean_original_value(self) -> Decimal:
        original = self.cleaned_data["original_value"]
        if original == 0:
            raise forms.ValidationError("O valor original não pode ser zero.")
        return abs(original)

    def clean_received_value(self) -> Decimal | None:
        received = self.cleaned_data.get("received_value")
        if received in (None, ""):
            return None
        return abs(received)

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        payment_date = cleaned.get("payment_date")
        received_value = cleaned.get("received_value")
        if payment_date and not received_value:
            self.add_error("received_value", "Informe o valor recebido/pago ao definir a data de pagamento.")

        multiplier = -1 if cleaned.get("tipo_lancamento") == self.PAY else 1
        original_value = cleaned.get("original_value")
        if original_value is not None:
            cleaned["original_value"] = original_value * multiplier
        if received_value is not None:
            cleaned["received_value"] = received_value * multiplier
        return cleaned
