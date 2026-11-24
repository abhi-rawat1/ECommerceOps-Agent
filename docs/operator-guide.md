# Operator Guide

## Roles

### Support Agent

- Ask natural-language questions.
- Look up orders and customers.
- Review inventory and semantic metrics.
- Submit return, cancellation, and refund requests for approval.

### Operations Manager

- Perform support-agent actions.
- Review pending approvals.
- Approve, reject, or cancel controlled actions.
- Review operational audit events.

### Finance Analyst

- Review metrics and support analytics.
- View approval history.
- Review audit evidence.

## Approval lifecycle

Controlled actions use these statuses:

- `pending`
- `approved`
- `rejected`
- `cancelled`

A cancellation or return should include the affected order and reason. Refund decisions should be supported by order, item, payment, and policy evidence.

## Audit behavior

The application records workflow decisions, approval state changes, and query or action evidence. Audit retention and export must be implemented according to organizational requirements before production use.

## Human review boundaries

ECommerceOps-Agent does not execute a write action merely because the model proposes it. Read-only database access is the default, and high-risk actions require an explicit approval path.
