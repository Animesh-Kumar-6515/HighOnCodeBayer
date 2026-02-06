


from typing import Dict, Any, List
import json
from pathlib import Path

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    MessageRole,
    FunctionTool,
    ToolSet
)
from azure.identity import DefaultAzureCredential


# ===================================================
# Commander Agent Tool Functions
# ===================================================

def decide_agents(incident: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decide which diagnostic agents to invoke based on expected symptoms.
    """
    expected = str(incident.get("expected_symptoms", {})).lower()
    agents: List[str] = []

    if any(k in expected for k in [
        "latency", "timeout", "retry", "error",
        "circuit", "failure"
    ]):
        agents.append("logs_agent")

    if any(k in expected for k in [
        "capacity", "exhaustion", "connections",
        "autoscaling", "saturation", "usage"
    ]):
        agents.append("metrics_agent")

    if any(k in expected for k in [
        "deployment", "config", "change", "release"
    ]):
        agents.append("deploy_intelligence_agent")

    return {
        "incident_id": incident["incident_id"],
        "agents_to_call": list(set(agents))
    }


def synthesize_verdict(
    incident: Dict[str, Any],
    agent_findings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Commander-only synthesis of final incident verdict.
    """
    combined_text = " ".join(
        json.dumps(f).lower() for f in agent_findings
    )

    failure_summary = []
    remediation = {
        "immediate": [],
        "short_term": [],
        "long_term": []
    }

    root_cause = "Undetermined"

    if "connection" in combined_text or "dbtimeout" in combined_text:
        root_cause = (
            "Database connection pool exhaustion caused by "
            "application scaling without corresponding database capacity"
        )
        failure_summary.append(
            "Database max_connections limit exceeded"
        )
        remediation["immediate"].append(
            "Increase database max_connections temporarily"
        )

    if "retry" in combined_text:
        failure_summary.append(
            "Retry storms amplified database pressure"
        )

    if "autoscaling" in combined_text:
        failure_summary.append(
            "Application autoscaled without database capacity alignment"
        )
        remediation["short_term"].append(
            "Reduce application replica count"
        )

    if "deployment" in combined_text or "config" in combined_text:
        remediation["immediate"].append(
            "Rollback recent configuration deployment"
        )

    remediation["long_term"].extend([
        "Introduce centralized connection pooling",
        "Implement capacity-aware autoscaling",
        "Add read replicas or shard database workload"
    ])

    return {
        "incident_id": incident["incident_id"],
        "severity": incident["severity"],
        "root_cause": root_cause,
        "failure_summary": failure_summary,
        "recommended_actions": remediation,
        "confidence": 0.92
    }


# ===================================================
# Context Loader (Topology + Scenario)
# ===================================================

def load_context_data() -> Dict[str, Any]:
    base = Path("mock-data")

    return {
        "topology": json.load(open(base / "topology/production.json")),
        "scenario": json.load(
            open(base / "scenarios/inc-db-5001-database-failure.json")
        ),
        "data_references": {
            "logs": [
                "high_level",
                "application",
                "database",
                "infrastructure"
            ],
            "metrics": [
                "application",
                "database",
                "infrastructure"
            ]
        }
    }


# ===================================================
# Azure Agents Client
# ===================================================

agents_client = AgentsClient(
    endpoint="",
    credential=DefaultAzureCredential()
)


# ===================================================
# Commander Agent Definition
# ===================================================

commander_tools = ToolSet(
    tools=[
        FunctionTool.from_function(
            fn=decide_agents,
            name="decide_agents",
            description="Decide which diagnostic agents to invoke"
        ),
        FunctionTool.from_function(
            fn=synthesize_verdict,
            name="synthesize_verdict",
            description="Generate the final incident verdict from agent findings"
        )
    ]
)

commander_agent = agents_client.agents.create(
    name="commander_agent",
    description=(
        "Autonomous Incident Commander responsible for "
        "planning investigations and synthesizing final verdicts."
    ),
    tools=commander_tools,
    instructions="""
You are the Incident Commander.

Rules:
- You do NOT analyze raw logs or metrics.
- You use context only to understand system structure.
- You decide which agents to invoke.
- You wait for findings from diagnostic agents.
- You synthesize the final incident verdict.
- Your verdict is authoritative and final.

Always output structured JSON.
"""
)


# ===================================================
# Example Execution (Sprint-0 Demo)
# ===================================================

if __name__ == "__main__":

    context_data = load_context_data()

    incident_payload = {
        "incident_id": "inc-db-5001",
        "title": "Database connection pool exhaustion",
        "category": "database_failure",
        "severity": "SEV-1",
        "environment": "production",
        "affected_services": ["payment-api", "orders-db"],
        "expected_symptoms": {
            "application": [
                "increased latency",
                "database timeouts",
                "retry storms"
            ],
            "database": [
                "high connection usage",
                "connection pool exhaustion"
            ],
            "infrastructure": [
                "autoscaling mismatch"
            ]
        }
    }

    commander_input = {
        "incident": incident_payload,
        "context": context_data,
        "instructions": (
            "Use context for planning only. "
            "Do not analyze logs or metrics. "
            "Decide agents, await findings, and produce final verdict."
        )
    }

    # Create a thread
    thread = agents_client.threads.create()

    # Send enriched context to Commander
    agents_client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=json.dumps(commander_input, indent=2)
    )

    # Run Commander Agent
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=commander_agent.id
    )

    print(f"Commander run started: {run.id}")
