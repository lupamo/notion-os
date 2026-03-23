"""
Node: gcal
Fetches today's and tomorrow's calendar events using Google Calendar API directly.
"""

import pickle
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from agent.state import AgentState, CalendarEvent

TOKEN_PATH = "token.pickle"


def _get_calendar_service():
    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return build("calendar", "v3", credentials=creds)


def gcal_node(state: AgentState) -> AgentState:
    errors = list(state.get("errors", []))
    events: list[CalendarEvent] = []

    try:
        service = _get_calendar_service()
        now = datetime.now(timezone.utc)
        time_min = now.replace(hour=0, minute=0, second=0).isoformat()
        time_max = (now + timedelta(days=2)).replace(
            hour=0, minute=0, second=0
        ).isoformat()

        result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=20,
        ).execute()

        for item in result.get("items", []):
            start = item["start"].get("dateTime", item["start"].get("date", ""))
            end = item["end"].get("dateTime", item["end"].get("date", ""))
            if not item["start"].get("dateTime"):
                continue  # skip all-day events

            attendees = [
                a.get("displayName") or a.get("email", "")
                for a in item.get("attendees", [])
            ]

            events.append(CalendarEvent(
                title=item.get("summary", "Untitled"),
                start=start,
                end=end,
                attendees=attendees,
                location=item.get("location"),
                description=item.get("description"),
            ))

    except FileNotFoundError:
        errors.append("GCal node: token.pickle not found — run auth_setup.py first")
    except Exception as e:
        errors.append(f"GCal node: {e}")

    return {**state, "calendar_events": events, "errors": errors}