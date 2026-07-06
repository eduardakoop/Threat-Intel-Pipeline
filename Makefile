PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: setup install install-dev health run web cron test

setup:
	./scripts/setup_local_env.sh

install:
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install -r requirements-dev.txt

health:
	PYTHONPATH=src $(PYTHON) -m ta_pipeline --mode health --print-config

run:
	./scripts/run_full_pipeline.sh

web:
	./scripts/run_web_ui.sh

cron:
	./scripts/install_weekly_cron.sh

test:
	PYTHONPATH=src $(PYTHON) -m pytest tests
