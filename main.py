import json
from pathlib import Path
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import ConnectedAgentTool, MessageRole
from azure.identity import DefaultAzureCredential


# -----------------------------
# Helper to load JSON files
# -----------------------------
def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------
# Load mock data
# -----------------------------
BASE_PATH = Path("data")
INCIDENT_ID = "inc-db-5001"

topology = load_json(BASE_PATH / "topology/production.json")
scenario = load_json(BASE_PATH / "scenarios/inc-db-5001-database-failure.json")

logs = {
    "high_level": load_json(BASE_PATH / f"logs/{INCIDENT_ID}/high_level.json"),
    "application": load_json(BASE_PATH / f"logs/{INCIDENT_ID}/application_logs.json"),
    "database": load_json(BASE_PATH / f"logs/{INCIDENT_ID}/database_logs.json"),
    "infrastructure": load_json(BASE_PATH / f"logs/{INCIDENT_ID}/infrastructure_logs.json"),
}

metrics = {
    "application": load_json(BASE_PATH / f"metrics/{INCIDENT_ID}/application_metrics.json"),
    "database": load_json(BASE_PATH / f"metrics/{INCIDENT_ID}/database_metrics.json"),
    "infrastructure": load_json(BASE_PATH / f"metrics/{INCIDENT_ID}/infrastructure_metrics.json"),
}


# -----------------------------
# Build Commander context
# -----------------------------
commander_context = f"""
SYSTEM CONTEXT:
You are the Commander Agent in an autonomous First Responder system.
You DO NOT analyze raw logs or metrics directly.
You coordinate investigation and reason ONLY over agent findings.

INCIDENT DETAILS:
Incident ID: {scenario["incident_id"]}
Severity: {scenario["severity"]}
Environment: {scenario["environment"]}

TOPOLOGY (REFERENCE ONLY):
{json.dumps(topology, indent=2)}

SCENARIO CONTEXT (REFERENCE ONLY):
{json.dumps(scenario, indent=2)}

OBSERVABILITY DATA (FOR AGENT CONTEXT — NOT FOR DIRECT ANALYSIS):

LOGS:
{json.dumps(logs, indent=2)}

METRICS:
{json.dumps(metrics, indent=2)}

AVAILABLE AGENTS:
- Logs Agent (Forensic Expert)
- Metrics Agent (Telemetry Analyst)

TASK:
1. Create an investigation plan
2. Assign tasks to Logs Agent and Metrics Agent
3. Wait for their findings
4. Aggregate findings using confidence-based reasoning
5. Identify the most probable root cause
6. Recommend ONE best action
7. Provide a short incident summary

RULES:
- Do NOT analyze logs or metrics yourself
- Trust sub-agent findings
- Be concise, structured, and explain your reasoning
"""

print(commander_context)


# -----------------------------
# Azure Agents setup
# -----------------------------
agents_client = AgentsClient(
    credential=DefaultAzureCredential(),
    endpoint="3"
)

# Fetch sub-agents
log_check_agent = agents_client.get_agent("asst_bBbVecYDUNwhSz1fclLrPLZg")
metric_check_agent = agents_client.get_agent("asst_pw6SSG8HiZ8ovpLtkPWG9HJq")

# Correct ConnectedAgentTool definitions
logs_tool = ConnectedAgentTool(
    id=log_check_agent.id,
    name="Logs Agent",
    description="Analyzes application, database, and infrastructure logs"
)

metrics_tool = ConnectedAgentTool(
    id=metric_check_agent.id,
    name="Metrics Agent",
    description="Analyzes latency, error rates, and system metrics"
)


with agents_client:
    commander_agent = agents_client.get_agent(
        agent_id=""
    )
    print(f"Commander agent ID: {commander_agent.id}")

    thread = agents_client.threads.create()
    print(f"Thread ID: {thread.id}")

    message = agents_client.messages.create(
        thread_id=thread.id,
        role=MessageRole.USER,
        content=commander_context
    )
    print(f"Message ID: {message.id}")

    # ✅ Attach tools here
    run = agents_client.runs.create_and_process(
        thread_id=thread.id,
        agent_id=commander_agent.id
        
    )

    print(f"Run finished with status: {run.status}")

    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    messages = agents_client.messages.list(thread_id=thread.id)
    for msg in messages:
        if msg.text_messages:
            print(f"{msg.role}: {msg.text_messages[-1].text.value}")
