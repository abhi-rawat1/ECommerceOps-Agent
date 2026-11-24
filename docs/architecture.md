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
    User[Viewer or Operations User] --> UI[Streamlit UI Dashboard]
    UI --> API[FastAPI]
    subgraph FastAPIServer ["FastAPIServer "]
        API --> Auth[JWT and RBAC Autorization]
        Auth --> Process[New Request]
        Auth --> Resume[Resume Request]
        
        subgraph Traces ["LangGraph Workflow with Guardrails & Trace/Langfuse Events "]
            Resume --> MergedState[Merge original request and follow-up answer]
            Process --> LLMAgentIntentDetection{LLM Agent Intent Detection}
            MergedState --> LLMAgentIntentDetection{LLM Agent Intent Detection}
            LLMAgentIntentDetection -->|Metrics| Metrics[Semantic DBT Metrics Definitions]
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
        
        classDef subboxhighlight1 fill:#90EE90,stroke:#90EE90,stroke-width:3px,color:#1b5e20
        class Traces subboxhighlight1

        Auth --> Approval[Approval Workflow- Cancel/Approve/Reject]
        Approval --> |Update Approval Request| DB1[(PostgreSQL)]
    end
    classDef boxhighlight fill:#e8f5e9,stroke:#2e7d32,stroke-width:3px,color:#1b5e20
    class FastAPIServer boxhighlight
    Response --> UI1[Streamlit UI Dashboard]
    DB1 -->  UI1[Streamlit UI Dashboard]
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