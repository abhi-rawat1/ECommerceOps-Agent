# Deployment

ECommerceOps-Agent is intended for controlled internal deployment. The included production Compose and NGINX examples are starting points, not a complete hardened platform.

## Required configuration

Supply these values through a secret manager or deployment platform:

- `POSTGRES_URL`
- `DB_SCHEMA`
- `OPENAI_API_KEY` or an equivalent OpenAI-compatible credential
- `JWT_SECRET_KEY`
- `MODEL_NAME`
- `LOG_DIR`
- Optional Langfuse public, secret, and host values

Do not commit `.env`, `.dev.env`, or `.prod.env` files.

## Production Compose

```bash
docker compose -f deployment/docker-compose.prod.yml up --build -d
```

Replace placeholder database hosts and credentials before deployment.

## Reverse proxy

The `deployment/nginx.conf` file provides an example entry point. Configure:

- HTTPS and modern TLS policies
- API and dashboard hostnames
- Request size and timeout limits
- Headers and network trust boundaries
- Health-check endpoints
- Firewall restrictions

## Production hardening checklist

- Replace demo authentication with SSO, OAuth, or enterprise identity.
- Use Argon2 or bcrypt password hashing, never plaintext passwords.
- Require a strong, rotated, non-default JWT secret.
- Store approvals in an audited relational database.
- Add route-level permission checks and organization-level authorization.
- Move audit logs to append-only or immutable storage.
- Restrict PostgreSQL privileges to required schemas and read-only query roles.
- Disable demo account seeding outside development.
- Add network, container, dependency, and secret scanning.
- Define backup, restore, retention, monitoring, and incident-response processes.
