# Agent Scheduler - Makefile
# ===========================

.PHONY: help install run test lint format ui clean

# Default input file
INPUT ?= ./input.csv
UTILIZATION ?= 1.0
FORMAT ?= text
CAPACITY ?=

# Python executable
PYTHON ?= python3

help:  ## Show this help message
	@echo "Agent Scheduler - Available Commands"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	$(PYTHON) -m pip install -r requirements.txt

# Build the run command with optional arguments
RUN_CMD = $(PYTHON) run.py --input $(INPUT) --utilization $(UTILIZATION) --format $(FORMAT)
ifdef CAPACITY
RUN_CMD += --capacity $(CAPACITY)
endif

run:  ## Run scheduler (INPUT=path, UTILIZATION=float, FORMAT=text|json|csv, CAPACITY=int)
	$(RUN_CMD)

run-verbose:  ## Run scheduler with verbose output
	$(RUN_CMD) --verbose

run-json:  ## Run scheduler with JSON output
	$(PYTHON) run.py --input $(INPUT) --format json

run-csv:  ## Run scheduler with CSV output
	$(PYTHON) run.py --input $(INPUT) --format csv

run-capacity:  ## Run with capacity constraint (CAPACITY=500)
	$(PYTHON) run.py --input $(INPUT) --capacity $(CAPACITY)

demo:  ## Run demo with sample input
	@echo "=== Basic Schedule ==="
	$(PYTHON) run.py --input ./input.csv
	@echo ""
	@echo "=== With 80% Utilization ==="
	$(PYTHON) run.py --input ./input.csv --utilization 0.8
	@echo ""
	@echo "=== With 500 Agent Capacity ==="
	$(PYTHON) run.py --input ./input.csv --capacity 500

test:  ## Run tests
	$(PYTHON) -m pytest tests/ -v

test-cov:  ## Run tests with coverage
	$(PYTHON) -m pytest tests/ -v --cov=scheduler --cov-report=term-missing

lint:  ## Run linter (mypy)
	$(PYTHON) -m mypy scheduler/ --ignore-missing-imports

format:  ## Format code with black
	$(PYTHON) -m black scheduler/ tests/

ui:  ## Start web UI (default port 5000)
	FLASK_APP=ui/app.py $(PYTHON) -m flask run --port 5000

ui-dev:  ## Start web UI in debug mode
	DEBUG=true FLASK_APP=ui/app.py $(PYTHON) -m flask run --port 5000 --reload

clean:  ## Clean up cache and build files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete

