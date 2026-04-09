#!/bin/bash
#
# MeshBBS Update Script
#
# This script updates MeshBBS to the latest version.
# Run as root or with sudo.
#
# Usage: sudo ./update.sh [OPTIONS]
#
# Options:
#   --backup        Create backup before updating
#   --restart       Restart services after update
#   --help          Show this help message
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CREATE_BACKUP=false
RESTART_SERVICES=false
MESHBBS_USER="meshbbs"
MESHBBS_HOME="/opt/meshbbs"
MESHBBS_DATA="/var/lib/meshbbs"
VENV_PATH="${MESHBBS_HOME}/venv"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --backup)
            CREATE_BACKUP=true
            shift
            ;;
        --restart)
            RESTART_SERVICES=true
            shift
            ;;
        --help)
            echo "MeshBBS Update Script"
            echo ""
            echo "Usage: sudo ./update.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --backup        Create backup before updating"
            echo "  --restart       Restart services after update"
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

# Check if MeshBBS is installed
if [ ! -d "$MESHBBS_HOME" ]; then
    echo -e "${RED}MeshBBS is not installed at $MESHBBS_HOME${NC}"
    exit 1
fi

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                MeshBBS Update Script                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

print_status() {
    echo -e "${GREEN}[*]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Detect script directory and source directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"

print_status "Source directory: $SOURCE_DIR"

# Step 1: Create backup if requested
if [ "$CREATE_BACKUP" = true ]; then
    print_status "Creating backup..."
    BACKUP_FILE="${MESHBBS_DATA}/backups/pre-update-$(date +%Y%m%d-%H%M%S).tar.gz"

    tar -czf "$BACKUP_FILE" \
        -C "$MESHBBS_DATA" \
        --exclude='backups' \
        . 2>/dev/null || true

    chown "$MESHBBS_USER:$MESHBBS_USER" "$BACKUP_FILE"
    print_status "Backup created: $BACKUP_FILE"
fi

# Step 2: Stop services
print_status "Stopping services..."
systemctl stop meshbbs-web.service 2>/dev/null || true
systemctl stop meshbbs.service 2>/dev/null || true

# Step 3: Update source files
print_status "Updating source files..."
rm -rf "$MESHBBS_HOME/src"
cp -r "$SOURCE_DIR/src" "$MESHBBS_HOME/"

# Update requirements if changed
if [ -f "$SOURCE_DIR/requirements.txt" ]; then
    cp "$SOURCE_DIR/requirements.txt" "$MESHBBS_HOME/"
fi

# Step 4: Update web interface
if [ -d "$MESHBBS_HOME/web" ] && [ -d "$SOURCE_DIR/web" ]; then
    print_status "Updating web interface..."

    # Keep node_modules to speed up update
    if [ -d "$MESHBBS_HOME/web/node_modules" ]; then
        mv "$MESHBBS_HOME/web/node_modules" /tmp/meshbbs_node_modules_backup
    fi

    rm -rf "$MESHBBS_HOME/web"
    cp -r "$SOURCE_DIR/web" "$MESHBBS_HOME/"

    # Restore node_modules
    if [ -d "/tmp/meshbbs_node_modules_backup" ]; then
        mv /tmp/meshbbs_node_modules_backup "$MESHBBS_HOME/web/node_modules"
    fi

    # Install any new dependencies
    cd "$MESHBBS_HOME/web"
    npm install --production

    # Rebuild
    print_status "Rebuilding web interface..."
    npm run build
fi

# Step 5: Update Python dependencies
print_status "Updating Python dependencies..."
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$MESHBBS_HOME/requirements.txt"

# Step 6: Set permissions
print_status "Setting permissions..."
chown -R "$MESHBBS_USER:$MESHBBS_USER" "$MESHBBS_HOME"

# Step 7: Restart services if requested
if [ "$RESTART_SERVICES" = true ]; then
    print_status "Restarting services..."
    systemctl start meshbbs.service
    systemctl start meshbbs-web.service

    # Wait and check status
    sleep 2
    if systemctl is-active --quiet meshbbs.service; then
        print_status "meshbbs.service is running"
    else
        print_warning "meshbbs.service failed to start"
    fi

    if systemctl is-active --quiet meshbbs-web.service; then
        print_status "meshbbs-web.service is running"
    else
        print_warning "meshbbs-web.service failed to start"
    fi
else
    print_warning "Services were stopped but not restarted."
    echo "  Start them manually with:"
    echo "    sudo systemctl start meshbbs"
    echo "    sudo systemctl start meshbbs-web"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 Update Complete!                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Show current version if available
if [ -f "$MESHBBS_HOME/src/version.py" ]; then
    VERSION=$("$VENV_PATH/bin/python" -c "from src.version import VERSION; print(VERSION)" 2>/dev/null || echo "unknown")
    echo -e "Installed version: ${BLUE}${VERSION}${NC}"
fi

echo ""
echo "Check the logs with:"
echo "  sudo journalctl -u meshbbs -f"
