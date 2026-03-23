"""
Node: gmail
Fetches action-needed emails from the last 24 hours using Gmail API directly.
"""

import pickle
import base64
import os
from datetime import datetime, timedelta, timezone
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from agent.state import AgentState, EmailItem

TOKEN_PATH = "token.pickle"


def _get_gmail_service():
    with open(TOKEN_PATH, "rb") as f:
        creds = pickle.load(f)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)
    return build("gmail", "v1", credentials=creds)


def _decode_snippet(snippet: str) -> str:
    return snippet or ""


def gmail_node(state: AgentState) -> AgentState:
    errors = list(state.get("errors", []))
    emails: list[EmailItem] = []

    try:
        service = _get_gmail_service()
        # Search for unread emails from last 24h, excluding promotions/social
        query = "is:unread newer_than:1d -category:promotions -category:social"
        result = service.users().messages().list(
            userId="me", q=query, maxResults=15
        ).execute()

        messages = result.get("messages", [])
        for msg in messages:
            detail = service.users().messages().get(
                userId="me", messageId=msg["id"], format="metadata",
                metadataHeaders=["Subject", "From", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            emails.append(EmailItem(
                subject=headers.get("Subject", "(no subject)"),
                sender=headers.get("From", "Unknown"),
                snippet=detail.get("snippet", "")[:200],
                received=headers.get("Date", ""),
                thread_id=detail.get("threadId", ""),
            ))

    except FileNotFoundError:
        errors.append("Gmail node: token.pickle not found — run auth_setup.py first")
    except Exception as e:
        errors.append(f"Gmail node: {e}")

    return {**state, "emails": emails, "errors": errors}