#!/data/data/com.termux/files/usr/bin/bash
# Run script for AI Builder
cd "$(dirname "$0")"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

python main.py "$@"