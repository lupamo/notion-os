"""
Node: synthesize
Uses Claude to:
  1. Generate plain-English summaries for each PR
  2. Extract action items from emails
  3. Write the full daily brief body
"""

import json
import anthropic
from agent.state import AgentState
from agent.prompts import PR_SUMMARY_SYSTEM, EMAIL_EXTRACTION_SYSTEM, DAILY_BRIEF_SYSTEM
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, GITHUB_USERNAME

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _call_claude(system: str, user: str, max_tokens: int = 1024) -> str:
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


def _summarize_prs(state: AgentState) -> dict[int, str]:
    if not state["pull_requests"]:
        return {}

    prs_text = "\n\n".join(
        f"PR #{pr['number']} — {pr['title']}\n"
        f"Repo: {pr['repo']}\n"
        f"Author: {pr['author']}\n"
        f"Files changed: {pr['files_changed']}, Lines: {pr['lines_changed']}\n"
        f"URL: {pr['url']}"
        for pr in state["pull_requests"]
    )
    raw = _call_claude(PR_SUMMARY_SYSTEM, f"Summarize these PRs:\n\n{prs_text}", max_tokens=1024)

    # Build a simple map: try to associate each paragraph with a PR number
    summaries: dict[int, str] = {}
    paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
    for i, pr in enumerate(state["pull_requests"]):
        summaries[pr["number"]] = paragraphs[i] if i < len(paragraphs) else "See PR for details."
    return summaries


def _extract_email_tasks(state: AgentState) -> list[dict]:
    if not state["emails"]:
        return []

    emails_text = "\n\n".join(
        f"Subject: {e['subject']}\nFrom: {e['sender']}\nReceived: {e['received']}\nSnippet: {e['snippet']}"
        for e in state["emails"]
    )
    raw = _call_claude(EMAIL_EXTRACTION_SYSTEM, f"Extract action items from these emails:\n\n{emails_text}")

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        return []


def _generate_brief(state: AgentState, pr_summaries: dict[int, str], email_tasks: list[dict]) -> str:
    # Build a rich context block for the brief prompt
    cal_text = "\n".join(
        f"- {e['start']} → {e['title']} ({', '.join(e['attendees'][:3]) if e['attendees'] else 'no attendees'})"
        for e in state["calendar_events"]
    ) or "No meetings today."

    email_text = "\n".join(
        f"- From {e['sender']}: {e['subject']}"
        for e in state["emails"]
    ) or "No action emails."

    pr_text = "\n".join(
        f"- PR #{pr['number']} in {pr['repo']} by {pr['author']}: {pr_summaries.get(pr['number'], '')}"
        for pr in state["pull_requests"]
    ) or "No open PRs."

    issues_text = "\n".join(
        f"- #{i['number']} [{i['repo']}]: {i['title']}"
        for i in state["github_issues"]
    ) or "No open issues assigned."

    user_prompt = (
        f"Date: {state['target_date']}\n"
        f"Developer: {GITHUB_USERNAME}\n\n"
        f"CALENDAR:\n{cal_text}\n\n"
        f"EMAILS NEEDING ACTION:\n{email_text}\n\n"
        f"PULL REQUESTS:\n{pr_text}\n\n"
        f"GITHUB ISSUES:\n{issues_text}\n"
    )

    system = DAILY_BRIEF_SYSTEM.replace("{name}", GITHUB_USERNAME)
    return _call_claude(system, user_prompt, max_tokens=2048)


def synthesize_node(state: AgentState) -> AgentState:
    """LangGraph node — synthesizes all collected data into a full daily brief."""
    errors = list(state.get("errors", []))
    pr_summaries: dict[int, str] = {}
    email_tasks: list[dict] = []
    brief_markdown = ""

    try:
        pr_summaries = _summarize_prs(state)
    except Exception as e:
        errors.append(f"Synthesis (PR summaries): {e}")

    try:
        email_tasks = _extract_email_tasks(state)
    except Exception as e:
        errors.append(f"Synthesis (email tasks): {e}")

    try:
        brief_markdown = _generate_brief(state, pr_summaries, email_tasks)
    except Exception as e:
        errors.append(f"Synthesis (brief): {e}")
        brief_markdown = f"# Daily Brief — {state['target_date']}\n\n*Brief generation failed. Check logs.*"

    return {
        **state,
        "pr_summaries": pr_summaries,
        "email_action_items": email_tasks,
        "brief_markdown": brief_markdown,
        "errors": errors,
    }
