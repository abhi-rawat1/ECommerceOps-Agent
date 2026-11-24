# CustomerSupportAssist architecture

```mermaid
flowchart LR
    U[Customer Support Agent / Operator] --> UI[Streamlit Dashboard\napp.py]
    U --> API[FastAPI Approval API\napi.py]

    UI --> WF[Support Workflow\nworkflows/support_workflow.py]
    API --> APS[Approval Service\nservices/approval_service.py]

    WF --> SA[SQL Agent\nservices/sql_agent.py]
    SA --> RG[Guardrails\ncore/guardrails.py]
    SA --> TOOLS[Support Tools\nlookup_order\nlookup_customer_orders\ncheck_inventory\nget_metric]

    TOOLS --> DB[(PostgreSQL\nE-commerce DB)]
    TOOLS --> MS[Metrics Service\nservices/metrics_service.py]
    MS --> DB

    RG --> TRACE[Audit & Trace log\ncore/tracing.py]
    APS --> APPROVAL_LOG[(Approval JSONL log)]
    TRACE --> LOGS[(Support Audit Logs)]

    DB --> RESP[Final Response\nOrder / inventory / return / metric results]
    WF --> RESP
    APS --> RESP

    RESP --> UI
    RESP --> U
```

## Workflow summary

1. A support user asks a natural-language question in the dashboard.
2. The workflow classifies the query as either read-only or action-based.
3. Guardrails validate whether the request is safe and within policy.
4. If the request is read-only, the SQL agent executes safe queries against the PostgreSQL database.
5. If the request attempts a return/refund/cancel action, it requires approval.
6. The approval-service writes the approval event to a JSONL log.
7. Every step is traced and stored in the audit log for observability and debugging.
8. The final result is displayed in the Streamlit app with clear evidence and trace details.

## Design principles

- Safe-by-default: all support queries are read-only unless a controlled approval path is used.
- Traceable: every tool call and workflow decision is recorded.
- Compliant: policy checks enforce approved tables and blocked SQL patterns.
- Operational: metrics and support data are surfaced for operations teams.
- Deployable: FastAPI and Streamlit can run together with Docker Compose.
