"""
LangGraph state machine definition for Notion OS
"""

from asyncio import graph
from datetime import date
from langgraph.graph import StateGraph, START, END

from agent.state import AgentState
from agent.nodes.github import github_node
from agent.nodes.gmail import gmail_node
from agent.nodes.gcal import gcal_node
from agent.nodes.synthesize import synthesize_node
from agent.nodes.notion import notion_writer_node

def build_graph() -> StateGraph:
	graph = StateGraph(AgentState)

	#register nodes
	graph.add_node("github", github_node)
	graph.add_node("gmail", gmail_node)
	graph.add_node("gcal", gcal_node)
	graph.add_node("synthesize", synthesize_node)
	graph.add_node("notion_writer", notion_writer_node)

	#Fan out from start to all data sources
	graph.add_edge(START, "github")
	graph.add_edge("github", "gmail")
	graph.add_edge("gmail", "gcal")
	graph.add_edge("gcal", "synthesize")


	#Then to notion writer and end
	graph.add_edge("synthesize", "notion_writer")
	graph.add_edge("notion_writer", END)

	return graph.compile()

def run_daily_brief(target_date: str | None = None) -> AgentState:
	"""
	Entry point builds the graph and runs it for a given date
	Default to today if no date provided
	"""

	if target_date is None:
		target_date = date.today().isoformat()

	initial_state: AgentState = {
		"target_date": target_date,
		"pull_requests": [],
		"github_issues": [],
		"emails": [],
		"calendar_events": [],
		"pr_summaries": [],
		"email_action_items": [],
		"brief_markdown": "",
		"notion_brief_page_id": None,
		"notion_task_ids": [],
		"notion_pr_card_ids": [],
		"errors": [],
	}

	app = build_graph()
	final_state: AgentState = app.invoke(initial_state)
	return final_state

