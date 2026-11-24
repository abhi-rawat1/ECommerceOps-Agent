# Production deployment notes

## Required production environment variables

Set the following in a secure environment or deployment secret manager:

```env
APP_ENV=prod
POSTGRES_URL=postgresql+psycopg://postgres:your_secure_password@prod-db-host:5432/postgres
DB_SCHEMA=ecommerce
OPENAI_API_KEY=your_production_key
MODEL_NAME=gpt-4o-mini
LOG_DIR=/var/log/customersupportassist
```

## Start production stack

```bash
docker-compose -f deployment/docker-compose.prod.yml up --build -d
```

## Reverse proxy

Use NGINX config in `deployment/nginx.conf` if you want a single entry point for the API and dashboard.

## Security recommendations

- Use secrets manager instead of plain .env files
- Enable HTTPS behind a reverse proxy
- Lock permissions for approval endpoints to authorized roles
- Add real user identity integration (SSO/OAuth)
- Keep PostgreSQL and application services separate
