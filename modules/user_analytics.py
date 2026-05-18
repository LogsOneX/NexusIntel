import asyncio
from collections import Counter
from typing import Dict, List

import httpx

from core.targets import classify_target


metadata = {
    "name": "Public User Analytics",
    "description": "Developer and creator profile enrichment from public APIs, activity metadata, and repository language signals.",
    "category": "identity",
    "target_types": ["username", "email", "url"],
    "tags": ["github", "devto", "analytics", "developer"],
    "passive": True,
    "risk": "low",
}


async def _github(client: httpx.AsyncClient, username: str) -> Dict[str, object]:
    output: Dict[str, object] = {}
    try:
        profile = await client.get(f"https://api.github.com/users/{username}")
        if profile.status_code == 200:
            data = profile.json()
            output["profile"] = {
                "login": data.get("login"),
                "name": data.get("name"),
                "company": data.get("company"),
                "blog": data.get("blog"),
                "location": data.get("location"),
                "bio": data.get("bio"),
                "public_repos": data.get("public_repos"),
                "followers": data.get("followers"),
                "following": data.get("following"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "html_url": data.get("html_url"),
            }
        else:
            output["profile_status"] = profile.status_code
    except Exception as exc:
        output["profile_error"] = str(exc)

    try:
        repos = await client.get(
            f"https://api.github.com/users/{username}/repos",
            params={"per_page": 30, "sort": "updated", "direction": "desc"},
        )
        if repos.status_code == 200:
            repo_data = repos.json()
            languages = Counter(repo.get("language") for repo in repo_data if repo.get("language"))
            output["recent_repositories"] = [
                {
                    "name": repo.get("name"),
                    "url": repo.get("html_url"),
                    "language": repo.get("language"),
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "updated_at": repo.get("updated_at"),
                }
                for repo in repo_data[:8]
            ]
            output["language_signals"] = dict(languages.most_common(8))
    except Exception:
        output["recent_repositories"] = []
    return output


async def _devto(client: httpx.AsyncClient, username: str) -> Dict[str, object]:
    try:
        response = await client.get("https://dev.to/api/users/by_username", params={"url": username})
        if response.status_code != 200:
            return {"status": response.status_code}
        data = response.json()
        return {
            "username": data.get("username"),
            "name": data.get("name"),
            "summary": data.get("summary"),
            "twitter_username": data.get("twitter_username"),
            "github_username": data.get("github_username"),
            "website_url": data.get("website_url"),
            "joined_at": data.get("joined_at"),
            "profile_image": data.get("profile_image"),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def _hackernews(client: httpx.AsyncClient, username: str) -> Dict[str, object]:
    try:
        response = await client.get(f"https://hacker-news.firebaseio.com/v0/user/{username}.json")
        if response.status_code != 200 or not response.text or response.text == "null":
            return {"status": "not_found"}
        data = response.json()
        return {
            "id": data.get("id"),
            "created": data.get("created"),
            "karma": data.get("karma"),
            "submitted_count": len(data.get("submitted", [])),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def run(target: str) -> dict:
    profile = classify_target(target)
    if not profile.candidate_usernames:
        return {"status": "skipped", "summary": "No username candidate.", "data": {"target": target}}
    username = profile.candidate_usernames[0]

    async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}) as client:
        github_task = asyncio.create_task(_github(client, username))
        devto_task = asyncio.create_task(_devto(client, username))
        hn_task = asyncio.create_task(_hackernews(client, username))
        github, devto, hackernews = await asyncio.gather(github_task, devto_task, hn_task)

    signals = 0
    if github.get("profile"):
        signals += 1
    if devto.get("username"):
        signals += 1
    if hackernews.get("id"):
        signals += 1
    signals += len(github.get("language_signals", {}))

    return {
        "status": "success",
        "summary": f"{signals} public analytics signal(s) for {username}.",
        "data": {
            "query": username,
            "target_type": profile.kind,
            "github": github,
            "devto": devto,
            "hackernews": hackernews,
        },
    }
