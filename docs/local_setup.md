# Local setup guide for CustomerSupportAssist

## 1. Prerequisites

Install the following on your machine:

- Python 3.11+
- PostgreSQL 14+ or later
- pgAdmin or psql (optional but helpful)
- Git
- VS Code (recommended)

## 2. Clone and navigate

```bash
cd c:\Abhishek\Agentic-AI\AgenticSQL
```

## 3. Create a virtual environment

```bash
cd customer_support_assist
python -m venv .venv
.venv\Scripts\activate
```

## 4. Install dependencies

```bash
pip install -r requirements.txt
```

## 5. Configure environment

Create a `.env` file from `.env.example`:

```bash
copy .env.example .env
```

Then edit `.env` with values like:

```env
POSTGRES_URL=postgresql+psycopg://postgres:your_password@localhost:5432/postgres
DB_SCHEMA=ecommerce
OPENAI_API_KEY=your_openai_api_key_here
MODEL_NAME=gpt-4o-mini
ALLOWED_TABLES=customers,orders,order_items,products,returns,refunds,inventory,shipments
APPROVAL_REQUIRED_ACTIONS=refund_order,create_return,cancel_order,update_inventory
LOG_DIR=logs
```

## 6. Create PostgreSQL database and schema

Open psql and run:

```sql
CREATE DATABASE postgres;
```

If using an existing database like `postgres`, ensure the user has access and then run:

```sql
CREATE SCHEMA IF NOT EXISTS ecommerce;
```

## 7. Load seed dataset

Run:

```bash
python scripts/load_ecommerce_data.py
```

This will execute the schema and seed script from `sql/ecommerce_schema.sql`.

## 8. Run the approval API first

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

Open the API docs at:

http://localhost:8000/docs

## 9. Run the dashboard with the JWT API configured

In a second terminal, set the API URL and start Streamlit:

```bash
set CUSTOMER_SUPPORT_API_URL=http://localhost:8000
streamlit run app.py
```

Open the browser at:

http://localhost:8501

The dashboard logs in through the FastAPI `/login` endpoint and keeps a bearer token in session state. Protected approval actions use the JWT token in the `Authorization` header.

## 10. Default demo users

The app ships with the following seeded users:

- support_agent / support123
- ops_manager / ops123
- finance_analyst / finance123

## 11. Example API calls

### Create a refund approval request

```bash
curl -X POST "http://localhost:8000/approvals" -H "Content-Type: application/json" -d "{\"order_id\":\"10021\",\"action_type\":\"refund_order\",\"reason\":\"damaged item\",\"requested_by\":\"support-agent@example.com\"}"
```

### View pending approvals

```bash
curl http://localhost:8000/approvals/pending
```

### Approve a request

```bash
curl -X POST "http://localhost:8000/approvals/decision" -H "Content-Type: application/json" -d "{\"request_id\":\"your_request_id\",\"approved_by\":\"ops-manager@example.com\"}"
```

## 12. Docker local deployment

From the project root:

```bash
docker-compose up --build
```

Then access:

- Streamlit: http://localhost:8501
- API: http://localhost:8000/docs

## 13. Useful commands

```bash
python -m pytest -q
python scripts/load_ecommerce_data.py
streamlit run app.py
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```
