from __future__ import annotations

from typing import Any

from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from config import settings
from core.guardrails import detect_action_intent, require_action_approval
from tools.customer_support_tools import (
    get_metric,
    get_support_schema,
    execute_read_query_tool
)


def build_sql_agent():
    llm = ChatOpenAI(model=settings.model_name, api_key=settings.openai_api_key)

    tools = [
        execute_read_query_tool,
        get_support_schema,
        get_metric,
    ]
    

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are ECommerceOps-Agent. "
                "You are a SQL Builder and use tools to execute a query and return the result as a pandas DataFrame. From the user input, you will determine if the request is read-only or requires an action. Execute read-only requests directly, but for any action requests, you must seek human approval before proceeding. Also, for read-only requests, you should only query the allowed tables: customers, orders, order_items, products, returns, refunds, inventory, shipments. "
                "Never execute destructive SQL. Always use the safe tools. If a request appears to require a refund, cancel, or return action, "
                "ask for human approval instead of executing the action."
            ),
            MessagesPlaceholder("agent_scratchpad"),
            ("user", "{input}"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


def classify_support_intent(message: str) -> str:
    action = detect_action_intent(message)
    if action:
        return action
    return "read_only_support_query"


def validate_support_request(message: str, approved_action: bool = False) -> dict[str, Any]:
    action = detect_action_intent(message)
    if action:
        approval = require_action_approval(action, approved_action)
        if not approval.allowed:
            return {"allowed": False, "reason": approval.reason, "action": action}
        return {"allowed": True, "reason": "Approved or not required", "action": action}
    return {"allowed": True, "reason": "Read-only request", "action": "read_only_support_query"}
