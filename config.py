import os
from dotenv import load_dotenv

load_dotenv()

# ── Groq
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")
GROQ_MODEL    = "llama-3.3-70b-versatile"

# ── Notion 
NOTION_API_KEY = os.getenv("NOTION_API_KEY")

NOTION_PARENT_PAGE_ID    = "32c27e20adc180d9a7bbe3f0425a938d"
NOTION_DAILY_BRIEFS_DB   = "aa2ce65c503842d288a8153eb7c6c4ad"
NOTION_TASKS_DB          = "47157ed5cb4d492d8f28f7b8b21ee7d1"
NOTION_PR_QUEUE_DB       = "6dc690512a284a6e911a29575a9015ac"

# ── GitHub 
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")

GITHUB_REPOS    = [r.strip() for r in os.getenv("GITHUB_REPOS", "").split(",") if r.strip()]

