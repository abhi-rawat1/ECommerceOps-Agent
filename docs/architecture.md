# ECommerceOps-Agent Architecture

## Runtime components

- **Streamlit dashboards:** support operations, analytics, and administration interfaces.
- **FastAPI API:** authentication, JWT authorization, support requests, approvals, metrics, and audit endpoints.
- **Agentic LLM Workflow:** intent classification, entity extraction, follow-up handling, and approval routing.
- **SQL agent:** natural-language-to-SQL generation and execution for approved read-only tables.
- **Guardrails:** SQL validation, blocked destructive statements, table allowlists, and approval-required actions.
- **PostgreSQL:** synthetic e-commerce data, users, and approval records.
- **Semantic metrics:** dbt-style definitions for revenue, returns, inventory risk, and support KPIs.
- **Tracing:** support audit events and optional Langfuse observability.

## High Level Flow Diagram

```mermaid
flowchart LR
    User[Viewer or Operations User] --> UI[Streamlit Dashboards]
    UI --> API[FastAPI]
    subgraph FastAPIServer ["FastAPIServer "]
        API --> Auth[JWT and RBAC Autorization]
        Auth --> Workflow[Workflow]
        Workflow --> LLMAgentIntentDetection{LLM Agent Intent Detection}
        
        subgraph Traces ["LangGraph Workflow with Guardrails & Trace/Langfuse Events "]
            LLMAgentIntentDetection -->|Metrics| Metrics[Semantic Metrics Definitions]
            Metrics --> DB[(PostgreSQL)]
            
            LLMAgentIntentDetection -->|General Query| LLMSQLGeneratorAgent
            LLMSQLGeneratorAgent[LLM SQL Generator Agent] --> Guardrails[SQL and Action Guardrails] 
            Guardrails --> DB[(PostgreSQL)]
            
            LLMAgentIntentDetection -->|Order Lifecycle Action| ApprovalWorkflow[Approval HITL Workflow]
            ApprovalWorkflow --> DB[(PostgreSQL)]

            DB --> Response[LLM Response Generator Agent- Chart/grid/summary/results]

            LLMAgentIntentDetection -->|Missing Info/ Clarification Needed| Response
            
        end
        classDef highlight fill:#dbeafe,stroke:#1d4ed8,stroke-width:3px,color:#1e3a8a
        class LLMAgentIntentDetection,Response,LLMSQLGeneratorAgent highlight

        Workflow --> Approval[Approval Workflow- Cancel/Approve/Reject]
        Approval --> |Update Approval Request| DB1[(PostgreSQL)]
    end
    classDef boxhighlight fill:#e8f5e9,stroke:#2e7d32,stroke-width:3px,color:#1b5e20
    class FastAPIServer boxhighlight
    Response --> UI1[Streamlit Dashboards]
    DB1 -->  UI1[Streamlit Dashboards]
```

## Low Level Flow Diagram

```mermaid
flowchart LR
    User[Viewer or Operations User] --> UI[Streamlit Dashboards]
    User --> Admin[Administration UI]
    UI --> API[FastAPI Support and Metrics APIs]
    Admin --> API

    API --> Auth[JWT and RBAC]
    API --> Process[process_support_request]
    API --> Resume[resume_support_request]

    subgraph LG[LangGraph Workflow with Guardrails & Trace/Langfuse Events]
        Process --> TraceStart[Trace workflow_started]
        Resume --> MergedState[Merge original request and follow-up answer]
        TraceStart --> LFStart[Langfuse workflow trace]
        MergedState --> FollowUpTrace[Trace follow_up_received]
        LFStart --> Intent
        FollowUpTrace --> Intent

        Intent[_intent_node<br/>detect intent, entities, missing fields] --> Route{_route_node}

        Route -->|missing_fields| FollowUp[_follow_up_node]
        Route -->|metric_query| Metric[_metric_query_node]
        Route -->|initiate_refund, cancel_item,<br/>cancel_order, initiate_return| Lifecycle[_lifecycle_action_node]
        Route -->|refund_status, general_query,<br/>lookup_order, lookup_customer_orders,<br/>inventory_check| Read[_read_query_node]
        Route -->|unknown or other intent| Clarify[_clarification_node]

        Metric --> Semantic[Semantic Metric Definition]
        Metric --> SQLAgent
        Read --> SQLAgent[SQL Agent generate and execute]
        Lifecycle --> LifecycleService[Lifecycle Service<br/>refund or cancel or return]

        SQLAgent --> Guardrails[SQL Guardrails and Table Allowlist]
        Guardrails --> DB[(PostgreSQL)]
        Semantic --> DB
        LifecycleService --> ApprovalRecord[Create approval request and return awaiting status]
        ApprovalRecord --> ApprovalStore[(Approval Records)]

        DeadApproval[_human_approval_node<br/>defined but not targeted by _route_node] -. graph node only .-> END1
        FollowUp --> END1([END])
        Clarify --> END1
        Metric --> END1
        Read --> END1
        Lifecycle --> END1
    end

    Admin --> ApprovalManager[Operations Manager<br/>approve, reject, or cancel]
    ApprovalManager --> ApprovalStore
    ApprovalStore --> DB
    ApprovalStore --> Audit[(Audit Logs)]

    END1 --> Response[Status, Answer, Rows, Presentation, SQL, Pending State]
    Guardrails --> Traces[Trace Events and Langfuse]
    LifecycleService --> Traces
    Traces --> Audit
    Response --> UI
```

## Request flow

1. A user submits a natural-language request.
2. The workflow identifies the intent and required entities.
3. The guardrail layer validates read-only SQL or identifies an approval-required action.
4. Read-only requests may execute a generated SQL query against the allowlisted PostgreSQL tables.
5. Return, cancellation, inventory update, and refund operations create an approval request.
6. An operations manager approves, rejects, or cancels the request.
7. The workflow records the action and returns trace and audit evidence.
8. Streamlit presents tables, summaries, or charts according to the result shape.

## Security boundaries

- Read-only SQL is the default.
- Destructive SQL and multiple statements are blocked.
- Queries are restricted to configured tables.
- Sensitive actions require role authorization and human approval.
- PostgreSQL, JWT, provider credentials, and audit storage must be hardened for production.

## Design principles

- Safe-by-default: all support queries are read-only unless a controlled approval path is used.
- Traceable: every tool call and workflow decision is recorded.
- Compliant: policy checks enforce approved tables and blocked SQL patterns.
- Operational: metrics and support data are surfaced for operations teams.
- Deployable: FastAPI and Streamlit can run together with Docker Compose.