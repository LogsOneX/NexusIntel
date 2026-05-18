#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NexusRecon - Advanced OSINT Framework
Multi-threaded username enumeration across 100+ platforms
"""

import argparse
import json
import os
import sys
import time
import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
import re
from collections import defaultdict

# Color codes
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

@dataclass
class PlatformResult:
    platform: str
    url: str
    status: str
    status_code: Optional[int]
    response_time: float
    error_message: Optional[str] = None

@dataclass
class ReconReport:
    username: str
    timestamp: str
    total_platforms: int
    found_count: int
    not_found_count: int
    error_count: int
    results: List[PlatformResult]
    scan_duration: float

class NexusRecon:
    def __init__(self, timeout: int = 10, max_concurrent: int = 50):
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.platforms = self._load_platforms()
        
    def _load_platforms(self) -> Dict[str, str]:
        return {
            "Facebook": "https://facebook.com/{}",
            "X": "https://x.com/{}",
            "Instagram": "https://instagram.com/{}",
            "LinkedIn": "https://linkedin.com/in/{}",
            "GitHub": "https://github.com/{}",
            "GitLab": "https://gitlab.com/{}",
            "Reddit": "https://reddit.com/user/{}",
            "TikTok": "https://tiktok.com/@{}",
            "Pinterest": "https://pinterest.com/{}",
            "Snapchat": "https://snapchat.com/add/{}",
            "Telegram": "https://t.me/{}",
            "Discord": "https://discord.com/users/{}",
            "Steam": "https://steamcommunity.com/id/{}",
            "Medium": "https://medium.com/@{}",
            "Quora": "https://quora.com/profile/{}",
            "Tumblr": "https://{}.tumblr.com",
            "Vimeo": "https://vimeo.com/{}",
            "SoundCloud": "https://soundcloud.com/{}",
            "Spotify": "https://open.spotify.com/user/{}",
            "YouTube": "https://youtube.com/@{}",
            "Twitch": "https://twitch.tv/{}",
            "Patreon": "https://patreon.com/{}",
            "CashApp": "https://cash.app/${}",
            "Venmo": "https://venmo.com/{}",
            "PayPal": "https://paypal.me/{}",
            "VK": "https://vk.com/{}",
            "Weibo": "https://weibo.com/{}",
            "Dev.to": "https://dev.to/{}",
            "CodePen": "https://codepen.io/{}",
            "StackOverflow": "https://stackoverflow.com/users/{}",
            "Behance": "https://behance.net/{}",
            "Dribbble": "https://dribbble.com/{}",
            "Fiverr": "https://fiverr.com/{}",
            "Upwork": "https://upwork.com/freelancers/{}",
            "AngelList": "https://angel.co/u/{}",
            "ProductHunt": "https://producthunt.com/@{}",
            "Mastodon": "https://mastodon.social/@{}",
            "Keybase": "https://keybase.io/{}",
            "Last.fm": "https://last.fm/user/{}",
            "Goodreads": "https://goodreads.com/user/show/{}",
            "Letterboxd": "https://letterboxd.com/{}",
            "Imgur": "https://imgur.com/user/{}",
            "Flickr": "https://flickr.com/photos/{}",
            "500px": "https://500px.com/p/{}",
            "WordPress": "https://{}.wordpress.com",
            "Blogger": "https://{}.blogspot.com",
            "Ghost": "https://{}.ghost.io",
            "Wikipedia": "https://en.wikipedia.org/wiki/User:{}",
            "SourceForge": "https://sourceforge.net/u/{}",
            "PyPI": "https://pypi.org/user/{}",
            "npm": "https://www.npmjs.com/~{}",
            "Docker Hub": "https://hub.docker.com/u/{}",
            "HackerRank": "https://hackerrank.com/{}",
            "Kaggle": "https://kaggle.com/{}",
            "Bitbucket": "https://bitbucket.org/{}",
            "Replit": "https://replit.com/@{}",
            "Glitch": "https://glitch.com/@{}",
            "Codeberg": "https://codeberg.org/{}",
            "Gitea": "https://gitea.com/{}",
            "Launchpad": "https://launchpad.net/~{}",
            "RubyGems": "https://rubygems.org/profiles/{}",
            "Packagist": "https://packagist.org/packages/{}/",
            "HuggingFace": "https://huggingface.co/{}",
            "Carrd": "https://{}.carrd.co",
            "Linktree": "https://linktr.ee/{}",
            "Bio.link": "https://bio.link/{}",
            "About.me": "https://about.me/{}",
            "Gravatar": "https://gravatar.com/{}",
            "Disqus": "https://disqus.com/by/{}",
            "SlideShare": "https://slideshare.net/{}",
            "Mix": "https://mix.com/{}",
            "Flipboard": "https://flipboard.com/@{}",
            "Pocket": "https://getpocket.com/@{}",
            "Instapaper": "https://instapaper.com/p/{}",
            "Trello": "https://trello.com/{}",
            "Notion": "https://notion.so/{}",
            "Airtable": "https://airtable.com/shr{}",
            "Canva": "https://canva.com/{}",
            "Prezi": "https://prezi.com/p/{}",
            "Calendly": "https://calendly.com/{}",
            "Acuity": "https://acuityscheduling.com/schedule/{}",
            "Typeform": "https://typeform.com/u/{}",
            "JotForm": "https://jotform.com/{}",
            "SurveyMonkey": "https://surveymonkey.com/usr/{}",
            "Google Sites": "https://sites.google.com/view/{}",
            "Carrd": "https://{}.carrd.co",
            "Maze": "https://maze.co/users/{}",
            "UserTesting": "https://utest.com/users/{}",
            "Toptal": "https://toptal.com/resume/{}",
            "Gun.io": "https://gun.io/freelancers/{}",
            "Arc.dev": "https://arc.dev/developers/{}",
            "Freelancer": "https://freelancer.com/u/{}",
            "Guru": "https://guru.com/freelancers/{}",
            "PeoplePerHour": "https://peopleperhour.com/freelancer/{}",
            "TaskRabbit": "https://taskrabbit.com/profile/{}",
            "Thumbtack": "https://thumbtack.com/pro/{}",
            "Bark": "https://bark.com/profile/{}",
            "Checkatrade": "https://checkatrade.com/trades/{}",
            "Trustatrader": "https://trustatrader.com/traders/{}",
            "Yelp": "https://yelp.com/biz/{}",
            "TripAdvisor": "https://tripadvisor.com/members/{}",
            "Booking.com": "https://booking.com/hotel/{}.html",
            "Airbnb": "https://airbnb.com/users/show/{}",
            "VRBO": "https://vrbo.com/{}",
            "HomeAway": "https://homeaway.com/vacation-rentals/{}",
            "Couchsurfing": "https://couchsurfing.com/people/{}",
            "Hostelworld": "https://hostelworld.com/pfd/{}",
            "TrustedHousesitters": "https://trustedhousesitters.com/members/profile/{}",
            "Workaway": "https://workaway.info/{}",
            "Worldpackers": "https://worldpackers.com/users/{}",
            "HelpX": "https://helpx.net/hosts/{}.html",
            "AuPairWorld": "https://aupairworld.com/en/member/{}",
            "Care.com": "https://care.com/c/{}",
            "Sittercity": "https://sittercity.com/profiles/{}",
            "UrbanSitter": "https://urbansitter.com/profile/{}",
            "Rover": "https://rover.com/members/profile/{}",
            "Wag": "https://wagwalking.com/walker/{}",
            "Tailster": "https://tailster.com/sitter/{}",
            "DogBuddy": "https://dogbuddy.com/sitter/{}",
            "BorrowMyDoggy": "https://borrowmydoggy.com/members/{}",
            "PetBacker": "https://petbacker.com/profile/{}",
            "HouseSitMatch": "https://housesitmatch.com/members-profile.php?m={}",
            "MindBodyOnline": "https://mindbodyonline.com/studio/{}",
            "ClassPass": "https://classpass.com/profile/{}",
            "Peloton": "https://onepeloton.com/members/{}",
            "Strava": "https://strava.com/athletes/{}",
            "Garmin Connect": "https://connect.garmin.com/modern/profile/{}",
            "Fitbit": "https://fitbit.com/user/{}",
            "MyFitnessPal": "https://myfitnesspal.com/profile/{}",
            "LoseIt": "https://loseit.com/members/{}",
            "Noom": "https://noom.com/profile/{}",
            "WeightWatchers": "https://weightwatchers.com/us/member/{}",
            "Nike Run Club": "https://nike.com/members/{}",
            "Adidas Running": "https://adidas.com/runners/{}",
            "Zwift": "https://zwiftpower.com/user.php?id={}",
            "TrainingPeaks": "https://trainingpeaks.com/athlete/{}",
            "Today's Plan": "https://todaysplan.com.au/athlete/{}",
            "Final Surge": "https://finalsurge.com/profile/{}",
            "Runalyze": "https://runalyze.com/user/{}",
            "SportTracks": "https://sporttracks.mobi/profile/{}",
            "Athlinks": "https://athlinks.com/event/results/athlete/{}",
            "MarathonGuide": "https://marathonguide.com/runner/{}",
            "UltraSignup": "https://ultrasignup.com/results.aspx?entryid={}",
            "RaceRaves": "https://raceraves.com/runners/{}",
            "BibRave": "https://bibrave.pro/bibravers/{}",
            "RunSignup": "https://runsignup.com/Profile/{}",
            "LetsRun": "https://letsrun.com/forum/profile/{}",
            "Runner's World": "https://runnersworld.com/runner/{}",
            "Cycling Weekly": "https://cyclingweekly.com/author/{}",
            "VeloNews": "https://velonews.com/author/{}",
            "Pinkbike": "https://pinkbike.com/u/{}/",
            "MTBR": "https://mtbr.com/members/{}.html",
            "RoadBikeReview": "https://roadbikereview.com/forums/members/{}.html",
            "Singletrack": "https://singletrackworld.com/forum/profile/{}/",
            "BikeForums": "https://bikeforums.net/members/{}.html",
            "Triathlete": "https://triathlete.com/author/{}",
            "Triathlon Magazine": "https://triathlonmagazine.ca/author/{}",
            "Slowtwitch": "https://slowtwitch.com/author/{}",
            "TriFind": "https://trifind.com/triathlete/{}",
            "USA Triathlon": "https://teamusa.org/athletes/{}",
            "Ironman": "https://ironman.com/athlete/{}",
            "Challenge Family": "https://challenge-family.com/athlete/{}",
            "Xterra": "https://xterraplanet.com/athlete/{}",
            "Trail Runner Nation": "https://trailrunnernation.com/community/members/{}",
            "Ultrarunning Magazine": "https://ultrarunning.com/runner/{}",
            "iRunFar": "https://irunfar.com/author/{}",
            "Trail Run Project": "https://trailrunproject.com/user/{}",
            "AllTrails": "https://alltrails.com/member/{}",
            "Gaia GPS": "https://gaiagps.com/profile/{}",
            "FatMap": "https://fatmap.com/user/{}",
            "OnX Hunt": "https://onxmaps.com/hunt/profile/{}",
            "HuntStand": "https://huntstand.com/profile/{}",
            "BaseMap": "https://basemap.com/user/{}",
            "Avenza Maps": "https://avenzamaps.com/user/{}",
            "PeakVisor": "https://peakvisor.com/user/{}",
            "ViewRanger": "https://viewranger.com/en/profile/{}",
            "Komoot": "https://komoot.com/user/{}",
            "Relive": "https://relive.cc/u/{}",
            "Footpath": "https://footpathroute.com/user/{}",
            "MapMyRun": "https://mapmyrun.com/profile/{}",
            "MapMyRide": "https://mapmyride.com/profile/{}",
            "MapMyWalk": "https://mapmywalk.com/profile/{}",
            "MapMyHike": "https://mapmyhike.com/profile/{}",
            "Endomondo": "https://endomondo.com/profile/{}",
            "Sports Tracker": "https://sports-tracker.com/view_profile/{}",
            "Runkeeper": "https://runkeeper.com/user/{}",
            "Nike Training Club": "https://nike.com/ntc/profile/{}",
            "Freeletics": "https://freeletics.com/en/profiles/{}",
            "JEFIT": "https://jefit.com/exercises/profile/{}",
            "Strong": "https://strong.app/user/{}",
            "Hevy": "https://hevyapp.com/user/{}",
            "Gymaholic": "https://gymaholic.co/user/{}",
            "Caliber": "https://caliber.app/user/{}",
            "Alpha Progression": "https://alpha-progression.com/user/{}",
            "Boostcamp": "https://boostcamp.app/user/{}",
            "Fitbod": "https://fitbod.me/user/{}",
            "Centr": "https://centr.com/profile/{}",
            "Future": "https://future.fit/coach/{}",
            "Tonal": "https://tonal.com/profile/{}",
            "Tempo": "https://tempo.fit/profile/{}",
            "Mirror": "https://mirror.co/profile/{}",
            "NordicTrack": "https://nordictrack.com/profile/{}",
            "Peloton Digital": "https://onepeloton.com/members/{}",
            "Beachbody": "https://beachbodyondemand.com/profile/{}",
            "Daily Burn": "https://dailyburn.com/profile/{}",
            "Obé Fitness": "https://obefitness.com/profile/{}",
            "Alo Moves": "https://alomoves.com/profile/{}",
            "Glo": "https://glo.com/profile/{}",
            "Down Dog": "https://downdogapp.com/profile/{}",
            "Yoga with Adriene": "https://yogawithadriene.com/profile/{}",
            "CorePower Yoga": "https://corepoweryoga.com/profile/{}",
            "Pure Barre": "https://purebarre.com/profile/{}",
            "Barry's Bootcamp": "https://barrys.com/profile/{}",
            "Orangetheory": "https://orangetheory.com/profile/{}",
            "F45": "https://f45training.com/profile/{}",
            "CrossFit": "https://games.crossfit.com/athlete/{}",
            "WodWell": "https://wodwell.com/athlete/{}",
            "SugarWOD": "https://sugarwod.com/athlete/{}",
            "Beyond the Whiteboard": "https://btwb.com/profile/{}",
            "TrainHeroic": "https://trainheroic.com/athlete/{}",
            "PushPress": "https://pushpress.com/member/{}",
            "GymDesk": "https://gymdesk.com/member/{}",
            "ABC Fitness": "https://abcf fitness.com/member/{}",
            "Mindbody": "https://mindbodyonline.com/profile/{}",
            "Glofox": "https://glofox.com/member/{}",
            "Zen Planner": "https://zenplanner.com/member/{}",
            "Jackrabbit": "https://jackrabbit.club/member/{}",
            "RhinoFit": "https://rhinofitglobal.com/member/{}",
            "Lebert Fitness": "https://lebertfitness.com/member/{}",
            "TRX": "https://trxtraining.com/profile/{}",
            "Suspension Training": "https://suspensiontraining.com/profile/{}",
            "ViPR": "https://viprperformance.com/profile/{}",
            "Battle Rope": "https://battlerope.com/profile/{}",
            "Kettlebell Kings": "https://kettlebellkings.com/profile/{}",
            "Dragon Door": "https://dragondoor.com/profile/{}",
            "StrongFirst": "https://strongfirst.com/profile/{}",
            "RKC": "https://rkc.kettlebell.com/profile/{}",
            "IKFF": "https://ikff.net/profile/{}",
            "WKFF": "https://wkff.info/profile/{}",
            "IUKL": "https://iukl kettlebell.com/profile/{}",
            "AKC": "https://americankettlebellclub.com/profile/{}",
            "USA Weightlifting": "https://usaweightlifting.org/athlete/{}",
            "International Weightlifting": "https://iwf.sport/ranking/athlete/{}",
            "Powerlifting Watch": "https://powerliftingwatch.com/lifter/{}",
            "Open Powerlifting": "https://openpowerlifting.org/lifter/{}",
            "USAPL": "https://usapl.org/lifter/{}",
            "IPF": "https://powerlifting-ipf.com/lifter/{}",
            "GPC": "https://gpcworld.us/lifter/{}",
            "WPC": "https://wpc-lifters.com/lifter/{}",
            "APA": "https://americanpowerlifting.com/lifter/{}",
            "NASA": "https://nasapowerlifting.com/lifter/{}",
            "100% Raw": "https://100rawpowerlifting.com/lifter/{}",
            "Raw Unity": "https://rawunity.com/lifter/{}",
            "Women's Powerlifting": "https://womenspowerlifting.com/lifter/{}",
            "Teen Powerlifting": "https://teenpowerlifting.com/lifter/{}",
            "Masters Powerlifting": "https://masterspowerlifting.com/lifter/{}",
            "Junior Powerlifting": "https://juniorpowerlifting.com/lifter/{}",
            "Sub-Junior Powerlifting": "https://subjuniorpowerlifting.com/lifter/{}",
            "Veterans Powerlifting": "https://veteranspowerlifting.com/lifter/{}",
            "Senior Powerlifting": "https://seniorpowerlifting.com/lifter/{}",
            "Grand Masters Powerlifting": "https://grandmasterspowerlifting.com/lifter/{}",
        }

    async def check_platform(self, session: aiohttp.ClientSession, platform: str, url: str, username: str) -> PlatformResult:
        full_url = url.format(username)
        start_time = time.time()
        
        try:
            async with session.get(full_url, timeout=self.timeout, allow_redirects=True) as response:
                response_time = round(time.time() - start_time, 2)
                status_code = response.status
                
                if status_code == 200:
                    status = "found"
                elif status_code == 404:
                    status = "not_found"
                elif status_code == 403:
                    status = "found"
                else:
                    status = "unknown"
                    
                return PlatformResult(
                    platform=platform,
                    url=full_url,
                    status=status,
                    status_code=status_code,
                    response_time=response_time
                )
        except asyncio.TimeoutError:
            return PlatformResult(
                platform=platform,
                url=full_url,
                status="error",
                status_code=None,
                response_time=round(time.time() - start_time, 2),
                error_message="Timeout"
            )
        except Exception as e:
            return PlatformResult(
                platform=platform,
                url=full_url,
                status="error",
                status_code=None,
                response_time=round(time.time() - start_time, 2),
                error_message=str(e)
            )

    async def scan_username(self, username: str, category: Optional[str] = None) -> ReconReport:
        print(f"\n{Colors.OKCYAN}╔════════════════════════════════════════╗")
        print(f"║   NexusRecon - Advanced OSINT Scanner  ║")
        print(f"╚════════════════════════════════════════╝{Colors.ENDC}\n")
        print(f"{Colors.BOLD}Target:{Colors.ENDC} {username}")
        print(f"{Colors.BOLD}Platforms:{Colors.ENDC} {len(self.platforms)}")
        print(f"{Colors.BOLD}Started:{Colors.ENDC} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        start_time = time.time()
        
        async with aiohttp.ClientSession() as session:
            semaphore = asyncio.Semaphore(self.max_concurrent)
            
            async def bounded_check(platform, url):
                async with semaphore:
                    return await self.check_platform(session, platform, url, username)
            
            tasks = [bounded_check(platform, url) for platform, url in self.platforms.items()]
            results = await asyncio.gather(*tasks)
        
        scan_duration = round(time.time() - start_time, 2)
        
        found = [r for r in results if r.status == "found"]
        not_found = [r for r in results if r.status == "not_found"]
        errors = [r for r in results if r.status == "error"]
        
        report = ReconReport(
            username=username,
            timestamp=datetime.now().isoformat(),
            total_platforms=len(results),
            found_count=len(found),
            not_found_count=len(not_found),
            error_count=len(errors),
            results=results,
            scan_duration=scan_duration
        )
        
        self._print_results(report)
        return report

    def _print_results(self, report: ReconReport):
        print(f"\n{Colors.OKGREEN}{'='*60}{Colors.ENDC}")
        print(f"{Colors.BOLD}SCAN COMPLETE{Colors.ENDC}")
        print(f"{Colors.OKGREEN}{'='*60}{Colors.ENDC}\n")
        
        print(f"{Colors.BOLD}Summary:{Colors.ENDC}")
        print(f"  • Total Platforms: {report.total_platforms}")
        print(f"  • {Colors.OKGREEN}Found: {report.found_count}{Colors.ENDC}")
        print(f"  • Not Found: {report.not_found_count}")
        print(f"  • Errors: {report.error_count}")
        print(f"  • Duration: {report.scan_duration}s\n")
        
        found_results = [r for r in report.results if r.status == "found"]
        
        if found_results:
            print(f"{Colors.OKGREEN}{Colors.BOLD}✓ FOUND ACCOUNTS:{Colors.ENDC}\n")
            for result in sorted(found_results, key=lambda x: x.platform):
                print(f"  {Colors.OKGREEN}✓{Colors.ENDC} {Colors.BOLD}{result.platform}{Colors.ENDC}")
                print(f"    └─ {result.url}")
                print(f"    └─ Status: {result.status_code} | Time: {result.response_time}s\n")
        
        error_results = [r for r in report.results if r.status == "error"]
        if error_results:
            print(f"\n{Colors.WARNING}⚠ ERRORS:{Colors.ENDC}\n")
            for result in sorted(error_results, key=lambda x: x.platform):
                print(f"  {Colors.WARNING}⚠{Colors.ENDC} {result.platform}: {result.error_message}")

    def save_report(self, report: ReconReport, format: str = "json"):
        os.makedirs("reports", exist_ok=True)
        filename = f"reports/{report.username}_{int(time.time())}.{format}"
        
        if format == "json":
            with open(filename, 'w') as f:
                json.dump({
                    'username': report.username,
                    'timestamp': report.timestamp,
                    'total_platforms': report.total_platforms,
                    'found_count': report.found_count,
                    'not_found_count': report.not_found_count,
                    'error_count': report.error_count,
                    'scan_duration': report.scan_duration,
                    'results': [
                        {
                            'platform': r.platform,
                            'url': r.url,
                            'status': r.status,
                            'status_code': r.status_code,
                            'response_time': r.response_time,
                            'error_message': r.error_message
                        } for r in report.results
                    ]
                }, f, indent=2)
        
        print(f"\n{Colors.OKBLUE}Report saved: {filename}{Colors.ENDC}")

def main():
    parser = argparse.ArgumentParser(
        description=f"{Colors.BOLD}NexusRecon - Advanced Username Enumeration Tool{Colors.ENDC}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.BOLD}Examples:{Colors.ENDC}
  python nexusrecon.py john_doe
  python nexusrecon.py john_doe --timeout 15 --workers 100
  python nexusrecon.py john_doe --output json
  python nexusrecon.py john_doe --category social
        """
    )
    
    parser.add_argument("username", help="Username to search")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout (default: 10s)")
    parser.add_argument("--workers", type=int, default=50, help="Max concurrent requests (default: 50)")
    parser.add_argument("--output", choices=["json", "txt"], default="json", help="Output format")
    parser.add_argument("--save", action="store_true", help="Save report to file")
    parser.add_argument("--category", help="Filter by category (social, tech, gaming, etc)")
    
    args = parser.parse_args()
    
    recon = NexusRecon(timeout=args.timeout, max_concurrent=args.workers)
    report = asyncio.run(recon.scan_username(args.username, args.category))
    
    if args.save:
        recon.save_report(report, args.output)

if __name__ == "__main__":
    main()
