CREATE SCHEMA IF NOT EXISTS ecommerce;

CREATE TABLE IF NOT EXISTS ecommerce.support_users (
    id VARCHAR(255) PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ecommerce.approval_requests (
    id VARCHAR(255) PRIMARY KEY,
    request_id VARCHAR(255) UNIQUE NOT NULL,
    order_id VARCHAR(255) NOT NULL,
    action_type VARCHAR(255) NOT NULL,
    reason TEXT NOT NULL,
    requested_by VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    approved_by VARCHAR(255),
    comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO ecommerce.support_users (id, username, password, role, name, is_active)
VALUES
    ('usr-support_agent', 'support_agent', 'support123', 'support_agent', 'Support Agent', TRUE),
    ('usr-ops_manager', 'ops_manager', 'ops123', 'operations_manager', 'Operations Manager', TRUE),
    ('usr-finance_analyst', 'finance_analyst', 'finance123', 'finance_analyst', 'Finance Analyst', TRUE)
ON CONFLICT (username) DO NOTHING;
