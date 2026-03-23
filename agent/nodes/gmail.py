"""
Node: gmail
Calls the Anthropic API with the Gmail MCP server attached to fetch and
filter action-needed emails from the last 24 hours.
"""

import json
import anthropic
from agent.state import AgentState, EmailItem
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

GMAIL_MCP_URL = "https://gmail.mcp.claude.com/mcp"

SYSTEM_PROMPT = """You are an email triage assistant. 
Use the Gmail tools to search for unread or recent emails from the last 24 hours.
Focus on emails that require action, a reply, or contain important information.
Ignore newsletters, notifications, and automated emails.

Return ONLY a valid JSON array with this exact structure — no markdown, no explanation:
[
  {
    "subject": "...",
    "sender": "Name <email@example.com>",
    "snippet": "...",
    "received": "...",
    "thread_id": "..."
  }
]

If there are no action-needed emails, return an empty array: []
"""


def gmail_node(state: AgentState) -> AgentState:
    """LangGraph node — fetches action-needed emails via Gmail MCP."""
    errors = list(state.get("errors", []))
    emails: list[EmailItem] = []

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Fetch action-needed emails from the last 24 hours for {state['target_date']}. "
                        "Return only the JSON array as instructed."
                    ),
                }
            ],
            mcp_servers=[
                {"type": "url", "url": GMAIL_MCP_URL, "name": "gmail"}
            ],
            betas=["mcp-client-2025-04-04"],
        )

        raw = ""
        for block in response.content:
            if block.type == "text":
                raw += block.text

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        parsed = json.loads(raw)
        emails = [EmailItem(**item) for item in parsed if isinstance(item, dict)]

    except Exception as e:
        errors.append(f"Gmail node: {e}")

    return {
        **state,
        "emails": emails,
        "errors": errors,
    }

