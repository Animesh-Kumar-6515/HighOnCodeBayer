

import json
from pathlib import Path
from typing import Dict, Any, List

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    MessageRole,
    FunctionTool,
    ToolSet
)
from azure.identity import DefaultAzureCredential


# ===================================================
# Log Agent Analysis Function
# ===================================================

def analyze_logs(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze logs provided via context and return findings + hypothesis.
    This agent NEVER decides final verdict.
    """

    incident = input_payload["incident"]
    context = input_payload["context"]

    incident_id = incident["incident_id"]
    logs = context.get("logs", {})

    findings: List[str] = []
    evidence: Dict[str, Any] = {}

    logs_text = json.dumps(logs).lower()

    if "timeout" in logs_text:
        findings.append("Application experienced database timeouts")
        evidence["timeouts"] = True

    if "retry" in logs_text:
        findings.append("Retry storms detected in application logs")
        evidence["retry_storms"] = True

    if "too many connections" in logs_text or "connection pool exhausted" in logs_text:
        findings.append("Database rejected connections due to connection limit")
        evidence["connection_exhaustion"] = True

    if "circuit" in logs_text:
        findings.append("Circuit breakers activated under load")
        evidence["circuit_breaker"] = True

    hypothesis = (
        "Log patterns indicate downstream database connection saturation "
        "triggering retries and circuit breaker activation"
    )

    return {
        "agent": "log_agent",
        "incident_id": incident_id,
        "findings": list(set(findings)),
        "evidence": evidence,
        "hypothesis": hypothesis,
        "confidence": 0.93
    }


# ===================================================
# Context Loader (LOGS ONLY)
# ===================================================

def load_log_context(incident_id: str) -> Dict[str, Any]:
    base = Path("mock-data") / "logs" / incident_id

    return {
        "high_level": json.load(open(base / "high_level.json")),
        "application": json.load(open(base / "application_logs.json")),
        "database": json.load(open(base / "database_logs.json")),
        "infrastructure": json.load(open(base / "infrastructure_logs.json")),
    }


# ===================================================
# Create Agents Client
# ===================================================

agents_client = AgentsClient(
    endpoint="",
    credential=DefaultAzureCredential()
)


# ===================================================
# Define Log Agent Tools
# ===================================================

log_agent_tools = ToolSet(
    tools=[
        FunctionTool.from_function(
            fn=analyze_logs,
            name="analyze_logs",
            description="Analyze application, database, and infrastructure logs"
        )
    ]
)


# ===================================================
# Create Log Agent
# ===================================================

log_agent = agents_client.agents.create(
    name="log_agent",
    description="Analyzes logs to identify failure patterns",
    tools=log_agent_tools,
    instructions="""
You are a Log Analysis Agent.

Rules:
- You ONLY analyze logs provided in context.
- You NEVER analyze metrics.
- You NEVER decide the final verdict.
- You return findings, evidence, hypothesis, and confidence.
- Be concise, factual, and evidence-based.
- Output structured JSON only.
"""
)


# ===================================================
# Example Run (Sprint-0 Demo)
# ===================================================

if __name__ == "__main__":

    INCIDENT_ID = "inc-db-5001"

    incident_payload = {
        "incident_id": INCIDENT_ID,
        "severity": "SEV-1"
    }

    log_context = load_log_context(INCIDENT_ID)

    log_agent_input = {
        "incident": incident_payload,
        "context": {
            "logs": log_context
        },
        "instructions": (
            "Analyze only the provided logs and return findings. "
            "Do not infer root cause beyond log evidence."
        )
    }

    # Create a thread
    thread = agents_client.threads.create()

    # Send context-enriched payload to Log Agent
    agents_client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=json.dumps(log_agent_input, indent=2)
    )

    # Run Log Agent
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=log_agent.id
    )

    print(f"Log agent run started: {run.id}")
