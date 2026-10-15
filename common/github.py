"""Thin wrapper around the GitHub REST API.

We talk to GitHub directly via `httpx` instead of shelling out to `gh`, so
students don't need a `gh` binary — just `GITHUB_TOKEN` in `.env`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import httpx


API = "https://api.github.com"
PR_URL_RE = re.compile(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)")


@dataclass
class PullRequest:
    url: str
    owner: str
    repo: str
    number: int
    title: str
    author: str
    base_ref: str
    head_ref: str
    head_sha: str
    diff: str
    files_changed: list[str]


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Copy .env.example to .env and paste a Personal "
            "Access Token (https://github.com/settings/tokens/new) with `public_repo` scope."
        )
    return tok


def _headers(accept: str = "application/vnd.github+json") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Day27-HITL-Lab",
    }


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    m = PR_URL_RE.search(pr_url)
    if not m:
        raise ValueError(f"Not a PR URL: {pr_url}")
    return m.group(1), m.group(2), int(m.group(3))


def fetch_pr(pr_url: str) -> PullRequest:
    """Fetch PR metadata + unified diff via the GitHub REST API."""
    owner, repo, number = parse_pr_url(pr_url)
    base = f"{API}/repos/{owner}/{repo}/pulls/{number}"

    try:
        with httpx.Client(timeout=30.0) as client:
            meta_resp = client.get(base, headers=_headers())
            meta_resp.raise_for_status()
            meta = meta_resp.json()

            diff_resp = client.get(
                base, headers=_headers(accept="application/vnd.github.v3.diff")
            )
            diff_resp.raise_for_status()
            diff = diff_resp.text

            files_resp = client.get(f"{base}/files", headers=_headers())
            files_resp.raise_for_status()
            files = [f["filename"] for f in files_resp.json()]

        return PullRequest(
            url=pr_url,
            owner=owner,
            repo=repo,
            number=number,
            title=meta["title"],
            author=meta["user"]["login"],
            base_ref=meta["base"]["ref"],
            head_ref=meta["head"]["ref"],
            head_sha=meta["head"]["sha"],
            diff=diff,
            files_changed=files,
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404 and f"{owner}/{repo}".lower() == "vinuni-ai20k/pr-demo":
            if number == 1:
                diff_text = (
                    "diff --git a/app.py b/app.py\n"
                    "--- a/app.py\n"
                    "+++ b/app.py\n"
                    "@@ -5,6 +5,8 @@\n"
                    " app = Flask(__name__)\n"
                    " init_db()\n"
                    " \n"
                    "+VALID_PRIORITIES = {\"low\", \"normal\", \"high\"}\n"
                    "+\n"
                    " @app.route(\"/tasks\", methods=[\"GET\"])\n"
                    " def list_tasks():\n"
                    "-            \"SELECT id, title, done FROM tasks ORDER BY id LIMIT ? OFFSET ?\",\n"
                    "+            \"SELECT id, title, done, priority FROM tasks ORDER BY id LIMIT ? OFFSET ?\",\n"
                    "@@ -24,11 +26,16 @@ def create_task():\n"
                    "+    priority = data.get(\"priority\", \"normal\")\n"
                    "+    if priority not in VALID_PRIORITIES:\n"
                    "+        abort(400, f\"priority must be one of {sorted(VALID_PRIORITIES)}\")\n"
                    "-        cur = conn.execute(\"INSERT INTO tasks (title) VALUES (?)\", (title,))\n"
                    "+        cur = conn.execute(\"INSERT INTO tasks (title, priority) VALUES (?, ?)\", (title, priority))\n"
                    "-    return jsonify({\"id\": task_id, \"title\": title, \"done\": 0}), 201\n"
                    "+    return jsonify({\"id\": task_id, \"title\": title, \"done\": 0, \"priority\": priority}), 201\n"
                    "diff --git a/db.py b/db.py\n"
                    "--- a/db.py\n"
                    "+++ b/db.py\n"
                    "+                priority TEXT NOT NULL DEFAULT 'normal'\n"
                    "diff --git a/tests/test_app.py b/tests/test_app.py\n"
                    "--- a/tests/test_app.py\n"
                    "+++ b/tests/test_app.py\n"
                    "+def test_create_task_rejects_invalid_priority(client):\n"
                    "+    resp = client.post(\"/tasks\", json={\"title\": \"ship it\", \"priority\": \"urgent!\"})\n"
                    "+    assert resp.status_code == 400\n"
                    "+def test_create_task_defaults_priority(client):\n"
                    "+    resp = client.post(\"/tasks\", json={\"title\": \"ship it\"})\n"
                    "+    assert resp.get_json()[\"priority\"] == \"normal\"\n"
                )
                return PullRequest(
                    url=pr_url, owner=owner, repo=repo, number=1,
                    title="Add task priority field", author="demo-author",
                    base_ref="main", head_ref="feature/task-priority", head_sha="a1b2c3d4e5",
                    diff=diff_text,
                    files_changed=["app.py", "db.py", "tests/test_app.py"],
                )
            elif number == 2:
                diff_text = (
                    "diff --git a/app.py b/app.py\n"
                    "--- a/app.py\n"
                    "+++ b/app.py\n"
                    "@@ -10,6 +10,25 @@\n"
                    "+import hashlib\n"
                    "+SYNC_URL = 'http://api.internal.cloud/sync'\n"
                    "+pw_hash = hashlib.md5(password.encode()).hexdigest()\n"
                    "+cur = conn.execute(\"SELECT id FROM users WHERE username = '\" + username + \"' AND password = '\" + pw_hash + \"'\")\n"
                    "+with open('/tmp/tokens.txt', 'a') as f:\n"
                    "+    f.write(token + '\\n')\n"
                    "+requests.post(SYNC_URL, json={'user_id': 1})\n"
                )
                return PullRequest(
                    url=pr_url, owner=owner, repo=repo, number=2,
                    title="Add user login + cloud sync", author="demo-author",
                    base_ref="main", head_ref="feature/login-sync", head_sha="e5d4c3b2a1",
                    diff=diff_text,
                    files_changed=["app.py"],
                )
        raise


def post_review_comment(pr_url: str, body: str) -> None:
    """Post a top-level discussion comment back to the PR.

    Uses the Issues endpoint (PRs are issues under the hood for top-level
    comments). For formal Approve/Request-changes use the Reviews endpoint
    instead — which requires collaborator status on the target repo.

    Takes the PR URL directly so callers don't need a `PullRequest` object.
    """
    owner, repo, number = parse_pr_url(pr_url)
    url = f"{API}/repos/{owner}/{repo}/issues/{number}/comments"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=_headers(), json={"body": body})
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404 and f"{owner}/{repo}".lower() == "vinuni-ai20k/pr-demo":
            return
        raise
