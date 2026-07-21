from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from core.models import Category

from .forms import CartaoForm, FaturaImportForm, GastoForm
from .models import Cartao, CompetenciaFatura, Gasto
from .services import InvoiceImportError, InvoiceImportService

DEFAULT_SORT_BY = "data_compra"
DEFAULT_SORT_DIRECTION = "desc"
SORTABLE_COLUMNS = {
    "data_compra",
    "descricao",
    "cartao",
    "categoria",
    "cost_center",
    "competencia",
    "parcela_atual",
    "valor_total",
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


def _column_order(sort_by: str, sort_direction: str) -> tuple[list[str], bool]:
    descending = sort_direction == "desc"
    if sort_by == "cartao":
        return [
            F("cartao__nome_apelido").desc(nulls_last=True)
            if descending
            else F("cartao__nome_apelido").asc(nulls_last=True)
        ], descending
    if sort_by == "categoria":
        return [
            F("categoria__description").desc(nulls_last=True)
            if descending
            else F("categoria__description").asc(nulls_last=True)
        ], descending
    if sort_by == "cost_center":
        return [
            F("cost_center__description").desc(nulls_last=True)
            if descending
            else F("cost_center__description").asc(nulls_last=True)
        ], descending
    field = f"-{sort_by}" if descending else sort_by
    return [field], descending


def _competencias_disponiveis() -> list[str]:
    return sorted(
        {
            item["competencia"]
            for gasto in Gasto.objects.select_related("cartao").all()
            for item in gasto.parcelas_projetadas()
        }
    )


def _competencia_padrao() -> str:
    return timezone.localdate().strftime("%m/%Y")


def _cartao_context(form: CartaoForm | None = None, editing_cartao: Cartao | None = None) -> dict[str, Any]:
    if form is None:
        form = CartaoForm(instance=editing_cartao) if editing_cartao else CartaoForm()
    cartoes = list(Cartao.objects.all())
    return {
        "form": form,
        "cartoes": cartoes,
        "editing_cartao": editing_cartao,
        "form_action": reverse("cartao:cartao_create")
        if editing_cartao is None
        else reverse("cartao:cartao_edit", args=[editing_cartao.pk]),
    }


def _gasto_context(
    request: HttpRequest | None = None,
    *,
    form: GastoForm | None = None,
    editing_gasto: Gasto | None = None,
) -> dict[str, Any]:
    if form is None:
        form = GastoForm(instance=editing_gasto) if editing_gasto else GastoForm()
    import_form = FaturaImportForm()
    form_visible = editing_gasto is not None or (form is not None and form.is_bound)

    search_query = ""
    selected_cartao = ""
    selected_categoria = ""
    selected_competencia = ""
    sort_by = DEFAULT_SORT_BY
    sort_direction = DEFAULT_SORT_DIRECTION
    if request:
        search_query = request.GET.get("q", "").strip()
        selected_cartao = request.GET.get("cartao", "").strip()
        selected_categoria = request.GET.get("categoria", "").strip()
        selected_competencia = request.GET.get("competencia", "").strip()
        sort_by, sort_direction = _normalize_sort(request)

    gastos_queryset = Gasto.objects.select_related("cartao", "categoria", "cost_center").all()

    if search_query:
        gastos_queryset = gastos_queryset.filter(
            Q(descricao__icontains=search_query)
            | Q(categoria__description__icontains=search_query)
            | Q(cost_center__description__icontains=search_query)
        )
    if selected_cartao:
        gastos_queryset = gastos_queryset.filter(cartao_id=selected_cartao)
    if selected_categoria:
        gastos_queryset = gastos_queryset.filter(categoria_id=selected_categoria)
    if selected_competencia:
        # Filtrar gastos cuja parcela atual ou futuras incluem a competência
        gastos_list = list(gastos_queryset)
        gastos_list = [
            gasto
            for gasto in gastos_list
            if any(
                item["competencia"] == selected_competencia
                for item in gasto.competencias_futuras()
            )
        ]
        # Aplicar ordenação na lista
        if sort_by == "competencia":
            reverse_order = sort_direction == "desc"
            gastos_list.sort(key=lambda g: g.competencia_label, reverse=reverse_order)
        elif sort_by in ["cartao", "categoria", "cost_center"]:
            # Para campos relacionados, ordenar por string
            reverse_order = sort_direction == "desc"
            key_func = {
                "cartao": lambda g: g.cartao.nome_apelido,
                "categoria": lambda g: g.categoria.description,
                "cost_center": lambda g: g.cost_center.description if g.cost_center else "",
            }[sort_by]
            gastos_list.sort(key=key_func, reverse=reverse_order)
        else:
            # Para campos diretos, podemos usar attrgetter
            from operator import attrgetter
            reverse_order = sort_direction == "desc"
            gastos_list.sort(key=attrgetter(sort_by), reverse=reverse_order)
        gastos_queryset = gastos_list

    if not isinstance(gastos_queryset, list):
        order_by_fields, _ = _column_order(sort_by, sort_direction)
        gastos_queryset = gastos_queryset.order_by(*order_by_fields, "-data_compra")

    paginator = Paginator(gastos_queryset, 10)
    page_obj = paginator.get_page(request.GET.get("page", 1) if request else 1)
    current_page_gastos = list(page_obj.object_list)
    total_gastos = sum((gasto.valor_total for gasto in current_page_gastos), Decimal("0.00"))

    competencias = _competencias_disponiveis()

    # Build sort links for template
    sort_links = {}
    for col in SORTABLE_COLUMNS:
        params = request.GET.copy() if request else {}
        params["sort"] = col
        params["dir"] = "asc" if sort_by == col and sort_direction == "desc" else "desc"
        sort_links[col] = params.urlencode()

    # Build pagination links
    total_pages = page_obj.paginator.num_pages
    current_page = page_obj.number
    start_page = max(1, current_page - 3)
    end_page = min(total_pages, current_page + 3)
    page_numbers = list(range(start_page, end_page + 1))

    pagination_links = {
        "first": _build_querystring(
            q=search_query,
            cartao=selected_cartao,
            categoria=selected_categoria,
            competencia=selected_competencia,
            sort=sort_by,
            dir=sort_direction,
            page=1,
        ),
        "previous": _build_querystring(
            q=search_query,
            cartao=selected_cartao,
            categoria=selected_categoria,
            competencia=selected_competencia,
            sort=sort_by,
            dir=sort_direction,
            page=page_obj.previous_page_number() if page_obj.has_previous() else 1,
        ),
        "next": _build_querystring(
            q=search_query,
            cartao=selected_cartao,
            categoria=selected_categoria,
            competencia=selected_competencia,
            sort=sort_by,
            dir=sort_direction,
            page=page_obj.next_page_number() if page_obj.has_next() else page_obj.paginator.num_pages,
        ),
        "last": _build_querystring(
            q=search_query,
            cartao=selected_cartao,
            categoria=selected_categoria,
            competencia=selected_competencia,
            sort=sort_by,
            dir=sort_direction,
            page=page_obj.paginator.num_pages,
        ),
        "pages": [
            (
                number,
                _build_querystring(
                    q=search_query,
                    cartao=selected_cartao,
                    categoria=selected_categoria,
                    competencia=selected_competencia,
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
        "import_form": import_form,
        "gastos": current_page_gastos,
        "page_obj": page_obj,
        "editing_gasto": editing_gasto,
        "form_visible": form_visible,
        "form_action": reverse("cartao:gasto_create")
        if editing_gasto is None
        else reverse("cartao:gasto_edit", args=[editing_gasto.pk]),
        "cartoes": list(Cartao.objects.all()),
        "categorias": list(Category.objects.all()),
        "selected_cartao": selected_cartao,
        "selected_categoria": selected_categoria,
        "selected_competencia": selected_competencia,
        "competencias": competencias,
        "total_gastos": total_gastos,
        "limite_total": Cartao.objects.aggregate(total=Sum("limite_total"))["total"]
        or Decimal("0.00"),
        "limite_utilizado": Gasto.objects.aggregate(total=Sum("valor_total"))["total"]
        or Decimal("0.00"),
        "search_query": search_query,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "sort_links": sort_links,
        "pagination_links": pagination_links,
    }


def _fatura_context(request: HttpRequest | None = None) -> dict[str, Any]:
    cartoes = list(Cartao.objects.all())
    competencias = _competencias_disponiveis()

    selected_cartao = ""
    selected_competencia = _competencia_padrao()
    if request:
        selected_cartao = request.GET.get("cartao", "").strip()
        selected_competencia = request.GET.get("competencia", selected_competencia).strip()

    fatura = None
    selected_card = None
    if selected_cartao:
        try:
            selected_card = Cartao.objects.get(pk=int(selected_cartao))
            competencia = CompetenciaFatura.from_label(selected_competencia)
            fatura = selected_card.fatura(competencia.ano, competencia.mes)
        except (Cartao.DoesNotExist, ValueError):
            selected_cartao = ""
            fatura = None

    return {
        "cartoes": cartoes,
        "competencias": competencias,
        "selected_cartao": selected_cartao,
        "selected_competencia": selected_competencia,
        "selected_card": selected_card,
        "fatura": fatura,
    }


@login_required
@require_GET
def cartao_list(request: HttpRequest) -> HttpResponse:
    return render(request, "cartao/cartao_list.html", _cartao_context())


@login_required
@require_POST
def cartao_create(request: HttpRequest) -> HttpResponse:
    form = CartaoForm(request.POST)
    if form.is_valid():
        cartao = form.save()
        messages.success(request, f"Cartão '{cartao.nome_apelido}' criado com sucesso.")
        return redirect("cartao:cartao_list")

    messages.error(request, "Corrija os erros do cartão antes de salvar.")
    return render(request, "cartao/cartao_list.html", _cartao_context(form=form), status=400)


@login_required
@require_http_methods(["GET", "POST"])
def cartao_edit(request: HttpRequest, pk: int) -> HttpResponse:
    cartao = get_object_or_404(Cartao, pk=pk)
    if request.method == "POST":
        form = CartaoForm(request.POST, instance=cartao)
        if form.is_valid():
            cartao = form.save()
            messages.success(request, f"Cartão '{cartao.nome_apelido}' atualizado.")
            return redirect("cartao:cartao_list")
        messages.error(request, "Corrija os erros do cartão antes de salvar.")
        return render(
            request,
            "cartao/cartao_list.html",
            _cartao_context(form=form, editing_cartao=cartao),
            status=400,
        )
    return render(
        request,
        "cartao/cartao_list.html",
        _cartao_context(editing_cartao=cartao),
    )


@login_required
@require_POST
def cartao_delete(request: HttpRequest, pk: int) -> HttpResponse:
    cartao = get_object_or_404(Cartao, pk=pk)
    cartao.delete()
    messages.success(request, "Cartão removido.")
    return redirect("cartao:cartao_list")


@login_required
@require_GET
def gasto_list(request: HttpRequest) -> HttpResponse:
    return render(request, "cartao/gasto_list.html", _gasto_context(request))


@login_required
@require_GET
def fatura_list(request: HttpRequest) -> HttpResponse:
    return render(request, "cartao/fatura_list.html", _fatura_context(request))


@login_required
@require_POST
def gasto_create(request: HttpRequest) -> HttpResponse:
    form = GastoForm(request.POST)
    if form.is_valid():
        gasto = form.save()
        messages.success(request, f"Gasto '{gasto.descricao}' criado com sucesso.")
        return redirect("cartao:gasto_list")

    messages.error(request, "Corrija os erros do gasto antes de salvar.")
    return render(
        request,
        "cartao/gasto_list.html",
        _gasto_context(request, form=form),
        status=400,
    )


@login_required
@require_POST
def gasto_import(request: HttpRequest) -> HttpResponse:
    import_form = FaturaImportForm(request.POST, request.FILES)
    if not import_form.is_valid():
        messages.error(request, "Corrija os erros da importação antes de enviar o PDF.")
        context = _gasto_context(request)
        context["import_form"] = import_form
        return render(request, "cartao/gasto_list.html", context, status=400)

    service = InvoiceImportService()
    cartao = import_form.cleaned_data["cartao"]
    pdf_file = import_form.cleaned_data["pdf_file"]
    try:
        result = service.import_pdf(
            cartao=cartao,
            uploaded_file=pdf_file,
            filename=pdf_file.name,
        )
    except InvoiceImportError as exc:
        messages.error(request, str(exc))
        context = _gasto_context(request)
        context["import_form"] = import_form
        return render(request, "cartao/gasto_list.html", context, status=400)

    messages.success(
        request,
        f"Importação concluída: {result.imported_count} gasto(s) criado(s) e "
        f"{result.ignored_count} ignorado(s).",
    )
    return redirect("cartao:gasto_list")


@login_required
@require_http_methods(["GET", "POST"])
def gasto_edit(request: HttpRequest, pk: int) -> HttpResponse:
    gasto = get_object_or_404(Gasto.objects.select_related("cartao", "categoria"), pk=pk)
    if request.method == "POST":
        form = GastoForm(request.POST, instance=gasto)
        if form.is_valid():
            gasto = form.save()
            messages.success(request, f"Gasto '{gasto.descricao}' atualizado.")
            return redirect("cartao:gasto_list")
        messages.error(request, "Corrija os erros do gasto antes de salvar.")
        return render(
            request,
            "cartao/gasto_list.html",
            _gasto_context(request, form=form, editing_gasto=gasto),
            status=400,
        )
    return render(
        request,
        "cartao/gasto_list.html",
        _gasto_context(request, editing_gasto=gasto),
    )


@login_required
@require_POST
def gasto_delete(request: HttpRequest, pk: int) -> HttpResponse:
    gasto = get_object_or_404(Gasto, pk=pk)
    gasto.delete()
    messages.success(request, "Gasto removido.")
    return redirect("cartao:gasto_list")
