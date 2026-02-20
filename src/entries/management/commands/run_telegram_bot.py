from __future__ import annotations

from django.core.management.base import BaseCommand

from entries.bot.handlers import build_application, get_bot_token


class Command(BaseCommand):
    help = "Executa o bot do Telegram para cadastro de lançamentos."

    def handle(self, *args, **options) -> None:
        token = get_bot_token()
        application = build_application(token)
        self.stdout.write(self.style.SUCCESS("Bot do Telegram iniciado (long polling)."))
        application.run_polling(allowed_updates=["message", "callback_query"])
