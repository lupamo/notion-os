"""
Node: notion_writer
Writes all synthesized data to Notion using the official Notion MCP server
via the MCP Python client — true MCP tool calls, no LLM middleman needed.
"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from agent.state import AgentState
from config import NOTION_API_KEY, NOTION_DAILY_BRIEFS_DB, NOTION_TASKS_DB, NOTION_PR_QUEUE_DB


def _get_server_params() -> StdioServerParameters:
    return StdioServerParameters(
        command="npx",
        args=["-y", "@notionhq/notion-mcp-server"],
        env={"OPENAPI_MCP_HEADERS": json.dumps({
            "Authorization": f"Bearer {NOTION_API_KEY}",
            "Notion-Version": "2022-06-28"
        })}
    )


async def _write_to_notion(state: AgentState) -> dict:
    """Opens one MCP session and fires all write operations through it."""
    results = {
        "brief_page_id": None,
        "task_ids": [],
        "pr_ids": [],
        "errors": list(state.get("errors", [])),
    }

    server_params = _get_server_params()

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ── 1. Daily Brief page
            try:
                meeting_count = len(state["calendar_events"])
                energy = "Low" if meeting_count >= 5 else "Medium" if meeting_count >= 3 else "High"

                brief_result = await session.call_tool(
                    "API-post-page",
                    arguments={
                        "parent": {"database_id": NOTION_DAILY_BRIEFS_DB},
                        "properties": {
                            "Title": {
                                "title": [{"text": {"content": f"Daily Brief — {state['target_date']}"}}]
                            },
                            "Date": {"date": {"start": state["target_date"]}},
                            "Status": {"select": {"name": "Draft"}},
                            "Energy Level": {"select": {"name": energy}},
                            "Open PRs": {"number": len(state["pull_requests"])},
                            "Action Emails": {"number": len(state["emails"])},
                            "Meetings Today": {"number": meeting_count},
                        },
                        "children": _markdown_to_blocks(state["brief_markdown"]),
                    }
                )
                page_id = brief_result.content[0].text
                parsed = json.loads(page_id) if isinstance(page_id, str) else page_id
                results["brief_page_id"] = parsed.get("id") if isinstance(parsed, dict) else None
            except Exception as e:
                results["errors"].append(f"MCP (daily brief): {e}")

            # ── 2. Task cards
            all_tasks = []
            for task in state.get("email_action_items", []):
                all_tasks.append({
                    "title": task.get("title", "Untitled Task"),
                    "source": task.get("source", "Email"),
                    "priority": task.get("priority", "P2 - Normal"),
                    "url": task.get("source_url", ""),
                    "summary": task.get("ai_summary", ""),
                })
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
                        "Title": {"title": [{"text": {"content": task["title"][:2000]}}]},
                        "Source": {"select": {"name": task["source"]}},
                        "Priority": {"select": {"name": task["priority"]}},
                        "Status": {"select": {"name": "Inbox"}},
                        "AI Summary": {"rich_text": [{"text": {"content": task["summary"][:2000]}}]},
                    }
                    if task["url"]:
                        props["Source URL"] = {"url": task["url"]}

                    res = await session.call_tool(
                        "API-post-page",
                        arguments={
                            "parent": {"database_id": NOTION_TASKS_DB},
                            "properties": props,
                        }
                    )
                    raw = json.loads(res.content[0].text)
                    results["task_ids"].append(raw.get("id", ""))
                except Exception as e:
                    results["errors"].append(f"MCP (task): {e}")

            # ── 3. PR cards
            summaries = state.get("pr_summaries", {})
            for pr in state.get("pull_requests", []):
                try:
                    props = {
                        "Title": {"title": [{"text": {"content": f"[{pr['repo']}] PR #{pr['number']} — {pr['title']}"[:2000]}}]},
                        "Repo": {"select": {"name": pr["repo"].split("/")[-1]}},
                        "Author": {"rich_text": [{"text": {"content": pr["author"]}}]},
                        "Status": {"select": {"name": "Needs Review"}},
                        "PR URL": {"url": pr["url"]},
                        "Files Changed": {"number": pr["files_changed"]},
                        "Lines Changed": {"number": pr["lines_changed"]},
                        "AI Summary": {"rich_text": [{"text": {"content": summaries.get(pr["number"], "")[:2000]}}]},
                        "Opened": {"date": {"start": pr["opened"]}},
                    }
                    res = await session.call_tool(
                        "API-post-page",
                        arguments={
                            "parent": {"database_id": NOTION_PR_QUEUE_DB},
                            "properties": props,
                        }
                    )
                    raw = json.loads(res.content[0].text)
                    results["pr_ids"].append(raw.get("id", ""))
                except Exception as e:
                    results["errors"].append(f"MCP (PR card): {e}")

    return results


def _markdown_to_blocks(md: str) -> list[dict]:
    """Convert markdown to Notion block objects."""
    blocks = []
    for line in md.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block", "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]}
            })
        elif stripped.startswith("- "):
            blocks.append({
                "object": "block", "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]}
            })
        else:
            blocks.append({
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": stripped}}]}
            })
    return blocks


def notion_writer_node(state: AgentState) -> AgentState:
    """LangGraph node — writes everything to Notion via MCP."""
    results = asyncio.run(_write_to_notion(state))

    return {
        **state,
        "notion_brief_page_id": results["brief_page_id"],
        "notion_task_ids": results["task_ids"],
        "notion_pr_card_ids": results["pr_ids"],
        "errors": results["errors"],
    }

