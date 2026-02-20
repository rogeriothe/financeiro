from __future__ import annotations

from decimal import Decimal

from django import forms

from .models import Entry


class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = [
            "description",
            "category",
            "cost_center",
            "forma_pagamento",
            "due_date",
            "original_value",
            "received_value",
            "payment_date",
        ]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: Mensalidade de agosto"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "forma_pagamento": forms.Select(attrs={"class": "form-select"}),
            "due_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
            "original_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "received_value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "payment_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}),
        }

    def clean_original_value(self) -> Decimal:
        original = self.cleaned_data["original_value"]
        if original == 0:
            raise forms.ValidationError("O valor original não pode ser zero.")
        return original

    def clean_received_value(self) -> Decimal | None:
        received = self.cleaned_data.get("received_value")
        if received in (None, ""):
            return None
        original = self.cleaned_data.get("original_value")
        if original is not None and received and (original > 0) != (received > 0):
            raise forms.ValidationError("Use o mesmo sinal do valor original.")
        return received

    def clean(self) -> dict[str, object]:
        cleaned = super().clean()
        payment_date = cleaned.get("payment_date")
        received_value = cleaned.get("received_value")
        if payment_date and not received_value:
            self.add_error("received_value", "Informe o valor recebido/pago ao definir a data de pagamento.")
        return cleaned
