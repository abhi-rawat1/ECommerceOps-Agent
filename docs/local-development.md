# Local Development

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- Git
- Optional: Docker Desktop or Docker Engine
- An OpenAI-compatible API key for generated SQL and chat responses

## Python setup

### Windows PowerShell

```powershell
cd ECommerceOps-Agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

### macOS or Linux

```bash
cd ECommerceOps-Agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Configure the values in `.env`, including `POSTGRES_URL`, `OPENAI_API_KEY`, and optional Langfuse credentials.

## Database setup

Create a database and schema, then load the synthetic demonstration data:

```bash
python scripts/load_ecommerce_data.py
```

The loader uses `sql/ecommerce_schema.sql` and the configured PostgreSQL connection.

## Run the API

```bash
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Open the interactive API documentation at `http://localhost:8000/docs`.

## Run the dashboard

In another terminal:

```bash
streamlit run app.py
```

Open `http://localhost:8501`.

Set `CUSTOMER_SUPPORT_API_URL=http://localhost:8000` if the dashboard cannot reach the local API. On PowerShell:

```powershell
$env:CUSTOMER_SUPPORT_API_URL="http://localhost:8000"
```

## Demo identities

Demo identities are enabled only for isolated local evaluation:

- `support_agent` / `support123`
- `ops_manager` / `ops123`
- `finance_analyst` / `finance123`

Change or disable these identities before any external deployment. Never reuse demo passwords in production.

## Docker

The Docker Compose file uses `host.docker.internal` for the local PostgreSQL host. Verify host resolution for your operating system.

```bash
docker compose up --build
```

Access:

- Dashboard: `http://localhost:8501`
- API: `http://localhost:8000/docs`

## Tests

```bash
python -m pytest -q
```

PostgreSQL and provider credentials may be required for integration-style workflow tests. Unit tests should be run in an isolated environment where possible.
