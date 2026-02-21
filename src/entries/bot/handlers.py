from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from entries.forms import EntryForm
from entries.models import Category, CostCenter, Entry

logger = logging.getLogger(__name__)

(
    STATE_KIND,
    STATE_DESCRIPTION,
    STATE_CATEGORY,
    STATE_COST_CENTER,
    STATE_PAYMENT_METHOD,
    STATE_DUE_DATE_TODAY,
    STATE_DUE_DATE,
    STATE_ORIGINAL_VALUE,
    STATE_SETTLED_CASH,
    STATE_SETTLED,
    STATE_PAYMENT_DATE,
    STATE_RECEIVED_VALUE,
    STATE_CONFIRMATION,
) = range(13)


@dataclass(frozen=True)
class PaymentMethodOption:
    index: int
    value: str
    label: str


PAYMENT_METHOD_OPTIONS = [
    PaymentMethodOption(index=index, value=value, label=label)
    for index, (value, label) in enumerate(Entry.PaymentMethod.choices)
]


def _load_authorized_ids() -> set[int]:
    raw_ids = os.getenv(
        "TELEGRAM_ALLOWED_USER_IDS",
        getattr(settings, "TELEGRAM_ALLOWED_USER_IDS", ""),
    )
    authorized_ids: set[int] = set()
    for raw_id in raw_ids.split(","):
        raw_id = raw_id.strip()
        if not raw_id:
            continue
        try:
            authorized_ids.add(int(raw_id))
        except ValueError:
            logger.warning("Ignorando TELEGRAM_ALLOWED_USER_IDS inválido: %s", raw_id)
    return authorized_ids


AUTHORIZED_IDS = _load_authorized_ids()


def _is_authorized(user_id: int) -> bool:
    return not AUTHORIZED_IDS or user_id in AUTHORIZED_IDS


def _kind_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Recebendo", callback_data="kind:recebendo"),
                InlineKeyboardButton("Pagando", callback_data="kind:pagando"),
            ]
        ]
    )


def _settled_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Sim", callback_data="settled:sim"),
                InlineKeyboardButton("Não", callback_data="settled:nao"),
            ]
        ]
    )


def _settled_cash_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Sim", callback_data="settled_cash:sim"),
                InlineKeyboardButton("Não", callback_data="settled_cash:nao"),
            ]
        ]
    )


def _due_today_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Sim", callback_data="due_today:sim"),
                InlineKeyboardButton("Não", callback_data="due_today:nao"),
            ]
        ]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Confirmar", callback_data="confirm:ok"),
                InlineKeyboardButton("Cancelar", callback_data="confirm:cancel"),
            ]
        ]
    )


@sync_to_async
def _cost_centers() -> list[CostCenter]:
    return list(CostCenter.objects.order_by("description"))


@sync_to_async
def _categories() -> list[Category]:
    return list(Category.objects.order_by("description"))


@sync_to_async
def _latest_entries(limit: int = 10) -> list[Entry]:
    return list(Entry.objects.order_by("-created_at", "-pk")[:limit])


def _category_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    category.description,
                    callback_data=f"cat:{category.pk}",
                )
            ]
            for category in categories
        ]
    )


def _cost_center_keyboard(cost_centers: list[CostCenter]) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                cost_center.description,
                callback_data=f"cc:{cost_center.pk}",
            )
        ]
        for cost_center in cost_centers
    ]
    buttons.append(
        [InlineKeyboardButton("Sem centro de custo", callback_data="cc:none")]
    )
    return InlineKeyboardMarkup(buttons)


def _payment_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(option.label, callback_data=f"pm:{option.index}")]
            for option in PAYMENT_METHOD_OPTIONS
        ]
    )


def _parse_money(raw_value: str) -> Decimal | None:
    normalized = raw_value.strip().replace(".", "").replace(",", ".")
    try:
        parsed = Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None
    if parsed <= 0:
        return None
    return parsed


def _parse_date(raw_value: str) -> date | None:
    candidate = raw_value.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _signed_amount(kind: str, amount: Decimal) -> Decimal:
    return -amount if kind == "pagando" else amount


def _entry_payload(user_data: dict[str, Any]) -> dict[str, Any]:
    original_value = _signed_amount(user_data["kind"], user_data["original_value"])
    received_value = user_data.get("received_value")
    if received_value is not None:
        received_value = _signed_amount(user_data["kind"], received_value)
    return {
        "description": user_data["description"],
        "category": user_data["category"],
        "cost_center": user_data.get("cost_center"),
        "forma_pagamento": user_data["forma_pagamento"],
        "due_date": user_data["due_date"].isoformat(),
        "original_value": str(original_value),
        "received_value": str(received_value) if received_value is not None else None,
        "payment_date": (
            user_data["payment_date"].isoformat()
            if user_data.get("payment_date")
            else None
        ),
    }


def _format_brl(value: Decimal) -> str:
    return f"{value:.2f}".replace(".", ",")


def _summary(user_data: dict[str, Any]) -> str:
    kind_label = "Recebimento" if user_data["kind"] == "recebendo" else "Pagamento"
    amount = user_data["original_value"]
    due_date = user_data["due_date"].strftime("%d/%m/%Y")
    payment_date = (
        user_data["payment_date"].strftime("%d/%m/%Y")
        if user_data.get("payment_date")
        else "Em aberto"
    )
    cost_center_label = user_data.get("cost_center_label") or "Sem centro de custo"
    return (
        "Confirma este lançamento?\n\n"
        f"Tipo: {kind_label}\n"
        f"Descrição: {user_data['description']}\n"
        f"Categoria: {user_data['category_label']}\n"
        f"Centro de custo: {cost_center_label}\n"
        f"Forma de pagamento: {user_data['forma_pagamento_label']}\n"
        f"Vencimento: {due_date}\n"
        f"Valor: R$ {amount:.2f}\n"
        f"Pagamento: {payment_date}"
    )


@sync_to_async
def _create_entry_from_payload(
    payload: dict[str, Any],
) -> tuple[Entry | None, dict[str, list[str]]]:
    form = EntryForm(payload)
    if form.is_valid():
        return form.save(), {}
    cleaned_errors = {
        field: [str(error) for error in errors]
        for field, errors in form.errors.items()
    }
    return None, cleaned_errors


async def _list_entries(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    user = update.effective_user
    if not user or not _is_authorized(user.id):
        if update.message:
            await update.message.reply_text(
                "Seu usuário não está autorizado para este bot."
            )
        return

    entries = await _latest_entries()
    if not update.message:
        return
    if not entries:
        await update.message.reply_text("Nenhum lançamento encontrado.")
        return

    lines = ["Últimos 10 lançamentos:"]
    for entry in entries:
        lines.append(
            f"- {entry.description} | {entry.due_date:%d/%m/%Y} | "
            f"R$ {_format_brl(entry.original_value)}"
        )
    await update.message.reply_text("\n".join(lines))


async def _start_conversation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    user = update.effective_user
    if not user or not _is_authorized(user.id):
        if update.message:
            await update.message.reply_text(
                "Seu usuário não está autorizado para este bot."
            )
        return ConversationHandler.END

    context.user_data.clear()
    if update.message:
        await update.message.reply_text(
            "Vamos cadastrar um lançamento.\n"
            "Você está pagando ou recebendo?\n"
            "Use /lista para ver os últimos 10 lançamentos.",
            reply_markup=_kind_keyboard(),
        )
    return STATE_KIND


async def _kind_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return STATE_KIND
    await query.answer()
    _, kind = query.data.split(":", maxsplit=1)
    context.user_data["kind"] = kind
    await query.edit_message_text("Informe a descrição do lançamento:")
    return STATE_DESCRIPTION


async def _description_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if not update.message:
        return STATE_DESCRIPTION
    description = update.message.text.strip()
    if not description:
        await update.message.reply_text(
            "Descrição não pode ficar vazia. Tente novamente."
        )
        return STATE_DESCRIPTION
    context.user_data["description"] = description
    categories = await _categories()
    if not categories:
        await update.message.reply_text(
            "Nenhuma categoria cadastrada. Cadastre uma categoria no sistema web e tente novamente."
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "Selecione a categoria:",
        reply_markup=_category_keyboard(categories),
    )
    return STATE_CATEGORY


async def _category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return STATE_CATEGORY
    await query.answer()
    _, selection = query.data.split(":", maxsplit=1)
    try:
        category_id = int(selection)
    except ValueError:
        await query.edit_message_text("Categoria inválida. Tente novamente.")
        return STATE_CATEGORY
    categories = await _categories()
    selected_category = next(
        (category for category in categories if category.pk == category_id),
        None,
    )
    if selected_category is None:
        await query.edit_message_text("Categoria inválida. Tente novamente.")
        return STATE_CATEGORY
    context.user_data["category"] = category_id
    context.user_data["category_label"] = selected_category.description
    centers = await _cost_centers()
    await query.edit_message_text(
        "Selecione o centro de custo:",
        reply_markup=_cost_center_keyboard(centers),
    )
    return STATE_COST_CENTER


async def _cost_center_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    if not query:
        return STATE_COST_CENTER
    await query.answer()
    _, selection = query.data.split(":", maxsplit=1)
    if selection == "none":
        context.user_data["cost_center"] = None
        context.user_data["cost_center_label"] = None
    else:
        try:
            center_id = int(selection)
        except ValueError:
            await query.edit_message_text("Centro de custo inválido. Tente novamente.")
            return STATE_COST_CENTER
        centers = await _cost_centers()
        chosen_center = next(
            (center for center in centers if center.pk == center_id),
            None,
        )
        context.user_data["cost_center"] = center_id
        context.user_data["cost_center_label"] = (
            chosen_center.description if chosen_center else None
        )
    await query.edit_message_text(
        "Escolha a forma de pagamento:",
        reply_markup=_payment_method_keyboard(),
    )
    return STATE_PAYMENT_METHOD


async def _payment_method_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    if not query:
        return STATE_PAYMENT_METHOD
    await query.answer()
    _, option_index_raw = query.data.split(":", maxsplit=1)
    try:
        option_index = int(option_index_raw)
    except ValueError:
        await query.edit_message_text("Forma de pagamento inválida. Tente novamente.")
        return STATE_PAYMENT_METHOD
    selected = next(
        (option for option in PAYMENT_METHOD_OPTIONS if option.index == option_index),
        None,
    )
    if selected is None:
        await query.edit_message_text("Forma de pagamento inválida. Tente novamente.")
        return STATE_PAYMENT_METHOD
    context.user_data["forma_pagamento"] = selected.value
    context.user_data["forma_pagamento_label"] = selected.label
    await query.edit_message_text(
        "O vencimento foi hoje?",
        reply_markup=_due_today_keyboard(),
    )
    return STATE_DUE_DATE_TODAY


async def _due_date_today_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    if not query:
        return STATE_DUE_DATE_TODAY
    await query.answer()
    _, selection = query.data.split(":", maxsplit=1)
    if selection == "sim":
        context.user_data["due_date"] = date.today()
        await query.edit_message_text(
            "Informe o valor (apenas número positivo, ex: 250,90):"
        )
        return STATE_ORIGINAL_VALUE
    await query.edit_message_text("Informe a data de vencimento (DD/MM/AAAA):")
    return STATE_DUE_DATE


async def _due_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message:
        return STATE_DUE_DATE
    due_date = _parse_date(update.message.text)
    if due_date is None:
        await update.message.reply_text("Data inválida. Use DD/MM/AAAA.")
        return STATE_DUE_DATE
    context.user_data["due_date"] = due_date
    await update.message.reply_text(
        "Informe o valor (apenas número positivo, ex: 250,90):"
    )
    return STATE_ORIGINAL_VALUE


async def _original_value_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if not update.message:
        return STATE_ORIGINAL_VALUE
    amount = _parse_money(update.message.text)
    if amount is None:
        await update.message.reply_text("Valor inválido. Envie um número positivo.")
        return STATE_ORIGINAL_VALUE
    context.user_data["original_value"] = amount
    await update.message.reply_text(
        "Foi liquidado à vista?",
        reply_markup=_settled_cash_keyboard(),
    )
    return STATE_SETTLED_CASH


async def _settled_cash_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    query = update.callback_query
    if not query:
        return STATE_SETTLED_CASH
    await query.answer()
    _, selection = query.data.split(":", maxsplit=1)
    if selection == "sim":
        context.user_data["payment_date"] = context.user_data["due_date"]
        context.user_data["received_value"] = context.user_data["original_value"]
        await query.edit_message_text(
            _summary(context.user_data),
            reply_markup=_confirm_keyboard(),
        )
        return STATE_CONFIRMATION
    await query.edit_message_text(
        "Esse lançamento foi liquidado?",
        reply_markup=_settled_keyboard(),
    )
    return STATE_SETTLED


async def _settled_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return STATE_SETTLED
    await query.answer()
    _, selection = query.data.split(":", maxsplit=1)
    is_settled = selection == "sim"
    context.user_data["is_settled"] = is_settled
    if not is_settled:
        context.user_data["payment_date"] = None
        context.user_data["received_value"] = None
        await query.edit_message_text(
            _summary(context.user_data),
            reply_markup=_confirm_keyboard(),
        )
        return STATE_CONFIRMATION
    await query.edit_message_text(
        "Informe a data do pagamento/recebimento (DD/MM/AAAA):"
    )
    return STATE_PAYMENT_DATE


async def _payment_date_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if not update.message:
        return STATE_PAYMENT_DATE
    payment_date = _parse_date(update.message.text)
    if payment_date is None:
        await update.message.reply_text("Data inválida. Use DD/MM/AAAA.")
        return STATE_PAYMENT_DATE
    context.user_data["payment_date"] = payment_date
    await update.message.reply_text(
        "Informe o valor liquidado (positivo). "
        "Você pode enviar 'mesmo' para usar o valor original."
    )
    return STATE_RECEIVED_VALUE


async def _received_value_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    if not update.message:
        return STATE_RECEIVED_VALUE
    raw_value = update.message.text.strip().lower()
    if raw_value == "mesmo":
        context.user_data["received_value"] = context.user_data["original_value"]
    else:
        amount = _parse_money(update.message.text)
        if amount is None:
            await update.message.reply_text(
                "Valor inválido. Envie um número positivo ou 'mesmo'."
            )
            return STATE_RECEIVED_VALUE
        context.user_data["received_value"] = amount
    await update.message.reply_text(
        _summary(context.user_data),
        reply_markup=_confirm_keyboard(),
    )
    return STATE_CONFIRMATION


async def _confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return STATE_CONFIRMATION
    await query.answer()
    _, decision = query.data.split(":", maxsplit=1)
    if decision == "cancel":
        await query.edit_message_text(
            "Cadastro cancelado. Use /novo para iniciar novamente."
        )
        context.user_data.clear()
        return ConversationHandler.END

    payload = _entry_payload(context.user_data)
    entry, errors = await _create_entry_from_payload(payload)
    if entry is None:
        message_lines = ["Não foi possível salvar o lançamento:"]
        for field, messages_list in errors.items():
            for message in messages_list:
                message_lines.append(f"- {field}: {message}")
        await query.edit_message_text("\n".join(message_lines))
        return ConversationHandler.END

    await query.edit_message_text(
        f"Lançamento '{entry.description}' criado com sucesso. "
        "Use /novo para cadastrar outro."
    )
    context.user_data.clear()
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Cadastro cancelado.")
    return ConversationHandler.END


def build_application(bot_token: str) -> Application:
    application = Application.builder().token(bot_token).build()
    application.add_handler(CommandHandler("lista", _list_entries))
    conversation = ConversationHandler(
        entry_points=[
            CommandHandler("start", _start_conversation),
            CommandHandler("novo", _start_conversation),
        ],
        states={
            STATE_KIND: [CallbackQueryHandler(_kind_handler, pattern=r"^kind:")],
            STATE_DESCRIPTION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    _description_handler,
                )
            ],
            STATE_CATEGORY: [
                CallbackQueryHandler(_category_handler, pattern=r"^cat:")
            ],
            STATE_COST_CENTER: [
                CallbackQueryHandler(_cost_center_handler, pattern=r"^cc:")
            ],
            STATE_PAYMENT_METHOD: [
                CallbackQueryHandler(_payment_method_handler, pattern=r"^pm:")
            ],
            STATE_DUE_DATE_TODAY: [
                CallbackQueryHandler(
                    _due_date_today_handler,
                    pattern=r"^due_today:",
                )
            ],
            STATE_DUE_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _due_date_handler)
            ],
            STATE_ORIGINAL_VALUE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    _original_value_handler,
                )
            ],
            STATE_SETTLED_CASH: [
                CallbackQueryHandler(
                    _settled_cash_handler,
                    pattern=r"^settled_cash:",
                )
            ],
            STATE_SETTLED: [
                CallbackQueryHandler(_settled_handler, pattern=r"^settled:")
            ],
            STATE_PAYMENT_DATE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    _payment_date_handler,
                )
            ],
            STATE_RECEIVED_VALUE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    _received_value_handler,
                )
            ],
            STATE_CONFIRMATION: [
                CallbackQueryHandler(_confirm_handler, pattern=r"^confirm:")
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", _cancel),
            CommandHandler("cancel", _cancel),
        ],
        allow_reentry=True,
    )
    application.add_handler(conversation)
    return application


def get_bot_token() -> str:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if bot_token:
        return bot_token
    if getattr(settings, "TELEGRAM_BOT_TOKEN", ""):
        return settings.TELEGRAM_BOT_TOKEN
    raise ImproperlyConfigured("Defina TELEGRAM_BOT_TOKEN no ambiente (.env).")
