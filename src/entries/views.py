from __future__ import annotations

from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, F, IntegerField, Q, Sum, Value, When
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .forms import EntryForm
from .models import CostCenter, Entry

DEFAULT_SORT_BY = "payment_date"
DEFAULT_SORT_DIRECTION = "desc"
SORTABLE_COLUMNS = {
    "description",
    "category",
    "cost_center",
    "kind",
    "original_value",
    "received_value",
    "due_date",
    "payment_date",
    "status",
}


def _build_querystring(**params: Any) -> str:
    clean_params = {key: value for key, value in params.items() if value not in ("", None)}
    return urlencode(clean_params)


def _normalize_sort(request: HttpRequest | None) -> tuple[str, str]:
    if not request:
        return DEFAULT_SORT_BY, DEFAULT_SORT_DIRECTION
    sort_by = request.GET.get("sort", DEFAULT_SORT_BY)
    sort_direction = request.GET.get("dir", DEFAULT_SORT_DIRECTION)
    if sort_by not in SORTABLE_COLUMNS:
        sort_by = DEFAULT_SORT_BY
    if sort_direction not in {"asc", "desc"}:
        sort_direction = DEFAULT_SORT_DIRECTION
    return sort_by, sort_direction


def _column_order(sort_by: str, sort_direction: str) -> tuple[list[Any], bool]:
    descending = sort_direction == "desc"
    if sort_by == "payment_date":
        return [F("payment_date").desc(nulls_last=True) if descending else F("payment_date").asc(nulls_last=True)], descending
    if sort_by == "received_value":
        return [F("received_value").desc(nulls_last=True) if descending else F("received_value").asc(nulls_last=True)], descending
    if sort_by == "cost_center":
        return [
            F("cost_center__description").desc(nulls_last=True)
            if descending
            else F("cost_center__description").asc(nulls_last=True)
        ], descending
    if sort_by == "category":
        return [
            F("category__description").desc(nulls_last=True)
            if descending
            else F("category__description").asc(nulls_last=True)
        ], descending
    if sort_by == "kind":
        return ["-kind_sort" if descending else "kind_sort"], descending
    if sort_by == "status":
        return ["-status_sort" if descending else "status_sort"], descending
    field = f"-{sort_by}" if descending else sort_by
    return [field], descending


def _totals_context(entries_queryset=None) -> dict[str, Decimal]:
    def _safe_sum(queryset, field: str) -> Decimal:
        return queryset.aggregate(total=Sum(field))["total"] or Decimal("0.00")

    filtered_entries = entries_queryset if entries_queryset is not None else Entry.objects.all()
    receivables_total = _safe_sum(filtered_entries.receivables(), "original_value")
    payables_total = abs(_safe_sum(filtered_entries.payables(), "original_value"))
    result_total = _safe_sum(filtered_entries.settled(), "received_value")
    receivables_received_total = _safe_sum(filtered_entries.receivables(), "received_value")
    outstanding_total = receivables_total - receivables_received_total
    if outstanding_total < 0:
        outstanding_total = Decimal("0.00")

    return {
        "receivables_total": receivables_total,
        "payables_total": payables_total,
        "result_total": result_total,
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
    selected_cost_center = ""
    page_number = 1
    sort_by = DEFAULT_SORT_BY
    sort_direction = DEFAULT_SORT_DIRECTION
    if request:
        search_query = request.GET.get("q", "").strip()
        selected_cost_center = request.GET.get("cost_center", "").strip()
        try:
            page_number = int(request.GET.get("page", 1))
        except (TypeError, ValueError):
            page_number = 1
        sort_by, sort_direction = _normalize_sort(request)
    entries_queryset = Entry.objects.select_related("category", "cost_center").annotate(
        kind_sort=Case(
            When(original_value__lt=0, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        status_sort=Case(
            When(payment_date__isnull=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    )
    if search_query:
        entries_queryset = entries_queryset.filter(
            Q(description__icontains=search_query)
            | Q(category__description__icontains=search_query)
            | Q(cost_center__description__icontains=search_query)
        )
    if selected_cost_center:
        try:
            entries_queryset = entries_queryset.filter(cost_center_id=int(selected_cost_center))
        except (TypeError, ValueError):
            selected_cost_center = ""
    order_by_fields, descending = _column_order(sort_by, sort_direction)
    entries_queryset = entries_queryset.order_by(*order_by_fields, "-created_at")
    paginator = Paginator(entries_queryset, 10)
    page_obj = paginator.get_page(page_number)
    total_pages = paginator.num_pages
    current_page = page_obj.number
    start_page = max(1, current_page - 3)
    end_page = min(total_pages, current_page + 3)
    page_numbers = list(range(start_page, end_page + 1))
    cost_centers = CostCenter.objects.order_by("description")
    sort_links = {}
    for column in SORTABLE_COLUMNS:
        next_direction = "desc" if sort_by == column and not descending else "asc"
        sort_links[column] = _build_querystring(
            q=search_query,
            cost_center=selected_cost_center,
            sort=column,
            dir=next_direction,
            page=1,
        )

    pagination_links = {
        "first": _build_querystring(
            q=search_query,
            cost_center=selected_cost_center,
            sort=sort_by,
            dir=sort_direction,
            page=1,
        ),
        "previous": _build_querystring(
            q=search_query,
            cost_center=selected_cost_center,
            sort=sort_by,
            dir=sort_direction,
            page=page_obj.previous_page_number() if page_obj.has_previous() else 1,
        ),
        "next": _build_querystring(
            q=search_query,
            cost_center=selected_cost_center,
            sort=sort_by,
            dir=sort_direction,
            page=page_obj.next_page_number() if page_obj.has_next() else page_obj.paginator.num_pages,
        ),
        "last": _build_querystring(
            q=search_query,
            cost_center=selected_cost_center,
            sort=sort_by,
            dir=sort_direction,
            page=page_obj.paginator.num_pages,
        ),
        "pages": [
            (
                number,
                _build_querystring(
                    q=search_query,
                    cost_center=selected_cost_center,
                    sort=sort_by,
                    dir=sort_direction,
                    page=number,
                ),
            )
            for number in page_numbers
        ],
    }
    return {
        "form": form,
        "entries": list(page_obj.object_list),
        "page_obj": page_obj,
        "paginator": paginator,
        "page_numbers": page_numbers,
        "search_query": search_query,
        "selected_cost_center": selected_cost_center,
        "cost_centers": list(cost_centers),
        "editing_entry": editing_entry,
        "form_action": form_action,
        "form_visible": form_visible,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "sort_links": sort_links,
        "pagination_links": pagination_links,
        **_totals_context(entries_queryset),
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
