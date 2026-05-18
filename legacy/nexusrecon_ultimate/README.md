# 🚀 NexusRecon Ultimate

**Advanced OSINT Framework** - Username, Email, Phone & Domain Reconnaissance

Inspired by: **Sherlock**, **G-Hunt**, **Holehe**, **Flowsint**

---

## ✨ Features

### 🔍 Multi-Module OSINT
- **Username Scanner** - Check 260+ platforms (Sherlock-style)
- **Email OSINT** - Provider detection, service enumeration (G-Hunt/Holehe-style)
- **Phone Recon** - Country, carrier, line type detection
- **Domain Recon** - WHOIS, subdomains, associated emails

### ⚡ Performance
- **Async/Await** - Non-blocking I/O operations
- **Multi-threaded** - Configurable workers (default: 50)
- **Fast Scanning** - Scan 260+ platforms in ~9 seconds
- **Smart Timeout** - Configurable per-request timeout

### 🎨 User Experience
- **Beautiful CLI** - Color-coded terminal output
- **JSON Reports** - Auto-save detailed reports
- **Error Handling** - Graceful handling of timeouts, SSL errors
- **Verbose Mode** - Detailed debugging information

---

## 📦 Installation

### Quick Install
```bash
cd nexusrecon_ultimate

# Install dependencies
pip3 install -r requirements.txt

# Or use the quick script
./nexusrecon.sh --install
```

### Requirements
- Python 3.8+
- aiohttp
- colorama
- requests
- beautifulsoup4
- dnspython
- phonenumbers
- email-validator

---

## 🚀 Usage

### Basic Commands

#### Username Scan
```bash
# Scan username across 260+ platforms
python main.py -u elonmusk

# Save results to JSON
python main.py -u elonmusk --save

# Custom timeout and workers
python main.py -u username -t 5 -w 30
```

#### Email Scan
```bash
# Scan email (G-Hunt/Holehe style)
python main.py -e test@gmail.com

# Save results
python main.py -e target@company.com --save
```

#### Phone Scan
```bash
# Scan phone number
python main.py -p +1234567890

# International format
python main.py -p +44-20-7946-0958
```

#### Domain Scan
```bash
# Scan domain
python main.py -d example.com

# Save full report
python main.py -d target.com --save
```

### Using Shell Script
```bash
# Show help
./nexusrecon.sh --help

# Quick scan
./nexusrecon.sh -u username

# Full recon with save
./nexusrecon.sh -u username -e email@test.com -d domain.com --save
```

### Command Line Options
```
-u, --username <name>   Scan username across 260+ platforms
-e, --email <address>   Scan email (G-Hunt/Holehe style)
-p, --phone <number>    Scan phone number
-d, --domain <domain>   Scan domain (WHOIS, subdomains)
-t, --timeout <sec>     Request timeout (default: 10)
-w, --workers <num>     Concurrent workers (default: 50)
-s, --save              Save results to JSON file
-v, --verbose           Verbose output
-h, --help              Show help message
```

---

## 📊 Modules Detail

### 1. Username Scanner (Sherlock-style)
Checks username availability across **260+ platforms**:

**Categories:**
- **Social Media**: Facebook, Twitter, Instagram, TikTok, LinkedIn, Reddit, Pinterest, Snapchat
- **Tech Platforms**: GitHub, GitLab, StackOverflow, Dev.to, npm, PyPI, Docker Hub
- **Gaming**: Steam, Twitch, Discord, Xbox, PlayStation, Epic Games, Roblox
- **Fitness**: Strava, Peloton, Garmin, Fitbit, MyFitnessPal
- **E-commerce**: eBay, Etsy, Poshmark, Mercari, Depop
- **Creative**: Behance, Dribbble, ArtStation, Flickr, Vimeo, SoundCloud
- **Blogging**: Medium, WordPress, Blogger, Tumblr, Substack
- **Professional**: AngelList, ProductHunt, Crunchbase
- **Finance**: PayPal, CashApp, Venmo
- **Travel**: TripAdvisor, Airbnb, Booking.com
- **Food**: Yelp, Zomato, Uber Eats
- **+200 more platforms!**

### 2. Email Module (G-Hunt/Holehe-style)
Advanced email reconnaissance:

**Features:**
- Email format validation
- Provider detection (Gmail, Outlook, Yahoo, ProtonMail, etc.)
- Service enumeration
- Breach data checking (future)
- Account existence verification

**Supported Providers:**
- Google (Gmail, GoogleMail)
- Microsoft (Outlook, Hotmail, Live)
- Apple (iCloud, Me, Mac)
- Yahoo, Yandex, Mail.ru
- ProtonMail, Tutanota
- Regional providers (Orange, Free, SFR, etc.)

### 3. Phone Module
Phone number intelligence:

**Features:**
- Country code detection
- Carrier identification
- Line type detection (mobile, landline, VoIP)
- Format normalization
- Account linkage (future)

**Supported Countries:**
- US/CA, UK, EU, Russia, China, Japan, India
- Brazil, Mexico, Argentina
- Australia, South Africa, Nigeria
- Middle East, Southeast Asia
- +50 countries total

### 4. Domain Module
Domain reconnaissance:

**Features:**
- WHOIS lookup
- Registration details
- Nameserver enumeration
- Subdomain discovery
- Associated email finding
- DNS records analysis (future)

---

## 📁 Project Structure

```
nexusrecon_ultimate/
├── main.py              # Core scanner with all modules
├── nexusrecon.sh        # Quick start shell script
├── requirements.txt     # Python dependencies
├── README.md            # This file
├── LICENSE              # MIT License
├── core/                # Core engine modules
├── modules/             # Additional OSINT modules
├── data/                # Platform signatures, configs
├── templates/           # Report templates
└── reports/             # Saved JSON reports
    ├── username_elonmusk_20240101_120000.json
    ├── email_test_at_gmail_20240101_120500.json
    └── domain_example_dot_com_20240101_121000.json
```

---

## 🎯 Examples

### Example 1: Full Username Scan
```bash
$ python main.py -u github

╔══════════════════════════════════════════════════════════╗
║  _   _                   ____  _             _           ║
║ | \ | |_   _ _ __ ___   |  _ \| |_ __ _  ___| |__        ║
║ |  \| | | | | '_ ` _ \  | |_) | __/ _` |/ __| '_ \       ║
║ | |\  | |_| | | | | | | |  __/| || (_| | (__| | | |      ║
║ |_| \_|\__,_|_| |_| |_| |_|    \__\__,_|\___|_| |_|      ║
║                                                          ║
║ Ultimate OSINT Framework                                 ║
║ Username • Email • Phone • Domain Recon                  ║
║ Inspired by: Sherlock, G-Hunt, Holehe, Flowsint          ║
╚══════════════════════════════════════════════════════════╝

[*] Scanning username: github
[*] Checking 119 platforms...

[+] Found on github (https://github.com/github)
[+] Found on twitter (https://twitter.com/github)
[+] Found on instagram (https://instagram.com/github)
[+] Found on linkedin (https://linkedin.com/company/github)
...

[+] Found: 87
[!] Errors: 3
[-] Not Found: 29

[✓] Report saved: reports/username_github_20240101_120000.json
```

### Example 2: Email Investigation
```bash
$ python main.py -e john.doe@gmail.com

[*] Scanning email: john.doe@gmail.com

[+] Valid: True
[+] Providers: Google
[+] Accounts Found: 1

[✓] Report saved: reports/email_john_doe_at_gmail_20240101_120500.json
```

### Example 3: Domain Intelligence
```bash
$ python main.py -d google.com

[*] Scanning domain: google.com

[+] Registered: True
[+] Registrar: MarkMonitor Inc.
[+] Creation Date: 1997-09-15
[+] Subdomains Found: 8
[+] Emails Found: 3

[✓] Report saved: reports/domain_google_dot_com_20240101_121000.json
```

---

## 🔧 Advanced Configuration

### Custom Timeout & Workers
```bash
# Faster scan with more workers
python main.py -u username -w 100 -t 5

# Slower but more reliable
python main.py -u username -w 20 -t 30
```

### Verbose Mode
```bash
# See detailed errors and progress
python main.py -u username -v
```

### Batch Processing
```bash
# Scan multiple usernames
for user in user1 user2 user3; do
    python main.py -u $user --save
done

# Scan multiple emails
while read email; do
    python main.py -e $email --save
done < emails.txt
```

---

## 🛡️ Legal & Ethical Use

**IMPORTANT**: This tool is for **educational and authorized security research only**.

- ✅ Use on your own accounts/data
- ✅ Use with explicit permission
- ✅ Use for legitimate security audits
- ❌ Do NOT use for harassment or stalking
- ❌ Do NOT use for unauthorized access
- ❌ Respect privacy and terms of service

**Disclaimer**: The authors are not responsible for misuse of this tool.

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:

- [ ] Add more platforms to username scanner
- [ ] Integrate real breach databases
- [ ] Add social media scraping
- [ ] Implement API integrations (Hunter.io, HaveIBeenPwned)
- [ ] Add GUI/TUI interface
- [ ] Docker container support
- [ ] REST API endpoint
- [ ] Export to CSV, PDF formats

---

## 📚 Inspiration

This project draws inspiration from:

- **[Sherlock](https://github.com/sherlock-project/sherlock)** - Username search
- **[G-Hunt](https://github.com/mxrch/GHunt)** - Google account investigation
- **[Holehe](https://github.com/megadose/holehe)** - Email enumeration
- **[Flowsint](https://github.com/reconurge/flowsint)** - OSINT workflows

---

## 📄 License

MIT License - See [LICENSE](LICENSE) file

---

## 🙏 Support

If you find this tool useful:

- ⭐ Star this repository
- 🐛 Report bugs and issues
- 💡 Suggest new features
- 🔧 Submit pull requests

---

**Made with ❤️ by the OSINT Community**

*Happy (ethical) hunting! 🕵️*
