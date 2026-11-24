# Contributing

Thank you for considering a contribution to ECommerceOps-Agent.

## Development setup

1. Fork and clone the repository.
2. Create a Python 3.11 virtual environment.
3. Install `requirements.txt`.
4. Copy `.env.example` to `.env` and configure a local PostgreSQL database.
5. Run `python -m pytest -q`.

See [local development](docs/local-development.md) for detailed instructions.

## Pull requests

- Keep changes focused and documented.
- Add or update tests for behavior changes.
- Never include real credentials, customer data, audit logs, or runtime databases.
- Describe security, database, and deployment implications.
- Update relevant documentation and the README when public behavior changes.

## Code expectations

- Python 3.11-compatible code.
- Prefer explicit validation and typed models.
- Keep SQL read-only unless an approval workflow intentionally adds a controlled action.
- Preserve role boundaries and audit evidence.
- Do not weaken existing guardrails to make tests or demos pass.
