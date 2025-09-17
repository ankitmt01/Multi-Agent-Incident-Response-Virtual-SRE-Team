
import json, httpx
from .config import SLACK_WEBHOOK_URL, JIRA_BASE_URL, JIRA_API_TOKEN, JIRA_PROJECT_KEY

async def notify_slack(text: str):
    if not SLACK_WEBHOOK_URL: return False
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(SLACK_WEBHOOK_URL, json={"text": text})
        return r.status_code in (200, 204)

# NEW: send blocks (for interactive buttons)
async def notify_slack_blocks(text: str, blocks: list):
    if not SLACK_WEBHOOK_URL: return False
    payload = {"text": text, "blocks": blocks}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(SLACK_WEBHOOK_URL, json=payload)
        return r.status_code in (200, 204)

async def create_jira_ticket(summary: str, description: str):
    if not (JIRA_BASE_URL and JIRA_API_TOKEN and JIRA_PROJECT_KEY): return None
    url = f"{JIRA_BASE_URL.rstrip('/')}/rest/api/3/issue"
    headers = {"Authorization": f"Bearer {JIRA_API_TOKEN}", "Content-Type":"application/json"}
    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Task"}
        }
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, headers=headers, content=json.dumps(payload))
        return r.json() if r.status_code < 300 else None
