.PHONY: up down restart migrate collectstatic backupdb

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

backupdb:
	@mkdir -p backups
	@docker compose exec -T db sh -c 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup gerado em backups/"
