#!/usr/bin/env bash
set -e

mkdir -p checkpoints

if [ ! -f checkpoints/best.pt ]; then
    echo "Downloading ForenSight model..."
    curl -L "$MODEL_URL" -o checkpoints/best.pt
fi

echo "Starting ForenSight..."
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"