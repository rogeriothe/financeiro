# Repository Guidelines

## Project Structure & Module Organization
- Código Django fica em `src/financeiro_project/` (configurações) e `src/entries/` (modelos, formulários, views e fixtures). Templates globais residem em `src/templates/`, enquanto ativos estáticos ficam em `src/static/`.
- Mantenha parciais HTMX no diretório `src/templates/entries/partials/` para reaproveitamento nas respostas dinâmicas.
- Arquivos de infraestrutura (`Dockerfile`, `docker-compose.yml`, `.env.example`) permanecem na raiz. Ajuste a stack aqui antes de replicar em produção.

## Build & Development Commands
- `uv sync` instala dependências declaradas em `pyproject.toml` e cria o ambiente gerenciado pelo uv.
- `cp .env.example .env` gera a configuração padrão; personalize segredos antes de subir serviços.
- `uv run python src/manage.py migrate` aplica migrações; `uv run python src/manage.py loaddata sample_entries` carrega dados de exemplo.
- `uv run python src/manage.py runserver` inicia o servidor local com SQLite; use `docker compose up --build` para executar com PostgreSQL 16.
- `uv run ruff check src` garante estilo e ordenação de imports antes de abrir PR.

## Coding Style & Naming Conventions
- Utilize Python 3.12, indentação de quatro espaços e limite de 88 colunas. `ruff` cobre linting, formatação e ordenação de imports.
- Mantenha nomes em snake_case para funções/módulos, PascalCase para classes e CONSTANTES em caixa alta (`PAYMENT_CATEGORY_DEFAULT`).
- Templates HTMX devem expor IDs estáveis (`#entries-table`, `#entries-summary`) para facilitar trocas parciais.
- Campos monetários usam `DecimalField` com 2 casas; preserve o sinal dos valores para indicar recebimentos (positivo) e pagamentos (negativo).

## Commit & Pull Request Guidelines
- Acompanhe o padrão Conventional Commits (`feat: suporte a liquidação parcial`, `fix: corrige cálculo de saldo`). Adicione escopos quando útil (`feat(entries): ...`).
- PRs devem descrever mudanças funcionais, incluir comandos executados (`uv run ruff check src`, `docker compose up`) e capturas de tela sempre que mexer em UI.
- Faça squash de commits ruidosos antes de abrir o PR e mantenha o branch alinhado com `main` para facilitar o deploy contínuo.
