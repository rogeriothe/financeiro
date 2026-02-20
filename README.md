# Financeiro

Aplicação Django para registrar contas a pagar e receber, com interface responsiva baseada em Bootstrap. O layout apresenta totais consolidados, uma grade com os lançamentos e um formulário lateral que pode ser recolhido quando não estiver em uso.

## Requisitos

- Python 3.12
- [uv](https://github.com/astral-sh/uv) 0.4 ou superior
- Docker 24+ (opcional)

## Configuração com uv

```bash
uv sync
cp .env.example .env
uv run python src/manage.py migrate
uv run python src/manage.py loaddata sample_entries  # opcional
uv run python src/manage.py createsuperuser          # requer credenciais de login
uv run python src/manage.py runserver
```

A aplicação ficará disponível em `http://127.0.0.1:8000`. O acesso requer autenticação; utilize o usuário criado via `createsuperuser`. Para adicionar outros usuários, repita o comando ou use o admin (`/admin/`).

### Bot do Telegram

Defina no `.env`:

```bash
TELEGRAM_BOT_TOKEN=seu_token_do_botfather
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

`TELEGRAM_ALLOWED_USER_IDS` é opcional. Quando vazio, qualquer usuário que descobrir o bot poderá conversar com ele.

Para rodar localmente sem Docker:

```bash
uv run python src/manage.py run_telegram_bot
```

## Executando com Docker

```bash
cp .env.example .env
docker compose up --build
```

O serviço web utiliza `uv` dentro do container e depende do PostgreSQL 16 definido em `docker-compose.yml`.
O `docker-compose.yml` também sobe o serviço `telegram-bot`, usando as variáveis do `.env`.

## Estrutura principal

- `src/financeiro_project/` — configurações globais do Django, formulários compartilhados e URLs do projeto.
- `src/entries/` — app responsável pelos lançamentos (modelos, formulários, views, templates e fixtures).
- `src/templates/` — templates base, telas HTML e página de login.
- `src/static/` — ativos estáticos (CSS, imagens).

## Boas práticas

- Valores positivos representam recebimentos; valores negativos, pagamentos.
- Informe o mesmo sinal ao preencher o campo “Valor recebido/pago”.
- Use `uv run ruff check src` para garantir estilo e imports.
- Em ambiente Docker, aplique migrações com `docker compose exec web uv run python src/manage.py migrate`.

## Licença

Este projeto está licenciado sob a [Creative Commons Attribution-ShareAlike 4.0 International](LICENSE) (CC BY-SA 4.0). Você pode reutilizar e adaptar, desde que forneça crédito e compartilhe contribuições derivadas sob a mesma licença.
