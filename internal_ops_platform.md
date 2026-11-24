# Internal operations platform view

This project is now organized to behave like an internal operations platform, not just a demo app.

## Operational experience

- Secure login for support agents and operations managers
- Role-aware access to approval workflows
- Approval dashboard with approve / reject / cancel buttons
- KPI cards for revenue, return rate, and inventory health
- Audit log and request history for operational compliance
- Read-only SQL support by default for all support conversations
- Controlled escalation for actions requiring approval

## Example roles

- support_agent
- operations_manager
- finance_analyst

## Example logins

- support_agent / support123
- ops_manager / ops123
- finance_analyst / finance123

## Security design

- Built-in username/password auth for local demo purposes
- Role-based access pattern for future enterprise integration with Active Directory, SSO, or OAuth
- Approval decisions logged with actor and comments
- All sensitive actions require explicit human approval

## Production-ready readiness

This is suitable for:

- internal support operations dashboards
- e-commerce service centers
- order and return governance workflows
- executive KPI snapshots and support analytics

## Recommended next production improvements

- Replace demo auth with SSO / Azure AD / Okta
- Store approval records in a relational table instead of JSONL
- Add RBAC and permission checks on each route / action
- Add user session management and audit trail at the UI layer
- Deploy behind a reverse proxy with HTTPS and environment variables
- Add background jobs for refund processing and order operations
