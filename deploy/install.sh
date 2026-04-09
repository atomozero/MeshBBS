#!/bin/bash
#
# MeshBBS Installation Script for Raspberry Pi
#
# This script installs MeshBBS on a Raspberry Pi running Raspberry Pi OS.
# Run as root or with sudo.
#
# Usage: sudo ./install.sh [OPTIONS]
#
# Options:
#   --dev           Install development dependencies
#   --no-web        Skip web interface installation
#   --serial-port   Specify serial port (default: /dev/ttyUSB0)
#   --help          Show this help message
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
INSTALL_DEV=false
INSTALL_WEB=true
SERIAL_PORT="/dev/ttyUSB0"
MESHBBS_USER="meshbbs"
MESHBBS_HOME="/opt/meshbbs"
MESHBBS_DATA="/var/lib/meshbbs"
VENV_PATH="${MESHBBS_HOME}/venv"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            INSTALL_DEV=true
            shift
            ;;
        --no-web)
            INSTALL_WEB=false
            shift
            ;;
        --serial-port)
            SERIAL_PORT="$2"
            shift 2
            ;;
        --help)
            echo "MeshBBS Installation Script"
            echo ""
            echo "Usage: sudo ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dev           Install development dependencies"
            echo "  --no-web        Skip web interface installation"
            echo "  --serial-port   Specify serial port (default: /dev/ttyUSB0)"
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

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              MeshBBS Installation Script                   ║"
echo "║                    for Raspberry Pi                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}[*]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[x]${NC} $1"
}

# Detect script directory and source directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(dirname "$SCRIPT_DIR")"

print_status "Source directory: $SOURCE_DIR"
print_status "Installing to: $MESHBBS_HOME"
print_status "Data directory: $MESHBBS_DATA"
print_status "Serial port: $SERIAL_PORT"

# Step 1: Update system
print_status "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

# Step 2: Install system dependencies
print_status "Installing system dependencies..."
apt-get install -y -qq \
    python3 \
    python3-pip \
    python3-venv \
    git \
    sqlite3

# Install Node.js for web interface
if [ "$INSTALL_WEB" = true ]; then
    print_status "Installing Node.js..."
    if ! command -v node &> /dev/null; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y -qq nodejs
    else
        print_warning "Node.js already installed: $(node --version)"
    fi
fi

# Step 3: Create meshbbs user if not exists
if ! id "$MESHBBS_USER" &>/dev/null; then
    print_status "Creating user '$MESHBBS_USER'..."
    useradd -r -s /bin/false -d "$MESHBBS_HOME" "$MESHBBS_USER"
else
    print_warning "User '$MESHBBS_USER' already exists"
fi

# Add user to dialout group for serial port access
usermod -aG dialout "$MESHBBS_USER"

# Step 4: Create directories
print_status "Creating directories..."
mkdir -p "$MESHBBS_HOME"
mkdir -p "$MESHBBS_DATA"
mkdir -p "$MESHBBS_DATA/backups"
mkdir -p /var/log/meshbbs

# Step 5: Copy source files
print_status "Copying source files..."
cp -r "$SOURCE_DIR/src" "$MESHBBS_HOME/"
cp "$SOURCE_DIR/requirements.txt" "$MESHBBS_HOME/"
cp "$SOURCE_DIR/pytest.ini" "$MESHBBS_HOME/" 2>/dev/null || true

# Copy web interface if enabled
if [ "$INSTALL_WEB" = true ]; then
    print_status "Copying web interface..."
    cp -r "$SOURCE_DIR/web" "$MESHBBS_HOME/"
fi

# Step 6: Create Python virtual environment
print_status "Creating Python virtual environment..."
python3 -m venv "$VENV_PATH"

# Step 7: Install Python dependencies
print_status "Installing Python dependencies..."
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$MESHBBS_HOME/requirements.txt"

if [ "$INSTALL_DEV" = true ]; then
    print_status "Installing development dependencies..."
    "$VENV_PATH/bin/pip" install black isort mypy pytest-cov
fi

# Step 8: Install web interface dependencies
if [ "$INSTALL_WEB" = true ]; then
    print_status "Installing web interface dependencies..."
    cd "$MESHBBS_HOME/web"
    npm install --production

    # Build production version
    print_status "Building web interface..."
    npm run build
fi

# Step 9: Create configuration file
print_status "Creating configuration file..."
cat > "$MESHBBS_DATA/config.env" << EOF
# MeshBBS Configuration
# Edit this file to customize your BBS

# BBS Identity
BBS_NAME=MeshBBS
BBS_WELCOME="Welcome to MeshBBS!"

# Serial Port
SERIAL_PORT=${SERIAL_PORT}
BAUD_RATE=115200

# Database
DATABASE_PATH=${MESHBBS_DATA}/meshbbs.db

# Web Interface
WEB_HOST=0.0.0.0
WEB_PORT=8080

# JWT Secret (auto-generated, keep secure!)
JWT_SECRET=$(openssl rand -hex 32)

# Admin credentials (change after first login!)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=meshbbs123

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/meshbbs/meshbbs.log

# Backup
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=24
BACKUP_PATH=${MESHBBS_DATA}/backups

# Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_COMMANDS_PER_MINUTE=30
EOF

# Step 10: Create systemd service files
print_status "Creating systemd service files..."

# Main BBS service
cat > /etc/systemd/system/meshbbs.service << EOF
[Unit]
Description=MeshBBS Core Service
After=network.target

[Service]
Type=simple
User=${MESHBBS_USER}
Group=${MESHBBS_USER}
WorkingDirectory=${MESHBBS_HOME}
EnvironmentFile=${MESHBBS_DATA}/config.env
ExecStart=${VENV_PATH}/bin/python -m src.main
Restart=always
RestartSec=10

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${MESHBBS_DATA} /var/log/meshbbs
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Web API service
cat > /etc/systemd/system/meshbbs-web.service << EOF
[Unit]
Description=MeshBBS Web API Service
After=network.target meshbbs.service

[Service]
Type=simple
User=${MESHBBS_USER}
Group=${MESHBBS_USER}
WorkingDirectory=${MESHBBS_HOME}
EnvironmentFile=${MESHBBS_DATA}/config.env
ExecStart=${VENV_PATH}/bin/uvicorn src.web.main:app --host \${WEB_HOST} --port \${WEB_PORT}
Restart=always
RestartSec=10

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${MESHBBS_DATA} /var/log/meshbbs
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Step 11: Set permissions
print_status "Setting permissions..."
chown -R "$MESHBBS_USER:$MESHBBS_USER" "$MESHBBS_HOME"
chown -R "$MESHBBS_USER:$MESHBBS_USER" "$MESHBBS_DATA"
chown -R "$MESHBBS_USER:$MESHBBS_USER" /var/log/meshbbs
chmod 600 "$MESHBBS_DATA/config.env"
chmod 755 "$MESHBBS_HOME"

# Step 12: Reload systemd
print_status "Reloading systemd..."
systemctl daemon-reload

# Step 13: Enable services (but don't start yet)
print_status "Enabling services..."
systemctl enable meshbbs.service
systemctl enable meshbbs-web.service

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Installation Complete!                         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Configuration file: ${BLUE}${MESHBBS_DATA}/config.env${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit the configuration file:"
echo -e "     ${YELLOW}sudo nano ${MESHBBS_DATA}/config.env${NC}"
echo ""
echo "  2. Connect your companion radio to ${SERIAL_PORT}"
echo ""
echo "  3. Start the services:"
echo -e "     ${YELLOW}sudo systemctl start meshbbs${NC}"
echo -e "     ${YELLOW}sudo systemctl start meshbbs-web${NC}"
echo ""
echo "  4. Check the logs:"
echo -e "     ${YELLOW}sudo journalctl -u meshbbs -f${NC}"
echo ""
echo "  5. Access the web interface at:"
echo -e "     ${BLUE}http://$(hostname -I | awk '{print $1}'):8080${NC}"
echo ""
echo "Default credentials:"
echo -e "  Username: ${YELLOW}admin${NC}"
echo -e "  Password: ${YELLOW}meshbbs123${NC}"
echo -e "  ${RED}(Change these immediately after first login!)${NC}"
echo ""
