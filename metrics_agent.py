

import json
from typing import Dict, Any, List

from azure.ai.agents import AgentsClient
from azure.ai.agents.models import (
    MessageRole,
    FunctionTool,
    ToolSet
)
from azure.identity import DefaultAzureCredential


# ===================================================
# Metric Agent Analysis Function
# ===================================================

def analyze_metrics(input_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze metrics provided via context and return findings + hypothesis.
    This agent NEVER decides final verdict.
    """

    incident = input_payload["incident"]
    context = input_payload["context"]

    incident_id = incident["incident_id"]
    metrics = context.get("metrics", {})

    findings: List[str] = []
    evidence: Dict[str, Any] = {}

    metrics_text = json.dumps(metrics).lower()

    # --- Capacity / saturation signals ---
    if "connection" in metrics_text and ("1.0" in metrics_text or "100" in metrics_text):
        findings.append("Database active connections reached maximum capacity")
        evidence["db_connection_saturation"] = True

    # --- Scaling behavior ---
    if "replica" in metrics_text or "autoscale" in metrics_text:
        findings.append("Application autoscaled rapidly under traffic spike")
        evidence["autoscaling_event"] = True

    # --- Latency correlation ---
    if "latency" in metrics_text or "p99" in metrics_text or "p95" in metrics_text:
        findings.append("Latency increased in correlation with load and saturation")
        evidence["latency_spike"] = True

    # --- Resource utilization sanity check ---
    if "cpu" in metrics_text and "low" in metrics_text:
        findings.append("Database CPU remained underutilized during incident")
        evidence["cpu_not_bottleneck"] = True

    hypothesis = (
        "Metrics indicate database capacity constrained by connection limits "
        "rather than compute resources, amplified by application autoscaling"
    )

    return {
        "agent": "metric_agent",
        "incident_id": incident_id,
        "findings": list(set(findings)),
        "evidence": evidence,
        "hypothesis": hypothesis,
        "confidence": 0.91
    }


# ===================================================
# Context Loader (METRICS ONLY)
# ===================================================

def load_metric_context(incident_id: str) -> Dict[str, Any]:
    """
    Load metrics for an incident to simulate upstream orchestration.
    """
    from pathlib import Path

    base = Path("mock-data") / "metrics" / incident_id

    return {
        "application": json.load(open(base / "application_metrics.json")),
        "database": json.load(open(base / "database_metrics.json")),
        "infrastructure": json.load(open(base / "infrastructure_metrics.json")),
    }


# ===================================================
# Create Agents Client
# ===================================================

agents_client = AgentsClient(
    endpoint="",
    credential=DefaultAzureCredential()
)


# ===================================================
# Define Metric Agent Tools
# ===================================================

metric_agent_tools = ToolSet(
    tools=[
        FunctionTool.from_function(
            fn=analyze_metrics,
            name="analyze_metrics",
            description="Analyze application, database, and infrastructure metrics"
        )
    ]
)


# ===================================================
# Create Metric Agent
# ===================================================

metric_agent = agents_client.agents.create(
    name="metric_agent",
    description="Analyzes metrics to detect capacity, saturation, and scaling issues",
    tools=metric_agent_tools,
    instructions="""
You are a Metric Analysis Agent.

Rules:
- You ONLY analyze metrics provided in context.
- You NEVER analyze logs.
- You NEVER decide the final verdict.
- You focus on capacity, saturation, and scaling behavior.
- You return findings, evidence, hypothesis, and confidence.
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

    metric_context = load_metric_context(INCIDENT_ID)

    metric_agent_input = {
        "incident": incident_payload,
        "context": {
            "metrics": metric_context
        },
        "instructions": (
            "Analyze only the provided metrics and return findings. "
            "Do not infer root cause beyond metric evidence."
        )
    }

    # Create a thread
    thread = agents_client.threads.create()

    # Send context-enriched payload to Metric Agent
    agents_client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=json.dumps(metric_agent_input, indent=2)
    )

    # Run Metric Agent
    run = agents_client.runs.create(
        thread_id=thread.id,
        agent_id=metric_agent.id
    )

    print(f"Metric agent run started: {run.id}")
