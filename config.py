import os
from dotenv import load_dotenv

load_dotenv()

# ── Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ── Notion 
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

NOTION_PARENT_PAGE_ID    = "32c27e20adc180d9a7bbe3f0425a938d"
NOTION_DAILY_BRIEFS_DB   = "32c27e20adc180099c29ea8b519a685b"
NOTION_TASKS_DB          = "32c27e20adc180059e08f85ac1bdac12"
NOTION_PR_QUEUE_DB       = "32c27e20adc18058a009f0b49af4339a"

# ── GitHub 
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

GITHUB_REPOS    = [r.strip() for r in os.getenv("GITHUB_REPOS", "").split(",") if r.strip()]

# ── Model 
CLAUDE_MODEL    = "claude-sonnet-4-20250514"
MAX_TOKENS      = 2048
