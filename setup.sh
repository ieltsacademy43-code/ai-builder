#!/data/data/com.termux/files/usr/bin/bash
# Installation script for Termux
set -e

echo "========================================"
echo "  AI Builder - Phase 1 Installation"
echo "========================================"

# Update packages
pkg update -y && pkg upgrade -y

# Install Python and essentials
pkg install -y python python-pip git

# Install Termux API (optional, for device features)
pkg install -y termux-api 2>/dev/null || true

# Create virtual environment
echo "[*] Creating virtual environment..."
python -m venv venv 2>/dev/null || {
    echo "[!] venv not available, installing globally"
    pip install --upgrade pip
    pip install -r requirements.txt
    echo "[OK] Dependencies installed globally."
    exit 0
}

# Activate and install
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "========================================"
echo "  Installation Complete!"
echo "========================================"
echo ""
echo "To activate:  source venv/bin/activate"
echo "To run:       python main.py"
echo ""