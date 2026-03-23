"""
FastAPI entry poiny for Notion OS
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date

from agent.graph import run_daily_brief

app = FastAPI(
	title="Notion OS",
	description="AI-powered developer operating system — GitHub + Gmail + GCal → Notion",
    version="1.0.0",
)

class RunBriefRequest(BaseModel):
	target_date: Optional[str] = None

class RunBriefResponse(BaseModel):
	target_date: str
	notion_brief_page_id: Optional[str] = None
	tasks_created: int
	pr_cards_created: int
	emails_processed: int
	prs_processed: int
	issues_processed: int
	errors: list[str]

@app.get("/health")
def health():
	return {"status": "ok", "date": date.today().isoformat()}

@app.post("/run-brief", response_model=RunBriefResponse)
def run_brie(request: RunBriefRequest = RunBriefRequest()):
	"""
	Triggers a full Notion OS run:
    1. Fetches GitHub PRs and issues
    2. Fetches action emails from Gmail
    3. Fetches calendar events from Google Calendar
    4. Synthesizes everything with Claude
    5. Writes the Daily Brief, Tasks, and PR cards to Notion
	"""
	try:
		state = run_daily_brief(target_date=request.target_date)
	except Exception as e:
		raise HTTPException(status_code=500, detail=str(e))
	
	return RunBriefResponse(
		target_date=state["target_date"],
        notion_brief_page_id=state.get("notion_brief_page_id"),
        tasks_created=len(state.get("notion_task_ids", [])),
        pr_cards_created=len(state.get("notion_pr_card_ids", [])),
        emails_processed=len(state.get("emails", [])),
        prs_processed=len(state.get("pull_requests", [])),
        issues_processed=len(state.get("github_issues", [])),
        errors=state.get("errors", []),
	)
