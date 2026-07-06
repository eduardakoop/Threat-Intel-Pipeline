# Security Policy

TAsAutomation is intended to run locally with local model access and local artifacts. Treat `.env.local`, generated run output, logs, model directories, and security audit records as machine-local data unless your organization has approved sharing them.

## Reporting Issues

Do not open public issues for suspected secrets, prompt-injection bypasses, unsafe model-output behavior, or vulnerabilities that could expose local data. Use a private channel with the repository owner or GitHub private vulnerability reporting if it is enabled for the repository.

## Handling Secrets

- Keep real API keys and model-server credentials in `.env.local` or the host environment.
- Commit `.env.example` only with placeholder values.
- Before publishing, verify that `.env.local`, `storage/`, `logs/`, `.venv/`, and `vllm_models/` are ignored.

## Supported Versions

Until the project has tagged releases, security fixes target the default branch.
