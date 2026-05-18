#!/bin/bash

# NexusRecon Ultimate - Quick Start Script
# Advanced OSINT Framework with Username, Email, Phone, Domain Recon

VERSION="1.0.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check Python
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}[!] Python 3 is not installed${NC}"
        exit 1
    fi
}

# Install dependencies
install_deps() {
    echo -e "${CYAN}[*] Installing dependencies...${NC}"
    pip3 install -r "$SCRIPT_DIR/requirements.txt" --quiet
    echo -e "${GREEN}[✓] Dependencies installed${NC}"
}

# Show help
show_help() {
    cat << EOF
${CYAN}╔══════════════════════════════════════════════════════════╗
║  NexusRecon Ultimate v${VERSION}                              ║
║  Advanced OSINT Framework                                     ║
╚══════════════════════════════════════════════════════════╝${NC}

${GREEN}USAGE:${NC}
    $0 [OPTIONS] <target>

${GREEN}OPTIONS:${NC}
    -u, --username <name>   Scan username across 260+ platforms
    -e, --email <address>   Scan email (G-Hunt/Holehe style)
    -p, --phone <number>    Scan phone number
    -d, --domain <domain>   Scan domain (WHOIS, subdomains)
    -t, --timeout <sec>     Request timeout (default: 10)
    -w, --workers <num>     Concurrent workers (default: 50)
    -s, --save              Save results to JSON file
    -v, --verbose           Verbose output
    -i, --install           Install dependencies
    -h, --help              Show this help message

${GREEN}EXAMPLES:${NC}
    $0 -u elonmusk                  # Scan username
    $0 -e test@gmail.com            # Scan email
    $0 -p +1234567890               # Scan phone
    $0 -d example.com               # Scan domain
    $0 -u username --save           # Save results
    $0 -u username -t 5 -w 30       # Custom settings
    $0 --install                    # Install dependencies

${GREEN}MODULES:${NC}
    • Username Scanner (Sherlock-style) - 260+ platforms
    • Email OSINT (G-Hunt/Holehe-style) - Provider detection
    • Phone Recon - Country, carrier, line type
    • Domain Recon - WHOIS, subdomains, emails

${CYAN}Inspired by: Sherlock, G-Hunt, Holehe, Flowsint${NC}
EOF
}

# Main
main() {
    if [ "$1" == "--install" ] || [ "$1" == "-i" ]; then
        install_deps
        exit 0
    fi

    if [ "$1" == "--help" ] || [ "$1" == "-h" ] || [ -z "$1" ]; then
        show_help
        exit 0
    fi

    # Run the Python script with all arguments
    python3 "$SCRIPT_DIR/main.py" "$@"
}

main "$@"
