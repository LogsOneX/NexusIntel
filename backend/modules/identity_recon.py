from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from .common import AsyncHttpClient, EmitCallback, ReconFinding, html_title, looks_like_not_found, maybe_emit, normalize_username, text_contains_username


@dataclass(frozen=True, slots=True)
class PlatformProfile:
    name: str
    url: str
    category: str
    expected_status: tuple[int, ...] = (200,)
    username_required_in_body: bool = False
    not_found_terms: tuple[str, ...] = ()
    json_probe: bool = False


PLATFORMS: tuple[PlatformProfile, ...] = tuple(
    PlatformProfile(name=name, url=url, category=category, username_required_in_body=required)
    for name, url, category, required in [
        ("GitHub", "https://github.com/{username}", "code", True),
        ("GitLab", "https://gitlab.com/{username}", "code", True),
        ("Codeberg", "https://codeberg.org/{username}", "code", True),
        ("SourceHut", "https://sr.ht/~{username}", "code", True),
        ("Bitbucket", "https://bitbucket.org/{username}/", "code", True),
        ("Launchpad", "https://launchpad.net/~{username}", "code", True),
        ("npm", "https://www.npmjs.com/~{username}", "code", True),
        ("PyPI", "https://pypi.org/user/{username}/", "code", True),
        ("RubyGems", "https://rubygems.org/profiles/{username}", "code", True),
        ("DockerHub", "https://hub.docker.com/u/{username}", "code", True),
        ("Kaggle", "https://www.kaggle.com/{username}", "data", True),
        ("HuggingFace", "https://huggingface.co/{username}", "ai", True),
        ("StackOverflow", "https://stackoverflow.com/users/{username}", "community", True),
        ("AskUbuntu", "https://askubuntu.com/users/{username}", "community", True),
        ("SuperUser", "https://superuser.com/users/{username}", "community", True),
        ("Reddit", "https://www.reddit.com/user/{username}/", "social", True),
        ("X", "https://x.com/{username}", "social", True),
        ("Threads", "https://www.threads.net/@{username}", "social", True),
        ("Instagram", "https://www.instagram.com/{username}/", "social", True),
        ("TikTok", "https://www.tiktok.com/@{username}", "social", True),
        ("YouTube", "https://www.youtube.com/@{username}", "video", True),
        ("Twitch", "https://www.twitch.tv/{username}", "video", True),
        ("Vimeo", "https://vimeo.com/{username}", "video", True),
        ("Dailymotion", "https://www.dailymotion.com/{username}", "video", True),
        ("SoundCloud", "https://soundcloud.com/{username}", "audio", True),
        ("SpotifyUser", "https://open.spotify.com/user/{username}", "audio", False),
        ("Bandcamp", "https://bandcamp.com/{username}", "audio", True),
        ("LastFM", "https://www.last.fm/user/{username}", "audio", True),
        ("Medium", "https://medium.com/@{username}", "blog", True),
        ("Substack", "https://substack.com/@{username}", "blog", True),
        ("DevTo", "https://dev.to/{username}", "blog", True),
        ("Hashnode", "https://hashnode.com/@{username}", "blog", True),
        ("ProductHunt", "https://www.producthunt.com/@{username}", "startup", True),
        ("Dribbble", "https://dribbble.com/{username}", "design", True),
        ("Behance", "https://www.behance.net/{username}", "design", True),
        ("FigmaCommunity", "https://www.figma.com/@{username}", "design", True),
        ("Patreon", "https://www.patreon.com/{username}", "creator", True),
        ("BuyMeACoffee", "https://www.buymeacoffee.com/{username}", "creator", True),
        ("KoFi", "https://ko-fi.com/{username}", "creator", True),
        ("Keybase", "https://keybase.io/{username}", "identity", True),
        ("AboutMe", "https://about.me/{username}", "identity", True),
        ("Linktree", "https://linktr.ee/{username}", "identity", True),
        ("Carrd", "https://{username}.carrd.co/", "identity", False),
        ("GravatarProfile", "https://gravatar.com/{username}", "identity", True),
        ("Wikimedia", "https://meta.wikimedia.org/wiki/User:{username}", "wiki", True),
        ("Wikipedia", "https://en.wikipedia.org/wiki/User:{username}", "wiki", True),
        ("MastodonSocial", "https://mastodon.social/@{username}", "federated", True),
        ("InfosecExchange", "https://infosec.exchange/@{username}", "federated", True),
        ("Bsky", "https://bsky.app/profile/{username}.bsky.social", "federated", True),
        ("Steam", "https://steamcommunity.com/id/{username}", "gaming", True),
        ("Roblox", "https://www.roblox.com/user.aspx?username={username}", "gaming", True),
        ("ChessCom", "https://www.chess.com/member/{username}", "gaming", True),
        ("Lichess", "https://lichess.org/@/{username}", "gaming", True),
        ("TryHackMe", "https://tryhackme.com/p/{username}", "security", True),
        ("HackTheBox", "https://app.hackthebox.com/profile/{username}", "security", True),
        ("RootMe", "https://www.root-me.org/{username}", "security", True),
        ("LeetCode", "https://leetcode.com/{username}/", "code", True),
        ("Codeforces", "https://codeforces.com/profile/{username}", "code", True),
        ("HackerRank", "https://www.hackerrank.com/{username}", "code", True),
        ("CodePen", "https://codepen.io/{username}", "code", True),
        ("Replit", "https://replit.com/@{username}", "code", True),
        ("Observable", "https://observablehq.com/@{username}", "data", True),
        ("Slideshare", "https://www.slideshare.net/{username}", "docs", True),
        ("Scribd", "https://www.scribd.com/{username}", "docs", True),
        ("ResearchGate", "https://www.researchgate.net/profile/{username}", "academic", True),
        ("ORCID", "https://orcid.org/{username}", "academic", False),
        ("Academia", "https://independent.academia.edu/{username}", "academic", True),
        ("Strava", "https://www.strava.com/athletes/{username}", "fitness", False),
        ("Flickr", "https://www.flickr.com/people/{username}/", "photo", True),
        ("Unsplash", "https://unsplash.com/@{username}", "photo", True),
        ("500px", "https://500px.com/p/{username}", "photo", True),
        ("Pinterest", "https://www.pinterest.com/{username}/", "social", True),
        ("Tumblr", "https://{username}.tumblr.com/", "blog", False),
        ("WordPress", "https://{username}.wordpress.com/", "blog", False),
        ("Blogger", "https://{username}.blogspot.com/", "blog", False),
        ("Disqus", "https://disqus.com/by/{username}/", "community", True),
        ("Goodreads", "https://www.goodreads.com/{username}", "books", True),
        ("Letterboxd", "https://letterboxd.com/{username}/", "film", True),
        ("Rumble", "https://rumble.com/user/{username}", "video", True),
        ("Kick", "https://kick.com/{username}", "stream", True),
        ("TripAdvisor", "https://www.tripadvisor.com/Profile/{username}", "travel", True),
        ("Duolingo", "https://www.duolingo.com/profile/{username}", "learning", True),
        ("Codecademy", "https://www.codecademy.com/profiles/{username}", "learning", True),
        ("Coursera", "https://www.coursera.org/user/{username}", "learning", True),
        ("OpenStreetMap", "https://www.openstreetmap.org/user/{username}", "maps", True),
        ("Etsy", "https://www.etsy.com/shop/{username}", "commerce", True),
        ("Mercari", "https://www.mercari.com/u/{username}/", "commerce", False),
        ("Gumroad", "https://{username}.gumroad.com/", "commerce", False),
        ("Notion", "https://www.notion.so/@{username}", "identity", True),
        ("ReadCV", "https://read.cv/{username}", "professional", True),
        ("Polywork", "https://www.polywork.com/{username}", "professional", True),
        ("AngelList", "https://angel.co/u/{username}", "professional", True),
        ("Wellfound", "https://wellfound.com/u/{username}", "professional", True),
        ("Mixcloud", "https://www.mixcloud.com/{username}/", "audio", True),
        ("Trello", "https://trello.com/{username}", "productivity", True),
        ("Scratch", "https://scratch.mit.edu/users/{username}/", "code", True),
        ("AniList", "https://anilist.co/user/{username}/", "media", True),
        ("MyAnimeList", "https://myanimelist.net/profile/{username}", "media", True),
        ("OpenCollective", "https://opencollective.com/{username}", "funding", True),
        ("Liberapay", "https://liberapay.com/{username}/", "funding", True),
        ("Sessionize", "https://sessionize.com/{username}/", "events", True),
        ("SpeakerDeck", "https://speakerdeck.com/{username}", "docs", True),
        ("Qiita", "https://qiita.com/{username}", "code", True),
        ("Zenn", "https://zenn.dev/{username}", "code", True),
        ("Wantedly", "https://www.wantedly.com/id/{username}", "professional", True),
        ("NaverBlog", "https://blog.naver.com/{username}", "blog", True),
        ("Rarible", "https://rarible.com/{username}", "web3", True),
        ("OpenSea", "https://opensea.io/{username}", "web3", True),
        ("Lens", "https://hey.xyz/u/{username}", "web3", True),
        ("ENSVision", "https://www.ens.vision/name/{username}.eth", "web3", False),
        ("TelegramPublic", "https://t.me/{username}", "messaging_public_username", True),
    ]
)


class IdentityResolver:
    def __init__(self, *, concurrency: int = 64, timeout: float = 10.0):
        self.concurrency = concurrency
        self.timeout = timeout

    async def check_platform(self, client: AsyncHttpClient, username: str, platform: PlatformProfile) -> ReconFinding | None:
        url = platform.url.format(username=username)
        result = await client.request_text("GET", url, retries=2)
        status = int(result.get("status") or 0)
        text = str(result.get("text") or "")
        title = html_title(text)
        if status in {401, 403}:
            return ReconFinding(
                "profile_candidate",
                f"{username} @ {platform.name}",
                url,
                "ghost_identity",
                "low",
                "OBSERVED_ON",
                {"platform": platform.name, "category": platform.category, "status_code": status, "title": title, "reason": "restricted_or_auth_wall"},
            )
        if status not in platform.expected_status:
            return None
        if looks_like_not_found(text) or any(term.lower() in text.lower() for term in platform.not_found_terms):
            return None
        if platform.username_required_in_body and not text_contains_username(text, username):
            return None
        confidence = "high" if platform.username_required_in_body else "medium"
        return ReconFinding(
            "profile",
            f"{username} @ {platform.name}",
            url,
            "ghost_identity",
            confidence,
            "REGISTERED_ON",
            {"platform": platform.name, "category": platform.category, "status_code": status, "final_url": result.get("url"), "title": title},
        )

    async def resolve(self, username: str, *, emit: EmitCallback | None = None, limit: int | None = None) -> dict[str, Any]:
        normalized = normalize_username(username)
        platforms = PLATFORMS[:limit] if limit is not None else PLATFORMS
        findings: list[ReconFinding] = []
        async with AsyncHttpClient(concurrency=self.concurrency, timeout=self.timeout) as client:
            tasks = [self.check_platform(client, normalized, platform) for platform in platforms]
            for future in asyncio.as_completed(tasks):
                finding = await future
                if finding:
                    findings.append(finding)
                    await maybe_emit(emit, f"Found public profile signal: {finding.label}", finding.as_artifact())
        return {
            "target": normalized,
            "checked": len(platforms),
            "found": len(findings),
            "artifacts": [finding.as_artifact() for finding in findings],
        }
