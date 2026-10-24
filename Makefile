.PHONY: help install run-web run-cli run-demo test docker-build docker-up clean

PYTHON := python

help:
	@echo "FinRecon-AI Management Commands:"
	@echo "  make install       Install dependencies"
	@echo "  make run-web       Launch interactive FastAPI Web Dashboard"
	@echo "  make run-cli       Run reconciliation CLI with sample fixtures"
	@echo "  make run-demo      Execute quick terminal reconciliation demo"
	@echo "  make test          Run standalone test suite"
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-up     Start container with docker-compose"
	@echo "  make clean         Remove Python and test artifacts"

install:
	pip install -r requirements.txt

run-web:
	$(PYTHON) -m finrecon.main web

run-cli:
	$(PYTHON) -m finrecon.main cli

run-demo:
	$(PYTHON) -m finrecon.main demo

test:
	$(PYTHON) -m tests.run_all_tests

docker-build:
	docker build -t finrecon-ai:latest .

docker-up:
	docker-compose up --build -d

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache build dist *.egg-info
