.PHONY: up down restart migrate collectstatic

up:
	docker compose up --build -d
	$(MAKE) collectstatic

down:
	docker compose down

restart:
	$(MAKE) down
	$(MAKE) up

migrate:
	docker compose up -d
	docker compose exec web uv run python src/manage.py migrate

collectstatic:
	docker compose exec web uv run python src/manage.py collectstatic --noinput
