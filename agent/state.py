from typing import TypeDict, Optional
from datetime import date

class PRItem(TypeDict):
	title: str
	repo: str
	author: str
	url: str
	files_changed: int
	lines_changed: int
	opened: str
	updated: str
	number: int

class EmailItem(TypeDict):
	subject: str
	sender: str
	snippet: str
	received: str
	thread_id: str

class CalendarEvent(TypeDict):
	title: str
	start: str
	end: str
	attendees: list[str]
	location: Optional[str]
	description: Optional[str]

class GithubIssue(TypeDict):
	title: str
	repo: str
	number: int
	url: str
	body: str
	labels: list[str]
	created: str

class AgentState(TypeDict):
	target_date: str
	pull_requests: list[PRItem]
	github_issues: list[GithubIssue]
	emails: list[EmailItem]
	calendar_events: list[CalendarEvent]
	pr_summaries: list[str]
	email_action_items: list[str]
	brief_markdown: str
	notion_brief_page_id: Optional[str]
	notion_task_ids: list[str]
	notion_pr_card_ids: list[str]
	errors: list[str]
