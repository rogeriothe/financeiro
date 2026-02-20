.PHONY: up down restart migrate

up:
	docker compose up --build -d

down:
	docker compose down

restart:
	$(MAKE) down
	$(MAKE) up

migrate:
	docker compose up -d
	docker compose exec web uv run python src/manage.py migrate
