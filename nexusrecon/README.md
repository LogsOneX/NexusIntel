# NexusRecon - Advanced OSINT Framework

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

**NexusRecon** is an advanced multi-threaded username enumeration tool inspired by Sherlock and Flowsint. It scans 260+ platforms to find where a specific username is registered.

## 🚀 Features

- **260+ Platforms**: Supports social media, development, gaming, fitness, e-commerce, and more
- **Multi-threaded Scanning**: Async HTTP requests for fast scanning (50 concurrent by default)
- **Beautiful Terminal Output**: Color-coded results with clear status indicators
- **JSON Reports**: Save detailed reports for later analysis
- **Customizable**: Adjust timeout, workers, and filter by categories
- **Error Handling**: Gracefully handles timeouts, SSL errors, and connection issues
- **Risk Scoring**: Calculates digital footprint risk level

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/nexusrecon.git
cd nexusrecon

# Install dependencies
pip install aiohttp

# Run the tool
python main.py <username>
```

## 🎯 Usage

### Basic Scan
```bash
python main.py john_doe
```

### Advanced Options
```bash
# Custom timeout and workers
python main.py john_doe --timeout 15 --workers 100

# Save report to JSON
python main.py john_doe --save

# Combine options
python main.py john_doe --timeout 5 --workers 50 --save
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `username` | Username to search (required) | - |
| `--timeout` | Request timeout in seconds | 10 |
| `--workers` | Max concurrent requests | 50 |
| `--output` | Output format (json/txt) | json |
| `--save` | Save report to file | False |
| `--category` | Filter by category | All |

## 📊 Example Output

```
╔════════════════════════════════════════╗
║   NexusRecon - Advanced OSINT Scanner  ║
╚════════════════════════════════════════╝

Target: github
Platforms: 260
Started: 2024-01-15 10:30:45

============================================================
SCAN COMPLETE
============================================================

Summary:
  • Total Platforms: 260
  • Found: 130
  • Not Found: 79
  • Errors: 38
  • Duration: 9.44s

✓ FOUND ACCOUNTS:

  ✓ GitHub
    └─ https://github.com/github
    └─ Status: 200 | Time: 1.1s

  ✓ Instagram
    └─ https://instagram.com/github
    └─ Status: 200 | Time: 0.78s

  ✓ Twitter
    └─ https://twitter.com/github
    └─ Status: 200 | Time: 0.54s

⚠ ERRORS:

  ⚠ SomePlatform: Timeout
  ⚠ AnotherPlatform: Connection refused
```

## 🗂️ Platform Categories

NexusRecon scans across multiple categories:

### Social Media
- Facebook, Twitter, Instagram, LinkedIn, TikTok
- Pinterest, Snapchat, Reddit, Tumblr, VK

### Development & Tech
- GitHub, GitLab, Bitbucket, StackOverflow
- Dev.to, CodePen, Replit, PyPI, npm
- Docker Hub, HackerRank, Kaggle

### Gaming
- Steam, Xbox, PlayStation, Epic Games
- Roblox, Twitch, Discord

### Communication
- Telegram, WhatsApp, Signal, Slack

### Fitness & Sports
- Strava, Garmin Connect, Fitbit
- Peloton, MyFitnessPal, Nike Run Club

### E-commerce
- eBay, Etsy, Amazon, Poshmark
- Mercari, Depop, StockX

### Professional
- AngelList, Behance, Dribbble
- Fiverr, Upwork, Toptal

### Content Creation
- YouTube, Vimeo, SoundCloud, Spotify
- Medium, Substack, Patreon

### And 200+ More!

## 📁 Report Format

Reports are saved in JSON format with detailed information:

```json
{
  "username": "github",
  "timestamp": "2024-01-15T10:30:45",
  "total_platforms": 260,
  "found_count": 130,
  "not_found_count": 79,
  "error_count": 38,
  "scan_duration": 9.44,
  "results": [
    {
      "platform": "GitHub",
      "url": "https://github.com/github",
      "status": "found",
      "status_code": 200,
      "response_time": 1.1,
      "error_message": null
    }
  ]
}
```

## 🔧 Configuration

### Performance Tuning

For faster scans (less accurate):
```bash
python main.py username --timeout 3 --workers 100
```

For more accurate scans (slower):
```bash
python main.py username --timeout 15 --workers 20
```

### Handling Rate Limits

If you encounter rate limiting:
```bash
python main.py username --timeout 10 --workers 10
```

## ⚠️ Disclaimer

This tool is for educational and ethical purposes only. Always:
- Respect platform terms of service
- Don't use for harassment or stalking
- Obtain proper authorization before scanning
- Use responsibly and legally

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Inspired by [Sherlock](https://github.com/sherlock-project/sherlock)
- Inspired by [Flowsint](https://github.com/reconurge/flowsint)
- Thanks to all platform maintainers for their APIs

## 📬 Support

For issues and questions:
- Create an issue on GitHub
- Email: support@nexusrecon.com

---

**Made with ❤️ by Your Name**

⭐ Star this repo if you find it useful!
