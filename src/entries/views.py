from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import EntryForm
from .models import Entry


def _totals_context() -> dict[str, Decimal]:
    def _safe_total(queryset) -> Decimal:
        return queryset.aggregate(total=Sum("original_value"))["total"] or Decimal("0.00")

    receivables_total = _safe_total(Entry.objects.receivables())
    payables_total = abs(_safe_total(Entry.objects.payables()))
    settled_total = abs(
        (
            Entry.objects.filter(payment_date__isnull=False).aggregate(total=Sum("received_value"))["total"]
            or Decimal("0.00")
        )
    )
    totals = Entry.objects.aggregate(
        original_total=Sum("original_value"),
        received_total=Sum("received_value"),
    )
    original_total = totals["original_total"] or Decimal("0.00")
    received_total = totals["received_total"] or Decimal("0.00")
    outstanding_total = original_total - received_total

    return {
        "receivables_total": receivables_total,
        "payables_total": payables_total,
        "settled_total": settled_total,
        "outstanding_total": outstanding_total,
    }


def _entries_page_context(
    request: HttpRequest | None = None,
    *,
    form: EntryForm | None = None,
    editing_entry: Entry | None = None,
) -> dict[str, Any]:
    if form is None:
        form = EntryForm(instance=editing_entry) if editing_entry else EntryForm()
    form_action = (
        reverse("entries:create")
        if editing_entry is None
        else reverse("entries:edit", args=[editing_entry.pk])
    )
    form_visible = editing_entry is not None or (form is not None and form.is_bound)
    search_query = ""
    page_number = 1
    if request:
        search_query = request.GET.get("q", "").strip()
        try:
            page_number = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            page_number = 1
    entries_queryset = Entry.objects.all()
    if search_query:
        entries_queryset = entries_queryset.filter(Q(description__icontains=search_query))
    entries_queryset = entries_queryset.order_by("payment_date", "description")
    paginator = Paginator(entries_queryset, 10)
    page_obj = paginator.get_page(page_number)
    return {
        "form": form,
        "entries": list(page_obj.object_list),
        "page_obj": page_obj,
        "paginator": paginator,
        "search_query": search_query,
        "editing_entry": editing_entry,
        "form_action": form_action,
        "form_visible": form_visible,
        **_totals_context(),
    }


@login_required
@require_GET
def entry_list(request: HttpRequest) -> HttpResponse:
    return render(request, "entries/entry_list.html", _entries_page_context(request))


@login_required
@require_GET
def entry_summary(request: HttpRequest) -> HttpResponse:
    return render(request, "entries/partials/entry_summary.html", _totals_context())


@login_required
@require_POST
def entry_create(request: HttpRequest) -> HttpResponse:
    form = EntryForm(request.POST)
    if form.is_valid():
        entry = form.save()
        messages.success(request, f"Lançamento '{entry.description}' criado com sucesso.")
        return redirect("entries:list")

    messages.error(request, "Corrija os erros antes de salvar.")
    return render(
        request,
        "entries/entry_list.html",
        _entries_page_context(request, form=form),
        status=400,
    )


@login_required
@require_http_methods(["GET", "POST"])
def entry_edit(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(Entry, pk=pk)
    if request.method == "POST":
        form = EntryForm(request.POST, instance=entry)
        if form.is_valid():
            entry = form.save()
            messages.success(request, f"Lançamento '{entry.description}' atualizado.")
            return redirect("entries:list")
        messages.error(request, "Corrija os erros antes de salvar.")
        return render(
            request,
            "entries/entry_list.html",
            _entries_page_context(request, form=form, editing_entry=entry),
            status=400,
        )

    return render(
        request,
        "entries/entry_list.html",
        _entries_page_context(request, editing_entry=entry),
    )


@login_required
@require_POST
def entry_delete(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(Entry, pk=pk)
    entry.delete()
    messages.success(request, "Lançamento removido.")
    return redirect("entries:list")


@login_required
@require_POST
def entry_clone(request: HttpRequest, pk: int) -> HttpResponse:
    entry = get_object_or_404(Entry, pk=pk)
    # Preserve all user-provided fields while letting auto fields regenerate.
    excluded_fields = {Entry._meta.pk.attname, Entry._meta.pk.name, "created_at", "updated_at"}
    clone_data = {
        field.name: getattr(entry, field.name)
        for field in Entry._meta.fields
        if field.name not in excluded_fields
    }
    cloned_entry = Entry.objects.create(**clone_data)
    messages.success(request, f"Lançamento '{entry.description}' clonado com sucesso.")
    return redirect("entries:edit", cloned_entry.pk)
