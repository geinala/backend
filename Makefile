.PHONY: help install sync worker worker-verbose redis-cli test docker-up docker-down docker-logs docker-build docker-prod clean

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

help:
	@echo "$(BLUE)Simulation App Solver - Available Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Setup:$(NC)"
	@echo "  make install         Install dependencies with uv"
	@echo "  make sync            Sync dependencies from uv.lock"
	@echo ""
	@echo "$(GREEN)Development:$(NC)"
	@echo "  make worker          Run worker locally"
	@echo "  make worker-verbose  Run worker with verbose logging"
	@echo "  make redis-cli       Connect to local Redis"
	@echo "  make test            Run pytest suite"
	@echo ""
	@echo "$(GREEN)Docker Development:$(NC)"
	@echo "  make docker-up       Start Redis + Worker containers"
	@echo "  make docker-down     Stop all containers"
	@echo "  make docker-logs     View container logs"
	@echo "  make docker-build    Build Docker image"
	@echo ""
	@echo "$(GREEN)Docker Production:$(NC)"
	@echo "  make docker-prod     Build and run production setup (3 workers)"
	@echo ""
	@echo "$(GREEN)Cleanup:$(NC)"
	@echo "  make clean           Remove __pycache__, .pytest_cache, etc."

# Setup
install:
	@echo "$(BLUE)Installing dependencies...$(NC)"
	uv sync

sync:
	@echo "$(BLUE)Syncing dependencies...$(NC)"
	uv sync

# Development - Local
worker:
	@echo "$(BLUE)Starting RQ worker...$(NC)"
	rq worker

worker-verbose:
	@echo "$(BLUE)Starting RQ worker (verbose)...$(NC)"
	rq worker -v

redis-cli:
	@echo "$(BLUE)Connecting to Redis CLI...$(NC)"
	redis-cli

test:
	@echo "$(BLUE)Running tests...$(NC)"
	pytest -v

test-coverage:
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest --cov=app --cov-report=html

# Docker Development
docker-up:
	@echo "$(BLUE)Starting Docker containers (development)...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Redis on localhost:6379$(NC)"
	@echo "$(GREEN)✓ Worker running...$(NC)"

docker-down:
	@echo "$(BLUE)Stopping Docker containers...$(NC)"
	docker-compose down

docker-logs:
	@echo "$(BLUE)Showing Docker logs (press Ctrl+C to exit)...$(NC)"
	docker-compose logs -f

docker-build:
	@echo "$(BLUE)Building Docker image...$(NC)"
	docker-compose build

# Docker Production
docker-prod:
	@echo "$(BLUE)Building and running production setup...$(NC)"
	docker build -t solver:latest .
	@echo "$(GREEN)✓ Image built as 'solver:latest'$(NC)"
	docker-compose -f docker-compose.prod.yml up -d
	@echo "$(GREEN)✓ Production deployment with 3 workers$(NC)"

docker-prod-scale:
	@echo "$(BLUE)Scaling to 5 workers...$(NC)"
	docker-compose -f docker-compose.prod.yml up -d --scale worker=5

# Cleanup
clean:
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .rq -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .venv -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# Utility
redis-info:
	@redis-cli info

redis-flushdb:
	@echo "$(RED)Flushing Redis database...$(NC)"
	redis-cli FLUSHDB
	@echo "$(GREEN)✓ Redis flushed$(NC)"

.DEFAULT_GOAL := help
