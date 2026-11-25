CREATE TABLE IF NOT EXISTS ecommerce.agent_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    title TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS ecommerce.agent_conversation_turns (
    id VARCHAR(255) PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES ecommerce.agent_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ecommerce.agent_workflow_state (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    request_id VARCHAR(255),
    state JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    FOREIGN KEY (session_id) REFERENCES ecommerce.agent_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ecommerce.agent_memories (
    id VARCHAR(255) PRIMARY KEY,
    scope VARCHAR(50) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    memory_key VARCHAR(255) NOT NULL,
    memory_value JSONB NOT NULL,
    source_request_id VARCHAR(255),
    confidence DOUBLE PRECISION,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (scope, owner_id, memory_type, memory_key)
);

CREATE INDEX IF NOT EXISTS idx_agent_sessions_user ON ecommerce.agent_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_agent_turns_session ON ecommerce.agent_conversation_turns(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_agent_workflow_status ON ecommerce.agent_workflow_state(status);
CREATE INDEX IF NOT EXISTS idx_agent_memories_owner ON ecommerce.agent_memories(scope, owner_id);
