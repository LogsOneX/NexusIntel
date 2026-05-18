import httpx

async def run(target: str) -> dict:
    """Checks public profile existence across major Developer platforms."""
    # Strip URL styling if a full link was passed into username field
    username = target.split("/")[-1]
    
    platforms = {
        "GitHub": f"https://api.github.com/users/{username}",
        "Dev.to": f"https://dev.to/api/users/by_username?url={username}"
    }
    
    findings = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for platform, url in platforms.items():
            try:
                res = await client.get(url)
                if res.status_code == 200:
                    findings[platform] = "Active / Available"
                elif res.status_code == 404:
                    findings[platform] = "Not Found"
                else:
                    findings[platform] = f"Unknown Status ({res.status_code})"
            except Exception:
                findings[platform] = "Connection Timeout"

    return {"status": "success", "data": findings}
