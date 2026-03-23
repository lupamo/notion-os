"""
Node: github
Fetches open PRs and assigned issues from configured repos using the GitHub REST API.
"""

import httpx
from datetime import datetime, timezone
from agent.state import AgentState, PRItem, GithubIssue
from config import GITHUB_TOKEN, GITHUB_USERNAME, GITHUB_REPOS

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
BASE = "https://api.github.com"


def _format_dt(iso: str) -> str:
    """Return a short human-readable date string."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso


def fetch_pull_requests(repo: str, client: httpx.Client) -> list[PRItem]:
    """Fetch open PRs for a given repo that are relevant to the user."""
    prs: list[PRItem] = []
    resp = client.get(f"{BASE}/repos/{repo}/pulls", params={"state": "open", "per_page": 20})
    resp.raise_for_status()
    for pr in resp.json():
        # Include PRs authored by user OR that request user's review
        reviewers = [r["login"] for r in pr.get("requested_reviewers", [])]
        if pr["user"]["login"] != GITHUB_USERNAME and GITHUB_USERNAME not in reviewers:
            continue

        # Get diff stats from the PR commits endpoint
        files_changed = pr.get("changed_files", 0)
        additions = pr.get("additions", 0)
        deletions = pr.get("deletions", 0)

        prs.append(PRItem(
            title=pr["title"],
            repo=repo,
            author=pr["user"]["login"],
            url=pr["html_url"],
            files_changed=files_changed,
            lines_changed=additions + deletions,
            opened=_format_dt(pr["created_at"]),
            updated=_format_dt(pr["updated_at"]),
            number=pr["number"],
        ))
    return prs


def fetch_issues(repo: str, client: httpx.Client) -> list[GithubIssue]:
    """Fetch open issues assigned to the user in a given repo."""
    issues: list[GithubIssue] = []
    resp = client.get(
        f"{BASE}/repos/{repo}/issues",
        params={"state": "open", "assignee": GITHUB_USERNAME, "per_page": 20},
    )
    resp.raise_for_status()
    for issue in resp.json():
        if "pull_request" in issue:
            continue  
        issues.append(GithubIssue(
            title=issue["title"],
            repo=repo,
            number=issue["number"],
            url=issue["html_url"],
            body=(issue.get("body") or "")[:500],
            labels=[l["name"] for l in issue.get("labels", [])],
            created=_format_dt(issue["created_at"]),
        ))
    return issues


def github_node(state: AgentState) -> AgentState:
    """LangGraph node — fetches GitHub data and merges it into state."""
    all_prs: list[PRItem] = []
    all_issues: list[GithubIssue] = []
    errors: list[str] = list(state.get("errors", []))

    with httpx.Client(headers=HEADERS, timeout=15) as client:
        for repo in GITHUB_REPOS:
            try:
                all_prs.extend(fetch_pull_requests(repo, client))
            except Exception as e:
                errors.append(f"GitHub PRs [{repo}]: {e}")
            try:
                all_issues.extend(fetch_issues(repo, client))
            except Exception as e:
                errors.append(f"GitHub Issues [{repo}]: {e}")

    return {
        **state,
        "pull_requests": all_prs,
        "github_issues": all_issues,
        "errors": errors,
    }
