from __future__ import annotations

from django import forms

from .models import Cartao, Gasto


class CartaoForm(forms.ModelForm):
    class Meta:
        model = Cartao
        fields = ["nome_apelido", "dia_fechamento", "dia_vencimento", "limite_total"]
        widgets = {
            "nome_apelido": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Nubank"}
            ),
            "dia_fechamento": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "31"}
            ),
            "dia_vencimento": forms.NumberInput(
                attrs={"class": "form-control", "min": "1", "max": "31"}
            ),
            "limite_total": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
        }


class GastoForm(forms.ModelForm):
    class Meta:
        model = Gasto
        fields = [
            "cartao",
            "categoria",
            "cost_center",
            "data_compra",
            "descricao",
            "valor_total",
            "parcela_atual",
            "total_parcelas",
            "observacao",
        ]
        widgets = {
            "cartao": forms.Select(attrs={"class": "form-select"}),
            "categoria": forms.Select(attrs={"class": "form-select"}),
            "cost_center": forms.Select(attrs={"class": "form-select"}),
            "data_compra": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M",
                attrs={"type": "datetime-local", "class": "form-control"},
            ),
            "descricao": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex.: Mercado"}
            ),
            "valor_total": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0.01"}
            ),
            "parcela_atual": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "total_parcelas": forms.NumberInput(
                attrs={"class": "form-control", "min": "1"}
            ),
            "observacao": forms.Textarea(
                attrs={"class": "form-control", "rows": "3"}
            ),
        }


class FaturaImportForm(forms.Form):
    cartao = forms.ModelChoiceField(
        queryset=Cartao.objects.order_by("nome_apelido"),
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Cartão",
    )
    pdf_file = forms.FileField(
        label="PDF da fatura",
        widget=forms.FileInput(attrs={"class": "form-control", "accept": "application/pdf"}),
    )

    def clean_pdf_file(self):
        pdf_file = self.cleaned_data["pdf_file"]
        if not pdf_file.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Envie um arquivo PDF.")
        return pdf_file
