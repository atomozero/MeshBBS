# MeshBBS Installation Guide

This guide covers installation of MeshBBS on a Raspberry Pi.

## Prerequisites

### Hardware Requirements

- **Raspberry Pi 3B+, 4, or 5** (2GB+ RAM recommended)
- **MicroSD Card** (16GB+ recommended)
- **MeshCore Companion Radio** (Heltec V3, T-Beam, or compatible device)
- **USB Cable** to connect companion radio to Pi

### Software Requirements

- **Raspberry Pi OS** (64-bit recommended) or **Debian-based Linux**
- **Python 3.11+**
- **Node.js 20+** (for web interface)

## Quick Installation

### 1. Download MeshBBS

```bash
# Clone the repository
git clone https://github.com/meshbbs/meshbbs.git
cd meshbbs
```

### 2. Run the Installation Script

```bash
# Make the script executable
chmod +x deploy/install.sh

# Run as root
sudo ./deploy/install.sh
```

The installer will:
- Install system dependencies
- Create a `meshbbs` user
- Set up Python virtual environment
- Install the web interface
- Configure systemd services
- Generate a secure JWT secret

### 3. Configure MeshBBS

Edit the configuration file:

```bash
sudo nano /var/lib/meshbbs/config.env
```

Key settings to review:

```bash
# BBS Identity
BBS_NAME=MeshBBS
BBS_WELCOME="Welcome to MeshBBS!"

# Serial Port - adjust if needed
SERIAL_PORT=/dev/ttyUSB0
BAUD_RATE=115200

# Admin credentials - CHANGE THESE!
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
```

### 4. Connect Your Companion Radio

MeshBBS supporta tre metodi di connessione:

#### Option A: USB Serial Connection (Recommended)

1. Flash your device with USB Serial Companion firmware
2. Connect via USB to the Raspberry Pi
3. Check the serial port:
   ```bash
   ls -la /dev/ttyUSB*
   ls -la /dev/ttyACM*
   ```

#### Option B: BLE (Bluetooth Low Energy) Connection

1. Flash your device with BLE Companion firmware
2. Pair the device with your Raspberry Pi:
   ```bash
   bluetoothctl
   > scan on
   > pair 12:34:56:78:90:AB
   > exit
   ```
3. Configure BLE connection in config.env:
   ```bash
   CONNECTION_TYPE=ble
   BLE_ADDRESS=12:34:56:78:90:AB
   BLE_PIN=123456  # Optional, for secure pairing
   ```

#### Option C: TCP Connection

1. Flash your device with TCP Companion firmware
2. Configure TCP connection in config.env:
   ```bash
   CONNECTION_TYPE=tcp
   TCP_HOST=192.168.1.100
   TCP_PORT=4403
   ```

### 5. Start Services

```bash
# Start the BBS core service
sudo systemctl start meshbbs

# Start the web API service
sudo systemctl start meshbbs-web

# Enable auto-start on boot
sudo systemctl enable meshbbs
sudo systemctl enable meshbbs-web
```

### 6. Verify Installation

```bash
# Check service status
sudo systemctl status meshbbs
sudo systemctl status meshbbs-web

# View logs
sudo journalctl -u meshbbs -f
```

### 7. Access Web Interface

Open a browser and navigate to:
```
http://<raspberry-pi-ip>:8080
```

Default credentials:
- **Username:** admin
- **Password:** meshbbs123 (or whatever you set)

---

## Manual Installation

If you prefer manual installation:

### 1. Install System Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git sqlite3

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. Create User and Directories

```bash
sudo useradd -r -s /bin/false -d /opt/meshbbs meshbbs
sudo usermod -aG dialout meshbbs

sudo mkdir -p /opt/meshbbs
sudo mkdir -p /var/lib/meshbbs/backups
sudo mkdir -p /var/log/meshbbs
```

### 3. Clone Repository

```bash
sudo git clone https://github.com/meshbbs/meshbbs.git /opt/meshbbs
```

### 4. Setup Python Environment

```bash
cd /opt/meshbbs
sudo python3 -m venv venv
sudo ./venv/bin/pip install -r requirements.txt
```

### 5. Build Web Interface

```bash
cd /opt/meshbbs/web
sudo npm install
sudo npm run build
```

### 6. Create Configuration

```bash
sudo cat > /var/lib/meshbbs/config.env << EOF
BBS_NAME=MeshBBS
SERIAL_PORT=/dev/ttyUSB0
DATABASE_PATH=/var/lib/meshbbs/meshbbs.db
WEB_HOST=0.0.0.0
WEB_PORT=8080
JWT_SECRET=$(openssl rand -hex 32)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=meshbbs123
EOF

sudo chmod 600 /var/lib/meshbbs/config.env
```

### 7. Install Systemd Services

```bash
sudo cp /opt/meshbbs/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable meshbbs meshbbs-web
```

### 8. Set Permissions

```bash
sudo chown -R meshbbs:meshbbs /opt/meshbbs
sudo chown -R meshbbs:meshbbs /var/lib/meshbbs
sudo chown -R meshbbs:meshbbs /var/log/meshbbs
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BBS_NAME` | MeshBBS | Display name for the BBS |
| `BBS_WELCOME` | Welcome! | Welcome message for users |
| `SERIAL_PORT` | /dev/ttyUSB0 | Companion radio serial port |
| `BAUD_RATE` | 115200 | Serial baud rate |
| `DATABASE_PATH` | /var/lib/meshbbs/meshbbs.db | SQLite database path |
| `WEB_HOST` | 0.0.0.0 | Web server bind address |
| `WEB_PORT` | 8080 | Web server port |
| `JWT_SECRET` | (generated) | JWT signing secret |
| `JWT_EXPIRE_MINUTES` | 30 | Token expiration time |
| `ADMIN_USERNAME` | admin | Admin username |
| `ADMIN_PASSWORD` | meshbbs123 | Admin password |
| `LOG_LEVEL` | INFO | Logging level |
| `LOG_FILE` | /var/log/meshbbs/meshbbs.log | Log file path |
| `BACKUP_ENABLED` | true | Enable automatic backups |
| `BACKUP_INTERVAL_HOURS` | 24 | Backup frequency |
| `RATE_LIMIT_ENABLED` | true | Enable rate limiting |
| `RATE_LIMIT_COMMANDS_PER_MINUTE` | 30 | Max commands per minute |

---

## Troubleshooting

### Service Won't Start

1. Check logs:
   ```bash
   sudo journalctl -u meshbbs -n 50
   ```

2. Verify configuration:
   ```bash
   sudo cat /var/lib/meshbbs/config.env
   ```

3. Check file permissions:
   ```bash
   ls -la /opt/meshbbs
   ls -la /var/lib/meshbbs
   ```

### Serial Port Not Found

1. Check connected devices:
   ```bash
   dmesg | grep tty
   ls -la /dev/tty*
   ```

2. Verify user permissions:
   ```bash
   groups meshbbs
   ```
   Should include `dialout`

3. Try different port in config:
   ```bash
   SERIAL_PORT=/dev/ttyACM0
   ```

### Web Interface Not Loading

1. Check if service is running:
   ```bash
   sudo systemctl status meshbbs-web
   ```

2. Check firewall:
   ```bash
   sudo ufw status
   sudo ufw allow 8080/tcp
   ```

3. Test locally:
   ```bash
   curl http://localhost:8080/api/v1/health
   ```

### Database Errors

1. Check database file:
   ```bash
   ls -la /var/lib/meshbbs/meshbbs.db
   ```

2. Check disk space:
   ```bash
   df -h
   ```

3. Backup and recreate:
   ```bash
   sudo mv /var/lib/meshbbs/meshbbs.db /var/lib/meshbbs/meshbbs.db.bak
   sudo systemctl restart meshbbs
   ```

---

## Updating

To update MeshBBS:

```bash
cd meshbbs
git pull
sudo ./deploy/update.sh --backup --restart
```

---

## Uninstalling

To completely remove MeshBBS:

```bash
sudo ./deploy/uninstall.sh
```

To keep your data:

```bash
sudo ./deploy/uninstall.sh --keep-data
```

---

## Getting Help

- **Issues:** https://github.com/meshbbs/meshbbs/issues
- **Documentation:** https://github.com/meshbbs/meshbbs/docs

---

## Security Notes

1. **Change default passwords** immediately after installation
2. **Use HTTPS** in production (configure with reverse proxy)
3. **Restrict network access** to trusted networks
4. **Keep system updated** with security patches
5. **Backup regularly** to prevent data loss
