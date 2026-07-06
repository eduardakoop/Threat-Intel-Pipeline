# Contributing

Thanks for helping improve TAsAutomation.

## Local Setup

```bash
cp .env.example .env.local
./scripts/setup_local_env.sh
```

Use `.env.local` for machine-specific values. Do not commit secrets, model files, logs, generated runs, or local virtual environments.

## Development Checks

Run the test suite before opening a pull request:

```bash
make test
```

For CI-equivalent execution:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests
```

## Pull Request Notes

- Keep generated output under `storage/`, `logs/`, and `vllm_models/` out of commits.
- Include focused tests when changing clustering, scoring, selection, formatting, or the web UI.
- Update `README.md` or `docs/` when changing setup, runtime configuration, or operator workflow.
- Avoid committing real article exports that contain sensitive client or operational information.
