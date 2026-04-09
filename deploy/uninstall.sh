#!/bin/bash
#
# MeshBBS Uninstallation Script
#
# This script removes MeshBBS from the system.
# Run as root or with sudo.
#
# Usage: sudo ./uninstall.sh [OPTIONS]
#
# Options:
#   --keep-data     Keep data directory (database, backups, config)
#   --help          Show this help message
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

KEEP_DATA=false
MESHBBS_USER="meshbbs"
MESHBBS_HOME="/opt/meshbbs"
MESHBBS_DATA="/var/lib/meshbbs"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --help)
            echo "MeshBBS Uninstallation Script"
            echo ""
            echo "Usage: sudo ./uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --keep-data     Keep data directory (database, backups, config)"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

echo -e "${YELLOW}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              MeshBBS Uninstallation Script                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Confirm uninstallation
read -p "Are you sure you want to uninstall MeshBBS? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled."
    exit 0
fi

print_status() {
    echo -e "${GREEN}[*]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Step 1: Stop services
print_status "Stopping services..."
systemctl stop meshbbs-web.service 2>/dev/null || true
systemctl stop meshbbs.service 2>/dev/null || true

# Step 2: Disable services
print_status "Disabling services..."
systemctl disable meshbbs-web.service 2>/dev/null || true
systemctl disable meshbbs.service 2>/dev/null || true

# Step 3: Remove service files
print_status "Removing service files..."
rm -f /etc/systemd/system/meshbbs.service
rm -f /etc/systemd/system/meshbbs-web.service
systemctl daemon-reload

# Step 4: Remove application directory
print_status "Removing application directory..."
rm -rf "$MESHBBS_HOME"

# Step 5: Remove data directory (if not keeping)
if [ "$KEEP_DATA" = false ]; then
    print_warning "Removing data directory (database, backups, config)..."
    rm -rf "$MESHBBS_DATA"
else
    print_status "Keeping data directory: $MESHBBS_DATA"
fi

# Step 6: Remove log directory
print_status "Removing log directory..."
rm -rf /var/log/meshbbs

# Step 7: Remove user (if exists and not system user)
if id "$MESHBBS_USER" &>/dev/null; then
    print_status "Removing user '$MESHBBS_USER'..."
    userdel "$MESHBBS_USER" 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Uninstallation Complete!                       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$KEEP_DATA" = true ]; then
    echo -e "Data preserved at: ${YELLOW}${MESHBBS_DATA}${NC}"
    echo ""
fi

echo "MeshBBS has been removed from the system."
