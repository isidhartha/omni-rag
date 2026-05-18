#!/usr/bin/env bash
set -euo pipefail

echo "=== OmniRAG Setup ==="

python3 -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'" || {
    echo "ERROR: Python 3.11+ is required"
    exit 1
}

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env — add your OPENAI_API_KEY"
fi

cd backend
pip install -r requirements.txt

echo ""
echo "=== Setup Complete ==="
echo "Start with: docker-compose up --build"
