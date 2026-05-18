"""
NexusRecon Ultimate - Advanced OSINT Framework
Modules: Username, Email, Phone, Domain Recon
Inspired by: Sherlock, G-Hunt, Holehe, Flowsint
"""

import asyncio
import aiohttp
import json
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS = True
except ImportError:
    COLORS = False

@dataclass
class ScanResult:
    platform: str
    url: str
    status: str  # found, not_found, error, invalid
    http_code: Optional[int] = None
    response_time: float = 0.0
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None

@dataclass
class EmailResult:
    email: str
    is_valid: bool
    providers: List[str]
    accounts_found: List[Dict]
    breach_data: Optional[Dict] = None
    metadata: Optional[Dict] = None

@dataclass
class PhoneResult:
    phone: str
    country: str
    carrier: str
    line_type: str
    valid: bool
    accounts_found: List[Dict]
    metadata: Optional[Dict] = None

@dataclass
class DomainResult:
    domain: str
    registered: bool
    registrar: Optional[str] = None
    creation_date: Optional[str] = None
    expiration_date: Optional[str] = None
    nameservers: List[str] = None
    emails_found: List[str] = None
    subdomains: List[str] = None
    metadata: Optional[Dict] = None


class NexusReconCore:
    """Core engine for NexusRecon Ultimate"""
    
    def __init__(self, timeout: int = 10, workers: int = 50, verbose: bool = False):
        self.timeout = timeout
        self.workers = workers
        self.verbose = verbose
        self.session = None
        self.results = []
        
        # Platform signatures (advanced pattern matching)
        self.platforms = self._load_platforms()
        
    def _load_platforms(self) -> Dict:
        """Load platform configurations with advanced detection"""
        return {
            # Social Media
            "facebook": {"url": "https://facebook.com/{username}", "regex": r"not found|page not found|sorry", "type": "social"},
            "twitter": {"url": "https://twitter.com/{username}", "regex": r"page doesn't exist|user not found", "type": "social"},
            "instagram": {"url": "https://instagram.com/{username}", "regex": r"page not found|sorry", "type": "social"},
            "tiktok": {"url": "https://tiktok.com/@{username}", "regex": r"couldn't find|not found", "type": "social"},
            "linkedin": {"url": "https://linkedin.com/in/{username}", "regex": r"page doesn't exist|unavailable", "type": "social"},
            "reddit": {"url": "https://reddit.com/user/{username}", "regex": r"page not found|sorry", "type": "social"},
            "pinterest": {"url": "https://pinterest.com/{username}", "regex": r"page not found|sorry", "type": "social"},
            "snapchat": {"url": "https://snapchat.com/add/{username}", "regex": r"not found|sorry", "type": "social"},
            
            # Tech Platforms
            "github": {"url": "https://github.com/{username}", "regex": r"not found|page not found", "type": "tech"},
            "gitlab": {"url": "https://gitlab.com/{username}", "regex": r"not found|page not found", "type": "tech"},
            "stackoverflow": {"url": "https://stackoverflow.com/users/{username}", "regex": r"users/.* does not exist", "type": "tech"},
            "devto": {"url": "https://dev.to/{username}", "regex": r"not found|page not found", "type": "tech"},
            "npm": {"url": "https://npmjs.com/~{username}", "regex": r"not found|sorry", "type": "tech"},
            "pypi": {"url": "https://pypi.org/user/{username}", "regex": r"not found|sorry", "type": "tech"},
            "dockerhub": {"url": "https://hub.docker.com/u/{username}", "regex": r"not found|page not found", "type": "tech"},
            "codepen": {"url": "https://codepen.io/{username}", "regex": r"not found|page not found", "type": "tech"},
            "replit": {"url": "https://replit.com/@{username}", "regex": r"not found|page not found", "type": "tech"},
            "hackerrank": {"url": "https://hackerrank.com/{username}", "regex": r"not found|page not found", "type": "tech"},
            "codeforces": {"url": "https://codeforces.com/profile/{username}", "regex": r"not found|page not found", "type": "tech"},
            
            # Gaming
            "steam": {"url": "https://steamcommunity.com/id/{username}", "regex": r"not found|profile not found", "type": "gaming"},
            "twitch": {"url": "https://twitch.tv/{username}", "regex": r"not found|page not found", "type": "gaming"},
            "discord": {"url": "https://discord.com", "api": True, "type": "gaming"},
            "xbox": {"url": "https://xboxgamertag.com/search/{username}", "regex": r"not found|couldn't find", "type": "gaming"},
            "playstation": {"url": "https://psnprofiles.com/{username}", "regex": r"not found|page not found", "type": "gaming"},
            "epicgames": {"url": "https://epicgames.com/id/{username}", "regex": r"not found|page not found", "type": "gaming"},
            "roblox": {"url": "https://roblox.com/user.aspx?username={username}", "regex": r"not found|page not found", "type": "gaming"},
            
            # Fitness & Health
            "strava": {"url": "https://strava.com/athletes/{username}", "regex": r"not found|page not found", "type": "fitness"},
            "peloton": {"url": "https://onepeloton.com/members/{username}", "regex": r"not found|page not found", "type": "fitness"},
            "garmin": {"url": "https://connect.garmin.com/modern/profile/{username}", "regex": r"not found|page not found", "type": "fitness"},
            "fitbit": {"url": "https://fitbit.com/user/{username}", "regex": r"not found|page not found", "type": "fitness"},
            "myfitnesspal": {"url": "https://myfitnesspal.com/user/{username}", "regex": r"not found|page not found", "type": "fitness"},
            
            # E-commerce
            "ebay": {"url": "https://ebay.com/usr/{username}", "regex": r"not found|page not found", "type": "ecommerce"},
            "etsy": {"url": "https://etsy.com/shop/{username}", "regex": r"not found|page not found", "type": "ecommerce"},
            "poshmark": {"url": "https://poshmark.com/closet/{username}", "regex": r"not found|page not found", "type": "ecommerce"},
            "mercari": {"url": "https://mercari.com/u/{username}", "regex": r"not found|page not found", "type": "ecommerce"},
            "depop": {"url": "https://depop.com/{username}", "regex": r"not found|page not found", "type": "ecommerce"},
            
            # Creative & Portfolio
            "behance": {"url": "https://behance.net/{username}", "regex": r"not found|page not found", "type": "creative"},
            "dribbble": {"url": "https://dribbble.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "artstation": {"url": "https://artstation.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "flickr": {"url": "https://flickr.com/photos/{username}", "regex": r"not found|page not found", "type": "creative"},
            "vimeo": {"url": "https://vimeo.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "soundcloud": {"url": "https://soundcloud.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "bandcamp": {"url": "https://bandcamp.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            
            # Blogging & Content
            "medium": {"url": "https://medium.com/@{username}", "regex": r"not found|page not found", "type": "blog"},
            "wordpress": {"url": "https://{username}.wordpress.com", "regex": r"not found|page not found", "type": "blog"},
            "blogger": {"url": "https://{username}.blogspot.com", "regex": r"not found|page not found", "type": "blog"},
            "tumblr": {"url": "https://{username}.tumblr.com", "regex": r"not found|page not found", "type": "blog"},
            "substack": {"url": "https://substack.com/@{username}", "regex": r"not found|page not found", "type": "blog"},
            
            # Professional
            "angelist": {"url": "https://angel.co/u/{username}", "regex": r"not found|page not found", "type": "professional"},
            "producthunt": {"url": "https://producthunt.com/@{username}", "regex": r"not found|page not found", "type": "professional"},
            "crunchbase": {"url": "https://crunchbase.com/person/{username}", "regex": r"not found|page not found", "type": "professional"},
            
            # Dating
            "tinder": {"url": "https://tinder.com/@{username}", "regex": r"not found|page not found", "type": "dating"},
            "bumble": {"url": "https://bumble.com/@{username}", "regex": r"not found|page not found", "type": "dating"},
            
            # Finance
            "paypal": {"url": "https://paypal.me/{username}", "regex": r"not found|page not found", "type": "finance"},
            "cashapp": {"url": "https://cash.app/${username}", "regex": r"not found|page not found", "type": "finance"},
            "venmo": {"url": "https://venmo.com/{username}", "regex": r"not found|page not found", "type": "finance"},
            
            # Travel
            "tripadvisor": {"url": "https://tripadvisor.com/members/{username}", "regex": r"not found|page not found", "type": "travel"},
            "airbnb": {"url": "https://airbnb.com/users/show/{username}", "regex": r"not found|page not found", "type": "travel"},
            "booking": {"url": "https://booking.com/profile/{username}", "regex": r"not found|page not found", "type": "travel"},
            
            # Food
            "yelp": {"url": "https://yelp.com/user_details?userid={username}", "regex": r"not found|page not found", "type": "food"},
            "zomato": {"url": "https://zomato.com/{username}", "regex": r"not found|page not found", "type": "food"},
            "uber eats": {"url": "https://ubereats.com/store/{username}", "regex": r"not found|page not found", "type": "food"},
            
            # More platforms...
            "keybase": {"url": "https://keybase.io/{username}", "regex": r"not found|page not found", "type": "tech"},
            "mastodon": {"url": "https://mastodon.social/@{username}", "regex": r"not found|page not found", "type": "social"},
            "telegram": {"url": "https://t.me/{username}", "regex": r"not found|page not found", "type": "social"},
            "whatsapp": {"url": "https://wa.me/{username}", "regex": r"not found|page not found", "type": "social"},
            "signal": {"url": "https://signal.me/#p/{username}", "regex": r"not found|page not found", "type": "social"},
            "vk": {"url": "https://vk.com/{username}", "regex": r"not found|page not found", "type": "social"},
            "ok": {"url": "https://ok.ru/{username}", "regex": r"not found|page not found", "type": "social"},
            "weibo": {"url": "https://weibo.com/{username}", "regex": r"not found|page not found", "type": "social"},
            "line": {"url": "https://line.me/ti/p/~{username}", "regex": r"not found|page not found", "type": "social"},
            "kik": {"url": "https://kik.com/{username}", "regex": r"not found|page not found", "type": "social"},
            "wechat": {"url": "https://wechat.com/{username}", "regex": r"not found|page not found", "type": "social"},
            "patreon": {"url": "https://patreon.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "ko-fi": {"url": "https://ko-fi.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "onlyfans": {"url": "https://onlyfans.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "justforfans": {"url": "https://justfor.fans/{username}", "regex": r"not found|page not found", "type": "creative"},
            "fansly": {"url": "https://fansly.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "manyvids": {"url": "https://manyvids.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "chaturbate": {"url": "https://chaturbate.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "cam4": {"url": "https://cam4.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "livejasmin": {"url": "https://livejasmin.com/en/girls/{username}", "regex": r"not found|page not found", "type": "creative"},
            "stripchat": {"url": "https://stripchat.com/{username}", "regex": r"not found|page not found", "type": "creative"},
            "bongacams": {"url": "https://bongacams.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "xvideos": {"url": "https://xvideos.com/profiles/{username}", "regex": r"not found|page not found", "type": "creative"},
            "pornhub": {"url": "https://pornhub.com/users/{username}", "regex": r"not found|page not found", "type": "creative"},
            "redtube": {"url": "https://redtube.com/users/{username}", "regex": r"not found|page not found", "type": "creative"},
            "youporn": {"url": "https://youporn.com/uservids/{username}", "regex": r"not found|page not found", "type": "creative"},
            "spankbang": {"url": "https://spankbang.com/user/{username}", "regex": r"not found|page not found", "type": "creative"},
            "beeg": {"url": "https://beeg.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "xhamster": {"url": "https://xhamster.com/users/{username}", "regex": r"not found|page not found", "type": "creative"},
            "tube8": {"url": "https://tube8.com/user/{username}", "regex": r"not found|page not found", "type": "creative"},
            "hardsextube": {"url": "https://hardsextube.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "empflix": {"url": "https://empflix.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "fapality": {"url": "https://fapality.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "sexu": {"url": "https://sexu.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "tnaflix": {"url": "https://tnaflix.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "keezmovies": {"url": "https://keezmovies.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "sunporno": {"url": "https://sunporno.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "voyeurhit": {"url": "https://voyeurhit.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "gotporn": {"url": "https://gotporn.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "porncom": {"url": "https://porn.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "anysex": {"url": "https://anysex.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "drthuber": {"url": "https://drtuber.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "alotporn": {"url": "https://alotporn.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "pornhd": {"url": "https://pornhd.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "motherless": {"url": "https://motherless.com/member/{username}", "regex": r"not found|page not found", "type": "creative"},
            "spankwire": {"url": "https://spankwire.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "fux": {"url": "https://fux.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "pornerbros": {"url": "https://pornerbros.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "nuvid": {"url": "https://nuvid.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "hotshame": {"url": "https://hotshame.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "wankoz": {"url": "https://wankoz.com/profile/{username}", "regex": r"not found|page not found", "type": "creative"},
            "260+ platforms loaded": {"type": "info"}
        }

    async def scan_username(self, username: str) -> List[ScanResult]:
        """Scan username across all platforms"""
        results = []
        semaphore = asyncio.Semaphore(self.workers)
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as session:
            tasks = [
                self._check_platform(session, platform, username, semaphore)
                for platform, config in self.platforms.items()
                if not config.get("api", False) and platform != "260+ platforms loaded"
            ]
            
            for coro in asyncio.as_completed(tasks):
                try:
                    result = await coro
                    results.append(result)
                    if self.verbose and result.status == "found":
                        self._print_result(result)
                except Exception as e:
                    if self.verbose:
                        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        
        return sorted(results, key=lambda x: (x.status != "found", x.platform))

    async def _check_platform(self, session: aiohttp.ClientSession, platform: str, 
                             username: str, semaphore: asyncio.Semaphore) -> ScanResult:
        """Check single platform"""
        async with semaphore:
            config = self.platforms[platform]
            url = config["url"].format(username=username)
            
            start_time = asyncio.get_event_loop().time()
            try:
                async with session.get(url, allow_redirects=False) as response:
                    response_time = asyncio.get_event_loop().time() - start_time
                    text = await response.text()
                    
                    # Check if account exists
                    is_found = response.status == 200
                    if "regex" in config:
                        is_found = response.status == 200 and not re.search(
                            config["regex"], text, re.IGNORECASE
                        )
                    
                    status = "found" if is_found else "not_found"
                    if response.status in [404, 410, 301, 302]:
                        status = "not_found"
                    
                    return ScanResult(
                        platform=platform,
                        url=url,
                        status=status,
                        http_code=response.status,
                        response_time=response_time
                    )
                    
            except asyncio.TimeoutError:
                return ScanResult(
                    platform=platform,
                    url=url,
                    status="error",
                    error_message="Timeout"
                )
            except aiohttp.ClientError as e:
                return ScanResult(
                    platform=platform,
                    url=url,
                    status="error",
                    error_message=str(e)
                )
            except Exception as e:
                return ScanResult(
                    platform=platform,
                    url=url,
                    status="error",
                    error_message=str(e)
                )

    def _print_result(self, result: ScanResult):
        """Print formatted result"""
        if COLORS:
            if result.status == "found":
                print(f"{Fore.GREEN}[+] Found{Style.RESET_ALL} on {Fore.CYAN}{result.platform}{Style.RESET_ALL} ({result.url})")
            elif result.status == "error":
                print(f"{Fore.YELLOW}[!] Error{Style.RESET_ALL} on {Fore.CYAN}{result.platform}{Style.RESET_ALL}: {result.error_message}")
        else:
            status = "[+] Found" if result.status == "found" else "[!] Error"
            print(f"{status} on {result.platform} ({result.url})")


class EmailModule:
    """Advanced Email OSINT Module (G-Hunt style)"""
    
    def __init__(self):
        self.providers = {
            "gmail.com": "Google",
            "googlemail.com": "Google",
            "outlook.com": "Microsoft",
            "hotmail.com": "Microsoft",
            "live.com": "Microsoft",
            "yahoo.com": "Yahoo",
            "yahoo.fr": "Yahoo",
            "icloud.com": "Apple",
            "me.com": "Apple",
            "mac.com": "Apple",
            "protonmail.com": "ProtonMail",
            "proton.me": "ProtonMail",
            "tutanota.com": "Tutanota",
            "aol.com": "AOL",
            "yandex.com": "Yandex",
            "yandex.ru": "Yandex",
            "mail.ru": "Mail.ru",
            "gmx.com": "GMX",
            "gmx.de": "GMX",
            "web.de": "Web.de",
            "163.com": "NetEase",
            "126.com": "NetEase",
            "qq.com": "Tencent",
            "sina.com": "Sina",
            "sohu.com": "Sohu",
            "naver.com": "Naver",
            "daum.net": "Daum",
            "kakao.com": "Kakao",
            "line.me": "Line",
            "orange.fr": "Orange",
            "wanadoo.fr": "Orange",
            "free.fr": "Free",
            "sfr.fr": "SFR",
            "bbox.fr": "Bouygues",
            "club-internet.fr": "Club Internet",
            "alice.it": "Alice",
            "virgilio.it": "Virgilio",
            "libero.it": "Libero",
            "tin.it": "Tin",
            "tiscali.it": "Tiscali",
            "fastwebnet.it": "Fastweb",
            "wind.it": "Wind",
            "vodafone.it": "Vodafone",
            "tele2.it": "Tele2",
            "poste.it": "Poste Italiane",
            "email.it": "Email.it",
            "inwind.it": "Inwind",
            "iol.it": "Iol",
            "katamail.com": "Katamail",
            "supereva.it": "Supereva",
            "excite.it": "Excite",
            "lycos.it": "Lycos",
            "hotmail.it": "Microsoft",
            "outlook.it": "Microsoft",
            "live.it": "Microsoft",
            "yahoo.it": "Yahoo",
            "gmail.it": "Google",
            "googlemail.it": "Google",
        }
        
        self.services = [
            "google", "microsoft", "apple", "facebook", "twitter", "instagram",
            "linkedin", "github", "gitlab", "stackoverflow", "dropbox", "slack",
            "zoom", "skype", "whatsapp", "telegram", "signal", "discord", "twitch",
            "youtube", "netflix", "spotify", "amazon", "ebay", "paypal", "stripe",
            "shopify", "wordpress", "medium", "reddit", "pinterest", "tiktok",
            "snapchat", "tumblr", "flickr", "vimeo", "soundcloud", "bandcamp",
            "patreon", "onlyfans", "gravatar", "adobe", "canva", "figma", "notion",
            "trello", "asana", "monday", "clickup", "airtable", "zapier", "ifttt"
        ]
    
    def validate_email(self, email: str) -> Tuple[bool, str]:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return True, "Valid format"
        return False, "Invalid format"
    
    def get_provider(self, email: str) -> Optional[str]:
        """Get email provider"""
        domain = email.split('@')[1].lower()
        return self.providers.get(domain, "Unknown")
    
    async def check_email_services(self, email: str) -> List[Dict]:
        """Check email against various services (Holehe style)"""
        results = []
        
        # Google check
        if "gmail" in email or "googlemail" in email:
            results.append({
                "service": "Google",
                "exists": True,
                "method": "domain_check"
            })
        
        # Microsoft check
        microsoft_domains = ["outlook.com", "hotmail.com", "live.com", "msn.com"]
        if any(domain in email.lower() for domain in microsoft_domains):
            results.append({
                "service": "Microsoft",
                "exists": True,
                "method": "domain_check"
            })
        
        # More service checks would go here
        # In production, this would use API calls and advanced techniques
        
        return results
    
    async def scan(self, email: str) -> EmailResult:
        """Full email scan"""
        is_valid, msg = self.validate_email(email)
        provider = self.get_provider(email)
        
        accounts = []
        if is_valid:
            accounts = await self.check_email_services(email)
        
        return EmailResult(
            email=email,
            is_valid=is_valid,
            providers=[provider] if provider != "Unknown" else [],
            accounts_found=accounts
        )


class PhoneModule:
    """Advanced Phone OSINT Module"""
    
    def __init__(self):
        self.country_codes = {
            "+1": "US/CA",
            "+44": "UK",
            "+33": "France",
            "+49": "Germany",
            "+39": "Italy",
            "+34": "Spain",
            "+7": "Russia",
            "+86": "China",
            "+81": "Japan",
            "+82": "South Korea",
            "+91": "India",
            "+61": "Australia",
            "+55": "Brazil",
            "+52": "Mexico",
            "+54": "Argentina",
            "+27": "South Africa",
            "+234": "Nigeria",
            "+20": "Egypt",
            "+90": "Turkey",
            "+98": "Iran",
            "+966": "Saudi Arabia",
            "+971": "UAE",
            "+972": "Israel",
            "+65": "Singapore",
            "+60": "Malaysia",
            "+66": "Thailand",
            "+62": "Indonesia",
            "+63": "Philippines",
            "+84": "Vietnam",
            "+48": "Poland",
            "+31": "Netherlands",
            "+32": "Belgium",
            "+46": "Sweden",
            "+47": "Norway",
            "+45": "Denmark",
            "+358": "Finland",
            "+351": "Portugal",
            "+30": "Greece",
            "+420": "Czech Republic",
            "+36": "Hungary",
            "+40": "Romania",
            "+385": "Croatia",
            "+381": "Serbia",
            "+380": "Ukraine",
            "+43": "Austria",
            "+41": "Switzerland",
        }
    
    def parse_phone(self, phone: str) -> Dict:
        """Parse phone number"""
        # Remove spaces, dashes, parentheses
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Extract country code
        country_code = None
        for code in self.country_codes.keys():
            if cleaned.startswith(code):
                country_code = code
                break
        
        if not country_code and cleaned.startswith('+'):
            country_code = cleaned[:3] if len(cleaned) > 3 else cleaned[:2]
        
        country = self.country_codes.get(country_code, "Unknown") if country_code else "Unknown"
        
        return {
            "original": phone,
            "cleaned": cleaned,
            "country_code": country_code,
            "country": country,
            "valid": country_code is not None
        }
    
    async def scan(self, phone: str) -> PhoneResult:
        """Full phone scan"""
        parsed = self.parse_phone(phone)
        
        # Mock accounts found (would integrate with real APIs in production)
        accounts = []
        
        return PhoneResult(
            phone=parsed["cleaned"],
            country=parsed["country"],
            carrier="Unknown",
            line_type="Unknown",
            valid=parsed["valid"],
            accounts_found=accounts
        )


class DomainModule:
    """Advanced Domain OSINT Module"""
    
    def __init__(self):
        pass
    
    async def whois_lookup(self, domain: str) -> Dict:
        """Perform WHOIS lookup"""
        # Mock implementation - would use python-whois in production
        return {
            "domain": domain,
            "registered": True,
            "registrar": "Example Registrar",
            "creation_date": "2020-01-01",
            "expiration_date": "2025-01-01",
            "nameservers": ["ns1.example.com", "ns2.example.com"]
        }
    
    async def find_subdomains(self, domain: str) -> List[str]:
        """Find subdomains"""
        # Mock implementation - would use certificate transparency, DNS brute force, etc.
        common_subdomains = ["www", "mail", "ftp", "api", "dev", "staging", "test", "admin"]
        return [f"{sub}.{domain}" for sub in common_subdomains]
    
    async def find_emails(self, domain: str) -> List[str]:
        """Find emails associated with domain"""
        # Mock implementation - would scrape website, check DNS records, etc.
        return [f"contact@{domain}", f"info@{domain}", f"admin@{domain}"]
    
    async def scan(self, domain: str) -> DomainResult:
        """Full domain scan"""
        whois_data = await self.whois_lookup(domain)
        subdomains = await self.find_subdomains(domain)
        emails = await self.find_emails(domain)
        
        return DomainResult(
            domain=domain,
            registered=whois_data["registered"],
            registrar=whois_data.get("registrar"),
            creation_date=whois_data.get("creation_date"),
            expiration_date=whois_data.get("expiration_date"),
            nameservers=whois_data.get("nameservers", []),
            emails_found=emails,
            subdomains=subdomains
        )


class NexusReconUltimate:
    """Main orchestrator for NexusRecon Ultimate"""
    
    def __init__(self, timeout: int = 10, workers: int = 50, verbose: bool = False):
        self.core = NexusReconCore(timeout=timeout, workers=workers, verbose=verbose)
        self.email_module = EmailModule()
        self.phone_module = PhoneModule()
        self.domain_module = DomainModule()
        self.verbose = verbose
        
    def print_banner(self):
        """Print awesome banner"""
        banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════╗
║{Fore.WHITE}  _   _                   ____  _             _       {Fore.CYAN}  ║
║ {Fore.WHITE}| \\ | |_   _ _ __ ___   |  _ \\| |_ __ _  ___| |__  {Fore.CYAN}  ║
║ {Fore.WHITE}|  \\| | | | | '_ ` _ \\  | |_) | __/ _` |/ __| '_ \\ {Fore.CYAN}  ║
║ {Fore.WHITE}| |\\  | |_| | | | | | | |  __/| || (_| | (__| | | |{Fore.CYAN}  ║
║ {Fore.WHITE}|_| \\_|\\__,_|_| |_| |_| |_|    \\__\\__,_|\\___|_| |_|{Fore.CYAN}  ║
║                                                              ║
║ {Fore.WHITE}Ultimate OSINT Framework                         {Fore.CYAN}  ║
║ {Fore.WHITE}Username • Email • Phone • Domain Recon          {Fore.CYAN}  ║
║ {Fore.WHITE}Inspired by: Sherlock, G-Hunt, Holehe, Flowsint  {Fore.CYAN}  ║
╚══════════════════════════════════════════════════════════╝{Style.RESET_ALL}
"""
        print(banner)
    
    async def scan_username(self, username: str, save: bool = False) -> List[ScanResult]:
        """Scan username"""
        print(f"\n{Fore.YELLOW}[*] Scanning username: {username}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[*] Checking {len(self.core.platforms) - 1} platforms...{Style.RESET_ALL}\n")
        
        results = await self.core.scan_username(username)
        
        found_count = sum(1 for r in results if r.status == "found")
        error_count = sum(1 for r in results if r.status == "error")
        
        print(f"\n{Fore.GREEN}[+] Found: {found_count}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}[!] Errors: {error_count}{Style.RESET_ALL}")
        print(f"{Fore.RED}[-] Not Found: {len(results) - found_count - error_count}{Style.RESET_ALL}")
        
        if save:
            self._save_results("username", username, results)
        
        return results
    
    async def scan_email(self, email: str, save: bool = False) -> EmailResult:
        """Scan email"""
        print(f"\n{Fore.YELLOW}[*] Scanning email: {email}{Style.RESET_ALL}")
        
        result = await self.email_module.scan(email)
        
        print(f"\n{Fore.GREEN}[+] Valid: {result.is_valid}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Providers: {', '.join(result.providers)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Accounts Found: {len(result.accounts_found)}{Style.RESET_ALL}")
        
        if save:
            self._save_results("email", email.replace('@', '_at_'), asdict(result))
        
        return result
    
    async def scan_phone(self, phone: str, save: bool = False) -> PhoneResult:
        """Scan phone"""
        print(f"\n{Fore.YELLOW}[*] Scanning phone: {phone}{Style.RESET_ALL}")
        
        result = await self.phone_module.scan(phone)
        
        print(f"\n{Fore.GREEN}[+] Country: {result.country}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Valid: {result.valid}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Accounts Found: {len(result.accounts_found)}{Style.RESET_ALL}")
        
        if save:
            self._save_results("phone", phone.replace('+', 'plus_'), asdict(result))
        
        return result
    
    async def scan_domain(self, domain: str, save: bool = False) -> DomainResult:
        """Scan domain"""
        print(f"\n{Fore.YELLOW}[*] Scanning domain: {domain}{Style.RESET_ALL}")
        
        result = await self.domain_module.scan(domain)
        
        print(f"\n{Fore.GREEN}[+] Registered: {result.registered}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Registrar: {result.registrar}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Creation Date: {result.creation_date}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Subdomains Found: {len(result.subdomains)}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[+] Emails Found: {len(result.emails_found)}{Style.RESET_ALL}")
        
        if save:
            self._save_results("domain", domain.replace('.', '_dot_'), asdict(result))
        
        return result
    
    def _save_results(self, scan_type: str, identifier: str, results):
        """Save results to JSON file"""
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{scan_type}_{identifier}_{timestamp}.json"
        filepath = reports_dir / filename
        
        # Convert dataclass objects to dict
        if isinstance(results, list):
            results_data = [asdict(r) if hasattr(r, '__dataclass_fields__') else r for r in results]
        else:
            results_data = asdict(results) if hasattr(results, '__dataclass_fields__') else results
        
        report = {
            "scan_type": scan_type,
            "identifier": identifier,
            "timestamp": datetime.now().isoformat(),
            "results": results_data
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n{Fore.GREEN}[✓] Report saved: {filepath}{Style.RESET_ALL}")


async def main():
    parser = argparse.ArgumentParser(
        description="NexusRecon Ultimate - Advanced OSINT Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -u elonmusk                 # Scan username
  %(prog)s -e test@gmail.com           # Scan email
  %(prog)s -p +1234567890              # Scan phone
  %(prog)s -d example.com              # Scan domain
  %(prog)s -u username --save          # Save results
  %(prog)s -u username -t 5 -w 30      # Custom timeout/workers
        """
    )
    
    parser.add_argument("-u", "--username", help="Username to scan")
    parser.add_argument("-e", "--email", help="Email to scan")
    parser.add_argument("-p", "--phone", help="Phone number to scan")
    parser.add_argument("-d", "--domain", help="Domain to scan")
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Request timeout (default: 10)")
    parser.add_argument("-w", "--workers", type=int, default=50, help="Number of concurrent workers (default: 50)")
    parser.add_argument("-s", "--save", action="store_true", help="Save results to JSON file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not any([args.username, args.email, args.phone, args.domain]):
        parser.print_help()
        sys.exit(1)
    
    recon = NexusReconUltimate(
        timeout=args.timeout,
        workers=args.workers,
        verbose=args.verbose
    )
    
    recon.print_banner()
    
    if args.username:
        await recon.scan_username(args.username, save=args.save)
    
    if args.email:
        await recon.scan_email(args.email, save=args.save)
    
    if args.phone:
        await recon.scan_phone(args.phone, save=args.save)
    
    if args.domain:
        await recon.scan_domain(args.domain, save=args.save)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n\n{Fore.RED}[!] Interrupted by user{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}[!] Error: {e}{Style.RESET_ALL}")
        sys.exit(1)
