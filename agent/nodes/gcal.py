"""
Node: gcal
Calls the Anthropic API with the Google Calendar MCP server attached to fetch
today's and tomorrow's calendar events.
"""

import json
import anthropic
from agent.state import AgentState, CalendarEvent
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

GCAL_MCP_URL = "https://gcal.mcp.claude.com/mcp"

SYSTEM_PROMPT = """You are a calendar assistant.
Use the Google Calendar tools to fetch events for today and tomorrow.
Include all events that have a start time (skip all-day events with no time).

Return ONLY a valid JSON array with this exact structure — no markdown, no explanation:
[
  {
    "title": "...",
    "start": "2026-03-23T09:00:00",
    "end": "2026-03-23T10:00:00",
    "attendees": ["name <email>"],
    "location": "...",
    "description": "..."
  }
]

For attendees, location, and description: use null if not present.
If there are no events, return an empty array: []
"""


def gcal_node(state: AgentState) -> AgentState:
    """LangGraph node — fetches calendar events via Google Calendar MCP."""
    errors = list(state.get("errors", []))
    events: list[CalendarEvent] = []

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
                        f"Fetch all calendar events for today ({state['target_date']}) "
                        "and tomorrow. Return only the JSON array as instructed."
                    ),
                }
            ],
            mcp_servers=[
                {"type": "url", "url": GCAL_MCP_URL, "name": "gcal"}
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
        events = [CalendarEvent(**item) for item in parsed if isinstance(item, dict)]

    except Exception as e:
        errors.append(f"GCal node: {e}")

    return {
        **state,
        "calendar_events": events,
        "errors": errors,
    }
