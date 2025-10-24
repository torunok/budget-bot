# Makefile для швидких команд

.PHONY: help install run test lint format clean deploy

help:
	@echo "Available commands:"
	@echo "  make install  - Install dependencies"
	@echo "  make run      - Run bot locally"
	@echo "  make test     - Run tests"
	@echo "  make lint     - Run linter"
	@echo "  make format   - Format code"
	@echo "  make clean    - Clean cache files"
	@echo "  make deploy   - Deploy to Render"

install:
	pip install -r requirements.txt

run:
	python -m app.main

test:
	pytest tests/ -v

lint:
	flake8 app/ --max-line-length=120
	pylint app/

format:
	black app/
	isort app/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

deploy:
	git push origin main
	@echo "Deployment triggered on Render!"