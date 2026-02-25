.PHONY: help dev-up dev-down dev-build dev-logs dev-shell migrate migrate-create migrate-history migrate-rollback clean prod-up prod-down

# Default command
help:
	@echo "Strava Automation Service - Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev-up          - Start development environment"
	@echo "  make dev-build       - Rebuild and start development environment"
	@echo "  make dev-down        - Stop development environment"
	@echo "  make dev-logs        - View all development logs"
	@echo "  make dev-shell       - Open shell in api container"
	@echo ""
	@echo "Database Migrations:"
	@echo "  make migrate         - Run pending migrations"
	@echo "  make migrate-create  - Create new migration (use MSG='description')"
	@echo "  make migrate-history - Show migration history"
	@echo "  make migrate-rollback- Rollback last migration"
	@echo ""
	@echo "Production (VPS/Testing):"
	@echo "  make prod-up         - Start with production config"
	@echo "  make prod-down       - Stop production config"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean           - Remove containers and images"
	@echo ""
	@echo "Examples:"
	@echo "  make dev-up"
	@echo "  make migrate-create MSG='add_notes_column'"
	@echo "  make dev-logs"

# Development
dev-up:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "✓ Development environment started!"
	@echo "  API:      http://localhost:8000"
	@echo "  Frontend: http://localhost:3001"
	@echo "  Database: localhost:5433"

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-build:
	docker-compose -f docker-compose.dev.yml up -d --build
	@echo "✓ Development environment rebuilt and started!"
	@echo "  API:      http://localhost:8000"
	@echo "  Frontend: http://localhost:3001"
	@echo "  Database: localhost:5433"

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-shell:
	docker-compose -f docker-compose.dev.yml exec api bash

# Database Migrations
migrate:
	docker-compose -f docker-compose.dev.yml exec api alembic upgrade head

migrate-create:
ifndef MSG
	@echo "Error: Please provide a message: make migrate-create MSG='description'"
	@exit 1
endif
	docker-compose -f docker-compose.dev.yml exec api alembic revision --autogenerate -m "$(MSG)"
	@echo "✓ Migration created! Check: backend/alembic/versions/"

migrate-history:
	docker-compose -f docker-compose.dev.yml exec api alembic history

migrate-rollback:
	docker-compose -f docker-compose.dev.yml exec api alembic downgrade -1

# Production (for testing prod build locally, VPS uses default via CI/CD)
prod-up:
	docker-compose up -d

prod-down:
	docker-compose down

# Utilities
clean:
	docker-compose -f docker-compose.dev.yml down -v
	docker system prune -af
