import httpx

async def run(target: str) -> dict:
    """Inspects response metadata parameters returned inside public target headers."""
    url = target
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    findings = {}
    async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
        try:
            res = await client.head(url)
            headers = res.headers

            # Target relevant server analytics configurations
            findings["Server Banner"] = headers.get("server", "Hidden / Not Disclosed")
            findings["Content-Type"] = headers.get("content-type", "Not Specified")
            findings["Strict-Transport-Security"] = headers.get("strict-transport-security", "Not Configured")
            findings["X-Frame-Options"] = headers.get("x-frame-options", "Not Configured")
            findings["X-Content-Type-Options"] = headers.get("x-content-type-options", "Not Configured")
        except Exception as e:
            return {"status": "error", "message": f"Failed connection diagnostics check: {e}"}

    return {"status": "success", "data": findings}
