"""
Node: notion_writer
Writes all synthesized data to Notion:
  1. Daily Brief page (rich page body)
  2. Task cards in the Tasks database
  3. PR cards in the PR Review Queue database
"""

from notion_client import Client
from agent.state import AgentState
from config import (
    NOTION_API_KEY,
    NOTION_DAILY_BRIEFS_DB,
    NOTION_TASKS_DB,
    NOTION_PR_QUEUE_DB,
)

notion = Client(auth=NOTION_API_KEY)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _markdown_to_notion_blocks(md: str) -> list[dict]:
    """
    Converts a subset of markdown to Notion block objects.
    Handles: ## headings, **bold** (in paragraphs), - bullet lists, --- dividers.
    """
    blocks = []
    for line in md.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if stripped == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})

        elif stripped.startswith("## "):
            text = stripped[3:]
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            })

        elif stripped.startswith("- "):
            text = stripped[2:]
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": text}}]
                },
            })

        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": stripped}}]
                },
            })

    return blocks


def _prop_title(text: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}


def _prop_select(value: str) -> dict:
    return {"select": {"name": value}}


def _prop_rich_text(text: str) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": text[:2000]}}]}


def _prop_url(url: str) -> dict:
    return {"url": url or None}


def _prop_number(n: int) -> dict:
    return {"number": n}


def _prop_date(date_str: str) -> dict:
    return {"date": {"start": date_str}}


# ── Writers ──────────────────────────────────────────────────────────────────

def write_daily_brief(state: AgentState) -> str:
    """Creates a Daily Brief page in the Daily Briefs database."""
    title = f"Daily Brief — {state['target_date']}"

    # Determine energy level from meeting count
    meeting_count = len(state["calendar_events"])
    if meeting_count >= 5:
        energy = "Low"
    elif meeting_count >= 3:
        energy = "Medium"
    else:
        energy = "High"

    page = notion.pages.create(
        parent={"database_id": NOTION_DAILY_BRIEFS_DB},
        properties={
            "Title": _prop_title(title),
            "Date": _prop_date(state["target_date"]),
            "Status": _prop_select("Draft"),
            "Energy Level": _prop_select(energy),
            "Open PRs": _prop_number(len(state["pull_requests"])),
            "Action Emails": _prop_number(len(state["emails"])),
            "Meetings Today": _prop_number(meeting_count),
        },
        children=_markdown_to_notion_blocks(state["brief_markdown"]),
    )
    return page["id"]


def write_tasks(state: AgentState, brief_page_id: str) -> list[str]:
    """Writes email-extracted tasks + GitHub issues to the Tasks database."""
    task_ids: list[str] = []
    all_tasks = []

    # From email extraction
    for task in state.get("email_action_items", []):
        all_tasks.append({
            "title": task.get("title", "Untitled Task"),
            "source": task.get("source", "Email"),
            "priority": task.get("priority", "P2 - Normal"),
            "url": task.get("source_url", ""),
            "summary": task.get("ai_summary", ""),
        })

    # From GitHub issues
    for issue in state.get("github_issues", []):
        all_tasks.append({
            "title": f"[{issue['repo']}] #{issue['number']}: {issue['title']}",
            "source": "GitHub Issue",
            "priority": "P2 - Normal",
            "url": issue["url"],
            "summary": issue.get("body", "")[:500],
        })

    for task in all_tasks:
        try:
            props = {
                "Title": _prop_title(task["title"]),
                "Source": _prop_select(task["source"]),
                "Priority": _prop_select(task["priority"]),
                "Status": _prop_select("Inbox"),
                "AI Summary": _prop_rich_text(task["summary"]),
            }
            if task["url"]:
                props["Source URL"] = _prop_url(task["url"])

            page = notion.pages.create(
                parent={"database_id": NOTION_TASKS_DB},
                properties=props,
            )
            task_ids.append(page["id"])
        except Exception:
            pass  # individual task failures shouldn't abort the run

    return task_ids


def write_pr_cards(state: AgentState) -> list[str]:
    """Writes open PRs to the PR Review Queue database."""
    pr_ids: list[str] = []
    summaries = state.get("pr_summaries", {})

    for pr in state.get("pull_requests", []):
        try:
            summary = summaries.get(pr["number"], "")
            title = f"[{pr['repo']}] PR #{pr['number']} — {pr['title']}"
            props = {
                "Title": _prop_title(title),
                "Repo": _prop_select(pr["repo"].split("/")[-1]),
                "Author": _prop_rich_text(pr["author"]),
                "Status": _prop_select("Needs Review"),
                "PR URL": _prop_url(pr["url"]),
                "Files Changed": _prop_number(pr["files_changed"]),
                "Lines Changed": _prop_number(pr["lines_changed"]),
                "AI Summary": _prop_rich_text(summary),
                "Opened": _prop_date(pr["opened"]) if pr["opened"] else {"date": None},
            }
            page = notion.pages.create(
                parent={"database_id": NOTION_PR_QUEUE_DB},
                properties=props,
            )
            pr_ids.append(page["id"])
        except Exception:
            pass

    return pr_ids


# ── Node

def notion_writer_node(state: AgentState) -> AgentState:
    """LangGraph node — writes everything to Notion."""
    errors = list(state.get("errors", []))
    brief_page_id = None
    task_ids: list[str] = []
    pr_card_ids: list[str] = []

    try:
        brief_page_id = write_daily_brief(state)
    except Exception as e:
        errors.append(f"Notion (daily brief): {e}")

    try:
        task_ids = write_tasks(state, brief_page_id or "")
    except Exception as e:
        errors.append(f"Notion (tasks): {e}")

    try:
        pr_card_ids = write_pr_cards(state)
    except Exception as e:
        errors.append(f"Notion (PR cards): {e}")

    return {
        **state,
        "notion_brief_page_id": brief_page_id,
        "notion_task_ids": task_ids,
        "notion_pr_card_ids": pr_card_ids,
        "errors": errors,
    }
