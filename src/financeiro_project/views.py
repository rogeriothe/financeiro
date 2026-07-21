from __future__ import annotations

import json
from collections import OrderedDict
from datetime import date
from decimal import Decimal

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from entries.models import CostCenter, Entry


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    zero_index = (year * 12) + (month - 1) + offset
    return zero_index // 12, (zero_index % 12) + 1


def _dashboard_context(request: HttpRequest) -> dict[str, object]:
    today = timezone.localdate()
    monthly_buckets: OrderedDict[str, dict[str, Decimal | str]] = OrderedDict()
    for offset in range(-11, 1):
        year, month = _shift_month(today.year, today.month, offset)
        period_start = date(year, month, 1)
        label = period_start.strftime("%m/%Y")
        monthly_buckets[label] = {
            "label": label,
            "recebido": Decimal("0.00"),
            "pago": Decimal("0.00"),
        }

    selected_cost_center = request.GET.get("cost_center", "").strip()
    entries = Entry.objects.filter(
        payment_date__isnull=False,
        received_value__isnull=False,
        payment_date__gte=min(
            date(int(label.split("/")[1]), int(label.split("/")[0]), 1)
            for label in monthly_buckets
        ),
    ).select_related("cost_center")

    if selected_cost_center:
        try:
            entries = entries.filter(cost_center_id=int(selected_cost_center))
        except (TypeError, ValueError):
            selected_cost_center = ""

    for entry in entries:
        if entry.payment_date is None:
            continue
        label = entry.payment_date.strftime("%m/%Y")
        if label not in monthly_buckets:
            continue
        bucket = monthly_buckets[label]
        value = entry.received_value or Decimal("0.00")
        if value >= 0:
            bucket["recebido"] += value
        else:
            bucket["pago"] += abs(value)

    chart_labels = list(monthly_buckets.keys())
    received_data = [float(bucket["recebido"]) for bucket in monthly_buckets.values()]
    paid_data = [float(bucket["pago"]) for bucket in monthly_buckets.values()]

    total_received = sum((bucket["recebido"] for bucket in monthly_buckets.values()), Decimal("0.00"))
    total_paid = sum((bucket["pago"] for bucket in monthly_buckets.values()), Decimal("0.00"))

    return {
        "cost_centers": list(CostCenter.objects.order_by("description")),
        "selected_cost_center": selected_cost_center,
        "chart_labels_json": json.dumps(chart_labels, ensure_ascii=False),
        "received_data_json": json.dumps(received_data),
        "paid_data_json": json.dumps(paid_data),
        "chart_rows": list(monthly_buckets.values()),
        "total_received": total_received,
        "total_paid": total_paid,
    }


@login_required
def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect("login")


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    return render(request, "dashboard.html", _dashboard_context(request))
